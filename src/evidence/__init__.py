"""
Evidence: what an adjudication prompt concluded, and the harness that replays it.

Two modules and a hard line between them. ``adjudicator`` is the seam a prompt
version plugs into; ``replay`` rebuilds evidence from observations through that
seam and diffs the result against what is stored. Neither contains an
adjudication prompt -- that is backlog task 016.

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

__all__ = [
    "DIRECTIONS",
    "NULL_PROMPT_VERSION",
    "Adjudicator",
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
