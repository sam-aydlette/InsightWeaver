"""
The adjudication prompt: text, effort, caps, and the message builder.

Kept apart from the adjudicator so the prompt can be read as prose and so the
adjudicator module stays inside the repository's size rule. Everything here is
part of the prompt version's identity: :mod:`src.evidence.claude_adjudicator`
hashes these constants together with the response schema into the fingerprint
a test pins to ``PROMPT_VERSION``.

Added 2026-09-22 for backlog task 029.
"""

from __future__ import annotations

from typing import Any

from .adjudicator import ObservationView

__all__ = [
    "EFFORT",
    "MAX_TOKENS",
    "SYSTEM_PROMPT",
    "TEXT_CAP",
    "USER_TEMPLATE",
    "build_messages",
    "estimate_tokens",
]

# Reasoning depth for one judgement-shaped call. Part of the version identity:
# a different effort is a different judge. (2026-09-22, backlog task 029.)
EFFORT = "medium"

# Characters of observation text sent. Longer documents are truncated and the
# user message says so, which puts the fact in the audit log beside the text.
# (2026-09-22, backlog task 029.)
TEXT_CAP = 6000

# max_tokens caps thinking and the answer together, and the model thinks by
# default (see src/llm/claude_client.py). A low ceiling ends a call with no
# text block, which the adjudicator records as a failure. 16000 is the SDK
# guidance for a non-streaming call; what a call actually costs is what the
# API reports, not this ceiling. (2026-09-22, backlog task 029.)
MAX_TOKENS = 16000

SYSTEM_PROMPT = """You judge whether one published item bears on one pre-registered claim. You are not asked whether the claim is true, and you do not recommend anything.

Rules, in order of precedence:

1. Judge only what the text says. Do not infer what an author probably meant, what will likely follow, or what a reasonable reader would conclude beyond the words.
2. A claim the text does not address is not evidence. Most items are not evidence for most claims; say so.
3. When two readings are possible, take the weaker one: not evidence over evidence, a smaller magnitude over a larger one.
4. Direction is "supports" when what the text reports, taken at face value, would make the claim more likely to be true; "contradicts" when less likely; "none" when the item is not evidence. Evidence always has a direction; a non-evidence verdict always has direction "none".
5. Magnitude is the strength of bearing, from 0 (none) to 1 (the text directly reports the claim's resolution). It is not a probability that the claim is true. Confidence is your confidence in your own reading of the text.
6. If the item matches one of the claim's trigger clauses, name the clause index in satisfies_clause; otherwise -1.
7. The rationale is one or two sentences that quote or closely paraphrase the words the verdict rests on. No emotional language, no urgency, no advice.

Answer with the JSON object the schema describes and nothing else."""

USER_TEMPLATE = """CLAIM (watch {watch_id}):
{claim}

THE DECISION THIS CLAIM SERVES ({decision_key}), as the operator recorded it:
{so_what}

TRIGGER CLAUSES (index: clause):
{triggers}

ITEM
source: {source}
published: {published}
title: {title}
text ({text_note}):
{text}"""


def _clauses(triggers: Any) -> str:
    lines = []
    for index, clause in enumerate(triggers or ()):
        parts = [f"{key}: {', '.join(str(v) for v in values)}" for key, values in clause.items()]
        lines.append(f"  {index}: " + "; ".join(parts))
    return "\n".join(lines) or "  (none)"


def build_messages(observation: ObservationView, watch: Any) -> tuple[str, str]:
    """The exact system and user text for one pair. Pure; used by --dry-run."""
    text = observation.text
    if len(text) > TEXT_CAP:
        note = f"{len(text)} characters, truncated to {TEXT_CAP}"
        text = text[:TEXT_CAP]
    else:
        note = f"{len(text)} characters"
    payload = observation.payload
    user = USER_TEMPLATE.format(
        watch_id=watch.id,
        claim=watch.claim,
        decision_key=watch.decision_key,
        so_what=watch.so_what,
        triggers=_clauses(watch.triggers),
        source=payload.get("source_url") or "(unknown source)",
        published=payload.get("published_date") or "(undated)",
        title=observation.title or "(untitled)",
        text_note=note,
        text=text or "(no text)",
    )
    return SYSTEM_PROMPT, user


def estimate_tokens(system: str, user: str) -> int:
    """A character-count estimate, labelled as such wherever it is printed."""
    return (len(system) + len(user)) // 4
