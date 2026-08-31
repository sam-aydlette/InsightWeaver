"""
Position and Watch: the atomic units of the monitoring system.

Position holds the decisions the operator is carrying. A Watch is one
pre-registered claim serving one of those decisions. Both are hand-authored
YAML in a private repository; this package is the schema, the validator and the
one path by which a Watch reaches the database.

Added 2026-08-31 for backlog task 013.
"""

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
    "MAX_PAGES",
    "POSITION_PAGE_WORDS",
    "TRIGGER_FIELDS",
    "Decision",
    "Position",
    "PositionError",
    "TriggerClause",
    "Watch",
    "WatchError",
    "load_position",
    "load_watches",
    "sync_watches",
]
