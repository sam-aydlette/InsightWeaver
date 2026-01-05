"""
Pipeline Orchestrator
Coordinates RSS fetching, deduplication, and prioritization in sequence
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from src.config.settings import settings
from src.context.synthesizer import NarrativeSynthesizer
from src.processors.content_filter import ContentFilter
from src.processors.deduplicator import run_deduplication
from src.rss.parallel_fetcher import fetch_all_active_feeds
from src.utils.profile_loader import get_user_profile
from src.utils.profiler import get_profiler, profile

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """Orchestrates the complete data pipeline"""

    def __init__(self,
                 max_concurrent_feeds: int = 10,
                 rate_limit: float = 2.0,
                 dedup_hours: int = 24,
                 prioritize_hours: int = 48,
                 prioritize_limit: int | None = None,
                 topic_filters: dict | None = None,
                 verify_trust: bool = True):
        """
        Initialize pipeline orchestrator

        Args:
            max_concurrent_feeds: Max concurrent RSS feed fetches
            rate_limit: Requests per second for RSS fetching
            dedup_hours: Hours to look back for deduplication
            prioritize_hours: Hours to look back for prioritization
            prioritize_limit: Max articles to prioritize (None = all)
            topic_filters: Optional topic/scope filters for article selection
            verify_trust: Whether to run trust verification (default: True)
        """
        self.max_concurrent_feeds = max_concurrent_feeds
        self.rate_limit = rate_limit
        self.dedup_hours = dedup_hours
        self.prioritize_hours = prioritize_hours
        self.prioritize_limit = prioritize_limit
        self.topic_filters = topic_filters or {}
        self.verify_trust = verify_trust
        self.content_filter = None

    def _should_skip_rss_fetch(self, max_age_minutes: int = 60) -> tuple:
        """
        Check if RSS fetching should be skipped based on recent article freshness

        Args:
            max_age_minutes: Maximum age of articles in minutes to consider fresh

        Returns:
            tuple: (should_skip: bool, most_recent_timestamp: Optional[datetime])
        """
        from src.database.connection import get_db
        from src.database.models import Article

        try:
            with get_db() as session:
                most_recent = session.query(Article.fetched_at).order_by(
                    Article.fetched_at.desc()
                ).first()

                if not most_recent or not most_recent[0]:
                    logger.info("No articles found in database, will fetch RSS feeds")
                    return False, None

                most_recent_time = most_recent[0]

                # Handle timezone-aware comparison
                now = datetime.now(UTC)
                if most_recent_time.tzinfo is None:
                    most_recent_time = most_recent_time.replace(tzinfo=UTC)

                age_minutes = (now - most_recent_time).total_seconds() / 60
                should_skip = age_minutes < max_age_minutes

                if should_skip:
                    logger.info(f"Most recent articles are {age_minutes:.1f} minutes old (<{max_age_minutes}m threshold), skipping RSS fetch")
                else:
                    logger.info(f"Most recent articles are {age_minutes:.1f} minutes old (>{max_age_minutes}m threshold), will fetch RSS feeds")

                return should_skip, most_recent_time

        except Exception as e:
            logger.error(f"Error checking article freshness: {e}")
            # Fail-safe: always fetch on error
            return False, None

    async def run_full_pipeline(self) -> dict[str, Any]:
        """
        Run the complete pipeline:
        1. Fetch RSS feeds
        2. Deduplicate articles
        3. Filter content (based on user profile)
        4. Synthesize narrative (if API key configured)

        Returns:
            Dictionary with results from each stage
        """
        # Start profiling session
        profiler = get_profiler()
        profiler.start_session()

        results = {
            "pipeline_started": datetime.now(UTC).isoformat(),
            "stages": {}
        }

        try:
            # Stage 1: Smart RSS Feed Fetching
            with profile("STAGE_1_RSS_FETCH"):
                logger.info("Starting Stage 1: RSS Feed Fetching")

                # Check if smart RSS fetch is enabled
                smart_fetch_enabled = getattr(settings, 'enable_smart_rss_fetch', True)
                smart_fetch_threshold = getattr(settings, 'smart_rss_fetch_threshold_minutes', 60)

                skip_fetch = False
                most_recent = None

                if smart_fetch_enabled:
                    skip_fetch, most_recent = self._should_skip_rss_fetch(smart_fetch_threshold)

                if skip_fetch:
                    logger.info(f"Skipping RSS fetch (articles < {smart_fetch_threshold} min old)")
                    results["stages"]["fetch"] = {
                        "skipped": True,
                        "reason": f"Articles less than {smart_fetch_threshold} minutes old",
                        "most_recent_fetch": most_recent.isoformat() if most_recent else None,
                        "time_saved_seconds": 60
                    }
                else:
                    fetch_results = await self._fetch_feeds()
                    results["stages"]["fetch"] = fetch_results
                    logger.info(f"Stage 1 complete: {fetch_results['successful_feeds']}/{fetch_results['total_feeds']} feeds fetched")

            # Stage 2: Deduplication (only if we got new articles)
            with profile("STAGE_2_DEDUP"):
                fetch_stage = results["stages"]["fetch"]
                if not fetch_stage.get("skipped", False) and fetch_stage.get("total_articles", 0) > 0:
                    logger.info("Starting Stage 2: Article Deduplication")
                    dedup_results = await self._deduplicate_articles()
                    results["stages"]["deduplication"] = dedup_results
                    logger.info(f"Stage 2 complete: {dedup_results['total_duplicates']} duplicates found")
                else:
                    reason = "RSS fetch was skipped" if fetch_stage.get("skipped") else "No new articles"
                    logger.info(f"Skipping Stage 2: {reason}")
                    results["stages"]["deduplication"] = {"skipped": True, "reason": reason}

            # Stage 3: Content Filtering (based on user profile)
            with profile("STAGE_3_FILTER"):
                logger.info("Starting Stage 3: Content Filtering")
                filter_results = await self._filter_content()
                results["stages"]["filtering"] = filter_results
                logger.info(f"Stage 3 complete: {filter_results['filtered_count']} articles filtered")

            # Stage 4: Narrative Synthesis (only if API key configured)
            with profile("STAGE_4_SYNTHESIS"):
                if settings.anthropic_api_key:
                    logger.info("Starting Stage 4: Narrative Synthesis")
                    synthesis_results = await self._synthesize_narrative()
                    results["stages"]["synthesis"] = synthesis_results

                    articles_synthesized = synthesis_results.get("articles_analyzed", 0)
                    logger.info(f"Stage 4 complete: {articles_synthesized} articles synthesized into narrative")
                else:
                    logger.info("Skipping Stage 4: ANTHROPIC_API_KEY not configured")
                    results["stages"]["synthesis"] = {"skipped": True, "reason": "API key not configured"}

            # Calculate pipeline summary
            results["pipeline_completed"] = datetime.now(UTC).isoformat()
            results["summary"] = self._generate_summary(results)

            logger.info(f"Pipeline complete: {results['summary']['total_stages_run']} stages run successfully")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            results["error"] = str(e)
            results["pipeline_failed"] = datetime.now(UTC).isoformat()
            raise

        return results

    async def _fetch_feeds(self) -> dict[str, Any]:
        """Run RSS feed fetching stage"""
        return await fetch_all_active_feeds(
            max_concurrent=self.max_concurrent_feeds,
            rate_limit=self.rate_limit
        )

    async def _deduplicate_articles(self) -> dict[str, Any]:
        """Run article deduplication stage"""
        # Deduplication is synchronous, wrap in executor
        return await asyncio.get_event_loop().run_in_executor(
            None,
            run_deduplication,
            self.dedup_hours
        )

    async def _filter_content(self) -> dict[str, Any]:
        """Run content filtering stage"""
        from datetime import timedelta

        from src.database.connection import get_db_session
        from src.database.models import Article

        if not self.content_filter:
            # Load user profile and initialize filter
            try:
                user_profile = get_user_profile()
                self.content_filter = ContentFilter(user_profile)
            except FileNotFoundError as e:
                logger.error(f"User profile not found: {e}")
                return {
                    "skipped": True,
                    "reason": "User profile not found",
                    "error": str(e)
                }

        # Get recent unfiltered articles
        session = get_db_session()
        try:
            cutoff_time = datetime.now(UTC) - timedelta(hours=self.dedup_hours)

            articles = session.query(Article).filter(
                Article.created_at >= cutoff_time,
                Article.filtered == False  # Only unfiltered articles
            ).all()

            if not articles:
                return {
                    "articles_evaluated": 0,
                    "filtered_count": 0,
                    "kept_count": 0,
                    "filter_rate": 0,
                    "reasons": {}
                }

            # Filter articles
            kept, filtered = self.content_filter.filter_articles(articles)

            # Commit changes to database
            session.commit()

            # Get statistics
            stats = self.content_filter.get_filter_stats(articles)

            logger.info(f"Content filtering: {stats['filtered_count']}/{stats['total_articles']} filtered ({stats['filter_rate']:.1%})")
            for reason, count in stats['reasons'].items():
                logger.info(f"  - {reason}: {count} articles")

            return stats

        finally:
            session.close()

    async def _synthesize_narrative(self) -> dict[str, Any]:
        """
        Run narrative synthesis stage with trust verification and citations

        Uses trust-verified synthesis with inline citations and automatic
        verification loop (max 3 retries). Falls back to basic synthesis
        if trust verification is disabled.
        """
        synthesizer = NarrativeSynthesizer(topic_filters=self.topic_filters)

        # Check if trust verification is enabled (can be overridden by CLI flag or settings)
        use_trust_verification = self.verify_trust and getattr(settings, 'enable_trust_verification', True)

        if use_trust_verification:
            logger.info("Using trust-verified synthesis with citations")
            return await synthesizer.synthesize_with_trust_verification(
                hours=self.prioritize_hours,
                max_articles=50,
                max_retries=3
            )
        else:
            logger.info("Using basic synthesis (trust verification disabled)")
            return await synthesizer.synthesize(
                hours=self.prioritize_hours,
                max_articles=50
            )

    def _generate_summary(self, results: dict[str, Any]) -> dict[str, Any]:
        """Generate pipeline execution summary"""
        stages = results.get("stages", {})

        # Count successful stages
        stages_run = len([s for s in stages.values() if not s.get("skipped")])

        # Extract key metrics
        fetch_stage = stages.get("fetch", {})
        dedup_stage = stages.get("deduplication", {})
        filter_stage = stages.get("filtering", {})
        priority_stage = stages.get("prioritization", {})
        synthesis_stage = stages.get("synthesis", {})

        summary = {
            "total_stages_run": stages_run,
            "feeds_processed": fetch_stage.get("total_feeds", 0),
            "articles_fetched": fetch_stage.get("total_articles", 0),
            "duplicates_removed": dedup_stage.get("total_duplicates", 0),
            "articles_filtered": filter_stage.get("filtered_count", 0),
            "articles_kept": filter_stage.get("kept_count", 0),
            "articles_synthesized": synthesis_stage.get("articles_analyzed", 0),
            "narrative_generated": synthesis_stage.get("synthesis_id") is not None
        }

        # Calculate duration
        if "pipeline_started" in results and "pipeline_completed" in results:
            start = datetime.fromisoformat(results["pipeline_started"])
            end = datetime.fromisoformat(results["pipeline_completed"])
            duration = (end - start).total_seconds()
            summary["duration_seconds"] = round(duration, 2)

        return summary

async def run_pipeline(
    max_concurrent: int = 10,
    rate_limit: float = 2.0,
    dedup_hours: int = 24,
    prioritize_hours: int = 48,
    prioritize_limit: int | None = None,
    topic_filters: dict | None = None,
    verify_trust: bool = True
) -> dict[str, Any]:
    """
    Convenience function to run the complete pipeline

    Args:
        max_concurrent: Max concurrent RSS feeds to fetch
        rate_limit: Requests per second for RSS fetching
        dedup_hours: Hours to look back for deduplication
        prioritize_hours: Hours to look back for prioritization
        prioritize_limit: Max articles to prioritize (None = all)
        topic_filters: Optional topic/scope filters for article selection
        verify_trust: Whether to run trust verification (default: True)

    Returns:
        Pipeline execution results
    """
    orchestrator = PipelineOrchestrator(
        max_concurrent_feeds=max_concurrent,
        rate_limit=rate_limit,
        dedup_hours=dedup_hours,
        prioritize_hours=prioritize_hours,
        prioritize_limit=prioritize_limit,
        topic_filters=topic_filters,
        verify_trust=verify_trust
    )

    return await orchestrator.run_full_pipeline()
