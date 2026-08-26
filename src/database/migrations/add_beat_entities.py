"""
Migration: Add Institutional Activity Tables
Adds BeatEntity and EntityMention so a beat can record which of its declared
institutions appeared in each run.

Purely additive (2026-08-26): no existing table is altered, so an unmigrated
database keeps working for every other command and this migration cannot lose
data. Requires the beat tables from add_beats.py, which both new tables key
off.

There is no persons table here and no place for one: `beat_entities.kind`
carries `org`, `program` or `document_type` only. See
backlog/006-institutional-activity.md.
"""

from src.database.connection import engine
from src.database.models import BeatEntity, EntityMention


def upgrade():
    """Create institutional activity tables."""
    print("Creating institutional activity tables...")

    BeatEntity.__table__.create(engine, checkfirst=True)
    print("  beat_entities table created")

    EntityMention.__table__.create(engine, checkfirst=True)
    print("  entity_mentions table created")

    print("\nInstitutional activity migration completed.")


def downgrade():
    """Drop institutional activity tables."""
    print("Dropping institutional activity tables...")

    EntityMention.__table__.drop(engine, checkfirst=True)
    print("  entity_mentions table dropped")

    BeatEntity.__table__.drop(engine, checkfirst=True)
    print("  beat_entities table dropped")

    print("\nInstitutional activity downgrade completed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
