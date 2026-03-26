"""Google Cloud Storage service for media uploads."""

import uuid
from datetime import timedelta
from typing import Any

from google.cloud.storage import Bucket, Client  # type: ignore[import-untyped]
from google.oauth2 import service_account


class GCSStorageService:
    """GCS storage service for media uploads.

    organization_id and decrypted config from OrganizationProvider.
    """

    def __init__(self, organization_id: int, config: dict[str, Any]):
        self.organization_id = organization_id
        self.config = config
        self._client: Client | None = None
        self._bucket: Bucket | None = None

    def initialize_client(self) -> Client:
        """Lazy initialization of GCS client from config."""
        if self._client is None:
            credentials_info = {
                "type": self.config["type"],
                "project_id": self.config["project_id"],
                "private_key_id": self.config["private_key_id"],
                "private_key": self.config["private_key"],
                "client_email": self.config["client_email"],
                "client_id": self.config["client_id"],
                "auth_uri": self.config["auth_uri"],
                "token_uri": self.config["token_uri"],
                "auth_provider_x509_cert_url": self.config[
                    "auth_provider_x509_cert_url"
                ],
                "client_x509_cert_url": self.config["client_x509_cert_url"],
            }
            credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
                credentials_info
            )
            self._client = Client(
                project=self.config["project_id"], credentials=credentials
            )
        return self._client

    def _get_bucket(self) -> Bucket:
        """Get the configured GCS bucket."""
        if self._bucket is None:
            client = self.initialize_client()
            self._bucket = client.bucket(self.config["bucket_name"])
        return self._bucket

    def test_connection(self) -> bool:
        """Test GCS connectivity by checking if bucket exists."""
        try:
            bucket = self._get_bucket()
            # Check if bucket exists by getting its metadata
            bucket.reload()
            return True
        except Exception:
            return False

    def upload(self, file_content: bytes, gcs_path: str, content_type: str) -> str:
        """Upload file to GCS and return the GCS path.

        Args:
            file_content: The file content as bytes
            gcs_path: The destination path in GCS (e.g., "org_1/questions/q_123.png")
            content_type: MIME type of the file

        Returns:
            The GCS path where the file was uploaded
        """
        bucket = self._get_bucket()
        blob = bucket.blob(gcs_path)
        blob.upload_from_string(file_content, content_type=content_type)
        return gcs_path

    def delete(self, gcs_path: str) -> bool:
        """Delete file from GCS.

        Args:
            gcs_path: The path of the file to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(gcs_path)
            if blob.exists():
                blob.delete()
                return True
            return False
        except Exception:
            return False

    def generate_signed_url(self, gcs_path: str) -> str:
        """Generate a signed URL for temporary access to a GCS object.

        Args:
            gcs_path: The path of the file in GCS

        Returns:
            A signed URL with configured expiration time
        """
        bucket = self._get_bucket()
        blob = bucket.blob(gcs_path)

        expiration_minutes = self.config.get("signed_url_expiration_minutes", 60)
        expiration = timedelta(minutes=expiration_minutes)

        url: str = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET",
        )
        return url

    def generate_media_path(
        self,
        question_id: int,
        file_extension: str,
        option_id: int | None = None,
    ) -> str:
        """Generate a unique GCS path for media upload.

        Args:
            question_id: The question ID
            file_extension: File extension (e.g., ".png", ".jpg")
            option_id: Optional option ID for option-level media

        Returns:
            A unique path like "org_1/questions/q_123_abc123.png"
            or "org_1/questions/q_123_opt_1_abc123.png" for options
        """
        unique_id = uuid.uuid4().hex[:12]

        if option_id is not None:
            return (
                f"org_{self.organization_id}/questions/"
                f"q_{question_id}_opt_{option_id}_{unique_id}{file_extension}"
            )
        return (
            f"org_{self.organization_id}/questions/"
            f"q_{question_id}_{unique_id}{file_extension}"
        )

    def file_exists(self, gcs_path: str) -> bool:
        """Check if a file exists in GCS.

        Args:
            gcs_path: The path of the file in GCS

        Returns:
            True if file exists, False otherwise
        """
        try:
            bucket = self._get_bucket()
            blob = bucket.blob(gcs_path)
            return bool(blob.exists())
        except Exception:
            return False
