"""
Trust Pipeline - Main Orchestrator
Coordinates trust-enhanced queries and analysis
"""
import logging
from typing import Optional, Dict, Any, List
from ..context.claude_client import ClaudeClient
from .trust_prompts import TRUST_ENHANCED_SYSTEM_PROMPT
from .fact_verifier import FactVerifier, FactVerification
from .bias_analyzer import BiasAnalyzer, BiasAnalysis
from .intimacy_detector import IntimacyDetector, IntimacyAnalysis

logger = logging.getLogger(__name__)


class TrustPipeline:
    """
    Main trust verification pipeline
    Coordinates input enhancement and output analysis

    Stage 2A: Core infrastructure only
    Stage 2B-2D: Will add fact verification, bias analysis, intimacy detection
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize trust pipeline

        Args:
            api_key: Optional Anthropic API key (defaults to settings)
        """
        self.client = ClaudeClient(api_key=api_key)
        self.fact_verifier = FactVerifier(self.client)
        self.bias_analyzer = BiasAnalyzer(self.client)
        self.intimacy_detector = IntimacyDetector(self.client)
        logger.info("Trust pipeline initialized")

    async def query_with_trust_constraints(
        self,
        user_query: str,
        temperature: float = 1.0
    ) -> str:
        """
        Query Claude with trust-building constraints

        This is the INPUT ENHANCEMENT phase - we inject constraints
        that counteract engagement model tendencies.

        Args:
            user_query: The user's question or request
            temperature: Sampling temperature (0-1)

        Returns:
            Claude's response with trust constraints applied
        """
        logger.info(f"Querying with trust constraints: {user_query[:100]}...")

        # Use trust-enhanced system prompt that counteracts engagement artifacts
        response = await self.client.analyze(
            system_prompt=TRUST_ENHANCED_SYSTEM_PROMPT,
            user_message=user_query,
            temperature=temperature
        )

        logger.info(f"Response received: {len(response)} characters")
        return response

    async def analyze_response(
        self,
        response: str,
        verify_facts: bool = True,
        check_bias: bool = True,
        check_intimacy: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze Claude response for trust issues

        This is the OUTPUT VERIFICATION phase - we use Claude to analyze
        its own response for engagement artifacts.

        Stage 2B: Fact verification implemented
        Stage 2C-2D: Bias and intimacy analysis (coming next)

        Args:
            response: Claude's response to analyze
            verify_facts: Whether to verify factual claims
            check_bias: Whether to analyze bias/framing
            check_intimacy: Whether to detect intimacy issues

        Returns:
            Dictionary with analysis results
        """
        logger.info("Starting trust analysis")

        analysis = {
            "analyzed": True,
            "response_length": len(response)
        }

        # Stage 2B: Fact Verification
        if verify_facts:
            logger.info("Running fact verification")
            fact_results = await self.fact_verifier.verify(response)
            analysis["facts"] = {
                "verifications": [v.to_dict() for v in fact_results],
                "total_claims": len(fact_results),
                "verified_count": sum(1 for v in fact_results if v.verdict == "VERIFIED"),
                "uncertain_count": sum(1 for v in fact_results if v.verdict == "UNVERIFIABLE"),
                "contradicted_count": sum(1 for v in fact_results if v.verdict == "CONTRADICTED"),
                "error_count": sum(1 for v in fact_results if v.verdict == "ERROR")
            }

        # Stage 2C: Bias Analysis
        if check_bias:
            logger.info("Running bias analysis")
            bias_results = await self.bias_analyzer.analyze(response)
            analysis["bias"] = bias_results.to_dict()
            analysis["bias"]["analyzed"] = True

        # Stage 2D: Intimacy Detection
        if check_intimacy:
            logger.info("Running intimacy detection")
            intimacy_results = await self.intimacy_detector.detect(response)
            analysis["intimacy"] = intimacy_results.to_dict()
            analysis["intimacy"]["analyzed"] = True

        return analysis

    async def run_full_pipeline(
        self,
        user_query: str,
        verify_response: bool = True,
        verify_facts: bool = True,
        check_bias: bool = True,
        check_intimacy: bool = True,
        temperature: float = 1.0
    ) -> Dict[str, Any]:
        """
        Run complete trust pipeline: enhanced query + analysis

        Args:
            user_query: The user's question
            verify_response: Whether to analyze the response (False = just get response)
            verify_facts: Whether to verify factual claims
            check_bias: Whether to analyze bias/framing
            check_intimacy: Whether to detect intimacy issues
            temperature: Sampling temperature

        Returns:
            Dictionary with:
                - original_query: User's query
                - response: Claude's response
                - analysis: Analysis results (if verify_response=True)
        """
        logger.info("Running full trust pipeline")

        # Phase 1: Get trust-enhanced response
        response = await self.query_with_trust_constraints(
            user_query=user_query,
            temperature=temperature
        )

        result = {
            "original_query": user_query,
            "response": response,
            "trust_enhanced": True
        }

        # Phase 2: Analyze response (if requested)
        if verify_response:
            analysis = await self.analyze_response(
                response=response,
                verify_facts=verify_facts,
                check_bias=check_bias,
                check_intimacy=check_intimacy
            )
            result["analysis"] = analysis

        return result
