"""
Cross-Cluster Reconciler

Pass 3: after all situations finalize, look across them for meta-fractures --
a single underlying frame conflict appearing in multiple topically distinct
situations. This catches frame structure as a corpus property rather than
just a per-cluster one.
"""

import logging

from ..prompts.meta_frames import META_FRAME_RECONCILIATION_PROMPT
from ._json import parse_claude_json
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)

RECONCILER_MODEL = "claude-haiku-4-5-20251001"
RECONCILER_MAX_TOKENS = 2048
# Reconciliation is only meaningful with at least two situations to compare.
MIN_SITUATIONS = 2


class CrossClusterReconciler:
    """Detects meta-fractures spanning multiple situations."""

    def __init__(self, client: ClaudeClient | None = None):
        self.client = client or ClaudeClient(model=RECONCILER_MODEL)

    async def reconcile(self, situations: list[dict]) -> list[dict]:
        """
        Return the list of detected meta-fractures, validated.

        Each entry has ``name``, ``description``, ``situation_indices``
        (subset of valid indices, length >= 2), and ``shared_point``. Returns
        an empty list when there is nothing to reconcile, the LLM fails, or
        no meta-fractures are found.
        """
        if len(situations) < MIN_SITUATIONS:
            return []

        situations_block = self._build_situations_block(situations)
        if not situations_block:
            return []

        prompt = META_FRAME_RECONCILIATION_PROMPT.format(situations_block=situations_block)

        try:
            raw = await self.client.analyze(
                system_prompt=(
                    "You find meta-fractures across multiple frame analyses. "
                    "Be conservative; empty results are common."
                ),
                user_message=prompt,
                temperature=0.0,
                max_tokens=RECONCILER_MAX_TOKENS,
            )
        except Exception as e:
            logger.warning(f"Reconciler LLM call failed; returning no meta-fractures: {e}")
            return []

        parsed = parse_claude_json(raw, label="reconciler response")
        result: list[dict] = []
        n = len(situations)
        for entry in parsed.get("meta_fractures", []):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            description = str(entry.get("description", "")).strip()
            shared_point = str(entry.get("shared_point", "")).strip()
            indices_raw = entry.get("situation_indices", [])
            if not isinstance(indices_raw, list):
                continue
            indices = sorted({i for i in indices_raw if isinstance(i, int) and 0 <= i < n})
            if len(indices) < MIN_SITUATIONS or not name or not shared_point:
                continue
            result.append(
                {
                    "name": name,
                    "description": description,
                    "situation_indices": indices,
                    "shared_point": shared_point,
                }
            )
        return result

    @staticmethod
    def _build_situations_block(situations: list[dict]) -> str:
        """Render each situation's frame info compactly for the prompt."""
        lines: list[str] = []
        for i, situation in enumerate(situations):
            title = situation.get("title", "Untitled")
            frame = situation.get("coverage_frame") or {}
            narrative_layers = (frame.get("narrative_layers") or "").strip()
            fractures = (frame.get("fractures") or "").strip()
            if not narrative_layers and not fractures:
                continue
            block = [f"[{i}] {title}"]
            if narrative_layers:
                block.append(f"  layers: {narrative_layers}")
            if fractures:
                block.append(f"  fractures: {fractures}")
            lines.append("\n".join(block))
        return "\n\n".join(lines)
