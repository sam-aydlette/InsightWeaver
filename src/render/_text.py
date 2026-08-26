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
