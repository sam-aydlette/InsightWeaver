"""
Data Retention System
Manages automatic cleanup of old data based on retention policies
Prevents database bloat while maintaining historical context
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import Article, NarrativeSynthesis
from ..config.settings import settings

logger = logging.getLogger(__name__)


class DataRetentionManager:
    """Manages data retention and cleanup operations"""

    def __init__(self):
        self.retention_articles = settings.retention_articles_days
        self.retention_syntheses = settings.retention_syntheses_days
        self.retention_feed_health = settings.retention_feed_health_days

    def cleanup_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run all cleanup operations

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Summary of cleanup operations
        """
        logger.info(f"Starting data retention cleanup (dry_run={dry_run})")

        results = {
            "dry_run": dry_run,
            "started_at": datetime.utcnow().isoformat(),
            "articles": {},
            "syntheses": {},
            "total_freed_mb": 0
        }

        with get_db() as session:
            # Cleanup old articles
            results["articles"] = self._cleanup_old_articles(session, dry_run)

            # Cleanup old syntheses
            results["syntheses"] = self._cleanup_old_syntheses(session, dry_run)

            # Estimate space freed (rough approximation)
            total_deleted = (
                results["articles"].get("deleted", 0) +
                results["syntheses"].get("deleted", 0)
            )
            # Rough estimate: 10 KB per article, 50 KB per synthesis
            estimated_kb = (
                results["articles"].get("deleted", 0) * 10 +
                results["syntheses"].get("deleted", 0) * 50
            )
            results["total_freed_mb"] = round(estimated_kb / 1024, 2)

        results["completed_at"] = datetime.utcnow().isoformat()

        # Log summary
        if dry_run:
            logger.info(
                f"DRY RUN: Would delete {results['articles'].get('deleted', 0)} articles, "
                f"{results['syntheses'].get('deleted', 0)} syntheses "
                f"(~{results['total_freed_mb']} MB)"
            )
        else:
            logger.info(
                f"Cleanup complete: Deleted {results['articles'].get('deleted', 0)} articles, "
                f"{results['syntheses'].get('deleted', 0)} syntheses "
                f"(~{results['total_freed_mb']} MB freed)"
            )

        return results

    def _cleanup_old_articles(self, session: Session, dry_run: bool) -> Dict[str, Any]:
        """
        Remove articles older than retention period

        Strategy:
        - Keep articles for retention_articles_days (default: 90 days)
        - Articles are already synthesized into narrative summaries
        - Original content not needed after synthesis

        Args:
            session: Database session
            dry_run: If True, only count what would be deleted

        Returns:
            Cleanup statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_articles)

        # Find old articles
        old_articles = session.query(Article).filter(
            Article.fetched_at < cutoff_date
        ).all()

        count = len(old_articles)

        if count == 0:
            logger.info("No articles to clean up")
            return {"deleted": 0, "oldest_kept": None}

        # Find oldest article we're keeping
        oldest_kept = session.query(Article).filter(
            Article.fetched_at >= cutoff_date
        ).order_by(Article.fetched_at.asc()).first()

        oldest_kept_date = oldest_kept.fetched_at if oldest_kept else None

        if dry_run:
            logger.info(
                f"Would delete {count} articles older than {cutoff_date.strftime('%Y-%m-%d')}"
            )
            return {
                "deleted": count,
                "cutoff_date": cutoff_date.isoformat(),
                "oldest_kept": oldest_kept_date.isoformat() if oldest_kept_date else None
            }

        # Actually delete
        try:
            session.query(Article).filter(
                Article.fetched_at < cutoff_date
            ).delete(synchronize_session=False)

            session.commit()

            logger.info(
                f"Deleted {count} articles older than {cutoff_date.strftime('%Y-%m-%d')}"
            )

            return {
                "deleted": count,
                "cutoff_date": cutoff_date.isoformat(),
                "oldest_kept": oldest_kept_date.isoformat() if oldest_kept_date else None
            }

        except Exception as e:
            logger.error(f"Failed to delete articles: {e}")
            session.rollback()
            return {"deleted": 0, "error": str(e)}

    def _cleanup_old_syntheses(self, session: Session, dry_run: bool) -> Dict[str, Any]:
        """
        Remove syntheses older than retention period

        Strategy:
        - Keep syntheses for retention_syntheses_days (default: 180 days)
        - Keeps 6 months of historical context for trend analysis
        - Semantic facts are extracted before deletion (handled separately)

        Args:
            session: Database session
            dry_run: If True, only count what would be deleted

        Returns:
            Cleanup statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_syntheses)

        # Find old syntheses
        old_syntheses = session.query(NarrativeSynthesis).filter(
            NarrativeSynthesis.generated_at < cutoff_date
        ).all()

        count = len(old_syntheses)

        if count == 0:
            logger.info("No syntheses to clean up")
            return {"deleted": 0, "oldest_kept": None}

        # Find oldest synthesis we're keeping
        oldest_kept = session.query(NarrativeSynthesis).filter(
            NarrativeSynthesis.generated_at >= cutoff_date
        ).order_by(NarrativeSynthesis.generated_at.asc()).first()

        oldest_kept_date = oldest_kept.generated_at if oldest_kept else None

        if dry_run:
            logger.info(
                f"Would delete {count} syntheses older than {cutoff_date.strftime('%Y-%m-%d')}"
            )
            return {
                "deleted": count,
                "cutoff_date": cutoff_date.isoformat(),
                "oldest_kept": oldest_kept_date.isoformat() if oldest_kept_date else None
            }

        # Actually delete
        try:
            session.query(NarrativeSynthesis).filter(
                NarrativeSynthesis.generated_at < cutoff_date
            ).delete(synchronize_session=False)

            session.commit()

            logger.info(
                f"Deleted {count} syntheses older than {cutoff_date.strftime('%Y-%m-%d')}"
            )

            return {
                "deleted": count,
                "cutoff_date": cutoff_date.isoformat(),
                "oldest_kept": oldest_kept_date.isoformat() if oldest_kept_date else None
            }

        except Exception as e:
            logger.error(f"Failed to delete syntheses: {e}")
            session.rollback()
            return {"deleted": 0, "error": str(e)}

    def get_retention_status(self) -> Dict[str, Any]:
        """
        Get current status of data retention

        Returns:
            Summary of data age and retention policies
        """
        with get_db() as session:
            # Count articles
            total_articles = session.query(Article).count()
            oldest_article = session.query(Article).order_by(
                Article.fetched_at.asc()
            ).first()
            newest_article = session.query(Article).order_by(
                Article.fetched_at.desc()
            ).first()

            # Extract article timestamps while session is active
            oldest_article_date = oldest_article.fetched_at.isoformat() if oldest_article else None
            newest_article_date = newest_article.fetched_at.isoformat() if newest_article else None

            # Count syntheses
            total_syntheses = session.query(NarrativeSynthesis).count()
            oldest_synthesis = session.query(NarrativeSynthesis).order_by(
                NarrativeSynthesis.generated_at.asc()
            ).first()
            newest_synthesis = session.query(NarrativeSynthesis).order_by(
                NarrativeSynthesis.generated_at.desc()
            ).first()

            # Extract synthesis timestamps while session is active
            oldest_synthesis_date = oldest_synthesis.generated_at.isoformat() if oldest_synthesis else None
            newest_synthesis_date = newest_synthesis.generated_at.isoformat() if newest_synthesis else None

            # Calculate what would be deleted
            article_cutoff = datetime.utcnow() - timedelta(days=self.retention_articles)
            synthesis_cutoff = datetime.utcnow() - timedelta(days=self.retention_syntheses)

            articles_to_delete = session.query(Article).filter(
                Article.fetched_at < article_cutoff
            ).count()

            syntheses_to_delete = session.query(NarrativeSynthesis).filter(
                NarrativeSynthesis.generated_at < synthesis_cutoff
            ).count()

        return {
            "retention_policies": {
                "articles_days": self.retention_articles,
                "syntheses_days": self.retention_syntheses,
            },
            "current_data": {
                "articles": {
                    "total": total_articles,
                    "oldest": oldest_article_date,
                    "newest": newest_article_date,
                    "pending_deletion": articles_to_delete
                },
                "syntheses": {
                    "total": total_syntheses,
                    "oldest": oldest_synthesis_date,
                    "newest": newest_synthesis_date,
                    "pending_deletion": syntheses_to_delete
                }
            }
        }


def cleanup_old_data(dry_run: bool = False) -> Dict[str, Any]:
    """
    Convenience function for cleanup operations

    Args:
        dry_run: If True, only report what would be deleted

    Returns:
        Summary of cleanup operations
    """
    manager = DataRetentionManager()
    return manager.cleanup_all(dry_run=dry_run)


def get_retention_status() -> Dict[str, Any]:
    """
    Convenience function to get retention status

    Returns:
        Summary of data age and retention policies
    """
    manager = DataRetentionManager()
    return manager.get_retention_status()
