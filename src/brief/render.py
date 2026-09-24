"""
The brief as text, deterministic to the byte, in two flavours that differ only
in headings: plain terminal text and markdown.

No wall-clock read, no colour codes, no row ids: everything printed comes from
the :class:`~src.brief.sections.Brief` it is handed, and the same brief renders
the same bytes forever. Every citation carries the observation hash it rests
on, shortened to a prefix long enough to be unique in any corpus this tool will
hold and short enough to read; ``sources show`` and the audit log take the
full hash. Every heading is printed, with a zero, when its section is empty:
a brief that looks the same when nothing happened and when the pipeline is
broken is the failure this design exists to prevent.

**The source header is compact by default** (``verbose=False``): a source
that answered, whatever it returned, is folded into the summary counts. A
source whose last attempt *failed* is never folded -- it is printed in full,
every time, because that is the one line invariant 5 exists to guarantee.
``--verbose`` on the CLI prints every source individually, as the header
always did before 2026-09-24.

Added 2026-09-22 for backlog task 031; reworked 2026-09-23 after its review;
the compact header added 2026-09-24 at the operator's request, after a first
real run showed a ~70-source header burying the four sections worth reading
daily.
"""

from __future__ import annotations

from datetime import datetime

from .sections import Brief, Citation

__all__ = ["HASH_CHARS", "render", "short"]

# Hex characters of a content hash printed after ``sha256:``. Twelve is 48
# bits; a collision needs on the order of sixteen million observations.
HASH_CHARS = 12


def short(content_hash: str) -> str:
    return content_hash[: len("sha256:") + HASH_CHARS]


def _stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%d %H:%M")


class _Doc:
    def __init__(self, markdown: bool) -> None:
        self.markdown = markdown
        self.lines: list[str] = []

    def title(self, text: str) -> None:
        self.lines.append(f"# {text}" if self.markdown else text.upper())

    def section(self, text: str) -> None:
        self.lines.append("")
        self.lines.append(f"## {text}" if self.markdown else text)
        if not self.markdown:
            self.lines.append("-" * len(text))

    def line(self, text: str = "") -> None:
        self.lines.append(text)

    def bullet(self, text: str, depth: int = 0) -> None:
        self.lines.append("  " * depth + ("- " if self.markdown else "* ") + text)

    def text(self) -> str:
        return "\n".join(self.lines).rstrip() + "\n"


def _cite(c: Citation) -> str:
    return (
        f"{c.direction} {c.magnitude:.2f}  {c.published}  {c.source}: {c.title}  "
        f"[{short(c.content_hash)}, {c.prompt_version}]"
    )


def _source_line(s) -> str:
    if s.last_attempt is None:
        when = "never fetched"
    elif s.last_error:
        when = f"LAST ATTEMPT FAILED {_stamp(s.last_attempt)}: {s.last_error}"
    else:
        when = f"fetched {_stamp(s.last_attempt)}"
    return f"{s.name}: {when}; {s.items_in_window} in window"


def _header(doc: _Doc, brief: Brief, verbose: bool) -> None:
    h = brief.header
    doc.title(f"Brief as of {_stamp(h.as_of)}")
    doc.line(f"window: since {_stamp(h.since)}")
    if h.position_problem:
        first, *rest = h.position_problem.splitlines() or [""]
        doc.line(f"POSITION NOT READ: {first}")
        for line in rest:
            doc.line(f"  {line.strip()}")
    elif h.reviewed is None:
        doc.line("position: never reviewed (no `reviewed` date in the file)")
    else:
        doc.line(f"position: reviewed {h.reviewed.isoformat()} ({h.days_since_review} days ago)")
    if h.review_banner:
        doc.line(
            "REVIEW OVERDUE: every item below was judged against a Position last reviewed more "
            "than 90 days ago, or never. The items still stand; the frame may not."
        )
    if not h.sources:
        doc.line("sources: none registered; nothing has been ingested")
        return
    if verbose:
        doc.line("sources:")
        for s in h.sources:
            doc.bullet(_source_line(s))
        return
    failed = [s for s in h.sources if s.last_error is not None]
    fetched = [s for s in h.sources if s.last_attempt is not None and s.last_error is None]
    never = [s for s in h.sources if s.last_attempt is None]
    doc.line(
        f"sources: {len(h.sources)} configured, {len(fetched)} fetched, {len(failed)} failed, "
        f"{len(never)} never fetched (--verbose for every source)"
    )
    for s in failed:
        doc.bullet(_source_line(s))


