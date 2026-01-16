"""
Trust Pipeline - Main Orchestrator
Coordinates trust-enhanced queries and analysis
"""

import asyncio
import logging
from typing import Any

from ..context.claude_client import ClaudeClient
from ..utils.web_tools import web_fetch
from .bias_analyzer import BiasAnalyzer
from .fact_verifier import FactVerifier
from .intimacy_detector import IntimacyDetector
from .source_matcher import AuthoritativeSourceMatcher
from .trust_prompts import TRUST_ENHANCED_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class TrustPipeline:
    """
    Main trust verification pipeline
    Coordinates input enhancement and output analysis

    Stage 2A: Core infrastructure only
    Stage 2B-2D: Will add fact verification, bias analysis, intimacy detection
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize trust pipeline

        Args:
            api_key: Optional Anthropic API key (defaults to settings)
        """
        self.client = ClaudeClient(api_key=api_key)
        self.fact_verifier = FactVerifier(self.client)
        self.bias_analyzer = BiasAnalyzer(self.client)
        self.intimacy_detector = IntimacyDetector(self.client)
        self.source_matcher = AuthoritativeSourceMatcher(claude_client=self.client)
        logger.info("Trust pipeline initialized")

    async def query_with_trust_constraints(self, user_query: str, temperature: float = 1.0) -> str:
        """
        Query Claude with trust-building constraints

        This is the INPUT ENHANCEMENT phase with FETCH-FIRST for time-sensitive queries:
        1. Detect if query is time-sensitive
        2. If yes, fetch current information from authoritative sources
        3. Include fetched information in context
        4. Claude responds with current, accurate data

        Args:
            user_query: The user's question or request
            temperature: Sampling temperature (0-1)

        Returns:
            Claude's response with trust constraints applied
        """
        logger.info(f"Querying with trust constraints: {user_query[:100]}...")

        # FETCH-FIRST: Get current facts for time-sensitive queries
        current_facts = await self._fetch_current_facts_if_needed(user_query)

        # Enhance query with current facts if available
        if current_facts:
            enhanced_query = f"""CURRENT VERIFIED INFORMATION (fetched from authoritative sources today):
{current_facts}

USER QUERY:
{user_query}

Please answer the user's query using the current verified information provided above. Be explicit about using the fetched current data rather than your knowledge cutoff."""
            logger.info("Enhanced query with current facts from authoritative sources")
        else:
            enhanced_query = user_query

        # Use trust-enhanced system prompt that counteracts engagement artifacts
        response = await self.client.analyze(
            system_prompt=TRUST_ENHANCED_SYSTEM_PROMPT,
            user_message=enhanced_query,
            temperature=temperature,
        )

        logger.info(f"Response received: {len(response)} characters")
        return response

    async def analyze_response(
        self,
        response: str,
        verify_facts: bool = True,
        check_bias: bool = True,
        check_intimacy: bool = True,
        skip_temporal_validation: bool = False,
    ) -> dict[str, Any]:
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
            skip_temporal_validation: Skip temporal validation (already done via fetch-first)

        Returns:
            Dictionary with analysis results
        """
        logger.info("Starting trust analysis (parallel execution)")

        analysis = {"analyzed": True, "response_length": len(response)}

        # Queue all verification tasks for parallel execution
        tasks = {}
        task_keys = []

        if verify_facts:
            logger.info("Queuing fact verification")
            tasks["facts"] = self.fact_verifier.verify(
                response, skip_temporal_validation=skip_temporal_validation
            )
            task_keys.append("facts")

        if check_bias:
            logger.info("Queuing bias analysis")
            tasks["bias"] = self.bias_analyzer.analyze(response)
            task_keys.append("bias")

        if check_intimacy:
            logger.info("Queuing intimacy detection")
            tasks["intimacy"] = self.intimacy_detector.detect(response)
            task_keys.append("intimacy")

        # Execute all tasks concurrently
        if tasks:
            logger.info(f"Executing {len(tasks)} verification tasks in parallel")
            results = await asyncio.gather(
                *[tasks[key] for key in task_keys], return_exceptions=True
            )

            # Map results back and handle individual task failures gracefully
            for i, key in enumerate(task_keys):
                result = results[i]

                if isinstance(result, Exception):
                    logger.error(f"Task '{key}' failed with error: {result}")
                    analysis[key] = {"analyzed": False, "error": str(result)}
                elif key == "facts":
                    fact_results = result
                    analysis["facts"] = {
                        "verifications": [v.to_dict() for v in fact_results],
                        "total_claims": len(fact_results),
                        "verified_count": sum(1 for v in fact_results if v.verdict == "VERIFIED"),
                        "uncertain_count": sum(
                            1 for v in fact_results if v.verdict == "UNVERIFIABLE"
                        ),
                        "contradicted_count": sum(
                            1 for v in fact_results if v.verdict == "CONTRADICTED"
                        ),
                        "error_count": sum(1 for v in fact_results if v.verdict == "ERROR"),
                    }
                elif key == "bias":
                    bias_results = result
                    analysis["bias"] = bias_results.to_dict()
                    analysis["bias"]["analyzed"] = True
                elif key == "intimacy":
                    intimacy_results = result
                    analysis["intimacy"] = intimacy_results.to_dict()
                    analysis["intimacy"]["analyzed"] = True

        return analysis

    async def _analyze_query_for_time_sensitivity(self, query: str) -> dict[str, Any] | None:
        """
        Use Claude to intelligently analyze if query is time-sensitive

        Args:
            query: User's query

        Returns:
            Dict with analysis or None if not time-sensitive
            {
                "is_time_sensitive": bool,
                "facts_needed": ["specific fact 1", "specific fact 2"],
                "source_type": "government_leadership|corporate_leadership|economic_data|sports|etc",
                "reasoning": "explanation"
            }
        """
        analysis_prompt = f"""Analyze this user query to determine if it asks about CURRENT or RECENT information that changes over time.

