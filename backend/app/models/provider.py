from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlmodel import JSON, Column, Field, Relationship, SQLModel

from app.core.timezone import get_timezone_aware_now

if TYPE_CHECKING:
    from app.models import Organization


class ProviderType(str, Enum):
    BIGQUERY = "BIGQUERY"


class ProviderBase(SQLModel):
    provider_type: ProviderType = Field(
        index=True,
        title="Provider Type",
        description="Type of data provider (BigQuery)",
    )
    name: str = Field(
        index=True,
        title="Provider Name",
        description="Human-readable name for the provider",
    )
    description: str | None = Field(
        default=None, title="Description", description="Description of the provider"
    )
    is_active: bool = Field(
        default=True,
        title="Is Active",
        description="Whether this provider type is active",
    )


class Provider(ProviderBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )

    # Relationships
    organization_providers: list["OrganizationProvider"] = Relationship(
        back_populates="provider"
    )


class OrganizationProviderBase(SQLModel):
    organization_id: int = Field(
        foreign_key="organization.id",
        title="Organization ID",
        description="ID of the organization",
    )
    provider_id: int = Field(
        foreign_key="provider.id", title="Provider ID", description="ID of the provider"
    )
    config_json: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON),
        title="Configuration JSON",
        description="Encrypted provider-specific configuration",
    )
    is_enabled: bool = Field(
        default=True,
        title="Is Enabled",
        description="Whether this provider is enabled for the organization",
    )
    last_sync_timestamp: datetime | None = Field(
        default=None,
        title="Last Sync Timestamp",
        description="Timestamp of the last successful sync",
    )


class OrganizationProvider(OrganizationProviderBase, table=True):
    __tablename__ = "organization_provider"
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )

    # Relationships
    organization: "Organization" = Relationship(back_populates="organization_providers")
    provider: Provider = Relationship(back_populates="organization_providers")


class ProviderCreate(ProviderBase):
    pass


class ProviderPublic(ProviderBase):
    id: int | None
    created_date: datetime | None
    modified_date: datetime | None


class ProviderUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class OrganizationProviderCreate(SQLModel):
    provider_id: int
    config_json: dict[str, Any] | None = None
    is_enabled: bool = True


class OrganizationProviderPublic(SQLModel):
    """
    Public representation of OrganizationProvider - excludes sensitive config_json
    """

    id: int | None
    organization_id: int
    provider_id: int
    is_enabled: bool
    last_sync_timestamp: datetime | None
    created_date: datetime | None
    modified_date: datetime | None
    provider: ProviderPublic


class OrganizationProviderUpdate(SQLModel):
    config_json: dict[str, Any] | None = None
    is_enabled: bool | None = None
    last_sync_timestamp: datetime | None = None


class ProviderSyncStatus(SQLModel):
    provider_id: int
    provider_name: str
    provider_type: ProviderType
    is_enabled: bool
    last_sync_timestamp: datetime | None
    sync_status: str  # "never_synced", "syncing", "success", "failed"
    error_message: str | None = None