def _moved(doc: _Doc, brief: Brief) -> None:
    doc.section("MOVED")
    if not brief.moved:
        doc.line("nothing: no watch gained evidence in the window")
    for watch in brief.moved:
        state = f" [{watch.state}]" if watch.state else ""
        doc.bullet(f"{watch.watch_id}{state}: {watch.claim}")
        for cluster in watch.clusters:
            # Distinct observations, not citations: one observation judged
            # under two prompt versions is two citations of one story.
            others = len({c.content_hash for c in cluster}) - 1
            also = f" (+{others} near-duplicate{'s' if others != 1 else ''})" if others else ""
            doc.bullet(_cite(cluster[0]) + also, depth=1)
            for c in cluster[1:]:
                doc.bullet(f"also {_cite(c)}", depth=2)


def _due(doc: _Doc, brief: Brief) -> None:
    doc.section("DUE")
    if not brief.position_read:
        doc.line("decisions: POSITION NOT READ (see the header); watches only below")
    if not brief.due_decisions and not brief.due_watches:
        doc.line("nothing inside the horizon")
    for d in brief.due_decisions:
        when = (
            f"{d.deadline.isoformat()}, {d.days_left} days"
            if d.days_left >= 0
            else f"{d.deadline.isoformat()}, {-d.days_left} days PAST"
        )
        doc.bullet(f"decision {d.key}: {d.name} ({when})")
        if d.stake:
            doc.bullet(f"stake: {d.stake.strip()}", depth=1)
    for w in brief.due_watches:
        when = (
            f"expires {w.expires.isoformat()}, {w.days_left} days"
            if w.days_left >= 0
            else f"EXPIRED {w.expires.isoformat()}, {-w.days_left} days ago, unresolved"
        )
        doc.bullet(f"watch {w.watch_id}: {w.claim} ({when})")


def _watching(doc: _Doc, brief: Brief) -> None:
    doc.section("WATCHING")
    if not brief.watching:
        doc.line("no live watches")
    for r in brief.watching:
        last = r.last_evidence.isoformat() if r.last_evidence else "never"
        doc.bullet(
            f"{r.watch_id}: belief {r.belief:.2f} ({r.belief_source}, "
            f"{r.belief_date.isoformat()}); serves {r.decision_key}; expires in "
            f"{r.days_to_expiry} days; evidence in window {r.evidence_in_window}, last {last}"
        )
        doc.bullet(r.claim, depth=1)


def _quiet(doc: _Doc, brief: Brief) -> None:
    doc.section("QUIET")
    doc.line(
        f"watches with nothing routed inside their staleness window: {len(brief.quiet_watches)}"
    )
    for q in brief.quiet_watches:
        last = (
            f"nothing routed since {q.last_routed.isoformat()}" if q.last_routed else "never routed"
        )
        doc.bullet(f"{q.watch_id}: {last} (alert after {q.staleness_alert_days} days)")
    doc.line(f"sources that ran in the window and returned nothing: {len(brief.silent_sources)}")
    for s in brief.silent_sources:
        note = "HAS PRODUCED BEFORE; check the source" if s.produced_before else "never produced"
        doc.bullet(f"{s.name} ({note})")
    pairs = sum(p.pairs for p in brief.pending)
    doc.line(f"routed pairs no adjudication has answered: {pairs}")
    for p in brief.pending:
        doc.bullet(f"{p.watch_id}: {p.pairs}")
    doc.line(f"failed adjudications in the window: {len(brief.failed)}")
    for f in brief.failed:
        doc.bullet(f"{short(f.content_hash)} / {f.watch_id} [{f.prompt_version}]: {f.error}")


def render(brief: Brief, *, markdown: bool = False, verbose: bool = False) -> str:
    """
    The whole document: header first, then the four sections in fixed order.

    ``verbose`` controls only the header's source list (see the module
    docstring); the other four sections never summarise, because they are
    already the compact view over their own data.
    """
    doc = _Doc(markdown)
    _header(doc, brief, verbose)
    for part in (_moved, _due, _watching, _quiet):
        part(doc, brief)
    return doc.text()
