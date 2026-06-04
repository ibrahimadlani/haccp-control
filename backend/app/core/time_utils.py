"""
Site-local datetime utilities.

Provides a single helper to obtain the current wall-clock time expressed
in an establishment's configured IANA timezone.  All HACCP timestamps
(temperature records, cleaning logs, time-clock events) must use
:func:`now_for_site` rather than ``datetime.utcnow()`` or
``datetime.now()`` so that records are always anchored to the local
kitchen time, which is what the operator sees on the tablet.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


def now_for_site(timezone: str) -> datetime:
    """Return the current timezone-aware datetime for an establishment's locale.

    Args:
        timezone (str): A valid IANA timezone string as stored in
            ``Etablissement.timezone`` (e.g. ``"Europe/Paris"``).

    Returns:
        datetime: The current local time with full timezone information
            (not UTC-naive), so PostgreSQL stores it correctly as
            ``TIMESTAMP WITH TIME ZONE``.
    """
    return datetime.now(ZoneInfo(timezone))
