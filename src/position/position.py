"""
Position: the decisions the operator is actually carrying, with deadlines.

Position is the root of the commitment graph. Everything downstream -- watches,
routing, adjudication, alerts -- exists to serve a decision named here. A watch
that serves no decision in this file is curiosity, and invariant 2 exists to
keep curiosity out of the notification path.

**Position is not in this repository.** It names real decisions, real deadlines
and real exposures; this repo is public. The file lives in a private repo under
version control -- under version control because the quarterly review's value is
the *diff* (what did I believe last quarter, which decisions closed), which a
gitignored file cannot provide. What ships here is the schema, the loader and
``config/position.example.yaml``. The path is configurable
(``POSITION_PATH``) and defaults to ``~/.config/insightweaver/position.yaml``,
outside any checkout.

**Why the size check warns and does not fail.** The brief says a Position over
two pages has drifted into describing interests rather than stakes. A hard limit
would enforce a proxy: a three-page Position full of genuine deadlines is better
than a one-page Position of vague interests. So the check names the drift and
lets the human judge, the same way ``coverage_probes`` reports INCONCLUSIVE
rather than dropping a probe. Everything that is *structurally* checkable --
a decision with no deadline, a duplicate key, a date that is not a date -- is a
hard rejection, because those are not judgement calls.

Added 2026-08-31 for backlog task 013.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "MAX_PAGES",
    "POSITION_PAGE_WORDS",
    "Decision",
    "Position",
    "PositionError",
    "load_position",
]

logger = logging.getLogger(__name__)

# A page of prose, for the purpose of the drift warning only. The number is a
# proxy and is treated as one: it can only produce a warning, never a rejection.
POSITION_PAGE_WORDS = 500
MAX_PAGES = 2

# Decision keys are slugs because watches reference them by key and a key with
# spaces or capitals invites two spellings of the same decision.
_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

_TOP_LEVEL_KEYS = {"version", "reviewed", "decisions"}
_DECISION_KEYS = {"key", "name", "deadline", "stake"}


class PositionError(ValueError):
    """
    Raised when a Position file cannot be read as a Position.

    Carries every problem found, not just the first: the file is hand-edited,
    and a loader that reports one error per run turns a five-minute fix into
    five runs.
    """

    def __init__(self, path: Path, problems: list[str]) -> None:
        self.path = path
        self.problems = list(problems)
        body = "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(f"{path} is not a valid Position:\n{body}")


@dataclass(frozen=True)
class Decision:
    """One standing decision, with the date by which it stops being open."""

    key: str
    name: str
    deadline: date
    stake: str | None = None

    def days_remaining(self, today: date) -> int:
        return (self.deadline - today).days


@dataclass(frozen=True)
class Position:
    """A loaded Position, plus whatever the loader wants to say about it."""

    path: Path
    version: int
    decisions: tuple[Decision, ...]
    reviewed: date | None = None
    warnings: tuple[str, ...] = ()
    word_count: int = 0

    @property
    def decision_keys(self) -> frozenset[str]:
        return frozenset(d.key for d in self.decisions)

    def decision(self, key: str) -> Decision | None:
        """The decision with this key, or None. Watches resolve `so_what` here."""
        for candidate in self.decisions:
            if candidate.key == key:
                return candidate
        return None


def default_position_path() -> Path:
    """Where Position lives when nothing says otherwise."""
    from src.config.settings import settings

    return Path(settings.position_path).expanduser()


def _as_date(value: Any) -> date | None:
    """A YAML scalar as a date, or None if it is not one."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def _is_blank(value: Any) -> bool:
    """True for None, for a non-string, or for a string that is only whitespace."""
    return not isinstance(value, str) or not value.strip()


