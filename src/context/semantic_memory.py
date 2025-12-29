"""
Semantic Memory System
Persistent fact storage and historical context retrieval
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from .claude_client import ClaudeClient
from ..database.models import MemoryFact, Article
from ..config.settings import settings

logger = logging.getLogger(__name__)


class SemanticMemory:
    """Manages persistent semantic facts for historical context"""

    def __init__(self, session: Session):
        """
        Initialize semantic memory

        Args:
            session: Database session
        """
        self.session = session
        self.client = ClaudeClient()

    async def extract_facts_from_synthesis(
        self,
        synthesis_data: Dict[str, Any],
        source_synthesis_id: int
    ) -> List[MemoryFact]:
        """
        Extract structured facts from synthesis output

        Args:
            synthesis_data: Synthesis output dictionary
            source_synthesis_id: Database ID for source tracking

        Returns:
            List of MemoryFact objects ready for storage
        """
        logger.info(f"Extracting facts from synthesis {source_synthesis_id}")

        # Format synthesis for fact extraction
        synthesis_text = self._format_synthesis_for_extraction(synthesis_data)

        # Build extraction prompt
        extraction_prompt = self._build_extraction_prompt(synthesis_text)

        try:
            # Get Claude to extract facts
            response = await self.client.analyze(
                system_prompt="You are a fact extraction system. Extract structured facts from intelligence briefs.",
                user_message=extraction_prompt,
                temperature=0.3,  # Lower temperature for consistent extraction
                max_tokens=2000
            )

            # Parse extracted facts
            facts_data = self._parse_extraction_response(response)

            # Convert to MemoryFact objects
            facts = []
            for fact_dict in facts_data:
                fact_type = fact_dict.get('type', 'metric')

                fact = MemoryFact(
                    fact_type=fact_type,
                    subject=fact_dict.get('subject', ''),
                    predicate=fact_dict.get('predicate', ''),
                    object=fact_dict.get('object', ''),
                    temporal_context=fact_dict.get('temporal_context'),
                    confidence=float(fact_dict.get('confidence', 0.7)),
                    source_synthesis_id=source_synthesis_id,
                    expires_at=self._calculate_expiration(fact_type),
                    fact_metadata={'extraction_date': datetime.utcnow().isoformat()}
                )
                facts.append(fact)

            logger.info(f"Extracted {len(facts)} facts from synthesis")
            return facts

        except Exception as e:
            logger.error(f"Fact extraction failed: {e}", exc_info=True)
            return []

    def store_facts(self, facts: List[MemoryFact]) -> int:
        """
        Store facts in database

        Args:
            facts: List of MemoryFact objects

        Returns:
            Number of facts stored
        """
        if not facts:
            return 0

        try:
            for fact in facts:
                self.session.add(fact)

            self.session.commit()
            logger.info(f"Stored {len(facts)} facts in memory")
            return len(facts)

        except Exception as e:
            logger.error(f"Failed to store facts: {e}")
            self.session.rollback()
            return 0

    def retrieve_relevant_facts(
        self,
        articles: List[Article],
        max_facts: int = 20
    ) -> List[MemoryFact]:
        """
        Retrieve facts relevant to current article set

        Retention is managed by fact-type-based expires_at:
        - decision/event facts expire after 60 days
        - trend facts expire after 180 days
        - metric/relationship facts expire after 365 days

        Args:
            articles: Current articles being analyzed
            max_facts: Maximum facts to retrieve

        Returns:
            List of relevant MemoryFact objects, prioritized by relevance and recency
        """
        if not articles:
            return []

        # Extract keywords/entities from articles for matching
        keywords = self._extract_keywords_from_articles(articles)

        # Query facts matching keywords that haven't expired
        facts = []

        for keyword in keywords[:10]:  # Limit to top 10 keywords
            matching_facts = self.session.query(MemoryFact).filter(
                MemoryFact.subject.ilike(f'%{keyword}%'),
                (MemoryFact.expires_at.is_(None) | (MemoryFact.expires_at > datetime.utcnow())),
                MemoryFact.confidence >= getattr(settings, 'memory_relevance_threshold', 0.6)
            ).order_by(
                MemoryFact.confidence.desc(),
                MemoryFact.created_at.desc()
            ).limit(3).all()

            facts.extend(matching_facts)

        # Deduplicate and limit
        seen_ids = set()
        unique_facts = []
        for fact in facts:
            if fact.id not in seen_ids:
                seen_ids.add(fact.id)
                unique_facts.append(fact)

                if len(unique_facts) >= max_facts:
                    break

        logger.info(f"Retrieved {len(unique_facts)} relevant facts from memory")
        return unique_facts

    def build_historical_context(self, facts: List[MemoryFact]) -> str:
        """
        Format facts as context string for synthesis

        Args:
            facts: Retrieved memory facts

        Returns:
            Formatted context string (target: ~2-3k tokens)
        """
        if not facts:
            return ""

        # Group facts by type
        grouped_facts = {
            'metric': [],
            'trend': [],
            'relationship': [],
            'decision': [],
            'civic_event': [],
            'policy_position': []
        }

        for fact in facts:
            fact_type = fact.fact_type
            if fact_type in grouped_facts:
                grouped_facts[fact_type].append(fact)
            else:
                grouped_facts['metric'].append(fact)  # Default to metric

        # Build formatted context
        context_parts = ["## Historical Context (from past syntheses)\n"]

        # Civic Events (prioritized for actionability)
        if grouped_facts['civic_event']:
            context_parts.append("### Upcoming Civic Events:")
            for fact in grouped_facts['civic_event'][:5]:
                context_parts.append(
                    f"- {fact.subject} {fact.predicate} {fact.object} "
                    f"({fact.temporal_context or 'date TBD'})"
                )
            context_parts.append("")

        # Policy Positions
        if grouped_facts['policy_position']:
            context_parts.append("### Policy Positions:")
            for fact in grouped_facts['policy_position'][:5]:
                context_parts.append(
                    f"- {fact.subject} {fact.predicate} {fact.object} "
                    f"({fact.temporal_context or 'recent'})"
                )
            context_parts.append("")

        # Metrics
        if grouped_facts['metric']:
            context_parts.append("### Key Metrics:")
            for fact in grouped_facts['metric'][:5]:
                context_parts.append(
                    f"- {fact.subject} {fact.predicate} {fact.object} "
                    f"({fact.temporal_context or 'recent'})"
                )
            context_parts.append("")

        # Trends
        if grouped_facts['trend']:
            context_parts.append("### Observed Trends:")
            for fact in grouped_facts['trend'][:5]:
                context_parts.append(
                    f"- {fact.subject}: {fact.predicate} {fact.object} "
                    f"({fact.temporal_context or 'ongoing'})"
                )
            context_parts.append("")

        # Relationships
        if grouped_facts['relationship']:
            context_parts.append("### Known Relationships:")
            for fact in grouped_facts['relationship'][:5]:
                context_parts.append(
                    f"- {fact.subject} {fact.predicate} {fact.object}"
                )
            context_parts.append("")

        # Decisions
        if grouped_facts['decision']:
            context_parts.append("### Past Decisions/Events:")
            for fact in grouped_facts['decision'][:5]:
                context_parts.append(
                    f"- {fact.subject} {fact.predicate} {fact.object} "
                    f"({fact.temporal_context or 'date unknown'})"
                )
            context_parts.append("")

        context = "\n".join(context_parts)
        logger.info(f"Built historical context: {len(context)} characters from {len(facts)} facts")
        return context

    def cleanup_expired_facts(self) -> int:
        """
        Remove facts that have passed their expiration date

        This should be run periodically (e.g., daily or weekly) to keep the
        memory database clean. Safe to call frequently as it only deletes
        expired facts.

        Returns:
            Number of facts deleted
        """
        try:
            now = datetime.utcnow()

            # Find all expired facts
            expired_facts = self.session.query(MemoryFact).filter(
                MemoryFact.expires_at.isnot(None),
                MemoryFact.expires_at <= now
            ).all()

            count = len(expired_facts)

            if count > 0:
                # Delete expired facts
                self.session.query(MemoryFact).filter(
                    MemoryFact.expires_at.isnot(None),
                    MemoryFact.expires_at <= now
                ).delete(synchronize_session=False)

                self.session.commit()
                logger.info(f"Cleaned up {count} expired facts from memory")
            else:
                logger.info("No expired facts to clean up")

            return count

        except Exception as e:
            logger.error(f"Failed to cleanup expired facts: {e}")
            self.session.rollback()
            return 0

    def _format_synthesis_for_extraction(self, synthesis_data: Dict[str, Any]) -> str:
        """Format synthesis data for fact extraction"""
        sections = []

        # Bottom line
        if "bottom_line" in synthesis_data:
            summary = synthesis_data["bottom_line"].get("summary", "")
            sections.append(f"Summary: {summary}")

        # Trends
        if "trends_and_patterns" in synthesis_data:
            trends = synthesis_data["trends_and_patterns"]
            for category, items in trends.items():
                for item in items[:3]:  # Top 3 per category
                    if isinstance(item, dict):
                        subject = item.get("subject", "")
                        direction = item.get("direction", "")
                        quantifier = item.get("quantifier", "")
                        if subject and direction:
                            sections.append(f"Trend: {subject} {direction} {quantifier}")

        # Priority events
        if "priority_events" in synthesis_data:
            events = synthesis_data["priority_events"]
            for event in events[:3]:  # Top 3 events
                if isinstance(event, dict):
                    evt = event.get("event", "")
                    when = event.get("when", "")
                    if evt:
                        sections.append(f"Event: {evt} ({when})")

        # Predictions
        if "predictions_scenarios" in synthesis_data:
            predictions = synthesis_data["predictions_scenarios"]
            for category, items in predictions.items():
                for pred in items[:2]:  # Top 2 per category
                    if isinstance(pred, dict):
                        prediction = pred.get("prediction", "")
                        confidence = pred.get("confidence", "")
                        if prediction:
                            sections.append(f"Prediction: {prediction} (confidence: {confidence})")

        return "\n".join(sections)

    def _build_extraction_prompt(self, synthesis_text: str) -> str:
        """Build prompt for fact extraction"""
        return f"""Extract key facts from this intelligence brief in structured format.

Intelligence Brief:
{synthesis_text}

Extract facts as subject-predicate-object triples. Focus on:
- Metrics (quantifiable data points)
- Trends (directional changes over time)
- Relationships (connections between entities)
- Decisions (actions taken or planned)
- Civic Events (government meetings, public hearings, elections, deadlines)
- Policy Positions (who supports/opposes what)

For each fact, provide:
- type: 'metric', 'trend', 'relationship', 'decision', 'civic_event', or 'policy_position'
- subject: The entity or topic
- predicate: The relationship or attribute
- object: The value or related entity
- temporal_context: When this applies (date, month, quarter, etc.) - be specific if mentioned
- confidence: 0.0-1.0 based on evidence strength

Return ONLY valid JSON array:
[
  {{
    "type": "metric",
    "subject": "Fairfax County unemployment",
    "predicate": "rate",
    "object": "2.3%",
    "temporal_context": "January 2025",
    "confidence": 0.9
  }},
  {{
    "type": "civic_event",
    "subject": "Fairfax County Board of Supervisors",
    "predicate": "public hearing",
    "object": "Route 28 widening project",
    "temporal_context": "February 4, 2025 at 7pm",
    "confidence": 0.95
  }},
  {{
    "type": "policy_position",
    "subject": "Springfield District Supervisor",
    "predicate": "supports",
    "object": "rezoning for mixed-use development",
    "temporal_context": "announced January 2025",
    "confidence": 0.85
  }},
  ...
]

