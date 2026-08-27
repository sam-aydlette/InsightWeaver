"""
Beat configuration loading.

A **beat** is a subject: a standing topic with its own sources. It is a
different shape from the person-shaped profile in ``config/user_profile.json``
(which models a location, a profession and a civic context), and the two
coexist -- a beat never replaces the profile and is never validated against it.
``src/utils/profile_loader.py`` is deliberately not reused here.

Source selection reuses the existing ``applicability`` tag vocabulary from
``config/feeds/*.json`` (``scope`` / ``geo_tags`` / ``domain_tags`` /
``specialty_tags``) rather than introducing a parallel selector: a beat source
declares which of those tags a feed must carry, and :class:`FeedMatcher` is the
one place feeds are read from disk.

Added 2026-08-26 for backlog task 004.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .feed_matcher import Feed, FeedMatcher

# Where beat definitions live, relative to the project root.
DEFAULT_BEATS_DIR = Path(__file__).parent.parent.parent / "config" / "beats"

# Ingestion adapters a beat source may name. An unknown adapter is an error
# rather than a silently skipped source, so a beat written against a future
# adapter fails loudly on this version.
#
# "federal_register" added 2026-08-26 (backlog task 005) alongside
# src/sources/federal_register.py. HTML scraping adapters are deliberately
# still absent -- see SOURCES.md.
SUPPORTED_ADAPTERS = frozenset({"rss", "federal_register"})

# Render channels a beat may request. These mirror src/render/.
SUPPORTED_CHANNELS = frozenset({"terminal", "markdown", "html", "email"})

BEAT_KEYS = frozenset(
    {
        "name",
        "description",
        "sources",
        "coverage",
        "standing_questions",
        "coverage_probes",
        "channels",
    }
)
REQUIRED_BEAT_KEYS = frozenset({"name", "sources"})
SOURCE_KEYS = frozenset({"adapter", "feed_tags", "geo_tags", "scope"})
REQUIRED_SOURCE_KEYS = frozenset({"adapter", "feed_tags"})

# Keys permitted on one coverage probe (backlog task 010, 2026-08-27).
PROBE_KEYS = frozenset({"date", "what", "terms", "any_of", "window_days"})
REQUIRED_PROBE_KEYS = frozenset({"date", "what", "terms"})

# How far either side of a probe's date a report of it is still a report of it.
# Symmetric because coverage runs both ways: a rule is trailed before it lands
# and analysed for a week after. Fourteen days is the interval the FedRAMP miss
# was measured over -- "3 incidental mentions and none within two weeks".
DEFAULT_PROBE_WINDOW_DAYS = 14

# The least evidence a probe may rest on. A probe is a claim that a match means
# the beat saw a specific event, and one bare term cannot carry that claim:
# `FedRAMP` alone is matched by an AWS region-launch post. Two independent
# pieces of evidence -- two required terms, or one required term plus one
# `any_of` group -- is the floor, enforced here rather than left to the author's
# judgement, because a probe that passes on generic terms manufactures exactly
# the confidence this feature exists to remove.
MIN_PROBE_EVIDENCE = 2

# The only three things a beat may track, and the plural config key that
# declares each. The mapping is closed on purpose: any other key -- `people`,
# `officials`, `staff`, anything -- is a validation error rather than a
# silently ignored block, so the boundary cannot be reintroduced by convention.
COVERAGE_KINDS: dict[str, str] = {
    "orgs": "org",
    "programs": "program",
    "document_types": "document_type",
}
ENTITY_KINDS = frozenset(COVERAGE_KINDS.values())

# Keys permitted on the long form of one coverage entry.
COVERAGE_ENTRY_KEYS = frozenset({"name", "aliases"})


class BeatNotFound(FileNotFoundError):
    """Raised when no beat file exists for the requested name."""

    def __init__(self, name: str, beats_dir: Path, available: list[str]) -> None:
        self.name = name
        self.available = available
        known = ", ".join(available) if available else "none"
        super().__init__(f"No beat named '{name}' in {beats_dir}. Available beats: {known}")


class BeatValidationError(ValueError):
    """Raised when a beat file exists but does not describe a usable beat."""

    def __init__(self, path: Path, problem: str) -> None:
        self.path = path
        self.problem = problem
        super().__init__(f"Invalid beat file {path}: {problem}")


@dataclass(frozen=True)
class BeatSource:
    """
    One source declaration inside a beat.

    ``feed_tags`` is matched against a feed's ``domain_tags`` and
    ``specialty_tags`` -- the "what is this feed about" families. ``geo_tags``
    and ``scope`` are optional narrowing constraints matched against the
    families of the same name. Within a family the match is ANY; across
    families it is ALL. An omitted family constrains nothing.

    ``adapter`` is the one family that is not optional and not a tag: a source
    declaration selects sources of one ingestion kind. Added 2026-08-26 with
    backlog task 005 -- before it, every configured source was RSS and the
    field was decoration.
    """

    adapter: str
    feed_tags: tuple[str, ...]
    geo_tags: tuple[str, ...] = ()
    scope: tuple[str, ...] = ()

    def matches(self, feed: Feed) -> bool:
        """True when ``feed`` satisfies every family this source constrains."""
        if feed.adapter != self.adapter:
            return False
        subject_tags = set(feed.domain_tags) | set(feed.specialty_tags)
        if not subject_tags & set(self.feed_tags):
            return False
        if self.geo_tags and not set(feed.geo_tags) & set(self.geo_tags):
            return False
        return not (self.scope and not set(feed.scope) & set(self.scope))


@dataclass(frozen=True)
class CoverageEntity:
    """
    One institution a beat tracks: an organization, a program, or a type of
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
        """Stable identity of this entity within a beat: ``kind:name``."""
        return f"{self.kind}:{self.name}"

    @property
    def terms(self) -> tuple[str, ...]:
        """
        Every surface form that counts as this entity, canonical name first.

        Deduplicated but order-preserving, so matching is deterministic
        regardless of how the config repeated itself.
        """
        seen: dict[str, None] = {}
        for term in (self.name, *self.aliases):
            seen.setdefault(term, None)
        return tuple(seen)


