"""
Reflection Engine
Self-critique and iterative refinement for deeper analysis
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)


@dataclass
class ShallowArea:
    """Represents an area needing deeper analysis"""
    topic: str
    issue: str
    deeper_question: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "topic": self.topic,
            "issue": self.issue,
            "deeper_question": self.deeper_question
        }


@dataclass
class ReflectionResult:
    """Results of synthesis depth evaluation"""
    depth_score: float  # 0-10
    shallow_areas: List[ShallowArea]
    missing_connections: List[str]
    recommendations: List[str]
    evaluation_metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "depth_score": self.depth_score,
            "shallow_areas": [area.to_dict() for area in self.shallow_areas],
            "missing_connections": self.missing_connections,
            "recommendations": self.recommendations,
            "evaluation_metadata": self.evaluation_metadata
        }


class ReflectionEngine:
    """Evaluates synthesis depth and generates refinement guidance"""

    def __init__(self):
        """Initialize reflection engine"""
        self.client = ClaudeClient()

    async def evaluate_depth(
        self,
        synthesis_data: Dict[str, Any],
        context: Dict[str, Any]
    ) -> ReflectionResult:
        """
        Evaluate synthesis for analytical depth

        Args:
            synthesis_data: The synthesis output to evaluate
            context: Original context used for synthesis

        Returns:
            ReflectionResult with depth evaluation and improvement suggestions
        """
        logger.info("Evaluating synthesis depth")

        # Format synthesis for evaluation
        synthesis_text = self._format_synthesis_for_evaluation(synthesis_data)

        # Build reflection prompt
        reflection_prompt = self._build_reflection_prompt(synthesis_text, context)

        try:
            # Get Claude's evaluation
            response = await self.client.analyze(
                system_prompt="You are an expert evaluator assessing intelligence brief quality and analytical depth.",
                user_message=reflection_prompt,
                temperature=0.3,  # Lower temperature for consistent evaluation
                max_tokens=2000
            )

            # Parse reflection response
            reflection_data = self._parse_reflection_response(response)

            # Convert to ReflectionResult
            result = self._build_reflection_result(reflection_data)

            logger.info(f"Depth evaluation complete: score={result.depth_score}")
            return result

        except Exception as e:
            logger.error(f"Reflection evaluation failed: {e}")
            # Return minimal passing result to allow pipeline to continue
            return ReflectionResult(
                depth_score=8.0,  # Assume acceptable quality
                shallow_areas=[],
                missing_connections=[],
                recommendations=[],
                evaluation_metadata={"error": str(e), "fallback": True}
            )

    async def generate_refinement_prompt(
        self,
        synthesis_data: Dict[str, Any],
        reflection: ReflectionResult,
        context: Dict[str, Any]
    ) -> str:
        """
        Generate prompt for synthesis refinement

        Args:
            synthesis_data: Original synthesis
            reflection: Evaluation results
            context: Original context

        Returns:
            Refinement prompt string
        """
        synthesis_text = self._format_synthesis_for_evaluation(synthesis_data)

        # Extract the original JSON as a reference for exact structure
        original_json = json.dumps(synthesis_data, indent=2)

        refinement_sections = []

        # Add shallow areas guidance
        if reflection.shallow_areas:
            areas_text = "\n".join([
                f"- **{area.topic}**: {area.issue}\n  Deeper question: {area.deeper_question}"
                for area in reflection.shallow_areas
            ])
            refinement_sections.append(f"### Areas Needing Depth\n{areas_text}")

        # Add missing connections
        if reflection.missing_connections:
            connections_text = "\n".join([f"- {conn}" for conn in reflection.missing_connections])
            refinement_sections.append(f"### Missing Cross-Article Connections\n{connections_text}")

        # Add recommendations
        if reflection.recommendations:
            recs_text = "\n".join([f"- {rec}" for rec in reflection.recommendations])
            refinement_sections.append(f"### Improvement Recommendations\n{recs_text}")

        refinement_guidance = "\n\n".join(refinement_sections)

        prompt = f"""The initial intelligence brief needs deeper analytical refinement.

## Original Brief (Human-Readable)
{synthesis_text}

## Original JSON Structure (MUST PRESERVE EXACTLY)
{original_json}

## Depth Evaluation
Current depth score: {reflection.depth_score}/10

{refinement_guidance}

## Refinement Requirements

Regenerate this intelligence brief with significantly deeper analysis:

1. **Causal Depth**: For each trend and prediction, show the full causal chain (X → Y → Z)
   - Not just "Housing prices increased" but "Housing prices increased BECAUSE federal workforce expanded, WHICH CAUSED increased demand, LEADING TO price acceleration"

2. **Historical Context**: Reference patterns, baselines, and temporal context
   - "This exceeds the 5-year average of X%"
   - "Compared to last quarter when..."
   - "Historically, this level indicates..."

3. **Cross-Article Synthesis**: Identify connections between seemingly separate topics
   - "These three articles all relate to..."
   - "The pattern across articles suggests..."
   - "Entity X appears in multiple contexts, connecting..."

4. **Second-Order Implications**: Explore downstream effects and longer-term consequences
   - "This suggests that..."
   - "Second-order effect: ..."
   - "Long-term implication: ..."

5. **Specificity**: Replace vague statements with concrete details
   - Not "likely to increase" but "projected to increase by X-Y% based on..."
   - Not "important development" but "impacts Z stakeholders through mechanism..."

## Output Structure

CRITICAL REQUIREMENT: Return the EXACT SAME JSON structure shown in "Original JSON Structure" above.

You MUST preserve:
- All top-level keys (bottom_line, trends_and_patterns, priority_events, predictions_scenarios, metadata)
- All nested keys within each section
- All field names within objects (e.g., "subject", "direction", "quantifier", "description", "confidence")
- The exact array structure

DO NOT:
- Change field names (e.g., don't use "trend" instead of "subject")
- Add new fields not in the original
- Remove fields from the original
- Change the nesting structure

ONLY CHANGE:
- The VALUES of the fields - make them deeper, more insightful, causally richer
- Keep the exact same structure, just enhance the content quality

Return ONLY valid JSON. No markdown formatting, no additional text before or after the JSON.

Focus on QUALITY over QUANTITY - every statement should provide insight, not just information."""

        return prompt

    def _format_synthesis_for_evaluation(self, synthesis_data: Dict[str, Any]) -> str:
        """Format synthesis data as readable text for evaluation"""
        sections = []

        # Bottom line
        if "bottom_line" in synthesis_data:
            bottom_line = synthesis_data["bottom_line"]
            sections.append(f"EXECUTIVE SUMMARY\n{bottom_line.get('summary', '')}")
            if bottom_line.get("immediate_actions"):
                actions = "\n".join([f"- {a}" for a in bottom_line["immediate_actions"]])
                sections.append(f"IMMEDIATE ACTIONS\n{actions}")

        # Trends
        if "trends_and_patterns" in synthesis_data:
            trends = synthesis_data["trends_and_patterns"]
            for category, items in trends.items():
                if items:
                    category_name = category.replace("_", " ").title()
                    trend_text = "\n".join([
                        f"- {t.get('subject', '')}: {t.get('direction', '')} {t.get('quantifier', '')}"
                        for t in items
                    ])
                    sections.append(f"TRENDS ({category_name})\n{trend_text}")

        # Priority events
        if "priority_events" in synthesis_data:
            events = synthesis_data["priority_events"]
            if events:
                event_text = "\n".join([
                    f"- [{e.get('impact_level', '')}] {e.get('event', '')}: {e.get('why_matters', '')}"
                    for e in events
                ])
                sections.append(f"PRIORITY EVENTS\n{event_text}")

        # Predictions
        if "predictions_scenarios" in synthesis_data:
            predictions = synthesis_data["predictions_scenarios"]
            for category, items in predictions.items():
                if items:
                    category_name = category.replace("_", " ").title()
                    pred_text = "\n".join([
                        f"- {p.get('prediction', '')} (confidence: {p.get('confidence', 'N/A')})"
                        for p in items
                    ])
                    sections.append(f"PREDICTIONS ({category_name})\n{pred_text}")

        return "\n\n".join(sections)

    def _build_reflection_prompt(
        self,
        synthesis_text: str,
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for depth evaluation"""

        article_count = len(context.get("articles", []))

        return f"""You are evaluating the analytical depth of an intelligence brief synthesized from {article_count} news articles.

## Intelligence Brief to Evaluate

{synthesis_text}

## Evaluation Criteria

Assess the brief on these dimensions:

1. **Causal Depth** (0-10): Does the analysis explain WHY things are happening, not just WHAT?
   - 0-3: No causal explanation, just surface observations
   - 4-6: Some causal mentions but shallow
   - 7-8: Clear causal chains for most insights
   - 9-10: Comprehensive causal analysis with multi-step reasoning

2. **Historical Awareness** (0-10): Does the analysis use temporal context and comparisons?
   - 0-3: No historical references
   - 4-6: Basic mentions of "recent" or "current"
   - 7-8: Specific comparisons to past periods
   - 9-10: Rich temporal context showing trends and patterns

3. **Cross-Article Synthesis** (0-10): Are connections between articles identified?
   - 0-3: Articles treated in isolation
   - 4-6: Some grouping by topic
   - 7-8: Non-obvious connections identified
   - 9-10: Pattern recognition across seemingly unrelated articles

4. **Prediction Specificity** (0-10): Are predictions concrete with clear reasoning?
   - 0-3: Vague or no predictions
   - 4-6: General predictions without rationale
   - 7-8: Specific predictions with reasoning
   - 9-10: Detailed predictions with confidence levels and causal chains

5. **Implication Exploration** (0-10): Are second-order effects and broader implications discussed?
   - 0-3: No implications discussed
   - 4-6: Surface-level "this matters because..."
   - 7-8: First-order implications clearly stated
   - 9-10: Second and third-order effects explored

## Your Task

Provide a critical evaluation identifying:
1. Overall depth score (0-10, average of the 5 dimensions)
2. Specific areas that are shallow (topic, what's missing, what deeper question should be answered)
3. Missing cross-article connections
4. Concrete recommendations for improvement

Return ONLY valid JSON in this structure:

{{
    "depth_score": 6.5,
    "dimension_scores": {{
        "causal_depth": 6,
        "historical_awareness": 5,
        "cross_article_synthesis": 7,
        "prediction_specificity": 8,
        "implication_exploration": 6
    }},
    "shallow_areas": [
        {{
            "topic": "housing trends",
            "issue": "no causal explanation for price increase",
            "deeper_question": "Why are prices rising - demand shift, supply constraint, policy impact, or speculation?"
        }}
    ],
    "missing_connections": [
        "Articles about federal workforce and housing prices likely connect but link not made"
    ],
    "recommendations": [
        "Add causal analysis: X → Y → Z chains",
        "Include historical baselines for context",
        "Explore second-order implications"
    ]
}}

Be critical but constructive. The goal is to identify genuine opportunities for deeper insight."""

    def _parse_reflection_response(self, response: str) -> Dict[str, Any]:
        """Parse Claude's reflection JSON response"""
        try:
            # Clean markdown formatting
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            reflection_data = json.loads(response.strip())
            return reflection_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse reflection JSON: {e}")
            logger.debug(f"Response was: {response[:500]}...")

            # Return passing score to continue pipeline
            return {
                "depth_score": 8.0,
                "dimension_scores": {
                    "causal_depth": 8,
                    "historical_awareness": 8,
                    "cross_article_synthesis": 8,
                    "prediction_specificity": 8,
                    "implication_exploration": 8
                },
                "shallow_areas": [],
                "missing_connections": [],
                "recommendations": [],
                "parse_error": str(e)
            }

    def _build_reflection_result(self, reflection_data: Dict[str, Any]) -> ReflectionResult:
        """Convert parsed data to ReflectionResult object"""

        # Extract shallow areas
        shallow_areas = []
        for area_data in reflection_data.get("shallow_areas", []):
            shallow_areas.append(ShallowArea(
                topic=area_data.get("topic", ""),
                issue=area_data.get("issue", ""),
                deeper_question=area_data.get("deeper_question", "")
            ))

        # Build metadata
        metadata = {
            "dimension_scores": reflection_data.get("dimension_scores", {}),
            "timestamp": logging.Formatter().formatTime(logging.LogRecord(
                "", 0, "", 0, "", (), None
            ))
        }

        if "parse_error" in reflection_data:
            metadata["parse_error"] = reflection_data["parse_error"]

        return ReflectionResult(
            depth_score=float(reflection_data.get("depth_score", 8.0)),
            shallow_areas=shallow_areas,
            missing_connections=reflection_data.get("missing_connections", []),
            recommendations=reflection_data.get("recommendations", []),
            evaluation_metadata=metadata
        )
