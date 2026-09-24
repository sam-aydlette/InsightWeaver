"""
What a matcher is pointed at: entities.

This value object was lifted verbatim from ``src/config/beats.py`` when the
briefing product was deleted (backlog task 012). The *beat* it used to belong
to is gone -- a beat was a subject with its own source list, and the new shape
tracks one operator's decisions instead. What survives is the description the
deterministic matchers consume:

* :class:`CoverageEntity` -- an institution and its surface forms, read by
  :mod:`src.matching.entity_matcher` (Tier 1 routing).

``CoverageProbe`` and its module :mod:`src.matching.coverage_probe` left with
backlog task 027 on 2026-09-22: the staleness check in ``docs/PLAN.md`` is a
query over ``routes`` ("nothing routed for N days"), not a probe match over
``articles``, and no rewritten task names a probe. See ``backlog/027-sweep.md``
for the record.

:class:`CoverageEntity` carries no loader. The JSON beat-file parsing and
validation that used to build it died with ``src/config/beats.py``; whatever
declares an entity in the new shape constructs it directly.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "COVERAGE_KINDS",
    "ENTITY_KINDS",
    "CoverageEntity",
]

# The only three things coverage may track, and the plural config key that used
# to declare each. The mapping is closed on purpose: any other key -- `people`,
# `officials`, `staff`, anything -- was a validation error rather than a
# silently ignored block, so the boundary cannot be reintroduced by convention.
COVERAGE_KINDS: dict[str, str] = {
    "orgs": "org",
    "programs": "program",
    "document_types": "document_type",
}
ENTITY_KINDS = frozenset(COVERAGE_KINDS.values())


@dataclass(frozen=True)
class CoverageEntity:
    """
    One institution being tracked: an organization, a program, or a type of
    document.

    ``kind`` is one of :data:`ENTITY_KINDS`. There is no person kind, and the
    absence is the point -- personnel rotate while offices persist, so a name
    goes dark on reassignment and the silence reads as inactivity, which is a
    wrong answer that looks like a real one. ``name`` is the canonical form
    used everywhere the entity is displayed or stored; ``aliases`` are the
    other surface forms that count as the same entity.
    """

    kind: str
    name: str
    aliases: tuple[str, ...] = ()

    @property
    def key(self) -> str:
        """Stable identity of this entity: ``kind:name``."""
        return f"{self.kind}:{self.name}"

    @property
    def terms(self) -> tuple[str, ...]:
        """
        Every surface form that counts as this entity, canonical name first.

        Deduplicated but order-preserving, so matching is deterministic
        regardless of how the source repeated itself.
        """
        seen: dict[str, None] = {}
        for term in (self.name, *self.aliases):
            seen.setdefault(term, None)
        return tuple(seen)
