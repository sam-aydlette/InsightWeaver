"""
Prioritization Agent
Uses Claude API to prioritize articles based on timeliness, impact, and actionability
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.agents.claude_client import ClaudeClient
from src.database.models import Article
from src.database.connection import get_db

logger = logging.getLogger(__name__)

class PrioritizationAgent(BaseAgent):
    """
    Agent that prioritizes articles using Claude API based on:
    1. Timeliness (within 48 hours)
    2. High impact (affects millions of people, thousands of institutions, billions of dollars, global events)
    3. Actionability (requires decision, worldview change, or strategic shift)
    """

    def __init__(self):
        super().__init__("PrioritizationAgent", "1.0")
        self.claude_client = ClaudeClient()

    def _create_system_prompt(self) -> str:
        """Create the system prompt for Claude"""
        return """You are an expert news analyst specializing in prioritizing articles for a Northern Virginia resident who works in government/technology sectors.

Your task is to analyze articles and assign priority scores from 0.0 to 1.0 based on these three criteria:

1. TIMELINESS (25% weight): Articles should be from the last 48 hours. Older articles get lower scores.

2. HIGH IMPACT (50% weight): Prioritize articles describing events that:
   - Affect millions of people (or more)
   - Impact thousands of major institutions (or more)
   - Involve hundreds of millions of dollars (or more)
   - Have significant influence on global events
   - Affect government policy, technology sector, or Northern Virginia region

3. ACTIONABILITY (25% weight): Prioritize articles that describe events requiring:
   - A decision by the reader
   - A worldview change
   - A strategic shift in thinking or planning
   - Professional or personal action

SCORING GUIDELINES:
- 0.9-1.0: Extremely high priority (breaking major news, immediate action required)
- 0.7-0.8: High priority (significant impact, likely action needed)
- 0.5-0.6: Medium priority (notable but not urgent)
- 0.3-0.4: Low priority (background knowledge)
- 0.0-0.2: Very low priority (routine news)

Return your analysis as JSON with this exact format:
{
  "results": [
    {
      "article_id": 123,
      "priority_score": 0.85,
      "timeliness_score": 0.9,
      "impact_score": 0.8,
      "actionability_score": 0.9,
      "reasoning": "Breaking: Federal spending bill affects millions, requires immediate awareness for government contractors",
      "key_factors": ["federal_policy", "financial_impact", "professional_relevance"]
    }
  ]
}

Be precise with scores and provide clear reasoning focused on the three criteria."""

    async def analyze_articles(self, articles: List[Article]) -> Dict[str, Any]:
        """
        Analyze articles using Claude API for prioritization
        """
        if not articles:
            return {"prioritized_articles": [], "summary": "No articles to analyze"}

        # Prepare articles data for Claude
        articles_data = []
        for article in articles:
            article_age_hours = (datetime.utcnow() - article.fetched_at).total_seconds() / 3600

            articles_data.append({
                "id": article.id,
                "title": article.title or "No title",
                "content": (article.normalized_content or article.description or "")[:2000],  # Limit content length
                "published_date": article.published_date.isoformat() if article.published_date else "Unknown",
                "source": article.feed.name if article.feed else "Unknown",
                "age_hours": round(article_age_hours, 1),
                "url": article.url
            })

        self.logger.info(f"Sending {len(articles_data)} articles to Claude for prioritization")

        try:
            # Get prioritization from Claude
            system_prompt = self._create_system_prompt()
            results = await self.claude_client.analyze_batch(
                system_prompt=system_prompt,
                articles_data=articles_data,
                batch_size=8  # Conservative batch size
            )

            # Update database with results
            updated_count = await self._update_article_priorities(results)

            # Generate summary
            high_priority_count = len([r for r in results if r.get("priority_score", 0) >= 0.7])

            summary = {
                "total_articles": len(articles),
                "high_priority_articles": high_priority_count,
                "updated_articles": updated_count,
                "analysis_timestamp": datetime.utcnow().isoformat()
            }

            self.logger.info(f"Prioritization complete: {high_priority_count}/{len(articles)} high priority articles")

            return {
                "prioritized_articles": results,
                "summary": summary
            }

        except Exception as e:
            self.logger.error(f"Prioritization analysis failed: {e}")
            raise

    async def _update_article_priorities(self, results: List[Dict[str, Any]]) -> int:
        """
        Update article priority scores and metadata in database
        """
        updated_count = 0

        with get_db() as db:
            for result in results:
                article_id = result.get("article_id")
                if not article_id:
                    continue

                article = db.query(Article).filter(Article.id == article_id).first()
                if not article:
                    continue

                # Update priority score
                article.priority_score = result.get("priority_score", 0.5)

                # Update priority metadata
                priority_metadata = {
                    "prioritization_timestamp": datetime.utcnow().isoformat(),
                    "agent_name": self.agent_name,
                    "agent_version": self.agent_version,
                    "timeliness_score": result.get("timeliness_score"),
                    "impact_score": result.get("impact_score"),
                    "actionability_score": result.get("actionability_score"),
                    "reasoning": result.get("reasoning"),
                    "key_factors": result.get("key_factors", [])
                }

                # Preserve existing metadata, update priority section
                if article.priority_metadata:
                    article.priority_metadata.update(priority_metadata)
                else:
                    article.priority_metadata = priority_metadata

                updated_count += 1

            db.commit()

        return updated_count

    def get_high_priority_articles(self,
                                 min_score: float = 0.7,
                                 hours: int = 48,
                                 limit: int = 50) -> List[Article]:
        """
        Get high priority articles from the database
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        with get_db() as db:
            articles = db.query(Article).filter(
                Article.priority_score >= min_score,
                Article.fetched_at >= cutoff_time
            ).order_by(Article.priority_score.desc()).limit(limit).all()

        return articles

    def get_prioritization_summary(self, hours: int = 48) -> Dict[str, Any]:
        """
        Get summary statistics of prioritized articles
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        with get_db() as db:
            all_articles = db.query(Article).filter(
                Article.fetched_at >= cutoff_time,
                Article.priority_score.isnot(None)
            ).all()

            if not all_articles:
                return {"total_articles": 0, "message": "No prioritized articles found"}

            scores = [a.priority_score for a in all_articles]
            high_priority = [a for a in all_articles if a.priority_score >= 0.7]
            medium_priority = [a for a in all_articles if 0.4 <= a.priority_score < 0.7]
            low_priority = [a for a in all_articles if a.priority_score < 0.4]

            return {
                "total_articles": len(all_articles),
                "high_priority_count": len(high_priority),
                "medium_priority_count": len(medium_priority),
                "low_priority_count": len(low_priority),
                "average_score": sum(scores) / len(scores),
                "highest_score": max(scores),
                "lowest_score": min(scores),
                "analysis_timeframe_hours": hours
            }