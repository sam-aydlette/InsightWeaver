"""
Evidence: what an adjudication prompt concluded, and the harness that replays it.

``adjudicator`` is the seam a prompt version plugs into; ``replay`` rebuilds
evidence from routed observations through that seam and diffs the result
against what is stored. ``claude_adjudicator`` is the one prompt version that
calls a model (backlog task 029, 2026-09-22), registered here so that
``resolve("claude-v1")`` works without constructing a client; ``adjudicate``
is the run loop that asks it about every routed pair once and records every
answer.

Added 2026-08-31 for backlog task 014.
"""

from .adjudicator import (
    DIRECTIONS,
    NULL_PROMPT_VERSION,
    Adjudicator,
    NullAdjudicator,
    ObservationView,
    UnknownPromptVersion,
    Verdict,
    known_prompt_versions,
    load_adjudicator,
    register,
    resolve,
)
from .claude_adjudicator import PROMPT_VERSION as CLAUDE_PROMPT_VERSION
from .claude_adjudicator import AdjudicationFailed, AdjudicationVerdict, ClaudeAdjudicator
from .replay import (
    EvidenceRow,
    NondeterministicReplay,
    ReplayDiff,
    commit,
    diff,
    format_diff,
    rebuild,
    stored_evidence,
)

register(CLAUDE_PROMPT_VERSION, ClaudeAdjudicator)

__all__ = [
    "CLAUDE_PROMPT_VERSION",
    "DIRECTIONS",
    "NULL_PROMPT_VERSION",
    "AdjudicationFailed",
    "AdjudicationVerdict",
    "Adjudicator",
    "ClaudeAdjudicator",
    "EvidenceRow",
    "NondeterministicReplay",
    "NullAdjudicator",
    "ObservationView",
    "ReplayDiff",
    "UnknownPromptVersion",
    "Verdict",
    "commit",
    "diff",
    "format_diff",
    "known_prompt_versions",
    "load_adjudicator",
    "rebuild",
    "register",
    "resolve",
    "stored_evidence",
]
