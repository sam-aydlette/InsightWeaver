"""
Base Agent Class
Foundation for all InsightWeaver AI agents
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.database.models import AnalysisRun, Article
from src.database.connection import get_db

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all InsightWeaver AI agents"""

    def __init__(self, agent_name: str, agent_version: str = "1.0"):
        self.agent_name = agent_name
        self.agent_version = agent_version
        self.logger = logging.getLogger(f"{__name__}.{agent_name}")

    def start_analysis_run(self, run_type: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Start a new analysis run and return the run ID
        """
        with get_db() as db:
            analysis_run = AnalysisRun(
                run_type=run_type,
                status="started",
                started_at=datetime.utcnow(),
                analysis_metadata={
                    "agent_name": self.agent_name,
                    "agent_version": self.agent_version,
                    **(metadata or {})
                }
            )
            db.add(analysis_run)
            db.commit()

            self.logger.info(f"Started {run_type} analysis run with ID {analysis_run.id}")
            return analysis_run.id

    def complete_analysis_run(self, run_id: int, articles_processed: int, error_message: Optional[str] = None):
        """
        Mark an analysis run as completed
        """
        with get_db() as db:
            analysis_run = db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()
            if analysis_run:
                analysis_run.status = "failed" if error_message else "completed"
                analysis_run.completed_at = datetime.utcnow()
                analysis_run.articles_processed = articles_processed
                if error_message:
                    analysis_run.error_message = error_message
                db.commit()

                status = "completed" if not error_message else f"failed: {error_message}"
                self.logger.info(f"Analysis run {run_id} {status} ({articles_processed} articles processed)")

    def get_recent_articles(self, hours: int = 48, limit: Optional[int] = None) -> List[Article]:
        """
        Get recent articles for analysis
        """
        from datetime import timedelta
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        with get_db() as db:
            query = db.query(Article).filter(
                Article.fetched_at >= cutoff_time,
                Article.title.isnot(None),
                Article.normalized_content.isnot(None)
            ).order_by(Article.fetched_at.desc())

            if limit:
                query = query.limit(limit)

            return query.all()

    @abstractmethod
    async def analyze_articles(self, articles: List[Article]) -> Dict[str, Any]:
        """
        Main analysis method to be implemented by each agent
        """
        pass

    async def run_analysis(self, hours: int = 48, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Complete analysis workflow
        """
        run_id = None
        try:
            # Start analysis run
            run_id = self.start_analysis_run(
                run_type=self.agent_name.lower(),
                metadata={"hours": hours, "limit": limit}
            )

            # Get articles to analyze
            articles = self.get_recent_articles(hours=hours, limit=limit)
            self.logger.info(f"Found {len(articles)} articles for analysis")

            if not articles:
                self.complete_analysis_run(run_id, 0)
                return {"articles_processed": 0, "results": []}

            # Run the analysis
            results = await self.analyze_articles(articles)

            # Complete the run
            self.complete_analysis_run(run_id, len(articles))

            return {
                "analysis_run_id": run_id,
                "articles_processed": len(articles),
                **results
            }

        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            if run_id:
                self.complete_analysis_run(run_id, 0, str(e))
            raise