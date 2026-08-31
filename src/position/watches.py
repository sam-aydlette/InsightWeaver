"""
Watch: one pre-registered claim, the decision it serves, and what would move it.

A Watch is the atomic unit of the monitoring system. It says what the operator
believes (``claim`` + ``belief``), which decision that belief bears on
(``so_what``), what evidence would be candidate evidence (``triggers``), when
the question stops mattering (``expires``), and how long silence is allowed to
run before silence itself is the finding (``staleness_alert_days``).

Three shape decisions, each made against a specific thing this repository has
already got wrong:

**Watch is a new table, not an evolution of Decision + Factor.** The audit found
``decision_factors.what_would_update_me`` was a trigger, ``.current_state_note``
a belief state, and ``decisions.name`` what ``so_what`` points at -- all of it
holding zero rows, all of it dropped by task 012. So there is nothing to evolve:
the choice is not between two live models but between a clean shape and a
resurrection. What is worth carrying forward is why the old one stayed empty --
it was prose all the way down, so nothing could be computed from it and nothing
ever was. ``belief`` is a float here and ``triggers`` is structured for exactly
that reason. Decision does survive, in Position, where it belongs: it is an
operator commitment, not a database row the system writes.

**``so_what`` is a key plus prose, not prose alone.** It is a mapping of
``decision`` (a key into the Position's decisions) and ``because`` (the sentence
naming what changes). The key makes invariant 2 machine-checkable and makes
"which watches serve this decision" a query; the prose is what makes the answer
readable. An invariant enforced only by prose is the pattern the repository
spent the week correcting -- the ledger accumulated 25 unfalsifiable predictions
because a field was tolerated empty.

**``triggers`` is structured and must stay that way.** It is a list of clauses
over ``terms``, ``entities`` and ``sources`` -- the three things Tier 1 can
compile into a deterministic word-boundary predicate. A prose trigger cannot be
compiled, and the repository has the receipt: 33 predictions were written
against a free-text ``trigger_condition`` and graded zero times. A clause that
is a sentence is rejected here, loudly, by name.

The file itself lives beside Position in the private repo, for the same reason:
a watch names a real claim about a real exposure. This repo carries the schema
and ``config/watches.example.yaml``.

Nothing in this module creates a Watch from anything but the file. There is no
constructor path from a model response, a candidate, or a CLI argument, because
invariant 6 says the system never authors its own watches, and the way that
invariant is lost is one convenient write path at a time.

Added 2026-08-31 for backlog task 013.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from src.utils.cadence import InvalidCadence, parse_cadence

from .position import Position, _as_date, _is_blank

__all__ = [
    "TRIGGER_FIELDS",
    "TriggerClause",
    "Watch",
    "WatchError",
    "load_watches",
    "sync_watches",
]

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

_TOP_LEVEL_KEYS = {"version", "watches"}
_WATCH_KEYS = {
    "id",
    "claim",
    "belief",
    "so_what",
    "triggers",
    "expires",
    "staleness_alert_days",
}
_SO_WHAT_KEYS = {"decision", "because"}

# The only three axes a trigger clause may constrain. Each maps onto something
# Tier 1 can evaluate without a model: a word-boundary term match, an entity's
# declared surface forms, and the adapter that produced the observation.
TRIGGER_FIELDS = ("terms", "entities", "sources")


class WatchError(ValueError):
    """
    Raised when a watches file cannot be read as watches.

    Like :class:`~src.position.position.PositionError`, it carries every problem
    found rather than the first, and it is raised **before anything is written**:
    a file with one bad watch stores none of its watches, so the table never
    holds a half-applied file.
    """

    def __init__(self, path: Path, problems: list[str]) -> None:
        self.path = path
        self.problems = list(problems)
        body = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"{path} is not a valid watch set:\n{body}")


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


@dataclass(frozen=True)
class Watch:
    """One pre-registered claim. Constructed only by :func:`load_watches`."""

    id: str
    claim: str
    belief: float
    decision_key: str
    so_what: str
    triggers: tuple[TriggerClause, ...]
    expires: date
    staleness_alert_days: int
    source_path: Path | None = field(default=None, compare=False)

    def days_to_expiry(self, today: date) -> int:
        return (self.expires - today).days

    def triggers_json(self) -> list[dict[str, list[str]]]:
        return [clause.as_dict() for clause in self.triggers]


def default_watches_path() -> Path:
    """Where the watch set lives when nothing says otherwise."""
    from src.config.settings import settings

    return Path(settings.watches_path).expanduser()


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

    unknown = sorted(set(raw) - _SO_WHAT_KEYS)
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


def _validate_watch(
    index: int,
    raw: Any,
    position: Position,
    seen: set[str],
    today: date,
    problems: list[str],
) -> Watch | None:
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

    unknown = sorted(set(raw) - _WATCH_KEYS)
    if unknown:
        problems.append(f"{label}: unknown field(s) {unknown}; allowed: {sorted(_WATCH_KEYS)}")

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
    return Watch(
        id=watch_id,
        claim=str(claim).strip(),
        belief=belief,
        decision_key=decision_key,
        so_what=because,
        triggers=triggers,
        expires=expires,
        staleness_alert_days=staleness,
    )


def load_watches(
    path: str | Path | None = None,
    *,
    position: Position,
    today: date | None = None,
) -> list[Watch]:
    """
    Read and validate the watch set against a loaded Position.

    Raises :class:`FileNotFoundError` if the file is absent and
    :class:`WatchError` listing every problem otherwise. It never returns a
    partially valid set: if any watch is rejected, the call raises and the
    caller has nothing to store.
    """
    target = Path(path).expanduser() if path is not None else default_watches_path()
    if not target.exists():
        raise FileNotFoundError(
            f"No watch set at {target}. Watches live beside Position in your private repo; "
            f"point WATCHES_PATH at it, or start from config/watches.example.yaml."
        )

    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise WatchError(target, [f"file is not valid YAML: {exc}"])

    if raw is None:
        raise WatchError(target, ["file is empty"])
    if not isinstance(raw, dict):
        raise WatchError(target, [f"expected a mapping at the top level, got {type(raw).__name__}"])

    problems: list[str] = []
    unknown = sorted(set(raw) - _TOP_LEVEL_KEYS)
    if unknown:
        problems.append(f"unknown top-level field(s) {unknown}; allowed: {sorted(_TOP_LEVEL_KEYS)}")

    entries = raw.get("watches")
    watches: list[Watch] = []
    if entries is None:
        problems.append("'watches' is required")
    elif not isinstance(entries, list):
        problems.append(f"'watches' must be a list, got {type(entries).__name__}")
    else:
        seen: set[str] = set()
        stamp = today or date.today()
        for index, entry in enumerate(entries):
            watch = _validate_watch(index, entry, position, seen, stamp, problems)
            if watch is not None:
                watches.append(watch)

    if problems:
        raise WatchError(target, problems)

    return [
        Watch(
            id=w.id,
            claim=w.claim,
            belief=w.belief,
            decision_key=w.decision_key,
            so_what=w.so_what,
            triggers=w.triggers,
            expires=w.expires,
            staleness_alert_days=w.staleness_alert_days,
            source_path=target,
        )
        for w in watches
    ]


def sync_watches(session: Any, watches: list[Watch]) -> dict[str, list[str]]:
    """
    Make the ``watches`` table match the file, and report what moved.

    The file is authoritative: a watch removed from it is removed from the
    table. That is the whole write path -- there is no other way a row gets into
    this table, and there is deliberately no argument by which a caller could
    describe a watch that is not in the file.

    Takes already-validated :class:`Watch` values, so an invalid file cannot
    reach this function at all.
    """
    from src.database.models import Watch as WatchRow

    incoming = {w.id: w for w in watches}
    existing = {row.id: row for row in session.query(WatchRow).all()}

    summary: dict[str, list[str]] = {"added": [], "updated": [], "removed": []}

    for watch_id, watch in incoming.items():
        row = existing.get(watch_id)
        if row is None:
            session.add(
                WatchRow(
                    id=watch.id,
                    claim=watch.claim,
                    belief=watch.belief,
                    so_what=watch.so_what,
                    decision_key=watch.decision_key,
                    triggers=watch.triggers_json(),
                    expires=watch.expires,
                    staleness_alert_days=watch.staleness_alert_days,
                )
            )
            summary["added"].append(watch_id)
            continue
        row.claim = watch.claim
        row.belief = watch.belief
        row.so_what = watch.so_what
        row.decision_key = watch.decision_key
        row.triggers = watch.triggers_json()
        row.expires = watch.expires
        row.staleness_alert_days = watch.staleness_alert_days
        summary["updated"].append(watch_id)

    for watch_id, row in existing.items():
        if watch_id not in incoming:
            session.delete(row)
            summary["removed"].append(watch_id)

    session.flush()
    return summary
