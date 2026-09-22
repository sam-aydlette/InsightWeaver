"""
Part of the model split of 2026-09-22 (backlog task 030); see ``__init__``.
"""

from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    event,
)

from ...utils import utcnow
from .base import Base, LedgerIsAppendOnly


class Watch(Base):
    """
    One pre-registered claim, the decision it serves, and what would move it.

    Rows arrive from exactly one place: ``src.position.watches.sync_watches``,
    reading the operator's hand-authored file. Nothing else creates one.
    Invariant 6 -- the system never authors its own watches -- is a property of
    the code paths that exist, so no path exists. Two other writers touch
    existing rows and nothing else (since 2026-09-22, backlog task 030):
    sync sets and clears ``retired_at``, and ``src.position.ledger.resolve_watch``
    writes the three resolution columns once, at the operator's command.

    **The constraints are the enforcement, not a formality.** Invariant 2 says
    every Watch must name a decision; the loader rejects a blank ``so_what``,
    and ``ck_watches_so_what_present`` rejects it again at the storage layer, so
    a row written by hand through ``sqlite3`` fails the same way a bad YAML file
    does. The repository's own history is the argument: 25 unfalsifiable
    predictions accumulated in the deleted ledger because a missing field was
    tolerated by every layer that could have refused it.

    ``triggers`` is JSON, and structured JSON specifically -- a list of clauses
    over terms, entities and source allowlists. Tier 1 compiles it into a
    deterministic predicate. The column it replaces, ``predictions.
    trigger_condition``, was free text; 33 rows were written against it and none
    were ever graded, because nothing downstream could evaluate a sentence.
    """

    __tablename__ = "watches"

    # The operator's own id from the file, not a surrogate. It is the name they
    # will type and the name an alert will carry, and a watch that is renamed in
    # the file is a different watch.
    id = Column(String(100), primary_key=True)

    claim = Column(Text, nullable=False)
    belief = Column(Float, nullable=False)

    # so_what, split: the key is what makes invariant 2 machine-checkable, the
    # prose is what makes it readable. `decision_key` references a decision in
    # the Position file, which is not a table -- Position lives in a private
    # repo under git, so this is deliberately not a foreign key.
    decision_key = Column(String(100), nullable=False)
    so_what = Column(Text, nullable=False)

    triggers = Column(JSON, nullable=False)
    expires = Column(Date, nullable=False)
    staleness_alert_days = Column(Integer, nullable=False)

    # Lifecycle, added 2026-09-22 (backlog task 030). `retired_at` is set by
    # sync when the watch leaves the file and cleared if it returns; the row
    # is never deleted, because the belief ledger hangs off it. `resolved_at`,
    # `outcome` and `resolution_note` are written once, by the operator,
    # through src.position.ledger.resolve_watch, and by nothing else.
    retired_at = Column(DateTime)
    resolved_at = Column(DateTime)
    # A column-level constraint, not a table-level one: SQLite can DROP a
    # column that carries its own CHECK and cannot drop one a table CHECK
    # names, and the migration's way down drops these four.
    outcome = Column(
        String(10),
        CheckConstraint("outcome IS NULL OR outcome IN ('yes', 'no')", name="ck_watches_outcome"),
    )
    resolution_note = Column(Text)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        CheckConstraint("length(trim(so_what)) > 0", name="ck_watches_so_what_present"),
        CheckConstraint("length(trim(decision_key)) > 0", name="ck_watches_decision_present"),
        CheckConstraint("belief >= 0.0 AND belief <= 1.0", name="ck_watches_belief_range"),
        CheckConstraint("staleness_alert_days >= 1", name="ck_watches_staleness_min"),
        Index("idx_watches_decision_key", "decision_key"),
        Index("idx_watches_expires", "expires"),
    )


class WatchBelief(Base):
    """
    One belief value for one watch, with who set it and when. Append-only.

    ``watches.belief`` is the value at registration; this table is every value
    since, including that first one. ``source`` is ``file`` when
    ``sync_watches`` wrote it from the watch file and ``principal`` when the
    operator wrote it with ``watch believe``. Nothing else writes here, and
    nothing updates or deletes: the ORM guards below refuse a flush, and the
    triggers refuse an UPDATE or DELETE from anywhere else, the same two-layer
    enforcement ``observations`` has. Belief history is the calibration record
    the system exists to accumulate, and a row that can be edited is a history
    that can be rewritten.

    Added 2026-09-22 for backlog task 030.
    """

    __tablename__ = "watch_beliefs"

    id = Column(Integer, primary_key=True)
    watch_id = Column(String(100), ForeignKey("watches.id"), nullable=False)
    belief = Column(Float, nullable=False)
    source = Column(String(20), nullable=False)
    note = Column(Text)
    observed_at = Column(DateTime, nullable=False)

    __table_args__ = (
        CheckConstraint("belief >= 0.0 AND belief <= 1.0", name="ck_watch_beliefs_range"),
        CheckConstraint("source IN ('file', 'principal')", name="ck_watch_beliefs_source"),
        Index("idx_watch_beliefs_watch_time", "watch_id", "observed_at"),
    )


_LEDGER_MESSAGE = (
    "watch_beliefs is append-only: belief history is the calibration record, "
    "and a row that can be changed is a history that can be rewritten. "
    "Insert a new row instead."
)

for _verb in ("UPDATE", "DELETE"):
    event.listen(
        WatchBelief.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER watch_beliefs_no_{_verb.lower()} BEFORE {_verb} ON watch_beliefs "
            f"BEGIN SELECT RAISE(ABORT, '{_LEDGER_MESSAGE}'); END"
        ).execute_if(dialect="sqlite"),
    )


@event.listens_for(WatchBelief, "before_update", propagate=True)
def _refuse_belief_update(_mapper, _connection, target):
    raise LedgerIsAppendOnly(f"refusing to update belief row {target.id}: {_LEDGER_MESSAGE}")


@event.listens_for(WatchBelief, "before_delete", propagate=True)
def _refuse_belief_delete(_mapper, _connection, target):
    raise LedgerIsAppendOnly(f"refusing to delete belief row {target.id}: {_LEDGER_MESSAGE}")
