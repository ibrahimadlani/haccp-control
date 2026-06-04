"""Unit tests for app/core/role_utils.py."""

from unittest.mock import MagicMock

from app.core.role_utils import is_manager_role, is_platform_admin_role


def _make_role(nom_role: str, permissions: dict | None = None) -> MagicMock:
    role = MagicMock()
    role.nom_role = nom_role
    role.permissions = permissions or {}
    return role


# ── is_manager_role ────────────────────────────────────────────────────────────


def test_is_manager_role_none_returns_false():
    assert is_manager_role(None) is False


def test_is_manager_role_by_name_manager():
    assert is_manager_role(_make_role("MANAGER")) is True


def test_is_manager_role_by_name_admin():
    assert is_manager_role(_make_role("ADMIN")) is True


def test_is_manager_role_by_name_responsable():
    assert is_manager_role(_make_role("RESPONSABLE")) is True


def test_is_manager_role_by_name_case_insensitive():
    assert is_manager_role(_make_role("manager")) is True
    assert is_manager_role(_make_role("Manager")) is True


def test_is_manager_role_by_name_with_whitespace():
    assert is_manager_role(_make_role("  MANAGER  ")) is True


def test_is_manager_role_by_permission_flag():
    assert is_manager_role(_make_role("CUSTOM", {"manager": True})) is True


def test_is_manager_role_by_can_manage_device_login_flag():
    assert is_manager_role(_make_role("CUSTOM", {"can_manage_device_login": True})) is True


def test_is_manager_role_unknown_role_returns_false():
    assert is_manager_role(_make_role("OPERATOR")) is False


def test_is_manager_role_permission_false_does_not_grant():
    assert is_manager_role(_make_role("CUSTOM", {"manager": False})) is False


# ── is_platform_admin_role ────────────────────────────────────────────────────


def test_is_platform_admin_role_none_returns_false():
    assert is_platform_admin_role(None) is False


def test_is_platform_admin_role_by_name():
    assert is_platform_admin_role(_make_role("PLATFORM_ADMIN")) is True
    assert is_platform_admin_role(_make_role("SUPER_ADMIN")) is True


def test_is_platform_admin_role_by_permission_flag():
    assert is_platform_admin_role(_make_role("CUSTOM", {"platform_admin": True})) is True


def test_is_platform_admin_role_manager_is_not_platform_admin():
    assert is_platform_admin_role(_make_role("MANAGER")) is False
