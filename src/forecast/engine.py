"""
Forecast Engine
Core forecasting logic using certainty-based categorization (Rumsfeld framework)
"""

import json
import logging
import re
from datetime import datetime, timedelta
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
        current_date = datetime.utcnow()
        current_date_str = current_date.strftime("%B %d, %Y")

        task = f"""Generate forecasts organized by certainty level using the Rumsfeld framework.

## CURRENT DATE: {current_date_str}

CRITICAL TEMPORAL REQUIREMENT: All forecasts must be for events AFTER {current_date_str}.
- Events that have ALREADY OCCURRED are FACTS, not forecasts - do not include them
- Events HAPPENING TODAY are NEWS, not forecasts - do not include them
- Only FUTURE events (after {current_date_str}) can be forecasts

Analyze the provided articles and data to identify forecasts across three certainty categories.
Use trend analysis, pattern recognition, and causal reasoning internally to ground your forecasts,
but organize your output by certainty level rather than by methodology.

Each forecast MUST include its own timeline (when it will occur/unfold) - and that timeline
MUST be in the future relative to {current_date_str}.

## CATEGORY 1: KNOWN KNOWNS (Certain or Near-Certain FUTURE Events)
These are forecasts for events that HAVE NOT YET OCCURRED but are virtually guaranteed to happen.

CRITICAL DISTINCTION - Read carefully:
- If an article describes something that HAS ALREADY HAPPENED -> This is a FACT, not a forecast. DO NOT INCLUDE IT.
- If an article describes something HAPPENING NOW/TODAY -> This is NEWS, not a forecast. DO NOT INCLUDE IT.
- If an article announces something SCHEDULED FOR THE FUTURE -> This IS a forecast. Include it.

Examples of what IS a Known Known (future events):
- "Election scheduled for November 2026" -> YES, include this
- "Budget deadline in Q3 2026" -> YES, include this
- "Construction to begin Spring 2026" -> YES, include this

Examples of what is NOT a Known Known (past/present events):
- "Governor sworn in today" -> NO, this is news (present) - DO NOT INCLUDE
- "Democrats won the election" -> NO, this is a fact (past) - DO NOT INCLUDE
- "Legislature passed the bill" -> NO, this is a fact (past) - DO NOT INCLUDE
- "Company announced layoffs" -> NO, this already happened - DO NOT INCLUDE

For genuine FUTURE events, Known Knowns are virtually guaranteed based on:
- Scheduled events (elections, policy deadlines, product launches)
- Announced plans (confirmed projects, stated intentions by authorities)
- Legal/regulatory requirements (compliance deadlines, mandated changes)
- Demographic certainties (population milestones, generational shifts)

For each Known Known, provide:
- The forecast itself (what WILL happen in the future)
- Timeline (specific FUTURE date or timeframe - must be after {current_date_str})
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
{{
  "known_knowns": [
    {{
      "forecast": "Clear description of the certain/near-certain forecast",
      "timeline": "Specific date or timeframe (e.g., 'November 2026', 'Q2 2026', '6 months')",
      "basis": "Why this is certain - cite specific evidence from articles",
      "impact": "How this affects the user's local/professional context"
    }}
  ],
  "known_unknowns": [
    {{
      "forecast": "Description of the evidence-based projection",
      "timeline": "Expected timeframe for resolution/occurrence",
      "evidence": "What data/trends support this projection",
      "possible_outcomes": ["outcome1", "outcome2", "outcome3"],
      "key_factors": ["factor1", "factor2"]
    }}
  ],
  "unknown_unknowns": [
    {{
      "forecast": "Description of the speculative forecast",
      "timeline": "Potential timeframe if it occurs",
      "weak_signal": "What early indicator suggests this possibility",
      "potential_impact": "Consequences if this materializes",
      "why_plausible": "Reasoning for why this deserves consideration"
    }}
  ],
  "data_sources_summary": "Brief summary of what data informed these forecasts"
}}
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

        # Validate Known Knowns have future timelines
        current_date = datetime.utcnow()
        known_knowns = forecast.get("known_knowns", [])
        valid_known_knowns = []

        for item in known_knowns:
            timeline = item.get("timeline", "")
            parsed_date = self._parse_timeline_to_date(timeline)

            if parsed_date and parsed_date < current_date:
                logger.warning(
                    f"Removing Known Known with past timeline: '{item.get('forecast', '')[:50]}...' "
                    f"(timeline: {timeline})"
                )
                continue

            valid_known_knowns.append(item)

        if len(valid_known_knowns) < len(known_knowns):
            logger.info(
                f"Filtered {len(known_knowns) - len(valid_known_knowns)} Known Knowns with past timelines"
            )

        forecast["known_knowns"] = valid_known_knowns

        logger.info("Forecast structure validation passed")

    def _parse_timeline_to_date(self, timeline: str) -> datetime | None:
        """
        Attempt to parse a timeline string into a date.

        Handles formats like:
        - "December 6, 2025" -> datetime(2025, 12, 6)
        - "December 6th, 2025" -> datetime(2025, 12, 6)
        - "November 2026" -> datetime(2026, 11, 1)
        - "Q2 2026" -> datetime(2026, 4, 1)
        - "Spring 2026" -> datetime(2026, 3, 1)
        - "6 months" -> now + 6 months
        - "2026" -> datetime(2026, 1, 1)

        Returns None if unparseable.
        """
        if not timeline:
            return None

        timeline_lower = timeline.strip().lower()
        now = datetime.utcnow()

        month_names = [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ]

        # Month Day, Year format: "December 6, 2025" or "December 6th, 2025"
        month_day_year = re.match(
            r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})",
            timeline_lower,
        )
        if month_day_year:
            month = month_names.index(month_day_year.group(1)) + 1
            day = int(month_day_year.group(2))
            year = int(month_day_year.group(3))
            return datetime(year, month, day)

        # Month Year format: "November 2026"
        month_year = re.match(
            r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
            timeline_lower,
        )
        if month_year:
            month = month_names.index(month_year.group(1)) + 1
            year = int(month_year.group(2))
            return datetime(year, month, 1)

        # Quarter format: "Q2 2026"
        quarter = re.match(r"q([1-4])\s+(\d{4})", timeline_lower)
        if quarter:
            q = int(quarter.group(1))
            year = int(quarter.group(2))
            month = (q - 1) * 3 + 1  # Q1=1, Q2=4, Q3=7, Q4=10
            return datetime(year, month, 1)

        # Season format: "Spring 2026"
        season = re.match(r"(spring|summer|fall|autumn|winter)\s+(\d{4})", timeline_lower)
        if season:
            season_months = {"spring": 3, "summer": 6, "fall": 9, "autumn": 9, "winter": 12}
            month = season_months[season.group(1)]
            year = int(season.group(2))
            return datetime(year, month, 1)

        # Year only: "2026"
        year_only = re.match(r"^(\d{4})$", timeline_lower)
        if year_only:
            return datetime(int(year_only.group(1)), 1, 1)

        # Relative: "6 months", "2 years", "3 weeks"
        relative = re.match(r"(\d+)\s+(month|year|week)s?", timeline_lower)
        if relative:
            num = int(relative.group(1))
            unit = relative.group(2)
            if unit == "month":
                return now + timedelta(days=num * 30)
            elif unit == "year":
                return now + timedelta(days=num * 365)
            elif unit == "week":
                return now + timedelta(weeks=num)

        return None
