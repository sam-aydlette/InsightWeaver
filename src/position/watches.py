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
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from ._validate import TRIGGER_FIELDS, TriggerClause, validate_watch
from .position import Position

__all__ = [
    "TRIGGER_FIELDS",
    "TriggerClause",
    "Watch",
    "WatchError",
    "load_watches",
    "sync_watches",
]

logger = logging.getLogger(__name__)

_TOP_LEVEL_KEYS = {"version", "watches"}


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
            fields = validate_watch(index, entry, position, seen, stamp, problems)
            if fields is not None:
                watches.append(Watch(**fields, source_path=target))

    if problems:
        raise WatchError(target, problems)

    return watches


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
