"""
Tier 1: deterministic routing of observations to watches.

No model is involved anywhere in this package, and a test proves it by
blocking the import of ``src.llm`` while the full routing path runs. A watch's
trigger clauses compile to word-boundary regexes and a source-name test
(:mod:`~src.routing.compile`); the router evaluates them over a window of
observations and records the candidate pairs in ``routes``
(:mod:`~src.routing.route`). Everything the adjudicator is later asked about
passes through here first, which is what keeps the model from seeing the bulk
of the corpus.

Added 2026-09-22 for backlog task 028.
"""

from .compile import CompiledClause, CompiledWatch, TriggerCompileError, compile_triggers
from .route import RoutingReport, UnroutedCluster, WatchRouting, live_watches, route

__all__ = [
    "CompiledClause",
    "CompiledWatch",
    "RoutingReport",
    "TriggerCompileError",
    "UnroutedCluster",
    "WatchRouting",
    "compile_triggers",
    "live_watches",
    "route",
]
