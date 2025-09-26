import base64
import json
from typing import Any

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

from app.core.config import settings
from app.models.provider import ProviderType


class BigQueryConfig(BaseModel):
    """
    BigQuery configuration that accepts the service account JSON directly
    with optional dataset_id and other settings.
    """

    # Required service account fields
    type: str = Field(..., description="Service account type")
    project_id: str = Field(..., description="Google Cloud Project ID")
    private_key_id: str = Field(..., description="Private key ID")
    private_key: str = Field(..., description="Private key")
    client_email: str = Field(..., description="Service account email")
    client_id: str = Field(..., description="Client ID")
    auth_uri: str = Field(..., description="Auth URI")
    token_uri: str = Field(..., description="Token URI")
    auth_provider_x509_cert_url: str = Field(..., description="Auth provider cert URL")
    client_x509_cert_url: str = Field(..., description="Client cert URL")

    # Optional BigQuery-specific settings
    dataset_id: str = Field(
        default="sashakt_data",
        description="BigQuery dataset ID (organization suffix will be auto-added)",
    )
    table_prefix: str = Field(default="", description="Prefix for table names")
    sync_settings: dict[str, Any] = Field(
        default_factory=lambda: {"batch_size": 1000, "incremental": True},
        description="Sync configuration settings",
    )


class ProviderConfigService:
    def __init__(self) -> None:
        self._encryption_key = self._get_or_generate_key()

    def _get_or_generate_key(self) -> bytes:
        if settings.PROVIDER_ENCRYPTION_KEY:
            try:
                # Fernet expects the key as bytes, but in base64 format (not decoded)
                key_bytes = settings.PROVIDER_ENCRYPTION_KEY.encode()
                # Validate it's a proper Fernet key by trying to create a Fernet instance
                Fernet(key_bytes)
                return key_bytes
            except Exception as e:
                raise ValueError(f"Invalid PROVIDER_ENCRYPTION_KEY format: {e}")
        else:
            key = Fernet.generate_key()
            if settings.ENVIRONMENT != "local":
                raise ValueError(
                    "PROVIDER_ENCRYPTION_KEY must be set in non-local environments"
                )
            return key

    def encrypt_config(self, config: dict[str, Any]) -> str:
        fernet = Fernet(self._encryption_key)
        config_json = json.dumps(config)
        encrypted_data = fernet.encrypt(config_json.encode())
        return base64.urlsafe_b64encode(encrypted_data).decode()

    def decrypt_config(self, encrypted_config: str) -> dict[str, Any]:
        try:
            fernet = Fernet(self._encryption_key)
            encrypted_data = base64.urlsafe_b64decode(encrypted_config.encode())
            decrypted_data = fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except Exception as e:
            raise ValueError(f"Failed to decrypt provider configuration: {e}")

    def validate_provider_config(
        self, provider_type: ProviderType, config: dict[str, Any]
    ) -> dict[str, Any]:
        if provider_type == ProviderType.BIGQUERY:
            validated_config = BigQueryConfig(**config)
            return validated_config.model_dump()
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")

    def prepare_config_for_storage(
        self, provider_type: ProviderType, config: dict[str, Any]
    ) -> str:
        validated_config = self.validate_provider_config(provider_type, config)
        return self.encrypt_config(validated_config)

    def get_config_for_use(self, encrypted_config: str) -> dict[str, Any]:
        return self.decrypt_config(encrypted_config)

    @staticmethod
    def generate_encryption_key() -> str:
        key = Fernet.generate_key()
        return base64.urlsafe_b64encode(key).decode()


provider_config_service = ProviderConfigService()
