"""Unit tests for pure helper functions in HACCP and related service modules."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.modules.cleaning.models import ScheduleType
from app.modules.cleaning.service import _infer_schedule_type
from app.modules.haccp.models import TypeEvenementPointage
from app.modules.haccp.schemas import TimeclockStatus
from app.modules.haccp.service import (
    _is_temperature_compliant,
    _normalize_for_site,
    _status_from_event,
)
from app.modules.nonconformities.service import _deviation_celsius

# ── _is_temperature_compliant ─────────────────────────────────────────────────


def test_temperature_compliant_within_range():
    assert _is_temperature_compliant(Decimal("2.0"), Decimal("0"), Decimal("4")) is True


def test_temperature_compliant_at_min_boundary():
    assert _is_temperature_compliant(Decimal("0"), Decimal("0"), Decimal("4")) is True


def test_temperature_compliant_at_max_boundary():
    assert _is_temperature_compliant(Decimal("4"), Decimal("0"), Decimal("4")) is True


def test_temperature_not_compliant_below_min():
    assert _is_temperature_compliant(Decimal("-1"), Decimal("0"), Decimal("4")) is False


def test_temperature_not_compliant_above_max():
    assert _is_temperature_compliant(Decimal("5"), Decimal("0"), Decimal("4")) is False


def test_temperature_compliant_negative_range():
    # Frozen food range: -25°C to -18°C
    assert _is_temperature_compliant(Decimal("-20"), Decimal("-25"), Decimal("-18")) is True
    assert _is_temperature_compliant(Decimal("-15"), Decimal("-25"), Decimal("-18")) is False


# ── _status_from_event ────────────────────────────────────────────────────────


def test_status_from_event_none_returns_clocked_out():
    assert _status_from_event(None) == TimeclockStatus.CLOCKED_OUT


def test_status_from_event_clock_in_returns_active():
    assert _status_from_event(TypeEvenementPointage.CLOCK_IN) == TimeclockStatus.ACTIVE


def test_status_from_event_break_end_returns_active():
    assert _status_from_event(TypeEvenementPointage.BREAK_END) == TimeclockStatus.ACTIVE


def test_status_from_event_break_start_returns_on_break():
    assert _status_from_event(TypeEvenementPointage.BREAK_START) == TimeclockStatus.ON_BREAK


def test_status_from_event_clock_out_returns_clocked_out():
    assert _status_from_event(TypeEvenementPointage.CLOCK_OUT) == TimeclockStatus.CLOCKED_OUT


# ── _normalize_for_site ───────────────────────────────────────────────────────


def test_normalize_for_site_none_returns_current_time():
    result = _normalize_for_site(None, "Europe/Paris")
    assert result.tzinfo is not None
    assert result.tzinfo.key == ZoneInfo("Europe/Paris").key


def test_normalize_for_site_naive_datetime_attaches_timezone():
    naive = datetime(2024, 6, 1, 10, 0, 0)
    result = _normalize_for_site(naive, "Europe/Paris")
    assert result.tzinfo is not None
    assert result.year == 2024 and result.hour == 10


def test_normalize_for_site_aware_datetime_converts_timezone():
    utc_dt = datetime(2024, 6, 1, 8, 0, 0, tzinfo=UTC)
    result = _normalize_for_site(utc_dt, "Europe/Paris")
    # Paris is UTC+2 in summer, so 8 UTC = 10 Paris
    assert result.tzinfo is not None
    assert result.hour == 10


# ── _deviation_celsius ────────────────────────────────────────────────────────


def test_deviation_celsius_within_range_returns_zero():
    assert _deviation_celsius(Decimal("2"), Decimal("0"), Decimal("4")) == Decimal("0")


def test_deviation_celsius_at_boundary_returns_zero():
    assert _deviation_celsius(Decimal("0"), Decimal("0"), Decimal("4")) == Decimal("0")
    assert _deviation_celsius(Decimal("4"), Decimal("0"), Decimal("4")) == Decimal("0")


def test_deviation_celsius_below_min():
    assert _deviation_celsius(Decimal("-2"), Decimal("0"), Decimal("4")) == Decimal("2")


def test_deviation_celsius_above_max():
    assert _deviation_celsius(Decimal("8"), Decimal("0"), Decimal("4")) == Decimal("4")


def test_deviation_celsius_always_positive():
    result = _deviation_celsius(Decimal("-5"), Decimal("0"), Decimal("4"))
    assert result > 0


# ── _infer_schedule_type ──────────────────────────────────────────────────────


def test_infer_schedule_type_opening_before_noon():
    fixed_morning = datetime(2024, 6, 1, 9, 0, 0, tzinfo=ZoneInfo("Europe/Paris"))
    with patch("app.modules.cleaning.service.now_for_site", return_value=fixed_morning):
        result = _infer_schedule_type("Europe/Paris")
    assert result == ScheduleType.OPENING


def test_infer_schedule_type_closing_at_thirteen():
    fixed_afternoon = datetime(2024, 6, 1, 13, 0, 0, tzinfo=ZoneInfo("Europe/Paris"))
    with patch("app.modules.cleaning.service.now_for_site", return_value=fixed_afternoon):
        result = _infer_schedule_type("Europe/Paris")
    assert result == ScheduleType.CLOSING


def test_infer_schedule_type_closing_after_thirteen():
    fixed_evening = datetime(2024, 6, 1, 19, 0, 0, tzinfo=ZoneInfo("Europe/Paris"))
    with patch("app.modules.cleaning.service.now_for_site", return_value=fixed_evening):
        result = _infer_schedule_type("Europe/Paris")
    assert result == ScheduleType.CLOSING


def test_infer_schedule_type_opening_just_before_thirteen():
    fixed = datetime(2024, 6, 1, 12, 59, 0, tzinfo=ZoneInfo("Europe/Paris"))
    with patch("app.modules.cleaning.service.now_for_site", return_value=fixed):
        result = _infer_schedule_type("Europe/Paris")
    assert result == ScheduleType.OPENING
