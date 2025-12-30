"""
Fact Verification Module
Extract and verify factual claims using Claude
"""
import json
import logging
from typing import List, Dict, Any
from ..context.claude_client import ClaudeClient
from .trust_prompts import FACT_EXTRACTION_PROMPT, FACT_VERIFICATION_PROMPT

logger = logging.getLogger(__name__)


class Claim:
    """Represents a single claim extracted from response"""

    def __init__(
        self,
        text: str,
        claim_type: str,
        confidence: float = 0.5,
        reasoning: str = ""
    ):
        """
        Initialize claim

        Args:
            text: The claim text
            claim_type: FACT, INFERENCE, SPECULATION, or OPINION
            confidence: Confidence in the classification (0.0-1.0)
            reasoning: Explanation of the classification
        """
        self.text = text
        self.claim_type = claim_type.upper()
        self.confidence = confidence
        self.reasoning = reasoning

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "text": self.text,
            "type": self.claim_type,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }


class FactVerification:
    """Result of verifying a single claim"""

    def __init__(
        self,
        claim: Claim,
        verdict: str,
        confidence: float,
        reasoning: str,
        caveats: List[str] = None,
        contradictions: List[str] = None
    ):
        """
        Initialize verification result

        Args:
            claim: The claim being verified
            verdict: VERIFIED, CONTRADICTED, or UNVERIFIABLE
            confidence: Confidence in the verdict (0.0-1.0)
            reasoning: Explanation of the verdict
            caveats: List of caveats or additional context
            contradictions: List of contradicting information (if any)
        """
        self.claim = claim
        self.verdict = verdict.upper()
        self.confidence = confidence
        self.reasoning = reasoning
        self.caveats = caveats or []
        self.contradictions = contradictions or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "claim": self.claim.to_dict(),
            "verdict": self.verdict,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "caveats": self.caveats,
            "contradictions": self.contradictions
        }


class FactVerifier:
    """
    Extract and verify factual claims using Claude

    Uses Claude to:
    1. Extract discrete claims from response
    2. Classify each claim (FACT/INFERENCE/SPECULATION/OPINION)
    3. Verify factual claims against knowledge base
    """

    def __init__(self, client: ClaudeClient):
        """
        Initialize fact verifier

        Args:
            client: ClaudeClient instance for API calls
        """
        self.client = client

    async def verify(self, response: str) -> List[FactVerification]:
        """
        Complete fact verification pipeline

        Args:
            response: The AI response to verify

        Returns:
            List of FactVerification objects
        """
        logger.info("Starting fact verification")

        # Step 1: Extract and classify claims
        claims = await self._extract_claims(response)
        logger.info(f"Extracted {len(claims)} claims")

        # Step 2: Verify each claim
        verifications = []
        for claim in claims:
            verification = await self._verify_claim(claim)
            verifications.append(verification)

        logger.info(f"Verified {len(verifications)} claims")
        return verifications

    async def _extract_claims(self, response: str) -> List[Claim]:
        """
        Extract claims from response using Claude

        Args:
            response: The response to analyze

        Returns:
            List of Claim objects
        """
        prompt = FACT_EXTRACTION_PROMPT.format(response=response)

        try:
            result = await self.client.analyze(
                system_prompt="You are a claim extraction specialist. Extract and categorize factual claims from text with precision.",
                user_message=prompt,
                temperature=0.0  # Deterministic extraction
            )

            # Parse JSON response
            result_clean = self._clean_json_response(result)
            data = json.loads(result_clean)

            claims = []
            for claim_data in data.get("claims", []):
                claim = Claim(
                    text=claim_data.get("text", ""),
                    claim_type=claim_data.get("type", "UNKNOWN"),
                    confidence=claim_data.get("confidence", 0.5),
                    reasoning=claim_data.get("reasoning", "")
                )
                claims.append(claim)

            return claims

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse claim extraction JSON: {e}")
            logger.error(f"Raw response: {result[:200]}...")
            return []
        except Exception as e:
            logger.error(f"Claim extraction failed: {e}")
            return []

    async def _verify_claim(self, claim: Claim) -> FactVerification:
        """
        Verify a single claim using Claude

        Args:
            claim: Claim to verify

        Returns:
            FactVerification object
        """
        # Only verify FACT and INFERENCE claims
        # SPECULATION and OPINION are inherently unverifiable
        if claim.claim_type in ["SPECULATION", "OPINION"]:
            return FactVerification(
                claim=claim,
                verdict="UNVERIFIABLE",
                confidence=1.0,
                reasoning=f"Claim is {claim.claim_type.lower()} and cannot be factually verified",
                caveats=[],
                contradictions=[]
            )

        prompt = FACT_VERIFICATION_PROMPT.format(
            claim=claim.text,
            claim_type=claim.claim_type
        )

        try:
            result = await self.client.analyze(
                system_prompt="You are a fact verification specialist. Verify claims using your knowledge base with careful attention to accuracy.",
                user_message=prompt,
                temperature=0.0  # Deterministic verification
            )

            # Parse JSON
            result_clean = self._clean_json_response(result)
            data = json.loads(result_clean)

            return FactVerification(
                claim=claim,
                verdict=data.get("verdict", "UNVERIFIABLE"),
                confidence=data.get("confidence", 0.5),
                reasoning=data.get("reasoning", ""),
                caveats=data.get("caveats", []),
                contradictions=data.get("contradictions", [])
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse verification JSON: {e}")
            logger.error(f"Raw response: {result[:200]}...")
            return FactVerification(
                claim=claim,
                verdict="ERROR",
                confidence=0.0,
                reasoning=f"Verification failed: JSON parse error",
                caveats=[],
                contradictions=[]
            )
        except Exception as e:
            logger.error(f"Claim verification failed: {e}")
            return FactVerification(
                claim=claim,
                verdict="ERROR",
                confidence=0.0,
                reasoning=f"Verification failed: {str(e)}",
                caveats=[],
                contradictions=[]
            )

    def _clean_json_response(self, response: str) -> str:
        """
        Clean JSON response from Claude

        Sometimes Claude wraps JSON in markdown code blocks

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

        return result.strip()
