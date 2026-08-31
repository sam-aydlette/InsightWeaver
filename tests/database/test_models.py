"""
Tests for database models
Tests model creation, relationships, constraints, and indexes
"""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models import Article, RSSFeed


class TestRSSFeedModel:
    """Tests for RSSFeed model"""

    def test_create_rss_feed(self, test_session):
        """Should create an RSSFeed with required fields"""
        feed = RSSFeed(
            url="https://example.com/feed.xml",
            name="Example Feed",
        )
        test_session.add(feed)
        test_session.commit()

        assert feed.id is not None
        assert feed.url == "https://example.com/feed.xml"
        assert feed.name == "Example Feed"
        assert feed.is_active is True  # Default value
        assert feed.error_count == 0  # Default value

    def test_rss_feed_url_unique_constraint(self, test_session):
        """RSSFeed URL should be unique"""
        feed1 = RSSFeed(url="https://example.com/feed.xml", name="Feed 1")
        test_session.add(feed1)
        test_session.commit()

        feed2 = RSSFeed(url="https://example.com/feed.xml", name="Feed 2")
        test_session.add(feed2)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_rss_feed_optional_fields(self, test_session):
        """RSSFeed should handle optional fields"""
        feed = RSSFeed(
            url="https://example.com/feed.xml",
            name="Example Feed",
            category="technology",
            last_error="Connection timeout",
        )
        test_session.add(feed)
        test_session.commit()

        assert feed.category == "technology"
        assert feed.last_error == "Connection timeout"

    def test_rss_feed_timestamps(self, test_session):
        """RSSFeed should have created_at timestamp"""
        feed = RSSFeed(url="https://example.com/feed.xml", name="Test")
        test_session.add(feed)
        test_session.commit()

        assert feed.created_at is not None
        assert isinstance(feed.created_at, datetime)


class TestArticleModel:
    """Tests for Article model"""

    def test_create_article(self, test_session, sample_rss_feed):
        """Should create an Article with required fields"""
        article = Article(
            feed_id=sample_rss_feed.id,
            guid="unique-guid-123",
            title="Test Article",
        )
        test_session.add(article)
        test_session.commit()

        assert article.id is not None
        assert article.feed_id == sample_rss_feed.id
        assert article.guid == "unique-guid-123"
        assert article.filtered is False  # Default value

    def test_article_feed_guid_unique_constraint(self, test_session, sample_rss_feed):
        """Article feed_id + guid should be unique"""
        article1 = Article(feed_id=sample_rss_feed.id, guid="same-guid")
        test_session.add(article1)
        test_session.commit()

        article2 = Article(feed_id=sample_rss_feed.id, guid="same-guid")
        test_session.add(article2)

        with pytest.raises(IntegrityError):
            test_session.commit()

    def test_article_json_fields(self, test_session, sample_rss_feed):
        """Article should store JSON fields correctly"""
        article = Article(
            feed_id=sample_rss_feed.id,
            guid="json-test",
            categories=["tech", "news", "ai"],
            entities=["OpenAI", "Google", "Microsoft"],
            priority_metadata={"duplicate_of": None, "reason": "unique"},
            trend_metadata={"trending": True, "score": 0.95},
        )
        test_session.add(article)
        test_session.commit()

        # Retrieve and verify JSON fields
        retrieved = test_session.query(Article).filter_by(guid="json-test").first()
        assert retrieved.categories == ["tech", "news", "ai"]
        assert retrieved.entities == ["OpenAI", "Google", "Microsoft"]
        assert retrieved.priority_metadata["duplicate_of"] is None
        assert retrieved.trend_metadata["trending"] is True

    def test_article_relationship_to_feed(self, test_session, sample_article):
        """Article should have relationship to RSSFeed"""
        assert sample_article.feed is not None
        assert sample_article.feed.name == "Test Feed"

    def test_feed_relationship_to_articles(self, test_session, sample_rss_feed, sample_article):
        """RSSFeed should have relationship to Articles"""
        assert len(sample_rss_feed.articles) >= 1
        assert sample_article in sample_rss_feed.articles


class TestModelIndexes:
    """Tests for database indexes"""

    def test_article_indexes_exist(self, test_engine):
        """Article table should have performance indexes"""
        from sqlalchemy import inspect

        inspector = inspect(test_engine)
        indexes = inspector.get_indexes("articles")
        index_names = [idx["name"] for idx in indexes]

        expected_indexes = [
            "idx_published_date",
            "idx_fetched_at",
            "idx_relevance_score",
            "idx_filtered",
            "idx_articles_filtered_fetched",
            "idx_articles_filtered_published",
        ]

        for idx in expected_indexes:
            assert idx in index_names, f"Index {idx} should exist on articles table"


class TestSchemaBoundaries:
    """
    Structural invariants that outlived the briefing product.

    The institutional-activity tables these used to guard (``beat_entities``,
    ``entity_mentions``) were dropped by backlog task 012 along with beats. The
    boundary they enforced did not go with them: the entity vocabulary is still
    closed and still holds no person, it just lives with the ported matcher in
    :mod:`src.matching.terms` now.

    A named individual may appear inside a source document that names a
    signatory -- that is an attribute of a document and expires with it -- but
    never as a row, because a row accumulates across runs.
    """

    def test_the_kind_vocabulary_is_closed_and_holds_no_person(self):
        from src.matching.terms import ENTITY_KINDS

        assert frozenset({"org", "program", "document_type"}) == ENTITY_KINDS

    def test_no_table_in_the_schema_is_person_shaped(self, test_engine):
        """
        A blunt structural check over the whole schema: if a persons table is
        ever added, this fails.
        """
        from sqlalchemy import inspect

        from src.database.models import Base

        forbidden = ("people", "persons", "person", "officials", "individuals", "watchlist")
        names = set(Base.metadata.tables) | set(inspect(test_engine).get_table_names())

        assert not [name for name in names if any(word in name.lower() for word in forbidden)]

    def test_only_the_two_surviving_tables_are_mapped(self):
        """
        Task 012 removed nineteen models. If one comes back by accident,
        ``create_tables()`` would recreate a concept the rewrite deleted, so the
        mapped set is pinned rather than left to review.
        """
        from src.database.models import Base

        assert set(Base.metadata.tables) == {"rss_feeds", "articles"}
