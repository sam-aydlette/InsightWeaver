"""Shared utilities."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Naive UTC datetime, matching the existing schema convention.

    Replaces `datetime.utcnow()` which is deprecated as of Python 3.12.
    The schema stores naive datetimes, so we strip tzinfo to keep new
    writes shape-compatible with existing rows.
    """
    return datetime.now(UTC).replace(tzinfo=None)
