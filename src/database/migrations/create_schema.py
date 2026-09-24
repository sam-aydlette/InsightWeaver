"""
Migration: create every table the models declare that the database lacks.

For a fresh database. Before 2026-09-23 nothing created ``rss_feeds`` and
``articles`` on a new install -- the additive migrations cover only the tables
they were written for, and the ``create_all`` call that used to run at startup
went with the deleted pipeline -- so ``ingest`` on a clean checkout failed on
its first insert. This is the one bootstrap: ``Base.metadata.create_all`` over
the declared models, which creates what is absent and touches nothing that
exists. It adds no columns to an existing table; the additive migrations do
that, and re-running them after this is harmless.

Added 2026-09-23 for backlog task 033, found while writing GETTING_STARTED.
"""

from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from src.database.connection import engine
from src.database.models import Base

__all__ = ["upgrade"]


def upgrade(target: Engine = engine) -> list[str]:
    """Create the absent tables; return their names in creation order."""
    before = set(inspect(target).get_table_names())
    Base.metadata.create_all(bind=target)
    after = set(inspect(target).get_table_names())
    created = [name for name in Base.metadata.sorted_tables if name.name in after - before]
    return [table.name for table in created]


if __name__ == "__main__":
    made = upgrade()
    if made:
        for name in made:
            print(f"Created {name}.")
    else:
        print("Every declared table exists; nothing to do.")
