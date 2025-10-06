"""
Context Curator
Builds optimal context for Claude API calls from database and user profile
Implements token budget management following Anthropic's context engineering guidance
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from ..database.connection import get_db
from ..database.models import Article, NarrativeSynthesis
from ..utils.profile_loader import get_user_profile, UserProfile
from .perspectives import get_perspective, Perspective

logger = logging.getLogger(__name__)


class ContextCurator:
    """Curates optimal context for Claude analysis with token budget management"""

    # Token budget allocation for Claude Sonnet 4 (200k context window)
    TOKEN_BUDGET = {
        'system_prompt': 5000,      # Perspective + framework + examples
        'articles': 50000,           # Article content (50 articles × ~1000 tokens)
        'historical': 10000,         # Compressed memory/patterns
        'response': 8000,            # Claude's output
        'safety_margin': 127000      # Reserved buffer
    }

    # Total available: 200,000 tokens
    # Allocated: 73,000 tokens (system + articles + historical + response)
    # Safety margin: 127,000 tokens

    def __init__(
        self,
        user_profile: Optional[UserProfile] = None,
        perspective_id: Optional[str] = None
    ):
        """
        Initialize context curator

        Args:
            user_profile: User profile for personalization
            perspective_id: Perspective to use for analysis framing (defaults to user preference or daily_intelligence_brief)
        """
        try:
            self.user_profile = user_profile or get_user_profile()
        except FileNotFoundError:
            logger.warning("User profile not found, context will not be personalized")
            self.user_profile = None

        # Determine perspective: user preference > parameter > default
        if perspective_id is None:
            # Try to get from user profile preferences
            if self.user_profile:
                profile_data = self.user_profile.profile
                perspective_id = profile_data.get('briefing_preferences', {}).get('perspective')

            # Fall back to default if not in profile
            if perspective_id is None:
                from .perspectives import get_default_perspective
                perspective_id = get_default_perspective()

        # Load perspective configuration
        self.perspective = get_perspective(perspective_id)
        logger.info(f"Using perspective: {self.perspective.name}")

    def curate_for_narrative_synthesis(
        self,
        hours: int = 48,
        max_articles: int = 50
    ) -> Dict[str, Any]:
        """
        Curate context for narrative synthesis with token budget enforcement

        Args:
            hours: Hours to look back for articles
            max_articles: Maximum articles to include

        Returns:
            Curated context dictionary with token metadata
        """
        with get_db() as session:
            # Get recent unfiltered articles
            articles = self._get_recent_articles(session, hours, max_articles)

            # Get historical context
            memory = self._get_historical_memory(session)

            # Build initial context
            context = {
                "user_profile": self._format_user_profile(),
                "articles": self._format_articles(articles),
                "memory": memory,
                "instructions": self._get_synthesis_instructions()
            }

            # Enforce token budget
            context = self._enforce_token_budget(context)

            return context

    def curate_for_summary(
        self,
        articles: List[Article],
        brief_type: str = "daily"
    ) -> Dict[str, Any]:
        """
        Curate context for executive summary generation

        Args:
            articles: Articles to summarize
            brief_type: Type of brief ("daily" or "weekly")

        Returns:
            Curated context dictionary
        """
        context = {
            "user_profile": self._format_user_profile(),
            "articles": self._format_articles(articles[:20]),  # Top 20
            "instructions": self._get_summary_instructions(brief_type)
        }

        return context

    def _get_recent_articles(
        self,
        session: Session,
        hours: int,
        max_articles: int
    ) -> List[Article]:
        """Get recent unfiltered articles from database"""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        articles = session.query(Article).filter(
            Article.fetched_at >= cutoff_time,
            Article.filtered == False
        ).order_by(
            Article.fetched_at.desc()
        ).limit(max_articles).all()

        logger.info(f"Curated {len(articles)} articles from last {hours} hours")
        return articles

    def _get_historical_memory(self, session: Session) -> str:
        """Get historical context from past syntheses"""
        # Get last 3 narrative syntheses
        syntheses = session.query(NarrativeSynthesis).order_by(
            NarrativeSynthesis.generated_at.desc()
        ).limit(3).all()

        if not syntheses:
            return "No historical context available."

        memory_parts = ["## Recent Intelligence Summaries"]

        for synth in syntheses:
            if synth.executive_summary:
                date_str = synth.generated_at.strftime("%Y-%m-%d")
                memory_parts.append(f"\n**{date_str}:** {synth.executive_summary[:300]}...")

        return "\n".join(memory_parts)

    def _enforce_token_budget(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce token budget by compressing context if needed

        Strategy:
        1. Count current tokens
        2. If over budget, compress in this order:
           - Reduce articles (50 → 30 → 20)
           - Trim historical memory (keep top 2 summaries)
           - Truncate article content (1000 → 500 tokens)

        Args:
            context: Raw context dictionary

        Returns:
            Token-optimized context dictionary
        """
        # Estimate current token usage
        tokens = self._estimate_tokens(context)

        logger.info(f"Initial context: ~{tokens['total']} tokens")

        # Check if we're over budget (system + articles + historical)
        budget_used = tokens['system'] + tokens['articles'] + tokens['historical']
        budget_limit = (self.TOKEN_BUDGET['system_prompt'] +
                       self.TOKEN_BUDGET['articles'] +
                       self.TOKEN_BUDGET['historical'])

        if budget_used <= budget_limit:
            logger.info(f"Within token budget: {budget_used}/{budget_limit} tokens")
            context['_token_metadata'] = tokens
            return context

        logger.warning(f"Over token budget: {budget_used}/{budget_limit} tokens, compressing...")

        # Compression step 1: Reduce article count
        if len(context['articles']) > 30:
            logger.info(f"Reducing articles from {len(context['articles'])} to 30")
            context['articles'] = context['articles'][:30]
            tokens = self._estimate_tokens(context)
            budget_used = tokens['system'] + tokens['articles'] + tokens['historical']

        if budget_used <= budget_limit:
            context['_token_metadata'] = tokens
            return context

        # Compression step 2: Further reduce articles
        if len(context['articles']) > 20:
            logger.info(f"Further reducing articles from {len(context['articles'])} to 20")
            context['articles'] = context['articles'][:20]
            tokens = self._estimate_tokens(context)
            budget_used = tokens['system'] + tokens['articles'] + tokens['historical']

        if budget_used <= budget_limit:
            context['_token_metadata'] = tokens
            return context

        # Compression step 3: Trim historical memory
        if "Recent Intelligence Summaries" in context['memory']:
            logger.info("Trimming historical memory to last 2 summaries")
            memory_lines = context['memory'].split('\n')
            # Keep header + first 2 summaries (approximately)
            context['memory'] = '\n'.join(memory_lines[:8])
            tokens = self._estimate_tokens(context)

        context['_token_metadata'] = tokens
        logger.info(f"Compressed context: ~{tokens['total']} tokens")
        return context

    def _estimate_tokens(self, context: Dict[str, Any]) -> Dict[str, int]:
        """
        Estimate token count for context components

        Uses rough approximation: 1 token ≈ 4 characters
        This is conservative for English text

        Args:
            context: Context dictionary

        Returns:
            Token count breakdown
        """
        def count_chars(obj):
            return len(json.dumps(obj)) if obj else 0

        system_chars = (
            count_chars(context.get('user_profile', {})) +
            len(context.get('instructions', ''))
        )

        articles_chars = count_chars(context.get('articles', []))
        memory_chars = len(context.get('memory', ''))

        return {
            'system': system_chars // 4,
            'articles': articles_chars // 4,
            'historical': memory_chars // 4,
            'total': (system_chars + articles_chars + memory_chars) // 4
        }

    def _format_user_profile(self) -> Dict[str, Any]:
        """Format user profile for context"""
        if not self.user_profile:
            return {
                "location": "Unknown",
                "professional_domains": [],
                "civic_interests": []
            }

        location = self.user_profile.get_primary_location()
        location_str = f"{location.get('city', '')}, {location.get('state', '')}"

        return {
            "location": location_str,
            "professional_domains": self.user_profile.get_professional_domains(),
            "civic_interests": self.user_profile.get_civic_interests()
        }

    def _format_articles(self, articles: List[Article]) -> List[Dict[str, Any]]:
        """Format articles for context inclusion"""
        formatted = []

        for article in articles:
            # Use embedding_summary if available, fallback to normalized_content
            content = article.embedding_summary or article.normalized_content or article.description or ""

            formatted.append({
                "id": article.id,  # Include ID for tracking
                "title": article.title,
                "source": article.feed.name if article.feed else "Unknown",
                "published_date": article.published_date.isoformat() if article.published_date else None,
                "content": content,
                "url": article.url,
                "entities": article.entities if article.entities else []
            })

        return formatted

    def _get_synthesis_instructions(self) -> str:
        """Get instructions for narrative synthesis using configured perspective with user data injection"""

        # Extract user-specific data for framework injection
        if self.user_profile:
            location = self.user_profile.get_primary_location()
            professional = self.user_profile.get_professional_context()
            civic = self.user_profile.get_civic_interests()

            # Prepare replacement values
            city = location.get('city', 'your city')
            state = location.get('state', 'your state')
            region = location.get('region', location.get('city', 'your region'))
            country = location.get('country', 'United States')

            professional_domains = ', '.join(professional.get('professional_domains', ['your profession']))
            civic_focus = ', '.join(civic.get('policy_areas', ['civic issues'])[:3])
            tone = self.perspective.tone

            # Inject user data into perspective framework
            personalized_framework = self.perspective.framework.format(
                city=city,
                state=state,
                region=region,
                country=country,
                professional_domains=professional_domains,
                civic_focus=civic_focus,
                tone=tone
            )
        else:
            # No user profile - use framework as-is with generic placeholders
            personalized_framework = self.perspective.framework.format(
                city="your city",
                state="your state",
                region="your region",
                country="your country",
                professional_domains="your profession",
                civic_focus="civic issues",
                tone=self.perspective.tone
            )

        perspective_instructions = f"""# Perspective: {self.perspective.name}

{personalized_framework}

## Your Task

Analyze the provided articles and generate a structured narrative intelligence brief.

**Output Requirements:**
1. **Executive Summary**: 2-3 paragraphs synthesizing key developments and implications
2. **Temporal Layers**: Organize insights by time horizon
3. **Cross-Domain Insights**: Connect patterns across different domains
4. **Priority Actions**: Actionable recommendations with reasoning

**Tone**: {self.perspective.tone}
"""
        return perspective_instructions

    def _get_summary_instructions(self, brief_type: str) -> str:
        """Get instructions for executive summary using configured perspective with user data injection"""
        period = "today's developments" if brief_type == "daily" else "this week's trends"

        # Extract user context
        if self.user_profile:
            location = self.user_profile.get_primary_location()
            professional = self.user_profile.get_professional_context()
            civic = self.user_profile.get_civic_interests()

            location_str = f"{location.get('city', 'your city')}, {location.get('state', 'your state')}"
            professional_domains = ', '.join(professional.get('professional_domains', ['your profession']))
            civic_focus = ', '.join(civic.get('policy_areas', ['civic issues'])[:3])
        else:
            location_str = "your location"
            professional_domains = "your profession"
            civic_focus = "civic issues"

        return f"""Generate a concise executive summary (3-5 sentences) analyzing {period}.

**Perspective**: {self.perspective.name} ({location_str})
**Professional focus**: {professional_domains}
**Civic focus**: {civic_focus}

Focus on:
- Implications across the user's life contexts
- Regional and broader impacts for {location_str}
- Forward-looking analysis
- Actionable intelligence

Synthesize key themes rather than listing individual items. Maintain a {self.perspective.tone} tone."""
