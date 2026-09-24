"""
Deterministic text matching.

No model is involved anywhere in this package. A match is a word-boundary regex
hit, which makes every count reproducible from the same articles forever and
makes a wrong count debuggable by reading a regex rather than by re-running a
prompt.

Ported out of the deleted ``src/context/`` package by backlog task 012:

* :mod:`~src.matching.entity_matcher` -- alias matching for Tier 1 routing.
* :mod:`~src.matching.terms` -- the value object it consumes.

``coverage_probe.py`` left with backlog task 027 on 2026-09-22; see
``src/matching/terms.py`` for why.
"""

from .terms import CoverageEntity

__all__ = ["CoverageEntity"]
