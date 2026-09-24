"""
Trigger clauses compiled to predicates.

A watch's ``triggers`` is a list of clauses; a clause may populate ``terms``,
``entities`` and ``sources``. The semantics, restated so the compiler and the
file agree (``config/watches.example.yaml`` says the same thing to the author):

* within a clause, **every** populated field must match;
* within a field, **any** value matches;
* any clause matching routes the observation, and the first that does is the
  one recorded.

``terms`` and ``entities`` compile identically, through
:func:`src.matching.entity_matcher.term_pattern` with its two load-bearing
rules: word boundaries (``CISA`` is not in ``precisa``) and the shouted-term
case rule (``BOD`` matches, ``body`` does not). There is no alias registry, so
an entity is a name until a watch needs aliases; that is its own task.
``sources`` is a case-insensitive exact match on the source's name.

The loader in ``src/position/_validate.py`` already refuses a clause that is
prose, empty, or names an unknown field, so most of what this module could
reject never reaches it. It rejects again anyway (:class:`TriggerCompileError`),
because the row it compiles came from a table that ``sqlite3`` can write to.

Added 2026-09-22 for backlog task 028.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.matching.entity_matcher import is_shouted, term_pattern
from src.position._validate import TRIGGER_FIELDS

__all__ = ["CompiledClause", "CompiledWatch", "TriggerCompileError", "compile_triggers"]


class TriggerCompileError(ValueError):
    """A stored trigger clause that cannot be compiled. Raised, never skipped."""


def _compile_names(values: Sequence[str]) -> tuple[re.Pattern[str], ...]:
    """
    One pattern per case group, as ``compile_entities`` does.

    Shouted terms (acronyms) match case-sensitively; everything else matches
    case-insensitively. Grouping them into two alternations keeps each group on
    the flag it needs.
    """
    shouted = [term_pattern(v) for v in values if v.strip() and is_shouted(v)]
    relaxed = [term_pattern(v) for v in values if v.strip() and not is_shouted(v)]
    patterns: list[re.Pattern[str]] = []
    if shouted:
        patterns.append(re.compile("|".join(shouted)))
    if relaxed:
        patterns.append(re.compile("|".join(relaxed), re.IGNORECASE))
    return tuple(patterns)


@dataclass(frozen=True)
class CompiledClause:
    """One conjunctive clause. Empty fields are not constraints."""

    index: int
    terms: tuple[re.Pattern[str], ...]
    entities: tuple[re.Pattern[str], ...]
    sources: frozenset[str]

    def matches(self, text: str, source_name: str) -> bool:
        return (
            (not self.sources or source_name.strip().lower() in self.sources)
            and (not self.terms or any(p.search(text) for p in self.terms))
            and (not self.entities or any(p.search(text) for p in self.entities))
        )


@dataclass(frozen=True)
class CompiledWatch:
    """A watch's clauses, compiled once for reuse across every observation."""

    watch_id: str
    clauses: tuple[CompiledClause, ...]

    def first_match(self, text: str, source_name: str) -> int | None:
        """The index of the first clause that fires, or None."""
        for clause in self.clauses:
            if clause.matches(text, source_name):
                return clause.index
        return None


def _strings(watch_id: str, index: int, field_name: str, raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str) or not isinstance(raw, list | tuple):
        raise TriggerCompileError(
            f"watch '{watch_id}' clause {index}: '{field_name}' must be a list of strings, "
            f"got {type(raw).__name__}"
        )
    for value in raw:
        if not isinstance(value, str):
            raise TriggerCompileError(
                f"watch '{watch_id}' clause {index}: '{field_name}' contains "
                f"{type(value).__name__} {value!r}; every entry must be a string"
            )
    return [v for v in raw if v.strip()]


def compile_triggers(watch_id: str, triggers: Iterable[Mapping[str, Any]] | None) -> CompiledWatch:
    """Compile a watch's stored ``triggers`` JSON. Raises on anything uncompilable."""
    clauses: list[CompiledClause] = []
    for index, clause in enumerate(triggers or ()):
        if not isinstance(clause, Mapping):
            raise TriggerCompileError(
                f"watch '{watch_id}' clause {index}: expected a mapping, "
                f"got {type(clause).__name__}"
            )
        unknown = sorted(set(clause) - set(TRIGGER_FIELDS))
        if unknown:
            raise TriggerCompileError(
                f"watch '{watch_id}' clause {index}: unknown field(s) {unknown}; "
                f"a clause may constrain only {list(TRIGGER_FIELDS)}"
            )
        compiled = CompiledClause(
            index=index,
            terms=_compile_names(_strings(watch_id, index, "terms", clause.get("terms"))),
            entities=_compile_names(_strings(watch_id, index, "entities", clause.get("entities"))),
            sources=frozenset(
                s.strip().lower()
                for s in _strings(watch_id, index, "sources", clause.get("sources"))
            ),
        )
        if not (compiled.terms or compiled.entities or compiled.sources):
            raise TriggerCompileError(
                f"watch '{watch_id}' clause {index} constrains nothing and would match "
                f"every observation"
            )
        clauses.append(compiled)
    if not clauses:
        raise TriggerCompileError(
            f"watch '{watch_id}' has no trigger clauses; nothing can route to it"
        )
    return CompiledWatch(watch_id=watch_id, clauses=tuple(clauses))
