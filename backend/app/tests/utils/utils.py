import random
import string
from datetime import datetime

from fastapi.testclient import TestClient

from app.core.config import CURRENT_ZONE, settings


def random_lower_string() -> str:
    return "".join(random.choices(string.ascii_lowercase, k=32))


def random_email() -> str:
    return f"{random_lower_string()}@{random_lower_string()}.com"


def get_superuser_token_headers(client: TestClient) -> dict[str, str]:
    login_data = {
        "username": settings.FIRST_SUPERUSER,
        "password": settings.FIRST_SUPERUSER_PASSWORD,
    }
    r = client.post(f"{settings.API_V1_STR}/login/access-token", data=login_data)
    tokens = r.json()
    a_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {a_token}"}
    return headers


def check_created_modified_date(
    data_db: dict[str, datetime], created_date_public: str, modified_date_public: str
) -> None:
    """
    Check if the modified date in the API response matches the expected IST date.
    """
    assert data_db is not None, "Entity not found in database"

    # The datetime from DB is in UTC]
    created_date_utc = data_db.get("created_date")
    modified_date_utc = data_db.get("modified_date")

    # Convert to IST (which is what the API returns)
    created_date_ist = (
        created_date_utc.astimezone(CURRENT_ZONE).replace(tzinfo=None)
        if created_date_utc
        else None
    )
    modified_date_ist = (
        modified_date_utc.astimezone(CURRENT_ZONE).replace(tzinfo=None)
        if modified_date_utc
        else None
    )

    # Parse the API response times (which are in string format)
    api_created_time = (
        datetime.fromisoformat(str(created_date_public))
        if created_date_public
        else None
    )
    api_modified_time = (
        datetime.fromisoformat(str(modified_date_public))
        if modified_date_public
        else None
    )

    # Compare the times
    print("API Created Time:", api_created_time)
    print("DB Created Time:", created_date_ist)

    # Truncate microseconds for reliable comparison
    if api_created_time and created_date_ist:
        api_created_time = api_created_time.replace(microsecond=0)
        created_date_ist = created_date_ist.replace(microsecond=0)
    if api_modified_time and modified_date_ist:
        api_modified_time = api_modified_time.replace(microsecond=0)
        modified_date_ist = modified_date_ist.replace(microsecond=0)

    assert api_created_time == created_date_ist
    assert api_modified_time == modified_date_ist