USER QUERY: "{query}"

Determine:
1. Is this asking about current/recent facts (vs historical facts or non-factual topics)?
2. What specific current facts need to be verified?
3. What type of authoritative source would be appropriate?

Examples of TIME-SENSITIVE queries:
- "Who is the president?" (current position)
- "What is the unemployment rate?" (recent economic data)
- "Who is the starting forward for the Celtics?" (current roster)
- "Is the government shut down?" (current status)
- "Who is the CEO of Apple?" (current leadership)

Examples of NOT time-sensitive:
- "Who was the first president?" (historical, won't change)
- "What is Python?" (conceptual, not time-dependent)
- "How do I learn programming?" (advice, not factual)
- "Who won World War 2?" (historical fact)

Respond with JSON:
{{
    "is_time_sensitive": true/false,
    "facts_needed": ["specific fact to verify"] or [],
    "source_type": "government_leadership|corporate_leadership|economic_data|sports|legislative|military|academic|other|none",
    "reasoning": "brief explanation of why this is/isn't time-sensitive"
}}"""

        try:
            result = await self.client.analyze(
                system_prompt="You are a query classifier. Determine if queries ask about current, time-sensitive information.",
                user_message=analysis_prompt,
                temperature=0.0,
            )

            # Parse JSON response
            import json

            result_clean = result.strip()
            if result_clean.startswith("```json"):
                result_clean = result_clean[7:]
            elif result_clean.startswith("```"):
                result_clean = result_clean[3:]
            if result_clean.endswith("```"):
                result_clean = result_clean[:-3]
            result_clean = result_clean.strip()

            analysis = json.loads(result_clean)

            if analysis.get("is_time_sensitive"):
                logger.info(f"Query classified as time-sensitive: {analysis.get('reasoning')}")
                return analysis
            else:
                logger.info("Query not time-sensitive")
                return None

        except Exception as e:
            logger.error(f"Query analysis failed: {e}")
            # Fail safe - don't fetch if we can't analyze
            return None

    async def _fetch_current_facts_if_needed(self, query: str) -> str | None:
        """
        Intelligently fetch current facts from authoritative sources if query is time-sensitive

        Uses Claude to analyze the query first, then fetches from appropriate sources.

        Args:
            query: User's query

        Returns:
            Formatted string with current facts, or None if not needed
        """
        # Use Claude to intelligently analyze if query is time-sensitive
        analysis = await self._analyze_query_for_time_sensitivity(query)

        if analysis is None:
            logger.info("Query not time-sensitive, skipping fetch-first")
            return None

        logger.info(f"Time-sensitive query detected: {analysis.get('reasoning')}")

        # Construct a search string from the facts needed
        facts_needed = analysis.get("facts_needed", [])
        search_string = " ".join(facts_needed) if facts_needed else query

        # Find authoritative source for this query using intelligent Claude-based matching
        source = await self.source_matcher.find_source(search_string)

        if source is None:
            logger.info(
                f"No authoritative source found for source_type: {analysis.get('source_type')}"
            )
            logger.info("Continuing without fetch-first - will rely on post-verification")
            return None

        # Fetch current information from authoritative source
        try:
            logger.info(f"Fetching current information from: {source['name']}")

            # Use the specific facts needed for a more targeted query
            if facts_needed:
                fetch_prompt = (
                    f"{source['query_prompt']} Specifically focus on: {', '.join(facts_needed)}"
                )
            else:
                fetch_prompt = source["query_prompt"]

            fetched_content = await web_fetch(url=source["url"], prompt=fetch_prompt)

            # Format as current facts
            current_facts = f"""Source: {source["name"]} ({source["url"]})
Retrieved: Today
Facts verified: {", ".join(facts_needed) if facts_needed else "general current information"}

{fetched_content}"""

            logger.info("Successfully fetched current facts for query")
            return current_facts

        except Exception as e:
            logger.error(f"Fetch-first failed: {e}")
            # Don't fail the whole query, just continue without current facts
            return None

    async def run_full_pipeline(
        self,
        user_query: str,
        verify_response: bool = True,
        verify_facts: bool = True,
        check_bias: bool = True,
        check_intimacy: bool = True,
        temperature: float = 1.0,
    ) -> dict[str, Any]:
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

        # Check if query is time-sensitive (to determine if fetch-first will be used)
        query_analysis = await self._analyze_query_for_time_sensitivity(user_query)
        used_fetch_first = query_analysis is not None

        # Phase 1: Get trust-enhanced response (with fetch-first if time-sensitive)
        response = await self.query_with_trust_constraints(
            user_query=user_query, temperature=temperature
        )

        result = {
            "original_query": user_query,
            "response": response,
            "trust_enhanced": True,
            "used_fetch_first": used_fetch_first,
        }

        # Phase 2: Analyze response (if requested)
        if verify_response:
            # When fetch-first was used, skip fact verification entirely since we've already
            # verified facts by fetching from authoritative sources. Verifying against Claude's
            # knowledge cutoff would create false contradictions for current facts.
            # Still run bias and intimacy checks.
            analysis = await self.analyze_response(
                response=response,
                verify_facts=verify_facts
                and not used_fetch_first,  # Skip fact verification if fetch-first was used
                check_bias=check_bias,
                check_intimacy=check_intimacy,
                skip_temporal_validation=used_fetch_first,
            )
            result["analysis"] = analysis

        return result
