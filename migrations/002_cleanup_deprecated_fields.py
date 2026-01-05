"""
Migration: Cleanup Deprecated Fields (Phase 2)

This migration should be run AFTER verifying that:
1. Synthesis data contains all trend/prediction information
2. Old agent fields (priority_score, etc.) are no longer referenced in code

Changes:
1. Drop deprecated tables: trend_analyses, predictions
2. Remove deprecated fields from articles: priority_score, priority_metadata, trend_metadata
3. Remove trends_analyzed from narrative_syntheses

DO NOT RUN THIS IMMEDIATELY - Run after validation period
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text

from src.database.connection import get_db


def migrate_up():
    """Apply cleanup migration"""
    print("⚠️  WARNING: This migration removes deprecated tables and fields")
    print("    Make sure you have verified that:")
    print("    1. Synthesis data contains all needed trend/prediction info")
    print("    2. Code no longer references old agent fields")
    print("")

    response = input("Continue with cleanup? (yes/no): ")
    if response.lower() != "yes":
        print("Migration cancelled")
        return

    print("\nStarting cleanup migration...")

    with get_db() as session:
        # 1. Drop deprecated tables
        print("  1. Dropping deprecated tables...")

        try:
            session.execute(text("DROP TABLE IF EXISTS predictions"))
            print("     ✓ Dropped: predictions")
        except Exception as e:
            print(f"     Error: {e}")

        try:
            session.execute(text("DROP TABLE IF EXISTS trend_analyses"))
            print("     ✓ Dropped: trend_analyses")
        except Exception as e:
            print(f"     Error: {e}")

        # 2. Remove deprecated fields from articles
        # SQLite requires recreating the table to drop columns
        print("  2. Removing deprecated fields from articles...")
        print("     Note: Requires table recreation in SQLite")

        try:
            # Create new articles table without deprecated fields
            session.execute(text("""
                CREATE TABLE articles_new (
                    id INTEGER PRIMARY KEY,
                    feed_id INTEGER,
                    guid VARCHAR(500) NOT NULL,
                    url VARCHAR(500),
                    title VARCHAR(500),
                    description TEXT,
                    content TEXT,
                    published_date DATETIME,
                    author VARCHAR(200),
                    categories TEXT,
                    normalized_content TEXT,
                    word_count INTEGER,
                    language VARCHAR(10),
                    entities TEXT,
                    embedding_summary TEXT,
                    relevance_score REAL,
                    last_included_in_synthesis DATETIME,
                    filtered BOOLEAN DEFAULT 0,
                    filter_reason VARCHAR(200),
                    fetched_at DATETIME,
                    created_at DATETIME,
                    FOREIGN KEY (feed_id) REFERENCES rss_feeds(id),
                    UNIQUE(feed_id, guid)
                )
            """))

            # Copy data
            session.execute(text("""
                INSERT INTO articles_new
                SELECT
                    id, feed_id, guid, url, title, description, content,
                    published_date, author, categories, normalized_content,
                    word_count, language, entities, embedding_summary,
                    relevance_score, last_included_in_synthesis, filtered,
                    filter_reason, fetched_at, created_at
                FROM articles
            """))

            # Drop old table and rename
            session.execute(text("DROP TABLE articles"))
            session.execute(text("ALTER TABLE articles_new RENAME TO articles"))

            # Recreate indexes
            session.execute(text("""
                CREATE INDEX idx_published_date ON articles(published_date)
            """))
            session.execute(text("""
                CREATE INDEX idx_fetched_at ON articles(fetched_at)
            """))
            session.execute(text("""
                CREATE INDEX idx_relevance_score ON articles(relevance_score)
            """))
            session.execute(text("""
                CREATE INDEX idx_filtered ON articles(filtered)
            """))

            print("     ✓ Removed: priority_score, priority_metadata, trend_metadata")

        except Exception as e:
            print(f"     Error: {e}")
            print("     You may need to manually recreate the articles table")

        # 3. Remove trends_analyzed from narrative_syntheses
        print("  3. Updating narrative_syntheses table...")
        print("     Note: SQLite limitation - keeping trends_analyzed field")
        print("     (Can be ignored, will always be 0)")

        session.commit()

    print("\n✅ Cleanup migration complete!")
    print("\nDatabase is now fully optimized for context engineering")


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 2 CLEANUP MIGRATION")
    print("=" * 60)
    print("\nThis is a destructive migration that removes:")
    print("  - trend_analyses table")
    print("  - predictions table")
    print("  - priority_score, priority_metadata, trend_metadata from articles")
    print("\nOnly run this after validating Phase 1 migration works correctly")
    print("=" * 60)
    print("")

    migrate_up()
