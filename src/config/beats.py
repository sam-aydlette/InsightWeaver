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
    {"name", "description", "sources", "coverage", "standing_questions", "channels"}
)
REQUIRED_BEAT_KEYS = frozenset({"name", "sources"})
SOURCE_KEYS = frozenset({"adapter", "feed_tags", "geo_tags", "scope"})
REQUIRED_SOURCE_KEYS = frozenset({"adapter", "feed_tags"})


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
class BeatConfig:
    """
    A loaded, validated beat definition.

    ``coverage`` and ``standing_questions`` are reserved: they are validated
    for shape so that backlog tasks 006 and 007 need no schema migration, but
    nothing in this codebase reads them yet.
    """

    name: str
    description: str
    sources: tuple[BeatSource, ...]
    coverage: dict[str, Any]
    standing_questions: tuple[Any, ...]
    channels: tuple[str, ...]
    config_path: str

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
        raise BeatValidationError(path, "'coverage' must be an object (reserved for task 006)")
    # A beat tracks institutions, not people. `coverage` will hold orgs, programs and
    # document types (task 006); a `people` key is refused here rather than ignored so
    # the boundary is enforced by the loader and cannot be reintroduced by convention.
    # This repository is public and covers a domain the operator works in: a per-person
    # activity ledger would read as surveillance of colleagues regardless of the
    # mechanism, and offices are the better signal anyway since personnel rotate.
    if "people" in coverage:
        raise BeatValidationError(
            path,
            "'coverage.people' is not supported: a beat tracks organizations, programs "
            "and document types, never individuals. A named person may appear as an "
            "attribute of a specific document, never as an accumulated record.",
        )

    standing_questions = raw.get("standing_questions", [])
    if not isinstance(standing_questions, list):
        raise BeatValidationError(
            path, "'standing_questions' must be a list (reserved for task 007)"
        )

    channels = _parse_channels(path, raw.get("channels", ["terminal"]))

    return BeatConfig(
        name=beat_name,
        description=description,
        sources=sources,
        coverage=coverage,
        standing_questions=tuple(standing_questions),
        channels=channels,
        config_path=str(path),
    )


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
