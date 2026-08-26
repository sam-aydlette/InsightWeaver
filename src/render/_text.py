"""
Shared, pure text extraction for the brief renderers.

Every renderer reads the same fields out of a synthesis payload the same way.
These helpers are that reading, defined once. They contain no styling: they
return plain strings, and each renderer decides how to present them.
"""

from __future__ import annotations

import re
from typing import Any

# Glyphs for how a factor moved: shared by every renderer that shows decisions.
DIRECTION_GLYPH = {
    "supports": "+",
    "complicates": "-",
    "neutral": "~",
}


def clean_citations(text: str) -> str:
    """Convert ^[N,M] citation markers to [N,M] for display."""
    if not text:
        return text
    return re.sub(r"\^\[([0-9,\s]+)\]", r"[\1]", text)


def decision_summary(metadata: dict) -> list[dict]:
    """Pull the decision-routing summary out of synthesis metadata."""
    routing = metadata.get("decision_routing")
    return routing if isinstance(routing, list) else []


def prediction_check_line(check: dict | None) -> str:
    """One-line transparency summary of the pre-synthesis prediction check."""
    if not isinstance(check, dict):
        return ""
    checked = check.get("checked", 0)
    if not checked and not check.get("expired"):
        return ""
    triggered = check.get("triggered", 0)
    contradicted = check.get("contradicted", 0)
    still_open = check.get("still_open", 0)
    expired = check.get("expired", 0)
    return (
        f"Prediction check: {checked} open observables graded -- "
        f"{triggered} triggered, {contradicted} contradicted, "
        f"{still_open} still open, {expired} expired. "
        f"See 'predictions track-record'."
    )


# --- institutional activity -------------------------------------------------
#
# The section reports movement against a trailing average, never a tally. A
# flat count is noise: the entities a beat declares are the ones that appear
# most days, so "FedRAMP PMO: 6" reproduces a standing fact every morning. The
# sentences below are built to read like an analyst noting a change, and the
# ordering deliberately never sorts by count -- that would be a leaderboard,
# and activity is not significance.

MOVEMENT_UP = "up"
MOVEMENT_DOWN = "down"
MOVEMENT_UNCHANGED = "unchanged"
MOVEMENT_FIRST_RUN = "first_run"

ACTIVITY_NOTE = (
    "Movement against each entity's trailing average. "
    "A count is an observation, not a measure of significance."
)


def institutional_activity(metadata: dict) -> dict[str, Any]:
    """
    Pull the institutional activity block out of synthesis metadata.

    Returns ``{}`` when the run recorded none -- the default person brief, or a
    beat with no ``coverage`` entities.
    """
    block = metadata.get("institutional_activity")
    return block if isinstance(block, dict) else {}


def _activity_entries(block: dict) -> list[dict]:
    entries = block.get("entities")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def split_activity(block: dict) -> tuple[list[dict], list[dict]]:
    """
    Partition activity entries into ``(moved, steady)``, order preserved.

    ``moved`` carries the entities whose count departed from their baseline,
    plus the ones being observed for the first time (which have no baseline to
    depart from and are stated as such). ``steady`` carries the rest: entities
    that have been active before and are behaving normally, including normally
    quiet ones. They are kept because an entity going silent is information,
    and dropping it is the same class of bug as a standing question vanishing
    on a quiet day.
    """
    moved: list[dict] = []
    steady: list[dict] = []
    for entry in _activity_entries(block):
        movement = entry.get("movement")
        if movement in (MOVEMENT_UP, MOVEMENT_DOWN, MOVEMENT_FIRST_RUN):
            moved.append(entry)
        else:
            steady.append(entry)
    return moved, steady


