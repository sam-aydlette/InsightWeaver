"""
Deterministic text matching.

No model is involved anywhere in this package. A match is a word-boundary regex
hit, which makes every count reproducible from the same articles forever and
makes a wrong count debuggable by reading a regex rather than by re-running a
prompt.

Ported out of the deleted ``src/context/`` package by backlog task 012:

* :mod:`~src.matching.entity_matcher` -- alias matching for Tier 1 routing.
* :mod:`~src.matching.coverage_probe` -- "did anything match this in N days",
  which is the staleness check task 018 needs.
* :mod:`~src.matching.terms` -- the value objects both consume.
"""

from .terms import CoverageEntity, CoverageProbe

__all__ = ["CoverageEntity", "CoverageProbe"]
