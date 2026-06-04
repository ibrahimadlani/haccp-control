"""
Role classification utilities for access-control decisions.

This module defines the two role-checking predicates used throughout the
application to determine whether a ``Utilisateur`` (or its associated
``Role``) has manager-grade or platform-admin-grade permissions.

Both predicates inspect the ``Role`` record using two complementary
strategies:

1. **Name matching** — the role's ``nom_role`` is compared against a
   fixed set of well-known names (e.g. ``"MANAGER"``, ``"ADMIN"``).
2. **Permission flag matching** — the role's ``permissions`` JSONB
   dictionary is checked for explicit boolean flags
   (e.g. ``{"manager": true}``).

Using both strategies makes the system resilient to organisations that
create roles with non-standard names but set the appropriate permission
flags, as well as to standard names where the permissions dict may be
empty.
"""

from typing import Any

from app.modules.personnel.models import Role

MANAGER_ROLE_NAMES: frozenset[str] = frozenset(
    {"ADMIN", "ADMINISTRATEUR", "MANAGER", "RESPONSABLE"}
)
"""Well-known role names that grant manager-level access.

A ``frozenset`` is used for O(1) membership testing and immutability.
"""

PLATFORM_ADMIN_ROLE_NAMES: frozenset[str] = frozenset({"PLATFORM_ADMIN", "SUPER_ADMIN"})
"""Well-known role names that grant platform-administrator access.

Platform admin is a superset of manager access and gates irreversible
operations such as hard-deletes across tenants.
"""


def is_manager_role(role: Role | None) -> bool:
    """Return ``True`` if the given role grants manager-level access.

    A role is considered a manager role when any of the following holds:
    - Its ``nom_role`` (normalised to uppercase, stripped of whitespace)
      is present in :data:`MANAGER_ROLE_NAMES`.
    - Its ``permissions`` dict contains ``{"manager": true}``.
    - Its ``permissions`` dict contains ``{"can_manage_device_login": true}``.

    Args:
        role (Role | None): The ``Role`` ORM instance to evaluate, or
            ``None`` when the assignment carries no role.

    Returns:
        bool: ``True`` if the role confers manager-level rights, ``False``
            otherwise (including when ``role`` is ``None``).
    """
    if role is None:
        return False
    permissions: dict[str, Any] = role.permissions or {}
    return (
        role.nom_role.strip().upper() in MANAGER_ROLE_NAMES
        or permissions.get("manager") is True
        or permissions.get("can_manage_device_login") is True
    )


def is_platform_admin_role(role: Role | None) -> bool:
    """Return ``True`` if the given role grants platform-administrator access.

    Platform admin rights are required for irreversible cross-tenant
    operations (hard-deletes, tenant creation).  A role is considered
    platform-admin when:
    - Its ``nom_role`` (normalised) is in :data:`PLATFORM_ADMIN_ROLE_NAMES`.
    - Its ``permissions`` dict contains ``{"platform_admin": true}``.

    Args:
        role (Role | None): The ``Role`` ORM instance to evaluate, or
            ``None`` when no role is present.

    Returns:
        bool: ``True`` if the role confers platform-admin rights, ``False``
            otherwise.
    """
    if role is None:
        return False
    permissions: dict[str, Any] = role.permissions or {}
    return (
        role.nom_role.strip().upper() in PLATFORM_ADMIN_ROLE_NAMES
        or permissions.get("platform_admin") is True
    )
