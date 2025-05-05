from sqlmodel import Field, SQLModel


# Generic message
class Message(SQLModel):
    message: str


class CommonFilters(SQLModel):
    limit: int = Field(
        10,
        gt=0,
        le=1000,
        title="Limit",
        description="Maximum number of entries to return",
    )
    skip: int = Field(0, ge=0, title="Skip", description="Number of rows to skip")
    is_active: bool | None = None
    is_deleted: bool | None = False  # Default to showing non-deleted questions
    order_by: list[str] = Field(
        default=["created_date"], title="Order by", description="Order by fields"
    )
