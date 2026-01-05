"""
Forecast Engine
Core forecasting logic implementing 5 analysis types for long-term trend prediction
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from ..context.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class ForecastEngine:
    """
    Generates long-term forecasts using comprehensive analysis types

    Implements 5 analysis methodologies:
    1. Trend Extrapolation - Project current trends forward
    2. Scenario Modeling - Generate optimistic/baseline/pessimistic scenarios
    3. Pattern Recognition - Identify cyclical patterns and historical parallels
    4. Causal Chain Analysis - Map cause→effect relationships over time
    5. Event Risk Categorization - Rumsfeld framework (known knowns/unknowns/unknown unknowns)
    """

    def __init__(self, claude_client: ClaudeClient | None = None):
        """
        Initialize forecast engine

        Args:
            claude_client: Optional ClaudeClient instance (creates new if not provided)
        """
        self.client = claude_client or ClaudeClient()

    async def generate_forecast(
        self,
        horizon: str,
        context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Generate comprehensive forecast for specified time horizon

        Args:
            horizon: Time horizon (e.g., "6mo", "1yr", "3yr", "5yr")
            context: Curated context from ForecastContextCurator

        Returns:
            Forecast data dictionary with all 5 analysis types
        """
        logger.info(f"Generating {horizon} forecast...")

        # Build comprehensive forecast task
        task = self._build_forecast_task(horizon)

        # Send to Claude
        try:
            response = await self.client.analyze_with_context(
                context=context,
                task=task,
                temperature=1.0
            )

            # Parse JSON response
            forecast = self._parse_forecast_response(response)

            # Validate structure
            self._validate_forecast_structure(forecast)

            # Add metadata
            forecast['time_horizon'] = horizon
            forecast['horizon_months'] = self._parse_horizon_to_months(horizon)
            forecast['generated_at'] = datetime.utcnow().isoformat()

            logger.info(f"Successfully generated {horizon} forecast")
            return forecast

        except Exception as e:
            logger.error(f"Error generating forecast: {e}")
            raise

    def _build_forecast_task(self, horizon: str) -> str:
        """
        Build comprehensive forecast task prompt requiring all 5 analysis types

        Args:
            horizon: Time horizon string

        Returns:
            Formatted task prompt
        """
        horizon_months = self._parse_horizon_to_months(horizon)
        target_date = datetime.now() + timedelta(days=horizon_months * 30)
        target_date_str = target_date.strftime("%B %Y")

        task = f"""Generate a comprehensive {horizon} forecast (target: {target_date_str}).

You MUST provide ALL 5 analysis types below in valid JSON format.

### 1. TREND EXTRAPOLATION
Identify 3-5 significant current trends and project their trajectory over the {horizon} time horizon.

For each trend, provide:
- Trend description and current state
- Projected trajectory and endpoint
- Key drivers and potential obstacles
- Uncertainties and limiting factors

### 2. SCENARIO MODELING
Generate 3 distinct scenarios (optimistic, baseline, pessimistic) for how the {horizon} period could unfold.

For each scenario:
- Scenario name and type
- Key predictions and outcomes
- Critical assumptions
- Early warning signals/triggers
- Plausibility reasoning (why this scenario is realistic)

### 3. PATTERN RECOGNITION
Identify historical patterns, cycles, or parallels that may repeat or inform the forecast.

Include:
- Cyclical patterns (if applicable)
- Historical parallels (similar past situations)
- Pattern evidence from the data
- Implications for the forecast period

### 4. CAUSAL CHAIN ANALYSIS
Map 2-4 causal chains showing how current causes will propagate through intermediate effects to final outcomes.

For each chain:
- Initial cause (current condition)
- Intermediate effects (sequential steps)
- Final outcome (endpoint at {horizon})
- Time to unfold (in months)
- Key uncertainties in the chain

### 5. EVENT RISK CATEGORIZATION (Rumsfeld Framework)
Categorize anticipated events and risks into three categories:

**Known Knowns** (scheduled/confirmed events):
- Elections, policy deadlines, demographic milestones, scheduled releases, etc.
- Include specific dates where known

**Known Unknowns** (recognized but uncertain events):
- Geopolitical tensions, market volatility, policy debates, pending decisions, etc.
- Describe the range of possible outcomes

**Unknown Unknowns** (unforeseeable risks):
- Potential black swans, weak signals, emergent phenomena
- Acknowledge these are speculative by nature

### OUTPUT FORMAT
Return ONLY valid JSON matching this structure:

```json
{{
  "trend_extrapolations": [
    {{
      "trend": "Description of trend",
      "current_state": "Current situation",
      "projected_trajectory": "How it will evolve",
      "projected_outcome": "Expected endpoint",
      "key_drivers": ["driver1", "driver2"],
      "obstacles": ["obstacle1", "obstacle2"],
      "uncertainties": ["uncertainty1", "uncertainty2"]
    }}
  ],
  "scenarios": [
    {{
      "type": "optimistic",
      "name": "Scenario name",
      "predictions": ["prediction1", "prediction2"],
      "key_assumptions": ["assumption1", "assumption2"],
      "trigger_events": ["signal1", "signal2"],
      "plausibility": "Why this scenario is realistic given the data"
    }},
    {{
      "type": "baseline",
      "name": "Most likely scenario",
      "predictions": ["prediction1", "prediction2"],
      "key_assumptions": ["assumption1"],
      "trigger_events": ["signal1"],
      "plausibility": "Why this is the baseline expectation"
    }},
    {{
      "type": "pessimistic",
      "name": "Downside scenario",
      "predictions": ["prediction1", "prediction2"],
      "key_assumptions": ["assumption1"],
      "trigger_events": ["signal1"],
      "plausibility": "Why this scenario cannot be ruled out"
    }}
  ],
  "historical_patterns": [
    {{
      "pattern_type": "cyclical or parallel",
      "pattern": "Description of pattern",
      "evidence": ["evidence1", "evidence2"],
      "historical_period": "When this occurred before",
      "implications": "What this means for the forecast"
    }}
  ],
  "causal_chains": [
    {{
      "chain_name": "Chain identifier",
      "initial_cause": "Starting condition",
      "intermediate_effects": ["effect1", "effect2", "effect3"],
      "final_outcome": "Ultimate result",
      "time_to_unfold_months": {horizon_months},
      "key_uncertainties": ["uncertainty1", "uncertainty2"]
    }}
  ],
  "event_risks": {{
    "known_knowns": [
      {{
        "event": "Scheduled event",
        "date": "Specific date if known, or timeframe",
        "impact": "Expected impact",
        "certainty_basis": "Why this is certain (e.g., 'announced by', 'legally required')"
      }}
    ],
    "known_unknowns": [
      {{
        "uncertainty": "Recognized risk",
        "possible_outcomes": ["outcome1", "outcome2"],
        "factors_affecting_outcome": ["factor1", "factor2"]
      }}
    ],
    "unknown_unknowns": [
      {{
        "weak_signal": "Speculative risk",
        "potential_impact": "Possible impact if occurs",
        "why_plausible": "Reasoning for considering this risk"
      }}
    ]
  }},
  "key_uncertainties": ["uncertainty1", "uncertainty2"],
  "data_limitations": ["limitation1", "limitation2"],
  "data_sources_summary": "Brief summary of what data informed this forecast"
}}
```

IMPORTANT:
- Return ONLY the JSON object, no explanatory text before or after
- Base analysis ONLY on the articles and data provided in context
- Be explicit about uncertainties - acknowledge what you don't know
- For Known Knowns, provide evidence/source for why it's certain
- For scenarios, explain plausibility rather than assigning probabilities
- Be specific and grounded - avoid generic predictions
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
        Validate that forecast contains all required analysis types

        Args:
            forecast: Parsed forecast dictionary

        Raises:
            ValueError: If required fields are missing
        """
        required_fields = [
            'trend_extrapolations',
            'scenarios',
            'historical_patterns',
            'causal_chains',
            'event_risks'
        ]

        missing_fields = [field for field in required_fields if field not in forecast]

        if missing_fields:
            raise ValueError(f"Forecast missing required fields: {missing_fields}")

        # Validate event_risks structure
        if 'event_risks' in forecast:
            event_risks = forecast['event_risks']
            required_categories = ['known_knowns', 'known_unknowns', 'unknown_unknowns']
            missing_categories = [cat for cat in required_categories if cat not in event_risks]
            if missing_categories:
                raise ValueError(f"Event risks missing categories: {missing_categories}")

        logger.info("Forecast structure validation passed")

    def _parse_horizon_to_months(self, horizon: str) -> int:
        """
        Parse horizon string to number of months

        Args:
            horizon: Horizon string (e.g., "6mo", "1yr", "18 months")

        Returns:
            Number of months
        """
        horizon = horizon.lower().strip()

        if 'mo' in horizon:
            return int(horizon.replace('mo', '').strip())
        elif 'yr' in horizon or 'year' in horizon:
            years = int(horizon.replace('yr', '').replace('year', '').replace('s', '').strip())
            return years * 12
        elif 'month' in horizon:
            return int(horizon.replace('months', '').replace('month', '').strip())
        else:
            # Try to parse as just a number (assume months)
            try:
                return int(horizon)
            except ValueError:
                logger.warning(f"Could not parse horizon '{horizon}', defaulting to 12 months")
                return 12
