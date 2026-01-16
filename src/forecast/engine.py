"""
Forecast Engine
Core forecasting logic using certainty-based categorization (Rumsfeld framework)
"""

import json
import logging
from datetime import datetime
from typing import Any

from ..context.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class ForecastEngine:
    """
    Generates forecasts organized by certainty level using the Rumsfeld framework:
    - Known Knowns: Certain or near-certain forecasts
    - Known Unknowns: Mild conjecture grounded in significant evidence
    - Unknown Unknowns: Conjecture based on some evidence (weak signals)
    """

    def __init__(self, claude_client: ClaudeClient | None = None):
        """
        Initialize forecast engine

        Args:
            claude_client: Optional ClaudeClient instance (creates new if not provided)
        """
        self.client = claude_client or ClaudeClient()

    async def generate_forecast(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Generate forecasts organized by certainty level

        Args:
            context: Curated context from ForecastContextCurator

        Returns:
            Forecast data dictionary with three certainty categories
        """
        logger.info("Generating certainty-based forecast...")

        # Build forecast task
        task = self._build_forecast_task()

        # Send to Claude
        try:
            response = await self.client.analyze_with_context(
                context=context, task=task, temperature=1.0
            )

            # Parse JSON response
            forecast = self._parse_forecast_response(response)

            # Validate structure
            self._validate_forecast_structure(forecast)

            # Add metadata
            forecast["generated_at"] = datetime.utcnow().isoformat()

            logger.info("Successfully generated certainty-based forecast")
            return forecast

        except Exception as e:
            logger.error(f"Error generating forecast: {e}")
            raise

    def _build_forecast_task(self) -> str:
        """
        Build forecast task prompt using certainty-based categorization

        Returns:
            Formatted task prompt
        """
        task = """Generate forecasts organized by certainty level using the Rumsfeld framework.

Analyze the provided articles and data to identify forecasts across three certainty categories.
Use trend analysis, pattern recognition, and causal reasoning internally to ground your forecasts,
but organize your output by certainty level rather than by methodology.

Each forecast MUST include its own timeline (when it will occur/unfold).

## CATEGORY 1: KNOWN KNOWNS (Certain or Near-Certain)
These are forecasts that are virtually guaranteed to happen based on:
- Scheduled events (elections, policy deadlines, product launches)
- Announced plans (confirmed projects, stated intentions by authorities)
- Legal/regulatory requirements (compliance deadlines, mandated changes)
- Demographic certainties (population milestones, generational shifts)

For each Known Known, provide:
- The forecast itself (what will happen)
- Timeline (specific date or timeframe)
- Basis for certainty (why this is certain - cite evidence)
- Impact (how it affects the user's context)

## CATEGORY 2: KNOWN UNKNOWNS (Evidence-Based Projections)
These are forecasts with significant supporting evidence but uncertain outcomes:
- Clear trends with uncertain endpoints
- Pending decisions with known options
- Emerging patterns with multiple possible trajectories
- Policy debates with foreseeable resolution paths

For each Known Unknown, provide:
- The forecast (what is likely to happen)
- Timeline (expected timeframe)
- Evidence (what supports this projection)
- Possible outcomes (2-3 ways this could unfold)
- Key factors (what will determine the actual outcome)

## CATEGORY 3: UNKNOWN UNKNOWNS (Weak Signal Projections)
These are speculative forecasts based on emerging patterns or weak signals:
- Early-stage trends that could accelerate
- Potential disruptions visible only in weak signals
- Black swan possibilities grounded in some evidence
- Emergent phenomena that could materialize

For each Unknown Unknown, provide:
- The forecast (what could happen)
- Timeline (potential timeframe if it occurs)
- Weak signal (what suggests this possibility)
- Potential impact (consequences if it materializes)
- Why plausible (reasoning for considering this)

## OUTPUT FORMAT
Return ONLY valid JSON matching this structure:

```json
{
  "known_knowns": [
    {
      "forecast": "Clear description of the certain/near-certain forecast",
      "timeline": "Specific date or timeframe (e.g., 'November 2026', 'Q2 2026', '6 months')",
      "basis": "Why this is certain - cite specific evidence from articles",
      "impact": "How this affects the user's local/professional context"
    }
  ],
  "known_unknowns": [
    {
      "forecast": "Description of the evidence-based projection",
      "timeline": "Expected timeframe for resolution/occurrence",
      "evidence": "What data/trends support this projection",
      "possible_outcomes": ["outcome1", "outcome2", "outcome3"],
      "key_factors": ["factor1", "factor2"]
    }
  ],
  "unknown_unknowns": [
    {
      "forecast": "Description of the speculative forecast",
      "timeline": "Potential timeframe if it occurs",
      "weak_signal": "What early indicator suggests this possibility",
      "potential_impact": "Consequences if this materializes",
      "why_plausible": "Reasoning for why this deserves consideration"
    }
  ],
  "data_sources_summary": "Brief summary of what data informed these forecasts"
}
```

## GUIDELINES
- Generate 4-6 forecasts per category (12-18 total)
- Timelines can range from weeks to years - use appropriate granularity
- Base ALL forecasts on evidence from the provided articles and data
- For Known Knowns, only include truly certain events with clear evidence
- For Known Unknowns, ensure significant supporting evidence exists
- For Unknown Unknowns, identify genuine weak signals, not pure speculation
- Return ONLY the JSON object, no explanatory text before or after

## CRITICAL: FORECAST PRECISION REQUIREMENTS
Every forecast MUST be specific and precise. Vague predictions are useless.

BAD (too vague):
- "Federal contractor landscape may shift based on policy changes"
- "Housing market could change"
- "Technology sector will evolve"

GOOD (specific and precise):
- "Federal cybersecurity contractors will see 15-20% budget increases as agencies implement new CISA mandates"
- "Fairfax County housing prices will rise 5-8% as Dulles Tech Center converts to residential"
- "AI governance roles will become mandatory for federal contractors handling sensitive data"

For each forecast, clearly state:
- WHAT specifically will happen (not "may change" but the actual change)
- WHO is affected
- The DIRECTION and MAGNITUDE when quantifiable
- The SPECIFIC OUTCOME, not just that something "will shift"
"""

        return task

    def _parse_forecast_response(self, response: str) -> dict[str, Any]:
        """
        Parse Claude's response into structured forecast data

        Args:
            response: Raw response from Claude

        Returns:
            Parsed forecast dictionary

        Raises:
            ValueError: If response is not valid JSON
        """
        # Try to extract JSON from response
        # Sometimes Claude wraps JSON in markdown code blocks
        response = response.strip()

        # Remove markdown code blocks if present
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        try:
            forecast = json.loads(response)
            return forecast
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse forecast JSON: {e}")
            logger.error(f"Response was: {response[:500]}...")
            raise ValueError(f"Invalid JSON response from Claude: {e}")

    def _validate_forecast_structure(self, forecast: dict[str, Any]) -> None:
        """
        Validate that forecast contains all required certainty categories

        Args:
            forecast: Parsed forecast dictionary

        Raises:
            ValueError: If required fields are missing
        """
        required_categories = ["known_knowns", "known_unknowns", "unknown_unknowns"]

        missing_categories = [cat for cat in required_categories if cat not in forecast]

        if missing_categories:
            raise ValueError(f"Forecast missing required categories: {missing_categories}")

        # Validate each category has at least one item
        for category in required_categories:
            if not forecast.get(category):
                logger.warning(f"Category '{category}' is empty")

        logger.info("Forecast structure validation passed")
