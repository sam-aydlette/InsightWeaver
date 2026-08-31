"""
What a matcher is pointed at: entities and probes.

These two value objects were lifted verbatim from ``src/config/beats.py`` when
the briefing product was deleted (backlog task 012). The *beat* they used to
belong to is gone -- a beat was a subject with its own source list, and the new
shape tracks one operator's decisions instead. What survives is the pair of
descriptions the deterministic matchers consume:

* :class:`CoverageEntity` -- an institution and its surface forms, read by
  :mod:`src.matching.entity_matcher` (Tier 1 routing).
* :class:`CoverageProbe` -- one thing that actually happened plus the words any
  report of it would carry, read by :mod:`src.matching.coverage_probe` (the
  staleness check task 018 needs).

They carry no loader. The JSON beat-file parsing and validation that used to
build them died with ``src/config/beats.py``; whatever declares an entity or a
probe in the new shape constructs these directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

__all__ = [
    "COVERAGE_KINDS",
    "DEFAULT_PROBE_WINDOW_DAYS",
    "ENTITY_KINDS",
    "MIN_PROBE_EVIDENCE",
    "CoverageEntity",
    "CoverageProbe",
]

# How far either side of a probe's date a report of it is still a report of it.
# Symmetric because coverage runs both ways: a rule is trailed before it lands
# and analysed for a week after. Fourteen days is the interval the FedRAMP miss
# was measured over -- "3 incidental mentions and none within two weeks".
DEFAULT_PROBE_WINDOW_DAYS = 14

# The least evidence a probe may rest on. A probe is a claim that a match means
# the matcher saw a specific event, and one bare term cannot carry that claim:
# `FedRAMP` alone is matched by an AWS region-launch post. Two independent
# pieces of evidence -- two required terms, or one required term plus one
# `any_of` group -- is the floor. The beat-file loader used to enforce this at
# parse time; with the loader gone it stands here as the documented floor for
# whatever constructs probes next.
MIN_PROBE_EVIDENCE = 2

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


@dataclass(frozen=True)
class CoverageProbe:
    """
    One thing that actually happened, used to test whether coverage can see it.

    A probe is not a search. It is a claim of the form "an event of this
    description occurred on this date, and any report of it would carry these
    words" -- which makes an unmatched probe a statement about the source list
    rather than about the phrasing of a query.

    ``terms`` must **all** appear in the same article; each group in ``any_of``
    contributes one alternative that must appear. The two levels exist because
    a single distinctive term is too weak to be evidence and a whole headline is
    too brittle to survive a second outlet's phrasing.

    A term ending in ``*`` is a stem: ``reinstat*`` matches "reinstated" and
    "reinstatement". Without the marker a term matches whole words only. The
    marker is explicit rather than implied so that the widening is visible to
    whoever has to trust the result -- see :mod:`src.matching.coverage_probe`
    for the matching rules themselves.
    """

    date: date
    what: str
    terms: tuple[str, ...]
    any_of: tuple[tuple[str, ...], ...] = ()
    window_days: int = DEFAULT_PROBE_WINDOW_DAYS

    @property
    def window(self) -> tuple[date, date]:
        """The inclusive date range in which a report of this event counts."""
        span = timedelta(days=self.window_days)
        return self.date - span, self.date + span

    @property
    def evidence_count(self) -> int:
        """How many independent things this probe requires of an article."""
        return len(self.terms) + len(self.any_of)

    def describe(self) -> str:
        """The probe's requirement, written the way it was declared."""
        parts = [" AND ".join(self.terms)] if self.terms else []
        parts.extend("(" + " OR ".join(group) + ")" for group in self.any_of)
        return " AND ".join(parts)
