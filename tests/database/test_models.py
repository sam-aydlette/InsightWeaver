"""
Tests for database models
Tests model creation, relationships, constraints, and indexes
"""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models import (
    AnalysisRun,
    Article,
    ContextSnapshot,
    NarrativeSynthesis,
    RSSFeed,
)


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


class TestAnalysisRunModel:
    """Tests for AnalysisRun model"""

    def test_create_analysis_run(self, test_session):
        """Should create an AnalysisRun"""
        run = AnalysisRun(
            run_type="narrative_synthesis",
            status="started",
        )
        test_session.add(run)
        test_session.commit()

        assert run.id is not None
        assert run.started_at is not None

    def test_analysis_run_completed(self, test_session):
        """Should track completion of analysis run"""
        run = AnalysisRun(
            run_type="narrative_synthesis",
            status="completed",
            articles_processed=50,
            context_token_count=10000,
            claude_model="claude-3-5-sonnet",
        )
        test_session.add(run)
        test_session.commit()

        assert run.articles_processed == 50
        assert run.context_token_count == 10000


class TestNarrativeSynthesisModel:
    """Tests for NarrativeSynthesis model"""

    def test_create_narrative_synthesis(
        self, test_session, sample_analysis_run, sample_context_snapshot
    ):
        """Should create a NarrativeSynthesis"""
        synthesis = NarrativeSynthesis(
            analysis_run_id=sample_analysis_run.id,
            context_snapshot_id=sample_context_snapshot.id,
            user_profile_version="1.0",
            synthesis_data={"bottom_line": {"summary": "Test"}},
            articles_analyzed=10,
        )
        test_session.add(synthesis)
        test_session.commit()

        assert synthesis.id is not None
        assert synthesis.generated_at is not None

    def test_narrative_synthesis_json_data(self, test_session, sample_narrative_synthesis):
        """Should store complex JSON data correctly"""
        complex_data = {
            "bottom_line": {"summary": "Complex test", "immediate_actions": ["action1"]},
            "trends_and_patterns": {"local": [], "national": []},
            "priority_events": [{"event": "Test event", "impact_level": "HIGH"}],
        }

        sample_narrative_synthesis.synthesis_data = complex_data
        test_session.commit()

        retrieved = test_session.query(NarrativeSynthesis).get(sample_narrative_synthesis.id)
        assert retrieved.synthesis_data["bottom_line"]["summary"] == "Complex test"
        assert len(retrieved.synthesis_data["priority_events"]) == 1


class TestContextSnapshotModel:
    """Tests for ContextSnapshot model"""

    def test_create_context_snapshot(self, test_session):
        """Should create a ContextSnapshot"""
        snapshot = ContextSnapshot(
            article_ids=[1, 2, 3, 4, 5],
            context_size_tokens=8000,
            user_profile_hash="hash123",
        )
        test_session.add(snapshot)
        test_session.commit()

        assert snapshot.id is not None
        assert snapshot.article_ids == [1, 2, 3, 4, 5]


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


class TestInstitutionalActivitySchema:
    """
    The institutional activity tables, and the boundary they are built around.

    `beat_entities.kind` admits org / program / document_type. There is no
    person kind and no persons table, so there is no row a per-individual
    activity ledger could be assembled from. A named individual may appear
    inside a rendered situation where the source document names a signatory --
    that is an attribute of a document and expires with it -- but never as a
    row here, because a row here accumulates across runs.

    Added 2026-08-26 with backlog task 006.
    """

    def test_the_kind_vocabulary_is_closed_and_holds_no_person(self):
        from src.database.models import ENTITY_KINDS

        assert ENTITY_KINDS == ("org", "program", "document_type")

    def test_no_table_in_the_schema_is_person_shaped(self, test_engine):
        """
        A blunt structural check over the whole schema, not just the new
        tables: if a persons table is ever added, this fails.
        """
        from sqlalchemy import inspect

        from src.database.models import Base

        forbidden = ("people", "persons", "person", "officials", "individuals", "watchlist")
        names = set(Base.metadata.tables) | set(inspect(test_engine).get_table_names())

        assert not [name for name in names if any(word in name.lower() for word in forbidden)]

    def test_no_column_on_the_activity_tables_names_an_individual(self):
        from src.database.models import BeatEntity, EntityMention

        columns = {column.name for column in BeatEntity.__table__.columns} | {
            column.name for column in EntityMention.__table__.columns
        }

        assert columns == {
            "id",
            "beat_id",
            "kind",
            "name",
            "aliases",
            "created_at",
            "updated_at",
            "entity_id",
            "beat_run_id",
            "synthesis_id",
            "item_count",
            "items_scanned",
            "observed_at",
        }

    def test_one_mention_row_per_entity_per_run(self, test_session):
        """
        The uniqueness that keeps a re-run from doubling a baseline.
        """
        from src.database.models import Beat, BeatEntity, BeatRun, EntityMention

        beat = Beat(name="b")
        test_session.add(beat)
        test_session.flush()
        entity = BeatEntity(beat_id=beat.id, kind="org", name="GSA", aliases=[])
        run = BeatRun(beat_id=beat.id)
        test_session.add_all([entity, run])
        test_session.flush()

        test_session.add(EntityMention(entity_id=entity.id, beat_run_id=run.id, item_count=1))
        test_session.commit()
        test_session.add(EntityMention(entity_id=entity.id, beat_run_id=run.id, item_count=9))

        with pytest.raises(IntegrityError):
            test_session.commit()
