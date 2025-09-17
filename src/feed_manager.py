"""
Feed Management System for InsightWeaver
Handles loading, updating, and managing RSS feeds from configuration
"""

import logging
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from src.database.connection import get_db
from src.database.models import RSSFeed
from src.config.feeds import get_all_feeds, get_feed_count

logger = logging.getLogger(__name__)

class FeedManager:
    """Manages RSS feed configuration and database operations"""

    def __init__(self):
        self.configured_feeds = get_all_feeds()

    def load_feeds_to_database(self) -> Tuple[int, int, int]:
        """
        Load all configured feeds into the database
        Returns: (added_count, updated_count, total_count)
        """
        added_count = 0
        updated_count = 0

        with get_db() as db:
            for feed_config in self.configured_feeds:
                existing_feed = db.query(RSSFeed).filter(
                    RSSFeed.url == feed_config['url']
                ).first()

                if existing_feed:
                    # Update existing feed metadata
                    existing_feed.name = feed_config['name']
                    existing_feed.category = feed_config['category']
                    existing_feed.is_active = True
                    updated_count += 1
                    logger.debug(f"Updated feed: {feed_config['name']}")
                else:
                    # Create new feed
                    new_feed = RSSFeed(
                        name=feed_config['name'],
                        url=feed_config['url'],
                        category=feed_config['category'],
                        is_active=True
                    )
                    db.add(new_feed)
                    added_count += 1
                    logger.debug(f"Added feed: {feed_config['name']}")

            total_count = db.query(RSSFeed).filter(RSSFeed.is_active == True).count()

        logger.info(f"Feed loading complete: {added_count} added, {updated_count} updated, {total_count} total active")
        return added_count, updated_count, total_count

    def get_active_feeds(self) -> List[RSSFeed]:
        """Get all active feeds from database"""
        with get_db() as db:
            return db.query(RSSFeed).filter(RSSFeed.is_active == True).all()

    def deactivate_failed_feeds(self, error_threshold: int = 5) -> int:
        """
        Deactivate feeds that have exceeded error threshold
        Returns: number of feeds deactivated
        """
        deactivated_count = 0

        with get_db() as db:
            failed_feeds = db.query(RSSFeed).filter(
                RSSFeed.error_count >= error_threshold,
                RSSFeed.is_active == True
            ).all()

            for feed in failed_feeds:
                feed.is_active = False
                deactivated_count += 1
                logger.warning(f"Deactivated feed due to errors: {feed.name} ({feed.error_count} errors)")

        return deactivated_count

    def get_feed_statistics(self) -> Dict:
        """Get statistics about feeds in the database"""
        with get_db() as db:
            total_feeds = db.query(RSSFeed).count()
            active_feeds = db.query(RSSFeed).filter(RSSFeed.is_active == True).count()
            failed_feeds = db.query(RSSFeed).filter(RSSFeed.error_count > 0).count()

            # Get category breakdown
            categories = {}
            for feed in db.query(RSSFeed).filter(RSSFeed.is_active == True).all():
                category = feed.category or 'uncategorized'
                categories[category] = categories.get(category, 0) + 1

            return {
                'total_feeds': total_feeds,
                'active_feeds': active_feeds,
                'inactive_feeds': total_feeds - active_feeds,
                'feeds_with_errors': failed_feeds,
                'configured_feeds': len(self.configured_feeds),
                'categories': categories
            }

    def reset_error_counts(self) -> int:
        """Reset error counts for all feeds (useful for troubleshooting)"""
        reset_count = 0

        with get_db() as db:
            feeds_with_errors = db.query(RSSFeed).filter(RSSFeed.error_count > 0).all()

            for feed in feeds_with_errors:
                feed.error_count = 0
                feed.last_error = None
                reset_count += 1

        logger.info(f"Reset error counts for {reset_count} feeds")
        return reset_count

def setup_feeds():
    """Initialize feeds in database from configuration"""
    logger.info("Setting up RSS feeds from configuration...")

    feed_manager = FeedManager()
    added, updated, total = feed_manager.load_feeds_to_database()

    logger.info(f"Feed setup complete: {total} active feeds ready for processing")
    return feed_manager