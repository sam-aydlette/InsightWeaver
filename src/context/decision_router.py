"""
Decision Router
Runs after situation synthesis: matches each situation against the user's
open decision factors and produces evidence specs. This is the only place
situation-to-decision routing happens, so the chain from coverage to
decision stays centralized and inspectable.
"""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..database.models import (
    DECISION_STATUS_OPEN,
    EVIDENCE_DIRECTION_COMPLICATES,
    EVIDENCE_DIRECTION_NEUTRAL,
    EVIDENCE_DIRECTION_SUPPORTS,
    Decision,
    DecisionFactor,
)
from ..prompts.decisions import DECISION_ROUTING_PROMPT
from ._json import parse_claude_json
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)

ROUTER_MODEL = "claude-haiku-4-5-20251001"
ROUTER_MAX_TOKENS = 4096
SITUATION_EXCERPT_CHARS = 600

_VALID_DIRECTIONS = {
    EVIDENCE_DIRECTION_SUPPORTS,
    EVIDENCE_DIRECTION_COMPLICATES,
    EVIDENCE_DIRECTION_NEUTRAL,
}
_VALID_EPISTEMIC = {"reported_fact", "single_source", "consensus", "speculation"}


@dataclass
class RoutedEvidence:
    """One validated routing result, ready for the synthesizer to persist."""

    situation_index: int
    decision_id: int
    factor_id: int
    direction: str
    epistemic_status: str
    excerpt: str


class DecisionRouter:
    """Routes situation evidence into the user's open decision factors."""

    def __init__(self, client: ClaudeClient | None = None):
        self.client = client or ClaudeClient(model=ROUTER_MODEL)

    async def route_evidence(
        self, situations: list[dict], session: Session
    ) -> list[RoutedEvidence]:
        """
        Match situations against open decision factors.

        Returns validated RoutedEvidence specs. Does not write to the
        database -- the synthesizer attaches synthesis_id and question_id
        and persists them. Returns an empty list when there are no open
        decisions or no situations.
        """
        if not situations:
            return []

        factors = (
            session.query(DecisionFactor)
            .join(Decision, DecisionFactor.decision_id == Decision.id)
            .filter(Decision.status == DECISION_STATUS_OPEN)
            .all()
        )
        if not factors:
            return []

        # factor_id -> decision_id, for validating LLM output and attaching
        # the decision to each routed evidence row.
        decision_by_factor = {f.id: f.decision_id for f in factors}

        raw = await self._llm_route(factors, situations)
        results: list[RoutedEvidence] = []
        for entry in raw:
            sit_idx = entry.get("situation_index")
            factor_id = entry.get("factor_id")
            if not isinstance(sit_idx, int) or not (0 <= sit_idx < len(situations)):
                continue
            if not isinstance(factor_id, int) or factor_id not in decision_by_factor:
                continue

            direction = entry.get("direction")
            if direction not in _VALID_DIRECTIONS:
                direction = EVIDENCE_DIRECTION_NEUTRAL
            epistemic = entry.get("epistemic_status")
            if epistemic not in _VALID_EPISTEMIC:
                epistemic = "speculation"
            excerpt = str(entry.get("excerpt", "")).strip()
            if not excerpt:
                continue

            results.append(
                RoutedEvidence(
                    situation_index=sit_idx,
                    decision_id=decision_by_factor[factor_id],
                    factor_id=factor_id,
                    direction=direction,
                    epistemic_status=epistemic,
                    excerpt=excerpt,
                )
            )
        return results

    async def _llm_route(self, factors: list[DecisionFactor], situations: list[dict]) -> list[dict]:
        """One Haiku call: returns the raw evidence list (unvalidated)."""
        factor_lines = []
        for f in factors:
            decision_name = f.decision.name if f.decision else "(unknown decision)"
            update_clause = f.what_would_update_me or "(no update rule set)"
            factor_lines.append(
                f"[{f.id}] decision: {decision_name}\n"
                f"      factor: {f.name}\n"
                f"      would update me: {update_clause}"
            )
        factors_block = "\n\n".join(factor_lines)

        situation_lines = []
        for i, situation in enumerate(situations):
            title = situation.get("title", "Untitled")
            narrative = (situation.get("narrative") or "")[:SITUATION_EXCERPT_CHARS].strip()
            situation_lines.append(f"[{i}] {title}\n    {narrative}")
        situations_block = "\n\n".join(situation_lines)

        prompt = DECISION_ROUTING_PROMPT.format(
            factors_block=factors_block,
            situations_block=situations_block,
        )

        try:
            raw = await self.client.analyze(
                system_prompt=(
                    "You route news analysis into a user's standing decisions. "
                    "Be conservative; most situations route nowhere."
                ),
                user_message=prompt,
                temperature=0.0,
                max_tokens=ROUTER_MAX_TOKENS,
            )
        except Exception as e:
            logger.warning(f"Decision router LLM call failed; routing nothing: {e}")
            return []

        parsed = parse_claude_json(raw, label="decision router response")
        evidence = parsed.get("evidence", [])
        return evidence if isinstance(evidence, list) else []
