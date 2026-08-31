"""
Compiling a Watch's ``triggers`` into a deterministic predicate.

**This is Tier 1, and Tier 1 is the cost control.** Every observation the system
ingests is offered to this predicate; the ones it rejects die here and are never
seen by the adjudicator, which is the only tier that calls a model. So the
property the whole architecture rests on -- notification volume scaling with the
number of live watches rather than with news volume -- is a property of the code
in this file. A predicate that is slightly too loose does not raise, does not
log an error and does not fail a test that only checks it matches what it should:
it quietly bills.

**Shape.** ``triggers`` is a disjunction of conjunctions, guaranteed by
``src.position._validate``: a list of clauses, each constraining some of
``terms`` / ``entities`` / ``sources``. Within a clause every populated field
must match (AND) and any value inside a field will do (OR); across clauses, any
clause firing fires the watch. That is exactly enough structure to compile into
two regex alternations and a set-membership test, with no interpreter and no
model in between.

**Word boundaries are load-bearing and are not re-implemented here.** Every
pattern comes from :func:`src.matching.entity_matcher.compile_terms`, which owns
``LEFT_BOUNDARY`` / ``RIGHT_BOUNDARY`` and the shouted-acronym case rule. The
numbers that justify the anchoring were measured on this repository's own
corpus: across 55,249 articles ``nist`` occurs as a substring in 5,364 titles
and at a word boundary in 73; ``mail`` is 1,842 against 339. A second matcher in
this file would be a second place for that factor-of-seventy to come back.

**Entities have no alias registry yet, and this file does not invent one.** The
beat-file loader that used to declare a :class:`CoverageEntity`'s aliases died
with the briefing product (task 012), and nothing has replaced it. So an entity
named in a trigger clause is matched by the surface form the operator wrote and
by nothing else. ``terms`` and ``entities`` therefore match by identical rules
today; they remain separate fields because they are separate *conjuncts* --
"FedRAMP PMO AND (continuous monitoring OR ConMon)" is not expressible in one
list -- and because an alias registry plugs in at exactly one place,
:func:`_entity_terms`, when one exists.

Added 2026-08-31 for backlog task 015.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..matching.entity_matcher import compile_terms, matches_any

# Imported from the validator rather than restated, so that the compiler and the
# loader cannot disagree about which three axes a clause may constrain.
from ..position._validate import TRIGGER_FIELDS

__all__ = [
    "TRIGGER_FIELDS",
    "CompiledClause",
    "CompiledWatch",
    "TriggerCompileError",
    "compile_watch",
    "compile_watches",
    "source_keys",
]


class TriggerCompileError(ValueError):
    """
    Raised when stored triggers cannot be compiled into a predicate.

    The YAML loader already rejects unusable triggers, but it is not the only
    way a row reaches ``watches.triggers`` -- a hand-edited database, a restored
    dump, or a future migration can all put JSON there. A clause that constrains
    nothing matches *every* observation, which is the single most expensive
    mistake this tier can make, so it is refused loudly here rather than
    evaluated.
    """


def _normalize_source(value: str) -> str:
    """The comparison form of a source name or URL: trimmed and case-folded."""
    return value.strip().casefold()


def source_keys(*values: str | None) -> frozenset[str]:
    """
    Every name an observation's source answers to, in comparison form.

    A ``sources`` clause is an *allowlist*, matched by equality rather than by
    substring: "Federal Register" must not be satisfied by a feed called
    "Federal Register Watch Blog". Callers pass whatever identifies the source
    -- the feed's name, the feed's URL, the ``source_url`` recorded in the
    payload -- and any one of them matching is a match.
    """
    return frozenset(_normalize_source(v) for v in values if v and v.strip())


def _entity_terms(entity: str) -> tuple[str, ...]:
    """
    The surface forms of one entity named in a trigger clause.

    Today: the name as written, and nothing else. See the module docstring --
    there is no alias registry in the repository, and inventing surface forms
    the operator did not write is how a routing predicate widens without anyone
    editing a trigger. When an alias registry lands, it lands here.
    """
    return (entity,)


@dataclass(frozen=True)
class CompiledClause:
    """
    One conjunctive clause, compiled. Evaluated with regexes and a set test.

    ``index`` is the clause's position in the watch's ``triggers`` list, so a
    routing decision can name the line of the file that produced it.
    """

    index: int
    terms: tuple[re.Pattern[str], ...]
    entities: tuple[re.Pattern[str], ...]
    sources: frozenset[str]
    declared: Mapping[str, tuple[str, ...]]

    def matches(self, text: str, observation_sources: frozenset[str]) -> bool:
        """
        Whether this clause fires. Every populated field must match.

        Order is cheapest-first: the source test is a set intersection and
        rejects a whole feed's worth of observations without touching a regex.
        """
        if self.sources and not (self.sources & observation_sources):
            return False
        if self.terms and not matches_any(self.terms, text):
            return False
        return not self.entities or matches_any(self.entities, text)

    def describe(self) -> str:
        """The clause as it was declared, for a dry-run listing."""
        parts = [
            f"{name}=[{', '.join(values)}]" for name, values in self.declared.items() if values
        ]
        return " AND ".join(parts)


@dataclass(frozen=True)
class CompiledWatch:
    """
    One watch's triggers, compiled. ``matches`` returns the clause that fired.

    Returning the clause index rather than a bool is what makes a too-loose
    trigger attributable: "watch X routed 400 observations" is a bill, "clause 2
    of watch X routed 400 observations" is a diff.
    """

    watch_id: str
    clauses: tuple[CompiledClause, ...]

    def matching_clause(self, text: str, observation_sources: frozenset[str]) -> int | None:
        """The index of the first clause that fires, or None. First in file order."""
        for clause in self.clauses:
            if clause.matches(text, observation_sources):
                return clause.index
        return None

    def matches(self, text: str, observation_sources: frozenset[str]) -> bool:
        return self.matching_clause(text, observation_sources) is not None


def _clause_values(raw: Any, field: str, label: str) -> tuple[str, ...]:
    """One field of a stored clause, as a tuple of non-blank strings."""
    value = raw.get(field)
    if value is None:
        return ()
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise TriggerCompileError(
            f"{label}: '{field}' must be a list of strings, got {type(value).__name__}. "
            f"A trigger is compiled into a predicate, so it cannot be a sentence."
        )
    values = tuple(str(item).strip() for item in value if str(item).strip())
    if value and not values:
        # The field was written down and every value in it was blank. Dropping
        # it would remove a conjunct: `{entities: [" "], terms: [FedRAMP]}`
        # reads as "FedRAMP AND some entity" and would evaluate as "FedRAMP",
        # which is a broader watch than the one on the page.
        raise TriggerCompileError(
            f"{label}: '{field}' is {list(value)} -- every entry is blank, so the constraint "
            f"would be dropped and the clause would be broader than it reads."
        )
    return values


def compile_watch(watch_id: str, triggers: Any) -> CompiledWatch:
    """
    Compile one watch's stored ``triggers`` JSON into a predicate.

    Raises :class:`TriggerCompileError` rather than skipping anything it cannot
    compile. A silently skipped clause is a watch that has stopped watching, and
    the only symptom is a staleness alert weeks later; a silently *kept* empty
    clause is a watch that matches everything. Neither is allowed to happen
    quietly.
    """
    if not isinstance(triggers, list) or not triggers:
        raise TriggerCompileError(
            f"watch '{watch_id}': triggers must be a non-empty list of clauses, got "
            f"{type(triggers).__name__}. A watch nothing can trigger never fires."
        )

    clauses: list[CompiledClause] = []
    for index, raw in enumerate(triggers):
        label = f"watch '{watch_id}' triggers[{index}]"
        if not isinstance(raw, dict):
            raise TriggerCompileError(f"{label}: expected a mapping, got {type(raw).__name__}")

        unknown = sorted(set(raw) - set(TRIGGER_FIELDS))
        if unknown:
            raise TriggerCompileError(
                f"{label}: unknown field(s) {unknown}; a clause may constrain only "
                f"{list(TRIGGER_FIELDS)}"
            )

        declared = {field: _clause_values(raw, field, label) for field in TRIGGER_FIELDS}
        if not any(declared.values()):
            raise TriggerCompileError(
                f"{label}: constrains nothing. A clause with no terms, entities or sources "
                f"matches every observation, which is the most expensive possible bug in "
                f"this tier."
            )

        terms = compile_terms(declared["terms"])
        entity_forms = [form for name in declared["entities"] for form in _entity_terms(name)]
        entities = compile_terms(entity_forms)

        # compile_terms drops blank surface forms. If a field was declared and
        # every one of its values vanished, the clause silently lost a conjunct
        # and is now broader than it reads.
        for name, compiled in (("terms", terms), ("entities", entities)):
            if declared[name] and not compiled:
                raise TriggerCompileError(
                    f"{label}: '{name}' was declared as {list(declared[name])} but compiled to "
                    f"no pattern, which would drop the constraint and widen the clause."
                )

        clauses.append(
            CompiledClause(
                index=index,
                terms=terms,
                entities=entities,
                sources=source_keys(*declared["sources"]),
                declared=declared,
            )
        )

    return CompiledWatch(watch_id=watch_id, clauses=tuple(clauses))


def compile_watches(rows: Iterable[Any]) -> list[CompiledWatch]:
    """
    Compile every watch row, in id order. One bad row fails the whole call.

    Refusing the batch is deliberate: routing half the watch set would produce a
    report that looks complete, and the watches missing from it are exactly the
    ones whose triggers are broken.
    """
    return [compile_watch(row.id, row.triggers) for row in sorted(rows, key=lambda r: r.id)]
