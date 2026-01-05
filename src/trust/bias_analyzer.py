"""
Bias Analysis Module
Detect framing, assumptions, omissions, and loaded language using Claude
"""
import json
import logging
from typing import Any

from ..context.claude_client import ClaudeClient
from .trust_prompts import BIAS_FRAMING_PROMPT

logger = logging.getLogger(__name__)


class FramingIssue:
    """Represents a framing choice in the response"""

    def __init__(
        self,
        frame_type: str,
        text: str,
        effect: str,
        alternative: str
    ):
        """
        Initialize framing issue

        Args:
            frame_type: Description of the frame (e.g., "problem/solution")
            text: Specific text showing this frame
            effect: How this shapes interpretation
            alternative: Alternative neutral framing
        """
        self.frame_type = frame_type
        self.text = text
        self.effect = effect
        self.alternative = alternative

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "frame_type": self.frame_type,
            "text": self.text,
            "effect": self.effect,
            "alternative": self.alternative
        }


class Assumption:
    """Represents an implicit assumption in the response"""

    def __init__(
        self,
        assumption: str,
        basis: str,
        impact: str
    ):
        """
        Initialize assumption

        Args:
            assumption: The implicit assumption
            basis: Text that reveals this assumption
            impact: Why this matters
        """
        self.assumption = assumption
        self.basis = basis
        self.impact = impact

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "assumption": self.assumption,
            "basis": self.basis,
            "impact": self.impact
        }


class Omission:
    """Represents a missing perspective or consideration"""

    def __init__(
        self,
        missing_perspective: str,
        relevance: str,
        suggestion: str
    ):
        """
        Initialize omission

        Args:
            missing_perspective: What's not covered
            relevance: Why it matters
            suggestion: What should be added
        """
        self.missing_perspective = missing_perspective
        self.relevance = relevance
        self.suggestion = suggestion

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "missing_perspective": self.missing_perspective,
            "relevance": self.relevance,
            "suggestion": self.suggestion
        }


class LoadedTerm:
    """Represents emotionally or politically charged language"""

    def __init__(
        self,
        term: str,
        connotation: str,
        neutral_alternative: str
    ):
        """
        Initialize loaded term

        Args:
            term: The loaded word/phrase
            connotation: What it implies
            neutral_alternative: Better wording
        """
        self.term = term
        self.connotation = connotation
        self.neutral_alternative = neutral_alternative

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "term": self.term,
            "connotation": self.connotation,
            "neutral_alternative": self.neutral_alternative
        }


class BiasAnalysis:
    """Complete bias analysis results"""

    def __init__(
        self,
        framing_issues: list[FramingIssue],
        assumptions: list[Assumption],
        omissions: list[Omission],
        loaded_terms: list[LoadedTerm]
    ):
        """
        Initialize bias analysis results

        Args:
            framing_issues: List of framing issues
            assumptions: List of implicit assumptions
            omissions: List of missing perspectives
            loaded_terms: List of loaded language
        """
        self.framing_issues = framing_issues
        self.assumptions = assumptions
        self.omissions = omissions
        self.loaded_terms = loaded_terms

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "framing_issues": [f.to_dict() for f in self.framing_issues],
            "assumptions": [a.to_dict() for a in self.assumptions],
            "omissions": [o.to_dict() for o in self.omissions],
            "loaded_terms": [t.to_dict() for t in self.loaded_terms],
            "total_issues": len(self.framing_issues) + len(self.assumptions) + len(self.omissions) + len(self.loaded_terms)
        }


class BiasAnalyzer:
    """
    Detect framing, assumptions, omissions, and loaded language using Claude

    Uses Claude's understanding of rhetoric and persuasion to identify
    subtle biases that simple pattern matching would miss.
    """

    def __init__(self, client: ClaudeClient):
        """
        Initialize bias analyzer

        Args:
            client: ClaudeClient instance for API calls
        """
        self.client = client

    async def analyze(self, response: str) -> BiasAnalysis:
        """
        Complete bias analysis pipeline

        Args:
            response: The AI response to analyze

        Returns:
            BiasAnalysis object with all detected issues
        """
        logger.info("Starting bias analysis")

        # Single comprehensive analysis (more efficient than separate calls)
        prompt = BIAS_FRAMING_PROMPT.format(response=response)

        try:
            result = await self.client.analyze(
                system_prompt="You are a rhetorical analysis specialist. Identify framing effects, hidden assumptions, omissions, and loaded language with precision.",
                user_message=prompt,
                temperature=0.0  # Deterministic analysis
            )

            # Parse JSON response
            result_clean = self._clean_json_response(result)
            data = json.loads(result_clean)

            # Extract framing issues
            framing_issues = []
            for item in data.get("framing", []):
                framing_issues.append(FramingIssue(
                    frame_type=item.get("frame_type", ""),
                    text=item.get("text", ""),
                    effect=item.get("effect", ""),
                    alternative=item.get("alternative", "")
                ))

            # Extract assumptions
            assumptions = []
            for item in data.get("assumptions", []):
                assumptions.append(Assumption(
                    assumption=item.get("assumption", ""),
                    basis=item.get("basis", ""),
                    impact=item.get("impact", "")
                ))

            # Extract omissions
            omissions = []
            for item in data.get("omissions", []):
                omissions.append(Omission(
                    missing_perspective=item.get("missing_perspective", ""),
                    relevance=item.get("relevance", ""),
                    suggestion=item.get("suggestion", "")
                ))

            # Extract loaded terms
            loaded_terms = []
            for item in data.get("loaded_language", []):
                loaded_terms.append(LoadedTerm(
                    term=item.get("term", ""),
                    connotation=item.get("connotation", ""),
                    neutral_alternative=item.get("neutral_alternative", "")
                ))

            analysis = BiasAnalysis(
                framing_issues=framing_issues,
                assumptions=assumptions,
                omissions=omissions,
                loaded_terms=loaded_terms
            )

            logger.info(f"Bias analysis complete: {len(framing_issues)} framing, {len(assumptions)} assumptions, {len(omissions)} omissions, {len(loaded_terms)} loaded terms")
            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse bias analysis JSON: {e}")
            logger.error(f"Raw response: {result[:200]}...")
            # Return empty analysis on error
            return BiasAnalysis([], [], [], [])
        except Exception as e:
            logger.error(f"Bias analysis failed: {e}")
            return BiasAnalysis([], [], [], [])

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
            result = result[first_brace:last_brace + 1]

        return result.strip()
