"""
Content Engine for InsightWeaver Newsletter
Generates intelligent narrative summaries using Claude API
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import Article, TrendAnalysis
from ..agents.claude_client import ClaudeClient
from ..analyzers.trend_analyzer import TrendAnalyzer


class NewsletterContentEngine:
    """Generates intelligent content for newsletters using Claude API"""

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        self.claude_client = claude_client or ClaudeClient()
        self.trend_analyzer = TrendAnalyzer()

    async def generate_daily_brief_content(self, date: datetime) -> Dict[str, Any]:
        """Generate content for daily intelligence brief"""
        print(f"📊 Generating daily brief content for {date.strftime('%Y-%m-%d')}")

        start_time = datetime.now()
        with get_db() as session:
            # Get articles from the specified date
            articles = self._get_articles_for_date(session, date)
            if not articles:
                print("⚠️ No articles found for specified date")
                return self._generate_empty_brief(date)

            print(f"📄 Processing {len(articles)} articles from {date.strftime('%Y-%m-%d')}")

            # Get priority articles
            priority_articles = self._get_priority_articles(session, articles)

            # Get trends for the date
            trends = self._get_trends_for_date(session, date)

            # Get regional focus articles
            regional_articles = self._get_regional_articles(articles)

            # Generate executive summary using Claude
            executive_summary = await self._generate_executive_summary(
                priority_articles, trends, regional_articles, "daily"
            )

        processing_time = datetime.now() - start_time

        return {
            "date": date,
            "executive_summary": executive_summary,
            "priority_articles": priority_articles,
            "trends": trends,
            "regional_articles": regional_articles,
            "article_count": len(articles),
            "processing_time": f"{processing_time.total_seconds():.1f}s"
        }

    async def generate_weekly_trend_content(self, end_date: datetime) -> Dict[str, Any]:
        """Generate content for weekly trend analysis"""
        start_date = end_date - timedelta(days=7)
        print(f"📈 Generating weekly trend analysis: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        start_time = datetime.now()
        with get_db() as session:
            # Get all articles from the week
            articles = self._get_articles_for_period(session, start_date, end_date)
            if not articles:
                print("⚠️ No articles found for specified period")
                return self._generate_empty_weekly(start_date, end_date)

            print(f"📄 Analyzing {len(articles)} articles from past week")

            # Analyze trends across the week
            trends = self._get_weekly_trends(session, start_date, end_date)

            # Generate executive summary
            executive_summary = await self._generate_executive_summary(
                [], trends, [], "weekly"
            )

            # Generate predictions
            predictions = await self._generate_predictions(trends)

        processing_time = datetime.now() - start_time

        return {
            "start_date": start_date,
            "end_date": end_date,
            "executive_summary": executive_summary,
            "trends": trends,
            "predictions": predictions,
            "total_articles": len(articles),
            "processing_time": f"{processing_time.total_seconds():.1f}s"
        }

    def _get_articles_for_date(self, session: Session, date: datetime) -> List[Article]:
        """Get articles for a specific date"""
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        return session.query(Article).filter(
            Article.fetched_at >= start_of_day,
            Article.fetched_at < end_of_day
        ).all()

    def _get_articles_for_period(self, session: Session, start_date: datetime, end_date: datetime) -> List[Article]:
        """Get articles for a date range"""
        return session.query(Article).filter(
            Article.fetched_at >= start_date,
            Article.fetched_at <= end_date
        ).all()

    def _get_priority_articles(self, session: Session, articles: List[Article]) -> List[Dict]:
        """Get priority articles with scores and metadata"""
        # Filter articles that have priority scores >= 0.6
        priority_articles = []

        for article in articles:
            if article.priority_score and article.priority_score >= 0.6:
                priority_metadata = article.priority_metadata or {}

                priority_articles.append({
                    "id": article.id,
                    "title": article.title,
                    "source": article.feed.name if article.feed else "Unknown",
                    "url": article.url,
                    "summary": article.description or "",
                    "ai_summary": priority_metadata.get("ai_summary", article.description or ""),
                    "category": priority_metadata.get("category", "General"),
                    "priority_score": article.priority_score,
                    "reasoning": priority_metadata.get("reasoning", "")
                })

        # Sort by priority score descending and limit to top 15
        priority_articles.sort(key=lambda x: x["priority_score"], reverse=True)
        return priority_articles[:15]

    def _get_trends_for_date(self, session: Session, date: datetime) -> List[Dict]:
        """Get trends for a specific date"""
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        trend_analyses = session.query(TrendAnalysis).filter(
            TrendAnalysis.created_at >= start_of_day,
            TrendAnalysis.created_at < end_of_day
        ).all()

        trends = []
        for analysis in trend_analyses:
            # Use data_points field for trend data
            data_points = analysis.data_points or {}
            related_articles = analysis.related_articles or []

            trends.append({
                "name": analysis.trend_name,
                "description": self.trend_analyzer.get_trend_info().get(analysis.trend_name, {}).get("description", ""),
                "direction": data_points.get("direction", "stable"),
                "confidence": (analysis.confidence or 0) * 100,
                "article_count": len(related_articles),
                "momentum": data_points.get("momentum", "stable")
            })

        return trends

    def _get_weekly_trends(self, session: Session, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get comprehensive weekly trends with momentum analysis"""
        trend_analyses = session.query(TrendAnalysis).filter(
            TrendAnalysis.created_at >= start_date,
            TrendAnalysis.created_at <= end_date
        ).all()

        # Aggregate trends across the week
        trend_aggregation = {}

        for analysis in trend_analyses:
            trend_name = analysis.trend_name
            data_points = analysis.data_points or {}
            related_articles = analysis.related_articles or []

            if trend_name not in trend_aggregation:
                trend_aggregation[trend_name] = {
                    "total_articles": 0,
                    "supporting_count": 0,
                    "opposing_count": 0,
                    "daily_data": [],
                    "confidence_sum": 0,
                    "count": 0
                }

            agg = trend_aggregation[trend_name]
            agg["total_articles"] += len(related_articles)
            agg["supporting_count"] += data_points.get("supporting_count", 0)
            agg["opposing_count"] += data_points.get("opposing_count", 0)
            agg["confidence_sum"] += (analysis.confidence or 0)
            agg["count"] += 1
            agg["daily_data"].append({
                "date": analysis.created_at,
                "direction": data_points.get("direction", "stable"),
                "confidence": analysis.confidence or 0
            })

        # Calculate weekly momentum
        weekly_trends = []
        for trend_name, data in trend_aggregation.items():
            if data["total_articles"] >= 3:  # Only trends with sufficient data
                momentum = self._calculate_weekly_momentum(data["daily_data"])
                avg_confidence = data["confidence_sum"] / data["count"] if data["count"] > 0 else 0

                weekly_trends.append({
                    "name": trend_name,
                    "description": self.trend_analyzer.get_trend_info().get(trend_name, {}).get("description", ""),
                    "momentum": momentum,
                    "article_count": data["total_articles"],
                    "supporting_count": data["supporting_count"],
                    "opposing_count": data["opposing_count"],
                    "confidence": avg_confidence * 100,
                    "evidence": {
                        "supporting": [f"Pattern analysis from {data['supporting_count']} supporting articles"],
                        "opposing": [f"Counter-trend indicators from {data['opposing_count']} opposing articles"]
                    }
                })

        return sorted(weekly_trends, key=lambda x: x["article_count"], reverse=True)

    def _calculate_weekly_momentum(self, daily_data: List[Dict]) -> str:
        """Calculate trend momentum over the week"""
        if len(daily_data) < 2:
            return "stable"

        # Sort by date
        daily_data = sorted(daily_data, key=lambda x: x["date"])

        # Calculate confidence trend
        confidences = [d["confidence"] for d in daily_data]

        if len(confidences) >= 3:
            early_avg = sum(confidences[:len(confidences)//2]) / (len(confidences)//2)
            late_avg = sum(confidences[len(confidences)//2:]) / len(confidences[len(confidences)//2:])

            change = late_avg - early_avg

            if change > 0.2:
                return "strong_up"
            elif change > 0.1:
                return "moderate_up"
            elif change < -0.2:
                return "strong_down"
            elif change < -0.1:
                return "moderate_down"

        return "stable"

    def _get_regional_articles(self, articles: List[Article]) -> List[Dict]:
        """Get articles with regional relevance"""
        regional_keywords = [
            "virginia", "dc", "washington", "pentagon", "federal", "government",
            "northern virginia", "fairfax", "arlington", "alexandria", "loudoun"
        ]

        regional_articles = []
        for article in articles[:50]:  # Check top 50 articles
            title_lower = (article.title or "").lower()
            summary_lower = (article.description or "").lower()

            regional_score = 0
            for keyword in regional_keywords:
                if keyword in title_lower:
                    regional_score += 2
                if keyword in summary_lower:
                    regional_score += 1

            if regional_score >= 2:
                regional_articles.append({
                    "id": article.id,
                    "title": article.title,
                    "source": article.feed.name if article.feed else "Unknown",
                    "url": article.url,
                    "summary": article.description or "",
                    "regional_score": regional_score
                })

        return sorted(regional_articles, key=lambda x: x["regional_score"], reverse=True)[:5]

    async def _generate_executive_summary(self, priority_articles: List[Dict],
                                        trends: List[Dict], regional_articles: List[Dict],
                                        brief_type: str) -> str:
        """Generate executive summary using Claude API"""

        # Prepare context for Claude
        context = {
            "priority_count": len(priority_articles),
            "trend_count": len(trends),
            "regional_count": len(regional_articles),
            "brief_type": brief_type
        }

        # Sample top items for context
        top_priorities = priority_articles[:3] if priority_articles else []
        top_trends = trends[:3] if trends else []

        prompt = self._create_executive_summary_prompt(top_priorities, top_trends, brief_type)

        try:
            response = await self.claude_client.analyze_for_summary(prompt)
            return response.get("summary", self._generate_fallback_summary(context))
        except Exception as e:
            print(f"⚠️ Executive summary generation failed: {e}")
            return self._generate_fallback_summary(context)

    def _create_executive_summary_prompt(self, priorities: List[Dict], trends: List[Dict], brief_type: str) -> str:
        """Create prompt for executive summary generation"""

        period_desc = "today's developments" if brief_type == "daily" else "this week's strategic trends"

        prompt = f"""Generate a concise executive summary paragraph for a Northern Virginia intelligence brief analyzing {period_desc}.

Context:
- {len(priorities)} priority articles identified
- {len(trends)} significant trends detected
- Focus on government, technology, and regional implications

"""

        if priorities:
            prompt += "Top Priority Items:\n"
            for i, item in enumerate(priorities, 1):
                prompt += f"{i}. {item.get('title', 'Unknown')} (Score: {item.get('priority_score', 0):.2f})\n"
            prompt += "\n"

        if trends:
            prompt += "Key Trends:\n"
            for i, trend in enumerate(trends, 1):
                direction = trend.get('direction', 'stable')
                prompt += f"{i}. {trend.get('name', 'Unknown')} ({direction}, {trend.get('article_count', 0)} articles)\n"
            prompt += "\n"

        prompt += """Requirements:
- Write exactly one coherent paragraph (3-5 sentences)
- Focus on actionable intelligence for government/tech professionals
- Synthesize information rather than listing items
- Maintain professional, analytical tone
- Include forward-looking implications
- Return ONLY the paragraph text, no JSON or formatting

Generate the executive summary paragraph:"""

        return prompt

    async def _generate_predictions(self, trends: List[Dict]) -> str:
        """Generate forward-looking predictions based on trends"""
        if not trends:
            return "Insufficient trend data for forward projection analysis."

        top_trends = trends[:5]  # Focus on top 5 trends

        prompt = f"""Based on the following trend analysis, generate forward-looking predictions for the next 2-4 weeks.

Trends Analyzed:
"""
        for trend in top_trends:
            prompt += f"- {trend['name']}: {trend['momentum']} momentum ({trend['article_count']} articles)\n"

        prompt += """
Requirements:
- Focus on actionable predictions for Northern Virginia professionals
- Consider government, technology, and regional economic implications
- Write 2-3 sentences maximum
- Maintain analytical, professional tone
- Avoid speculation, focus on trend extrapolation
- Return ONLY the prediction text

Generate predictions:"""

        try:
            response = await self.claude_client.analyze_for_summary(prompt)
            return response.get("summary", "Trend momentum suggests continued development across multiple sectors with particular attention to technology policy and regional infrastructure initiatives.")
        except Exception as e:
            print(f"⚠️ Prediction generation failed: {e}")
            return "Trend momentum suggests continued development across multiple sectors with particular attention to technology policy and regional infrastructure initiatives."

    def _generate_fallback_summary(self, context: Dict) -> str:
        """Generate fallback executive summary when API fails"""
        priority_count = context.get("priority_count", 0)
        trend_count = context.get("trend_count", 0)
        brief_type = context.get("brief_type", "daily")

        if brief_type == "daily":
            return f"Today's intelligence analysis identified {priority_count} high-priority developments across government, technology, and regional affairs, with {trend_count} significant trend indicators. Key areas of focus include federal policy implications, technology sector movements, and Northern Virginia regional impacts. The analysis reveals continued evolution in established patterns with emerging cross-sector dependencies requiring ongoing monitoring."
        else:
            return f"This week's strategic analysis tracked {trend_count} significant trends with varying momentum across political, technological, and economic domains. Pattern analysis indicates sustained development in established trend directions with emerging convergence points requiring strategic attention. Forward indicators suggest continued acceleration in key areas affecting the Northern Virginia corridor and broader federal policy landscape."

    def _generate_empty_brief(self, date: datetime) -> Dict[str, Any]:
        """Generate empty brief structure when no data available"""
        return {
            "date": date,
            "executive_summary": "No significant intelligence data available for analysis during this period. System monitoring continues for emerging developments.",
            "priority_articles": [],
            "trends": [],
            "regional_articles": [],
            "article_count": 0,
            "processing_time": "0.0s"
        }

    def _generate_empty_weekly(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate empty weekly report when no data available"""
        return {
            "start_date": start_date,
            "end_date": end_date,
            "executive_summary": "Insufficient data available for comprehensive trend analysis during this period. Monitoring systems remain active for emerging patterns.",
            "trends": [],
            "predictions": "Unable to generate forward projections without sufficient historical data.",
            "total_articles": 0,
            "processing_time": "0.0s"
        }