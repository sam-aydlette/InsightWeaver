"""
The belief ledger, resolution, and what "live" means -- in one place.

Three things the rest of the monitor reads from here:

* **Belief is a ledger, not a column.** ``watches.belief`` is the value at
  registration. Every value, including that first one, is a ``watch_beliefs``
  row with a source and a date: ``file`` when the watch file set it at sync,
  ``principal`` when the operator wrote it with ``watch believe``. The current
  belief is the latest row. Nothing here moves belief on its own; there is no
  update rule (decided 2026-09-22, ``backlog/030``), and the ledger's
  append-only guards mean the history is reconstructable whatever later tasks
  add.
* **Resolution is a human act, once.** ``watch resolve`` sets the outcome and
  the date; there is no unresolve, no force, and no path from evidence to
  outcome. The 33 predictions graded zero times in the old ledger are the
  standing reason grading has to be deliberate. A retired watch can be graded
  (a claim often settles after it leaves the file) but takes no new belief.
* **Liveness has one definition.** A watch is live when it is not expired,
  not retired (absent from the file at the last sync) and not resolved.
  Routing filters through :func:`live_clause`; adjudication and replay, which
  read routed pairs, filter through :func:`open_clause` (retired and resolved,
  the two state-based conditions), because expiry is Tier 1's gate at routing
  time and a date-dependent filter there would make a replay depend on the
  day it ran.

Added 2026-09-22 for backlog task 030.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import ColumnElement, and_
from sqlalchemy.orm import Session

from src.database.models import Watch, WatchBelief
from src.utils import utcnow

__all__ = [
    "BELIEF_SOURCES",
    "OUTCOMES",
    "CurrentBelief",
    "LedgerError",
    "current_beliefs",
    "live_clause",
    "open_clause",
    "record_belief",
    "resolve_watch",
]

BELIEF_SOURCES = ("file", "principal")
OUTCOMES = ("yes", "no")


class LedgerError(ValueError):
    """A write the ledger refuses: unknown watch, dead watch, bad value, blank note."""


@dataclass(frozen=True)
class CurrentBelief:
    watch_id: str
    belief: float
    source: str
    observed_at: datetime
    note: str | None
    registered: float  # watches.belief, the value at registration


def open_clause() -> ColumnElement[bool]:
    """Not retired and not resolved: the state-based half of liveness."""
    return and_(Watch.retired_at.is_(None), Watch.resolved_at.is_(None))


def live_clause(today: date) -> ColumnElement[bool]:
    """Open and not expired: what routing links to."""
    return and_(open_clause(), Watch.expires >= today)


def _watch_for_write(db: Session, watch_id: str, *, allow_retired: bool) -> Watch:
    row = db.get(Watch, watch_id)
    if row is None:
        raise LedgerError(f"no watch '{watch_id}'; run 'watch sync' or check the id")
    if row.retired_at is not None and not allow_retired:
        raise LedgerError(
            f"watch '{watch_id}' was retired on {row.retired_at.date().isoformat()}; put it "
            f"back in the file and sync to restore it"
        )
    if row.resolved_at is not None:
        raise LedgerError(
            f"watch '{watch_id}' was resolved '{row.outcome}' on "
            f"{row.resolved_at.date().isoformat()}"
        )
    return row


def record_belief(
    db: Session,
    watch_id: str,
    belief: float,
    *,
    source: str,
    note: str | None,
    observed_at: datetime | None = None,
) -> WatchBelief:
    """Append one belief row. Refuses rather than defaults, on every field."""
    if source not in BELIEF_SOURCES:
        raise LedgerError(f"belief source must be one of {BELIEF_SOURCES}, got {source!r}")
    if not isinstance(belief, int | float) or isinstance(belief, bool):
        raise LedgerError(f"belief must be a number in [0, 1], got {belief!r}")
    if not 0.0 <= belief <= 1.0:
        raise LedgerError(f"belief must be in [0, 1], got {belief}")
    if source == "principal" and not (note or "").strip():
        raise LedgerError("a belief written by the operator needs a note saying why")
    # A retired watch takes no new belief: it is not being held. It can still
    # be graded (resolve_watch), because settling a claim after dropping it
    # from the file is an ordinary order of events.
    _watch_for_write(db, watch_id, allow_retired=False)
    row = WatchBelief(
        watch_id=watch_id,
        belief=float(belief),
        source=source,
        note=(note or "").strip() or None,
        observed_at=observed_at or utcnow(),
    )
    db.add(row)
    db.flush()
    return row


def current_beliefs(db: Session, *, as_of: datetime | None = None) -> dict[str, CurrentBelief]:
    """
    The latest ledger row per watch, or the latest at or before ``as_of``.

    A watch with no ledger row -- one stored before the ledger existed, or a
    row inserted by hand -- reads as its registration belief, labelled
    ``file`` and dated by its ``created_at``, which is what that value is.
    ``as_of`` is for the brief, which is a pure function of the moment it is
    rendered as of (2026-09-23, backlog task 031 review).
    """
    registered: dict[str, float] = {}
    out: dict[str, CurrentBelief] = {}
    for w in db.query(Watch).all():
        watch_id = str(w.id)
        registered[watch_id] = float(w.belief)
        # Column[...] versus value, as in src/sources/store.py: the models use
        # the pre-2.0 Column() style that mypy reads as the column type.
        out[watch_id] = CurrentBelief(
            watch_id,
            float(w.belief),
            "file",
            w.created_at,  # type: ignore[arg-type]
            None,
            float(w.belief),
        )
    query = db.query(WatchBelief)
    if as_of is not None:
        query = query.filter(WatchBelief.observed_at <= as_of)
    rows = query.order_by(WatchBelief.observed_at, WatchBelief.id).all()
    for row in rows:
        watch_id = str(row.watch_id)
        if watch_id not in registered:
            # SQLite is not enforcing the foreign key (no PRAGMA), so a hand
            # delete of a watch leaves its ledger behind. Say so, by name.
            raise LedgerError(
                f"watch_beliefs row {row.id} belongs to watch '{watch_id}', which does not "
                f"exist; a watch is retired by sync, never deleted, so this row was orphaned "
                f"by hand and must be repaired by hand"
            )
        out[watch_id] = CurrentBelief(
            watch_id=watch_id,
            belief=float(row.belief),
            source=str(row.source),
            observed_at=row.observed_at,  # type: ignore[arg-type]
            note=row.note,  # type: ignore[arg-type]
            registered=registered[watch_id],
        )
    return out


def resolve_watch(
    db: Session, watch_id: str, *, outcome: str, note: str, when: datetime | None = None
) -> Watch:
    """Grade a watch, once. There is no unresolve and no path from evidence here."""
    if outcome not in OUTCOMES:
        raise LedgerError(f"outcome must be one of {OUTCOMES}, got {outcome!r}")
    if not (note or "").strip():
        raise LedgerError("a resolution needs a note saying what settled it")
    row = _watch_for_write(db, watch_id, allow_retired=True)
    row.resolved_at = when or utcnow()  # type: ignore[assignment]
    row.outcome = outcome  # type: ignore[assignment]
    row.resolution_note = note.strip()  # type: ignore[assignment]
    db.flush()
    return row
