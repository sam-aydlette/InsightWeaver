"""
Health Monitoring System
Tracks system health metrics and operational statistics
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func

from ..config.settings import settings
from ..database.connection import get_db
from ..database.models import Article, MemoryFact, NarrativeSynthesis, RSSFeed

logger = logging.getLogger(__name__)


class HealthMonitor:
    """Monitor system health and performance metrics"""

    def get_system_health(self) -> dict[str, Any]:
        """
        Get comprehensive system health status

        Returns:
            Dictionary with health metrics and status
        """
        health = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "issues": [],
            "metrics": {},
        }

        try:
            with get_db() as session:
                # Database health
                db_health = self._check_database_health(session)
                health["metrics"]["database"] = db_health

                # Feed collection health
                feed_health = self._check_feed_health(session)
                health["metrics"]["feeds"] = feed_health

                # Synthesis health
                synthesis_health = self._check_synthesis_health(session)
                health["metrics"]["synthesis"] = synthesis_health

                # Memory system health
                memory_health = self._check_memory_health(session)
                health["metrics"]["memory"] = memory_health

                # Data retention status
                retention_health = self._check_retention_status(session)
                health["metrics"]["retention"] = retention_health

                # Disk space
                disk_health = self._check_disk_space()
                health["metrics"]["disk"] = disk_health

                # Determine overall status
                health["overall_status"] = self._determine_overall_status(health)

        except Exception as e:
            logger.error(f"Error getting system health: {e}", exc_info=True)
            health["overall_status"] = "error"
            health["issues"].append(f"Health check failed: {str(e)}")

        return health

    def _check_database_health(self, session) -> dict[str, Any]:
        """Check database health and size"""
        db_path = Path(settings.database_url.replace("sqlite:///", ""))

        return {
            "status": "healthy",
            "size_mb": round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0,
            "total_articles": session.query(Article).count(),
            "total_syntheses": session.query(NarrativeSynthesis).count(),
            "total_facts": session.query(MemoryFact).count(),
        }

    def _check_feed_health(self, session) -> dict[str, Any]:
        """Check RSS feed collection health"""
        total_feeds = session.query(RSSFeed).count()
        active_feeds = session.query(RSSFeed).filter(RSSFeed.is_active.is_(True)).count()

        # Feeds with recent errors
        error_threshold = datetime.utcnow() - timedelta(days=7)
        feeds_with_errors = (
            session.query(RSSFeed)
            .filter(RSSFeed.error_count > 0, RSSFeed.last_fetched >= error_threshold)
            .count()
        )

        # Feeds not fetched recently (last 48 hours)
        stale_threshold = datetime.utcnow() - timedelta(hours=48)
        stale_feeds = (
            session.query(RSSFeed)
            .filter(RSSFeed.is_active.is_(True), RSSFeed.last_fetched < stale_threshold)
            .count()
        )

        status = "healthy"
        issues = []

        if feeds_with_errors > active_feeds * 0.2:  # More than 20% with errors
            status = "degraded"
            issues.append(f"{feeds_with_errors} feeds have recent errors")

        if stale_feeds > 0:
            status = "degraded"
            issues.append(f"{stale_feeds} active feeds not fetched in 48h")

        return {
            "status": status,
            "total_feeds": total_feeds,
            "active_feeds": active_feeds,
            "feeds_with_errors": feeds_with_errors,
            "stale_feeds": stale_feeds,
            "issues": issues,
        }

    def _check_synthesis_health(self, session) -> dict[str, Any]:
        """Check synthesis generation health"""
        # Recent syntheses (last 7 days)
        recent_threshold = datetime.utcnow() - timedelta(days=7)
        recent_syntheses = (
            session.query(NarrativeSynthesis)
            .filter(NarrativeSynthesis.generated_at >= recent_threshold)
            .count()
        )

        # Latest synthesis
        latest_synthesis = (
            session.query(NarrativeSynthesis)
            .order_by(NarrativeSynthesis.generated_at.desc())
            .first()
        )

        latest_date = latest_synthesis.generated_at if latest_synthesis else None
        hours_since_last = (
            (datetime.utcnow() - latest_date).total_seconds() / 3600 if latest_date else None
        )

        status = "healthy"
        issues = []

        if hours_since_last and hours_since_last > 48:
            status = "degraded"
            issues.append(f"No synthesis in {hours_since_last:.1f} hours")

        return {
            "status": status,
            "recent_syntheses_7d": recent_syntheses,
            "latest_synthesis": latest_date.isoformat() if latest_date else None,
            "hours_since_last": round(hours_since_last, 1) if hours_since_last else None,
            "issues": issues,
        }

    def _check_memory_health(self, session) -> dict[str, Any]:
        """Check semantic memory health"""
        total_facts = session.query(MemoryFact).count()

        # Active facts (not expired)
        active_facts = (
            session.query(MemoryFact)
            .filter((MemoryFact.expires_at.is_(None)) | (MemoryFact.expires_at > datetime.utcnow()))
            .count()
        )

        # Expired facts
        expired_facts = total_facts - active_facts

        # Facts by type
        fact_types = (
            session.query(MemoryFact.fact_type, func.count(MemoryFact.id))
            .group_by(MemoryFact.fact_type)
            .all()
        )

        return {
            "status": "healthy",
            "total_facts": total_facts,
            "active_facts": active_facts,
            "expired_facts": expired_facts,
            "facts_by_type": dict(fact_types),
        }

    def _check_retention_status(self, session) -> dict[str, Any]:
        """Check data retention policy status"""
        article_cutoff = datetime.utcnow() - timedelta(days=settings.retention_articles_days)
        synthesis_cutoff = datetime.utcnow() - timedelta(days=settings.retention_syntheses_days)

        articles_pending_deletion = (
            session.query(Article).filter(Article.fetched_at < article_cutoff).count()
        )

        syntheses_pending_deletion = (
            session.query(NarrativeSynthesis)
            .filter(NarrativeSynthesis.generated_at < synthesis_cutoff)
            .count()
        )

        status = "healthy"
        issues = []

        if articles_pending_deletion > 1000:
            status = "degraded"
            issues.append(f"{articles_pending_deletion} articles pending cleanup")

        return {
            "status": status,
            "articles_pending_deletion": articles_pending_deletion,
            "syntheses_pending_deletion": syntheses_pending_deletion,
            "retention_days_articles": settings.retention_articles_days,
            "retention_days_syntheses": settings.retention_syntheses_days,
            "issues": issues,
        }

    def _check_disk_space(self) -> dict[str, Any]:
        """Check disk space usage"""
        data_dir = settings.data_dir

        # Calculate total size of data directory
        total_size = sum(f.stat().st_size for f in data_dir.rglob("*") if f.is_file())

        size_mb = round(total_size / (1024 * 1024), 2)

        status = "healthy"
        issues = []

        if size_mb > 1000:  # Over 1 GB
            status = "warning"
            issues.append(f"Data directory size: {size_mb} MB")

        return {"status": status, "data_dir_size_mb": size_mb, "issues": issues}

    def _determine_overall_status(self, health: dict[str, Any]) -> str:
        """Determine overall system status from individual metrics"""
        statuses = [metric.get("status", "healthy") for metric in health["metrics"].values()]

        # Collect all issues
        for metric_name, metric_data in health["metrics"].items():
            if "issues" in metric_data and metric_data["issues"]:
                for issue in metric_data["issues"]:
                    health["issues"].append(f"{metric_name}: {issue}")

        # Determine worst status
        if "error" in statuses:
            return "error"
        elif "degraded" in statuses:
            return "degraded"
        elif "warning" in statuses:
            return "warning"
        else:
            return "healthy"

    def get_performance_metrics(self, days: int = 7) -> dict[str, Any]:
        """
        Get performance metrics for recent operations

        Args:
            days: Number of days to look back

        Returns:
            Performance statistics
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        metrics = {
            "period_days": days,
            "start_date": cutoff_date.isoformat(),
            "end_date": datetime.utcnow().isoformat(),
        }

        try:
            with get_db() as session:
                # Article collection rate
                articles_collected = (
                    session.query(Article).filter(Article.fetched_at >= cutoff_date).count()
                )

                metrics["articles_collected"] = articles_collected
                metrics["articles_per_day"] = round(articles_collected / days, 1)

                # Synthesis generation
                syntheses_generated = (
                    session.query(NarrativeSynthesis)
                    .filter(NarrativeSynthesis.generated_at >= cutoff_date)
                    .count()
                )

                metrics["syntheses_generated"] = syntheses_generated

                # Memory facts created
                facts_created = (
                    session.query(MemoryFact).filter(MemoryFact.created_at >= cutoff_date).count()
                )

                metrics["facts_created"] = facts_created

        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}", exc_info=True)
            metrics["error"] = str(e)

        return metrics


def get_system_health() -> dict[str, Any]:
    """Convenience function to get system health"""
    monitor = HealthMonitor()
    return monitor.get_system_health()


def get_performance_metrics(days: int = 7) -> dict[str, Any]:
    """Convenience function to get performance metrics"""
    monitor = HealthMonitor()
    return monitor.get_performance_metrics(days=days)
