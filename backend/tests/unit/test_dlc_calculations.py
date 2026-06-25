"""Unit tests for the calculate_dlc_secondaire pure function."""

from datetime import date, timedelta

import pytest

from app.modules.receptions.service import calculate_dlc_secondaire


def test_dlc_secondaire_uses_duration_when_before_dluo():
    """Opening today + 3 days is less than DLUO in 10 days → use duration."""
    today = date(2026, 1, 1)
    dluo = date(2026, 1, 11)
    result = calculate_dlc_secondaire(today, dluo, 3)
    assert result == date(2026, 1, 4)


def test_dlc_secondaire_caps_at_dluo_primaire():
    """Opening today + 10 days exceeds DLUO in 3 days → cap at DLUO."""
    today = date(2026, 1, 1)
    dluo = date(2026, 1, 4)
    result = calculate_dlc_secondaire(today, dluo, 10)
    assert result == dluo


def test_dlc_secondaire_equals_dluo_when_duration_matches_exactly():
    """Opening today + 5 days == DLUO in 5 days → result equals DLUO."""
    today = date(2026, 1, 1)
    dluo = today + timedelta(days=5)
    result = calculate_dlc_secondaire(today, dluo, 5)
    assert result == dluo


def test_dlc_secondaire_same_day_opening_and_dluo():
    """DLUO is today and duration is 1 day → result is still today (cap wins)."""
    today = date(2026, 6, 24)
    result = calculate_dlc_secondaire(today, today, 1)
    assert result == today


def test_dlc_secondaire_one_day_duration():
    """Duration of 1 day with DLUO comfortably in the future."""
    today = date(2026, 1, 1)
    dluo = date(2026, 6, 30)
    result = calculate_dlc_secondaire(today, dluo, 1)
    assert result == date(2026, 1, 2)


def test_dlc_secondaire_result_never_exceeds_dluo():
    """Property: for any valid inputs, result must not exceed dluo_primaire."""
    today = date(2026, 3, 15)
    dluo = date(2026, 4, 1)
    for days in [1, 3, 7, 14, 30, 60]:
        result = calculate_dlc_secondaire(today, dluo, days)
        assert result <= dluo


def test_dlc_secondaire_refuses_zero_duration():
    """Duration of 0 is rejected at the schema level, but also defensively here."""
    today = date(2026, 1, 1)
    dluo = date(2026, 6, 1)
    with pytest.raises(ValueError):
        calculate_dlc_secondaire(today, dluo, 0)


def test_dlc_secondaire_refuses_negative_duration():
    """Negative duration must also be rejected."""
    today = date(2026, 1, 1)
    dluo = date(2026, 6, 1)
    with pytest.raises(ValueError):
        calculate_dlc_secondaire(today, dluo, -1)
