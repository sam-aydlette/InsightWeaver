"""
Migration: add the decision monitor's tables.

Additive. Creates whichever of the monitor's tables are absent and touches
nothing that exists. The tables are created from their models, as
``add_watches_table`` and ``add_observations_and_evidence`` do, so the
migration and the models cannot drift; a CHECK constraint on the model is a
CHECK constraint in the database.

One migration for the monitor rather than one per task, because none of it
has been applied anywhere yet: the tables arrive here as tasks 028 to 031 land
(``routes`` first), and an operator who runs this once gets whatever the tree
holds. Re-running it after a later task creates only what is new.

``downgrade()`` drops the tables and requires ``--confirm``. ``routes`` is
derived and rebuildable from observations and watches; ``adjudications``
(task 029) and ``watch_beliefs`` (task 030) are ledgers of what the model was
asked and what the operator believed, and nothing rebuilds them, which the
help text says. Task 030 also added four lifecycle columns to ``watches``;
``add_watch_columns`` adds whichever an existing table lacks, one ALTER each,
and the way down drops them.

Added 2026-09-22 for backlog task 028.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from src.database.connection import engine
from src.database.models import Adjudication, Route, WatchBelief

__all__ = ["TABLES", "WATCH_COLUMNS", "downgrade", "upgrade"]

# Creation order. Reversed on the way down.
TABLES = ("routes", "adjudications", "watch_beliefs")

_MODELS: dict[str, Any] = {
    "routes": Route,
    "adjudications": Adjudication,
    "watch_beliefs": WatchBelief,
}

# Columns task 030 added to `watches`, with the DDL that adds each to an
# existing table. A fresh table gets them from the model; an older table gets
# them here, one ALTER per missing column, so re-running is harmless.
WATCH_COLUMNS: dict[str, str] = {
    "retired_at": "DATETIME",
    "resolved_at": "DATETIME",
    "outcome": (
        "VARCHAR(10) CONSTRAINT ck_watches_outcome "
        "CHECK (outcome IS NULL OR outcome IN ('yes', 'no'))"
    ),
    "resolution_note": "TEXT",
}

_CONFIRM_HELP = (
    "Dropping the monitor tables discards routing links, the adjudication ledger\n"
    "and the belief ledger, and removes the lifecycle columns from watches.\n"
    "Routes are derived and `insightweaver route --rebuild` restores them; the\n"
    "two ledgers are the record of what the model was asked, what it cost, and\n"
    "what you believed when, and nothing restores them. Re-run with --confirm if\n"
    "that is what you want:\n\n"
    "    python -m src.database.migrations.add_monitor_tables --down --confirm\n"
)


def _watch_columns_present(target: Engine) -> set[str]:
    inspector = inspect(target)
    if not inspector.has_table("watches"):
        return set()
    return {c["name"] for c in inspector.get_columns("watches")}


def add_watch_columns(target: Engine | None = None) -> list[str]:
    """Add whichever lifecycle columns `watches` lacks. Returns the names added."""
    target = target or engine
    present = _watch_columns_present(target)
    if not present:
        return []  # no watches table yet; add_watches_table creates it with every column
    added = []
    with target.begin() as conn:
        for name, ddl in WATCH_COLUMNS.items():
            if name in present:
                continue
            conn.execute(text(f"ALTER TABLE watches ADD COLUMN {name} {ddl}"))
            print(f"Added watches.{name}.")
            added.append(name)
    return added


def upgrade(target: Engine | None = None) -> list[str]:
    """Create whichever monitor tables are absent and add the watches columns."""
    target = target or engine
    inspector = inspect(target)
    created = []
    for name in TABLES:
        if inspector.has_table(name):
            print(f"{name} already exists; nothing to do.")
            continue
        model = _MODELS[name]
        model.__table__.create(bind=target)
        print(f"Created {name} ({len(model.__table__.columns)} columns).")
        created.append(name)
    add_watch_columns(target)
    return created


def downgrade(target: Engine | None = None, *, confirmed: bool = False) -> list[str]:
    """Drop the monitor tables and the watches columns. Requires ``confirmed``."""
    if not confirmed:
        raise SystemExit(_CONFIRM_HELP)
    target = target or engine
    # Columns first, in one transaction: a DROP COLUMN is the step that can be
    # refused (a table-level constraint naming the column would refuse it), and
    # a refusal must leave the tables in place rather than half a schema.
    present = _watch_columns_present(target)
    with target.begin() as conn:
        for name in reversed(list(WATCH_COLUMNS)):
            if name in present:
                conn.execute(text(f"ALTER TABLE watches DROP COLUMN {name}"))
                print(f"Dropped watches.{name}.")
    inspector = inspect(target)
    dropped = []
    for name in reversed(TABLES):
        if not inspector.has_table(name):
            print(f"{name} does not exist; nothing to do.")
            continue
        _MODELS[name].__table__.drop(bind=target)
        print(f"Dropped {name}.")
        dropped.append(name)
    return dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="add_monitor_tables",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--down", action="store_true", help="drop the tables again")
    parser.add_argument("--confirm", action="store_true", help="required by --down")
    args = parser.parse_args(argv)

    if args.down:
        downgrade(confirmed=args.confirm)
        return 0
    upgrade()
    return 0


if __name__ == "__main__":
    sys.exit(main())
