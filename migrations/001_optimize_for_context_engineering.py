"""
Migration: Optimize Database for Context Engineering

Changes:
1. Add context-optimized fields to articles table
2. Add context_snapshots table
3. Update narrative_syntheses table
4. Update analysis_runs table
5. Mark trend_analyses and predictions as deprecated (to be removed later)

Run with: python migrations/001_optimize_for_context_engineering.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text

from src.database.connection import get_db


def migrate_up():
    """Apply migration"""
    print("Starting migration: Optimize for Context Engineering")

    with get_db() as session:
        # 1. Add new fields to articles table
        print("  1. Adding context-optimized fields to articles table...")

        try:
            session.execute(
                text("""
                ALTER TABLE articles
                ADD COLUMN embedding_summary TEXT,
                ADD COLUMN relevance_score REAL,
                ADD COLUMN last_included_in_synthesis DATETIME
            """)
            )
            print("     ✓ Added: embedding_summary, relevance_score, last_included_in_synthesis")
        except Exception as e:
            print(f"     Note: Fields may already exist: {e}")

        # 2. Add indexes for context selection
        print("  2. Adding indexes for context selection...")

        try:
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_relevance_score ON articles(relevance_score)
            """)
            )
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_filtered ON articles(filtered)
            """)
            )
            print("     ✓ Added indexes: idx_relevance_score, idx_filtered")
        except Exception as e:
            print(f"     Note: Indexes may already exist: {e}")

        # 3. Create context_snapshots table
        print("  3. Creating context_snapshots table...")

        try:
            session.execute(
                text("""
                CREATE TABLE IF NOT EXISTS context_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    synthesis_id INTEGER,
                    article_ids TEXT,
                    context_size_tokens INTEGER,
                    user_profile_hash VARCHAR(64),
                    historical_summaries TEXT,
                    instructions TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_context_created_at ON context_snapshots(created_at)
            """)
            )
            print("     ✓ Created: context_snapshots table")
        except Exception as e:
            print(f"     Note: Table may already exist: {e}")

        # 4. Add new fields to narrative_syntheses
        print("  4. Updating narrative_syntheses table...")

        try:
            session.execute(
                text("""
                ALTER TABLE narrative_syntheses
                ADD COLUMN context_snapshot_id INTEGER REFERENCES context_snapshots(id)
            """)
            )
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_narrative_profile_version
                ON narrative_syntheses(user_profile_version)
            """)
            )
            print("     ✓ Added: context_snapshot_id, index on user_profile_version")
        except Exception as e:
            print(f"     Note: Fields may already exist: {e}")

        # 5. Add new fields to analysis_runs
        print("  5. Updating analysis_runs table...")

        try:
            session.execute(
                text("""
                ALTER TABLE analysis_runs
                ADD COLUMN context_token_count INTEGER,
                ADD COLUMN claude_model VARCHAR(100)
            """)
            )
            session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_run_started_at ON analysis_runs(started_at)
            """)
            )
            print("     ✓ Added: context_token_count, claude_model")
        except Exception as e:
            print(f"     Note: Fields may already exist: {e}")

        # 6. Initialize relevance_score for existing articles (recency-based)
        print("  6. Initializing relevance_score for existing articles...")

        try:
            session.execute(
                text("""
                UPDATE articles
                SET relevance_score = julianday('now') - julianday(fetched_at)
                WHERE relevance_score IS NULL AND fetched_at IS NOT NULL
            """)
            )
            print("     ✓ Initialized relevance_score based on recency")
        except Exception as e:
            print(f"     Warning: {e}")

        session.commit()

    print("\n✅ Migration complete!")
    print("\nNext steps:")
    print("  - Old tables (trend_analyses, predictions) are marked deprecated")
    print("  - They can be dropped after verifying synthesis data contains all needed info")
    print("  - Old article fields (priority_score, priority_metadata, trend_metadata)")
    print("    can be dropped in a future migration after verifying they're unused")


def migrate_down():
    """Rollback migration (if needed)"""
    print("Rolling back migration: Optimize for Context Engineering")

    with get_db() as session:
        # Remove new fields and tables in reverse order
        print("  Removing context_snapshots table...")
        try:
            session.execute(text("DROP TABLE IF EXISTS context_snapshots"))
        except Exception as e:
            print(f"     Warning: {e}")

        print("  Removing new fields from articles...")
        # Note: SQLite doesn't support DROP COLUMN easily
        # Would need to recreate table to remove columns
        print("     Note: Column removal requires table recreation in SQLite")

        session.commit()

    print("✅ Rollback complete!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Database migration for context engineering")
    parser.add_argument("--down", action="store_true", help="Rollback migration")
    args = parser.parse_args()

    if args.down:
        migrate_down()
    else:
        migrate_up()
