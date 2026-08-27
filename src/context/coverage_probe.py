"""
Testing a beat against events that actually happened.

Task 005 asked whether a beat could reach its domain and answered with document
counts: 469 Federal Register documents narrowed to 24, 38 retrieved in seven
days. Both real, both green, and neither able to detect that the beat was
structurally unable to see a personnel change -- because a personnel change is
not a document. The beat's first live brief then missed the reinstatement of the
FedRAMP director, the largest event in its declared domain that week.

**An article count measures whether ingestion is running. It does not measure
whether ingestion reaches the domain.** A coverage probe measures the second
thing, by the only method that cannot be satisfied by ingesting more of what the
beat already reads:

    Name something that actually happened in this domain, then check whether the
    beat can see it.

Nothing here calls a model. A probe either matched a stored article or it did
not, and the answer is reproducible from the same rows forever and debuggable by
reading a regex rather than by re-running a prompt.

Three rules do the work:

* **Word boundaries, not substrings.** Measured on this repository's corpus on
  2026-08-27: of 54,044 stored articles, 657 titles contain the substring
  ``nist`` -- "administration", "minister", "Afghanistan", "communist",
  "sinister", "columnist" -- and exactly 4 are about NIST. A substring matcher
  would report 99.4% false coverage on that one term alone. Terms are anchored
  at word boundaries by :mod:`src.context.entity_matcher`, which is the same
  code path coverage entities use.
* **Stems are marked, never inferred.** ``reinstat*`` matches "reinstated" and
  "reinstatement"; ``reinstat`` matches neither. Inferring the widening would
  make every term quietly broader than it reads in the config, which is the
  direction that manufactures false confidence.
* **A window with no articles in it is not a failure.** A probe whose window
  predates the corpus, or falls in a gap, is ``INCONCLUSIVE`` -- it says nothing
  about the beat's reach, because there was nothing to reach with. It stays in
  the count regardless, since a probe set that quietly shrinks to the events
  still in retention is a green light that means nothing.

Added 2026-08-27 for backlog task 010.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time

from sqlalchemy.orm import Session

from ..config.beats import BeatConfig, CoverageProbe
from ..database.models import Article, RSSFeed
from .entity_matcher import is_shouted, term_pattern

__all__ = [
    "STATUS_INCONCLUSIVE",
    "STATUS_MATCHED",
    "STATUS_UNMATCHED",
    "CompiledProbe",
    "CoverageReport",
    "ProbeMatch",
    "ProbeResult",
    "compile_probe",
    "run_coverage_probes",
]

# A probe matched at least one article the beat's own sources carried.
STATUS_MATCHED = "MATCHED"
# The window held articles from the beat's sources and none of them matched.
# This is the finding the feature exists to produce.
STATUS_UNMATCHED = "UNMATCHED"
# The window held nothing to match against, so the probe answers nothing.
STATUS_INCONCLUSIVE = "INCONCLUSIVE"

# The marker that turns a term into a stem. Trailing only: a leading wildcard
# would drop the left-hand word boundary, which is the boundary that does
# essentially all of the collision filtering.
STEM_MARKER = "*"

# How many matching articles to keep per probe. The question is "can the beat
# see this", not "how loudly", so a handful of examples is the whole evidence a
# reader needs and an unbounded list would bury the verdict.
DEFAULT_MATCH_LIMIT = 5


@dataclass(frozen=True)
class CompiledTerm:
    """One probe term as written, with its compiled pattern."""

    raw: str
    pattern: re.Pattern[str]

    def found_in(self, text: str) -> bool:
        return bool(self.pattern.search(text))


def _compile_term(raw: str) -> CompiledTerm:
    """
    Compile one term under the same boundary and case rules as coverage entities.

    A term written entirely in capitals is an acronym and matches
    case-sensitively -- ``BOD`` is a directive, ``bod`` is not. Everything else
    matches case-insensitively, because ordinary names are case-varied in prose
    and long enough not to collide.
    """
    stem = raw.endswith(STEM_MARKER)
    body = raw[: -len(STEM_MARKER)] if stem else raw
    source = term_pattern(body, right_boundary=not stem)
    flags = 0 if is_shouted(body) else re.IGNORECASE
    return CompiledTerm(raw=raw, pattern=re.compile(source, flags))


@dataclass(frozen=True)
class CompiledProbe:
    """
    One probe with every term compiled, ready to be run against many articles.

    ``required`` must all be found in the same article; each group in ``groups``
    contributes one alternative that must be found. An article satisfies the
    probe only when both hold.
    """

    probe: CoverageProbe
    required: tuple[CompiledTerm, ...]
    groups: tuple[tuple[CompiledTerm, ...], ...]

    def matches(self, text: str) -> bool:
        """Whether one article's text satisfies every requirement."""
        absent, unsatisfied = self.missing(text)
        return not absent and not unsatisfied

    def missing(self, text: str) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
        """
        What this text failed to supply: absent required terms, then unsatisfied
        groups.

        Returned rather than swallowed so an unmatched probe can say *which*
        requirement went unmet. An operator reading "FedRAMP absent" fixes a
        source; one reading "matched FedRAMP but nothing in (director,
        administrator)" fixes the probe.
        """
        absent = tuple(term.raw for term in self.required if not term.found_in(text))
        unsatisfied = tuple(
            tuple(term.raw for term in group)
            for group in self.groups
            if not any(term.found_in(text) for term in group)
        )
        return absent, unsatisfied


