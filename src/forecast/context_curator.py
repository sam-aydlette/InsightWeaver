"""
Forecast Context Curator
Builds optimal context for long-term forecasting with authoritative data integration
Extends base ContextCurator with stratified historical sampling and external data sources
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from ..context.curator import ContextCurator
from ..database.connection import get_db
from ..database.models import Article, APIDataPoint
from ..utils.profile_loader import UserProfile

logger = logging.getLogger(__name__)


class ForecastContextCurator(ContextCurator):
    """
    Curates context specifically for long-term forecasting

    Extends ContextCurator with:
    - Stratified historical article sampling (evenly distributed across months)
    - Authoritative data integration (Census, World Bank, etc.)
    - Forecast-specific token budget allocation
    - Long-term trend context
    """

    # Forecast-specific token budget (200k total)
    FORECAST_TOKEN_BUDGET = {
        'system_prompt': 8000,       # Forecast instructions + framework
        'articles': 40000,            # Stratified historical articles
        'authoritative_data': 30000,  # Census, World Bank, UN, etc.
        'historical_memory': 15000,   # Semantic memory + past syntheses
        'response': 12000,            # Claude's forecast output
        'safety_margin': 95000        # Reserved buffer
    }

    # Total allocated: 105,000 tokens
    # Safety margin: 95,000 tokens

    async def curate_for_horizon(
        self,
        horizon_months: int,
        topic_filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Curate context for specific forecast horizon

        Args:
            horizon_months: Forecast horizon in months (6, 12, 36, 60)
            topic_filters: Optional topic/scope filters

        Returns:
            Curated context dictionary optimized for forecasting
        """
        with get_db() as session:
            # 1. Stratified article sampling (evenly distributed across time)
            lookback_months = min(horizon_months, 12)  # Cap at 12 months of history
            articles = self._get_stratified_articles(
                session,
                months=lookback_months,
                articles_per_month=8
            )

            # Apply topic filters if provided
            if topic_filters and self.topic_matcher and self.user_profile:
                articles = self.topic_matcher.filter_articles(
                    articles=articles,
                    topic_filters=topic_filters,
                    user_profile=self.user_profile
                )

            logger.info(f"Curated {len(articles)} stratified articles for {horizon_months}mo forecast")

            # 2. Authoritative data (NEW for forecasting)
            authoritative_data = self._get_authoritative_data(session, horizon_months)

            # 3. Semantic memory facts
            memory_facts = self._get_forecast_memory(session, articles)

            # 4. Build forecast context
            context = {
                "user_profile": self._format_user_profile(),
                "articles": self._format_articles(articles),
                "authoritative_data": self._format_authoritative_data(authoritative_data),
                "historical_memory": memory_facts,
                "instructions": self._get_forecast_instructions(horizon_months),
                "article_count": len(articles)  # Track count for metadata
            }

            # 5. Enforce forecast token budget
            context = self._enforce_forecast_token_budget(context)

            return context

    def _get_stratified_articles(
        self,
        session: Session,
        months: int,
        articles_per_month: int
    ) -> List[Article]:
        """
        Get articles evenly distributed across time period (stratified sampling)

        This maintains temporal distribution within token budget.
        For 12 months lookback: 8 articles/month = 96 articles total

        Args:
            session: Database session
            months: Number of months to look back
            articles_per_month: Articles to sample per month

        Returns:
            List of stratified articles
        """
        all_articles = []

        for month_offset in range(months):
            # Define month window
            end_date = datetime.utcnow() - timedelta(days=30 * month_offset)
            start_date = end_date - timedelta(days=30)

            # Query articles in this month
            month_articles = session.query(Article).filter(
                Article.fetched_at >= start_date,
                Article.fetched_at < end_date,
                Article.filtered == False
            ).order_by(
                Article.fetched_at.desc()
            ).limit(articles_per_month).all()

            all_articles.extend(month_articles)

            logger.debug(
                f"Month {month_offset + 1}/{months}: "
                f"sampled {len(month_articles)} articles from {start_date.date()} to {end_date.date()}"
            )

        logger.info(f"Stratified sampling: {len(all_articles)} articles across {months} months")
        return all_articles

    def _get_authoritative_data(
        self,
        session: Session,
        horizon_months: int
    ) -> List[APIDataPoint]:
        """
        Get authoritative data from external sources for forecasting

        Queries APIDataPoint for Census Bureau, World Bank, UN, think tanks, etc.

        Args:
            session: Database session
            horizon_months: Forecast horizon in months

        Returns:
            List of authoritative data points
        """
        # Get data from last 90 days (authoritative data refreshes weekly/monthly)
        cutoff_date = datetime.utcnow() - timedelta(days=90)

        # Query for statistical and authoritative data
        authoritative_sources = [
            'census_statistical',
            'world_bank_indicator',
            'un_statistical',
            'think_tank_research'
        ]

        data_points = session.query(APIDataPoint).filter(
            APIDataPoint.data_type.in_(authoritative_sources),
            APIDataPoint.fetched_at >= cutoff_date
        ).order_by(
            APIDataPoint.relevance_score.desc()
        ).limit(50).all()  # Top 50 most relevant data points

        logger.info(f"Retrieved {len(data_points)} authoritative data points for forecasting")
        return data_points

    def _get_forecast_memory(
        self,
        session: Session,
        articles: List[Article]
    ) -> str:
        """
        Get historical memory relevant to forecasting

        Combines semantic memory facts with past synthesis insights

        Args:
            session: Database session
            articles: Current article set

        Returns:
            Formatted memory context string
        """
        from ..config.settings import settings
        from ..context.semantic_memory import SemanticMemory

        memory_parts = []

        # Get semantic memory if enabled
        if getattr(settings, 'enable_semantic_memory', False):
            try:
                semantic_memory = SemanticMemory(session)
                relevant_facts = semantic_memory.retrieve_relevant_facts(
                    articles,
                    max_facts=30  # More facts for long-term context
                )
                semantic_context = semantic_memory.build_historical_context(relevant_facts)
                if semantic_context:
                    memory_parts.append(semantic_context)
                    logger.info(f"Added {len(relevant_facts)} semantic facts to forecast context")
            except Exception as e:
                logger.warning(f"Failed to retrieve semantic memory: {e}")

        # Get historical synthesis insights
        historical_memory = self._get_historical_memory(session)
        if historical_memory:
            memory_parts.append(historical_memory)

        return "\n\n".join(memory_parts)

    def _format_authoritative_data(self, data_points: List[APIDataPoint]) -> str:
        """
        Format authoritative data for context inclusion

        Args:
            data_points: List of APIDataPoint objects

        Returns:
            Formatted string for context
        """
        if not data_points:
            return "No authoritative data available."

        lines = ["## Authoritative Data Sources\n"]

        # Group by source type
        by_type = {}
        for dp in data_points:
            data_type = dp.data_type
            if data_type not in by_type:
                by_type[data_type] = []
            by_type[data_type].append(dp)

        # Format each type
        for data_type, points in by_type.items():
            lines.append(f"\n### {data_type.replace('_', ' ').title()}")

            for i, point in enumerate(points[:10], 1):  # Limit to 10 per type
                lines.append(f"\n**{i}. {point.title}**")
                if point.description:
                    lines.append(point.description[:300])  # Truncate long descriptions

                # Include key data from payload
                if point.data_payload:
                    payload_str = str(point.data_payload)[:200]  # First 200 chars
                    lines.append(f"Data: {payload_str}")

                if point.published_date:
                    lines.append(f"Date: {point.published_date.strftime('%Y-%m-%d')}")

        return "\n".join(lines)

    def _get_forecast_instructions(self, horizon_months: int) -> str:
        """
        Build forecast-specific instructions

        Args:
            horizon_months: Forecast horizon in months

        Returns:
            Instruction string for Claude
        """
        target_date = datetime.now() + timedelta(days=horizon_months * 30)
        target_str = target_date.strftime("%B %Y")

        instructions = f"""## Forecast Analysis Task

You are conducting a long-term trend analysis and forecast for {horizon_months} months ahead (target: {target_str}).

### Data Sources Available:
1. **Historical Articles**: Stratified sample across past months showing trend evolution
2. **Authoritative Data**: Statistical indicators from Census Bureau, World Bank, UN, research institutions
3. **Semantic Memory**: Key facts and patterns extracted from past analysis

### Analysis Requirements:
Generate a comprehensive forecast including ALL 5 analysis types:
1. Trend Extrapolation
2. Scenario Modeling (optimistic/baseline/pessimistic)
3. Pattern Recognition (cyclical patterns, historical parallels)
4. Causal Chain Analysis
5. Event Risk Categorization (known knowns/unknowns/unknown unknowns)

### Uncertainty and Limitations:
- {horizon_months} months is a {"short" if horizon_months <= 6 else "medium" if horizon_months <= 12 else "long"}-term horizon
- Be explicit about uncertainties, assumptions, and data limitations
- Acknowledge what you cannot know or predict
- For claimed certainties (Known Knowns), provide evidence

### Output:
Return structured JSON with all 5 analysis types as specified in the forecast engine prompt.
"""

        return instructions

    def _enforce_forecast_token_budget(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enforce forecast-specific token budget

        Args:
            context: Raw context dictionary

        Returns:
            Budget-compliant context
        """
        # Estimate token counts (rough: 1 token ≈ 4 characters)
        estimated_tokens = {}
        for key, value in context.items():
            if isinstance(value, str):
                estimated_tokens[key] = len(value) // 4
            else:
                estimated_tokens[key] = len(str(value)) // 4

        total_estimated = sum(estimated_tokens.values())
        budget_limit = sum(self.FORECAST_TOKEN_BUDGET.values()) - self.FORECAST_TOKEN_BUDGET['safety_margin']

        logger.info(f"Estimated context tokens: {total_estimated} (budget: {budget_limit})")

        # If over budget, compress
        if total_estimated > budget_limit:
            logger.warning(f"Context exceeds budget ({total_estimated} > {budget_limit}), compressing...")

            # Compression priority: articles first, then authoritative, then memory
            if estimated_tokens.get('articles', 0) > self.FORECAST_TOKEN_BUDGET['articles']:
                # Truncate article content
                context['articles'] = self._compress_text(
                    context['articles'],
                    self.FORECAST_TOKEN_BUDGET['articles']
                )

            if estimated_tokens.get('authoritative_data', 0) > self.FORECAST_TOKEN_BUDGET['authoritative_data']:
                context['authoritative_data'] = self._compress_text(
                    context['authoritative_data'],
                    self.FORECAST_TOKEN_BUDGET['authoritative_data']
                )

            if estimated_tokens.get('historical_memory', 0) > self.FORECAST_TOKEN_BUDGET['historical_memory']:
                context['historical_memory'] = self._compress_text(
                    context['historical_memory'],
                    self.FORECAST_TOKEN_BUDGET['historical_memory']
                )

        return context

    def _compress_text(self, text: str, target_tokens: int) -> str:
        """
        Compress text to fit token budget

        Args:
            text: Text to compress
            target_tokens: Target token count

        Returns:
            Compressed text
        """
        target_chars = target_tokens * 4  # Rough conversion
        if len(text) <= target_chars:
            return text

        # Simple truncation (could be enhanced with smarter compression)
        return text[:target_chars] + "\n\n[...truncated for token budget...]"
