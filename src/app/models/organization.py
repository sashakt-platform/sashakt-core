from app.models.location import BaseModel
from typing import Optional
from sqlmodel import Field


class Organization(BaseModel, table=True):
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None, nullable=True)
    is_deleted: bool = Field(default=False, nullable=False)
