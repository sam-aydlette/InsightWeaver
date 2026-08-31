"""
Migration: add the ``watches`` table.

Additive. It creates one table and touches nothing that exists -- unlike the
three drop migrations beside it, running this cannot lose data, so it needs no
``--confirm`` on the way up.

The DDL is not written out here. The table is created from
``src.database.models.Watch.__table__``, so the migration and the model cannot
drift: a column added to the model is a column this migration creates, and there
is no second copy of the schema to forget to update. The CHECK constraints ride
along, which is the point -- ``ck_watches_so_what_present`` is invariant 2
enforced at the storage layer, and a migration that quietly created the table
without it would leave the invariant resting on the loader alone.

``downgrade()`` **does** destroy data: dropping the table discards whatever
watches were synced, and while every watch is reconstructible from the
operator's private ``watches.yaml``, the belief history that later tasks will
hang off these rows is not. So the way down requires ``--confirm`` and the way
up does not.

Added 2026-08-31 for backlog task 013.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from src.database.connection import engine
from src.database.models import Watch

__all__ = ["TABLE", "downgrade", "upgrade"]

TABLE = "watches"

_CONFIRM_HELP = (
    "Dropping the watches table discards every synced watch and any state hung\n"
    "off it. Re-run with --confirm if that is what you want:\n\n"
    "    python -m src.database.migrations.add_watches_table --down --confirm\n"
)


def upgrade(target: Engine | None = None) -> bool:
    """Create ``watches`` if it is not already there. Returns True if it created it."""
    target = target or engine
    if inspect(target).has_table(TABLE):
        print(f"{TABLE} already exists; nothing to do.")
        return False
    Watch.__table__.create(bind=target)
    print(f"Created {TABLE} ({len(Watch.__table__.columns)} columns).")
    return True


def downgrade(target: Engine | None = None, *, confirmed: bool = False) -> bool:
    """Drop ``watches``. Requires ``confirmed`` -- this loses rows."""
    if not confirmed:
        raise SystemExit(_CONFIRM_HELP)
    target = target or engine
    if not inspect(target).has_table(TABLE):
        print(f"{TABLE} does not exist; nothing to do.")
        return False
    Watch.__table__.drop(bind=target)
    print(f"Dropped {TABLE}.")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="add_watches_table",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--down", action="store_true", help="drop the table again")
    parser.add_argument("--confirm", action="store_true", help="required by --down")
    args = parser.parse_args(argv)

    if args.down:
        downgrade(confirmed=args.confirm)
        return 0
    upgrade()
    return 0


if __name__ == "__main__":
    sys.exit(main())
