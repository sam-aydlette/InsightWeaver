"""
Fact Verification Module
Extract and verify factual claims using Claude
"""
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from ..context.claude_client import ClaudeClient
from .trust_prompts import FACT_EXTRACTION_PROMPT, FACT_VERIFICATION_PROMPT
from .source_matcher import AuthoritativeSourceMatcher

logger = logging.getLogger(__name__)

# Time-sensitive keywords that indicate a fact might be outdated
TIME_SENSITIVE_KEYWORDS = [
    'current', 'currently', 'now', 'today', 'this year',
    'present', 'recent', 'latest', 'director', 'ceo', 'president',
    'leader', 'head of', 'chairman', 'minister', 'secretary',
    'serving', 'incumbent', 'reigning', '2024', '2025'
]


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
        contradictions: List[str] = None,
        temporal_check: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize verification result

        Args:
            claim: The claim being verified
            verdict: VERIFIED, CONTRADICTED, OUTDATED, or UNVERIFIABLE
            confidence: Confidence in the verdict (0.0-1.0)
            reasoning: Explanation of the verdict
            caveats: List of caveats or additional context
            contradictions: List of contradicting information (if any)
            temporal_check: Result of temporal verification (if performed)
        """
        self.claim = claim
        self.verdict = verdict.upper()
        self.confidence = confidence
        self.reasoning = reasoning
        self.caveats = caveats or []
        self.contradictions = contradictions or []
        self.temporal_check = temporal_check

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "claim": self.claim.to_dict(),
            "verdict": self.verdict,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "caveats": self.caveats,
            "contradictions": self.contradictions
        }
        if self.temporal_check:
            result["temporal_check"] = self.temporal_check
        return result


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
        self.source_matcher = AuthoritativeSourceMatcher()

    async def verify(self, response: str, skip_temporal_validation: bool = False) -> List[FactVerification]:
        """
        Complete fact verification pipeline

        Args:
            response: The AI response to verify
            skip_temporal_validation: Skip temporal validation (already done via fetch-first)

        Returns:
            List of FactVerification objects
        """
        logger.info("Starting fact verification")

        if skip_temporal_validation:
            logger.info("Temporal validation will be skipped (fetch-first already provided current data)")

        # Step 1: Extract and classify claims
        claims = await self._extract_claims(response)
        logger.info(f"Extracted {len(claims)} claims")

        # Step 2: Verify each claim
        verifications = []
        for claim in claims:
            verification = await self._verify_claim(claim, skip_temporal_validation=skip_temporal_validation)
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

    async def _verify_claim(self, claim: Claim, skip_temporal_validation: bool = False) -> FactVerification:
        """
        Verify a single claim using Claude

        Args:
            claim: Claim to verify
            skip_temporal_validation: Skip temporal validation (already done via fetch-first)

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

            verification = FactVerification(
                claim=claim,
                verdict=data.get("verdict", "UNVERIFIABLE"),
                confidence=data.get("confidence", 0.5),
                reasoning=data.get("reasoning", ""),
                caveats=data.get("caveats", []),
                contradictions=data.get("contradictions", [])
            )

            # Perform temporal verification for time-sensitive claims (unless already done via fetch-first)
            if not skip_temporal_validation:
                temporal_check = await self._check_temporal_validity(claim, verification)
                if temporal_check:
                    verification.temporal_check = temporal_check

                    # Update verdict if claim is outdated
                    if temporal_check.get("still_current") is False:
                        verification.verdict = "OUTDATED"
                        update_info = temporal_check.get("update_info", "")
                        verification.reasoning = f"{verification.reasoning}\n\nTEMPORAL CHECK: This claim is outdated as of {temporal_check['checked_date']}. {update_info}"
                        verification.confidence = temporal_check.get("confidence", 0.8)

            return verification

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

    def _is_time_sensitive(self, claim: Claim) -> bool:
        """
        Check if claim contains time-sensitive keywords

        Args:
            claim: Claim to check

        Returns:
            True if claim appears time-sensitive
        """
        text_lower = claim.text.lower()
        return any(keyword in text_lower for keyword in TIME_SENSITIVE_KEYWORDS)

    async def _check_temporal_validity(self, claim: Claim, verification: FactVerification) -> Optional[Dict[str, Any]]:
        """
        Check if a verified fact is still current as of today using authoritative sources

        Uses WebFetch to retrieve real-time information from curated authoritative sources
        (government sites, corporate pages, etc.) to verify claims beyond model knowledge cutoff.

        Args:
            claim: The claim being checked
            verification: Initial verification result

        Returns:
            Temporal check result with current_status, reasoning, and checked_date
        """
        # Only check if initially verified
        if verification.verdict != "VERIFIED":
            return None

        # Check if claim is time-sensitive
        if not self._is_time_sensitive(claim):
            return None

        current_date = datetime.now().strftime("%Y-%m-%d")

        # Try to find authoritative source for this claim
        source = self.source_matcher.find_source(claim.text)

        if source is None:
            # No authoritative source available - acknowledge limitation
            fallback = self.source_matcher.get_fallback_config()
            logger.info(f"No authoritative source for temporal check: {claim.text[:50]}...")

            return {
                "still_current": None,
                "confidence": 0.0,
                "reasoning": fallback.get('reason', 'No authoritative source available for verification beyond model knowledge cutoff (January 2025)'),
                "checked_date": current_date,
                "source": None,
                "method": "knowledge_cutoff_limitation"
            }

        # Use WebFetch to get current information from authoritative source
        try:
            logger.info(f"Fetching from authoritative source: {source['name']} ({source['url']})")

            # Import WebFetch here to avoid circular dependencies
            from ..utils.web_tools import web_fetch

            fetched_content = await web_fetch(
                url=source['url'],
                prompt=source['query_prompt']
            )

            # Now ask Claude to verify the claim against the fetched content
            verification_prompt = f"""You are verifying a time-sensitive factual claim against authoritative source information.

CLAIM TO VERIFY:
"{claim.text}"

CURRENT INFORMATION FROM AUTHORITATIVE SOURCE ({source['name']}):
{fetched_content}

TASK:
Compare the claim against the current information from the authoritative source.
Determine if the claim is still accurate as of today ({current_date}).

Respond with JSON in this exact format:
{{
    "still_current": true/false/null,
    "confidence": 0.0-1.0,
    "reasoning": "Detailed explanation of whether claim matches current information",
    "update_info": "If claim is outdated, provide the current/corrected information",
    "source_quote": "Relevant quote from the authoritative source that supports your conclusion"
}}

Notes:
- still_current: true if claim matches source, false if contradicted, null if source doesn't address this claim
- Be precise - even small discrepancies matter (e.g., titles, dates)
- Quote specific text from the source to support your conclusion
"""

            result = await self.client.analyze(
                system_prompt=f"You are a fact verification specialist comparing claims to authoritative source data. Today is {current_date}.",
                user_message=verification_prompt,
                temperature=0.0
            )

            result_clean = self._clean_json_response(result)
            data = json.loads(result_clean)

            data["checked_date"] = current_date
            data["source"] = source['name']
            data["source_url"] = source['url']
            data["method"] = "authoritative_source_webfetch"

            logger.info(f"Temporal verification complete: still_current={data.get('still_current')}")
            return data

        except Exception as e:
            logger.error(f"Temporal verification via WebFetch failed: {e}")
            return {
                "still_current": None,
                "confidence": 0.0,
                "reasoning": f"Temporal verification failed: Could not fetch from authoritative source ({str(e)})",
                "checked_date": current_date,
                "source": source['name'] if source else None,
                "method": "webfetch_error"
            }

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
