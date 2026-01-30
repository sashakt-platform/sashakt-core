import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlmodel import JSON, Field, Relationship, SQLModel, UniqueConstraint
from typing_extensions import TypedDict

from app.core.timezone import get_timezone_aware_now

if TYPE_CHECKING:
    from app.models import Organization, User
    from app.models.candidate import CandidateTest
    from app.models.entity import EntityType
    from app.models.test import Test


class FormFieldType(str, enum.Enum):
    """Types of form fields available in the system"""

    # Core user fields
    FULL_NAME = "full_name"
    EMAIL = "email"
    PHONE = "phone"

    # Custom fields
    TEXT = "text"
    TEXTAREA = "textarea"
    NUMBER = "number"
    DATE = "date"
    SELECT = "select"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    MULTI_SELECT = "multi_select"

    # Entity field
    ENTITY = "entity"

    # Location fields
    STATE = "state"
    DISTRICT = "district"
    BLOCK = "block"


class FormFieldOption(TypedDict):
    """Represents a single option for select/radio/checkbox fields"""

    id: int
    label: str
    value: str


class FormFieldValidation(TypedDict, total=False):
    """Validation rules for a form field"""

    min_length: int | None
    max_length: int | None
    min_value: float | None
    max_value: float | None
    pattern: str | None
    custom_error_message: str | None


# ============== Form Models ==============


class FormBase(SQLModel):
    name: str = Field(
        nullable=False,
        index=True,
        description="Name of the form",
    )
    description: str | None = Field(
        default=None,
        nullable=True,
        description="Description of the form",
    )
    is_active: bool = Field(default=True)


class Form(FormBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )
    organization_id: int = Field(
        foreign_key="organization.id",
        nullable=False,
        description="Organization ID to which the form belongs",
    )
    created_by_id: int = Field(
        foreign_key="user.id",
        nullable=False,
        description="User ID who created the form",
    )

    # Relationships
    fields: list["FormField"] = Relationship(
        back_populates="form",
        sa_relationship_kwargs={"order_by": "FormField.order"},
    )
    tests: list["Test"] = Relationship(back_populates="form")
    organization: "Organization" = Relationship(back_populates="forms")
    created_by: "User" = Relationship(back_populates="forms")
    responses: list["FormResponse"] = Relationship(back_populates="form")


class FormCreate(FormBase):
    organization_id: int | None = Field(
        default=None,
        description="Organization ID. If not provided, uses current user's organization.",
    )


class FormPublic(FormBase):
    id: int
    created_date: datetime
    modified_date: datetime
    organization_id: int
    created_by_id: int
    fields: list["FormFieldPublic"] = []


class FormUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


# ============== FormField Models ==============


class FormFieldBase(SQLModel):
    field_type: FormFieldType = Field(
        nullable=False,
        description="Type of the form field",
    )
    label: str = Field(
        nullable=False,
        description="Display label for the field",
    )
    name: str = Field(
        nullable=False,
        description="Field name/key used in form submissions",
    )
    placeholder: str | None = Field(
        default=None,
        description="Placeholder text for the field",
    )
    help_text: str | None = Field(
        default=None,
        description="Help text displayed below the field",
    )
    is_required: bool = Field(
        default=False,
        description="Whether this field is required",
    )
    order: int = Field(
        default=0,
        description="Display order of the field within the form",
    )
    options: list[FormFieldOption] | None = Field(
        sa_type=JSON,
        default=None,
        description="Options for select/radio/checkbox fields",
    )
    validation: FormFieldValidation | None = Field(
        sa_type=JSON,
        default=None,
        description="Validation rules for the field",
    )
    default_value: str | None = Field(
        default=None,
        description="Default value for the field",
    )
    entity_type_id: int | None = Field(
        default=None,
        foreign_key="entitytype.id",
        nullable=True,
        description="Entity type to filter entities for entity field type",
    )


class FormField(FormFieldBase, table=True):
    __tablename__ = "form_field"

    id: int | None = Field(default=None, primary_key=True)
    form_id: int = Field(
        foreign_key="form.id",
        ondelete="CASCADE",
        nullable=False,
        description="Form ID to which this field belongs",
    )
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )

    # Relationships
    form: "Form" = Relationship(back_populates="fields")
    entity_type: "EntityType" = Relationship()


class FormFieldCreate(FormFieldBase):
    pass


class FormFieldPublic(FormFieldBase):
    id: int
    form_id: int
    created_date: datetime
    modified_date: datetime


class FormFieldUpdate(SQLModel):
    label: str | None = None
    name: str | None = None
    placeholder: str | None = None
    help_text: str | None = None
    is_required: bool | None = None
    order: int | None = None
    options: list[FormFieldOption] | None = None
    validation: FormFieldValidation | None = None
    default_value: str | None = None
    entity_type_id: int | None = None


class FormFieldReorder(SQLModel):
    """Request model for reordering fields"""

    field_ids: list[int] = Field(
        description="List of field IDs in the desired order",
    )


# ============== FormResponse Models ==============


class FormResponseBase(SQLModel):
    responses: dict[str, Any] = Field(
        sa_type=JSON,
        default_factory=dict,
        description="Key-value mapping of field_name to response value",
    )


class FormResponse(FormResponseBase, table=True):
    __tablename__ = "form_response"
    __table_args__ = (UniqueConstraint("candidate_test_id", "form_id"),)

    id: int | None = Field(default=None, primary_key=True)
    candidate_test_id: int = Field(
        foreign_key="candidate_test.id",
        ondelete="CASCADE",
        nullable=False,
        description="CandidateTest ID this response belongs to",
    )
    form_id: int = Field(
        foreign_key="form.id",
        ondelete="CASCADE",
        nullable=False,
        description="Form ID this response is for",
    )
    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)

    # Relationships
    candidate_test: "CandidateTest" = Relationship(back_populates="form_responses")
    form: "Form" = Relationship(back_populates="responses")


class FormResponsePublic(FormResponseBase):
    id: int
    candidate_test_id: int
    form_id: int
    created_date: datetime
