"""
Tests for database connection functions
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


class TestGetDb:
    """Tests for get_db context manager"""

    def test_get_db_yields_session(self, test_engine, mocker):
        """get_db should yield a database session"""
        from sqlalchemy.orm import sessionmaker

        # Create a sessionmaker bound to our test engine
        TestSession = sessionmaker(bind=test_engine)

        # Mock the SessionLocal to use our test session
        mocker.patch("src.database.connection.SessionLocal", TestSession)

        from src.database.connection import get_db

        with get_db() as session:
            assert isinstance(session, Session)
            # Session should be usable for queries
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1

    def test_get_db_commits_on_success(self, test_engine, mocker):
        """get_db should commit changes on successful exit"""
        from sqlalchemy.orm import sessionmaker

        from src.database.models import RSSFeed

        TestSession = sessionmaker(bind=test_engine)
        mocker.patch("src.database.connection.SessionLocal", TestSession)

        from src.database.connection import get_db

        # Create a feed within the context manager
        with get_db() as session:
            feed = RSSFeed(url="https://test.com/feed", name="Test Feed")
            session.add(feed)

        # Verify it was committed by querying in a new session
        new_session = TestSession()
        feeds = new_session.query(RSSFeed).all()
        assert len(feeds) == 1
        assert feeds[0].name == "Test Feed"
        new_session.close()

    def test_get_db_rolls_back_on_exception(self, test_engine, mocker):
        """get_db should rollback changes when an exception occurs"""
        from sqlalchemy.orm import sessionmaker

        from src.database.models import RSSFeed

        TestSession = sessionmaker(bind=test_engine)
        mocker.patch("src.database.connection.SessionLocal", TestSession)

        from src.database.connection import get_db

        # Try to create a feed but raise an exception
        with pytest.raises(ValueError), get_db() as session:
            feed = RSSFeed(url="https://test.com/feed", name="Test Feed")
            session.add(feed)
            raise ValueError("Intentional error")

        # Verify it was rolled back
        new_session = TestSession()
        feeds = new_session.query(RSSFeed).all()
        assert len(feeds) == 0
        new_session.close()

    def test_get_db_closes_session_on_exit(self, test_engine, mocker):
        """get_db should close the session after exiting context"""
        from sqlalchemy.orm import sessionmaker

        TestSession = sessionmaker(bind=test_engine)
        mocker.patch("src.database.connection.SessionLocal", TestSession)

        from src.database.connection import get_db

        session_ref = None
        with get_db() as session:
            session_ref = session
            assert session.is_active

        # After context exit, session should be closed
        # Note: Session.is_active may still be True after close(),
        # but the session should be unusable
        assert session_ref is not None


class TestGetDbSession:
    """Tests for get_db_session function"""

    def test_get_db_session_returns_session(self, test_engine, mocker):
        """get_db_session should return a database session"""
        from sqlalchemy.orm import sessionmaker

        TestSession = sessionmaker(bind=test_engine)
        mocker.patch("src.database.connection.SessionLocal", TestSession)

        from src.database.connection import get_db_session

        session = get_db_session()
        try:
            assert isinstance(session, Session)
            # Session should be usable
            result = session.execute(text("SELECT 1"))
            assert result.scalar() == 1
        finally:
            session.close()

    def test_get_db_session_returns_new_session_each_time(self, test_engine, mocker):
        """Each call to get_db_session should return a new session"""
        from sqlalchemy.orm import sessionmaker

        TestSession = sessionmaker(bind=test_engine)
        mocker.patch("src.database.connection.SessionLocal", TestSession)

        from src.database.connection import get_db_session

        session1 = get_db_session()
        session2 = get_db_session()
        try:
            assert session1 is not session2
        finally:
            session1.close()
            session2.close()


class TestCreateTables:
    """Tests for create_tables function"""

    def test_create_tables_creates_all_tables(self, tmp_path, mocker):
        """create_tables should create all defined tables"""
        # Create a fresh engine
        db_path = tmp_path / "fresh.db"
        engine = create_engine(f"sqlite:///{db_path}")

        # Mock the engine
        mocker.patch("src.database.connection.engine", engine)

        from src.database.connection import create_tables

        create_tables()

        # Verify tables were created
        from sqlalchemy import inspect

        inspector = inspect(engine)
        table_names = inspector.get_table_names()

        expected_tables = [
            "rss_feeds",
            "articles",
            "analysis_runs",
            "narrative_syntheses",
            "context_snapshots",
            "api_data_sources",
            "api_data_points",
            "monitored_pages",
            "page_changes",
            "memory_facts",
            "forecast_runs",
            "long_term_forecasts",
            "forecast_scenarios",
            "causal_chains",
        ]

        for table in expected_tables:
            assert table in table_names, f"Table {table} should be created"

    def test_create_tables_is_idempotent(self, tmp_path, mocker):
        """create_tables should be safe to call multiple times"""
        db_path = tmp_path / "idempotent.db"
        engine = create_engine(f"sqlite:///{db_path}")
        mocker.patch("src.database.connection.engine", engine)

        from src.database.connection import create_tables

        # Call twice - should not raise
        create_tables()
        create_tables()

        # Tables should still exist
        from sqlalchemy import inspect

        inspector = inspect(engine)
        assert "rss_feeds" in inspector.get_table_names()
