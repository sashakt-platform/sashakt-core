from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel, UniqueConstraint

if TYPE_CHECKING:
    from app.models import Test, User


# Linking Tables between Candidate and Test
class CandidateTestBase(SQLModel):
    __test__ = False
    test_id: int = Field(foreign_key="test.id", ondelete="CASCADE")
    candidate_id: int = Field(foreign_key="candidate.id", ondelete="CASCADE")
    device: str = Field(nullable=False)
    consent: bool = Field(default=False, nullable=False)
    start_time: datetime = Field(nullable=False)
    end_time: datetime | None = Field(nullable=False, default=None)
    is_submitted: bool = Field(default=False, nullable=False)


class CandidateTest(CandidateTestBase, table=True):
    __tablename__ = "candidate_test"
    __test__ = False
    __table_args__ = (UniqueConstraint("test_id", "candidate_id"),)
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )


class CandidateTestCreate(CandidateTestBase):
    __test__ = False


class CandidateTestPublic(CandidateTestBase):
    __test__ = False
    id: int
    created_date: datetime
    modified_date: datetime


class CandidateTestUpdate(SQLModel):
    device: str
    consent: bool
    end_time: datetime | None
    is_submitted: bool


# Models for Candidates


class CandidateBase(SQLModel):
    user_id: int | None = Field(
        default=None, foreign_key="user.id", nullable=True, ondelete="CASCADE"
    )


class CandidateCreate(CandidateBase):
    pass


class Candidate(CandidateBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    modified_date: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column_kwargs={"onupdate": datetime.now(timezone.utc)},
    )
    is_active: bool | None = Field(default=None, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False)
    user: "User" = Relationship(back_populates="candidates")
    tests: list["Test"] | None = Relationship(
        back_populates="candidates", link_model=CandidateTest
    )


class CandidatePublic(CandidateBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool


class CandidateUpdate(CandidateBase):
    pass
