"""
Tests for database models
Tests model creation, relationships, constraints, and indexes
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from src.database.models import (
    AnalysisRun,
    APIDataPoint,
    APIDataSource,
    Article,
    CausalChain,
    ContextSnapshot,
    ForecastRun,
    ForecastScenario,
    LongTermForecast,
    MemoryFact,
    MonitoredPage,
    NarrativeSynthesis,
    PageChange,
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


class TestAPIDataSourceModel:
    """Tests for APIDataSource model"""

    def test_create_api_data_source(self, test_session):
        """Should create an APIDataSource"""
        source = APIDataSource(
            name="Test API",
            source_type="calendar",
            endpoint_url="https://api.example.com",
        )
        test_session.add(source)
        test_session.commit()

        assert source.id is not None
        assert source.refresh_frequency_hours == 24  # Default
        assert source.is_active is True  # Default


class TestAPIDataPointModel:
    """Tests for APIDataPoint model"""

    def test_create_api_data_point(self, test_session, sample_api_data_source):
        """Should create an APIDataPoint"""
        point = APIDataPoint(
            source_id=sample_api_data_source.id,
            data_type="event",
            external_id="ext-123",
            title="Test Event",
        )
        test_session.add(point)
        test_session.commit()

        assert point.id is not None
        assert point.included_count == 0  # Default

    def test_api_data_point_unique_constraint(self, test_session, sample_api_data_source):
        """APIDataPoint source_id + external_id should be unique"""
        point1 = APIDataPoint(
            source_id=sample_api_data_source.id,
            data_type="event",
            external_id="same-id",
        )
        test_session.add(point1)
        test_session.commit()

        point2 = APIDataPoint(
            source_id=sample_api_data_source.id,
            data_type="event",
            external_id="same-id",
        )
        test_session.add(point2)

        with pytest.raises(IntegrityError):
            test_session.commit()


class TestMonitoredPageModel:
    """Tests for MonitoredPage model"""

    def test_create_monitored_page(self, test_session):
        """Should create a MonitoredPage"""
        page = MonitoredPage(
            url="https://example.gov/policy",
            name="Policy Page",
        )
        test_session.add(page)
        test_session.commit()

        assert page.id is not None
        assert page.check_frequency_hours == 24  # Default
        assert page.is_active is True  # Default

    def test_monitored_page_url_unique(self, test_session):
        """MonitoredPage URL should be unique"""
        page1 = MonitoredPage(url="https://example.gov/page", name="Page 1")
        test_session.add(page1)
        test_session.commit()

        page2 = MonitoredPage(url="https://example.gov/page", name="Page 2")
        test_session.add(page2)

        with pytest.raises(IntegrityError):
            test_session.commit()


class TestPageChangeModel:
    """Tests for PageChange model"""

    def test_create_page_change(self, test_session, sample_monitored_page):
        """Should create a PageChange"""
        change = PageChange(
            monitored_page_id=sample_monitored_page.id,
            change_type="content_added",
            new_content="New content here",
        )
        test_session.add(change)
        test_session.commit()

        assert change.id is not None
        assert change.detected_at is not None


class TestMemoryFactModel:
    """Tests for MemoryFact model"""

    def test_create_memory_fact(self, test_session):
        """Should create a MemoryFact"""
        fact = MemoryFact(
            fact_type="metric",
            subject="GDP growth",
            predicate="rate",
            object="2.5%",
            temporal_context="Q4 2025",
            confidence=0.9,
        )
        test_session.add(fact)
        test_session.commit()

        assert fact.id is not None
        assert fact.created_at is not None

    def test_memory_fact_with_expiration(self, test_session):
        """Should handle expiration dates"""
        fact = MemoryFact(
            fact_type="trend",
            subject="Stock market",
            predicate="direction",
            object="upward",
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
        test_session.add(fact)
        test_session.commit()

        assert fact.expires_at is not None


class TestForecastRunModel:
    """Tests for ForecastRun model"""

    def test_create_forecast_run(self, test_session):
        """Should create a ForecastRun"""
        run = ForecastRun(
            run_type="multi_horizon",
            horizons_requested=["6mo", "1yr"],
            scenario_count=3,
            status="running",
        )
        test_session.add(run)
        test_session.commit()

        assert run.id is not None
        assert run.horizons_requested == ["6mo", "1yr"]


class TestLongTermForecastModel:
    """Tests for LongTermForecast model"""

    def test_create_long_term_forecast(self, test_session, sample_forecast_run):
        """Should create a LongTermForecast"""
        forecast = LongTermForecast(
            forecast_run_id=sample_forecast_run.id,
            time_horizon="1yr",
            horizon_months=12,
            target_date=datetime.utcnow() + timedelta(days=365),
            forecast_data={"scenarios": []},
        )
        test_session.add(forecast)
        test_session.commit()

        assert forecast.id is not None
        assert forecast.time_horizon == "1yr"


class TestForecastScenarioModel:
    """Tests for ForecastScenario model"""

    def test_create_forecast_scenario(self, test_session, sample_long_term_forecast):
        """Should create a ForecastScenario"""
        scenario = ForecastScenario(
            forecast_id=sample_long_term_forecast.id,
            scenario_type="optimistic",
            scenario_name="Best Case",
            scenario_probability=0.25,
        )
        test_session.add(scenario)
        test_session.commit()

        assert scenario.id is not None


class TestCausalChainModel:
    """Tests for CausalChain model"""

    def test_create_causal_chain(self, test_session, sample_long_term_forecast):
        """Should create a CausalChain"""
        chain = CausalChain(
            forecast_id=sample_long_term_forecast.id,
            chain_name="Economic Impact",
            initial_cause="Tax increase",
            intermediate_effects=["Reduced spending", "Lower investment"],
            final_outcome="Economic slowdown",
            time_to_unfold_months=12,
            confidence=0.6,
        )
        test_session.add(chain)
        test_session.commit()

        assert chain.id is not None
        assert len(chain.intermediate_effects) == 2


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

    def test_memory_fact_indexes_exist(self, test_engine):
        """MemoryFact table should have retrieval indexes"""
        from sqlalchemy import inspect

        inspector = inspect(test_engine)
        indexes = inspector.get_indexes("memory_facts")
        index_names = [idx["name"] for idx in indexes]

        expected_indexes = [
            "idx_memory_fact_subject",
            "idx_memory_fact_type",
            "idx_memory_fact_temporal",
        ]

        for idx in expected_indexes:
            assert idx in index_names, f"Index {idx} should exist on memory_facts table"
