from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pytest import MonkeyPatch

from app.core.timezone import get_timezone_aware_now


def test_get_timezone_aware_now_invalid_timezone(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("TIMEZONE", "Invalid/Timezone")
    result = get_timezone_aware_now()
    expected = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs((result - expected).total_seconds()) < 5
    assert result.tzinfo is None


def test_get_timezone_aware_now_valid_timezone(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("TIMEZONE", "Asia/Kolkata")
    result = get_timezone_aware_now()
    expected = datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)

    assert abs((result - expected).total_seconds()) < 5
    assert result.tzinfo is None
