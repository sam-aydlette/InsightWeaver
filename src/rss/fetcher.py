import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from src.database.models import RSSFeed, Article
from src.database.connection import get_db

logger = logging.getLogger(__name__)

class RSSFetcher:
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def close(self):
        """Close HTTP client session"""
        await self.session.aclose()

    async def fetch_feed(self, feed_url: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
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
                    logger.warning(f"Feed parsing issues for {feed_url}: {feed_data.bozo_exception}")

                return True, feed_data, None

            except httpx.HTTPError as e:
                logger.warning(f"HTTP error fetching {feed_url}: {e}")
                if attempt == self.max_retries - 1:
                    return False, None, f"HTTP error: {str(e)}"
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

            except Exception as e:
                logger.error(f"Unexpected error fetching {feed_url}: {e}")
                return False, None, f"Unexpected error: {str(e)}"

        return False, None, "Max retries exceeded"

    def normalize_article(self, entry, feed_info: Dict) -> Dict:
        """Normalize an RSS entry into our article format"""

        # Extract published date
        published_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            published_date = datetime(*entry.published_parsed[:6])
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            published_date = datetime(*entry.updated_parsed[:6])

        # Extract and clean content
        content = ""
        if hasattr(entry, 'content') and entry.content:
            content = entry.content[0].value if isinstance(entry.content, list) else entry.content
        elif hasattr(entry, 'summary'):
            content = entry.summary

        # Clean HTML from content
        normalized_content = self.clean_html(content) if content else ""

        # Extract categories
        categories = []
        if hasattr(entry, 'tags'):
            categories = [tag.term for tag in entry.tags]

        return {
            'guid': getattr(entry, 'id', entry.link),
            'url': getattr(entry, 'link', ''),
            'title': getattr(entry, 'title', ''),
            'description': getattr(entry, 'summary', ''),
            'content': content,
            'normalized_content': normalized_content,
            'published_date': published_date,
            'author': getattr(entry, 'author', ''),
            'categories': categories,
            'word_count': len(normalized_content.split()) if normalized_content else 0,
            'language': 'en'  # Default to English for now
        }

    def clean_html(self, html_content: str) -> str:
        """Remove HTML tags and return clean text"""
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text and clean up whitespace
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        clean_text = ' '.join(chunk for chunk in chunks if chunk)

        return clean_text

    async def fetch_and_store_feed(self, feed_id: int) -> Tuple[bool, int, Optional[str]]:
        """
        Fetch a specific feed and store articles in database with enhanced retry logic
        Returns: (success, articles_count, error_message)
        """
        with get_db() as db:
            feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()
            if not feed:
                return False, 0, f"Feed with ID {feed_id} not found"

            if not feed.is_active:
                return False, 0, f"Feed {feed.name} is inactive"

            # Enhanced retry logic with exponential backoff
            success, feed_data, error = await self._fetch_with_retry(feed.url, feed.name)

            # Update feed status
            feed.last_fetched = datetime.utcnow()

            if not success:
                feed.last_error = error
                feed.error_count += 1

                # Auto-deactivate feeds with too many consecutive errors
                if feed.error_count >= 10:
                    feed.is_active = False
                    logger.warning(f"Auto-deactivated feed {feed.name} after {feed.error_count} consecutive errors")

                db.commit()
                return False, 0, error

            # Reset error count on success
            if feed.error_count > 0:
                logger.info(f"Feed {feed.name} recovered after {feed.error_count} errors")
            feed.error_count = 0
            feed.last_error = None

            # Process articles
            articles_count = 0
            articles_with_errors = 0

            for entry in feed_data.entries:
                try:
                    article_data = self.normalize_article(entry, feed_data.feed)

                    # Skip articles with insufficient data
                    if not article_data.get('title') or not article_data.get('guid'):
                        continue

                    # Check if article already exists (improved deduplication check)
                    existing = db.query(Article).filter(
                        Article.feed_id == feed.id,
                        Article.guid == article_data['guid']
                    ).first()

                    if not existing:
                        article = Article(
                            feed_id=feed.id,
                            **article_data
                        )
                        db.add(article)
                        articles_count += 1

                except Exception as e:
                    articles_with_errors += 1
                    logger.error(f"Error processing article from {feed.name}: {e}")
                    if articles_with_errors > 5:  # Stop processing if too many article errors
                        logger.error(f"Too many article processing errors for {feed.name}, stopping")
                        break
                    continue

            db.commit()

            if articles_with_errors > 0:
                logger.warning(f"Processed {articles_count} articles from {feed.name} with {articles_with_errors} errors")
            else:
                logger.info(f"Successfully processed {articles_count} new articles from {feed.name}")

            return True, articles_count, None

    async def _fetch_with_retry(self, url: str, feed_name: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
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
                    logger.warning(f"Feed parsing issues for {feed_name}: {feed_data.bozo_exception}")
                    # Still continue if we got some data
                    if not feed_data.entries:
                        return False, None, f"Feed parsing failed: {feed_data.bozo_exception}"

                # Check if feed has any entries
                if not feed_data.entries:
                    return False, None, "Feed contains no entries"

                logger.debug(f"Successfully fetched {len(feed_data.entries)} entries from {feed_name}")
                return True, feed_data, None

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Attempt {attempt + 1} failed for {feed_name}: {e}")

                # Exponential backoff with jitter
                if attempt < self.max_retries - 1:
                    import random
                    backoff_time = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(backoff_time)

        return False, None, f"Failed after {self.max_retries} attempts: {last_error}"

def create_test_feed(db: Session, name: str = "NASA Breaking News", url: str = "https://www.nasa.gov/rss/dyn/breaking_news.rss") -> RSSFeed:
    """Create a test RSS feed for development"""
    existing = db.query(RSSFeed).filter(RSSFeed.url == url).first()
    if existing:
        return existing

    feed = RSSFeed(
        name=name,
        url=url,
        category="news",
        is_active=True
    )
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed