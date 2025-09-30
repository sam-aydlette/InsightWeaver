"""
Unit tests for database models and migrations
"""

import unittest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, Article, NarrativeSynthesis, RSSFeed


class TestDatabaseModels(unittest.TestCase):
    """Test database models and schema"""

    def setUp(self):
        """Create temporary test database"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.engine = create_engine(f'sqlite:///{self.db_path}')
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def tearDown(self):
        """Clean up test database"""
        self.session.close()
        self.engine.dispose()
        Path(self.db_path).unlink(missing_ok=True)

    def test_article_model_has_filter_columns(self):
        """Test that Article model has new filter columns"""
        feed = RSSFeed(
            url="http://test.com/rss",
            name="Test Feed"
        )
        self.session.add(feed)
        self.session.commit()

        article = Article(
            feed_id=feed.id,
            guid="test-guid-123",
            title="Test Article",
            filtered=True,
            filter_reason="sports"
        )
        self.session.add(article)
        self.session.commit()

        retrieved = self.session.query(Article).first()
        self.assertTrue(retrieved.filtered)
        self.assertEqual(retrieved.filter_reason, "sports")

    def test_article_default_filtered_false(self):
        """Test that filtered defaults to False"""
        feed = RSSFeed(
            url="http://test.com/rss",
            name="Test Feed"
        )
        self.session.add(feed)
        self.session.commit()

        article = Article(
            feed_id=feed.id,
            guid="test-guid-456",
            title="Test Article"
        )
        self.session.add(article)
        self.session.commit()

        retrieved = self.session.query(Article).first()
        self.assertFalse(retrieved.filtered)

    def test_narrative_synthesis_model(self):
        """Test NarrativeSynthesis model creation"""
        synthesis = NarrativeSynthesis(
            analysis_run_id=1,
            user_profile_version="1.0",
            synthesis_data={"test": "data"},
            executive_summary="Test summary",
            articles_analyzed=10,
            trends_analyzed=5,
            temporal_scope="immediate,near,medium"
        )
        self.session.add(synthesis)
        self.session.commit()

        retrieved = self.session.query(NarrativeSynthesis).first()
        self.assertEqual(retrieved.user_profile_version, "1.0")
        self.assertEqual(retrieved.articles_analyzed, 10)
        self.assertEqual(retrieved.synthesis_data, {"test": "data"})
        self.assertEqual(retrieved.executive_summary, "Test summary")

    def test_narrative_synthesis_timestamps(self):
        """Test that generated_at timestamp is set"""
        synthesis = NarrativeSynthesis(
            synthesis_data={},
            executive_summary="Test",
            articles_analyzed=5
        )
        self.session.add(synthesis)
        self.session.commit()

        retrieved = self.session.query(NarrativeSynthesis).first()
        self.assertIsNotNone(retrieved.generated_at)


class TestMigrations(unittest.TestCase):
    """Test that migrations create correct schema"""

    def setUp(self):
        """Create temporary database for migration testing"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name

    def tearDown(self):
        """Clean up"""
        Path(self.db_path).unlink(missing_ok=True)

    def test_migration_001_adds_filter_columns(self):
        """Test that migration 001 adds filtered and filter_reason columns"""
        conn = sqlite3.connect(self.db_path)

        # Create basic articles table
        conn.execute("""
            CREATE TABLE articles (
                id INTEGER PRIMARY KEY,
                title TEXT
            )
        """)

        # Apply migration 001
        with open('migrations/001_add_content_filtering.sql', 'r') as f:
            migration_sql = f.read()
            conn.executescript(migration_sql)

        # Check columns exist
        cursor = conn.execute("PRAGMA table_info(articles)")
        columns = {row[1] for row in cursor.fetchall()}

        self.assertIn('filtered', columns)
        self.assertIn('filter_reason', columns)

        conn.close()

    def test_migration_002_creates_narrative_table(self):
        """Test that migration 002 creates narrative_syntheses table"""
        conn = sqlite3.connect(self.db_path)

        # Apply migration 002
        with open('migrations/002_add_narrative_synthesis.sql', 'r') as f:
            migration_sql = f.read()
            conn.executescript(migration_sql)

        # Check table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='narrative_syntheses'"
        )
        result = cursor.fetchone()

        self.assertIsNotNone(result)

        # Check columns
        cursor = conn.execute("PRAGMA table_info(narrative_syntheses)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            'id', 'analysis_run_id', 'user_profile_version',
            'synthesis_data', 'executive_summary', 'articles_analyzed',
            'trends_analyzed', 'temporal_scope', 'generated_at'
        }
        self.assertTrue(expected_columns.issubset(columns))

        conn.close()


if __name__ == '__main__':
    unittest.main()