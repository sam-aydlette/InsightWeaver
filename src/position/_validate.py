"""
Field-by-field validation for a hand-authored watch set.

Split out of :mod:`src.position.watches` on 2026-08-31 to keep both files
inside the repository's 200-300 line rule. The split is along a real seam:
everything here takes a raw YAML value and either appends a sentence to
``problems`` or returns a clean value, and nothing here touches the database or
the file system.

**Every function in this module rejects rather than defaults.** That is the
whole point of the module. The deleted prediction ledger accumulated 25
unfalsifiable rows because a missing field was tolerated at every layer that
could have refused it, and the fix is not better review -- it is a validator
that has no branch in which a blank field survives.

Problems accumulate rather than raising, so a hand-edited file reports all of
its errors in one run. The caller raises once, before anything is written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.utils.cadence import InvalidCadence, parse_cadence

from .position import Position, _as_date, _is_blank

__all__ = [
    "SO_WHAT_KEYS",
    "TRIGGER_FIELDS",
    "WATCH_KEYS",
    "TriggerClause",
    "validate_watch",
]

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

WATCH_KEYS = {
    "id",
    "claim",
    "belief",
    "so_what",
    "triggers",
    "expires",
    "staleness_alert_days",
}
SO_WHAT_KEYS = {"decision", "because"}

# The only three axes a trigger clause may constrain. Each maps onto something
# Tier 1 can evaluate without a model: a word-boundary term match, an entity's
# declared surface forms, and the adapter that produced the observation.
TRIGGER_FIELDS = ("terms", "entities", "sources")


@dataclass(frozen=True)
class TriggerClause:
    """
    One conjunctive clause of a trigger.

    A clause fires when every field it populates matches: any of its ``terms``
    appears, **and** any of its ``entities`` appears, **and** the observation
    came from one of its ``sources``. Fields left out are not constraints. The
    watch fires when any clause fires, so ``triggers`` as a whole is a
    disjunction of conjunctions -- expressive enough to say "FedRAMP *and*
    continuous monitoring, or anything about it in the Federal Register", and
    small enough that Tier 1 compiles it to regexes and a set membership test
    with no interpreter in between.
    """

    terms: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, list[str]]:
        """The JSON shape stored in ``watches.triggers``. Empty fields are omitted."""
        return {name: list(getattr(self, name)) for name in TRIGGER_FIELDS if getattr(self, name)}


def _validate_so_what(
    label: str, raw: Any, position: Position, problems: list[str]
) -> tuple[str, str] | None:
    """
    Invariant 2, enforced. Returns ``(decision_key, because)`` or None.

    Every branch here rejects. None of them defaults, substitutes a placeholder,
    or falls back to the claim text -- a Watch with no articulable decision is
    curiosity, and the point of the invariant is that curiosity does not get
    stored and then quietly alert.
    """
    if raw is None:
        problems.append(
            f"{label}: 'so_what' is required and names the decision this watch serves. "
            f"A watch with no decision attached is curiosity, not monitoring."
        )
        return None
    if isinstance(raw, str):
        if not raw.strip():
            problems.append(
                f"{label}: 'so_what' is empty. It must name a decision from the Position and "
                f"say what changes; blank is rejected, never defaulted."
            )
        else:
            problems.append(
                f"{label}: 'so_what' must be a mapping of 'decision' (a key from the Position) "
                f"and 'because' (what changes), not a bare string."
            )
        return None
    if not isinstance(raw, dict):
        problems.append(f"{label}: 'so_what' must be a mapping, got {type(raw).__name__}")
        return None

    unknown = sorted(set(raw) - SO_WHAT_KEYS)
    if unknown:
        problems.append(
            f"{label}: so_what has unknown field(s) {unknown}; allowed: ['because', 'decision']"
        )

    decision_key = raw.get("decision")
    because = raw.get("because")
    ok = True

    if _is_blank(decision_key):
        problems.append(
            f"{label}: so_what.decision is required and must name a decision key from the "
            f"Position. Known keys: {sorted(position.decision_keys)}"
        )
        ok = False
    elif str(decision_key).strip() not in position.decision_keys:
        problems.append(
            f"{label}: so_what.decision '{str(decision_key).strip()}' names no decision in "
            f"{position.path}. Known keys: {sorted(position.decision_keys)}. Add the decision "
            f"to the Position, or drop the watch."
        )
        ok = False

    if _is_blank(because):
        problems.append(
            f"{label}: so_what.because is required and must be a non-empty sentence saying what "
            f"changes for that decision if the claim resolves."
        )
        ok = False

    if not ok:
        return None
    return str(decision_key).strip(), str(because).strip()


def _validate_string_list(
    label: str, field_name: str, raw: Any, problems: list[str]
) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        problems.append(
            f"{label}: trigger '{field_name}' must be a list of terms, not a string. "
            f"A trigger is compiled into a predicate, so it cannot be a sentence."
        )
        return ()
    if not isinstance(raw, list):
        problems.append(f"{label}: trigger '{field_name}' must be a list, got {type(raw).__name__}")
        return ()
    values: list[str] = []
    for item in raw:
        if _is_blank(item):
            problems.append(f"{label}: trigger '{field_name}' contains an empty entry")
            continue
        values.append(str(item).strip())
    return tuple(values)


def _validate_triggers(label: str, raw: Any, problems: list[str]) -> tuple[TriggerClause, ...]:
    """
    Structure, not prose. Every rejection here is a rejection of prose.

    ``trigger_condition`` in the deleted ledger accepted free text, and 33 rows
    were written against it and graded zero times, because nothing downstream
    could evaluate a sentence. Tier 1 compiles these clauses; a clause it cannot
    compile is refused at the door rather than stored and skipped.
    """
    if raw is None:
        problems.append(
            f"{label}: 'triggers' is required -- what observation would be candidate evidence?"
        )
        return ()
    if isinstance(raw, str):
        problems.append(
            f"{label}: 'triggers' is prose. It must be a list of clauses over "
            f"{list(TRIGGER_FIELDS)}, because Tier 1 compiles triggers into a deterministic "
            f"predicate and cannot compile a sentence."
        )
        return ()
    if not isinstance(raw, list):
        problems.append(f"{label}: 'triggers' must be a list, got {type(raw).__name__}")
        return ()
    if not raw:
        problems.append(f"{label}: 'triggers' is empty -- a watch nothing can trigger never fires")
        return ()

    clauses: list[TriggerClause] = []
    for index, entry in enumerate(raw):
        clause_label = f"{label}.triggers[{index}]"
        if isinstance(entry, str):
            problems.append(
                f"{clause_label}: a trigger clause is a mapping over {list(TRIGGER_FIELDS)}, "
                f"not the sentence {entry.strip()[:60]!r}. Prose triggers are what left 33 "
                f"predictions ungradeable; write the terms and entities that would match."
            )
            continue
        if not isinstance(entry, dict):
            problems.append(f"{clause_label}: expected a mapping, got {type(entry).__name__}")
            continue
        unknown = sorted(set(entry) - set(TRIGGER_FIELDS))
        if unknown:
            problems.append(
                f"{clause_label}: unknown field(s) {unknown}; a clause may constrain only "
                f"{list(TRIGGER_FIELDS)}"
            )
            continue
        clause = TriggerClause(
            terms=_validate_string_list(clause_label, "terms", entry.get("terms"), problems),
            entities=_validate_string_list(
                clause_label, "entities", entry.get("entities"), problems
            ),
            sources=_validate_string_list(clause_label, "sources", entry.get("sources"), problems),
        )
        if not (clause.terms or clause.entities or clause.sources):
            problems.append(
                f"{clause_label}: constrains nothing. A clause with no terms, entities or "
                f"sources matches every observation."
            )
            continue
        clauses.append(clause)
    return tuple(clauses)


def _validate_belief(label: str, raw: Any, problems: list[str]) -> float | None:
    if raw is None:
        problems.append(f"{label}: 'belief' is required -- a probability in [0.0, 1.0]")
        return None
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        problems.append(f"{label}: belief must be a number in [0.0, 1.0], got {raw!r}")
        return None
    value = float(raw)
    if not (0.0 <= value <= 1.0):
        problems.append(f"{label}: belief {value} is outside [0.0, 1.0]")
        return None
    return value


def _validate_staleness(label: str, raw: Any, problems: list[str]) -> int | None:
    """
    Days, written as an integer or as a cadence (``2w``, ``30d``).

    The cadence spelling goes through :mod:`src.utils.cadence` rather than a
    second parser, so the whole system reads one interval grammar.
    """
    if raw is None:
        problems.append(
            f"{label}: 'staleness_alert_days' is required -- after how much silence is the "
            f"silence itself the finding?"
        )
        return None
    if isinstance(raw, bool):
        problems.append(
            f"{label}: staleness_alert_days must be a whole number of days, got {raw!r}"
        )
        return None
    if isinstance(raw, str):
        try:
            days = parse_cadence(raw).days
        except InvalidCadence as exc:
            problems.append(f"{label}: staleness_alert_days {raw!r} is not an interval -- {exc}")
            return None
    elif isinstance(raw, int):
        days = raw
    else:
        problems.append(
            f"{label}: staleness_alert_days must be a whole number of days, got {raw!r}"
        )
        return None
    if days < 1:
        problems.append(
            f"{label}: staleness_alert_days is {days}; it must be at least 1. Zero would make "
            f"every watch stale the moment it is loaded."
        )
        return None
    return days


def validate_watch(
    index: int,
    raw: Any,
    position: Position,
    seen: set[str],
    today: date,
    problems: list[str],
) -> dict[str, Any] | None:
    """
    One watch entry, validated. Returns constructor keywords, or None.

    It returns keywords rather than a :class:`~src.position.watches.Watch`
    deliberately: the validator would otherwise have to import the type from the
    module that imports it, and the loader is the right place for construction
    anyway -- validation decides whether a watch is admissible, the loader is
    what admits it.
    """
    label = f"watches[{index}]"
    if not isinstance(raw, dict):
        problems.append(f"{label}: expected a mapping, got {type(raw).__name__}")
        return None

    watch_id = raw.get("id")
    if _is_blank(watch_id):
        problems.append(f"{label}: 'id' is required and must be a non-empty string")
        watch_id = None
    elif not _ID_RE.match(str(watch_id).strip()):
        problems.append(
            f"{label}: id '{watch_id}' is not a slug -- lowercase letters, digits, '-', '_', '.'"
        )
        watch_id = None
    else:
        watch_id = str(watch_id).strip()
        if watch_id in seen:
            problems.append(f"{label}: duplicate watch id '{watch_id}'")
            watch_id = None
        else:
            seen.add(watch_id)

    label = f"watches[{index}]" if watch_id is None else f"watch '{watch_id}'"

    unknown = sorted(set(raw) - WATCH_KEYS)
    if unknown:
        problems.append(f"{label}: unknown field(s) {unknown}; allowed: {sorted(WATCH_KEYS)}")

    claim = raw.get("claim")
    if _is_blank(claim):
        problems.append(f"{label}: 'claim' is required and must be a non-empty string")

    belief = _validate_belief(label, raw.get("belief"), problems)
    so_what = _validate_so_what(label, raw.get("so_what"), position, problems)
    triggers = _validate_triggers(label, raw.get("triggers"), problems)
    staleness = _validate_staleness(label, raw.get("staleness_alert_days"), problems)

    expires = None
    if "expires" not in raw or raw.get("expires") is None:
        problems.append(
            f"{label}: 'expires' is required -- a watch with no end date outlives the decision "
            f"it serves and becomes a subscription."
        )
    else:
        expires = _as_date(raw.get("expires"))
        if expires is None:
            problems.append(f"{label}: expires {raw.get('expires')!r} is not a date (YYYY-MM-DD)")
        elif expires < today:
            problems.append(
                f"{label}: expires {expires.isoformat()} is in the past "
                f"({(today - expires).days}d ago). Extend it or delete the watch."
            )
            expires = None

    if (
        watch_id is None
        or _is_blank(claim)
        or belief is None
        or so_what is None
        or not triggers
        or expires is None
        or staleness is None
    ):
        return None

    decision_key, because = so_what
    return {
        "id": watch_id,
        "claim": str(claim).strip(),
        "belief": belief,
        "decision_key": decision_key,
        "so_what": because,
        "triggers": triggers,
        "expires": expires,
        "staleness_alert_days": staleness,
    }
