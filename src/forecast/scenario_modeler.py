"""
Scenario Modeler
Generates detailed scenario branches from baseline forecast
Explores alternative futures beyond optimistic/baseline/pessimistic
"""

import logging
import json
from typing import Dict, Any, List, Optional

from ..context.claude_client import ClaudeClient

logger = logging.getLogger(__name__)


class ScenarioModeler:
    """
    Generates detailed scenario analysis for forecasts

    Takes a baseline forecast and generates:
    - Standard scenarios (optimistic/baseline/pessimistic)
    - Custom scenarios exploring specific uncertainties
    - Scenario comparison and divergence points
    """

    def __init__(self, claude_client: Optional[ClaudeClient] = None):
        """
        Initialize scenario modeler

        Args:
            claude_client: Optional ClaudeClient instance
        """
        self.client = claude_client or ClaudeClient()

    async def generate_scenarios(
        self,
        baseline_forecast: Dict[str, Any],
        context: Dict[str, Any],
        scenario_count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Generate scenario branches from baseline forecast

        Args:
            baseline_forecast: Base forecast data
            context: Context dictionary from ForecastContextCurator
            scenario_count: Number of scenarios to generate (default 3)

        Returns:
            List of scenario dictionaries
        """
        logger.info(f"Generating {scenario_count} scenarios...")

        # Build scenario generation task
        task = self._build_scenario_task(baseline_forecast, scenario_count)

        # Send to Claude
        try:
            response = await self.client.analyze_with_context(
                context=context,
                task=task,
                temperature=1.2  # Higher temperature for creative scenarios
            )

            # Parse JSON response
            scenarios = self._parse_scenario_response(response)

            logger.info(f"Successfully generated {len(scenarios)} scenarios")
            return scenarios

        except Exception as e:
            logger.error(f"Error generating scenarios: {e}")
            raise

    def _build_scenario_task(
        self,
        baseline_forecast: Dict[str, Any],
        scenario_count: int
    ) -> str:
        """
        Build scenario generation task prompt

        Args:
            baseline_forecast: Base forecast data
            scenario_count: Number of scenarios to generate

        Returns:
            Formatted task prompt
        """
        # Extract key uncertainties from baseline
        key_uncertainties = baseline_forecast.get('key_uncertainties', [])
        uncertainties_text = "\n".join(f"- {u}" for u in key_uncertainties)

        task = f"""Based on the baseline forecast provided, generate {scenario_count} distinct scenarios exploring how the future could unfold.

BASELINE FORECAST SUMMARY:
The baseline forecast identified these key uncertainties:
{uncertainties_text}

TASK:
Generate {scenario_count} plausible scenarios showing different paths forward.

If generating 3 scenarios (standard):
1. **Optimistic scenario**: Most favorable realistic outcomes
2. **Baseline scenario**: Most likely path based on current trends
3. **Pessimistic scenario**: Challenging but plausible outcomes

If generating more than 3 scenarios, include the standard 3 plus additional scenarios exploring specific uncertainties or divergence points.

For each scenario, provide:

1. **Type**: optimistic, baseline, pessimistic, or custom (e.g., "regulatory_shift")
2. **Name**: Descriptive scenario name (3-6 words)
3. **Plausibility**: Why this scenario is realistic given the data
4. **Narrative**: 2-3 paragraph description of how events unfold
5. **Key predictions**: Specific outcomes (list of 5-8 items)
6. **Critical assumptions**: What must be true for this scenario
7. **Trigger events**: Early signals this scenario is materializing
8. **Divergence points**: Where this scenario branches from others
9. **Timeframe**: When key events occur

REQUIREMENTS:
- Scenarios must be internally consistent
- Base scenarios on data from the context, not speculation
- Identify where scenarios diverge from each other
- Acknowledge uncertainties within each scenario
- Explain plausibility rather than assigning probabilities

Return ONLY valid JSON matching this structure:

```json
[
  {{
    "type": "optimistic",
    "name": "Accelerated Progress",
    "plausibility": "Why this scenario is realistic based on current trends...",
    "narrative": "Detailed 2-3 paragraph narrative...",
    "key_predictions": [
      "Specific outcome 1",
      "Specific outcome 2",
      "..."
    ],
    "critical_assumptions": [
      "Assumption 1",
      "Assumption 2"
    ],
    "trigger_events": [
      "Early signal 1",
      "Early signal 2"
    ],
    "divergence_points": [
      "Point where this diverges from baseline",
      "Key decision or event that splits paths"
    ],
    "timeframe": {{
      "early_indicators": "First 3 months",
      "key_developments": "Months 4-8",
      "outcomes_visible": "Months 9-12"
    }}
  }},
  {{
    "type": "baseline",
    "name": "Continuation of Trends",
    "plausibility": "Why this is the most likely path...",
    "narrative": "...",
    "key_predictions": [...],
    "critical_assumptions": [...],
    "trigger_events": [...],
    "divergence_points": [...],
    "timeframe": {{...}}
  }},
  {{
    "type": "pessimistic",
    "name": "Headwinds and Setbacks",
    "plausibility": "Why this scenario cannot be ruled out...",
    "narrative": "...",
    "key_predictions": [...],
    "critical_assumptions": [...],
    "trigger_events": [...],
    "divergence_points": [...],
    "timeframe": {{...}}
  }}
]
```

IMPORTANT:
- Return ONLY the JSON array
- Ground scenarios in the data provided
- Explain plausibility rather than assigning probabilities
- Be specific about divergence points and triggers
"""

        return task

    def _parse_scenario_response(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse Claude's scenario response

        Args:
            response: Raw response from Claude

        Returns:
            List of parsed scenarios

        Raises:
            ValueError: If response is not valid JSON
        """
        # Clean response
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
            scenarios = json.loads(response)

            if not isinstance(scenarios, list):
                raise ValueError("Response must be a JSON array of scenarios")

            return scenarios

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scenarios JSON: {e}")
            logger.error(f"Response was: {response[:500]}...")
            raise ValueError(f"Invalid JSON response from Claude: {e}")

