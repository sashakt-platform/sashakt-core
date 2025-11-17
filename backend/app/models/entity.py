from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.timezone import get_timezone_aware_now
from app.models.location import (
    Block,
    BlockPublic,
    District,
    DistrictPublic,
    State,
    StatePublic,
)
from app.models.organization import Organization

if TYPE_CHECKING:
    from app.models.user import User


class EntityTypeBase(SQLModel):
    name: str = Field(nullable=False, index=True, description="Name of the Entity Type")
    description: str | None = Field(
        default=None, nullable=True, description="Description of the Entity Type"
    )
    is_active: bool = Field(default=True)
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        description="Organization ID to which the Entity Type belongs",
    )


class EntityType(EntityTypeBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    entities: list["Entity"] = Relationship(back_populates="entity_type")
    created_by: "User" = Relationship(back_populates="entity_types")
    organization: "Organization" = Relationship(back_populates="entity_types")
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="User ID who created the Entity Type",
    )


class EntityTypeCreate(EntityTypeBase):
    pass


class EntityTypePublic(EntityTypeBase):
    id: int
    created_date: datetime
    modified_date: datetime
    created_by_id: int = Field(description="ID of the user who created the Entity Type")


class EntityTypeUpdate(EntityTypeBase):
    pass


class EntityBase(SQLModel):
    name: str = Field(nullable=False, index=True, description="Name of the Entity")
    description: str | None = Field(
        default=None, nullable=True, description="Description of the Entity"
    )
    is_active: bool = Field(default=True)


class Entity(EntityBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    entity_type_id: int | None = Field(
        default=None,
        foreign_key="entitytype.id",
        description="ID of the Entity Type to which the Entity should belong",
    )
    entity_type: "EntityType" = Relationship(back_populates="entities")
    state: "State" = Relationship(back_populates="entities")
    district: "District" = Relationship(back_populates="entities")
    block: "Block" = Relationship(back_populates="entities")

    created_by: "User" = Relationship(back_populates="entities")
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="User ID who created the Entity",
    )
    state_id: int | None = Field(
        default=None,
        nullable=True,
        foreign_key="state.id",
        description="ID of the state this entity is associated with",
    )
    district_id: int | None = Field(
        default=None,
        nullable=True,
        foreign_key="district.id",
        description="ID of the district this entity is associated with",
    )
    block_id: int | None = Field(
        default=None,
        nullable=True,
        foreign_key="block.id",
        description="ID of the block this entity is associated with",
    )


class EntityCreate(EntityBase):
    entity_type_id: int | None = None
    state_id: int | None = None
    district_id: int | None = None
    block_id: int | None = None


class EntityPublic(EntityBase):
    id: int
    created_date: datetime
    modified_date: datetime
    entity_type: EntityType | None = None
    state: StatePublic | None = None
    district: DistrictPublic | None = None
    block: BlockPublic | None = None
    created_by_id: int


class EntityUpdate(EntityBase):
    entity_type_id: int | None = None
    state_id: int | None = None
    district_id: int | None = None
    block_id: int | None = None


class EntityBulkUploadResponse(SQLModel):
    message: str
    uploaded_entities: int
    success_entities: int
    failed_entities: int
    error_log: str | None
