"""
Pipeline Orchestrator
Coordinates RSS fetching, deduplication, and prioritization in sequence
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from src.rss.parallel_fetcher import fetch_all_active_feeds
from src.processors.deduplicator import run_deduplication
from src.agents.prioritization_agent import PrioritizationAgent
from src.config.settings import settings

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    """Orchestrates the complete data pipeline"""

    def __init__(self,
                 max_concurrent_feeds: int = 10,
                 rate_limit: float = 2.0,
                 dedup_hours: int = 24,
                 prioritize_hours: int = 48,
                 prioritize_limit: Optional[int] = None):
        """
        Initialize pipeline orchestrator

        Args:
            max_concurrent_feeds: Max concurrent RSS feed fetches
            rate_limit: Requests per second for RSS fetching
            dedup_hours: Hours to look back for deduplication
            prioritize_hours: Hours to look back for prioritization
            prioritize_limit: Max articles to prioritize (None = all)
        """
        self.max_concurrent_feeds = max_concurrent_feeds
        self.rate_limit = rate_limit
        self.dedup_hours = dedup_hours
        self.prioritize_hours = prioritize_hours
        self.prioritize_limit = prioritize_limit
        self.prioritization_agent = None

    async def run_full_pipeline(self) -> Dict[str, Any]:
        """
        Run the complete pipeline:
        1. Fetch RSS feeds
        2. Deduplicate articles
        3. Prioritize articles (if API key configured)

        Returns:
            Dictionary with results from each stage
        """
        results = {
            "pipeline_started": datetime.now(timezone.utc).isoformat(),
            "stages": {}
        }

        try:
            # Stage 1: Fetch RSS feeds
            logger.info("Starting Stage 1: RSS Feed Fetching")
            fetch_results = await self._fetch_feeds()
            results["stages"]["fetch"] = fetch_results
            logger.info(f"Stage 1 complete: {fetch_results['successful_feeds']}/{fetch_results['total_feeds']} feeds fetched")

            # Stage 2: Deduplication (only if we got new articles)
            if fetch_results.get("total_articles", 0) > 0:
                logger.info("Starting Stage 2: Article Deduplication")
                dedup_results = await self._deduplicate_articles()
                results["stages"]["deduplication"] = dedup_results
                logger.info(f"Stage 2 complete: {dedup_results['total_duplicates']} duplicates found")
            else:
                logger.info("Skipping Stage 2: No new articles to deduplicate")
                results["stages"]["deduplication"] = {"skipped": True, "reason": "No new articles"}

            # Stage 3: Prioritization (only if API key is configured)
            if settings.anthropic_api_key:
                logger.info("Starting Stage 3: Article Prioritization")
                prioritize_results = await self._prioritize_articles()
                results["stages"]["prioritization"] = prioritize_results

                high_priority = prioritize_results.get("summary", {}).get("high_priority_articles", 0)
                logger.info(f"Stage 3 complete: {high_priority} high-priority articles identified")
            else:
                logger.info("Skipping Stage 3: ANTHROPIC_API_KEY not configured")
                results["stages"]["prioritization"] = {"skipped": True, "reason": "API key not configured"}

            # Calculate pipeline summary
            results["pipeline_completed"] = datetime.now(timezone.utc).isoformat()
            results["summary"] = self._generate_summary(results)

            logger.info(f"Pipeline complete: {results['summary']['total_stages_run']} stages run successfully")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            results["error"] = str(e)
            results["pipeline_failed"] = datetime.now(timezone.utc).isoformat()
            raise

        return results

    async def _fetch_feeds(self) -> Dict[str, Any]:
        """Run RSS feed fetching stage"""
        return await fetch_all_active_feeds(
            max_concurrent=self.max_concurrent_feeds,
            rate_limit=self.rate_limit
        )

    async def _deduplicate_articles(self) -> Dict[str, Any]:
        """Run article deduplication stage"""
        # Deduplication is synchronous, wrap in executor
        return await asyncio.get_event_loop().run_in_executor(
            None,
            run_deduplication,
            self.dedup_hours
        )

    async def _prioritize_articles(self) -> Dict[str, Any]:
        """Run article prioritization stage"""
        if not self.prioritization_agent:
            self.prioritization_agent = PrioritizationAgent()

        # Two-stage analysis handles cost optimization internally
        return await self.prioritization_agent.run_analysis(
            hours=self.prioritize_hours,
            limit=self.prioritize_limit  # Can be None for all articles
        )

    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate pipeline execution summary"""
        stages = results.get("stages", {})

        # Count successful stages
        stages_run = len([s for s in stages.values() if not s.get("skipped")])

        # Extract key metrics
        fetch_stage = stages.get("fetch", {})
        dedup_stage = stages.get("deduplication", {})
        priority_stage = stages.get("prioritization", {})

        summary = {
            "total_stages_run": stages_run,
            "feeds_processed": fetch_stage.get("total_feeds", 0),
            "articles_fetched": fetch_stage.get("total_articles", 0),
            "duplicates_removed": dedup_stage.get("total_duplicates", 0),
            "articles_prioritized": priority_stage.get("articles_processed", 0),
            "high_priority_articles": priority_stage.get("summary", {}).get("high_priority_articles", 0)
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
    prioritize_limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Convenience function to run the complete pipeline

    Args:
        max_concurrent: Max concurrent RSS feeds to fetch
        rate_limit: Requests per second for RSS fetching
        dedup_hours: Hours to look back for deduplication
        prioritize_hours: Hours to look back for prioritization
        prioritize_limit: Max articles to prioritize (None = all)

    Returns:
        Pipeline execution results
    """
    orchestrator = PipelineOrchestrator(
        max_concurrent_feeds=max_concurrent,
        rate_limit=rate_limit,
        dedup_hours=dedup_hours,
        prioritize_hours=prioritize_hours,
        prioritize_limit=prioritize_limit
    )

    return await orchestrator.run_full_pipeline()