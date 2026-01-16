"""
Tests for Pipeline Orchestrator
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.orchestrator import PipelineOrchestrator, run_pipeline


class TestPipelineOrchestratorInit:
    """Tests for PipelineOrchestrator initialization"""

    def test_init_with_defaults(self):
        """Should initialize with default values"""
        orchestrator = PipelineOrchestrator()

        assert orchestrator.max_concurrent_feeds == 10
        assert orchestrator.rate_limit == 2.0
        assert orchestrator.dedup_hours == 24
        assert orchestrator.prioritize_hours == 48
        assert orchestrator.prioritize_limit is None
        assert orchestrator.topic_filters == {}
        assert orchestrator.verify_trust is True
        assert orchestrator.content_filter is None

    def test_init_with_custom_values(self):
        """Should accept custom initialization values"""
        orchestrator = PipelineOrchestrator(
            max_concurrent_feeds=5,
            rate_limit=1.0,
            dedup_hours=12,
            prioritize_hours=24,
            prioritize_limit=100,
            topic_filters={"topics": ["cybersecurity"]},
            verify_trust=False,
        )

        assert orchestrator.max_concurrent_feeds == 5
        assert orchestrator.rate_limit == 1.0
        assert orchestrator.dedup_hours == 12
        assert orchestrator.prioritize_hours == 24
        assert orchestrator.prioritize_limit == 100
        assert orchestrator.topic_filters == {"topics": ["cybersecurity"]}
        assert orchestrator.verify_trust is False


class TestShouldSkipRssFetch:
    """Tests for RSS fetch skip logic"""

    @patch("src.database.connection.get_db")
    def test_skip_when_articles_fresh(self, mock_get_db):
        """Should skip fetch when articles are fresh"""
        orchestrator = PipelineOrchestrator()

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)

        # Mock recent article (30 minutes old)
        recent_time = datetime.now(UTC) - timedelta(minutes=30)
        mock_session.query.return_value.order_by.return_value.first.return_value = (
            recent_time,
        )

        should_skip, most_recent = orchestrator._should_skip_rss_fetch(max_age_minutes=60)

        assert should_skip is True
        assert most_recent is not None

    @patch("src.database.connection.get_db")
    def test_no_skip_when_articles_stale(self, mock_get_db):
        """Should not skip fetch when articles are stale"""
        orchestrator = PipelineOrchestrator()

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)

        # Mock old article (2 hours old)
        old_time = datetime.now(UTC) - timedelta(hours=2)
        mock_session.query.return_value.order_by.return_value.first.return_value = (
            old_time,
        )

        should_skip, most_recent = orchestrator._should_skip_rss_fetch(max_age_minutes=60)

        assert should_skip is False
        assert most_recent is not None

    @patch("src.database.connection.get_db")
    def test_no_skip_when_no_articles(self, mock_get_db):
        """Should not skip fetch when no articles exist"""
        orchestrator = PipelineOrchestrator()

        # Mock database session with no articles
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=None)
        mock_session.query.return_value.order_by.return_value.first.return_value = None

        should_skip, most_recent = orchestrator._should_skip_rss_fetch()

        assert should_skip is False
        assert most_recent is None

    @patch("src.database.connection.get_db")
    def test_no_skip_on_database_error(self, mock_get_db):
        """Should not skip fetch on database error (fail-safe)"""
        orchestrator = PipelineOrchestrator()

        # Mock database error
        mock_get_db.return_value.__enter__ = MagicMock(
            side_effect=Exception("DB error")
        )

        should_skip, most_recent = orchestrator._should_skip_rss_fetch()

        assert should_skip is False
        assert most_recent is None


class TestRunFullPipeline:
    """Tests for full pipeline execution"""

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.get_profiler")
    @patch("src.pipeline.orchestrator.profile")
    async def test_pipeline_runs_all_stages(
        self, mock_profile, mock_get_profiler, mock_settings
    ):
        """Should run all pipeline stages"""
        orchestrator = PipelineOrchestrator()

        # Mock profiler
        mock_profiler = MagicMock()
        mock_get_profiler.return_value = mock_profiler
        mock_profile.return_value.__enter__ = MagicMock()
        mock_profile.return_value.__exit__ = MagicMock()

        # Mock all stage methods
        orchestrator._should_skip_rss_fetch = MagicMock(return_value=(False, None))
        orchestrator._fetch_feeds = AsyncMock(
            return_value={"total_feeds": 10, "successful_feeds": 10, "total_articles": 50}
        )
        orchestrator._deduplicate_articles = AsyncMock(
            return_value={"total_duplicates": 5}
        )
        orchestrator._filter_content = AsyncMock(
            return_value={"filtered_count": 10, "kept_count": 40}
        )
        orchestrator._synthesize_narrative = AsyncMock(
            return_value={"synthesis_id": 1, "articles_analyzed": 40}
        )

        results = await orchestrator.run_full_pipeline()

        assert "stages" in results
        assert "fetch" in results["stages"]
        assert "deduplication" in results["stages"]
        assert "filtering" in results["stages"]
        assert "synthesis" in results["stages"]
        assert "pipeline_completed" in results
        assert "summary" in results

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.get_profiler")
    @patch("src.pipeline.orchestrator.profile")
    async def test_pipeline_skips_fetch_when_fresh(
        self, mock_profile, mock_get_profiler, mock_settings
    ):
        """Should skip fetch when articles are fresh"""
        orchestrator = PipelineOrchestrator()

        # Mock profiler
        mock_profiler = MagicMock()
        mock_get_profiler.return_value = mock_profiler
        mock_profile.return_value.__enter__ = MagicMock()
        mock_profile.return_value.__exit__ = MagicMock()

        # Mock skip condition
        recent_time = datetime.now(UTC) - timedelta(minutes=30)
        orchestrator._should_skip_rss_fetch = MagicMock(return_value=(True, recent_time))
        orchestrator._filter_content = AsyncMock(
            return_value={"filtered_count": 0, "kept_count": 0}
        )

        results = await orchestrator.run_full_pipeline()

        assert results["stages"]["fetch"]["skipped"] is True
        assert results["stages"]["deduplication"]["skipped"] is True

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.get_profiler")
    @patch("src.pipeline.orchestrator.profile")
    @patch("src.pipeline.orchestrator.settings")
    async def test_pipeline_skips_synthesis_without_api_key(
        self, mock_settings_obj, mock_profile, mock_get_profiler
    ):
        """Should skip synthesis when API key not configured"""
        orchestrator = PipelineOrchestrator()

        # Mock profiler
        mock_profiler = MagicMock()
        mock_get_profiler.return_value = mock_profiler
        mock_profile.return_value.__enter__ = MagicMock()
        mock_profile.return_value.__exit__ = MagicMock()

        # Mock settings without API key
        mock_settings_obj.anthropic_api_key = None
        mock_settings_obj.enable_smart_rss_fetch = False

        # Mock stage methods
        orchestrator._fetch_feeds = AsyncMock(
            return_value={"total_feeds": 10, "successful_feeds": 10, "total_articles": 50}
        )
        orchestrator._deduplicate_articles = AsyncMock(
            return_value={"total_duplicates": 5}
        )
        orchestrator._filter_content = AsyncMock(
            return_value={"filtered_count": 10, "kept_count": 40}
        )

        results = await orchestrator.run_full_pipeline()

        assert results["stages"]["synthesis"]["skipped"] is True
        assert results["stages"]["synthesis"]["reason"] == "API key not configured"


class TestFetchFeeds:
    """Tests for feed fetching stage"""

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.fetch_all_active_feeds")
    async def test_fetch_feeds_calls_parallel_fetcher(self, mock_fetch):
        """Should call parallel fetcher with correct params"""
        orchestrator = PipelineOrchestrator(max_concurrent_feeds=5, rate_limit=1.5)

        mock_fetch.return_value = {"total_feeds": 10, "total_articles": 50}

        await orchestrator._fetch_feeds()

        mock_fetch.assert_called_once_with(max_concurrent=5, rate_limit=1.5)


class TestDeduplicateArticles:
    """Tests for deduplication stage"""

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.run_deduplication")
    async def test_deduplicate_calls_deduplicator(self, mock_dedup):
        """Should call deduplication with correct hours"""
        orchestrator = PipelineOrchestrator(dedup_hours=12)

        mock_dedup.return_value = {"total_duplicates": 5}

        await orchestrator._deduplicate_articles()

        mock_dedup.assert_called_once_with(12)


class TestFilterContent:
    """Tests for content filtering stage"""

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.ContentFilter")
    @patch("src.pipeline.orchestrator.get_user_profile")
    @patch("src.database.connection.get_db_session")
    async def test_filter_content_returns_stats(
        self, mock_session, mock_get_profile, mock_filter_class
    ):
        """Should return filter stats when articles exist"""
        orchestrator = PipelineOrchestrator()

        # Mock user profile
        mock_profile = MagicMock()
        mock_get_profile.return_value = mock_profile

        # Mock database session
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        # Mock content filter
        mock_filter = MagicMock()
        mock_filter_class.return_value = mock_filter
        mock_filter.filter_articles.return_value = ([], [])
        mock_filter.get_filter_stats.return_value = {
            "articles_evaluated": 0,
            "filtered_count": 0,
            "kept_count": 0,
            "filter_rate": 0,
            "reasons": {},
        }

        result = await orchestrator._filter_content()

        assert "articles_evaluated" in result
        assert result["filtered_count"] == 0

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.get_user_profile")
    async def test_filter_content_handles_missing_profile(self, mock_get_profile):
        """Should handle missing user profile"""
        orchestrator = PipelineOrchestrator()
        orchestrator.content_filter = None  # Ensure it needs to load profile

        mock_get_profile.side_effect = FileNotFoundError("Profile not found")

        result = await orchestrator._filter_content()

        assert result["skipped"] is True
        assert "User profile not found" in result["reason"]


class TestSynthesizeNarrative:
    """Tests for narrative synthesis stage"""

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.NarrativeSynthesizer")
    @patch("src.pipeline.orchestrator.settings")
    async def test_synthesize_with_trust_verification(
        self, mock_settings, mock_synthesizer_class
    ):
        """Should use trust-verified synthesis by default"""
        mock_settings.enable_trust_verification = True

        orchestrator = PipelineOrchestrator(verify_trust=True)

        mock_synthesizer = MagicMock()
        mock_synthesizer_class.return_value = mock_synthesizer
        mock_synthesizer.synthesize_with_trust_verification = AsyncMock(
            return_value={"synthesis_id": 1}
        )

        await orchestrator._synthesize_narrative()

        mock_synthesizer.synthesize_with_trust_verification.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.pipeline.orchestrator.NarrativeSynthesizer")
    @patch("src.pipeline.orchestrator.settings")
    async def test_synthesize_without_trust_verification(
        self, mock_settings, mock_synthesizer_class
    ):
        """Should use basic synthesis when trust verification disabled"""
        mock_settings.enable_trust_verification = False

        orchestrator = PipelineOrchestrator(verify_trust=False)

        mock_synthesizer = MagicMock()
        mock_synthesizer_class.return_value = mock_synthesizer
        mock_synthesizer.synthesize = AsyncMock(return_value={"synthesis_id": 1})

        await orchestrator._synthesize_narrative()

        mock_synthesizer.synthesize.assert_called_once()


class TestGenerateSummary:
    """Tests for summary generation"""

    def test_generate_summary_counts_stages(self, sample_pipeline_results):
        """Should count non-skipped stages"""
        orchestrator = PipelineOrchestrator()

        summary = orchestrator._generate_summary(sample_pipeline_results)

        assert summary["total_stages_run"] == 4

    def test_generate_summary_extracts_metrics(self, sample_pipeline_results):
        """Should extract key metrics from stages"""
        orchestrator = PipelineOrchestrator()

        summary = orchestrator._generate_summary(sample_pipeline_results)

        assert "feeds_processed" in summary
        assert "articles_fetched" in summary
        assert "duplicates_removed" in summary
        assert "articles_filtered" in summary

    def test_generate_summary_calculates_duration(self):
        """Should calculate pipeline duration"""
        orchestrator = PipelineOrchestrator()

        now = datetime.now(UTC)
        results = {
            "pipeline_started": now.isoformat(),
            "pipeline_completed": (now + timedelta(seconds=30)).isoformat(),
            "stages": {},
        }

        summary = orchestrator._generate_summary(results)

        assert "duration_seconds" in summary
        assert summary["duration_seconds"] >= 29  # Allow for timing variance


class TestRunPipelineFunction:
    """Tests for convenience function"""

    @pytest.mark.asyncio
    @patch.object(PipelineOrchestrator, "run_full_pipeline")
    async def test_run_pipeline_creates_orchestrator(self, mock_run):
        """Should create orchestrator and run pipeline"""
        mock_run.return_value = {"stages": {}}

        await run_pipeline(
            max_concurrent=5,
            rate_limit=1.0,
            dedup_hours=12,
            prioritize_hours=24,
            topic_filters={"topics": ["cybersecurity"]},
            verify_trust=False,
        )

        mock_run.assert_called_once()
