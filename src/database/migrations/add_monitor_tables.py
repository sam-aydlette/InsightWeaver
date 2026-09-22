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
derived and rebuildable from observations and watches, so dropping it loses
nothing that ``route --rebuild`` cannot restore. That stops being true when
the belief ledger joins this list (backlog task 030), and the help text must
change in the same commit.

Added 2026-09-22 for backlog task 028.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from src.database.connection import engine
from src.database.models import Route

__all__ = ["TABLES", "downgrade", "upgrade"]

# Creation order. Reversed on the way down.
TABLES = ("routes",)

_MODELS: dict[str, Any] = {"routes": Route}

_CONFIRM_HELP = (
    "Dropping the monitor tables discards routing links. Routes are derived and\n"
    "`insightweaver route --rebuild` restores them from observations and watches.\n"
    "Re-run with --confirm if that is what you want:\n\n"
    "    python -m src.database.migrations.add_monitor_tables --down --confirm\n"
)


def upgrade(target: Engine | None = None) -> list[str]:
    """Create whichever monitor tables are absent. Returns the names created."""
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
    return created


def downgrade(target: Engine | None = None, *, confirmed: bool = False) -> list[str]:
    """Drop the monitor tables. Requires ``confirmed``."""
    if not confirmed:
        raise SystemExit(_CONFIRM_HELP)
    target = target or engine
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