@dataclass(frozen=True)
class CoverageProbe:
    """
    One thing that actually happened, used to test whether the beat can see it.

    A probe is not a search. It is a claim of the form "an event of this
    description occurred on this date, and any report of it would carry these
    words" -- which makes an unmatched probe a statement about the beat's
    sources rather than about the phrasing of a query.

    ``terms`` must **all** appear in the same article; each group in ``any_of``
    contributes one alternative that must appear. The two levels exist because
    a single distinctive term is too weak to be evidence and a whole headline is
    too brittle to survive a second outlet's phrasing.

    A term ending in ``*`` is a stem: ``reinstat*`` matches "reinstated" and
    "reinstatement". Without the marker a term matches whole words only. The
    marker is explicit rather than implied so that the widening is visible in
    the config to whoever has to trust the result -- see
    :mod:`src.context.coverage_probe` for the matching rules themselves.
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
        """The probe's requirement, written the way the config wrote it."""
        parts = [" AND ".join(self.terms)] if self.terms else []
        parts.extend("(" + " OR ".join(group) + ")" for group in self.any_of)
        return " AND ".join(parts)


@dataclass(frozen=True)
class BeatConfig:
    """
    A loaded, validated beat definition.

    ``coverage`` is the raw block as written; ``entities`` is the same block
    parsed into :class:`CoverageEntity` values, which is what the institutional
    activity pass reads.

    ``standing_questions`` are the questions this beat declares it is watching,
    whether or not any given run's coverage mentions them. They are read by
    ``src/context/standing_agenda.py`` (backlog task 007).

    ``coverage_probes`` are known past events the beat is tested against by
    ``insightweaver beat coverage`` (backlog task 010). They are the answer to
    "can this beat reach its domain" that an article count cannot give.
    """

    name: str
    description: str
    sources: tuple[BeatSource, ...]
    coverage: dict[str, Any]
    standing_questions: tuple[str, ...]
    channels: tuple[str, ...]
    config_path: str
    entities: tuple[CoverageEntity, ...] = ()
    coverage_probes: tuple[CoverageProbe, ...] = ()

    def resolve_feeds(self, matcher: FeedMatcher | None = None) -> list[Feed]:
        """
        Every configured feed this beat's sources select, deduplicated by URL
        and ordered by descending ``relevance_score`` then name.

        This reads ``config/feeds/``, not the database: it answers "which
        sources does this beat claim", not "which of them have articles".
        """
        matcher = matcher or FeedMatcher()
        selected: dict[str, Feed] = {}
        for feed in matcher.all_feeds:
            if any(source.matches(feed) for source in self.sources):
                selected.setdefault(feed.url, feed)
        return sorted(selected.values(), key=lambda f: (-f.relevance_score, f.name))

    def resolve_feed_urls(self, matcher: FeedMatcher | None = None) -> list[str]:
        """The URLs of :meth:`resolve_feeds`, in the same order."""
        return [feed.url for feed in self.resolve_feeds(matcher)]