def _content_words(text: str) -> int:
    """
    Words in the file, ignoring comments and blank lines.

    Comments are the operator's own notes about the decisions and counting them
    would make the drift warning fire on a well-annotated file, which is the
    opposite of what it is for.
    """
    kept = [
        line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    return len(" ".join(kept).split())


def _validate_decision(
    index: int, raw: Any, seen: set[str], problems: list[str]
) -> Decision | None:
    label = f"decisions[{index}]"
    if not isinstance(raw, dict):
        problems.append(
            f"{label}: expected a mapping with key/name/deadline, got {type(raw).__name__}"
        )
        return None

    unknown = sorted(set(raw) - _DECISION_KEYS)
    if unknown:
        problems.append(f"{label}: unknown field(s) {unknown}; allowed: {sorted(_DECISION_KEYS)}")

    key = raw.get("key")
    if _is_blank(key):
        problems.append(f"{label}: 'key' is required and must be a non-empty string")
        key = None
    elif not _KEY_RE.match(str(key).strip()):
        problems.append(
            f"{label}: key '{key}' is not a slug -- lowercase letters, digits, '-', '_' and '.'"
        )
        key = None
    else:
        key = str(key).strip()
        if key in seen:
            problems.append(f"{label}: duplicate decision key '{key}'")
            key = None
        else:
            seen.add(key)

    name = raw.get("name")
    if _is_blank(name):
        problems.append(f"{label}: 'name' is required and must be a non-empty string")

    deadline = _as_date(raw.get("deadline"))
    if "deadline" not in raw:
        problems.append(
            f"{label}: 'deadline' is required. A decision with no date is an interest; "
            f"Position holds stakes."
        )
    elif deadline is None:
        problems.append(f"{label}: deadline {raw.get('deadline')!r} is not a date (YYYY-MM-DD)")

    stake = raw.get("stake")

    if key is None or _is_blank(name) or deadline is None:
        return None
    return Decision(
        key=key,
        name=str(name).strip(),
        deadline=deadline,
        stake=str(stake).strip() if isinstance(stake, str) and stake.strip() else None,
    )


def _drift_warnings(decisions: tuple[Decision, ...], word_count: int, today: date) -> list[str]:
    """Everything the loader wants to say but will not refuse over."""
    notes: list[str] = []

    limit = POSITION_PAGE_WORDS * MAX_PAGES
    if word_count > limit:
        pages = word_count / POSITION_PAGE_WORDS
        notes.append(
            f"Position is {word_count} words (~{pages:.1f} pages), over the {MAX_PAGES}-page mark. "
            f"A Position this long has usually drifted from describing stakes -- decisions with "
            f"deadlines and exposure -- into describing interests. Nothing is rejected on length; "
            f"read it and cut what you are merely curious about."
        )

    for decision in decisions:
        if decision.deadline < today:
            notes.append(
                f"decision '{decision.key}' passed its deadline "
                f"({decision.deadline.isoformat()}, {(today - decision.deadline).days}d ago). "
                f"Close it or move the date; watches serving a dead decision are noise."
            )
        if decision.stake is None:
            notes.append(
                f"decision '{decision.key}' states no 'stake'. Without the exposure written down "
                f"it reads as an interest, and there is nothing to weigh an alert against."
            )
    return notes


def load_position(path: str | Path | None = None, *, today: date | None = None) -> Position:
    """
    Read and validate a Position file.

    Raises :class:`FileNotFoundError` if the file is absent -- there is no
    default Position, because a guessed set of decisions is worse than none --
    and :class:`PositionError` listing every structural problem otherwise.
    Judgement-call problems come back on :attr:`Position.warnings` and are also
    logged at WARNING.
    """
    target = Path(path).expanduser() if path is not None else default_position_path()
    if not target.exists():
        raise FileNotFoundError(
            f"No Position at {target}. Position lives in your private repo, not this one; "
            f"point POSITION_PATH at it, or start from config/position.example.yaml."
        )

    text = target.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PositionError(target, [f"file is not valid YAML: {exc}"])

    problems: list[str] = []
    if raw is None:
        raise PositionError(target, ["file is empty"])
    if not isinstance(raw, dict):
        raise PositionError(
            target, [f"expected a mapping at the top level, got {type(raw).__name__}"]
        )

    unknown = sorted(set(raw) - _TOP_LEVEL_KEYS)
    if unknown:
        problems.append(f"unknown top-level field(s) {unknown}; allowed: {sorted(_TOP_LEVEL_KEYS)}")

    version = raw.get("version", 1)
    if not isinstance(version, int) or isinstance(version, bool):
        problems.append(f"version must be an integer, got {version!r}")
        version = 1

    reviewed = None
    if raw.get("reviewed") is not None:
        reviewed = _as_date(raw.get("reviewed"))
        if reviewed is None:
            problems.append(f"reviewed {raw.get('reviewed')!r} is not a date (YYYY-MM-DD)")

    raw_decisions = raw.get("decisions")
    decisions: list[Decision] = []
    if raw_decisions is None:
        problems.append("'decisions' is required -- a Position with no decisions holds no stakes")
    elif not isinstance(raw_decisions, list):
        problems.append(f"'decisions' must be a list, got {type(raw_decisions).__name__}")
    elif not raw_decisions:
        problems.append("'decisions' is empty -- a Position with no decisions holds no stakes")
    else:
        seen: set[str] = set()
        for index, entry in enumerate(raw_decisions):
            decision = _validate_decision(index, entry, seen, problems)
            if decision is not None:
                decisions.append(decision)

    if problems:
        raise PositionError(target, problems)

    word_count = _content_words(text)
    notes = _drift_warnings(tuple(decisions), word_count, today or date.today())
    for note in notes:
        logger.warning("position: %s", note)

    return Position(
        path=target,
        version=version,
        decisions=tuple(decisions),
        reviewed=reviewed,
        warnings=tuple(notes),
        word_count=word_count,
    )
