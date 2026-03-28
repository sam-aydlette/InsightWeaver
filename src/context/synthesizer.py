"""
Two-Pass Narrative Synthesizer

Pass 1: Cluster articles into topic groups.
Pass 2: For clusters with 3+ articles, produce examined situation narratives.
         For clusters with 1-2 articles, produce thin coverage summaries.
"""

import json
import logging
from datetime import datetime
from typing import Any

from ..database.connection import get_db
from ..database.models import (
    AnalysisRun,
    Article,
    ContextSnapshot,
    NarrativeSynthesis,
)
from ..prompts import load_analysis_rules
from ..prompts.synthesis import (
    CLUSTERING_PROMPT,
    SITUATION_SYNTHESIS_PROMPT,
    THIN_COVERAGE_PROMPT,
)
from ..utils.profiler import profile
from .claude_client import ClaudeClient
from .curator import ContextCurator
from .frame_manager import FrameManager

logger = logging.getLogger(__name__)

ANALYSIS_THRESHOLD = 2  # Minimum articles for full situation analysis


class NarrativeSynthesizer:
    """Two-pass situation-based narrative synthesizer."""

    def __init__(self, topic_filters: dict | None = None):
        self.topic_filters = topic_filters or {}
        self.curator = ContextCurator(topic_filters=self.topic_filters)
        self.client = ClaudeClient()
        self.analysis_rules = load_analysis_rules()
        self.frame_manager = FrameManager(self.client)

    async def synthesize(self, hours: int = 48, max_articles: int = 50) -> dict[str, Any]:
        """
        Two-pass synthesis: cluster articles, then analyze each situation.

        Returns:
            {
                "status": "success" | "no_articles" | "error",
                "articles_analyzed": int,
                "synthesis_id": int | None,
                "synthesis_data": {
                    "situations": [...],
                    "thin_coverage": [...],
                    "metadata": {...}
                }
            }
        """
        with profile("SYNTHESIS_TOTAL"):
            logger.info(f"Starting two-pass synthesis for last {hours} hours")

            # Curate context
            context = await self.curator.curate_for_narrative_synthesis(hours, max_articles)
            articles = context.get("articles", [])

            if not articles:
                logger.warning("No articles available for synthesis")
                return {"articles_analyzed": 0, "synthesis_id": None, "status": "no_articles"}

            try:
                # Pass 1: Cluster articles
                with profile("PASS_1_CLUSTERING"):
                    clusters = await self._cluster_articles(articles)

                if not clusters:
                    logger.error("Clustering returned no clusters")
                    return {
                        "articles_analyzed": len(articles),
                        "synthesis_id": None,
                        "status": "error",
                        "error": "Article clustering failed",
                    }

                logger.info(
                    f"Pass 1 complete: {len(clusters)} clusters from {len(articles)} articles"
                )

                # Split clusters by coverage threshold
                full_clusters = [c for c in clusters if len(c["article_ids"]) >= ANALYSIS_THRESHOLD]
                thin_clusters = [c for c in clusters if len(c["article_ids"]) < ANALYSIS_THRESHOLD]

                logger.info(
                    f"Full analysis: {len(full_clusters)} clusters | "
                    f"Thin coverage: {len(thin_clusters)} clusters"
                )

                # Build citation map from all articles
                citation_map = self._build_citation_map(articles)

                # Pass 2a: Full situation analysis for clusters with 3+ articles
                situations = []
                with profile("PASS_2_SITUATIONS"):
                    for cluster in full_clusters:
                        cluster_articles = [
                            a
                            for a in articles
                            if a.get("id") in cluster["article_ids"]
                            or articles.index(a) + 1 in cluster["article_ids"]
                        ]
                        if not cluster_articles:
                            cluster_articles = [
                                articles[i - 1]
                                for i in cluster["article_ids"]
                                if 0 < i <= len(articles)
                            ]

                        if not cluster_articles:
                            continue

                        # Check for known frames
                        frame_prompt_addition = ""
                        existing_cluster = self.frame_manager.find_matching_cluster(cluster)

                        if existing_cluster:
                            validated_frames = self.frame_manager.get_validated_frames(
                                existing_cluster.id
                            )
                            if validated_frames:
                                frame_prompt_addition = self.frame_manager.build_frame_aware_prompt(
                                    existing_cluster.name, validated_frames
                                )
                                logger.info(
                                    f"Injecting {len(validated_frames)} known frames "
                                    f"for '{cluster['title']}'"
                                )

                        # Run situation synthesis
                        situation = await self._analyze_situation(
                            cluster_articles,
                            cluster,
                            citation_map,
                            frame_prompt_addition=frame_prompt_addition,
                        )

                        if not situation:
                            continue

                        situations.append(situation)

                        # Frame discovery: if no known frames, discover them
                        if not existing_cluster:
                            try:
                                discovery = await self.frame_manager.discover_frames(
                                    cluster_articles, cluster
                                )
                                if discovery:
                                    self.frame_manager.store_discovered_frames(cluster, discovery)
                            except Exception as e:
                                logger.warning(
                                    f"Frame discovery failed for '{cluster['title']}': {e}"
                                )

                        # Update gap tracking for existing clusters
                        elif existing_cluster and situation.get("coverage_frame"):
                            absent = situation.get("coverage_frame", {}).get("de_emphasized", "")
                            if absent:
                                self.frame_manager.update_frame_gaps(existing_cluster.id, [absent])

                # Pass 2b: Thin coverage summaries
                thin_coverage = []
                if thin_clusters:
                    with profile("PASS_2_THIN"):
                        thin_coverage = await self._summarize_thin_clusters(thin_clusters, articles)

                # Assemble output
                synthesis_data = {
                    "situations": situations,
                    "thin_coverage": thin_coverage,
                    "metadata": {
                        "articles_analyzed": len(articles),
                        "clusters_total": len(clusters),
                        "clusters_analyzed": len(full_clusters),
                        "clusters_thin": len(thin_clusters),
                        "analysis_threshold": f"{ANALYSIS_THRESHOLD}+ articles",
                        "generated_at": datetime.utcnow().isoformat(),
                        "citation_map": citation_map,
                    },
                }

                # Store in database
                synthesis_id = self._store_synthesis(
                    synthesis_data=synthesis_data,
                    articles_count=len(articles),
                    context=context,
                )

                logger.info(
                    f"Synthesis complete: {synthesis_id} "
                    f"({len(situations)} situations, {len(thin_coverage)} thin)"
                )

                return {
                    "status": "success",
                    "articles_analyzed": len(articles),
                    "synthesis_id": synthesis_id,
                    "synthesis_data": synthesis_data,
                }

            except Exception as e:
                logger.error(f"Synthesis failed: {e}", exc_info=True)
                return {
                    "articles_analyzed": len(articles),
                    "synthesis_id": None,
                    "status": "error",
                    "error": str(e),
                }

    # =========================================================================
    # Pass 1: Clustering
    # =========================================================================

    async def _cluster_articles(self, articles: list[dict]) -> list[dict]:
        """
        Group articles into topic clusters using a lightweight Claude call.

        Returns list of {"title": str, "article_ids": [int], "keywords": [str]}
        """
        # Build article summaries for clustering (titles + first paragraph only)
        article_summaries = []
        for i, article in enumerate(articles, 1):
            title = article.get("title", "Untitled")
            content = article.get("content", article.get("description", ""))
            # First 200 chars of content for clustering
            snippet = content[:200].strip() if content else ""
            article_summaries.append(f"[{i}] {title}\n    {snippet}")

        articles_text = "\n\n".join(article_summaries)
        prompt = CLUSTERING_PROMPT.format(articles=articles_text)

        response = await self.client.analyze(
            system_prompt="You are a news article classifier. Group articles by topic.",
            user_message=prompt,
            temperature=0.0,
        )

        parsed = self._parse_json_response(response)
        return parsed.get("clusters", [])

    # =========================================================================
    # Pass 2a: Full situation analysis
    # =========================================================================

    async def _analyze_situation(
        self,
        cluster_articles: list[dict],
        cluster: dict,
        _citation_map: dict,
        frame_prompt_addition: str = "",
    ) -> dict | None:
        """
        Produce an examined narrative for a single situation cluster.

        Args:
            frame_prompt_addition: Optional FRAME_AWARE_SYNTHESIS_PROMPT to append.

        Returns the situation dict or None on failure.
        """
        # Build article reference list for this cluster
        article_refs = []
        for i, article in enumerate(cluster_articles, 1):
            title = article.get("title", "Untitled")
            source = article.get("source", "Unknown")
            date = article.get("published_date", "No date")
            article_refs.append(f"[{i}] {title} - {source} ({date})")

        article_ref_list = "\n".join(article_refs)

        prompt = SITUATION_SYNTHESIS_PROMPT.format(
            analysis_rules=self.analysis_rules,
            article_ref_list=article_ref_list,
        )

        # Inject frame-aware prompt if known frames exist
        if frame_prompt_addition:
            prompt = f"{prompt}\n\n{frame_prompt_addition}"

        # Build context with full article content for this cluster
        context = {
            "user_profile": self.curator._format_user_profile(),
            "articles": cluster_articles,
            "instructions": self.curator._get_synthesis_instructions(),
        }

        response = await self.client.analyze_with_context(
            context=context,
            task=prompt,
            temperature=1.0,
        )

        situation = self._parse_json_response(response)

        # Validate minimal structure
        if "title" not in situation and "narrative" not in situation:
            logger.warning(f"Situation analysis returned invalid structure for: {cluster['title']}")
            return None

        return situation

    # =========================================================================
    # Pass 2b: Thin coverage summaries
    # =========================================================================

    async def _summarize_thin_clusters(
        self, thin_clusters: list[dict], articles: list[dict]
    ) -> list[dict]:
        """Produce one-line summaries for clusters with insufficient coverage."""
        cluster_descriptions = []
        for cluster in thin_clusters:
            # Gather source names for this cluster
            sources = []
            for aid in cluster["article_ids"]:
                idx = aid - 1  # 1-indexed to 0-indexed
                if 0 <= idx < len(articles):
                    sources.append(articles[idx].get("source", "Unknown"))

            cluster_descriptions.append(
                f"- {cluster['title']} ({len(cluster['article_ids'])} articles, "
                f"sources: {', '.join(set(sources))})"
            )

        clusters_text = "\n".join(cluster_descriptions)
        prompt = THIN_COVERAGE_PROMPT.format(clusters=clusters_text)

        response = await self.client.analyze(
            system_prompt="You are summarizing news topics with thin coverage.",
            user_message=prompt,
            temperature=0.0,
        )

        parsed = self._parse_json_response(response)
        return parsed.get("thin_coverage", [])

    # =========================================================================
    # Utilities
    # =========================================================================

    def _build_citation_map(self, articles: list[dict]) -> dict:
        """Build authoritative citation map from articles."""
        citation_map = {}
        for i, article in enumerate(articles, 1):
            citation_map[str(i)] = {
                "article_id": article.get("id"),
                "title": article.get("title", "Untitled"),
                "source": article.get("source", "Unknown"),
                "url": article.get("url", ""),
            }
        return citation_map

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse Claude's JSON response, stripping markdown fences."""
        try:
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            return json.loads(response.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response was: {response[:500]}...")
            return {}

    def _store_synthesis(
        self,
        synthesis_data: dict[str, Any],
        articles_count: int,
        context: dict[str, Any] | None = None,
    ) -> int | None:
        """Store synthesis and context snapshot in database."""
        try:
            with get_db() as session:
                run = AnalysisRun(
                    run_type="situation_synthesis",
                    status="completed",
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow(),
                    articles_processed=articles_count,
                    context_token_count=self._estimate_tokens(context) if context else None,
                    claude_model="claude-sonnet-4-20250514",
                )
                session.add(run)
                session.flush()

                # Context snapshot
                context_snapshot_id = None
                if context:
                    article_ids = [a.get("id") for a in context.get("articles", []) if "id" in a]
                    snapshot = ContextSnapshot(
                        synthesis_id=None,
                        article_ids=str(article_ids),
                        context_size_tokens=self._estimate_tokens(context),
                        user_profile_hash=self._hash_profile(context.get("user_profile")),
                        historical_summaries=context.get("memory", ""),
                        instructions=context.get("instructions", ""),
                    )
                    session.add(snapshot)
                    session.flush()
                    context_snapshot_id = snapshot.id

                # Extract summary from first situation
                situations = synthesis_data.get("situations", [])
                if situations:
                    exec_summary = situations[0].get("title", "No summary available")
                else:
                    exec_summary = "No situations identified"

                synthesis = NarrativeSynthesis(
                    analysis_run_id=run.id,
                    context_snapshot_id=context_snapshot_id,
                    user_profile_version="1.0",
                    synthesis_data=synthesis_data,
                    executive_summary=exec_summary,
                    articles_analyzed=articles_count,
                    generated_at=datetime.utcnow(),
                )
                session.add(synthesis)
                session.flush()

                if context_snapshot_id:
                    session.query(ContextSnapshot).filter_by(id=context_snapshot_id).update(
                        {"synthesis_id": synthesis.id}
                    )

                # Mark articles as included
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
                logger.info(f"Stored synthesis: {synthesis.id}")
                return synthesis.id

        except Exception as e:
            logger.error(f"Failed to store synthesis: {e}")
            return None

    def _estimate_tokens(self, context: dict[str, Any]) -> int:
        """Rough token count estimate (1 token ~ 4 chars)."""
        return len(json.dumps(context)) // 4

    def _hash_profile(self, profile: dict[str, Any] | None) -> str:
        """Hash user profile for tracking."""
        import hashlib

        if not profile:
            return "none"
        profile_str = json.dumps(profile, sort_keys=True)
        return hashlib.sha256(profile_str.encode()).hexdigest()
