"""
Two-Pass Narrative Synthesizer

Pass 1: Cluster articles into topic groups.
Pass 2: For clusters with 3+ articles, produce examined situation narratives.
         For clusters with 1-2 articles, produce thin coverage summaries.
"""

import json
import logging
from typing import Any

from ..database.connection import get_db
from ..database.models import (
    AnalysisRun,
    Article,
    ContextSnapshot,
    DecisionEvidence,
    NarrativeSynthesis,
    Prediction,
    Question,
    QuestionSituation,
)
from ..prompts import load_analysis_rules
from ..prompts.synthesis import (
    CLUSTERING_PROMPT,
    SITUATION_SYNTHESIS_PROMPT,
    THIN_COVERAGE_PROMPT,
)
from ..utils import utcnow
from ..utils.profiler import profile
from ._json import parse_claude_json
from .claude_client import ClaudeClient
from .cross_cluster_reconciler import CrossClusterReconciler
from .curator import ContextCurator
from .decision_router import DecisionRouter
from .frame_manager import FrameManager
from .prediction_tracker import PredictionTracker
from .question_matcher import ProposedQuestion, QuestionMatcher

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
        self.question_matcher = QuestionMatcher()
        self.prediction_tracker = PredictionTracker()
        self.decision_router = DecisionRouter()
        self.cross_cluster_reconciler = CrossClusterReconciler()

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
                # Pre-pass: grade the open-prediction ledger against today's
                # coverage before any new analysis. This keeps the tool's own
                # forward-looking statements auditable.
                with profile("PREDICTION_CHECK"):
                    prediction_check = await self._check_predictions(articles)

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

                        # Frame discovery: if no known frames, discover them,
                        # then tag this cluster's articles against the result.
                        if not existing_cluster:
                            try:
                                discovery = await self.frame_manager.discover_frames(
                                    cluster_articles, cluster
                                )
                                if discovery:
                                    tc_id = self.frame_manager.store_discovered_frames(
                                        cluster, discovery
                                    )
                                    if tc_id:
                                        frames = self.frame_manager.get_cluster_frames(tc_id)
                                        await self.frame_manager.classify_articles_to_frames(
                                            cluster_articles, frames
                                        )
                            except Exception as e:
                                logger.warning(
                                    f"Frame discovery failed for '{cluster['title']}': {e}"
                                )

                        # Known frames: tag articles and update gap tracking.
                        elif existing_cluster:
                            try:
                                cluster_frames = self.frame_manager.get_cluster_frames(
                                    existing_cluster.id
                                )
                                if cluster_frames:
                                    await self.frame_manager.classify_articles_to_frames(
                                        cluster_articles, cluster_frames
                                    )
                            except Exception as e:
                                logger.warning(
                                    f"Frame classification failed for '{cluster['title']}': {e}"
                                )

                            if situation.get("coverage_frame"):
                                absent = situation.get("coverage_frame", {}).get(
                                    "de_emphasized", ""
                                )
                                if absent:
                                    self.frame_manager.update_frame_gaps(
                                        existing_cluster.id, [absent]
                                    )

                # Pass 2b: Thin coverage summaries
                thin_coverage = []
                if thin_clusters:
                    with profile("PASS_2_THIN"):
                        thin_coverage = await self._summarize_thin_clusters(thin_clusters, articles)

                # Pass 3: look across situations for meta-fractures (one
                # underlying frame conflict surfacing in multiple topical
                # guises). Empty result is the common case; we skip silently.
                meta_fractures = []
                if situations:
                    with profile("PASS_3_RECONCILE"):
                        try:
                            meta_fractures = await self.cross_cluster_reconciler.reconcile(
                                situations
                            )
                        except Exception as e:
                            logger.warning(f"Cross-cluster reconciliation failed: {e}")

                # Assemble output
                synthesis_data = {
                    "situations": situations,
                    "thin_coverage": thin_coverage,
                    "meta_fractures": meta_fractures,
                    "metadata": {
                        "articles_analyzed": len(articles),
                        "clusters_total": len(clusters),
                        "clusters_analyzed": len(full_clusters),
                        "clusters_thin": len(thin_clusters),
                        "analysis_threshold": f"{ANALYSIS_THRESHOLD}+ articles",
                        "generated_at": utcnow().isoformat(),
                        "citation_map": citation_map,
                        "prediction_check": prediction_check,
                    },
                }

                # Store in database (also resolves Questions and writes joins)
                synthesis_id = await self._store_synthesis(
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

        parsed = parse_claude_json(response, label="clustering response")
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

        situation = parse_claude_json(response, label="situation analysis response")

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

        parsed = parse_claude_json(response, label="thin coverage response")
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

    async def _store_synthesis(
        self,
        synthesis_data: dict[str, Any],
        articles_count: int,
        context: dict[str, Any] | None = None,
    ) -> int | None:
        """Store synthesis, resolve Questions, and write join rows in one txn."""
        try:
            with get_db() as session:
                run = AnalysisRun(
                    run_type="situation_synthesis",
                    status="completed",
                    started_at=utcnow(),
                    completed_at=utcnow(),
                    articles_processed=articles_count,
                    context_token_count=self._estimate_tokens(context) if context else None,
                    claude_model="claude-sonnet-4-20250514",
                )
                session.add(run)
                session.flush()

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

                # Resolve Questions against persistent graph, then enrich
                # synthesis_data with question identity metadata so the
                # formatter can render Q-id prefixes without DB access.
                situations = synthesis_data.get("situations", [])
                question_plan = self._collect_proposed_questions(situations)
                if question_plan:
                    proposed = [pq for _, _, pq in question_plan]
                    resolved = await self.question_matcher.resolve_questions(proposed, session)
                    self._enrich_situations_with_questions(situations, question_plan, resolved)
                else:
                    resolved = []

                # Route situation evidence into open decision factors. Done
                # before the synthesis row write so the routing summary lands
                # in the stored synthesis_data blob.
                routed_evidence = await self.decision_router.route_evidence(situations, session)
                synthesis_data.setdefault("metadata", {})["decision_routing"] = (
                    self._build_decision_summary(routed_evidence, session)
                )

                exec_summary = (
                    situations[0].get("title", "No summary available")
                    if situations
                    else "No situations identified"
                )

                synthesis = NarrativeSynthesis(
                    analysis_run_id=run.id,
                    context_snapshot_id=context_snapshot_id,
                    user_profile_version="1.0",
                    synthesis_data=synthesis_data,
                    executive_summary=exec_summary,
                    articles_analyzed=articles_count,
                    generated_at=utcnow(),
                )
                session.add(synthesis)
                session.flush()

                if context_snapshot_id:
                    session.query(ContextSnapshot).filter_by(id=context_snapshot_id).update(
                        {"synthesis_id": synthesis.id}
                    )

                # Write QuestionSituation join rows now that we have synthesis.id.
                primary_question_by_situation: dict[int, Question] = {}
                for (sit_idx, slot, _pq), q in zip(question_plan, resolved, strict=True):
                    session.add(
                        QuestionSituation(
                            question_id=q.id,
                            synthesis_id=synthesis.id,
                            situation_index=sit_idx,
                        )
                    )
                    if slot == "primary":
                        primary_question_by_situation[sit_idx] = q

                # Persist this run's what_to_watch observables as Predictions,
                # each keyed to its situation's primary Question.
                for sit_idx, observable, trigger in self._collect_predictions(situations):
                    question = primary_question_by_situation.get(sit_idx)
                    if question is None:
                        continue
                    session.add(
                        Prediction(
                            question_id=question.id,
                            observable_text=observable,
                            trigger_condition=trigger,
                            made_in_synthesis_id=synthesis.id,
                        )
                    )

                # Persist routed decision evidence, attaching synthesis_id and
                # the situation's primary Question.
                for routed in routed_evidence:
                    primary_q = primary_question_by_situation.get(routed.situation_index)
                    session.add(
                        DecisionEvidence(
                            decision_id=routed.decision_id,
                            factor_id=routed.factor_id,
                            synthesis_id=synthesis.id,
                            question_id=primary_q.id if primary_q else None,
                            situation_excerpt=routed.excerpt,
                            direction=routed.direction,
                            epistemic_status=routed.epistemic_status,
                        )
                    )

                if context:
                    article_ids = [
                        int(a.get("id")) for a in context.get("articles", []) if a.get("id")
                    ]
                    if article_ids:
                        session.query(Article).filter(Article.id.in_(article_ids)).update(
                            {"last_included_in_synthesis": utcnow()},
                            synchronize_session=False,
                        )

                session.commit()
                logger.info(f"Stored synthesis: {synthesis.id}")
                return synthesis.id

        except Exception as e:
            logger.error(f"Failed to store synthesis: {e}")
            return None

    async def _check_predictions(self, articles: list[dict]) -> dict:
        """Grade the open-prediction ledger against today's coverage."""
        try:
            with get_db() as session:
                return await self.prediction_tracker.check_open_predictions(articles, session)
        except Exception as e:
            logger.warning(f"Prediction check failed; continuing without it: {e}")
            return {
                "checked": 0,
                "triggered": 0,
                "contradicted": 0,
                "expired": 0,
                "still_open": 0,
            }

    @staticmethod
    def _build_decision_summary(routed_evidence, session) -> list[dict]:
        """
        Group routed evidence by decision into a compact brief summary:
        ``[{"decision": name, "factors": [{"name", "direction"}]}]``.
        """
        from ..database.models import Decision, DecisionFactor

        if not routed_evidence:
            return []

        decision_ids = {r.decision_id for r in routed_evidence}
        factor_ids = {r.factor_id for r in routed_evidence}
        decisions = {
            d.id: d.name
            for d in session.query(Decision).filter(Decision.id.in_(decision_ids)).all()
        }
        factors = {
            f.id: f.name
            for f in session.query(DecisionFactor).filter(DecisionFactor.id.in_(factor_ids)).all()
        }

        grouped: dict[int, list[dict]] = {}
        for r in routed_evidence:
            grouped.setdefault(r.decision_id, []).append(
                {"name": factors.get(r.factor_id, "(factor)"), "direction": r.direction}
            )
        return [
            {"decision": decisions.get(did, "(decision)"), "factors": factor_list}
            for did, factor_list in grouped.items()
        ]

    @staticmethod
    def _collect_predictions(situations: list[dict]) -> list[tuple[int, str, str]]:
        """
        Walk situations and extract what_to_watch observables.

        Returns ``[(situation_index, observable_text, trigger_condition), ...]``.
        """
        out: list[tuple[int, str, str]] = []
        for s_idx, situation in enumerate(situations):
            futures = situation.get("where_this_goes") or {}
            watch = futures.get("what_to_watch")
            if isinstance(watch, list):
                for entry in watch:
                    if not isinstance(entry, dict):
                        continue
                    observable = (entry.get("observable") or "").strip()
                    trigger = (entry.get("trigger_condition") or "").strip()
                    if observable and trigger:
                        out.append((s_idx, observable, trigger))
        return out

    @staticmethod
    def _collect_proposed_questions(
        situations: list[dict],
    ) -> list[tuple[int, str, ProposedQuestion]]:
        """
        Walk situations and extract their unresolved questions.

        Returns ``[(situation_index, slot, ProposedQuestion), ...]`` where
        ``slot`` is "primary" or "secondary:N". Order matches the order
        situations + secondaries are emitted, so callers can zip in parallel.
        """
        plan: list[tuple[int, str, ProposedQuestion]] = []
        for s_idx, situation in enumerate(situations):
            futures = situation.get("where_this_goes") or {}
            uq = futures.get("unresolved_questions")
            if isinstance(uq, dict):
                primary = uq.get("primary")
                if isinstance(primary, str) and primary.strip():
                    plan.append((s_idx, "primary", ProposedQuestion(primary.strip(), True)))
                for i, sec in enumerate(uq.get("secondary") or []):
                    if isinstance(sec, str) and sec.strip():
                        plan.append((s_idx, f"secondary:{i}", ProposedQuestion(sec.strip(), False)))
            elif isinstance(uq, str) and uq.strip():
                # Backward compat for any synthesis emitting the old string form.
                plan.append((s_idx, "primary", ProposedQuestion(uq.strip(), True)))
            else:
                legacy = futures.get("unresolved_question")
                if isinstance(legacy, str) and legacy.strip():
                    plan.append((s_idx, "primary", ProposedQuestion(legacy.strip(), True)))
        return plan

    @staticmethod
    def _enrich_situations_with_questions(
        situations: list[dict],
        plan: list[tuple[int, str, ProposedQuestion]],
        resolved: list[Question],
    ) -> None:
        """Attach question identity metadata onto each situation's questions."""
        # Group resolved by situation_index + slot for easy lookup.
        by_slot: dict[tuple[int, str], Question] = {}
        for (sit_idx, slot, _pq), q in zip(plan, resolved, strict=True):
            by_slot[(sit_idx, slot)] = q

        for sit_idx, situation in enumerate(situations):
            futures = situation.get("where_this_goes")
            if not isinstance(futures, dict):
                continue
            primary_q = by_slot.get((sit_idx, "primary"))
            if primary_q:
                appearance_count = len(primary_q.situation_links) + 1
                futures["unresolved_questions"] = {
                    "primary": {
                        "text": primary_q.text,
                        "question_id": primary_q.id,
                        "first_asked_at": primary_q.first_asked_at.isoformat(),
                        "appearance_count": appearance_count,
                        "previous_question_id": primary_q.previous_question_id,
                    },
                    "secondary": [],
                }
                # Drop the legacy key if it was present.
                futures.pop("unresolved_question", None)

            sec_idx = 0
            while True:
                sec_q = by_slot.get((sit_idx, f"secondary:{sec_idx}"))
                if not sec_q:
                    break
                appearance_count = len(sec_q.situation_links) + 1
                futures.setdefault("unresolved_questions", {"primary": None, "secondary": []})
                futures["unresolved_questions"].setdefault("secondary", []).append(
                    {
                        "text": sec_q.text,
                        "question_id": sec_q.id,
                        "first_asked_at": sec_q.first_asked_at.isoformat(),
                        "appearance_count": appearance_count,
                        "previous_question_id": sec_q.previous_question_id,
                    }
                )
                sec_idx += 1

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
