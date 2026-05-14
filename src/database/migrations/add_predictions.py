"""
Migration: Add Predictions Ledger
Adds the Prediction table for tracking falsifiable observables across runs.
"""

from src.database.connection import engine
from src.database.models import Prediction


def upgrade():
    """Create the predictions table."""
    print("Creating predictions table...")
    Prediction.__table__.create(engine, checkfirst=True)
    print("  predictions table created")
    print("\nPredictions ledger migration completed.")


def downgrade():
    """Drop the predictions table."""
    print("Dropping predictions table...")
    Prediction.__table__.drop(engine, checkfirst=True)
    print("  predictions table dropped")
    print("\nPredictions ledger downgrade completed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
