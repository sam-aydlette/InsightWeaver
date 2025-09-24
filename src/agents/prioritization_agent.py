"""
Prioritization Agent
Uses Claude API to prioritize articles based on timeliness, impact, and actionability
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.agents.claude_client import ClaudeClient
from src.analyzers.sentiment_analyzer import SentimentAnalyzer
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
        self.haiku_client = ClaudeClient(model="claude-3-haiku-20240307")  # Fast, cheap screening
        self.sonnet_client = ClaudeClient(model="claude-sonnet-4-20250514")  # Detailed analysis
        self.sentiment_analyzer = SentimentAnalyzer()  # Local sentiment analysis

    def _create_category_ranking_prompt(self) -> str:
        """Create the prompt for Haiku to rank articles within sentiment categories"""
        return """You are a news analyst ranking articles within a specific sentiment category for a Northern Virginia resident in government/technology.

You will receive 3 articles from the same sentiment category. Rank them 1-3 based on:
- IMPACT: Affects millions of people, major institutions, or billions of dollars
- RELEVANCE: Government policy, technology, or Northern Virginia region
- URGENCY: Recent and requires immediate awareness/action

Return JSON only:
{"results": [{"article_id": 123, "rank": 1, "priority_score": 0.85}]}

Rank 1 = highest priority, 3 = lowest priority within this category."""

    def _create_final_selection_prompt(self) -> str:
        """Create the prompt for Sonnet to select the single highest priority article"""
        return """You are an expert news analyst making the final selection of the single most important article for a Northern Virginia resident who works in government/technology sectors.

You will receive the top-ranked article from each sentiment category (crisis, opportunity, policy, technology, neutral). Your task is to select the ONE article that deserves the highest priority today.

Consider these criteria:
1. IMMEDIATE IMPACT: Will this affect the reader's work, decisions, or life in the next 24-48 hours?
2. STRATEGIC IMPORTANCE: Does this represent a significant shift that requires attention or action?
3. TIMELINESS: Is this breaking news or time-sensitive information?
4. RELEVANCE: How directly does this relate to government/technology work in Northern Virginia?

Return your analysis as JSON with this exact format:
{
  "selected_article": {
    "article_id": 123,
    "priority_score": 0.95,
    "reasoning": "Federal AI regulation bill passed - immediate impact on government contractors and tech companies in Northern Virginia",
    "key_factors": ["federal_policy", "immediate_action_required", "professional_impact"],
    "category": "policy"
  },
  "runner_ups": [
    {"article_id": 456, "category": "crisis", "brief_reason": "Cybersecurity breach affects federal systems"},
    {"article_id": 789, "category": "technology", "brief_reason": "New AWS government cloud contract"}
  ]
}

