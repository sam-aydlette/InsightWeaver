"""
Migration: Drop Orphan Tables
Removes tables left behind by feature versions that were ripped out of the
codebase. None of these have a model class in src/database/models.py, so
SQLAlchemy never touches them -- they just occupy space and, in the case of
`decisions` and `predictions`, collide with names later stages need.

This migration is intentionally one-directional: there is no downgrade,
because the schemas of these tables were never tracked in version control
and there is nothing meaningful to recreate.
"""

from sqlalchemy import text

from src.database.connection import engine

ORPHAN_TABLES = [
    "api_data_points",
    "api_data_sources",
    "civic_action_windows",
    "decision_conversations",
    "decision_dossiers",
    "decisions",
    "extracted_claims",
    "monitored_pages",
    "page_changes",
    "predictions",
    "privacy_captures",
    "source_profiles",
    "state_vector_observations",
    "trend_analyses",
]


def upgrade():
    """Drop orphan tables if present."""
    print("Dropping orphan tables...")
    with engine.begin() as conn:
        for table in ORPHAN_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
            print(f"  dropped {table} (if it existed)")
    print("\nOrphan table cleanup completed.")


if __name__ == "__main__":
    upgrade()
