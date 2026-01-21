from datetime import datetime
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from app.core.timezone import get_timezone_aware_now

if TYPE_CHECKING:
    from app.models.test import Test


class CertificateBase(SQLModel):
    name: str = Field(nullable=False, index=True, description="Certificate name")
    description: str | None = Field(
        default=None, nullable=True, description="Certificate description"
    )
    url: str = Field(
        nullable=False,
        description="Certificate template file URL",
    )
    is_active: bool = Field(default=True)


class Certificate(CertificateBase, table=True):
    id: int | None = Field(default=None, primary_key=True)

    created_date: datetime | None = Field(default_factory=get_timezone_aware_now)
    modified_date: datetime | None = Field(
        default_factory=get_timezone_aware_now,
        sa_column_kwargs={"onupdate": get_timezone_aware_now},
    )

    # relationship with Test
    tests: list["Test"] = Relationship(back_populates="certificate")


class CertificateCreate(CertificateBase):
    pass


class CertificatePublic(CertificateBase):
    id: int
    created_date: datetime
    modified_date: datetime


class CertificateUpdate(CertificateBase):
    pass
