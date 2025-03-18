from datetime import datetime, timezone

from sqlmodel import Field, Relationship, SQLModel

from ..models.user import User


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
    user: User | None = Relationship(back_populates="candidates")


class CandidatePublic(CandidateBase):
    id: int
    created_date: datetime
    modified_date: datetime
    is_active: bool | None
    is_deleted: bool


class CandidateUpdate(CandidateBase):
    pass
