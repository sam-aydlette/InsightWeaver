"""
Content Engine for InsightWeaver Newsletter
Generates intelligent narrative summaries using Claude API
"""

from datetime import datetime, timedelta
from typing import Any

from ..config.settings import settings
from ..context.claude_client import ClaudeClient
from ..context.curator import ContextCurator
from ..database.connection import get_db
from ..database.models import Article, NarrativeSynthesis
from ..utils.profile_loader import get_user_profile


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
        except ValueError:
            # API key not configured
            self.curator = ContextCurator()
            self.claude_client = None

    async def generate_intelligence_report(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        hours: int | None = None,
        max_articles: int = 50,
        topic_filters: dict | None = None,
        synthesis_id: int | None = None
    ) -> dict[str, Any]:
        """
        Generate intelligence report for any time period

        Args:
            start_date: Start of analysis window (or use hours)
            end_date: End of analysis window (defaults to now)
            hours: Look back N hours from end_date (alternative to start_date)
            max_articles: Max articles to analyze
            topic_filters: Optional topic/scope filters for article selection
            synthesis_id: Optional synthesis ID from pipeline (prevents duplicate generation)

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

        # If synthesis_id provided by pipeline, use it directly (prevents duplicate synthesis)
        if synthesis_id is not None:
            with get_db() as session:
                synthesis = session.query(NarrativeSynthesis).filter(
                    NarrativeSynthesis.id == synthesis_id
                ).first()

                if synthesis and synthesis.synthesis_data:
                    print(f"✅ Using synthesis from pipeline (ID: {synthesis_id})")
                    return self._format_synthesis_report(
                        synthesis, start_date, end_date, duration_hours
                    )
                else:
                    print(f"⚠️  Warning: Synthesis ID {synthesis_id} not found in database, querying for existing synthesis...")

        # Try to get existing synthesis for this window
        # Prefer syntheses with citation_map (trust-verified with citations)
        with get_db() as session:
            all_syntheses = session.query(NarrativeSynthesis).filter(
                NarrativeSynthesis.generated_at >= start_date,
                NarrativeSynthesis.generated_at <= end_date
            ).order_by(NarrativeSynthesis.generated_at.desc()).all()

            # Look for synthesis with citations first
            synthesis = None
            for s in all_syntheses:
                if s.synthesis_data and 'metadata' in s.synthesis_data:
                    if 'citation_map' in s.synthesis_data.get('metadata', {}):
                        synthesis = s
                        print(f"✨ Using existing trust-verified synthesis with citations from {s.generated_at}")
                        break

            # Fallback to most recent synthesis if no citation-enhanced one found
            if not synthesis and all_syntheses:
                synthesis = all_syntheses[0]
                print(f"⚠️  Using older synthesis without citations from {synthesis.generated_at}")
                print("    Generating new synthesis with citations...")
                synthesis = None  # Force regeneration

            if synthesis and synthesis.synthesis_data:
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
        synthesizer = NarrativeSynthesizer(topic_filters=topic_filters)

        # Calculate hours for synthesizer
        synthesis_hours = int(duration_hours) + 1

        # Use trust-verified synthesis with citations (default)
        # Falls back to reflection-enhanced synthesis if trust verification disabled
        use_trust_verification = getattr(settings, 'enable_trust_verification', True)

        if use_trust_verification:
            print("🔒 Generating trust-verified synthesis with citations...")
            synthesis_result = await synthesizer.synthesize_with_trust_verification(
                hours=synthesis_hours,
                max_articles=max_articles,
                max_retries=3
            )
        else:
            print("📝 Generating synthesis with reflection (trust verification disabled)...")
            synthesis_result = await synthesizer.synthesize_with_reflection(
                hours=synthesis_hours,
                max_articles=max_articles,
                depth_threshold=settings.reflection_depth_threshold
            )

        # Handle case where no synthesis was created (no articles)
        if synthesis_result['synthesis_id'] is None:
            return self._generate_empty_report(start_date, end_date, duration_hours)

        # Get fresh synthesis from DB
        with get_db() as session:
            synthesis = session.query(NarrativeSynthesis).get(
                synthesis_result['synthesis_id']
            )

            if synthesis is None:
                return self._generate_empty_report(start_date, end_date, duration_hours)

            return self._format_synthesis_report(
                synthesis, start_date, end_date, duration_hours
            )

    def _format_synthesis_report(
        self,
        synthesis,
        start_date: datetime,
        end_date: datetime,
        duration_hours: float
    ) -> dict[str, Any]:
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

        # Extract trust verification metadata if present
        trust_verification = synthesis_data.get('trust_verification', {})

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
            "processing_time": f"{(datetime.now() - synthesis.generated_at).total_seconds():.1f}s",
            "trust_verification": trust_verification  # Include trust verification metadata
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
    ) -> dict[str, Any]:
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

