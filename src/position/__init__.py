"""
Position and Watch: the atomic units of the monitoring system.

Position holds the decisions the operator is carrying. A Watch is one
pre-registered claim serving one of those decisions. Both are hand-authored
YAML in a private repository; this package is the schema, the validator and the
one path by which a Watch reaches the database.

Added 2026-08-31 for backlog task 013.
"""

from .ledger import (
    BELIEF_SOURCES,
    OUTCOMES,
    CurrentBelief,
    LedgerError,
    current_beliefs,
    live_clause,
    open_clause,
    record_belief,
    resolve_watch,
)
from .position import (
    MAX_PAGES,
    POSITION_PAGE_WORDS,
    Decision,
    Position,
    PositionError,
    load_position,
)
from .watches import (
    TRIGGER_FIELDS,
    TriggerClause,
    Watch,
    WatchError,
    load_watches,
    sync_watches,
)

__all__ = [
    "BELIEF_SOURCES",
    "MAX_PAGES",
    "OUTCOMES",
    "POSITION_PAGE_WORDS",
    "TRIGGER_FIELDS",
    "CurrentBelief",
    "Decision",
    "LedgerError",
    "Position",
    "PositionError",
    "TriggerClause",
    "Watch",
    "WatchError",
    "current_beliefs",
    "live_clause",
    "load_position",
    "load_watches",
    "open_clause",
    "record_belief",
    "resolve_watch",
    "sync_watches",
]
