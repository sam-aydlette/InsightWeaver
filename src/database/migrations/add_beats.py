"""
Migration: Add Beat Tables
Adds Beat and BeatRun tables so brief runs can be attributed to a subject.

Purely additive (2026-08-26): no existing table is altered, so an unmigrated
database keeps working for every non-beat command and this migration cannot
lose data.
"""

from src.database.connection import engine
from src.database.models import Beat, BeatRun


def upgrade():
    """Create beat tables."""
    print("Creating beat tables...")

    Beat.__table__.create(engine, checkfirst=True)
    print("  beats table created")

    BeatRun.__table__.create(engine, checkfirst=True)
    print("  beat_runs table created")

    print("\nBeat migration completed.")


def downgrade():
    """Drop beat tables."""
    print("Dropping beat tables...")

    BeatRun.__table__.drop(engine, checkfirst=True)
    print("  beat_runs table dropped")

    Beat.__table__.drop(engine, checkfirst=True)
    print("  beats table dropped")

    print("\nBeat downgrade completed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
