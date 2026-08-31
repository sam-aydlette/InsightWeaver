"""
Migration: add the ``route_candidates`` table.

Additive. It creates one table and touches nothing that exists -- in particular
it does not read, rewrite or migrate ``articles``, and it does not touch
``observations``, whose rows are immutable.

The DDL is not written out here. The table is created from its model, as
``add_watches_table`` and ``add_observations_and_evidence`` do, so the migration
and the models cannot drift. The unique constraint on
``(observation_hash, watch_id)`` is what makes routing idempotent, and a
hand-written CREATE TABLE that forgot it would produce a table that looks right
and silently doubles every watch's candidate count on the second run.

``downgrade()`` requires ``--confirm``. What it destroys is derived -- routing
is deterministic, so re-running it rebuilds every row from the same observations
-- but it also destroys the record of *when* each candidate was routed, which is
not.

Added 2026-08-31 for backlog task 015.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from src.database.connection import engine
from src.database.models import RouteCandidate

__all__ = ["TABLE", "downgrade", "upgrade"]

TABLE = "route_candidates"

_CONFIRM_HELP = (
    "Dropping route_candidates discards every Tier 1 routing decision and the\n"
    "time each was made. The decisions are recomputable -- routing is\n"
    "deterministic -- but the routed_at timestamps are not.\n"
    "Re-run with --confirm if that is what you want:\n\n"
    "    python -m src.database.migrations.add_route_candidates --down --confirm\n"
)


def upgrade(target: Engine | None = None) -> list[str]:
    """Create the table if it is absent. Returns the names created."""
    target = target or engine
    if inspect(target).has_table(TABLE):
        print(f"{TABLE} already exists; nothing to do.")
        return []
    RouteCandidate.__table__.create(bind=target)
    print(f"Created {TABLE} ({len(RouteCandidate.__table__.columns)} columns).")
    return [TABLE]


def downgrade(target: Engine | None = None, *, confirmed: bool = False) -> list[str]:
    """Drop the table. Requires ``confirmed`` -- this loses rows."""
    if not confirmed:
        raise SystemExit(_CONFIRM_HELP)
    target = target or engine
    if not inspect(target).has_table(TABLE):
        print(f"{TABLE} does not exist; nothing to do.")
        return []
    RouteCandidate.__table__.drop(bind=target)
    print(f"Dropped {TABLE}.")
    return [TABLE]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="add_route_candidates",
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