def compile_probe(probe: CoverageProbe) -> CompiledProbe:
    """Compile one probe's terms once, for reuse across every candidate article."""
    return CompiledProbe(
        probe=probe,
        required=tuple(_compile_term(term) for term in probe.terms),
        groups=tuple(tuple(_compile_term(term) for term in group) for group in probe.any_of),
    )


@dataclass(frozen=True)
class ProbeMatch:
    """One article that satisfied a probe, and the source that carried it."""

    article_id: int
    title: str
    feed_name: str
    published_date: datetime | None
    in_beat_sources: bool

    @property
    def published_day(self) -> str:
        return self.published_date.date().isoformat() if self.published_date else "undated"


@dataclass(frozen=True)
class ProbeResult:
    """
    What one probe found.

    ``elsewhere`` is only populated for a probe the beat's own sources missed:
    it names articles from feeds *outside* this beat that would have satisfied
    it. That distinction is the actionable part. "Nobody in the corpus carried
    it" and "three feeds you do not subscribe to carried it" are the same
    ``UNMATCHED`` verdict and completely different repairs.
    """

    probe: CoverageProbe
    status: str
    window: tuple[date, date]
    articles_in_window: int
    matches: tuple[ProbeMatch, ...] = ()
    match_count: int = 0
    elsewhere: tuple[ProbeMatch, ...] = ()
    elsewhere_count: int = 0
    reason: str = ""
    missing_terms: tuple[str, ...] = ()
    unsatisfied_groups: tuple[tuple[str, ...], ...] = ()

    @property
    def matched(self) -> bool:
        return self.status == STATUS_MATCHED

    @property
    def conclusive(self) -> bool:
        return self.status != STATUS_INCONCLUSIVE


@dataclass(frozen=True)
class CoverageReport:
    """
    Every probe's result for one beat, plus the corpus facts that framed them.

    ``total`` is the number of probes the beat *declared*, and the passed,
    unmatched and inconclusive counts always sum to it. The invariant is the
    point: an inconclusive probe is subtracted from neither side, so a probe set
    rotting out of retention shows up as a shrinking denominator of *answered*
    questions rather than as a clean sweep of the ones that remain.
    """

    beat_name: str
    results: tuple[ProbeResult, ...]
    feed_names: tuple[str, ...]
    earliest: datetime | None
    latest: datetime | None

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def matched(self) -> tuple[ProbeResult, ...]:
        return tuple(r for r in self.results if r.status == STATUS_MATCHED)

    @property
    def unmatched(self) -> tuple[ProbeResult, ...]:
        return tuple(r for r in self.results if r.status == STATUS_UNMATCHED)

    @property
    def inconclusive(self) -> tuple[ProbeResult, ...]:
        return tuple(r for r in self.results if r.status == STATUS_INCONCLUSIVE)

    @property
    def conclusive(self) -> tuple[ProbeResult, ...]:
        return tuple(r for r in self.results if r.conclusive)


