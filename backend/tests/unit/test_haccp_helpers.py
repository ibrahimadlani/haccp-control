"""Unit tests for pure helper functions in HACCP and related service modules."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.modules.cleaning.models import ScheduleType
from app.modules.cleaning.service import _infer_schedule_type
from app.modules.haccp.models import TypeEvenementPointage
from app.modules.haccp.schemas import TimeclockStatus
import pytest
from fastapi import HTTPException

from app.modules.haccp.service import (
    _MAX_FUTURE_DELTA,
    _MAX_PAST_DELTA,
    _is_temperature_compliant,
    _normalize_for_site,
    _status_from_event,
    _validate_measurement_time,
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


# ── _validate_measurement_time ────────────────────────────────────────────────

_PARIS = ZoneInfo("Europe/Paris")


def _now_paris() -> datetime:
    return datetime.now(tz=_PARIS)


def test_validate_measurement_time_within_window_passes():
    recent = _now_paris() - (_MAX_PAST_DELTA - timedelta(minutes=1))
    _validate_measurement_time(recent)  # must not raise


def test_validate_measurement_time_exactly_at_past_boundary_passes():
    # Exactly at the boundary (now - 8h + 1s) must be accepted.
    at_boundary = _now_paris() - _MAX_PAST_DELTA + timedelta(seconds=1)
    _validate_measurement_time(at_boundary)  # must not raise


def test_validate_measurement_time_one_second_beyond_past_boundary_raises_422():
    too_old = _now_paris() - _MAX_PAST_DELTA - timedelta(seconds=1)
    with pytest.raises(HTTPException) as exc_info:
        _validate_measurement_time(too_old)
    assert exc_info.value.status_code == 422
    assert "8h" in exc_info.value.detail


def test_validate_measurement_time_well_in_past_raises_422():
    yesterday = _now_paris() - timedelta(days=1)
    with pytest.raises(HTTPException) as exc_info:
        _validate_measurement_time(yesterday)
    assert exc_info.value.status_code == 422


def test_validate_measurement_time_within_future_tolerance_passes():
    near_future = _now_paris() + (_MAX_FUTURE_DELTA - timedelta(seconds=1))
    _validate_measurement_time(near_future)  # must not raise


def test_validate_measurement_time_exactly_at_future_boundary_passes():
    at_boundary = _now_paris() + _MAX_FUTURE_DELTA
    _validate_measurement_time(at_boundary)  # must not raise


def test_validate_measurement_time_one_second_beyond_future_boundary_raises_422():
    too_future = _now_paris() + _MAX_FUTURE_DELTA + timedelta(seconds=1)
    with pytest.raises(HTTPException) as exc_info:
        _validate_measurement_time(too_future)
    assert exc_info.value.status_code == 422
    assert "5 min" in exc_info.value.detail


def test_validate_measurement_time_preserves_timezone():
    # Validation must work for any timezone-aware datetime, not just Paris.
    utc_recent = datetime.now(tz=UTC) - timedelta(hours=1)
    _validate_measurement_time(utc_recent)  # must not raise


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
