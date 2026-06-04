"""Unit tests for app/core/time_utils.py."""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.time_utils import now_for_site


def test_now_for_site_returns_timezone_aware_datetime():
    result = now_for_site("Europe/Paris")
    assert result.tzinfo is not None


def test_now_for_site_uses_correct_timezone():
    result = now_for_site("America/New_York")
    expected_tz = ZoneInfo("America/New_York")
    # The key attribute is that the timezone key matches
    assert result.tzinfo.key == expected_tz.key


def test_now_for_site_europe_paris():
    result = now_for_site("Europe/Paris")
    paris_tz = ZoneInfo("Europe/Paris")
    assert result.tzinfo.key == paris_tz.key


def test_now_for_site_different_timezones_differ():
    paris = now_for_site("Europe/Paris")
    tokyo = now_for_site("Asia/Tokyo")
    # Both are aware datetimes but with different tzinfo
    assert paris.tzinfo != tokyo.tzinfo


def test_now_for_site_returns_current_time():
    before = datetime.now(ZoneInfo("Europe/Paris"))
    result = now_for_site("Europe/Paris")
    after = datetime.now(ZoneInfo("Europe/Paris"))
    # Result should be between before and after (within a second)
    assert before <= result <= after