def available_beats(beats_dir: Path | str | None = None) -> list[str]:
    """Names of every beat file on disk, sorted."""
    directory = Path(beats_dir) if beats_dir is not None else DEFAULT_BEATS_DIR
    if not directory.is_dir():
        return []
    return sorted(path.stem for path in directory.glob("*.json"))


def load_beat(name: str, beats_dir: Path | str | None = None) -> BeatConfig:
    """
    Load and validate ``config/beats/<name>.json``.

    Fails fast: a missing file raises :class:`BeatNotFound`, and any structural
    problem raises :class:`BeatValidationError` naming the problem. A beat is
    never partially loaded and never falls back to defaults for a field the
    author got wrong.
    """
    directory = Path(beats_dir) if beats_dir is not None else DEFAULT_BEATS_DIR
    path = directory / f"{name}.json"
    if not path.is_file():
        raise BeatNotFound(name, directory, available_beats(directory))

    try:
        with open(path, encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise BeatValidationError(path, f"not valid JSON ({exc})")

    if not isinstance(raw, dict):
        raise BeatValidationError(path, "top level must be a JSON object")

    unknown = set(raw) - BEAT_KEYS
    if unknown:
        raise BeatValidationError(path, f"unknown key(s): {', '.join(sorted(unknown))}")

    missing = REQUIRED_BEAT_KEYS - set(raw)
    if missing:
        raise BeatValidationError(path, f"missing required key(s): {', '.join(sorted(missing))}")

    beat_name = raw["name"]
    if not isinstance(beat_name, str) or not beat_name.strip():
        raise BeatValidationError(path, "'name' must be a non-empty string")
    if beat_name != path.stem:
        raise BeatValidationError(
            path, f"'name' is '{beat_name}' but the file is named '{path.stem}.json'"
        )

    description = raw.get("description", "")
    if not isinstance(description, str):
        raise BeatValidationError(path, "'description' must be a string")

    sources = _parse_sources(path, raw["sources"])

    coverage = raw.get("coverage", {})
    if not isinstance(coverage, dict):
        raise BeatValidationError(path, "'coverage' must be an object")
    entities = _parse_coverage(path, coverage)

    standing_questions = _parse_standing_questions(path, raw.get("standing_questions", []))

    coverage_probes = _parse_coverage_probes(path, raw.get("coverage_probes", []))

    channels = _parse_channels(path, raw.get("channels", ["terminal"]))

    return BeatConfig(
        name=beat_name,
        description=description,
        sources=sources,
        coverage=coverage,
        standing_questions=tuple(standing_questions),
        channels=channels,
        config_path=str(path),
        entities=entities,
        coverage_probes=coverage_probes,
    )


def _parse_coverage_probes(path: Path, raw_probes: Any) -> tuple[CoverageProbe, ...]:
    """
    Validate the ``coverage_probes`` block into :class:`CoverageProbe` values.

    Every rule here refuses a probe rather than repairing it. A probe is
    evidence about whether the beat's sources reach its domain, and a probe
    that was quietly loosened -- an unparseable date defaulted to today, a
    single generic term accepted -- would answer the question with something
    other than what the author wrote.
    """
    if not isinstance(raw_probes, list):
        raise BeatValidationError(path, "'coverage_probes' must be a list of objects")

    parsed: list[CoverageProbe] = []
    for index, entry in enumerate(raw_probes):
        where = f"coverage_probes[{index}]"
        if not isinstance(entry, dict):
            raise BeatValidationError(path, f"{where} must be an object, got {entry!r}")

        unknown = set(entry) - PROBE_KEYS
        if unknown:
            supported = ", ".join(sorted(PROBE_KEYS))
            raise BeatValidationError(
                path,
                f"{where} has unknown key(s): {', '.join(sorted(unknown))} (supported: {supported})",
            )
        missing = REQUIRED_PROBE_KEYS - set(entry)
        if missing:
            raise BeatValidationError(
                path, f"{where} missing required key(s): {', '.join(sorted(missing))}"
            )

        raw_date = entry["date"]
        if not isinstance(raw_date, str):
            raise BeatValidationError(path, f"{where}.date must be a 'YYYY-MM-DD' string")
        try:
            when = date.fromisoformat(raw_date)
        except ValueError:
            raise BeatValidationError(
                path, f"{where}.date is not a 'YYYY-MM-DD' date: {raw_date!r}"
            )

        what = entry["what"]
        if not isinstance(what, str) or not what.strip():
            raise BeatValidationError(
                path, f"{where}.what must be a non-empty description of the event"
            )

        terms = _parse_probe_terms(path, f"{where}.terms", entry["terms"])
        if not terms:
            raise BeatValidationError(path, f"{where}.terms must not be empty")

        raw_any_of = entry.get("any_of", [])
        if not isinstance(raw_any_of, list):
            raise BeatValidationError(path, f"{where}.any_of must be a list of term lists")
        any_of: list[tuple[str, ...]] = []
        for group_index, group in enumerate(raw_any_of):
            alternatives = _parse_probe_terms(
                path, f"{where}.any_of[{group_index}]", group, allow_bare_string=False
            )
            if not alternatives:
                raise BeatValidationError(
                    path,
                    f"{where}.any_of[{group_index}] must not be empty -- an empty group of "
                    f"alternatives is satisfied by nothing and would make the probe unmatchable",
                )
            any_of.append(alternatives)

        window_days = entry.get("window_days", DEFAULT_PROBE_WINDOW_DAYS)
        if not isinstance(window_days, int) or isinstance(window_days, bool) or window_days < 1:
            raise BeatValidationError(
                path, f"{where}.window_days must be a positive integer, got {window_days!r}"
            )

        probe = CoverageProbe(
            date=when,
            what=what.strip(),
            terms=terms,
            any_of=tuple(any_of),
            window_days=window_days,
        )
        if probe.evidence_count < MIN_PROBE_EVIDENCE:
            raise BeatValidationError(
                path,
                f"{where} rests on a single term ({terms[0]!r}). A probe needs at least "
                f"{MIN_PROBE_EVIDENCE} independent requirements -- another entry in 'terms', "
                f"or an 'any_of' group -- because one term on its own is matched by articles "
                f"that merely mention the subject, and a probe that passes on a passing "
                f"mention is worse than no probe.",
            )
        parsed.append(probe)

    return tuple(parsed)


def _parse_probe_terms(
    path: Path, where: str, value: Any, allow_bare_string: bool = True
) -> tuple[str, ...]:
    """Validate one list of probe terms, order-preserving and deduplicated."""
    if allow_bare_string and isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        raise BeatValidationError(path, f"{where} must be a list of strings")

    seen: dict[str, None] = {}
    for term in value:
        if not isinstance(term, str) or not term.strip():
            raise BeatValidationError(
                path, f"{where} must contain only non-empty strings, got {term!r}"
            )
        stripped = term.strip()
        if stripped.rstrip("*") == "":
            raise BeatValidationError(
                path,
                f"{where} contains {term!r}, which is a stem marker with no stem and "
                f"would match every article",
            )
        seen.setdefault(stripped, None)
    return tuple(seen)


def _parse_coverage(path: Path, coverage: dict[str, Any]) -> tuple[CoverageEntity, ...]:
    """
    Validate the ``coverage`` block into :class:`CoverageEntity` values.

    A beat tracks institutions, not people. ``coverage`` holds orgs, programs
    and document types; a ``people`` key is refused here rather than ignored so
    the boundary is enforced by the loader and cannot be reintroduced by
    convention. This repository is public and covers a domain the operator
    works in: a per-person activity ledger would read as surveillance of
    colleagues regardless of the mechanism, and offices are the better signal
    anyway since personnel rotate.

    The `people` rejection is checked before the general unknown-key check so
    that the specific reason is the one the author reads.
    """
    if "people" in coverage:
        raise BeatValidationError(
            path,
            "'coverage.people' is not supported: a beat tracks organizations, programs "
            "and document types, never individuals. A named person may appear as an "
            "attribute of a specific document, never as an accumulated record.",
        )

    unknown = set(coverage) - set(COVERAGE_KINDS)
    if unknown:
        supported = ", ".join(sorted(COVERAGE_KINDS))
        raise BeatValidationError(
            path,
            f"'coverage' has unknown key(s): {', '.join(sorted(unknown))} "
            f"(supported: {supported}). A beat tracks organizations, programs and "
            f"document types, never individuals.",
        )

    parsed: list[CoverageEntity] = []
    seen: set[str] = set()
    for block, kind in COVERAGE_KINDS.items():
        raw_entries = coverage.get(block, [])
        if not isinstance(raw_entries, list):
            raise BeatValidationError(path, f"'coverage.{block}' must be a list")
        for index, entry in enumerate(raw_entries):
            entity = _parse_coverage_entry(path, f"coverage.{block}[{index}]", kind, entry)
            if entity.key in seen:
                raise BeatValidationError(
                    path, f"'coverage.{block}' declares '{entity.name}' more than once"
                )
            seen.add(entity.key)
            parsed.append(entity)

    return tuple(parsed)


def _parse_coverage_entry(path: Path, where: str, kind: str, entry: Any) -> CoverageEntity:
    """
    Validate one coverage entry, in either the short or the long form.

    Short form is a bare string -- the canonical name, matched on its own.
    Long form is ``{"name": ..., "aliases": [...]}``. Any other key is an
    error: a coverage entry describes an institution and its surface forms,
    and there is nothing else for it to carry.
    """
    if isinstance(entry, str):
        name = entry
        aliases: tuple[str, ...] = ()
    elif isinstance(entry, dict):
        unknown = set(entry) - COVERAGE_ENTRY_KEYS
        if unknown:
            supported = ", ".join(sorted(COVERAGE_ENTRY_KEYS))
            raise BeatValidationError(
                path,
                f"{where} has unknown key(s): {', '.join(sorted(unknown))} "
                f"(supported: {supported})",
            )
        if "name" not in entry:
            raise BeatValidationError(path, f"{where} is missing required key 'name'")
        name = entry["name"]
        raw_aliases = entry.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raise BeatValidationError(path, f"{where}.aliases must be a list of strings")
        for alias in raw_aliases:
            if not isinstance(alias, str) or not alias.strip():
                raise BeatValidationError(
                    path, f"{where}.aliases must contain only non-empty strings, got {alias!r}"
                )
        aliases = tuple(alias.strip() for alias in raw_aliases)
    else:
        raise BeatValidationError(
            path, f"{where} must be a string or an object with a 'name', got {entry!r}"
        )

    if not isinstance(name, str) or not name.strip():
        raise BeatValidationError(path, f"{where} must have a non-empty 'name'")

    return CoverageEntity(kind=kind, name=name.strip(), aliases=aliases)


def _parse_sources(path: Path, raw_sources: Any) -> tuple[BeatSource, ...]:
    """Validate the ``sources`` block into :class:`BeatSource` values."""
    if not isinstance(raw_sources, list) or not raw_sources:
        raise BeatValidationError(path, "'sources' must be a non-empty list")

    parsed: list[BeatSource] = []
    for index, entry in enumerate(raw_sources):
        where = f"sources[{index}]"
        if not isinstance(entry, dict):
            raise BeatValidationError(path, f"{where} must be an object")

        unknown = set(entry) - SOURCE_KEYS
        if unknown:
            raise BeatValidationError(
                path, f"{where} has unknown key(s): {', '.join(sorted(unknown))}"
            )
        missing = REQUIRED_SOURCE_KEYS - set(entry)
        if missing:
            raise BeatValidationError(
                path, f"{where} missing required key(s): {', '.join(sorted(missing))}"
            )

        adapter = entry["adapter"]
        if adapter not in SUPPORTED_ADAPTERS:
            supported = ", ".join(sorted(SUPPORTED_ADAPTERS))
            raise BeatValidationError(
                path, f"{where} adapter '{adapter}' is not supported (supported: {supported})"
            )

        parsed.append(
            BeatSource(
                adapter=adapter,
                feed_tags=_parse_tag_list(path, where, "feed_tags", entry["feed_tags"], True),
                geo_tags=_parse_tag_list(path, where, "geo_tags", entry.get("geo_tags", []), False),
                scope=_parse_tag_list(path, where, "scope", entry.get("scope", []), False),
            )
        )

    return tuple(parsed)


def _parse_standing_questions(path: Path, raw_questions: Any) -> tuple[str, ...]:
    """
    Validate the ``standing_questions`` block into a tuple of question texts.

    A standing question is declared by a human, deliberately (added 2026-08-26
    for backlog task 007). This loader therefore never invents one and never
    drops one it cannot parse. Duplicates are refused rather than silently
    deduplicated: two identical declarations mean the author has lost track of
    the agenda, and collapsing them would hide that.
    """
    if not isinstance(raw_questions, list):
        raise BeatValidationError(path, "'standing_questions' must be a list of strings")

    parsed: list[str] = []
    seen: set[str] = set()
    for index, entry in enumerate(raw_questions):
        where = f"standing_questions[{index}]"
        if not isinstance(entry, str) or not entry.strip():
            raise BeatValidationError(path, f"{where} must be a non-empty string, got {entry!r}")
        text = entry.strip()
        key = text.casefold()
        if key in seen:
            raise BeatValidationError(
                path, f"{where} duplicates an earlier standing question: {text!r}"
            )
        seen.add(key)
        parsed.append(text)
    return tuple(parsed)


def _parse_tag_list(
    path: Path, where: str, field: str, value: Any, required_non_empty: bool
) -> tuple[str, ...]:
    """Validate one tag family into a tuple of non-empty strings."""
    if not isinstance(value, list):
        raise BeatValidationError(path, f"{where}.{field} must be a list of strings")
    if required_non_empty and not value:
        raise BeatValidationError(path, f"{where}.{field} must not be empty")
    for tag in value:
        if not isinstance(tag, str) or not tag.strip():
            raise BeatValidationError(
                path, f"{where}.{field} must contain only non-empty strings, got {tag!r}"
            )
    return tuple(value)


def _parse_channels(path: Path, raw_channels: Any) -> tuple[str, ...]:
    """Validate the ``channels`` block."""
    if not isinstance(raw_channels, list) or not raw_channels:
        raise BeatValidationError(path, "'channels' must be a non-empty list")
    for channel in raw_channels:
        if channel not in SUPPORTED_CHANNELS:
            supported = ", ".join(sorted(SUPPORTED_CHANNELS))
            raise BeatValidationError(path, f"unknown channel {channel!r} (supported: {supported})")
    return tuple(raw_channels)
