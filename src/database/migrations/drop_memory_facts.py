"""
Migration: Drop the memory_facts table.

MemoryFact was schema-only -- a subject/predicate/object triple table with a
confidence float and no extractor populating it from synthesis output. The
information it was supposed to capture is already structured in the
situation prompt (actors, power_dynamics, etc.), making the table inert
dead schema. This migration drops it.

One-directional: there is no downgrade because no production data ever lived
here.
"""

from sqlalchemy import text

from src.database.connection import engine


def upgrade():
    """Drop memory_facts if present."""
    print("Dropping memory_facts table...")
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS memory_facts"))
    print("memory_facts dropped (if it existed).")


if __name__ == "__main__":
    upgrade()
