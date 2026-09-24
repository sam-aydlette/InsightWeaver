"""
The brief's sections as plain data: what :mod:`select` produces and
:mod:`render` prints. Frozen where a row is a record; ``Brief`` itself is
mutable only so the selector can fill it section by section.

Added 2026-09-22 for backlog task 031.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

__all__ = [
    "Brief",
    "Citation",
    "DueDecision",
    "DueWatch",
    "FailedAdjudication",
    "Header",
    "MovedWatch",
    "PendingWatch",
    "QuietWatch",
    "SilentSource",
    "SourceState",
    "WatchingRow",
]


@dataclass(frozen=True)
class SourceState:
    name: str
    last_attempt: datetime | None  # rss_feeds.last_fetched: the last attempt, success or not
    last_error: str | None  # the error of that attempt, None when it succeeded
    items_in_window: int


@dataclass(frozen=True)
class Header:
    as_of: datetime
    since: datetime
    position_problem: str | None  # the loader's whole message when the Position was not read
    reviewed: date | None
    days_since_review: int | None
    review_banner: bool
    sources: tuple[SourceState, ...]


@dataclass(frozen=True)
class Citation:
    content_hash: str
    title: str
    source: str
    published: str
    direction: str
    magnitude: float
    prompt_version: str


@dataclass(frozen=True)
class MovedWatch:
    watch_id: str
    claim: str
    # None while the watch is live; otherwise why it is not ("expired 2026-08-22,
    # unresolved", "resolved yes", "retired"). Evidence that arrived in the
    # window is shown whatever the watch's state, because grading needs it.
    state: str | None
    # One entry per near-duplicate cluster, earliest cluster first; within a
    # cluster the earliest citation first. One citation per evidence row, so
    # an observation judged under two prompt versions is two citations.
    clusters: tuple[tuple[Citation, ...], ...]


@dataclass(frozen=True)
class DueDecision:
    key: str
    name: str
    deadline: date
    days_left: int  # negative when the deadline has passed
    stake: str | None


@dataclass(frozen=True)
class DueWatch:
    watch_id: str
    claim: str
    expires: date
    days_left: int  # negative when already expired


@dataclass(frozen=True)
class WatchingRow:
    watch_id: str
    claim: str
    belief: float
    belief_source: str
    belief_date: date
    decision_key: str
    days_to_expiry: int
    evidence_in_window: int
    last_evidence: date | None


@dataclass(frozen=True)
class QuietWatch:
    watch_id: str
    staleness_alert_days: int
    last_routed: date | None  # the day routing last linked something to it


@dataclass(frozen=True)
class SilentSource:
    name: str
    produced_before: bool  # the runner's "went silent" versus "never produced"


@dataclass(frozen=True)
class PendingWatch:
    watch_id: str
    pairs: int  # routed pairs with no adjudication under any prompt version


@dataclass(frozen=True)
class FailedAdjudication:
    content_hash: str
    watch_id: str
    prompt_version: str
    error: str


@dataclass
class Brief:
    header: Header
    position_read: bool = True
    moved: list[MovedWatch] = field(default_factory=list)
    due_decisions: list[DueDecision] = field(default_factory=list)
    due_watches: list[DueWatch] = field(default_factory=list)
    watching: list[WatchingRow] = field(default_factory=list)
    quiet_watches: list[QuietWatch] = field(default_factory=list)
    silent_sources: list[SilentSource] = field(default_factory=list)
    pending: list[PendingWatch] = field(default_factory=list)
    failed: list[FailedAdjudication] = field(default_factory=list)