def article_text(article: Article) -> str:
    """
    The text of one stored article that probe matching reads.

    Title, summary and normalized body. ``author`` is excluded, as it is in
    :func:`src.context.entity_matcher.item_text`: a byline is a person, and a
    probe is about whether a source carried an event, never about who wrote it.
    """
    parts = [
        article.title or "",
        article.description or "",
        article.normalized_content or article.content or "",
    ]
    return "\n".join(part for part in parts if part)


def _window_bounds(probe: CoverageProbe) -> tuple[datetime, datetime]:
    """The probe's date window as the half-open datetime range SQL compares."""
    start, end = probe.window
    return datetime.combine(start, time.min), datetime.combine(end, time.max)


def _to_match(article: Article, feed_name: str | None, in_beat_sources: bool) -> ProbeMatch:
    return ProbeMatch(
        article_id=article.id,
        title=article.title or "(untitled)",
        feed_name=feed_name or "(unattributed source)",
        published_date=article.published_date,
        in_beat_sources=in_beat_sources,
    )


def _rows_in_window(
    session: Session, probe: CoverageProbe, feed_ids: Sequence[int] | None
) -> list[tuple[Article, str | None]]:
    """
    Every dated article in the probe's window, with its source name.

    Undated rows are excluded rather than assumed recent: an article with no
    ``published_date`` cannot be placed in or out of any window, and counting it
    as in-window would let an unplaceable row turn an inconclusive probe into a
    failure.

    This is the only database access in the module and it is a SELECT. Nothing
    in the coverage path writes -- the corpus is shared, and a read-only
    question must not leave a trace in the thing it is asking about.
    """
    start, end = _window_bounds(probe)
    query = (
        session.query(Article, RSSFeed.name)
        .outerjoin(RSSFeed, Article.feed_id == RSSFeed.id)
        .filter(Article.published_date.isnot(None))
        .filter(Article.published_date >= start)
        .filter(Article.published_date <= end)
    )
    if feed_ids is not None:
        query = query.filter(Article.feed_id.in_(feed_ids))
    return query.order_by(Article.published_date.asc()).all()


@dataclass(frozen=True)
class _Evaluation:
    """One probe's outcome over one set of candidate rows."""

    matches: tuple[ProbeMatch, ...]
    match_count: int
    missing_terms: tuple[str, ...]
    unsatisfied_groups: tuple[tuple[str, ...], ...]


def _evaluate(
    compiled: CompiledProbe,
    rows: Iterable[tuple[Article, str | None]],
    in_beat_sources: bool,
    limit: int,
) -> _Evaluation:
    """
    Run one compiled probe over candidate rows.

    ``match_count`` is every match; ``matches`` is the earliest ``limit`` of
    them, kept separate so the display cap can never make a widely-reported
    event look like a single lucky hit.

    Also returns the *closest* near miss -- the requirements unmet by whichever
    article satisfied the most of them. With no matches that is the diagnostic
    an operator acts on; with matches it is discarded by the caller.
    """
    matches: list[ProbeMatch] = []
    match_count = 0
    best_absent: tuple[str, ...] = tuple(term.raw for term in compiled.required)
    best_groups: tuple[tuple[str, ...], ...] = tuple(
        tuple(term.raw for term in group) for group in compiled.groups
    )
    best_score = len(best_absent) + len(best_groups)

    for article, feed_name in rows:
        absent, unsatisfied = compiled.missing(article_text(article))
        if not absent and not unsatisfied:
            match_count += 1
            if len(matches) < limit:
                matches.append(_to_match(article, feed_name, in_beat_sources))
            continue
        score = len(absent) + len(unsatisfied)
        if score < best_score:
            best_score, best_absent, best_groups = score, absent, unsatisfied

    return _Evaluation(tuple(matches), match_count, best_absent, best_groups)


