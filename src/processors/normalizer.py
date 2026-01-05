import logging
import re
from datetime import datetime, timedelta

from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from src.database.models import Article

logger = logging.getLogger(__name__)

class ArticleNormalizer:
    """Handles article content normalization and cleanup"""

    def __init__(self):
        # Compile regex patterns for efficiency
        self.whitespace_pattern = re.compile(r'\s+')

    def normalize_content(self, html_content: str) -> str:
        """
        Convert HTML content to clean, normalized text
        """
        if not html_content:
            return ""

        try:
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                element.decompose()

            # Extract text
            text = soup.get_text()

            # Clean up whitespace
            text = self.whitespace_pattern.sub(' ', text)
            text = text.strip()

            return text

        except Exception as e:
            logger.error(f"Error normalizing content: {e}")
            return html_content

    def is_complete(self, article: Article) -> bool:
        """
        Check if article has basic required fields
        """
        return bool(
            article.title and
            article.title.strip() and
            article.normalized_content and
            len(article.normalized_content.strip()) > 0 and
            article.published_date
        )

    def process_article(self, article: Article) -> Article:
        """
        Process and normalize a single article
        """
        try:
            # Normalize content if not already done
            if article.content and not article.normalized_content:
                article.normalized_content = self.normalize_content(article.content)
                article.word_count = len(article.normalized_content.split())

            # Set language (basic detection for now)
            if not article.language:
                article.language = 'en'  # Default to English

            logger.debug(f"Normalized article {article.id}: {article.word_count} words")

        except Exception as e:
            logger.error(f"Error processing article {article.id}: {e}")

        return article

class ArticleStorage:
    """Handles article storage operations"""

    def __init__(self, db: Session):
        self.db = db
        self.normalizer = ArticleNormalizer()

    def store_articles(self, articles: list[Article]) -> int:
        """
        Store multiple articles in the database
        Returns: number of articles successfully stored
        """
        stored_count = 0

        for article in articles:
            try:
                # Normalize the article
                article = self.normalizer.process_article(article)

                # Add to database
                self.db.add(article)
                stored_count += 1

            except Exception as e:
                logger.error(f"Error storing article {article.guid}: {e}")
                continue

        try:
            self.db.commit()
            logger.info(f"Successfully stored {stored_count} articles")
        except Exception as e:
            logger.error(f"Error committing articles to database: {e}")
            self.db.rollback()
            stored_count = 0

        return stored_count

    def get_recent_articles(self, hours: int = 48) -> list[Article]:
        """
        Get articles from the last N hours
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return self.db.query(Article).filter(
            Article.fetched_at >= cutoff_time
        ).order_by(Article.published_date.desc()).all()

    def get_articles_by_feed(self, feed_id: int, limit: int = 100) -> list[Article]:
        """
        Get recent articles from a specific feed
        """
        return self.db.query(Article).filter(
            Article.feed_id == feed_id
        ).order_by(Article.published_date.desc()).limit(limit).all()

    def get_complete_articles(self, limit: int = 100) -> list[Article]:
        """
        Get articles that have all required fields
        """
        articles = self.db.query(Article).order_by(Article.published_date.desc()).limit(limit).all()
        return [article for article in articles if self.normalizer.is_complete(article)]
