"""
Deterministic alias matching for a beat's declared coverage.

No model is involved. A mention is a word-boundary regex hit for one of an
entity's declared surface forms, which makes the count reproducible from the
same articles forever and makes a wrong count debuggable by reading a regex
rather than by re-running a prompt.

Two collision hazards drive the rules here, and both are tested:

* **Substrings.** ``CISA`` sits inside ``precisa``, ``OMB`` inside ``bombing``
  and ``combat``, ``BOD`` inside ``body``, ``GSA`` inside ``Gsander``. Every
  term is therefore anchored between non-alphanumeric positions rather than
  searched for as a substring.
* **Case.** A term written entirely in capitals is an acronym, and an acronym
  is only itself when it is shouted: ``BOD`` is a directive, ``bod`` is not,
  and ``combat`` must never become a mention of ``OMB``. Such terms match
  case-sensitively. Everything else -- ``FedRAMP PMO``, ``Emergency
  Directive`` -- matches case-insensitively, because ordinary names are
  case-varied in prose and are long enough not to collide.

Nothing in this module knows what a person is, because nothing it can be
handed is one: it takes :class:`~src.matching.terms.CoverageEntity` values,
whose ``kind`` is restricted to ``org`` / ``program`` / ``document_type``.

Moved here from ``src/context/`` by backlog task 012. The beat whose coverage
it used to count is gone; the boundary and case rules below are what Tier 1
routing needs and are not re-derivable by reading the code that calls them.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from .terms import CoverageEntity

__all__ = [
    "LEFT_BOUNDARY",
    "RIGHT_BOUNDARY",
    "CompiledEntity",
    "compile_entities",
    "count_item_mentions",
    "is_shouted",
    "item_text",
    "term_pattern",
]

# What counts as "inside a word". Deliberately alphanumerics only: a hyphen or
# a slash is a boundary, so "CISA-issued" and "FedRAMP/StateRAMP" are mentions,
# while "precisa" and "bombing" are not.
_WORD_CHAR = "[0-9A-Za-z]"
LEFT_BOUNDARY = f"(?<!{_WORD_CHAR})"
RIGHT_BOUNDARY = f"(?!{_WORD_CHAR})"
# Any run of whitespace, including a line wrap, between the words of a term.
_WHITESPACE = r"\s+"

# Kept public since backlog task 010: coverage probes match their terms by the
# same rules as coverage entities, and a second boundary definition would be a
# second thing to get wrong.


def is_shouted(term: str) -> bool:
    """
    True when a term is written in capitals only -- i.e. it is an acronym.

    ``CISA``/``OMB``/``TX-RAMP`` are shouted; ``FedRAMP``/``StateRAMP``/
    ``Emergency Directive`` are not. A term with no letters at all is not
    shouted, since case cannot distinguish it from anything.
    """
    letters = [char for char in term if char.isalpha()]
    return bool(letters) and all(char.isupper() for char in letters)


def term_pattern(term: str, right_boundary: bool = True) -> str:
    """
    Regex source for one surface form.

    Runs of whitespace in the term match any run of whitespace in the text, so
    a name broken across a line wrap in the source still matches.

    ``right_boundary=False`` anchors only the left-hand side, which turns the
    term into a stem: it must still begin a word, but the word may continue.
    Coverage probes use it for ``reinstat*``; coverage entities never do,
    because an entity's surface forms are whole names.
    """
    body = _WHITESPACE.join(re.escape(token) for token in term.split())
    tail = RIGHT_BOUNDARY if right_boundary else ""
    return f"{LEFT_BOUNDARY}(?:{body}){tail}"


@dataclass(frozen=True)
class CompiledEntity:
    """One coverage entity with its surface forms compiled to regexes."""

    entity: CoverageEntity
    patterns: tuple[re.Pattern[str], ...]

    @property
    def key(self) -> str:
        return self.entity.key

    def mentioned_in(self, text: str) -> bool:
        """
        Whether any surface form of this entity appears in ``text``.

        Presence, not frequency: an article that says "CISA" nine times is one
        item that mentioned CISA, and counting the repetitions would make a
        verbose outlet look like institutional activity.
        """
        return any(pattern.search(text) for pattern in self.patterns)


def compile_entities(entities: Iterable[CoverageEntity]) -> list[CompiledEntity]:
    """
    Compile every entity's surface forms once, for reuse across all items.

    Shouted and unshouted terms are grouped into separate alternations so each
    group can carry the case flag it needs; a term that is only whitespace is
    dropped rather than compiled into a pattern that matches everywhere.
    """
    compiled: list[CompiledEntity] = []
    for entity in entities:
        shouted: list[str] = []
        relaxed: list[str] = []
        for term in entity.terms:
            if not term.strip():
                continue
            (shouted if is_shouted(term) else relaxed).append(term_pattern(term))

        patterns: list[re.Pattern[str]] = []
        if shouted:
            patterns.append(re.compile("|".join(shouted)))
        if relaxed:
            patterns.append(re.compile("|".join(relaxed), re.IGNORECASE))
        compiled.append(CompiledEntity(entity=entity, patterns=tuple(patterns)))
    return compiled


def item_text(item: Mapping[str, Any]) -> str:
    """
    The text of one curated article that alias matching reads.

    Title and body only. Author is deliberately excluded: a byline is a person,
    and feeding it to a counter that accumulates across runs is the thing this
    feature exists not to do.
    """
    title = item.get("title") or ""
    content = item.get("content") or ""
    return f"{title}\n{content}"


def count_item_mentions(compiled: Iterable[CompiledEntity], texts: Iterable[str]) -> dict[str, int]:
    """
    How many of ``texts`` mention each entity, keyed by ``CoverageEntity.key``.

    Every compiled entity gets a key, including the ones counting zero: a zero
    is an observation about a quiet office, and dropping it here would make
    "never mentioned" and "not looked for" indistinguishable downstream.
    """
    compiled = list(compiled)
    counts = {entry.key: 0 for entry in compiled}
    for text in texts:
        if not text:
            continue
        for entry in compiled:
            if entry.mentioned_in(text):
                counts[entry.key] += 1
    return counts