def run_coverage_probes(
    session: Session,
    beat: BeatConfig,
    feed_urls: Sequence[str] | None = None,
    match_limit: int = DEFAULT_MATCH_LIMIT,
) -> CoverageReport:
    """
    Run every probe a beat declares against the corpus, read-only.

    The verdict is scoped to the beat's own sources: a probe passes when a feed
    *this beat subscribes to* carried the event. An unmatched probe is then
    re-run across the whole corpus, and any hit is reported as ``elsewhere`` --
    evidence that the event was reachable and this beat's source list is what
    missed it.

    A beat with no probes returns an empty report. That is not a pass, and the
    caller is expected to say so: an undeclared probe set is the state the beat
    was already in when it missed the FedRAMP reinstatement.
    """
    feeds = beat.resolve_feeds()
    urls = list(feed_urls) if feed_urls is not None else [feed.url for feed in feeds]
    feed_rows = session.query(RSSFeed).filter(RSSFeed.url.in_(urls)).all() if urls else []
    feed_ids = [row.id for row in feed_rows]
    feed_names = tuple(sorted(row.name for row in feed_rows))

    earliest, latest = _corpus_bounds(session, feed_ids)

    results: list[ProbeResult] = []
    for probe in beat.coverage_probes:
        compiled = compile_probe(probe)
        rows = _rows_in_window(session, probe, feed_ids) if feed_ids else []
        found = _evaluate(compiled, rows, True, match_limit)

        if found.match_count:
            results.append(
                ProbeResult(
                    probe=probe,
                    status=STATUS_MATCHED,
                    window=probe.window,
                    articles_in_window=len(rows),
                    matches=found.matches,
                    match_count=found.match_count,
                )
            )
            continue

        if not rows:
            results.append(
                ProbeResult(
                    probe=probe,
                    status=STATUS_INCONCLUSIVE,
                    window=probe.window,
                    articles_in_window=0,
                    reason=_inconclusive_reason(probe, earliest, latest, bool(feed_ids)),
                )
            )
            continue

        searched_ids = {article.id for article, _ in rows}
        wider = _evaluate(compiled, _rows_in_window(session, probe, None), False, match_limit)
        elsewhere = tuple(m for m in wider.matches if m.article_id not in searched_ids)
        results.append(
            ProbeResult(
                probe=probe,
                status=STATUS_UNMATCHED,
                window=probe.window,
                articles_in_window=len(rows),
                elsewhere=elsewhere,
                elsewhere_count=wider.match_count,
                missing_terms=found.missing_terms,
                unsatisfied_groups=found.unsatisfied_groups,
            )
        )

    return CoverageReport(
        beat_name=beat.name,
        results=tuple(results),
        feed_names=feed_names,
        earliest=earliest,
        latest=latest,
    )


def _corpus_bounds(
    session: Session, feed_ids: Sequence[int]
) -> tuple[datetime | None, datetime | None]:
    """Oldest and newest dated article carried by the beat's own sources."""
    if not feed_ids:
        return None, None
    query = session.query(Article.published_date).filter(
        Article.feed_id.in_(feed_ids), Article.published_date.isnot(None)
    )
    earliest = query.order_by(Article.published_date.asc()).first()
    latest = query.order_by(Article.published_date.desc()).first()
    return (earliest[0] if earliest else None), (latest[0] if latest else None)


def _inconclusive_reason(
    probe: CoverageProbe,
    earliest: datetime | None,
    latest: datetime | None,
    has_feeds: bool,
) -> str:
    """
    Why a probe could not be answered, in the terms an operator can act on.

    The three cases are different problems. Predating the corpus means the probe
    has aged out and should be replaced. Postdating it means the pipeline has not
    run far enough forward yet. A gap in the middle means ingestion was down, and
    that is worth knowing on its own.
    """
    if not has_feeds:
        return "this beat's sources have no rows in the corpus, so nothing was searched"
    if earliest is None:
        return "this beat's sources have stored no dated articles, so nothing was searched"
    start, end = probe.window
    if end < earliest.date():
        return (
            f"window ends {end.isoformat()}, before the beat's oldest stored article "
            f"({earliest.date().isoformat()}) -- the event predates the corpus"
        )
    if latest is not None and start > latest.date():
        return (
            f"window starts {start.isoformat()}, after the beat's newest stored article "
            f"({latest.date().isoformat()}) -- the corpus has not reached the event yet"
        )
    return (
        "the beat's sources stored no dated articles anywhere in this window -- "
        "a gap in the corpus, not a gap in the beat"
    )
