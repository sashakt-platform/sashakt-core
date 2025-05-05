from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic.networks import EmailStr
from sqlmodel import SQLModel

from app.api.deps import get_current_active_superuser
from app.models import Message
from app.utils import generate_test_email, send_email

router = APIRouter(prefix="/utils", tags=["utils"])


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/")
async def health_check() -> bool:
    return True


# Helper Function to refine query by applying ordering and pagination
def get_refined_query(query: Any, Table: type[SQLModel], filters: Any) -> Any:
    for order in filters.order_by:
        is_desc = order.startswith("-")
        order = order.lstrip("-")
        column = getattr(Table, order, None)
        if column is None:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid order_by field: {order}",
            )
        query = query.order_by(column.desc() if is_desc else column)
    query = query.offset(filters.skip).limit(filters.limit)
    return query
