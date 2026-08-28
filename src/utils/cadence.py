"""
Review cadences: how often a question is worth re-examining.

A cadence is written the way an operator says it out loud -- ``7d``, ``90d``,
``1y`` -- and parsed here into a plain interval. It is **not** a deadline. A
question's cadence says how often to look at it again; a prediction's
``due_by`` says when a specific claim resolves. A question reviewed quarterly
can hold a claim that resolves in three weeks, and collapsing the two into one
field would destroy that nesting.

Added 2026-08-27 for backlog task 011.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

# Units are calendar-approximate on purpose. A cadence is the operator's read
# on how fast a subject moves, not a contract -- "90d" and "3m" being the same
# interval is fine, and month-end arithmetic would add precision the concept
# does not have.
_UNIT_DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}

_CADENCE_RE = re.compile(r"^\s*(\d+)\s*([dwmy])\s*$", re.IGNORECASE)

# The forms the help text advertises, in the order it advertises them.
CADENCE_EXAMPLES = ("7d", "30d", "90d", "1y")


class InvalidCadence(ValueError):
    """Raised when a cadence string cannot be read as an interval."""

    def __init__(self, raw: str) -> None:
        self.raw = raw
        super().__init__(
            f"'{raw}' is not a review cadence. Write a whole number followed by "
            f"d (days), w (weeks), m (months, 30d) or y (years, 365d) -- "
            f"for example {', '.join(CADENCE_EXAMPLES)}."
        )


def parse_cadence(raw: str) -> timedelta:
    """
    Turn ``7d`` / ``2w`` / ``3m`` / ``1y`` into an interval.

    Raises :class:`InvalidCadence` rather than defaulting. A cadence the tool
    silently guessed at would not be the operator's read on the subject, which
    is the only thing that makes the interval itself falsifiable.
    """
    match = _CADENCE_RE.match(raw or "")
    if not match:
        raise InvalidCadence(raw)
    amount = int(match.group(1))
    if amount <= 0:
        raise InvalidCadence(raw)
    return timedelta(days=amount * _UNIT_DAYS[match.group(2).lower()])


def normalize_cadence(raw: str) -> str:
    """Canonical spelling of a valid cadence: lowercased, whitespace stripped."""
    match = _CADENCE_RE.match(raw or "")
    if not match:
        raise InvalidCadence(raw)
    if int(match.group(1)) <= 0:
        raise InvalidCadence(raw)
    return f"{int(match.group(1))}{match.group(2).lower()}"


def next_review_at(
    cadence: str | None,
    last_reviewed_at: datetime | None,
    first_asked_at: datetime,
) -> datetime | None:
    """
    When this question next comes up for review, or None if it has no cadence.

    The interval counts from the last review, or from when the question was
    first asked if it has never been reviewed -- a question declared today at a
    90-day cadence is not due today.
    """
    if not cadence:
        return None
    baseline = last_reviewed_at or first_asked_at
    return baseline + parse_cadence(cadence)


def is_due(
    cadence: str | None,
    last_reviewed_at: datetime | None,
    first_asked_at: datetime,
    now: datetime,
) -> bool:
    """Whether this question's own interval has elapsed since its last review."""
    due_at = next_review_at(cadence, last_reviewed_at, first_asked_at)
    return due_at is not None and now >= due_at


def describe_next_review(
    cadence: str | None,
    last_reviewed_at: datetime | None,
    first_asked_at: datetime,
    now: datetime,
) -> str:
    """
    A short human phrase for time-until-next-review, for ``questions list``.

    Says "no cadence" rather than inventing one, because a question with no
    cadence is genuinely not on a review schedule.
    """
    due_at = next_review_at(cadence, last_reviewed_at, first_asked_at)
    if due_at is None:
        return "no cadence"
    if now >= due_at:
        overdue = (now - due_at).days
        return f"due now ({overdue}d overdue)" if overdue else "due now"
    return f"next review in {max((due_at - now).days, 0)}d"
