"""
Migration: add the ``observations`` and ``evidence`` tables.

Additive. It creates two tables and touches nothing that exists. In particular
it does not read, rewrite or migrate ``articles`` -- the 55,249 pre-rewrite rows
are left exactly as they are, and the standing rule for which table is
authoritative is written in ``src/database/models.py``.

The DDL is not written out here. Both tables are created from their models, as
``add_watches_table`` does, so the migration and the models cannot drift. That
matters more than usual for ``observations``: its immutability trigger is
attached to the table's ``after_create`` event in the models module, so creating
the table from the model is what installs the trigger. Hand-written DDL here
would produce a table that looks right and silently accepts UPDATEs.

Order matters on the way up and on the way down. ``evidence`` has foreign keys
into ``observations`` and ``watches``, so observations is created first and
dropped last.

``downgrade()`` destroys data and requires ``--confirm``. Dropping ``evidence``
loses adjudication output, which is derived and rebuildable by replay -- but
only if the observations that produced it still exist, which is exactly what
dropping ``observations`` in the same breath would take away.

Added 2026-08-31 for backlog task 014.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from src.database.connection import engine
from src.database.models import Evidence, Observation

__all__ = ["TABLES", "downgrade", "upgrade"]

# Creation order. Reversed on the way down.
TABLES = ("observations", "evidence")

# Annotated as Any because ``src.database.models`` is excluded from mypy (the
# pre-2.0 Column() style makes every attribute read as its column type), so the
# declarative classes arrive here as ``type[object]``.
_MODELS: dict[str, Any] = {"observations": Observation, "evidence": Evidence}

_CONFIRM_HELP = (
    "Dropping these tables discards the content-addressed corpus and every\n"
    "adjudication verdict recorded against it. Evidence is derived and can be\n"
    "replayed -- but only from observations, which this also drops.\n"
    "Re-run with --confirm if that is what you want:\n\n"
    "    python -m src.database.migrations.add_observations_and_evidence --down --confirm\n"
)


def upgrade(target: Engine | None = None) -> list[str]:
    """Create whichever of the two tables is absent. Returns the names created."""
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
    """Drop both tables. Requires ``confirmed`` -- this loses rows."""
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
        prog="add_observations_and_evidence",
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
