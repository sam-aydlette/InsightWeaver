"""
Perception Pipeline
Extracts cross-article patterns, entity relationships, and event sequences
Runs before synthesis to help Claude identify connections
"""

import json
import logging
from typing import Any

from ..database.models import Article
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class PerceptionEngine:
    """Extracts patterns and relationships from article sets before synthesis"""

    def __init__(self):
        """Initialize perception engine"""
        self.client = ClaudeClient()

    async def extract_perception(self, articles: list[Article]) -> dict[str, Any]:
        """
        Extract cross-article patterns and relationships

        Args:
            articles: List of articles to analyze

        Returns:
            Dictionary containing entity mentions, connections, and sequences
        """
        if not articles:
            return self._empty_perception()

        logger.info(f"Extracting perception from {len(articles)} articles")

        try:
            # Format articles for perception extraction
            articles_text = self._format_articles(articles)

            # Build extraction prompt
            prompt = self._build_extraction_prompt(len(articles))

            # Extract perception using Claude
            response = await self.client.analyze(
                system_prompt="You are a pattern recognition system. Identify connections across news articles.",
                user_message=f"{prompt}\n\n{articles_text}",
                temperature=0.3,  # Lower temperature for consistent extraction
                max_tokens=3000,  # Keep perception concise
            )

            # Parse response
            perception = self._parse_response(response)

            logger.info(
                f"Extracted perception: {len(perception.get('entity_mentions', []))} entities, "
                f"{len(perception.get('cross_article_connections', []))} connections, "
                f"{len(perception.get('event_sequences', []))} sequences"
            )

            return perception

        except Exception as e:
            logger.error(f"Perception extraction failed: {e}", exc_info=True)
            return self._empty_perception()

    def format_for_context(self, perception: dict[str, Any]) -> str:
        """
        Format perception data as context string for synthesis

        Args:
            perception: Extracted perception dictionary

        Returns:
            Formatted markdown string
        """
        if not perception or perception.get("_empty"):
            return ""

        parts = ["## Cross-Article Insights (Perception Layer)\n"]

        # Entity mentions across articles
        entities = perception.get("entity_mentions", [])
        if entities:
            parts.append("### Key Entities Appearing Across Multiple Articles:")
            for entity in entities[:10]:  # Top 10
                article_count = len(entity.get("article_ids", []))
                contexts = entity.get("contexts", [])
                context_str = "; ".join(contexts[:2])  # First 2 contexts
                parts.append(
                    f"- **{entity['entity']}** ({entity['type']}) - {article_count} articles: {context_str}"
                )
            parts.append("")

        # Cross-article connections
        connections = perception.get("cross_article_connections", [])
        if connections:
            parts.append("### Patterns Across Articles:")
            for conn in connections[:8]:  # Top 8
                article_count = len(conn.get("article_ids", []))
                parts.append(
                    f"- **{conn['theme']}** ({article_count} articles): {conn['connection']}"
                )
            parts.append("")

        # Event sequences
        sequences = perception.get("event_sequences", [])
        if sequences:
            parts.append("### Event Timelines:")
            for seq in sequences[:5]:  # Top 5
                timeframe = seq.get("timeframe", "recent")
                parts.append(f"- {seq['sequence']} ({timeframe})")
            parts.append("")

        return "\n".join(parts)

    def _format_articles(self, articles: list[Article]) -> str:
        """Format articles for perception extraction"""
        formatted = []

        for i, article in enumerate(articles, 1):
            content = (
                article.embedding_summary or article.normalized_content or article.description or ""
            )
            date_str = (
                article.published_date.strftime("%Y-%m-%d")
                if article.published_date
                else "unknown date"
            )

            formatted.append(f"Article {i} ({date_str}):")
            formatted.append(f"Title: {article.title}")
            formatted.append(f"Content: {content[:300]}...")  # Keep brief
            formatted.append("")

        return "\n".join(formatted)

    def _build_extraction_prompt(self, article_count: int) -> str:
        """Build prompt for perception extraction"""
        return f"""Analyze these {article_count} news articles and extract cross-article patterns.

Your task is to identify:
1. **Entities** mentioned in multiple articles (people, organizations, locations)
2. **Themes** that connect different articles
3. **Event sequences** showing temporal progression

## Output Format

Return ONLY valid JSON with this structure:

{{
  "entity_mentions": [
    {{
      "entity": "Full name or organization",
      "type": "person|organization|location|event",
      "article_ids": [1, 3, 7],
      "contexts": ["what they did in article 1", "what they did in article 3"]
    }}
  ],
  "cross_article_connections": [
    {{
      "theme": "Short theme name",
      "article_ids": [2, 5, 8, 12],
      "connection": "Brief explanation of how these articles connect"
    }}
  ],
  "event_sequences": [
    {{
      "sequence": "Event A → Event B → Event C",
      "article_ids": [1, 4, 9],
      "timeframe": "Specific dates or 'past week' etc"
    }}
  ]
}}

## Guidelines

- Only include entities mentioned in 2+ articles
- Only include connections spanning 3+ articles
- Keep contexts brief (1 sentence each)
- Focus on actionable insights, not trivial details
- Maximum 10 entities, 8 connections, 5 sequences

Return ONLY the JSON, no markdown formatting or additional text."""

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse Claude's perception extraction response"""
        try:
            # Remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            perception = json.loads(response.strip())

            # Validate structure
            if not isinstance(perception, dict):
                logger.warning("Perception response is not a dictionary")
                return self._empty_perception()

            # Ensure required keys exist
            perception.setdefault("entity_mentions", [])
            perception.setdefault("cross_article_connections", [])
            perception.setdefault("event_sequences", [])

            return perception

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse perception JSON: {e}")
            logger.debug(f"Response was: {response[:500]}...")
            return self._empty_perception()

    def _empty_perception(self) -> dict[str, Any]:
        """Return empty perception structure"""
        return {
            "entity_mentions": [],
            "cross_article_connections": [],
            "event_sequences": [],
            "_empty": True,
        }