def _format_average(value: Any) -> str:
    """Render a trailing average without trailing zeros: 1.0 -> "1"."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return "0"
    return f"{round(float(value), 1):g}"


def _items(count: int) -> str:
    return "1 item" if count == 1 else f"{count} items"


def activity_sentence(entry: dict) -> str:
    """
    One entity's reading as a sentence.

    Three forms, because there are three things that can be true: it moved
    against a baseline, it has no baseline yet, or it is where it usually is.
    """
    name = str(entry.get("name", "(entity)"))
    raw_count = entry.get("count", 0)
    count = raw_count if isinstance(raw_count, int) and not isinstance(raw_count, bool) else 0
    movement = entry.get("movement")

    if movement == MOVEMENT_FIRST_RUN:
        return f"{name} appeared in {_items(count)} this run; no trailing average yet."
    if movement in (MOVEMENT_UP, MOVEMENT_DOWN):
        average = _format_average(entry.get("trailing_average"))
        return (
            f"{name} appeared in {_items(count)} this run, against a trailing average of {average}."
        )
    return f"{name} appeared in {count}, unchanged."


def activity_footnote(block: dict) -> str:
    """
    One line accounting for the entities the section does not list.

    An entity with no mentions and no history does not appear -- declaring it
    was a hypothesis about where news comes from, and a hypothesis that has
    never paid out is a note about the config rather than a line in the brief.
    Saying how many were withheld keeps that omission visible without naming
    them into the brief.
    """
    withheld = block.get("never_observed")
    if not isinstance(withheld, int) or isinstance(withheld, bool) or withheld <= 0:
        return ""
    if withheld == 1:
        return "1 declared entity has never been mentioned and is not listed."
    return f"{withheld} declared entities have never been mentioned and are not listed."


def standing_agenda(metadata: dict) -> list[dict]:
    """
    Pull this beat's standing-agenda review out of synthesis metadata.

    Returns every entry the run recorded, including the ones that did not move.
    Renderers must not filter this list: an unmoved standing question is the
    finding, and dropping it is the failure the standing agenda exists to
    prevent (added 2026-08-26, backlog task 007).
    """
    agenda = metadata.get("standing_agenda")
    if not isinstance(agenda, list):
        return []
    return [entry for entry in agenda if isinstance(entry, dict)]


def standing_agenda_status(entry: dict) -> str:
    """The short label for how one standing question moved: MOVED or NO MOVEMENT."""
    return "MOVED" if entry.get("moved") else "NO MOVEMENT"


def standing_agenda_provenance(entry: dict) -> str:
    """
    The identity line under a standing question: which Q it is, how many runs
    of this beat have moved it, and when it last did.
    """
    parts = [f"Q{entry.get('question_id', '?')}"]
    declared = entry.get("declared_at")
    if declared:
        parts.append(f"declared {declared}")

    count = entry.get("appearance_count") or 0
    if entry.get("moved"):
        parts.append(f"run {count}")
    elif count:
        last = entry.get("last_moved_at")
        parts.append(
            f"{count} prior run(s), last moved {last}" if last else f"{count} prior run(s)"
        )
    else:
        parts.append("never moved")

    status = entry.get("status")
    if status and status != "open":
        parts.append(str(status))
    return f"{parts[0]} ({', '.join(parts[1:])})" if len(parts) > 1 else parts[0]


def standing_agenda_movement(entry: dict) -> list[str]:
    """
    What moved this standing question in this run, one line per situation.

    Empty when nothing moved -- the caller says so explicitly rather than
    rendering nothing.
    """
    lines: list[str] = []
    for item in entry.get("moved_in") or []:
        if not isinstance(item, dict):
            continue
        index = item.get("situation_index")
        title = clean_citations(str(item.get("title") or "")).strip()
        label = f"Situation {index}" if index is not None else "This run"
        lines.append(f"{label}: {title}" if title else label)
    return lines


def standing_agenda_no_movement(entry: dict) -> str:
    """The sentence shown when a standing question did not move this run."""
    last = entry.get("last_moved_at")
    if last:
        return f"No coverage this run bore on this question. Last moved {last}."
    return "No coverage this run bore on this question, and none ever has."


def watch_items(futures: dict) -> list[str]:
    """Extract what_to_watch observables. Handles the list-of-objects shape
    and the legacy single-string shape."""
    watch = futures.get("what_to_watch")
    if isinstance(watch, str):
        return [watch] if watch.strip() else []
    if not isinstance(watch, list):
        return []
    items: list[str] = []
    for entry in watch:
        if isinstance(entry, str) and entry.strip():
            items.append(entry.strip())
        elif isinstance(entry, dict):
            observable = (entry.get("observable") or "").strip()
            trigger = (entry.get("trigger_condition") or "").strip()
            if observable and trigger:
                items.append(f"{observable} -- {trigger}")
            elif observable:
                items.append(observable)
    return items


def question_lines(
    futures: dict,
) -> tuple[str, str, list[tuple[str, str]]]:
    """
    Extract primary question text + identity prefix and secondary lines from
    a ``where_this_goes`` block. Returns ``(primary_text, primary_prefix,
    secondary)`` where each secondary is ``(text, prefix)``. Prefix is empty
    when a question has no identity metadata or is appearing for the first
    time -- accumulation context is only shown for repeat appearances.
    """
    uq = futures.get("unresolved_questions")
    if not isinstance(uq, dict):
        legacy = futures.get("unresolved_question")
        if isinstance(legacy, str):
            return legacy, "", []
        return "", "", []

    def _split(entry: Any) -> tuple[str, str]:
        if isinstance(entry, str):
            return entry, ""
        if not isinstance(entry, dict):
            return "", ""
        text = entry.get("text", "")
        qid = entry.get("question_id")
        appearance = entry.get("appearance_count")
        if qid is None or appearance is None:
            return text, ""
        if appearance <= 1:
            return text, f"Q{qid} (new)"
        first = entry.get("first_asked_at", "")
        first_date = first.split("T", 1)[0] if isinstance(first, str) else ""
        return text, f"Q{qid} (run {appearance}, asked {first_date})"

    primary_text, primary_prefix = _split(uq.get("primary"))
    secondary: list[tuple[str, str]] = []
    for entry in uq.get("secondary") or []:
        text, prefix = _split(entry)
        if text:
            secondary.append((text, prefix))
    return primary_text, primary_prefix, secondary