Select only ONE article as the top priority. Be decisive and provide clear reasoning."""

    async def analyze_articles(self, articles: List[Article]) -> Dict[str, Any]:
        """
        Sentiment-based three-stage analysis:
        1. Local sentiment analysis & grouping
        2. Haiku ranks top 3 per sentiment category
        3. Sonnet selects final winner from category champions
        """
        if not articles:
            return {"prioritized_articles": [], "summary": "No articles to analyze"}

        # Prepare articles data for analysis
        articles_data = []
        with get_db() as db:
            for article in articles:
                # Re-attach article to session to access properties
                article = db.merge(article)

                # Handle timezone-aware comparison
                fetched_at = article.fetched_at.replace(tzinfo=timezone.utc) if article.fetched_at.tzinfo is None else article.fetched_at
                article_age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600

                articles_data.append({
                    "id": article.id,
                    "title": article.title or "No title",
                    "content": (article.normalized_content or article.description or "")[:2000],
                    "published_date": article.published_date.isoformat() if article.published_date else "Unknown",
                    "source": article.feed.name if article.feed else "Unknown",
                    "age_hours": round(article_age_hours, 1),
                    "url": article.url
                })

        self.logger.info(f"Starting sentiment-based analysis of {len(articles_data)} articles")

        try:
            # STAGE 1: Local sentiment analysis and grouping (FREE)
            self.logger.info("Stage 1: Local sentiment analysis and grouping...")
            sentiment_groups = self.sentiment_analyzer.group_articles_by_sentiment(articles_data)

            # Get top 3 from each category that has articles
            top_per_category = self.sentiment_analyzer.get_top_articles_per_category(sentiment_groups, top_n=3)

            total_local_processed = sum(len(articles) for articles in sentiment_groups.values())
            total_for_haiku = sum(len(articles) for articles in top_per_category.values())

            self.logger.info(f"Stage 1 complete: {total_local_processed} articles grouped, {total_for_haiku} selected for Haiku")

            # STAGE 2: Haiku ranks articles within each sentiment category
            category_winners = {}
            haiku_calls = 0

            for category, category_articles in top_per_category.items():
                if not category_articles:
                    continue

                self.logger.info(f"Stage 2: Haiku ranking {len(category_articles)} articles in {category} category...")

                # Prepare articles for Haiku (include content for better ranking)
                haiku_data = [
                    {
                        "id": article["id"],
                        "title": article["title"],
                        "content": article["content"][:500],  # Truncated content for ranking
                        "age_hours": article["age_hours"],
                        "source": article["source"]
                    }
                    for article in category_articles
                ]

                category_ranking_prompt = self._create_category_ranking_prompt()
                ranking_results = await self.haiku_client.analyze_batch(
                    system_prompt=category_ranking_prompt,
                    articles_data=haiku_data,
                    batch_size=3  # Small batches - max 3 articles per category
                )

                haiku_calls += 1

                # Find the rank 1 (highest priority) article from this category
                top_article = None
                for result in ranking_results:
                    if result.get("rank") == 1:
                        # Find the full article data
                        article_id = result.get("article_id")
                        for article in category_articles:
                            if article["id"] == article_id:
                                top_article = {**article, **result}
                                break
                        break

                if top_article:
                    category_winners[category] = top_article
                    self.logger.info(f"Category winner for {category}: Article {top_article['id']}")

            self.logger.info(f"Stage 2 complete: {len(category_winners)} category winners, {haiku_calls} Haiku calls")

            # STAGE 3: Sonnet selects the final winner from category champions
            final_winner = None
            sonnet_calls = 0

            if category_winners:
                self.logger.info("Stage 3: Sonnet selecting final winner from category champions...")

                # Prepare category winners for final selection
                champion_articles = list(category_winners.values())

                final_selection_prompt = self._create_final_selection_prompt()
                final_results = await self.sonnet_client.analyze_batch(
                    system_prompt=final_selection_prompt,
                    articles_data=champion_articles,
                    batch_size=len(champion_articles)  # Send all champions together
                )

                sonnet_calls += 1

                # Extract the selected winner
                if final_results and len(final_results) > 0:
                    selected_result = final_results[0]  # Should contain the selection
                    if "selected_article" in selected_result:
                        final_winner = selected_result["selected_article"]
                        self.logger.info(f"Final winner selected: Article {final_winner.get('article_id')}")

            # Update database with results
            all_results = []

            # Add the final winner with highest priority
            if final_winner:
                all_results.append({
                    "article_id": final_winner.get("article_id"),
                    "priority_score": final_winner.get("priority_score", 0.95),
                    "reasoning": final_winner.get("reasoning", "Selected as top priority"),
                    "key_factors": final_winner.get("key_factors", []),
                    "analysis_stage": "final_winner"
                })

            # Add category runners-up with high scores
            for category, winner in category_winners.items():
                if not final_winner or winner["id"] != final_winner.get("article_id"):
                    all_results.append({
                        "article_id": winner["id"],
                        "priority_score": winner.get("priority_score", 0.8),
                        "reasoning": f"Top article in {category} category",
                        "analysis_stage": "category_winner"
                    })

            # Add local analysis results for remaining articles
            for category, articles in sentiment_groups.items():
                for article in articles:
                    # Skip if already included above
                    if not any(r["article_id"] == article["id"] for r in all_results):
                        all_results.append({
                            "article_id": article["id"],
                            "priority_score": article["local_priority_score"],
                            "reasoning": f"Local sentiment analysis: {category.value} category",
                            "analysis_stage": "local_sentiment"
                        })

            updated_count = await self._update_article_priorities(all_results)

            # Generate summary
            high_priority_count = len([r for r in all_results if r.get("priority_score", 0) >= 0.7])

            summary = {
                "total_articles": len(articles),
                "sentiment_groups": len(sentiment_groups),
                "category_winners": len(category_winners),
                "final_winner": 1 if final_winner else 0,
                "high_priority_articles": high_priority_count,
                "haiku_api_calls": haiku_calls,
                "sonnet_api_calls": sonnet_calls,
                "updated_articles": updated_count,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }

            self.logger.info(f"Sentiment-based analysis complete: {len(articles)} articles, "
                           f"{haiku_calls} Haiku calls, {sonnet_calls} Sonnet calls, "
                           f"{high_priority_count} high priority")

            return {
                "prioritized_articles": all_results,
                "summary": summary
            }

        except Exception as e:
            self.logger.error(f"Sentiment-based prioritization analysis failed: {e}")
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
                    "prioritization_timestamp": datetime.now(timezone.utc).isoformat(),
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