Extract 5-15 most significant facts. Prioritize civic events with specific dates/deadlines. Return ONLY the JSON array, no additional text."""

    def _parse_extraction_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse Claude's fact extraction response"""
        try:
            # Clean markdown formatting
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            facts_data = json.loads(response.strip())

            # Validate it's a list
            if not isinstance(facts_data, list):
                logger.warning("Extraction response is not a list, wrapping")
                facts_data = [facts_data]

            return facts_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction JSON: {e}")
            logger.debug(f"Response was: {response[:500]}...")
            return []

    def _calculate_expiration(self, fact_type: str) -> Optional[datetime]:
        """
        Calculate expiration date based on fact type

        Retention policy:
        - decision/event: 60 days (time-bound, loses relevance fast)
        - civic_event: 90 days (civic deadlines and meetings remain relevant longer)
        - policy_position: 180 days (positions may evolve over time)
        - trend: 180 days (track until trend changes)
        - metric/relationship: 365 days (structural data, changes slowly)
        - Unknown types default to metric retention

        Returns None for evergreen facts (could add 'evergreen' type in future)
        """
        now = datetime.utcnow()

        if fact_type in ['decision', 'event']:
            return now + timedelta(days=60)
        elif fact_type == 'civic_event':
            return now + timedelta(days=90)
        elif fact_type == 'policy_position':
            return now + timedelta(days=180)
        elif fact_type == 'trend':
            return now + timedelta(days=180)
        elif fact_type in ['metric', 'relationship']:
            return now + timedelta(days=365)
        else:
            # Default to metric retention for unknown types
            return now + timedelta(days=365)

    def _extract_keywords_from_articles(self, articles: List[Article]) -> List[str]:
        """Extract keywords from articles for fact matching"""
        keywords = set()

        for article in articles[:10]:  # Sample first 10 articles
            # Extract from title
            if article.title:
                words = article.title.lower().split()
                # Add significant words (>3 chars, not common)
                keywords.update([
                    w.strip('.,!?()[]{}":;')
                    for w in words
                    if len(w) > 3 and w.lower() not in {'this', 'that', 'with', 'from', 'have', 'will', 'been'}
                ])

            # Extract from entities if available
            if article.entities:
                if isinstance(article.entities, list):
                    keywords.update([e.lower() for e in article.entities[:5]])

        # Return sorted by length (longer = more specific)
        return sorted(list(keywords), key=len, reverse=True)
