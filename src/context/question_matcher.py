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
from .beat_scope import declared_standing_question_ids, question_scope_filter
from .claude_client import ClaudeClient

logger = logging.getLogger(__name__)

MATCHER_MODEL = "claude-haiku-4-5-20251001"
OPEN_QUESTION_LIMIT = 100
MATCHER_MAX_TOKENS = 2048

# How much subject vocabulary a proposed question must share with a *declared*
# standing question before the matcher will bind them (added 2026-08-26,
# backlog task 007).
#
# Emergent questions are matched on the LLM's judgement alone, and that stays
# exactly as it was. A declared question is different in kind: it was written
# by a human before any coverage existed, it is typically broad ("Which CSPs
# move to FedRAMP authorized?"), and broad text is what a similarity matcher
# over-matches. Binding it to unrelated coverage is worse than missing a real
# match, because a standing question that falsely reads "moved" destroys the
# one thing the agenda is for -- so the LLM's answer is treated as a proposal
# and this lexical gate has a veto over it.
#
# Measured as overlap against the *shorter* question's content tokens rather
# than Jaccard: the two texts are routinely different lengths (a declared
# question is terser than a question drawn out of a week's coverage), and
# Jaccard penalises that length difference rather than the topic drift the
# gate is actually trying to catch.
STANDING_BINDING_MIN_OVERLAP = 0.6

# Function words carry no subject, so they would inflate every overlap score.
# fmt: off
_STOPWORDS = frozenset(
    [
        "a", "an", "and", "any", "are", "as", "at", "be", "been", "being", "but", "by", "can",
        "could", "did", "do", "does", "doing", "for", "from", "had", "has", "have", "how", "i",
        "if", "in", "into", "is", "it", "its", "may", "might", "must", "of", "on", "or",
        "over", "should", "so", "some", "such", "than", "that", "the", "their", "them", "then",
        "there", "these", "they", "this", "those", "to", "under", "up", "was", "were", "what",
        "when", "where", "whether", "which", "while", "who", "whom", "why", "will", "with",
        "within", "would", "you", "your",
    ]
)
# fmt: on


_PUNCT = re.compile(r"[^\w\s]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_question(text: str) -> str:
    """Lowercase, strip diacritics and punctuation, collapse whitespace."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    stripped = _PUNCT.sub(" ", folded.lower())
    return _WHITESPACE.sub(" ", stripped).strip()


def content_tokens(text: str) -> set[str]:
    """
    The subject-bearing words of a question: normalized, stopwords removed,
    trailing plural ``s`` folded.

    The plural fold is naive on purpose -- it is not stemming, it just stops
    "deadline inside 90 days" and "a 90-day deadline" from reading as different
    subjects. Both sides of a comparison go through it, so it can only merge
    tokens, never invent an overlap that the words do not support.
    """
    tokens = set()
    for token in normalize_question(text).split():
        if token in _STOPWORDS:
            continue
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.add(token)
    return tokens


def binding_overlap(proposed: str, candidate: str) -> float:
    """
    How much subject vocabulary two questions share, from 0.0 to 1.0.

    The overlap coefficient: shared content tokens over the size of the smaller
    token set. Returns 0.0 when either question has no content tokens at all,
    which refuses the bind rather than guessing at it.
    """
    left, right = content_tokens(proposed), content_tokens(candidate)
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


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

        Declared standing questions live in the same scope and enter the same
        matcher, but bind on a tighter rule -- see
        :data:`STANDING_BINDING_MIN_OVERLAP`. Emergent questions are unaffected.
        """
        if not proposed:
            return []

        scope = question_scope_filter(session, beat_id)
        standing_ids = declared_standing_question_ids(session, beat_id)
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
                        if matched and self._binding_allowed(
                            proposed[original_idx].text, matched, standing_ids
                        ):
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

    @staticmethod
    def _binding_allowed(proposed_text: str, matched: Question, standing_ids: set[int]) -> bool:
        """
        Whether an LLM-proposed match may stand.

        Always yes for an emergent question -- that path is unchanged. For a
        *declared* standing question the LLM's answer additionally has to clear
        :data:`STANDING_BINDING_MIN_OVERLAP`, and a refused bind is not a
        failure: the proposed question simply becomes a new emergent Question,
        and the standing question is reported as unmoved, which is the honest
        answer when the coverage was about something else.

        Note the exact-normalized-text path above needs no gate: identical text
        is already the tightest match there is.
        """
        if matched.id not in standing_ids:
            return True

        overlap = binding_overlap(proposed_text, matched.text)
        if overlap >= STANDING_BINDING_MIN_OVERLAP:
            return True

        logger.info(
            f"Refused to bind {proposed_text!r} to standing question Q{matched.id}: "
            f"subject overlap {overlap:.2f} < {STANDING_BINDING_MIN_OVERLAP}"
        )
        return False

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
                temperature=0.0,
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
