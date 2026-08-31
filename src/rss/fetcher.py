import asyncio
import logging
from datetime import datetime

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from src.database.models import RSSFeed

logger = logging.getLogger(__name__)


class LegacyWritePathClosed(RuntimeError):
    """
    Raised by the legacy RSS storage entry points, which no longer write.

    Closed 2026-08-31 for backlog task 025. ``RSSFetcher.fetch_and_store_feed``
    used to insert ``Article`` rows itself, which was the one remaining way to
    grow the corpus without also writing the ``Observation`` that task 014 made
    the authoritative record. An article stored that way can never be routed --
    routing reads observations -- and nothing surfaces the gap: the corpus
    grows and the coverage hole looks like a source problem.

    It is closed rather than rewired because the work it did is already done
    correctly elsewhere: ``src/sources/rss_adapter.py`` reads the same feed
    through the same normalizer and stores through ``src/sources/store.py``,
    which writes the article and the observation in one transaction. Wiring
    this second entry point into ``store_items`` would have preserved a
    duplicate ingestion path that must be kept in step with the adapter path
    forever, for no caller. Reading a feed is unaffected: ``fetch_feed`` and
    ``normalize_article`` are untouched and are what the adapter uses.
    """


LEGACY_PATH_MESSAGE = (
    "The legacy RSS write path is closed (backlog task 025). It wrote articles "
    "without observations, which Tier 1 routing cannot see. Ingest through "
    "src/sources: RSSAdapter reads the feed and src.sources.store.store_items "
    "writes the article and its observation in one transaction."
)


class RSSFetcher:
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def close(self):
        """Close HTTP client session"""
        await self.session.aclose()

    async def fetch_feed(self, feed_url: str) -> tuple[bool, dict | None, str | None]:
        """
        Fetch and parse an RSS feed
        Returns: (success, parsed_feed_data, error_message)
        """
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Fetching RSS feed: {feed_url} (attempt {attempt + 1})")

                response = await self.session.get(feed_url)
                response.raise_for_status()

                # Parse the RSS content
                feed_data = feedparser.parse(response.content)

                if feed_data.bozo:
                    logger.warning(
                        f"Feed parsing issues for {feed_url}: {feed_data.bozo_exception}"
                    )

                return True, feed_data, None

            except httpx.HTTPError as e:
                logger.warning(f"HTTP error fetching {feed_url}: {e}")
                if attempt == self.max_retries - 1:
                    return False, None, f"HTTP error: {str(e)}"
                await asyncio.sleep(2**attempt)  # Exponential backoff

            except Exception as e:
                logger.error(f"Unexpected error fetching {feed_url}: {e}")
                return False, None, f"Unexpected error: {str(e)}"

        return False, None, "Max retries exceeded"

    def normalize_article(self, entry, _feed_info: dict) -> dict:
        """Normalize an RSS entry into our article format"""

        # Extract published date
        published_date = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            published_date = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
            published_date = datetime(*entry.updated_parsed[:6])

        # Extract and clean content
        content = ""
        if hasattr(entry, "content") and entry.content:
            content = entry.content[0].value if isinstance(entry.content, list) else entry.content
        elif hasattr(entry, "summary"):
            content = entry.summary

        # Clean HTML from content
        normalized_content = self.clean_html(content) if content else ""

        # Extract categories
        categories = []
        if hasattr(entry, "tags"):
            categories = [tag.term for tag in entry.tags]

        return {
            "guid": getattr(entry, "id", entry.link),
            "url": getattr(entry, "link", ""),
            "title": getattr(entry, "title", ""),
            "description": getattr(entry, "summary", ""),
            "content": content,
            "normalized_content": normalized_content,
            "published_date": published_date,
            "author": getattr(entry, "author", ""),
            "categories": categories,
            "word_count": len(normalized_content.split()) if normalized_content else 0,
            "language": "en",  # Default to English for now
        }

    def clean_html(self, html_content: str) -> str:
        """Remove HTML tags and return clean text"""
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text and clean up whitespace
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = " ".join(chunk for chunk in chunks if chunk)

        return clean_text

    # ARG002: feed_id is unused on purpose. The parameter is kept so an existing
    # caller reaches the refusal rather than a TypeError, which would read as a
    # signature change rather than as a closed path (2026-08-31, task 025).
    async def fetch_and_store_feed(self, feed_id: int) -> tuple[bool, int, str | None]:  # noqa: ARG002
        """
        Closed. Always raises :class:`LegacyWritePathClosed`; stores nothing.

        The signature is kept so that a caller outside this repository -- a
        cron entry or a shell script -- fails loudly at the call site with a
        message naming the replacement, rather than silently importing a name
        that vanished or, worse, continuing to write observation-less articles.
        Nothing is read and no session is opened before the raise, so a call
        cannot touch the database at all: in particular it cannot stamp
        ``last_fetched`` or increment ``error_count`` toward auto-deactivation.
        """
        raise LegacyWritePathClosed(LEGACY_PATH_MESSAGE)

    async def _fetch_with_retry(
        self, url: str, feed_name: str
    ) -> tuple[bool, dict | None, str | None]:
        """Enhanced fetch with smarter retry logic"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Fetching {feed_name}: attempt {attempt + 1}/{self.max_retries}")

                response = await self.session.get(url)
                response.raise_for_status()

                # Parse the RSS content
                feed_data = feedparser.parse(response.content)

                # Check for parsing issues
                if feed_data.bozo:
                    logger.warning(
                        f"Feed parsing issues for {feed_name}: {feed_data.bozo_exception}"
                    )
                    # Still continue if we got some data
                    if not feed_data.entries:
                        return False, None, f"Feed parsing failed: {feed_data.bozo_exception}"

                # Check if feed has any entries
                if not feed_data.entries:
                    return False, None, "Feed contains no entries"

                logger.debug(
                    f"Successfully fetched {len(feed_data.entries)} entries from {feed_name}"
                )
                return True, feed_data, None

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed for {feed_name}: {e}")

                # Exponential backoff with jitter
                if attempt < self.max_retries - 1:
                    import random

                    backoff_time = (2**attempt) + random.uniform(0, 1)
                    await asyncio.sleep(backoff_time)

        return False, None, f"Failed after {self.max_retries} attempts: {last_error}"


def create_test_feed(
    db: Session,
    name: str = "NASA Breaking News",
    url: str = "https://www.nasa.gov/rss/dyn/breaking_news.rss",
) -> RSSFeed:
    """Create a test RSS feed for development"""
    existing = db.query(RSSFeed).filter(RSSFeed.url == url).first()
    if existing:
        return existing

    feed = RSSFeed(name=name, url=url, category="news", is_active=True)
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed
