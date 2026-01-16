"""
Intimacy Detection Module
Detect emotional claims, false empathy, and anthropomorphization using Claude
"""

import json
import logging
from typing import Any

from ..context.claude_client import ClaudeClient
from .trust_prompts import INTIMACY_DETECTION_PROMPT

logger = logging.getLogger(__name__)


class IntimacyIssue:
    """Represents an inappropriate intimacy or anthropomorphization issue"""

    def __init__(
        self,
        category: str,
        text: str,
        explanation: str,
        severity: str,
        professional_alternative: str,
    ):
        """
        Initialize intimacy issue

        Args:
            category: Type of issue (EMOTION, EMPATHY, ANTHROPOMORPHIZATION, FAMILIARITY)
            text: The exact problematic phrase
            explanation: Why this is inappropriate for an AI
            severity: Impact level (HIGH, MEDIUM, LOW)
            professional_alternative: Better way to say this
        """
        self.category = category.upper()
        self.text = text
        self.explanation = explanation
        self.severity = severity.upper()
        self.professional_alternative = professional_alternative

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "category": self.category,
            "text": self.text,
            "explanation": self.explanation,
            "severity": self.severity,
            "professional_alternative": self.professional_alternative,
        }


class IntimacyAnalysis:
    """Complete intimacy detection results"""

    def __init__(self, issues: list[IntimacyIssue], overall_tone: str, summary: str):
        """
        Initialize intimacy analysis results

        Args:
            issues: List of detected intimacy issues
            overall_tone: Overall tone assessment (PROFESSIONAL, FAMILIAR, INAPPROPRIATE)
            summary: Brief overall assessment
        """
        self.issues = issues
        self.overall_tone = overall_tone.upper()
        self.summary = summary

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "issues": [i.to_dict() for i in self.issues],
            "overall_tone": self.overall_tone,
            "summary": self.summary,
            "total_issues": len(self.issues),
            "high_severity_count": sum(1 for i in self.issues if i.severity == "HIGH"),
            "medium_severity_count": sum(1 for i in self.issues if i.severity == "MEDIUM"),
            "low_severity_count": sum(1 for i in self.issues if i.severity == "LOW"),
        }


class IntimacyDetector:
    """
    Detect emotional language and false rapport using Claude

    Uses Claude's understanding of tone and rhetoric to identify
    inappropriate anthropomorphization that would erode trust.
    """

    def __init__(self, client: ClaudeClient):
        """
        Initialize intimacy detector

        Args:
            client: ClaudeClient instance for API calls
        """
        self.client = client

    async def detect(self, response: str) -> IntimacyAnalysis:
        """
        Complete intimacy detection pipeline

        Args:
            response: The AI response to analyze

        Returns:
            IntimacyAnalysis object with all detected issues
        """
        logger.info("Starting intimacy detection")

        # Single comprehensive analysis
        prompt = INTIMACY_DETECTION_PROMPT.format(response=response)

        try:
            result = await self.client.analyze(
                system_prompt="You are a tone analysis specialist. Identify inappropriate anthropomorphization and emotional language with precision. Return ONLY valid JSON with properly escaped quotes in all string values.",
                user_message=prompt,
                temperature=0.0,  # Deterministic analysis
            )

            # Parse JSON response
            result_clean = self._clean_json_response(result)
            data = json.loads(result_clean)

            # Extract issues
            issues = []
            for item in data.get("issues", []):
                issues.append(
                    IntimacyIssue(
                        category=item.get("category", ""),
                        text=item.get("text", ""),
                        explanation=item.get("explanation", ""),
                        severity=item.get("severity", "LOW"),
                        professional_alternative=item.get("professional_alternative", ""),
                    )
                )

            analysis = IntimacyAnalysis(
                issues=issues,
                overall_tone=data.get("overall_tone", "PROFESSIONAL"),
                summary=data.get("summary", "No issues detected"),
            )

            logger.info(
                f"Intimacy detection complete: {len(issues)} issues ({analysis.overall_tone} tone)"
            )
            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intimacy detection JSON: {e}")
            logger.error(f"Raw response: {result[:200]}...")
            # Return empty analysis on error
            return IntimacyAnalysis([], "PROFESSIONAL", "Analysis failed")
        except Exception as e:
            logger.error(f"Intimacy detection failed: {e}")
            return IntimacyAnalysis([], "PROFESSIONAL", "Analysis failed")

    def _clean_json_response(self, response: str) -> str:
        """
        Clean JSON response from Claude

        Sometimes Claude wraps JSON in markdown code blocks or adds explanatory text

        Args:
            response: Raw response from Claude

        Returns:
            Cleaned JSON string
        """
        result = response.strip()

        # Remove markdown code blocks
        if result.startswith("```json"):
            result = result[7:]
        elif result.startswith("```"):
            result = result[3:]

        if result.endswith("```"):
            result = result[:-3]

        result = result.strip()

        # Extract JSON object: find first { and last }
        # This handles cases where Claude adds text before or after the JSON
        first_brace = result.find("{")
        last_brace = result.rfind("}")

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            result = result[first_brace : last_brace + 1]

        return result.strip()
