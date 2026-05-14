"""
Migration: Add Question Graph Tables
Adds Question and QuestionSituation tables for cross-run question tracking.
"""

from src.database.connection import engine
from src.database.models import Question, QuestionSituation


def upgrade():
    """Create question graph tables."""
    print("Creating question graph tables...")

    Question.__table__.create(engine, checkfirst=True)
    print("  questions table created")

    QuestionSituation.__table__.create(engine, checkfirst=True)
    print("  question_situations table created")

    print("\nQuestion graph migration completed.")


def downgrade():
    """Drop question graph tables."""
    print("Dropping question graph tables...")

    QuestionSituation.__table__.drop(engine, checkfirst=True)
    print("  question_situations table dropped")

    Question.__table__.drop(engine, checkfirst=True)
    print("  questions table dropped")

    print("\nQuestion graph downgrade completed.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "down":
        downgrade()
    else:
        upgrade()
