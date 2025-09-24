"""
Article Deduplication System
Identifies and handles duplicate articles across different RSS feeds
"""

import logging
import hashlib
from typing import List, Set, Dict, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from src.database.models import Article
from src.database.connection import get_db

logger = logging.getLogger(__name__)

class ArticleDeduplicator:
    """Handles detection and management of duplicate articles"""

    def __init__(self,
                 similarity_threshold: float = 0.85,
                 time_window_hours: int = 72):
        self.similarity_threshold = similarity_threshold
        self.time_window_hours = time_window_hours

    def generate_content_hash(self, title: str, content: str) -> str:
        """Generate a hash for article content for exact duplicate detection"""
        if not title or not content:
            return ""

        # Normalize content for comparison
        normalized_title = self._normalize_text(title)
        normalized_content = self._normalize_text(content)

        # Create combined hash
        combined_text = f"{normalized_title}|{normalized_content}"
        return hashlib.md5(combined_text.encode('utf-8')).hexdigest()

    def generate_title_hash(self, title: str) -> str:
        """Generate a hash for article title for near-duplicate detection"""
        if not title:
            return ""

        normalized_title = self._normalize_text(title)
        return hashlib.md5(normalized_title.encode('utf-8')).hexdigest()

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (remove punctuation, lowercase, etc.)"""
        if not text:
            return ""

        # Convert to lowercase and remove extra whitespace
        text = text.lower().strip()

        # Remove common punctuation and special characters
        import re
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)

        return text

    def find_exact_duplicates(self, article: Article, db: Session) -> List[Article]:
        """Find exact duplicates based on content hash"""
        if not article.title or not article.normalized_content:
            return []

        content_hash = self.generate_content_hash(article.title, article.normalized_content)
        if not content_hash:
            return []

        # Store hash in article for comparison
        if not hasattr(article, '_content_hash'):
            article._content_hash = content_hash

        # Look for articles with same content hash within time window
        time_cutoff = datetime.utcnow() - timedelta(hours=self.time_window_hours)

        # Much more efficient: limit the query and only get necessary fields
        candidates = db.query(Article.id, Article.title, Article.normalized_content, Article.fetched_at).filter(
            and_(
                Article.id != article.id,
                Article.fetched_at >= time_cutoff,
                Article.title.isnot(None),
                Article.normalized_content.isnot(None)
            )
        ).limit(1000).all()  # Reasonable limit to prevent runaway queries

        # Check content hash for each candidate
        exact_duplicates = []
        for candidate_data in candidates:
            candidate_hash = self.generate_content_hash(candidate_data.title, candidate_data.normalized_content)
            if candidate_hash == content_hash:
                # Get full article object only for matches
                full_candidate = db.query(Article).filter(Article.id == candidate_data.id).first()
                if full_candidate:
                    exact_duplicates.append(full_candidate)

        return exact_duplicates

    def find_near_duplicates(self, article: Article, db: Session) -> List[Article]:
        """Find near-duplicates based on title similarity and URL"""
        if not article.title:
            return []

        near_duplicates = []
        time_cutoff = datetime.utcnow() - timedelta(hours=self.time_window_hours)

        # Find articles with same URL (different feeds might have same URL)
        if article.url:
            url_duplicates = db.query(Article).filter(
                and_(
                    Article.id != article.id,
                    Article.url == article.url,
                    Article.fetched_at >= time_cutoff
                )
            ).all()
            near_duplicates.extend(url_duplicates)

        # Find articles with very similar titles - much more efficient approach
        title_hash = self.generate_title_hash(article.title)
        if title_hash:
            # Only get necessary fields for comparison
            candidates = db.query(Article.id, Article.title).filter(
                and_(
                    Article.id != article.id,
                    Article.fetched_at >= time_cutoff,
                    Article.title.isnot(None)
                )
            ).limit(500).all()  # Reasonable limit

            matched_ids = []
            for candidate_data in candidates:
                if candidate_data.title:
                    candidate_hash = self.generate_title_hash(candidate_data.title)
                    if candidate_hash == title_hash:
                        matched_ids.append(candidate_data.id)

            # Get full articles only for matches, avoiding duplicates from URL check
            if matched_ids:
                existing_ids = {dup.id for dup in near_duplicates}
                new_matches = db.query(Article).filter(
                    and_(
                        Article.id.in_(matched_ids),
                        ~Article.id.in_(existing_ids)
                    )
                ).all()
                near_duplicates.extend(new_matches)

        return near_duplicates

    def mark_as_duplicate(self, original_article: Article, duplicate_article: Article, db: Session):
        """Mark an article as a duplicate of another"""
        # Add metadata to track duplication
        if not duplicate_article.priority_metadata:
            duplicate_article.priority_metadata = {}

        duplicate_article.priority_metadata.update({
            'is_duplicate': True,
            'duplicate_of': original_article.id,
            'duplicate_detected_at': datetime.utcnow().isoformat(),
            'duplicate_type': 'exact' if self._is_exact_duplicate(original_article, duplicate_article) else 'near'
        })

        # Lower priority score for duplicates
        duplicate_article.priority_score = 0.1

        logger.debug(f"Marked article {duplicate_article.id} as duplicate of {original_article.id}")

    def _is_exact_duplicate(self, article1: Article, article2: Article) -> bool:
        """Check if two articles are exact duplicates"""
        if not all([article1.title, article1.normalized_content, article2.title, article2.normalized_content]):
            return False

        hash1 = self.generate_content_hash(article1.title, article1.normalized_content)
        hash2 = self.generate_content_hash(article2.title, article2.normalized_content)

        return hash1 == hash2 and hash1 != ""

    def _stage1_url_duplicates(self, db: Session, unprocessed_ids: List[int], time_cutoff: datetime) -> Dict[str, int]:
        """
        Stage 1: Quick URL duplicate detection - instant wins
        Groups articles by URL and marks later ones as duplicates
        """
        # Get all articles with URLs in a single query
        articles_with_urls = db.query(Article).filter(
            and_(
                Article.id.in_(unprocessed_ids),
                Article.url.isnot(None),
                Article.url != ""
            )
        ).order_by(Article.fetched_at.asc()).all()

        # Group by URL and mark duplicates
        url_groups = {}
        for article in articles_with_urls:
            if article.url not in url_groups:
                url_groups[article.url] = []
            url_groups[article.url].append(article)

        url_duplicates = 0
        for url, articles in url_groups.items():
            if len(articles) > 1:
                # Keep the earliest, mark others as duplicates
                original = articles[0]
                for duplicate in articles[1:]:
                    # Skip if already marked as duplicate
                    if duplicate.priority_metadata and duplicate.priority_metadata.get('is_duplicate'):
                        continue
                    self.mark_as_duplicate(original, duplicate, db)
                    unprocessed_ids.remove(duplicate.id)  # Remove from further processing
                    url_duplicates += 1

        return {'url_duplicates': url_duplicates}

    def _stage2_exact_duplicates(self, db: Session, unprocessed_ids: List[int], time_cutoff: datetime) -> Dict[str, int]:
        """
        Stage 2: Exact content hash matches - fast hash-based detection
        Only processes articles that survived Stage 1
        """
        # Get articles that need content hash comparison
        remaining_articles = db.query(Article).filter(
            and_(
                Article.id.in_(unprocessed_ids),
                Article.title.isnot(None),
                Article.normalized_content.isnot(None)
            )
        ).order_by(Article.fetched_at.asc()).all()

        # Group by content hash
        hash_groups = {}
        for article in remaining_articles:
            # Skip if already marked as duplicate
            if article.priority_metadata and article.priority_metadata.get('is_duplicate'):
                continue

            content_hash = self.generate_content_hash(article.title, article.normalized_content)
            if content_hash:
                if content_hash not in hash_groups:
                    hash_groups[content_hash] = []
                hash_groups[content_hash].append(article)

        exact_duplicates = 0
        for content_hash, articles in hash_groups.items():
            if len(articles) > 1:
                # Keep the earliest, mark others as duplicates
                original = articles[0]
                for duplicate in articles[1:]:
                    self.mark_as_duplicate(original, duplicate, db)
                    if duplicate.id in unprocessed_ids:
                        unprocessed_ids.remove(duplicate.id)  # Remove from further processing
                    exact_duplicates += 1

        return {'exact_duplicates': exact_duplicates}

    def _stage3_title_similarity(self, db: Session, unprocessed_ids: List[int], time_cutoff: datetime) -> Dict[str, int]:
        """
        Stage 3: Title similarity analysis - slowest but most thorough
        Only processes articles that survived Stages 1 & 2
        """
        # Get remaining articles that need title similarity comparison
        remaining_articles = db.query(Article).filter(
            and_(
                Article.id.in_(unprocessed_ids),
                Article.title.isnot(None)
            )
        ).order_by(Article.fetched_at.asc()).all()

        # Group by title hash for similarity detection
        title_hash_groups = {}
        for article in remaining_articles:
            # Skip if already marked as duplicate
            if article.priority_metadata and article.priority_metadata.get('is_duplicate'):
                continue

            title_hash = self.generate_title_hash(article.title)
            if title_hash:
                if title_hash not in title_hash_groups:
                    title_hash_groups[title_hash] = []
                title_hash_groups[title_hash].append(article)

        title_duplicates = 0
        for title_hash, articles in title_hash_groups.items():
            if len(articles) > 1:
                # Keep the earliest or most reliable source
                original = articles[0]
                for duplicate in articles[1:]:
                    self.mark_as_duplicate(original, duplicate, db)
                    title_duplicates += 1

        return {'title_duplicates': title_duplicates}

    def deduplicate_recent_articles(self, hours: int = 24) -> Dict[str, int]:
        """
        Staged deduplication processing for optimal performance:
        Stage 1: Quick URL duplicate detection
        Stage 2: Exact content hash matches
        Stage 3: Title similarity analysis
        """
        time_cutoff = datetime.utcnow() - timedelta(hours=hours)

        with get_db() as db:
            # Get recent articles that haven't been processed for duplicates
            recent_articles_data = db.query(
                Article.id, Article.priority_metadata
            ).filter(
                Article.fetched_at >= time_cutoff
            ).order_by(Article.fetched_at.desc()).all()

            # Filter out already processed duplicates in Python
            unprocessed_ids = []
            for article_data in recent_articles_data:
                if not article_data.priority_metadata or not article_data.priority_metadata.get('is_duplicate'):
                    unprocessed_ids.append(article_data.id)

            logger.info(f"Starting staged deduplication of {len(unprocessed_ids)} articles")

            # STAGE 1: Quick URL duplicate detection (instant wins)
            stage1_stats = self._stage1_url_duplicates(db, unprocessed_ids, time_cutoff)
            logger.info(f"Stage 1 complete: {stage1_stats['url_duplicates']} URL duplicates found")

            # STAGE 2: Exact content hash matches (fast)
            stage2_stats = self._stage2_exact_duplicates(db, unprocessed_ids, time_cutoff)
            logger.info(f"Stage 2 complete: {stage2_stats['exact_duplicates']} exact duplicates found")

            # STAGE 3: Title similarity analysis (slower, but fewer candidates)
            stage3_stats = self._stage3_title_similarity(db, unprocessed_ids, time_cutoff)
            logger.info(f"Stage 3 complete: {stage3_stats['title_duplicates']} title duplicates found")

            # Final commit
            db.commit()

            total_duplicates = (stage1_stats['url_duplicates'] +
                              stage2_stats['exact_duplicates'] +
                              stage3_stats['title_duplicates'])

            logger.info(f"Staged deduplication complete: {len(unprocessed_ids)} articles processed, "
                       f"{total_duplicates} total duplicates found")

            return {
                'processed_articles': len(unprocessed_ids),
                'url_duplicates': stage1_stats['url_duplicates'],
                'exact_duplicates': stage2_stats['exact_duplicates'],
                'title_duplicates': stage3_stats['title_duplicates'],
                'total_duplicates': total_duplicates
            }

    def get_duplicate_statistics(self) -> Dict[str, int]:
        """Get statistics about duplicates in the database"""
        with get_db() as db:
            total_articles = db.query(Article).count()

            # Count duplicates and originals in Python since SQLite JSON queries are limited
            all_articles = db.query(Article).all()
            duplicate_articles = 0
            original_articles = 0

            for article in all_articles:
                if article.priority_metadata:
                    if article.priority_metadata.get('is_duplicate'):
                        duplicate_articles += 1
                    if article.priority_metadata.get('duplicate_of'):
                        original_articles += 1

            return {
                'total_articles': total_articles,
                'duplicate_articles': duplicate_articles,
                'original_articles': original_articles,
                'unique_articles': total_articles - duplicate_articles,
                'duplication_rate': duplicate_articles / total_articles if total_articles > 0 else 0.0
            }

def run_deduplication(hours: int = 24) -> Dict[str, int]:
    """Convenience function to run deduplication on recent articles"""
    deduplicator = ArticleDeduplicator()
    return deduplicator.deduplicate_recent_articles(hours=hours)