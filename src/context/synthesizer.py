"""
Narrative Synthesizer
Context-driven narrative generation using Claude
"""

import json
import logging
from datetime import datetime
from typing import Any

from ..config.settings import settings
from ..database.connection import get_db
from ..database.models import AnalysisRun, Article, ContextSnapshot, NarrativeSynthesis
from ..utils.profiler import profile
from .claude_client import ClaudeClient
from .curator import ContextCurator
from .reflection_engine import ReflectionEngine
from .semantic_memory import SemanticMemory

logger = logging.getLogger(__name__)


class NarrativeSynthesizer:
    """Generates narrative intelligence briefs using context engineering"""

    def __init__(self, topic_filters: dict | None = None):
        """
        Initialize narrative synthesizer

        Args:
            topic_filters: Optional topic/scope filters for article selection
        """
        self.topic_filters = topic_filters or {}
        self.curator = ContextCurator(topic_filters=self.topic_filters)
        self.client = ClaudeClient()
        self.reflection_engine = ReflectionEngine()

    async def synthesize(self, hours: int = 48, max_articles: int = 50) -> dict[str, Any]:
        """
        Generate narrative synthesis from recent articles

        Args:
            hours: Hours to look back for articles
            max_articles: Maximum articles to include in context

        Returns:
            Synthesis results dictionary
        """
        logger.info(f"Starting narrative synthesis for last {hours} hours")

        # Curate context
        context = await self.curator.curate_for_narrative_synthesis(hours, max_articles)

        if not context["articles"]:
            logger.warning("No articles available for synthesis")
            return {"articles_analyzed": 0, "synthesis_id": None, "status": "no_articles"}

        # Build synthesis task
        task = self._build_synthesis_task(len(context["articles"]))

        try:
            # Get Claude's analysis
            response = await self.client.analyze_with_context(
                context=context, task=task, temperature=1.0
            )

            # Parse structured output
            synthesis_data = self._parse_synthesis_response(response)

            # Store in database with context snapshot
            synthesis_id = self._store_synthesis(
                synthesis_data=synthesis_data,
                articles_count=len(context["articles"]),
                context=context,
            )

            logger.info(f"Narrative synthesis complete: {synthesis_id}")

            return {
                "articles_analyzed": len(context["articles"]),
                "synthesis_id": synthesis_id,
                "synthesis_data": synthesis_data,
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Narrative synthesis failed: {e}")
            return {
                "articles_analyzed": 0,
                "synthesis_id": None,
                "status": "error",
                "error": str(e),
            }

    async def synthesize_with_trust_verification(
        self, hours: int = 48, max_articles: int = 50, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Generate narrative synthesis with trust verification and citation requirements

        This method generates synthesis with inline citations, then verifies trustworthiness.
        If verification fails, it regenerates with progressively stricter prompts (max 3 attempts).

        Args:
            hours: Hours to look back for articles
            max_articles: Maximum articles to include in context
            max_retries: Maximum regeneration attempts (default: 3)

        Returns:
            Synthesis results dictionary with trust verification metadata
        """
        with profile("SYNTHESIS_TOTAL"):
            logger.info(
                f"Starting narrative synthesis with trust verification (max retries: {max_retries})"
            )

            # Curate context (NOTE: This already has profiling inside curator.py)
            context = await self.curator.curate_for_narrative_synthesis(hours, max_articles)

            if not context["articles"]:
                logger.warning("No articles available for synthesis")
                return {"articles_analyzed": 0, "synthesis_id": None, "status": "no_articles"}

            # Initialize trust pipeline
            from ..trust.trust_pipeline import TrustPipeline

            trust_pipeline = TrustPipeline()

            # Verification loop
            attempt = 0
            trust_passed = False
            synthesis_data = None
            verification_history = []

            while attempt < max_retries and not trust_passed:
                attempt += 1
                logger.info(f"Synthesis attempt {attempt}/{max_retries}")

                with profile(f"SYNTHESIS_ATTEMPT_{attempt}"):
                    try:
                        # Build citation-enhanced task
                        task = self._build_synthesis_task_with_citations(
                            context["articles"], len(context["articles"])
                        )

                        # Generate synthesis (progressively stricter)
                        with profile(f"CLAUDE_API_SYNTHESIS_ATTEMPT_{attempt}"):
                            if attempt == 1:
                                # First attempt: normal temperature
                                response = await self.client.analyze_with_context(
                                    context=context, task=task, temperature=1.0
                                )
                            else:
                                # Retry with stricter prompt and lower temperature
                                logger.info(
                                    f"Retry {attempt}: Using stricter constraints and temperature=0.7"
                                )
                                stricter_task = self._add_trust_constraints(
                                    task, verification_history
                                )
                                response = await self.client.analyze_with_context(
                                    context=context, task=stricter_task, temperature=0.7
                                )

                        # Parse synthesis
                        synthesis_data = self._parse_synthesis_response(response)

                        # Extract narrative text for verification
                        narrative_text = self._extract_narrative_for_verification(synthesis_data)

                        if not narrative_text:
                            logger.warning("No narrative text extracted for verification")
                            verification_history.append(
                                {
                                    "attempt": attempt,
                                    "passed": False,
                                    "error": "No narrative text extracted",
                                }
                            )
                            continue

                        # Verify trustworthiness (NOTE: This already has profiling inside trust_pipeline.py)
                        with profile(f"TRUST_VERIFICATION_ATTEMPT_{attempt}"):
                            logger.info(f"Verifying synthesis trustworthiness (attempt {attempt})")
                            trust_analysis = await trust_pipeline.analyze_response(
                                response=narrative_text,
                                verify_facts=True,
                                check_bias=True,
                                check_intimacy=True,
                            )

                        # Evaluate against thresholds
                        trust_passed = self._evaluate_trust_threshold(trust_analysis)

                        verification_history.append(
                            {"attempt": attempt, "passed": trust_passed, "analysis": trust_analysis}
                        )

                        if trust_passed:
                            logger.info(f"Trust verification passed on attempt {attempt}")
                            break
                        else:
                            logger.warning(f"Trust verification failed on attempt {attempt}")
                            # Log specific failures
                            facts = trust_analysis.get("facts", {})
                            bias = trust_analysis.get("bias", {})
                            intimacy = trust_analysis.get("intimacy", {})
                            logger.warning(
                                f"  Contradicted facts: {facts.get('contradicted_count', 0)}/{facts.get('total_claims', 0)}, "
                                f"Loaded language: {len(bias.get('loaded_language', []))}, "
                                f"High intimacy issues: {len([i for i in intimacy.get('issues', []) if i.get('severity') == 'HIGH'])}"
                            )

                    except Exception as e:
                        logger.error(f"Synthesis attempt {attempt} failed: {e}", exc_info=True)
                        verification_history.append(
                            {"attempt": attempt, "passed": False, "error": str(e)}
                        )

        # Handle outcome
        if not trust_passed:
            logger.error(f"Trust verification failed after {max_retries} attempts")
            logger.warning("Storing synthesis with trust_verification_warning flag")

            # Store the best attempt even if it failed verification
            # This allows the system to function while we tune thresholds
            if synthesis_data:
                synthesis_data["trust_verification"] = {
                    "passed": False,
                    "attempts": attempt,
                    "warning": f"Failed trust verification after {max_retries} attempts",
                    "final_analysis": verification_history[-1]["analysis"]
                    if verification_history
                    else {},
                    "verification_history": verification_history,
                }

                # Store with warning flag
                synthesis_id = self._store_synthesis(
                    synthesis_data=synthesis_data,
                    articles_count=len(context["articles"]),
                    context=context,
                )

                logger.warning(f"Synthesis stored with trust warning: {synthesis_id}")

                return {
                    "status": "success_with_warning",
                    "articles_analyzed": len(context["articles"]),
                    "synthesis_id": synthesis_id,
                    "synthesis_data": synthesis_data,
                    "trust_verification": {
                        "passed": False,
                        "attempts": attempt,
                        "warning": "Synthesis did not meet all trust thresholds",
                        "verification_history": verification_history,
                    },
                }
            else:
                # No synthesis data at all - complete failure
                return {
                    "status": "verification_failed",
                    "articles_analyzed": len(context["articles"]),
                    "verification_history": verification_history,
                    "error": f"Synthesis failed trust verification after {max_retries} attempts",
                }

        # Success: Add trust verification metadata to synthesis
        synthesis_data["trust_verification"] = {
            "passed": True,
            "attempts": attempt,
            "final_analysis": verification_history[-1]["analysis"] if verification_history else {},
        }

        # Store successful synthesis in database
        synthesis_id = self._store_synthesis(
            synthesis_data=synthesis_data, articles_count=len(context["articles"]), context=context
        )

        logger.info(f"Trust-verified synthesis complete: {synthesis_id} (attempts: {attempt})")

        return {
            "status": "success",
            "articles_analyzed": len(context["articles"]),
            "synthesis_id": synthesis_id,
            "synthesis_data": synthesis_data,
            "trust_verification": {
                "passed": True,
                "attempts": attempt,
                "verification_history": verification_history,
            },
        }

    async def synthesize_with_reflection(
        self, hours: int = 48, max_articles: int = 50, depth_threshold: float = 8.0
    ) -> dict[str, Any]:
        """
        Generate narrative synthesis with reflection loop for deeper analysis

        Args:
            hours: Hours to look back for articles
            max_articles: Maximum articles to include in context
            depth_threshold: Minimum depth score to skip refinement (0-10)

        Returns:
            Synthesis results dictionary with reflection metadata
        """
        logger.info(
            f"Starting narrative synthesis with reflection (depth threshold: {depth_threshold})"
        )

        # Check if reflection is enabled
        enable_reflection = getattr(settings, "enable_reflection", True)
        if not enable_reflection:
            logger.info("Reflection disabled in settings, using standard synthesis")
            return await self.synthesize(hours, max_articles)

        # Curate context
        context = await self.curator.curate_for_narrative_synthesis(hours, max_articles)

        if not context["articles"]:
            logger.warning("No articles available for synthesis")
            return {"articles_analyzed": 0, "synthesis_id": None, "status": "no_articles"}

        # Build synthesis task
        task = self._build_synthesis_task(len(context["articles"]))

        try:
            # STEP 1: Initial synthesis
            logger.info("Step 1: Generating initial synthesis")
            response = await self.client.analyze_with_context(
                context=context, task=task, temperature=1.0
            )

            # Parse structured output
            initial_synthesis = self._parse_synthesis_response(response)

            # STEP 2: Evaluate depth with reflection engine
            logger.info("Step 2: Evaluating synthesis depth")
            reflection = await self.reflection_engine.evaluate_depth(
                synthesis_data=initial_synthesis, context=context
            )

            logger.info(f"Initial depth score: {reflection.depth_score}/10")

            # Store reflection metadata
            initial_synthesis["reflection"] = {
                "initial_depth_score": reflection.depth_score,
                "dimension_scores": reflection.evaluation_metadata.get("dimension_scores", {}),
                "refinement_applied": False,
            }

            # STEP 3: Decide if refinement needed
            if reflection.depth_score >= depth_threshold:
                logger.info(
                    f"Depth score {reflection.depth_score} meets threshold {depth_threshold}, skipping refinement"
                )
                final_synthesis = initial_synthesis
            else:
                logger.info(
                    f"Depth score {reflection.depth_score} below threshold {depth_threshold}, refining analysis"
                )

                # Generate refinement prompt
                refinement_prompt = await self.reflection_engine.generate_refinement_prompt(
                    synthesis_data=initial_synthesis, reflection=reflection, context=context
                )

                # STEP 4: Regenerate with deeper focus
                logger.info("Step 4: Generating refined synthesis")
                # Build complete system prompt with all context
                complete_system_prompt = self._build_complete_refinement_system_prompt(context)
                refined_response = await self.client.analyze(
                    system_prompt=complete_system_prompt,
                    user_message=refinement_prompt,
                    temperature=1.0,
                )

                # Parse refined synthesis
                final_synthesis = self._parse_synthesis_response(refined_response)

                # Update reflection metadata
                final_synthesis["reflection"] = {
                    "initial_depth_score": reflection.depth_score,
                    "dimension_scores": reflection.evaluation_metadata.get("dimension_scores", {}),
                    "refinement_applied": True,
                    "shallow_areas_addressed": [
                        area.to_dict() for area in reflection.shallow_areas
                    ],
                    "recommendations_followed": reflection.recommendations,
                }

                logger.info("Refinement complete")

            # Store in database with context snapshot
            synthesis_id = self._store_synthesis(
                synthesis_data=final_synthesis,
                articles_count=len(context["articles"]),
                context=context,
            )

            logger.info(f"Narrative synthesis with reflection complete: {synthesis_id}")

            # Extract and store facts for semantic memory (if enabled)
            if synthesis_id and getattr(settings, "enable_semantic_memory", False):
                try:
                    logger.info("Extracting facts for semantic memory")
                    with get_db() as memory_session:
                        memory = SemanticMemory(memory_session)
                        facts = await memory.extract_facts_from_synthesis(
                            final_synthesis, synthesis_id
                        )
                        stored_count = memory.store_facts(facts)
                        logger.info(f"Stored {stored_count} facts in semantic memory")
                except Exception as e:
                    logger.error(f"Fact extraction failed (non-fatal): {e}")
                    # Don't fail synthesis if fact extraction fails

            return {
                "articles_analyzed": len(context["articles"]),
                "synthesis_id": synthesis_id,
                "synthesis_data": final_synthesis,
                "reflection_metadata": final_synthesis.get("reflection", {}),
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Narrative synthesis with reflection failed: {e}", exc_info=True)
            return {
                "articles_analyzed": 0,
                "synthesis_id": None,
                "status": "error",
                "error": str(e),
            }

    def _build_system_prompt(self, context: dict[str, Any]) -> str:
        """Build system prompt from context (mirrors ClaudeClient logic)"""
        parts = []

        # Add user profile context
        if "user_profile" in context:
            profile = context["user_profile"]
            parts.append("## User Context")
            parts.append(f"Location: {profile.get('location', 'Unknown')}")
            parts.append(
                f"Professional Domains: {', '.join(profile.get('professional_domains', []))}"
            )
            parts.append(f"Civic Interests: {', '.join(profile.get('civic_interests', []))}")
            parts.append("")

        # Add recent articles context (abbreviated for refinement)
        if "articles" in context:
            parts.append(f"## Context: {len(context['articles'])} articles analyzed")
            parts.append("(Full article content available in original synthesis)")
            parts.append("")

        # Add instructions
        if "instructions" in context:
            parts.append("## Core Instructions")
            parts.append(context["instructions"])
            parts.append("")

        return "\n".join(parts)

    def _build_complete_refinement_system_prompt(self, context: dict[str, Any]) -> str:
        """
        Build complete system prompt for refinement that includes both context and task specification
        This mirrors what analyze_with_context() does but allows custom refinement instructions
        """
        parts = []

        # Add all the context from _build_system_prompt
        if "user_profile" in context:
            profile = context["user_profile"]
            parts.append("## User Context")
            parts.append(f"Location: {profile.get('location', 'Unknown')}")
            parts.append(
                f"Professional Domains: {', '.join(profile.get('professional_domains', []))}"
            )
            parts.append(f"Civic Interests: {', '.join(profile.get('civic_interests', []))}")
            parts.append("")

        # Add decision context if present
        if context.get("decision_context"):
            parts.append("## Decision Context")
            parts.append(context["decision_context"])
            parts.append("")

        # Add anomaly analysis if present
        if context.get("anomaly_analysis"):
            parts.append("## Coverage Anomalies")
            parts.append(context["anomaly_analysis"])
            parts.append("")

        # Add recent articles context (full content like claude_client does)
        if "articles" in context:
            parts.append(f"## Recent Articles ({len(context['articles'])} total)")
            for i, article in enumerate(context["articles"], 1):
                parts.append(f"\n### Article {i}")
                parts.append(f"**Title:** {article.get('title', 'Untitled')}")
                parts.append(f"**Source:** {article.get('source', 'Unknown')}")
                if article.get("published_date"):
                    parts.append(f"**Date:** {article['published_date']}")
                if article.get("content"):
                    content = article["content"]
                    parts.append(f"**Content:** {content}")
                if article.get("entities"):
                    parts.append(f"**Entities:** {', '.join(article['entities'][:10])}")
            parts.append("")

        # Add historical memory if present
        if context.get("memory"):
            parts.append("## Historical Context")
            parts.append(context["memory"])
            parts.append("")

        # Add core instructions from perspective
        if "instructions" in context:
            parts.append("## Instructions")
            parts.append(context["instructions"])
            parts.append("")

        # Add synthesis task specification with JSON schema
        article_count = len(context.get("articles", []))
        parts.append(self._build_synthesis_task(article_count))

        return "\n".join(parts)

    def _build_synthesis_task(self, article_count: int) -> str:
        """Build synthesis task prompt"""
        return f"""Analyze the {article_count} articles provided and generate a structured intelligence brief.

## Analysis Requirements

### Trends: Extract Measurable Patterns
Format trends as: "[Subject] [direction] [quantifier if available]"
Examples:
- "Federal cybersecurity spending increasing 15% year-over-year"
- "Local school enrollment declining in northern suburbs"
- "Cloud infrastructure adoption accelerating among government contractors"

### Events: Identify Upcoming Priority Items (next 2-4 weeks)
Rank by impact level:
- CRITICAL: Immediate action needed or major decision point
- HIGH: Significant impact on work, family, or community
- MEDIUM: Notable but manageable
- LOW: Awareness only

### Predictions: Project Likely Developments (2-4 week horizon)
Use confidence score (0.0-1.0) to indicate how likely the prediction is to occur.

### Confidence Scores
Assign confidence scores (0.0-1.0) representing probability of occurrence:
- 0.9-1.0: Very likely to occur - multiple confirming sources, clear causal chain
- 0.7-0.89: Likely to occur - strong evidence, plausible mechanism
- 0.5-0.69: Moderate probability - some evidence, notable uncertainty
- 0.3-0.49: Low probability - limited evidence, speculative
- <0.3: Very unlikely - weak or contradictory evidence

## Output Structure

Return ONLY valid JSON with this exact structure:

{{
    "bottom_line": {{
        "summary": "2-3 sentence executive summary highlighting most important takeaways",
        "immediate_actions": ["action 1 if any", "action 2 if any"]
    }},
    "trends_and_patterns": {{
        "local": [
            {{
                "subject": "Specific trend subject",
                "direction": "increasing|decreasing|stable|emerging",
                "quantifier": "Specific measure if available, or qualitative indicator",
                "description": "Brief context",
                "confidence": 0.85
            }}
        ],
        "state_regional": [],
        "national": [],
        "global": [],
        "niche_field": []
    }},
    "priority_events": [
        {{
            "event": "What it is",
            "when": "Specific timeframe",
            "impact_level": "CRITICAL|HIGH|MEDIUM|LOW",
            "why_matters": "Clear explanation of impact",
            "recommended_action": "Specific action to consider",
            "confidence": 0.90
        }}
    ],
    "predictions_scenarios": {{
        "local_governance": [
            {{
                "prediction": "Specific predicted development",
                "confidence": 0.75,
                "timeframe": "2-4 weeks",
                "rationale": "Why this is likely to occur"
            }}
        ],
        "education": [],
        "niche_field": [],
        "economic_conditions": [],
        "infrastructure": []
    }},
    "metadata": {{
        "articles_analyzed": {article_count},
        "generated_at": "ISO timestamp"
    }}
}}

Note: Use "niche_field" for the user's professional domain (from context).
Return ONLY valid JSON, no markdown formatting or additional text."""

    def _build_synthesis_task_with_citations(self, articles: list, article_count: int) -> str:
        """
        Build synthesis task prompt with citation requirements

        Args:
            articles: List of article dictionaries with id, title, source, url, published_date
            article_count: Number of articles

        Returns:
            Enhanced synthesis task prompt requiring inline citations
        """
        # Create numbered article reference list
        article_refs = []
        citation_map = {}

        for i, article in enumerate(articles, 1):
            # Build reference line for prompt
            article_refs.append(
                f"[{i}] {article.get('title', 'Untitled')} - {article.get('source', 'Unknown')} "
                f"({article.get('published_date', 'No date')})"
            )

            # Build citation map entry (will be JSON-encoded properly)
            citation_map[str(i)] = {
                "article_id": article.get("id"),
                "title": article.get("title", "Untitled"),
                "source": article.get("source", "Unknown"),
                "url": article.get("url", ""),
            }

        article_ref_list = "\n".join(article_refs)
        # Properly JSON-encode the citation map with indentation
        citation_map_json = json.dumps(citation_map, indent=8)[1:-1].strip()  # Remove outer braces

        return f"""Analyze the {article_count} articles and generate a structured intelligence brief WITH INLINE CITATIONS.

## CRITICAL REQUIREMENT: Citation Discipline

For EVERY factual claim, quantifier, event, or specific assertion:
1. Include inline citation using this format: "claim^[1,3]" (article numbers from reference list below)
2. Only cite articles that DIRECTLY support the claim
3. Include an "article_citations" array in each JSON object listing the article numbers used
4. Multiple citations are separated by commas: "claim^[1,3,7]"

### Citation Examples:
- Bottom line: "Federal cybersecurity spending increased 15%^[1,3] due to new CISA mandates^[3,7]"
- Trend subject: "Local tech hiring^[1]"
- Trend quantifier: "23% year-over-year^[1,4]"
- Event: "City council vote on zoning reform^[2]"
- Prediction: "Zoning changes likely to pass^[2,5]"

### When to Cite:
- ALWAYS cite: Quantitative claims (numbers, percentages, statistics)
- ALWAYS cite: Specific events with dates/times
- ALWAYS cite: Direct quotes or paraphrased statements
- ALWAYS cite: Predictions based on specific sources
- DO NOT cite: Your own analytical conclusions or synthesis
- DO NOT cite: General knowledge or obvious facts

## Article Reference List
{article_ref_list}

## Analysis Requirements

### Trends: Extract Measurable Patterns
Format trends as: "[Subject^[citation]] [direction] [quantifier^[citation] if available]"
Examples:
- "Federal cybersecurity spending^[1] increasing 15% year-over-year^[1,3]"
- "Local school enrollment^[2] declining in northern suburbs^[2]"
- "Cloud infrastructure adoption^[5] accelerating among government contractors^[5,8]"

### Events: Identify Upcoming Priority Items (next 2-4 weeks)
Cite the source article for each event and its details.
Rank by impact level:
- CRITICAL: Immediate action needed or major decision point
- HIGH: Significant impact on work, family, or community
- MEDIUM: Notable but manageable
- LOW: Awareness only

### Predictions: Project Likely Developments (2-4 week horizon)
Cite the articles that provide evidence for each prediction.
Use confidence score (0.0-1.0) to indicate how likely the prediction is to occur.

### Confidence Scores
Assign confidence scores (0.0-1.0) representing probability of occurrence:
- 0.9-1.0: Very likely to occur - multiple confirming sources, clear causal chain
- 0.7-0.89: Likely to occur - strong evidence, plausible mechanism
- 0.5-0.69: Moderate probability - some evidence, notable uncertainty
- 0.3-0.49: Low probability - limited evidence, speculative
- <0.3: Very unlikely - weak or contradictory evidence

## Output Structure

Return ONLY valid JSON with this exact structure (including article_citations fields):

{{
    "bottom_line": {{
        "summary": "2-3 sentence executive summary with inline citations^[1,2]",
        "immediate_actions": ["action 1^[3] if any", "action 2^[5] if any"],
        "article_citations": [1, 2, 3, 5]
    }},
    "trends_and_patterns": {{
        "local": [
            {{
                "subject": "Specific trend subject^[1]",
                "direction": "increasing|decreasing|stable|emerging",
                "quantifier": "Specific measure^[1,4] if available, or qualitative indicator",
                "description": "Brief context^[1]",
                "confidence": 0.85,
                "article_citations": [1, 4]
            }}
        ],
        "state_regional": [],
        "national": [],
        "global": [],
        "niche_field": []
    }},
    "priority_events": [
        {{
            "event": "What it is^[2]",
            "when": "Specific timeframe^[2]",
            "impact_level": "CRITICAL|HIGH|MEDIUM|LOW",
            "why_matters": "Clear explanation of impact^[2,5]",
            "recommended_action": "Specific action to consider",
            "confidence": 0.90,
            "article_citations": [2, 5]
        }}
    ],
    "predictions_scenarios": {{
        "local_governance": [
            {{
                "prediction": "Specific predicted development^[2]",
                "confidence": 0.75,
                "timeframe": "2-4 weeks",
                "rationale": "Why this is likely to occur^[2,5]",
                "article_citations": [2, 5]
            }}
        ],
        "education": [],
        "niche_field": [],
        "economic_conditions": [],
        "infrastructure": []
    }},
    "metadata": {{
        "articles_analyzed": {article_count},
        "generated_at": "ISO timestamp",
        "citation_map": {{
{citation_map_json}
        }}
    }}
}}

IMPORTANT:
- Every quantitative claim MUST have a citation
- Every specific event/date MUST have a citation
- Every prediction MUST cite supporting evidence
- If a claim cannot be supported by the provided articles, do not include it
- Only include article numbers in article_citations that you actually cited in the text fields

Note: Use "niche_field" for the user's professional domain (from context).
Return ONLY valid JSON, no markdown formatting or additional text."""

    def _add_trust_constraints(self, task: str, verification_history: list) -> str:
        """
        Add stricter constraints to synthesis task based on previous verification failures

        Args:
            task: Original synthesis task prompt
            verification_history: List of previous verification attempts with analysis

        Returns:
            Enhanced task prompt with stricter trust constraints
        """
        constraints = ["\n## TRUST VERIFICATION REQUIREMENTS (STRICT)\n"]
        constraints.append(
            "Previous attempts failed trust verification. You MUST address these issues:\n"
        )

        # Analyze failure patterns from history
        fact_failures = sum(
            1
            for v in verification_history
            if v.get("analysis", {}).get("facts", {}).get("contradicted_count", 0) > 0
        )
        bias_failures = sum(
            1
            for v in verification_history
            if len(v.get("analysis", {}).get("bias", {}).get("loaded_language", [])) > 3
        )
        intimacy_failures = sum(
            1
            for v in verification_history
            if len(
                [
                    i
                    for i in v.get("analysis", {}).get("intimacy", {}).get("issues", [])
                    if i.get("severity") == "HIGH"
                ]
            )
            > 0
        )

        if fact_failures > 0:
            constraints.append(
                "\n### FACTUAL ACCURACY (CRITICAL):\n"
                "Previous attempts contained factual errors or unverified claims.\n"
                "- ONLY make claims that are DIRECTLY supported by the provided articles\n"
                "- Include citations ^[N] for EVERY factual assertion\n"
                "- Double-check all quantitative claims (numbers, percentages, statistics)\n"
                "- If you cannot find supporting evidence in the articles, DO NOT include the claim\n"
                "- Avoid speculation or inference beyond what articles explicitly state\n"
            )

        if bias_failures > 0:
            constraints.append(
                "\n### NEUTRAL FRAMING (CRITICAL):\n"
                "Previous attempts used biased or loaded language.\n"
                "- Use neutral, descriptive language only\n"
                "- Avoid emotionally charged words or value judgments\n"
                "- Present facts objectively without inserting opinion\n"
                "- When multiple perspectives exist, present them fairly\n"
                "- Avoid implicit assumptions or leading phrasing\n"
            )

        if intimacy_failures > 0:
            constraints.append(
                "\n### PROFESSIONAL TONE (CRITICAL):\n"
                "Previous attempts had inappropriate intimacy or tone issues.\n"
                "- Maintain professional, analytical distance\n"
                "- Do NOT make claims about user emotions or feelings\n"
                "- Do NOT use false empathy or overly familiar language\n"
                "- Focus on factual analysis, not relationship-building\n"
                "- Avoid anthropomorphization of institutions or abstract concepts\n"
            )

        # Add general strictness reminder
        constraints.append(
            "\n### VERIFICATION STANDARDS:\n"
            "This synthesis will be verified for:\n"
            "- Factual accuracy: Max 5% contradicted claims allowed\n"
            "- Bias: Max 3 instances of loaded language allowed\n"
            "- Tone: Zero high-severity intimacy issues allowed\n"
            "\nYou MUST meet these standards or the synthesis will be rejected.\n"
        )

        return task + "\n".join(constraints)

    def _extract_narrative_for_verification(self, synthesis_data: dict) -> str:
        """
        Extract narrative text from structured synthesis for trust verification

        Args:
            synthesis_data: Parsed synthesis JSON structure

        Returns:
            Combined narrative text for verification
        """
        parts = []

        # Extract bottom line summary
        bottom_line = synthesis_data.get("bottom_line", {})
        if summary := bottom_line.get("summary"):
            parts.append(summary)

        # Extract immediate actions
        if actions := bottom_line.get("immediate_actions"):
            parts.extend(actions)

        # Sample trends (3 per scope to keep verification efficient)
        trends = synthesis_data.get("trends_and_patterns", {})
        for scope in ["local", "state_regional", "national", "global", "niche_field"]:
            for trend in trends.get(scope, [])[:3]:
                trend_text = f"{trend.get('subject', '')} {trend.get('direction', '')} "
                if quantifier := trend.get("quantifier"):
                    trend_text += f"{quantifier} "
                if description := trend.get("description"):
                    trend_text += description
                parts.append(trend_text.strip())

        # Extract priority events (top 5)
        for event in synthesis_data.get("priority_events", [])[:5]:
            event_text = f"{event.get('event', '')} "
            if why_matters := event.get("why_matters"):
                event_text += f"{why_matters} "
            if action := event.get("recommended_action"):
                event_text += action
            parts.append(event_text.strip())

        # Sample predictions (2 per category)
        predictions = synthesis_data.get("predictions_scenarios", {})
        for category in [
            "local_governance",
            "education",
            "niche_field",
            "economic_conditions",
            "infrastructure",
        ]:
            for pred in predictions.get(category, [])[:2]:
                pred_text = f"{pred.get('prediction', '')} "
                if rationale := pred.get("rationale"):
                    pred_text += rationale
                parts.append(pred_text.strip())

        # Join with spaces and clean up
        narrative = " ".join(parts)
        return narrative.strip()

    def _evaluate_trust_threshold(self, trust_analysis: dict) -> bool:
        """
        Evaluate if trust analysis meets minimum thresholds

        Thresholds (from approved plan):
        - Max 5% contradicted facts
        - Max 3 instances of loaded language
        - Zero high-severity intimacy issues

        Args:
            trust_analysis: Trust analysis results from TrustPipeline

        Returns:
            True if all thresholds met, False otherwise
        """
        # Fact verification threshold
        facts = trust_analysis.get("facts", {})
        contradicted = facts.get("contradicted_count", 0)
        total_claims = facts.get("total_claims", 1)  # Avoid division by zero

        # Calculate contradicted ratio
        contradicted_ratio = contradicted / max(total_claims, 1)
        fact_pass = contradicted_ratio <= 0.05  # Max 5% contradicted

        logger.info(
            f"Fact verification: {contradicted}/{total_claims} contradicted ({contradicted_ratio:.1%}) - {'PASS' if fact_pass else 'FAIL'}"
        )

        # Bias threshold
        bias = trust_analysis.get("bias", {})
        loaded_language = bias.get("loaded_language", [])
        bias_pass = len(loaded_language) <= 3  # Max 3 instances

        logger.info(
            f"Bias check: {len(loaded_language)} loaded language instances - {'PASS' if bias_pass else 'FAIL'}"
        )

        # Intimacy/tone threshold
        intimacy = trust_analysis.get("intimacy", {})
        high_issues = [i for i in intimacy.get("issues", []) if i.get("severity") == "HIGH"]
        tone_pass = len(high_issues) == 0  # Zero high-severity issues

        logger.info(
            f"Tone check: {len(high_issues)} high-severity intimacy issues - {'PASS' if tone_pass else 'FAIL'}"
        )

        # All must pass
        overall_pass = fact_pass and bias_pass and tone_pass
        logger.info(f"Overall trust verification: {'PASS' if overall_pass else 'FAIL'}")

        return overall_pass

    def _parse_synthesis_response(self, response: str) -> dict[str, Any]:
        """Parse Claude's JSON response"""
        try:
            # Remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            synthesis_data = json.loads(response.strip())

            # Add timestamp if not present
            if "metadata" not in synthesis_data:
                synthesis_data["metadata"] = {}

            synthesis_data["metadata"]["generated_at"] = datetime.utcnow().isoformat()

            return synthesis_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse synthesis JSON: {e}")
            logger.debug(f"Response was: {response[:500]}...")

            # Return fallback structure matching new schema
            # Note: Provide user-friendly error message, not raw JSON
            return {
                "bottom_line": {
                    "summary": "Synthesis generation encountered an error. The AI response was incomplete or malformed. Please try regenerating the report.",
                    "immediate_actions": [],
                    "article_citations": [],
                },
                "trends_and_patterns": {
                    "local": [],
                    "state_regional": [],
                    "national": [],
                    "global": [],
                    "niche_field": [],
                },
                "priority_events": [],
                "predictions_scenarios": {
                    "local_governance": [],
                    "education": [],
                    "niche_field": [],
                    "economic_conditions": [],
                    "infrastructure": [],
                },
                "metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "parse_error": str(e),
                    "citation_map": {},
                },
            }

    def _store_synthesis(
        self,
        synthesis_data: dict[str, Any],
        articles_count: int,
        context: dict[str, Any] | None = None,
    ) -> int | None:
        """Store synthesis and context snapshot in database"""
        try:
            with get_db() as session:
                # Create analysis run with context metadata
                run = AnalysisRun(
                    run_type="narrative_synthesis",
                    status="completed",
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    articles_processed=articles_count,
                    context_token_count=self._estimate_tokens(context) if context else None,
                    claude_model="claude-sonnet-4-20250514",
                )
                session.add(run)
                session.flush()

                # Create context snapshot if context provided
                context_snapshot_id = None
                if context:
                    article_ids = [a.get("id") for a in context.get("articles", []) if "id" in a]

                    snapshot = ContextSnapshot(
                        synthesis_id=None,  # Will update after synthesis creation
                        article_ids=str(article_ids),  # Store as JSON string
                        context_size_tokens=self._estimate_tokens(context),
                        user_profile_hash=self._hash_profile(context.get("user_profile")),
                        historical_summaries=context.get("memory", ""),
                        instructions=context.get("instructions", ""),
                    )
                    session.add(snapshot)
                    session.flush()
                    context_snapshot_id = snapshot.id

                # Create narrative synthesis
                # Extract bottom line summary for executive_summary field
                bottom_line = synthesis_data.get("bottom_line", {})
                exec_summary = bottom_line.get("summary", "No summary available")

                synthesis = NarrativeSynthesis(
                    analysis_run_id=run.id,
                    context_snapshot_id=context_snapshot_id,
                    user_profile_version="1.0",
                    synthesis_data=synthesis_data,
                    executive_summary=exec_summary,
                    articles_analyzed=articles_count,
                    temporal_scope="local,state,national,global,niche",
                    generated_at=datetime.utcnow(),
                )
                session.add(synthesis)
                session.flush()

                # Update context snapshot with synthesis_id
                if context_snapshot_id:
                    session.query(ContextSnapshot).filter_by(id=context_snapshot_id).update(
                        {"synthesis_id": synthesis.id}
                    )

                # Update articles: mark as included in synthesis
                if context:
                    article_ids = [
                        int(a.get("id")) for a in context.get("articles", []) if a.get("id")
                    ]
                    if article_ids:
                        session.query(Article).filter(Article.id.in_(article_ids)).update(
                            {"last_included_in_synthesis": datetime.utcnow()},
                            synchronize_session=False,
                        )

                session.commit()

                logger.info(f"Stored narrative synthesis: {synthesis.id}")
                return synthesis.id

        except Exception as e:
            logger.error(f"Failed to store synthesis: {e}")
            return None

    def _estimate_tokens(self, context: dict[str, Any]) -> int:
        """Estimate token count for context (rough approximation)"""
        import json

        context_str = json.dumps(context)
        # Rough approximation: 1 token ≈ 4 characters
        return len(context_str) // 4

    def _hash_profile(self, profile: dict[str, Any] | None) -> str:
        """Hash user profile for tracking"""
        import hashlib
        import json

        if not profile:
            return "none"
        profile_str = json.dumps(profile, sort_keys=True)
        return hashlib.sha256(profile_str.encode()).hexdigest()
