"""
Migration: Add the beat standing-question table
Adds BeatStandingQuestion so a beat can declare what it is watching.

Purely additive (2026-08-26, backlog task 007): no existing table is altered.
A database that has run add_beats but not this migration keeps working for
every command except `brief --beat` on a beat that declares standing
questions, which fails loudly naming this migration rather than dropping the
declaration.
"""

from src.database.connection import engine
from src.database.models import BeatStandingQuestion


def upgrade():
    """Create the standing-question table."""
    print("Creating standing question table...")

    BeatStandingQuestion.__table__.create(engine, checkfirst=True)
    print("  beat_standing_questions table created")

    print("\nStanding question migration completed.")


def downgrade():
    """Drop the standing-question table."""
    print("Dropping standing question table...")

    BeatStandingQuestion.__table__.drop(engine, checkfirst=True)
    print("  beat_standing_questions table dropped")

    print("\nStanding question downgrade completed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
