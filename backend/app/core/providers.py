"""Seed default providers."""

from sqlmodel import Session, select

from app.models.provider import Provider, ProviderType

DEFAULT_PROVIDERS = [
    {
        "name": "Big Query",
        "provider_type": ProviderType.BIGQUERY,
        "description": "Google BigQuery data sync provider",
    },
    {
        "name": "Google Slides",
        "provider_type": ProviderType.GOOGLE_SLIDES,
        "description": "Google Slides certificate provider",
    },
    {
        "name": "Google Cloud Storage",
        "provider_type": ProviderType.GCS,
        "description": "Google Cloud Storage media provider",
    },
]


def init_providers(session: Session) -> None:
    """Create default providers if they don't exist."""
    for provider_data in DEFAULT_PROVIDERS:
        existing = session.exec(
            select(Provider).where(
                Provider.provider_type == provider_data["provider_type"]
            )
        ).first()
        if not existing:
            session.add(Provider(**provider_data))
    session.commit()
