"""
Efficient Trend Analysis Agent
Uses 3-stage approach: Local categorization → Haiku pro/against → 6-month aggregation
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from src.agents.base_agent import BaseAgent
from src.agents.claude_client import ClaudeClient
from src.analyzers.trend_analyzer import TrendAnalyzer, GlobalTrend
from src.database.models import Article
from src.database.connection import get_db
from src.utils.profile_loader import get_user_profile

logger = logging.getLogger(__name__)

class TrendAnalysisAgent(BaseAgent):
    """
    Efficient agent that tracks 15 global trends using 3-stage analysis:

    Stage 1: Local trend categorization with spaCy (FREE)
    Stage 2: Haiku pro/against classification (LOW COST)
    Stage 3: 6-month trend direction calculation (FREE)
    """

    def __init__(self):
        super().__init__("TrendAnalysisAgent", "1.0")
        self.haiku_client = ClaudeClient(model="claude-3-haiku-20240307")  # Fast, cheap for pro/against
        self.trend_analyzer = TrendAnalyzer()  # Local categorization

        # Load user profile for personalized trend selection
        try:
            self.user_profile = get_user_profile()
            self.logger.info(f"Loaded user profile for trend analysis: {self.user_profile}")
            # Adjust trend focus based on user profile
            self._customize_trends()
        except FileNotFoundError as e:
            self.logger.warning(f"User profile not found, using default trends: {e}")
            self.user_profile = None

    def _customize_trends(self):
        """Customize trend focus based on user profile civic interests and policy areas"""
        if not self.user_profile:
            return

        civic_interests = self.user_profile.get_civic_interests()
        policy_areas = civic_interests.get('policy_areas', [])

        # Map policy areas to relevant trends (boost priority)
        self.priority_trends = []

        policy_trend_mapping = {
            'technology policy': [GlobalTrend.DIGITAL_CENTRALIZATION_VS_DECENTRALIZATION,
                                 GlobalTrend.AUTOMATION_VS_HUMAN_LABOR,
                                 GlobalTrend.SECURITY_VS_PRIVACY],
            'privacy and surveillance': [GlobalTrend.SECURITY_VS_PRIVACY,
                                         GlobalTrend.DIGITAL_CENTRALIZATION_VS_DECENTRALIZATION],
            'education policy': [GlobalTrend.DEMOGRAPHIC_TRANSITION],
            'transportation infrastructure': [GlobalTrend.URBANIZATION_VS_DISTRIBUTED_LIVING,
                                             GlobalTrend.ENERGY_TRANSITION],
            'housing policy': [GlobalTrend.URBANIZATION_VS_DISTRIBUTED_LIVING],
            'economic policy': [GlobalTrend.ECONOMIC_GROWTH_VS_STAGNATION,
                               GlobalTrend.DEBT_EXPANSION_VS_FISCAL_RESTRAINT],
            'environmental policy': [GlobalTrend.ENERGY_TRANSITION,
                                    GlobalTrend.CLIMATE_ACTION_VS_ECONOMIC_PRIORITIES],
            'climate change': [GlobalTrend.ENERGY_TRANSITION,
                              GlobalTrend.CLIMATE_ACTION_VS_ECONOMIC_PRIORITIES],
            'foreign policy': [GlobalTrend.GEOPOLITICAL_FRAGMENTATION_VS_COOPERATION,
                              GlobalTrend.SCIENTIFIC_OPENNESS_VS_COMPETITION],
            'trade policy': [GlobalTrend.GEOPOLITICAL_FRAGMENTATION_VS_COOPERATION,
                           GlobalTrend.ECONOMIC_GROWTH_VS_STAGNATION]
        }

        # Collect priority trends based on user's policy interests
        for policy_area in policy_areas:
            policy_lower = policy_area.lower()
            for policy_key, trends in policy_trend_mapping.items():
                if policy_key in policy_lower:
                    self.priority_trends.extend(trends)

        # Remove duplicates
        self.priority_trends = list(set(self.priority_trends))

        if self.priority_trends:
            self.logger.info(f"Prioritizing {len(self.priority_trends)} trends based on user interests: "
                           f"{[t.value for t in self.priority_trends]}")

    def _create_pro_against_prompt(self, trend_name: str, trend_description: str) -> str:
        """Create prompt for Haiku to determine pro/against for specific trend"""

        # Add user context if analyzing priority trend
        context_note = ""
        if self.user_profile and hasattr(self, 'priority_trends'):
            # Check if this is a priority trend
            from src.analyzers.trend_analyzer import GlobalTrend
            trend_enum = None
            for t in GlobalTrend:
                if t.value == trend_name:
                    trend_enum = t
                    break

            if trend_enum and trend_enum in self.priority_trends:
                location = self.user_profile.get_primary_location()
                policy_areas = self.user_profile.get_civic_interests().get('policy_areas', [])
                context_note = f"\n\nNOTE: This trend is of HIGH INTEREST to user in {location.get('city', '')}, {location.get('state', '')} with policy interests in: {', '.join(policy_areas[:3])}"

        return f"""TREND STANCE CLASSIFICATION: Classify each article's relationship to this trend:

