"""
Parallel RSS Fetcher with rate limiting and error handling
Efficiently processes multiple RSS feeds concurrently
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime

from src.database.connection import get_db
from src.database.models import RSSFeed
from src.rss.fetcher import RSSFetcher

logger = logging.getLogger(__name__)


@dataclass
class FetchResult:
    """Result of fetching a single RSS feed"""

    feed_id: int
    feed_name: str
    success: bool
    articles_count: int
    error_message: str | None
    fetch_time: float


class ParallelRSSFetcher:
    """Fetches multiple RSS feeds in parallel with rate limiting"""

    def __init__(
        self, max_concurrent_feeds: int = 10, requests_per_second: float = 2.0, timeout: int = 30
    ):
        self.max_concurrent_feeds = max_concurrent_feeds
        self.requests_per_second = requests_per_second
        self.timeout = timeout
        self.rate_limiter = asyncio.Semaphore(max_concurrent_feeds)
        self.last_request_time = 0.0

    async def _rate_limited_fetch(self, fetcher: RSSFetcher, feed: RSSFeed) -> FetchResult:
        """Fetch a single feed with rate limiting"""
        async with self.rate_limiter:
            # Rate limiting: ensure minimum time between requests
            current_time = time.time()
            time_since_last = current_time - self.last_request_time
            min_interval = 1.0 / self.requests_per_second

            if time_since_last < min_interval:
                sleep_time = min_interval - time_since_last
                await asyncio.sleep(sleep_time)

            self.last_request_time = time.time()

            # Fetch the feed
            start_time = time.time()
            try:
                success, articles_count, error = await fetcher.fetch_and_store_feed(feed.id)
                fetch_time = time.time() - start_time

                return FetchResult(
                    feed_id=feed.id,
                    feed_name=feed.name,
                    success=success,
                    articles_count=articles_count,
                    error_message=error,
                    fetch_time=fetch_time,
                )

            except Exception as e:
                fetch_time = time.time() - start_time
                logger.error(f"Unexpected error fetching {feed.name}: {e}")

                return FetchResult(
                    feed_id=feed.id,
                    feed_name=feed.name,
                    success=False,
                    articles_count=0,
                    error_message=f"Unexpected error: {str(e)}",
                    fetch_time=fetch_time,
                )

    async def fetch_all_feeds(self, feeds: list[RSSFeed]) -> dict[str, any]:
        """
        Fetch all feeds in parallel with rate limiting
        Returns summary statistics and results
        """
        if not feeds:
            logger.warning("No feeds provided for fetching")
            return self._empty_results()

        start_time = time.time()
        logger.info(f"Starting parallel fetch of {len(feeds)} feeds...")

        # Create fetcher instance
        fetcher = RSSFetcher(timeout=self.timeout)

        try:
            # Create tasks for all feeds
            tasks = [self._rate_limited_fetch(fetcher, feed) for feed in feeds]

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            fetch_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task exception: {result}")
                    # Create a failed result for exceptions
                    fetch_results.append(
                        FetchResult(
                            feed_id=0,
                            feed_name="Unknown",
                            success=False,
                            articles_count=0,
                            error_message=str(result),
                            fetch_time=0.0,
                        )
                    )
                else:
                    fetch_results.append(result)

            total_time = time.time() - start_time

            # Generate summary
            summary = self._generate_summary(fetch_results, total_time)

            logger.info(
                f"Parallel fetch completed in {total_time:.2f}s: "
                f"{summary['successful_feeds']}/{summary['total_feeds']} successful, "
                f"{summary['total_articles']} articles"
            )

            return summary

        finally:
            await fetcher.close()

    def _generate_summary(self, results: list[FetchResult], total_time: float) -> dict[str, any]:
        """Generate summary statistics from fetch results"""
        successful_feeds = sum(1 for r in results if r.success)
        failed_feeds = len(results) - successful_feeds
        total_articles = sum(r.articles_count for r in results)

        # Calculate timing statistics
        successful_times = [r.fetch_time for r in results if r.success]
        avg_fetch_time = sum(successful_times) / len(successful_times) if successful_times else 0.0

        # Group errors
        error_summary = {}
        for result in results:
            if not result.success and result.error_message:
                # Simplify error message for grouping
                error_type = (
                    result.error_message.split(":")[0]
                    if ":" in result.error_message
                    else result.error_message
                )
                error_summary[error_type] = error_summary.get(error_type, 0) + 1

        # Feeds that succeeded but got no articles
        empty_feeds = [r for r in results if r.success and r.articles_count == 0]

        return {
            "total_feeds": len(results),
            "successful_feeds": successful_feeds,
            "failed_feeds": failed_feeds,
            "total_articles": total_articles,
            "total_time": total_time,
            "avg_fetch_time": avg_fetch_time,
            "articles_per_second": total_articles / total_time if total_time > 0 else 0,
            "feeds_per_second": len(results) / total_time if total_time > 0 else 0,
            "error_summary": error_summary,
            "empty_feeds": [f.feed_name for f in empty_feeds],
            "failed_feeds_list": [f.feed_name for f in results if not f.success],
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _empty_results(self) -> dict[str, any]:
        """Return empty results structure"""
        return {
            "total_feeds": 0,
            "successful_feeds": 0,
            "failed_feeds": 0,
            "total_articles": 0,
            "total_time": 0.0,
            "avg_fetch_time": 0.0,
            "articles_per_second": 0.0,
            "feeds_per_second": 0.0,
            "error_summary": {},
            "empty_feeds": [],
            "failed_feeds_list": [],
            "timestamp": datetime.utcnow().isoformat(),
        }


async def fetch_all_active_feeds(
    max_concurrent: int = 10, rate_limit: float = 2.0
) -> dict[str, any]:
    """
    Convenience function to fetch all active feeds from database
    """
    # Get active feed IDs and basic info from database
    with get_db() as db:
        active_feeds_data = (
            db.query(RSSFeed.id, RSSFeed.name, RSSFeed.url, RSSFeed.category)
            .filter(RSSFeed.is_active.is_(True))
            .all()
        )

    if not active_feeds_data:
        logger.warning("No active feeds found in database")
        return ParallelRSSFetcher()._empty_results()

    # Convert to simple feed objects for processing
    active_feeds = []
    for feed_data in active_feeds_data:
        feed_obj = RSSFeed(
            id=feed_data.id, name=feed_data.name, url=feed_data.url, category=feed_data.category
        )
        active_feeds.append(feed_obj)

    # Create parallel fetcher and process feeds
    parallel_fetcher = ParallelRSSFetcher(
        max_concurrent_feeds=max_concurrent, requests_per_second=rate_limit
    )

    return await parallel_fetcher.fetch_all_feeds(active_feeds)
