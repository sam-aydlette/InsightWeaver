"""
Narrative Synthesizer
Context-driven narrative generation using Claude
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from .curator import ContextCurator
from .claude_client import ClaudeClient
from .reflection_engine import ReflectionEngine
from .semantic_memory import SemanticMemory
from ..database.connection import get_db
from ..database.models import NarrativeSynthesis, AnalysisRun, ContextSnapshot, Article
from ..config.settings import settings

logger = logging.getLogger(__name__)


class NarrativeSynthesizer:
    """Generates narrative intelligence briefs using context engineering"""

    def __init__(self):
        """Initialize narrative synthesizer"""
        self.curator = ContextCurator()
        self.client = ClaudeClient()
        self.reflection_engine = ReflectionEngine()

    async def synthesize(
        self,
        hours: int = 48,
        max_articles: int = 50
    ) -> Dict[str, Any]:
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
            return {
                "articles_analyzed": 0,
                "synthesis_id": None,
                "status": "no_articles"
            }

        # Build synthesis task
        task = self._build_synthesis_task(len(context["articles"]))

        try:
            # Get Claude's analysis
            response = await self.client.analyze_with_context(
                context=context,
                task=task,
                temperature=1.0
            )

            # Parse structured output
            synthesis_data = self._parse_synthesis_response(response)

            # Store in database with context snapshot
            synthesis_id = self._store_synthesis(
                synthesis_data=synthesis_data,
                articles_count=len(context["articles"]),
                context=context
            )

            logger.info(f"Narrative synthesis complete: {synthesis_id}")

            return {
                "articles_analyzed": len(context["articles"]),
                "synthesis_id": synthesis_id,
                "synthesis_data": synthesis_data,
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Narrative synthesis failed: {e}")
            return {
                "articles_analyzed": 0,
                "synthesis_id": None,
                "status": "error",
                "error": str(e)
            }

    async def synthesize_with_reflection(
        self,
        hours: int = 48,
        max_articles: int = 50,
        depth_threshold: float = 8.0
    ) -> Dict[str, Any]:
        """
        Generate narrative synthesis with reflection loop for deeper analysis

        Args:
            hours: Hours to look back for articles
            max_articles: Maximum articles to include in context
            depth_threshold: Minimum depth score to skip refinement (0-10)

        Returns:
            Synthesis results dictionary with reflection metadata
        """
        logger.info(f"Starting narrative synthesis with reflection (depth threshold: {depth_threshold})")

        # Check if reflection is enabled
        enable_reflection = getattr(settings, 'enable_reflection', True)
        if not enable_reflection:
            logger.info("Reflection disabled in settings, using standard synthesis")
            return await self.synthesize(hours, max_articles)

        # Curate context
        context = await self.curator.curate_for_narrative_synthesis(hours, max_articles)

        if not context["articles"]:
            logger.warning("No articles available for synthesis")
            return {
                "articles_analyzed": 0,
                "synthesis_id": None,
                "status": "no_articles"
            }

        # Build synthesis task
        task = self._build_synthesis_task(len(context["articles"]))

        try:
            # STEP 1: Initial synthesis
            logger.info("Step 1: Generating initial synthesis")
            response = await self.client.analyze_with_context(
                context=context,
                task=task,
                temperature=1.0
            )

            # Parse structured output
            initial_synthesis = self._parse_synthesis_response(response)

            # STEP 2: Evaluate depth with reflection engine
            logger.info("Step 2: Evaluating synthesis depth")
            reflection = await self.reflection_engine.evaluate_depth(
                synthesis_data=initial_synthesis,
                context=context
            )

            logger.info(f"Initial depth score: {reflection.depth_score}/10")

            # Store reflection metadata
            initial_synthesis["reflection"] = {
                "initial_depth_score": reflection.depth_score,
                "dimension_scores": reflection.evaluation_metadata.get("dimension_scores", {}),
                "refinement_applied": False
            }

            # STEP 3: Decide if refinement needed
            if reflection.depth_score >= depth_threshold:
                logger.info(f"Depth score {reflection.depth_score} meets threshold {depth_threshold}, skipping refinement")
                final_synthesis = initial_synthesis
            else:
                logger.info(f"Depth score {reflection.depth_score} below threshold {depth_threshold}, refining analysis")

                # Generate refinement prompt
                refinement_prompt = await self.reflection_engine.generate_refinement_prompt(
                    synthesis_data=initial_synthesis,
                    reflection=reflection,
                    context=context
                )

                # STEP 4: Regenerate with deeper focus
                logger.info("Step 4: Generating refined synthesis")
                # Build complete system prompt with all context
                complete_system_prompt = self._build_complete_refinement_system_prompt(context)
                refined_response = await self.client.analyze(
                    system_prompt=complete_system_prompt,
                    user_message=refinement_prompt,
                    temperature=1.0
                )

                # Parse refined synthesis
                final_synthesis = self._parse_synthesis_response(refined_response)

                # Update reflection metadata
                final_synthesis["reflection"] = {
                    "initial_depth_score": reflection.depth_score,
                    "dimension_scores": reflection.evaluation_metadata.get("dimension_scores", {}),
                    "refinement_applied": True,
                    "shallow_areas_addressed": [area.to_dict() for area in reflection.shallow_areas],
                    "recommendations_followed": reflection.recommendations
                }

                logger.info("Refinement complete")

            # Store in database with context snapshot
            synthesis_id = self._store_synthesis(
                synthesis_data=final_synthesis,
                articles_count=len(context["articles"]),
                context=context
            )

            logger.info(f"Narrative synthesis with reflection complete: {synthesis_id}")

            # Extract and store facts for semantic memory (if enabled)
            if synthesis_id and getattr(settings, 'enable_semantic_memory', False):
                try:
                    logger.info("Extracting facts for semantic memory")
                    with get_db() as memory_session:
                        memory = SemanticMemory(memory_session)
                        facts = await memory.extract_facts_from_synthesis(
                            final_synthesis,
                            synthesis_id
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
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Narrative synthesis with reflection failed: {e}", exc_info=True)
            return {
                "articles_analyzed": 0,
                "synthesis_id": None,
                "status": "error",
                "error": str(e)
            }

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt from context (mirrors ClaudeClient logic)"""
        parts = []

        # Add user profile context
        if "user_profile" in context:
            profile = context["user_profile"]
            parts.append(f"## User Context")
            parts.append(f"Location: {profile.get('location', 'Unknown')}")
            parts.append(f"Professional Domains: {', '.join(profile.get('professional_domains', []))}")
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

    def _build_complete_refinement_system_prompt(self, context: Dict[str, Any]) -> str:
        """
        Build complete system prompt for refinement that includes both context and task specification
        This mirrors what analyze_with_context() does but allows custom refinement instructions
        """
        parts = []

        # Add all the context from _build_system_prompt
        if "user_profile" in context:
            profile = context["user_profile"]
            parts.append(f"## User Context")
            parts.append(f"Location: {profile.get('location', 'Unknown')}")
            parts.append(f"Professional Domains: {', '.join(profile.get('professional_domains', []))}")
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
                if article.get('published_date'):
                    parts.append(f"**Date:** {article['published_date']}")
                if article.get('content'):
                    content = article['content']
                    parts.append(f"**Content:** {content}")
                if article.get('entities'):
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

    def _parse_synthesis_response(self, response: str) -> Dict[str, Any]:
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
            return {
                "bottom_line": {
                    "summary": response[:500] if len(response) > 500 else response,
                    "immediate_actions": []
                },
                "trends_and_patterns": {
                    "local": [],
                    "state_regional": [],
                    "national": [],
                    "global": [],
                    "niche_field": []
                },
                "priority_events": [],
                "predictions_scenarios": {
                    "local_governance": [],
                    "education": [],
                    "niche_field": [],
                    "economic_conditions": [],
                    "infrastructure": []
                },
                "metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "parse_error": str(e)
                }
            }

    def _store_synthesis(
        self,
        synthesis_data: Dict[str, Any],
        articles_count: int,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
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
                    claude_model="claude-sonnet-4-20250514"
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
                        instructions=context.get("instructions", "")
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
                    generated_at=datetime.utcnow()
                )
                session.add(synthesis)
                session.flush()

                # Update context snapshot with synthesis_id
                if context_snapshot_id:
                    session.query(ContextSnapshot).filter_by(id=context_snapshot_id).update({
                        "synthesis_id": synthesis.id
                    })

                # Update articles: mark as included in synthesis
                if context:
                    article_ids = [int(a.get("id")) for a in context.get("articles", []) if a.get("id")]
                    if article_ids:
                        session.query(Article).filter(Article.id.in_(article_ids)).update({
                            "last_included_in_synthesis": datetime.utcnow()
                        }, synchronize_session=False)

                session.commit()

                logger.info(f"Stored narrative synthesis: {synthesis.id}")
                return synthesis.id

        except Exception as e:
            logger.error(f"Failed to store synthesis: {e}")
            return None

    def _estimate_tokens(self, context: Dict[str, Any]) -> int:
        """Estimate token count for context (rough approximation)"""
        import json
        context_str = json.dumps(context)
        # Rough approximation: 1 token ≈ 4 characters
        return len(context_str) // 4

    def _hash_profile(self, profile: Optional[Dict[str, Any]]) -> str:
        """Hash user profile for tracking"""
        import hashlib
        import json
        if not profile:
            return "none"
        profile_str = json.dumps(profile, sort_keys=True)
        return hashlib.sha256(profile_str.encode()).hexdigest()
