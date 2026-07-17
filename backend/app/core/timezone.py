import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def get_timezone_aware_now() -> datetime:
    """Returns current datetime in the configured timezone, without tzinfo for SQLModel compatibility."""
    tz_str = os.getenv("TIMEZONE", "UTC")
    try:
        tz = ZoneInfo(tz_str)
        return datetime.now(tz).replace(tzinfo=None)
    except Exception:
        # Fallback to UTC if timezone is invalid
        return datetime.now(UTC).replace(tzinfo=None)