{trend_description}{context_note}

Return EXACTLY this JSON format (no extra text):

{{
  "article_analysis": [
    {{"article_id": "123", "stance": "SUPPORTING", "confidence": 0.8, "reasoning": "Brief reason"}},
    {{"article_id": "124", "stance": "OPPOSING", "confidence": 0.7, "reasoning": "Brief reason"}},
    {{"article_id": "125", "stance": "NEUTRAL", "confidence": 0.5, "reasoning": "Brief reason"}}
  ]
}}

RULES:
- stance: "SUPPORTING", "OPPOSING", or "NEUTRAL"
  - SUPPORTING = article shows trend gaining momentum/strength
  - OPPOSING = article shows trend losing momentum/being challenged
  - NEUTRAL = article mentions trend but shows no clear direction OR is unrelated to this specific trend
- confidence: 0.1 to 1.0 (how confident you are in the classification)
- reasoning: under 50 characters explaining why
- Return ONLY the JSON, nothing else
- If article is clearly unrelated to this trend, use NEUTRAL with low confidence"""

    def get_recent_articles(self, days: int = 30, limit: Optional[int] = None) -> List[Article]:
        """
        Get recent articles for trend analysis (override base method to use days instead of hours)
        Excludes filtered articles
        """
        from datetime import timedelta
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

        with get_db() as db:
            query = db.query(Article).filter(
                Article.fetched_at >= cutoff_time,
                Article.title.isnot(None),
                Article.normalized_content.isnot(None),
                Article.filtered == False  # Exclude filtered articles
            ).order_by(Article.fetched_at.desc())

            if limit:
                query = query.limit(limit)

            return query.all()

    async def run_analysis(self, days: int = 30, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Complete trend analysis workflow (override base method to use days)
        """
        run_id = None
        try:
            # Start analysis run
            run_id = self.start_analysis_run(
                run_type=self.agent_name.lower(),
                metadata={"days": days, "limit": limit}
            )

            # Get articles to analyze
            articles = self.get_recent_articles(days=days, limit=limit)
            self.logger.info(f"Found {len(articles)} articles for trend analysis")

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
            self.logger.error(f"Trend analysis failed: {e}")
            if run_id:
                self.complete_analysis_run(run_id, 0, str(e))
            raise

    async def analyze_articles(self, articles: List[Article]) -> Dict[str, Any]:
        """
        Efficient 3-stage trend analysis workflow:
        Stage 1: Local trend categorization with spaCy (FREE)
        Stage 2: Haiku pro/against classification (LOW COST)
        Stage 3: 6-month trend direction calculation (FREE)
        """
        if not articles:
            return {"trend_analysis": [], "summary": "No articles to analyze"}

        # Prepare articles data
        articles_data = []
        with get_db() as db:
            for article in articles:
                # Re-attach article to session
                article = db.merge(article)

                # Calculate article age
                fetched_at = article.fetched_at.replace(tzinfo=timezone.utc) if article.fetched_at.tzinfo is None else article.fetched_at
                article_age_days = (datetime.now(timezone.utc) - fetched_at).total_seconds() / (24 * 3600)

                articles_data.append({
                    "id": article.id,
                    "title": article.title or "No title",
                    "content": (article.normalized_content or article.description or "")[:800],  # Shorter for trend analysis
                    "published_date": article.published_date.isoformat() if article.published_date else "Unknown",
                    "source": article.feed.name if article.feed else "Unknown",
                    "age_days": round(article_age_days, 1),
                    "url": article.url
                })

        self.logger.info(f"Starting efficient 3-stage trend analysis of {len(articles_data)} articles")

        try:
            # Stage 1: Local trend categorization (FREE)
            self.logger.info("Stage 1: Local trend categorization")
            trend_groups = self.trend_analyzer.categorize_articles_by_trends(articles_data)

            # Filter to only trends with sufficient articles
            filtered_groups = {k: v for k, v in trend_groups.items() if len(v) >= 3}

            if not filtered_groups:
                self.logger.info("No trends with sufficient article coverage found")
                return {"trend_analysis": [], "summary": "No trends detected with sufficient coverage"}

            # Stage 2: Haiku pro/against classification (LOW COST)
            self.logger.info(f"Stage 2: Haiku pro/against analysis for {len(filtered_groups)} trends")
            trend_stances = await self._analyze_trend_stances(filtered_groups)

            # Stage 3: 6-month trend direction calculation (FREE)
            self.logger.info("Stage 3: 6-month trend direction calculation")
            self.logger.info(f"Trend stances received: {len(trend_stances)} trends")
            for trend_name, trend_articles in trend_stances.items():
                self.logger.info(f"  {trend_name}: {len(trend_articles)} articles with stance data")
            trend_directions = self._calculate_trend_directions(trend_stances)

            # Update database with trend analysis
            self.logger.info(f"About to update metadata for {len(articles)} articles")
            self.logger.info(f"Articles type: {type(articles)}, first article type: {type(articles[0]) if articles else 'no articles'}")
            updated_count = await self._update_trend_metadata(articles, trend_directions)

            # Generate summary
            summary = {
                "total_articles": len(articles),
                "trends_analyzed": len(filtered_groups),
                "trends_detected": len(trend_directions),  # Changed for consistency with main.py
                "trends_with_direction": len(trend_directions),
                "updated_articles": updated_count,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }

            self.logger.info(f"Efficient trend analysis complete: {len(articles)} articles, {len(trend_directions)} trends detected")

            return {
                "trend_analysis": trend_directions,
                "summary": summary
            }

        except Exception as e:
            self.logger.error(f"Trend analysis failed: {e}")
            raise

    async def _analyze_trend_stances(self, trend_groups: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """
        Stage 2: Use Haiku to determine pro/against stance for articles in each trend
        """
        trend_stances = {}

        for trend_name, articles in trend_groups.items():
            if not articles:
                continue

            trend_info = self.trend_analyzer.get_trend_info(trend_name)
            if not trend_info:
                continue

            self.logger.info(f"Analyzing {len(articles)} articles for trend: {trend_name}")

            # Create pro/against prompt for this specific trend
            prompt = self._create_pro_against_prompt(trend_name, trend_info["description"])

            try:
                # Use Haiku for fast, cheap pro/against classification
                # Process in smaller batches to avoid truncation (max 10 per batch)
                batch_size = min(10, len(articles))
                result = await self.haiku_client.analyze_trend_batch(
                    system_prompt=prompt,
                    articles_data=articles,
                    batch_size=batch_size
                )

                if result and len(result) > 0:
                    self.logger.info(f"Received trend analysis result for {trend_name}: {len(result)} items")

                    # Debug: Log what Claude actually returned
                    self.logger.info(f"Sample API result for {trend_name}: {result[:2]}")

                    # Add stance data to articles - result is already the article_analysis array
                    stance_lookup = {}
                    neutral_fallback_count = 0
                    for analysis in result:
                        stance = analysis.get("stance", "MISSING_STANCE")
                        # Normalize article_id to string for comparison (Claude may return "123" or 123)
                        article_id_str = str(analysis['article_id']).strip()
                        self.logger.info(f"API returned stance for article {article_id_str}: {stance}")

                        # Accept NEUTRAL as valid - articles can be neutral on a trend
                        if stance == "NEUTRAL":
                            neutral_fallback_count += 1
                            self.logger.info(f"Article {article_id_str} has NEUTRAL stance for {trend_name}")

                        if stance not in ["SUPPORTING", "OPPOSING", "NEUTRAL"]:
                            raise ValueError(f"Invalid stance '{stance}' for article {article_id_str} - must be SUPPORTING, OPPOSING, or NEUTRAL")

                        stance_lookup[article_id_str] = {
                            "stance": stance,
                            "confidence": analysis.get("confidence", 0.0),
                            "reasoning": analysis.get("reasoning", "")
                        }

                    # Combine article data with stance analysis
                    # IMPORTANT: Only include articles that were successfully analyzed
                    # DO NOT assign random stances to missing articles
                    articles_with_stance = []
                    missing_count = 0
                    for article in articles:
                        # Normalize article ID to string for lookup
                        article_id_str = str(article["id"]).strip()
                        if article_id_str in stance_lookup:
                            article_stance = stance_lookup[article_id_str]
                            articles_with_stance.append({
                                **article,
                                **article_stance
                            })
                        else:
                            missing_count += 1
                            self.logger.warning(f"Article {article['id']} missing from API response - EXCLUDING from trend analysis")

                    # Warn if significant data loss
                    if missing_count > 0:
                        exclusion_rate = (missing_count / len(articles)) * 100
                        self.logger.warning(f"Excluded {missing_count}/{len(articles)} articles ({exclusion_rate:.1f}%) from {trend_name} due to missing API responses")

                    # Report neutral fallback statistics
                    if neutral_fallback_count > 0:
                        neutral_rate = (neutral_fallback_count / len(articles)) * 100
                        self.logger.info(f"NEUTRAL stances: {neutral_fallback_count}/{len(articles)} ({neutral_rate:.1f}%) for {trend_name}")

                    trend_stances[trend_name] = articles_with_stance
                    self.logger.info(f"Added {len(articles_with_stance)} articles with stance for {trend_name}")

                    # Log stance distribution for debugging
                    stances = [a["stance"] for a in articles_with_stance]
                    stance_counts = {"SUPPORTING": stances.count("SUPPORTING"),
                                   "OPPOSING": stances.count("OPPOSING"),
                                   "NEUTRAL": stances.count("NEUTRAL")}
                    self.logger.info(f"Stance distribution for {trend_name}: {stance_counts}")
                else:
                    self.logger.warning(f"Empty or invalid result for {trend_name}: {result}")

                # Rate limiting
                import asyncio
                await asyncio.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Failed to analyze stance for trend {trend_name}: {e}")
                # During development, we want to see the full error
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                # Re-raise to fail fast
                raise ValueError(f"Failed to analyze trend {trend_name}: {e}")

        return trend_stances

    def _calculate_trend_directions(self, trend_stances: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
        """
        Stage 3: Calculate 6-month trend directions based on pro/against counts
        """
        trend_directions = []

        for trend_name, articles_with_stance in trend_stances.items():
            if not articles_with_stance:
                continue

            # Count stances (handle both with and without NEUTRAL for compatibility)
            supporting_count = sum(1 for a in articles_with_stance if a.get("stance") == "SUPPORTING")
            opposing_count = sum(1 for a in articles_with_stance if a.get("stance") == "OPPOSING")
            neutral_count = sum(1 for a in articles_with_stance if a.get("stance") == "NEUTRAL")

            total_articles = len(articles_with_stance)

            # Determine overall direction
            # If no neutral articles (binary choice), use simpler thresholds
            if neutral_count == 0:
                if supporting_count > opposing_count:
                    direction = "GAINING"
                    ratio = supporting_count / max(1, opposing_count)
                    strength = "strong" if ratio > 2 else "moderate" if ratio > 1.5 else "weak"
                elif opposing_count > supporting_count:
                    direction = "LOSING"
                    ratio = opposing_count / max(1, supporting_count)
                    strength = "strong" if ratio > 2 else "moderate" if ratio > 1.5 else "weak"
                else:
                    direction = "NEUTRAL"  # Equal split
                    strength = "weak"
            else:
                # Original logic for when NEUTRAL is present
                if supporting_count > opposing_count * 1.5:  # Clear support
                    direction = "GAINING"
                    strength = "strong" if supporting_count > total_articles * 0.6 else "moderate"
                elif opposing_count > supporting_count * 1.5:  # Clear opposition
                    direction = "LOSING"
                    strength = "strong" if opposing_count > total_articles * 0.6 else "moderate"
                else:
                    direction = "NEUTRAL"
                    strength = "weak"

            # Calculate confidence based on article count and stance clarity
            stance_clarity = abs(supporting_count - opposing_count) / max(1, total_articles)
            article_factor = min(1.0, total_articles / 10.0)  # More articles = higher confidence
            confidence = (stance_clarity * 0.7 + article_factor * 0.3)

            # Get sample evidence
            supporting_articles = [a for a in articles_with_stance if a.get("stance") == "SUPPORTING"]
            opposing_articles = [a for a in articles_with_stance if a.get("stance") == "OPPOSING"]

            evidence_pieces = []
            if supporting_articles:
                evidence_pieces.extend([f"Supporting: {a.get('reasoning', a.get('title', ''))}"
                                      for a in supporting_articles[:2]])
            if opposing_articles:
                evidence_pieces.extend([f"Opposing: {a.get('reasoning', a.get('title', ''))}"
                                      for a in opposing_articles[:2]])

            trend_directions.append({
                "trend": trend_name,
                "direction": direction,
                "confidence": round(confidence, 3),
                "strength": strength,
                "evidence": "; ".join(evidence_pieces[:3]),
                "article_count": total_articles,
                "supporting_count": supporting_count,
                "opposing_count": opposing_count,
                "neutral_count": neutral_count
            })

        return trend_directions

    async def _update_trend_metadata(self, articles: List[Article], trend_results: List[Dict[str, Any]]) -> int:
        """
        Update articles with efficient trend analysis metadata
        """
        updated_count = 0

        with get_db() as db:
            for article in articles:
                article = db.merge(article)

                # Add trend analysis metadata
                trend_metadata = {
                    "trend_analysis_timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_name": self.agent_name,
                    "agent_version": self.agent_version,
                    "workflow": "3-stage-efficient",
                    "trend_indicators": trend_results
                }

                # Preserve existing metadata, add trend section
                if article.priority_metadata:
                    article.priority_metadata["trend_analysis"] = trend_metadata
                else:
                    article.priority_metadata = {"trend_analysis": trend_metadata}

                updated_count += 1

            db.commit()

        return updated_count

    def get_trend_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get trend analysis summary for the specified time period
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)

        with get_db() as db:
            articles = db.query(Article).filter(
                Article.fetched_at >= cutoff_time,
                Article.priority_metadata.isnot(None)
            ).all()

            trend_summary = {}

            for article in articles:
                if article.priority_metadata and "trend_analysis" in article.priority_metadata:
                    trend_data = article.priority_metadata["trend_analysis"]
                    trend_indicators = trend_data.get("trend_indicators", [])

                    for trend_indicator in trend_indicators:
                        trend_name = trend_indicator.get("trend")
                        if trend_name not in trend_summary:
                            trend_summary[trend_name] = {
                                "direction_counts": {"GAINING": 0, "LOSING": 0, "NEUTRAL": 0},
                                "avg_confidence": 0.0,
                                "total_mentions": 0
                            }

                        direction = trend_indicator.get("direction", "NEUTRAL")
                        confidence = trend_indicator.get("confidence", 0.0)

                        trend_summary[trend_name]["direction_counts"][direction] += 1
                        trend_summary[trend_name]["avg_confidence"] += confidence
                        trend_summary[trend_name]["total_mentions"] += 1

            # Calculate averages
            for trend_name in trend_summary:
                total = trend_summary[trend_name]["total_mentions"]
                if total > 0:
                    trend_summary[trend_name]["avg_confidence"] /= total

            return {
                "analysis_period_days": days,
                "trends_detected": len(trend_summary),
                "trend_summary": trend_summary,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat()
            }