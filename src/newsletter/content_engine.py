"""
Content Engine for InsightWeaver Newsletter
Generates intelligent narrative summaries using Claude API
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import Article, TrendAnalysis, NarrativeSynthesis
from ..utils.profile_loader import get_user_profile
from ..context.curator import ContextCurator
from ..context.claude_client import ClaudeClient


class NewsletterContentEngine:
    """Generates intelligent content for newsletters using context-driven approach"""

    def __init__(self):
        # Load user profile for personalization
        try:
            self.user_profile = get_user_profile()
            self.curator = ContextCurator(self.user_profile)
            self.claude_client = ClaudeClient()
        except FileNotFoundError:
            self.user_profile = None
            self.curator = ContextCurator()
            self.claude_client = None
        except ValueError as e:
            # API key not configured
            self.curator = ContextCurator()
            self.claude_client = None

    async def generate_intelligence_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        hours: Optional[int] = None,
        max_articles: int = 50
    ) -> Dict[str, Any]:
        """
        Generate intelligence report for any time period

        Args:
            start_date: Start of analysis window (or use hours)
            end_date: End of analysis window (defaults to now)
            hours: Look back N hours from end_date (alternative to start_date)
            max_articles: Max articles to analyze

        Returns:
            Report data with synthesis
        """
        # Determine time window
        end_date = end_date or datetime.now()
        if start_date is None:
            hours = hours or 24
            start_date = end_date - timedelta(hours=hours)

        duration_hours = (end_date - start_date).total_seconds() / 3600

        print(f"📊 Generating intelligence report: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')} ({duration_hours:.1f}h)")

        start_time = datetime.now()

        # Try to get existing synthesis for this window
        with get_db() as session:
            synthesis = session.query(NarrativeSynthesis).filter(
                NarrativeSynthesis.generated_at >= start_date,
                NarrativeSynthesis.generated_at <= end_date
            ).order_by(NarrativeSynthesis.generated_at.desc()).first()

            if synthesis and synthesis.synthesis_data:
                print(f"✨ Using existing synthesis from {synthesis.generated_at}")
                return self._format_synthesis_report(
                    synthesis, start_date, end_date, duration_hours
                )

            # No synthesis - generate new one
            print("🔄 No synthesis found in window, generating new synthesis...")
            articles = session.query(Article).filter(
                Article.published_date >= start_date,
                Article.published_date <= end_date,
                Article.filtered == False
            ).order_by(Article.published_date.desc()).limit(max_articles).all()

            if not articles:
                print("⚠️ No articles found in specified time window")
                return self._generate_empty_report(start_date, end_date, duration_hours)

            print(f"📰 Found {len(articles)} articles in window")

        # Generate new synthesis via NarrativeSynthesizer
        from ..context.synthesizer import NarrativeSynthesizer
        synthesizer = NarrativeSynthesizer()

        # Calculate hours for synthesizer
        synthesis_hours = int(duration_hours) + 1
        synthesis_result = await synthesizer.synthesize(
            hours=synthesis_hours,
            max_articles=max_articles
        )

        # Get fresh synthesis from DB
        with get_db() as session:
            synthesis = session.query(NarrativeSynthesis).get(
                synthesis_result['synthesis_id']
            )

            return self._format_synthesis_report(
                synthesis, start_date, end_date, duration_hours
            )

    def _format_synthesis_report(
        self,
        synthesis,
        start_date: datetime,
        end_date: datetime,
        duration_hours: float
    ) -> Dict[str, Any]:
        """Format synthesis into report data structure"""

        # Validate synthesis data
        if synthesis.synthesis_data is None:
            raise ValueError(f"Synthesis {synthesis.id} has NULL synthesis_data field")

        synthesis_data = synthesis.synthesis_data

        # Validate required fields for new schema
        required_fields = ['bottom_line', 'trends_and_patterns', 'priority_events', 'predictions_scenarios']
        missing_fields = []
        for field in required_fields:
            if field not in synthesis_data:
                missing_fields.append(field)

        if missing_fields:
            raise ValueError(f"Synthesis data missing required fields: {missing_fields}")

        return {
            "start_date": start_date,
            "end_date": end_date,
            "duration_hours": duration_hours,
            "report_type": self._determine_report_type(duration_hours),
            "synthesis_data": synthesis_data,
            "executive_summary": synthesis.executive_summary,
            "articles_analyzed": synthesis.articles_analyzed,
            "user_context": {
                "location": self.user_profile.get_primary_location(),
                "professional_domains": self.user_profile.get_professional_domains()
            } if self.user_profile else {},
            "synthesis_id": synthesis.id,
            "processing_time": f"{(datetime.now() - synthesis.generated_at).total_seconds():.1f}s"
        }

    def _determine_report_type(self, duration_hours: float) -> str:
        """Determine report type based on duration"""
        if duration_hours < 2:
            return "update"
        elif 18 <= duration_hours <= 30:
            return "daily"
        elif 144 <= duration_hours <= 192:  # 6-8 days
            return "weekly"
        else:
            return "custom"

    def _generate_empty_report(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_hours: float
    ) -> Dict[str, Any]:
        """Generate empty report structure when no articles found"""
        return {
            "start_date": start_date,
            "end_date": end_date,
            "duration_hours": duration_hours,
            "report_type": self._determine_report_type(duration_hours),
            "synthesis_data": {},
            "executive_summary": "No articles found in the specified time window.",
            "articles_analyzed": 0,
            "user_context": {
                "location": self.user_profile.get_primary_location(),
                "professional_domains": self.user_profile.get_professional_domains()
            } if self.user_profile else {},
            "processing_time": "0s"
        }

