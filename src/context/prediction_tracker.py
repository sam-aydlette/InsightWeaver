"""
Prediction Tracker
Runs before each synthesis: expires stale open predictions, then grades the
rest against today's coverage. This is what makes the tool's own
forward-looking statements auditable -- every observable it flagged gets
checked against what later actually showed up in the feeds.
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from ..database.models import (
    PREDICTION_EXPIRY_DAYS,
    PREDICTION_STATUS_CONTRADICTED,
    PREDICTION_STATUS_EXPIRED,
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    Prediction,
)
from ..prompts.predictions import PREDICTION_CHECK_PROMPT
from ..utils import utcnow
from ._json import parse_claude_json
from .beat_scope import prediction_scope_filter
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)

TRACKER_MODEL = "claude-haiku-4-5-20251001"
OPEN_PREDICTION_LIMIT = 200
CHECK_MAX_TOKENS = 4096
# Article snippets passed to the check pass; titles + a short lead is enough
# to tell whether an observable was reported.
COVERAGE_SNIPPET_CHARS = 200


class PredictionTracker:
    """Grades the open-prediction ledger against fresh coverage."""

    def __init__(self, client: ClaudeClient | None = None):
        self.client = client or ClaudeClient(model=TRACKER_MODEL)

    async def check_open_predictions(
        self, articles: list[dict], session: Session, beat_id: int | None = None
    ) -> dict:
        """
        Expire stale predictions, then grade the rest against today's coverage.

        Returns a summary dict for the brief's transparency block. Writes
        status changes to the session but does not commit -- the caller owns
        the transaction.

        ``beat_id`` restricts both the expiry sweep and the grading pass to one
        scope's ledger, so a beat run never resolves or ages out the default
        brief's observables and vice versa. With no beat runs on record the
        scope is the whole ledger, i.e. the behaviour that predates beats.
        """
        now = utcnow()
        scope = prediction_scope_filter(session, beat_id)
        summary = {
            "checked": 0,
            "triggered": 0,
            "contradicted": 0,
            "expired": 0,
            "still_open": 0,
        }

        # Expire anything that aged out without resolution.
        cutoff = now - timedelta(days=PREDICTION_EXPIRY_DAYS)
        stale = (
            session.query(Prediction)
            .filter(
                Prediction.status == PREDICTION_STATUS_OPEN,
                Prediction.made_at < cutoff,
                scope,
            )
            .all()
        )
        for pred in stale:
            pred.status = PREDICTION_STATUS_EXPIRED
            pred.resolved_at = now
            pred.resolution_note = (
                f"Expired after {PREDICTION_EXPIRY_DAYS} days without resolution."
            )
        summary["expired"] = len(stale)

        open_preds = (
            session.query(Prediction)
            .filter(Prediction.status == PREDICTION_STATUS_OPEN, scope)
            .order_by(Prediction.made_at.desc())
            .limit(OPEN_PREDICTION_LIMIT)
            .all()
        )
        summary["checked"] = len(open_preds)
        summary["still_open"] = len(open_preds)

        if not open_preds or not articles:
            session.flush()
            return summary

        verdicts = await self._llm_check(open_preds, articles)
        for pred in open_preds:
            verdict = verdicts.get(pred.id)
            if not verdict:
                continue
            label, note = verdict
            if label == "triggered":
                pred.status = PREDICTION_STATUS_TRIGGERED
                pred.resolved_at = now
                pred.resolution_note = f"Triggered: {note}"
                summary["triggered"] += 1
                summary["still_open"] -= 1
            elif label == "contradicted":
                pred.status = PREDICTION_STATUS_CONTRADICTED
                pred.resolved_at = now
                pred.resolution_note = f"Contradicted: {note}"
                summary["contradicted"] += 1
                summary["still_open"] -= 1

        session.flush()
        return summary

    async def _llm_check(
        self, predictions: list[Prediction], articles: list[dict]
    ) -> dict[int, tuple[str, str]]:
        """One Haiku call: maps prediction id to (verdict, note)."""
        pred_lines = []
        for p in predictions:
            question_text = p.question.text if p.question else "(unknown question)"
            pred_lines.append(
                f"[{p.id}] observable: {p.observable_text}\n"
                f"      trigger: {p.trigger_condition}\n"
                f"      bears on: {question_text}"
            )
        predictions_block = "\n\n".join(pred_lines)

        coverage_lines = []
        for article in articles:
            title = article.get("title", "Untitled")
            content = article.get("content") or article.get("description") or ""
            snippet = content[:COVERAGE_SNIPPET_CHARS].strip()
            source = article.get("source", "Unknown")
            coverage_lines.append(f"- {title} ({source})\n  {snippet}")
        coverage_block = "\n".join(coverage_lines)

        prompt = PREDICTION_CHECK_PROMPT.format(
            predictions_block=predictions_block,
            coverage_block=coverage_block,
        )

        try:
            raw = await self.client.analyze(
                system_prompt=(
                    "You grade open predictions against fresh news coverage. "
                    "Be conservative; 'open' is the default."
                ),
                user_message=prompt,
                effort="low",
                max_tokens=CHECK_MAX_TOKENS,
            )
        except Exception as e:
            logger.warning(f"Prediction check LLM call failed; leaving all open: {e}")
            return {}

        parsed = parse_claude_json(raw, label="prediction check response")
        results: dict[int, tuple[str, str]] = {}
        valid = {"triggered", "contradicted", "open"}
        for entry in parsed.get("verdicts", []):
            pid = entry.get("prediction_id")
            verdict = entry.get("verdict")
            note = entry.get("note", "")
            if isinstance(pid, int) and verdict in valid:
                results[pid] = (verdict, str(note))
        return results
