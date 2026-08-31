"""
Tier 1: deterministic routing from Observations to Watches.

Nothing in this package calls a model, and nothing in it may. Tier 1 decides
*candidacy* -- whether an observation is worth the adjudicator's attention --
using compiled word-boundary regexes and a source allowlist, and that is the
whole of it. The tier that reasons is Tier 2, it is the only one that costs
money per item, and it sees exactly what this package hands it.

Three modules:

* :mod:`predicate` compiles a watch's ``triggers`` into a predicate.
* :mod:`router` runs the predicates over stored observations and records the
  matches as :class:`~src.database.models.RouteCandidate` rows.
* :mod:`gaps` clusters what matched nothing, which is the coverage-gap signal.

Added 2026-08-31 for backlog task 015.
"""

from .gaps import (
    GAP_REPORT_SCHEMA,
    UnroutedCluster,
    cluster_unrouted,
    default_gap_report_path,
    gap_report,
    gap_terms,
    write_gap_report,
)
from .predicate import (
    CompiledClause,
    CompiledWatch,
    TriggerCompileError,
    compile_watch,
    compile_watches,
    source_keys,
)
from .router import RoutedLink, RoutingReport, persist, route

__all__ = [
    "GAP_REPORT_SCHEMA",
    "CompiledClause",
    "CompiledWatch",
    "RoutedLink",
    "RoutingReport",
    "TriggerCompileError",
    "UnroutedCluster",
    "cluster_unrouted",
    "compile_watch",
    "compile_watches",
    "default_gap_report_path",
    "gap_report",
    "gap_terms",
    "persist",
    "route",
    "source_keys",
    "write_gap_report",
]
