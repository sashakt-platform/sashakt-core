from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic.networks import EmailStr

from app.api.deps import CurrentUser, get_current_active_superuser
from app.core.timezone import get_timezone_aware_now
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


def get_current_time() -> datetime:
    """Returns the current datetime in the configured timezone."""
    return get_timezone_aware_now()


def clean_value(value: str | None) -> str:
    """Safely strip string values."""
    return (value or "").strip()


def get_current_user_location_ids(
    current_user: CurrentUser,
) -> tuple[Literal["district", "state"] | None, set[int] | None]:
    """Returns the location scope level and IDs for the current user.
    District takes precedence over state if both are assigned.
    """
    user_location_level: Literal["district", "state"] | None = None
    user_location_ids: set[int] | None = None
    if current_user.districts and len(current_user.districts) > 0:
        user_location_level = "district"
        user_location_ids = {
            district.id
            for district in current_user.districts
            if district.id is not None
        }
    elif current_user.states and len(current_user.states) > 0:
        user_location_level = "state"
        user_location_ids = {
            state.id for state in current_user.states if state.id is not None
        }

    return user_location_level, user_location_ids
