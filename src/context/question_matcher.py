"""
Question Matcher
Resolves freshly-proposed unresolved_questions against the persistent
Question graph: matches to existing open questions where appropriate,
creates new Question records otherwise.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..database.models import (
    QUESTION_STATUS_OPEN,
    QUESTION_STATUS_RESOLVED,
    Question,
)
from ..prompts.questions import QUESTION_MATCHING_PROMPT
from ..utils import utcnow
from ._json import parse_claude_json
from .beat_scope import question_scope_filter
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)

MATCHER_MODEL = "claude-haiku-4-5-20251001"
OPEN_QUESTION_LIMIT = 100
MATCHER_MAX_TOKENS = 2048


_PUNCT = re.compile(r"[^\w\s]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_question(text: str) -> str:
    """Lowercase, strip diacritics and punctuation, collapse whitespace."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    stripped = _PUNCT.sub(" ", folded.lower())
    return _WHITESPACE.sub(" ", stripped).strip()


@dataclass
class ProposedQuestion:
    """One question proposed by today's synthesis."""

    text: str
    is_primary: bool = True


class QuestionMatcher:
    """Resolves proposed questions against persistent Question records."""

    def __init__(self, client: ClaudeClient | None = None):
        self.client = client or ClaudeClient(model=MATCHER_MODEL)

    async def resolve_questions(
        self,
        proposed: list[ProposedQuestion],
        session: Session,
        beat_id: int | None = None,
    ) -> list[Question]:
        """
        Map each proposed question to a Question row (existing or new).

        Returns a list parallel to ``proposed``: each Question is either an
        existing row or a newly added one (session.add). The caller commits.

        ``beat_id`` selects the scope questions are matched within: a beat's
        run only ever binds to that beat's questions, and the default (no-beat)
        run only ever binds to questions no beat has claimed. Without any beat
        runs on record the scope is the whole graph, i.e. the behaviour that
        predates beats.
        """
        if not proposed:
            return []

        scope = question_scope_filter(session, beat_id)
        normalized = [normalize_question(p.text) for p in proposed]
        resolved: list[Question | None] = [None] * len(proposed)

        for i, norm in enumerate(normalized):
            if not norm:
                continue
            hit = (
                session.query(Question)
                .filter(
                    Question.status == QUESTION_STATUS_OPEN,
                    Question.normalized_text == norm,
                    scope,
                )
                .first()
            )
            if hit:
                resolved[i] = hit

        remaining_idx = [i for i, r in enumerate(resolved) if r is None]
        if remaining_idx:
            open_questions = (
                session.query(Question)
                .filter(Question.status == QUESTION_STATUS_OPEN, scope)
                .order_by(Question.first_asked_at.desc())
                .limit(OPEN_QUESTION_LIMIT)
                .all()
            )

            if open_questions:
                llm_matches = await self._llm_match(
                    [proposed[i].text for i in remaining_idx],
                    open_questions,
                )
                for slot, original_idx in enumerate(remaining_idx):
                    matched_id = llm_matches.get(slot)
                    if matched_id is not None:
                        matched = next((q for q in open_questions if q.id == matched_id), None)
                        if matched:
                            resolved[original_idx] = matched

        previous_link: dict[int, int] = {}
        still_unmatched = [i for i, r in enumerate(resolved) if r is None]
        for i in still_unmatched:
            norm = normalized[i]
            if not norm:
                continue
            prior = (
                session.query(Question.id)
                .filter(
                    Question.status == QUESTION_STATUS_RESOLVED,
                    Question.normalized_text == norm,
                    scope,
                )
                .order_by(Question.resolved_at.desc())
                .first()
            )
            if prior:
                previous_link[i] = prior[0]

        now = utcnow()
        for i, q in enumerate(resolved):
            if q is not None:
                continue
            new_q = Question(
                text=proposed[i].text,
                normalized_text=normalized[i],
                first_asked_at=now,
                status=QUESTION_STATUS_OPEN,
                is_primary=proposed[i].is_primary,
                previous_question_id=previous_link.get(i),
            )
            session.add(new_q)
            resolved[i] = new_q

        session.flush()
        return resolved  # type: ignore[return-value]

    async def _llm_match(
        self, proposed_texts: list[str], open_questions: list[Question]
    ) -> dict[int, int | None]:
        """One Haiku call: maps each proposed slot index to a matched_id or None."""
        proposed_block = "\n".join(f"[{i}] {text}" for i, text in enumerate(proposed_texts))
        open_block = "\n".join(
            f"[{q.id}] (asked {q.first_asked_at.date().isoformat()}) {q.text}"
            for q in open_questions
        )
        prompt = QUESTION_MATCHING_PROMPT.format(
            proposed_block=proposed_block,
            open_block=open_block,
        )

        try:
            raw = await self.client.analyze(
                system_prompt="You match unresolved questions across runs. Be conservative.",
                user_message=prompt,
                effort="low",
                max_tokens=MATCHER_MAX_TOKENS,
            )
        except Exception as e:
            logger.warning(f"Question matcher LLM call failed; treating all as new: {e}")
            return {}

        parsed = parse_claude_json(raw, label="question matcher response")
        results: dict[int, int | None] = {}
        for entry in parsed.get("matches", []):
            idx = entry.get("proposed_index")
            matched_id = entry.get("matched_id")
            if isinstance(idx, int):
                results[idx] = matched_id if isinstance(matched_id, int) else None
        return results
