"""
Running adapters, and refusing to let one go quiet without saying so.

Three outcomes are kept distinct, because collapsing any two of them is how a
brief goes thin without anybody noticing (backlog task 005, LANDMINES):

1. ``fetched > 0`` -- the source is working. ``inserted`` may still be 0; that
   is dedup doing its job on a re-run and is *not* an alarm.
2. ``fetched == 0`` and this source has never produced an article -- quiet, but
   nothing has regressed. Logged at INFO.
3. ``fetched == 0`` and this source *has* produced articles before -- the
   source has gone silent. Logged at ERROR and flagged on the result so the
   CLI can shout about it. A misconfigured filter and a changed API contract
   both land here.

An unreachable source never reaches any of the three: the adapter raises
:class:`~src.sources.base.SourceUnavailable` and the result is an error.

"Has produced articles before" is read from the database rather than from a
counter, so it survives restarts and needs no new table.

Added 2026-08-26 for backlog task 005.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from ..config.feed_matcher import FeedMatcher
from ..database.connection import get_db
from ..utils import utcnow
from .base import SourceAdapter, SourceUnavailable
from .federal_register import FederalRegisterAdapter, FederalRegisterConfigError
from .store import ensure_source, source_article_count, store_items

logger = logging.getLogger(__name__)

# Adapter name -> factory, for sources declared in config/feeds/*.json with an
# "adapter" other than "rss". Unknown adapter names are an error at load time,
# never a silently skipped source.
ADAPTER_FACTORIES: dict[str, Callable[[], SourceAdapter]] = {
    "federal_register": lambda: FederalRegisterAdapter(),
}

# How far back a scheduled run asks each adapter to look. Not a backfill: it is
# the smallest window that survives a weekend, since the Federal Register
# publishes on business days and a Monday run with a 24h window would miss
# Friday. Re-fetching an already-ingested day costs one request and inserts
# nothing, because identity is a content hash.
DEFAULT_LOOKBACK_DAYS = 4

DEFAULT_FEEDS_DIR = Path(__file__).resolve().parents[2] / "config" / "feeds"

DbFactory = Callable[[], AbstractContextManager[Session]]


@dataclass
class IngestResult:
    """What one adapter run did."""

    source: str
    fetched: int = 0
    inserted: int = 0
    duplicates: int = 0
    error: str | None = None
    went_silent: bool = False

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class AdapterRunSummary:
    """The aggregate of a set of adapter runs, in fetch-stage shape."""

    results: list[IngestResult] = field(default_factory=list)

    @property
    def total_sources(self) -> int:
        return len(self.results)

    @property
    def successful_sources(self) -> int:
        return sum(1 for result in self.results if result.success)

    @property
    def total_articles(self) -> int:
        return sum(result.inserted for result in self.results)

    @property
    def alerts(self) -> list[str]:
        """Human-readable lines for anything the operator must not miss."""
        lines = []
        for result in self.results:
            if result.error:
                lines.append(f"{result.source}: UNREACHABLE - {result.error}")
            elif result.went_silent:
                lines.append(
                    f"{result.source}: RETURNED ZERO ITEMS after previously returning some "
                    f"- the filter or the upstream contract may have changed"
                )
        return lines

    def as_dict(self) -> dict[str, object]:
        return {
            "total_sources": self.total_sources,
            "successful_sources": self.successful_sources,
            "failed_sources": self.total_sources - self.successful_sources,
            "total_articles": self.total_articles,
            "alerts": self.alerts,
            "sources": [
                {
                    "source": result.source,
                    "fetched": result.fetched,
                    "inserted": result.inserted,
                    "duplicates": result.duplicates,
                    "error": result.error,
                    "went_silent": result.went_silent,
                }
                for result in self.results
            ],
        }


async def run_adapter(
    adapter: SourceAdapter,
    since: datetime,
    db_factory: DbFactory = get_db,
) -> IngestResult:
    """Fetch one adapter, store what it returned, and police the zero case."""
    result = IngestResult(source=adapter.name)

    with db_factory() as db:
        source = ensure_source(db, adapter.name, adapter.source_url, adapter.category)
        prior_articles = source_article_count(db, source)
        source_id = int(source.id)

    try:
        items = await adapter.fetch(since)
    except SourceUnavailable as exc:
        result.error = exc.reason
        logger.error(f"SOURCE UNREACHABLE: {adapter.name} - {exc.reason}")
        _record_error(db_factory, source_id, exc.reason)
        return result
    except Exception as exc:  # noqa: BLE001 - an adapter bug is still an outage
        result.error = f"unexpected {type(exc).__name__}: {exc}"
        logger.error(f"SOURCE FAILED: {adapter.name} - {result.error}")
        _record_error(db_factory, source_id, result.error)
        return result

    result.fetched = len(items)

    if not items:
        if prior_articles > 0:
            result.went_silent = True
            logger.error(
                f"SOURCE WENT SILENT: {adapter.name} returned zero items for "
                f"since={since.isoformat()}, but has {prior_articles} article(s) on record from "
                f"earlier runs. This is not 'a quiet day' -- check the filter config and the "
                f"upstream API contract before trusting this brief."
            )
        else:
            logger.info(
                f"{adapter.name} returned zero items for since={since.isoformat()} and has no "
                f"articles on record yet -- nothing to compare against."
            )
        return result

    with db_factory() as db:
        source = ensure_source(db, adapter.name, adapter.source_url, adapter.category)
        inserted, duplicates = store_items(db, source, items)

    result.inserted = inserted
    result.duplicates = duplicates
    logger.info(
        f"{adapter.name}: fetched {result.fetched}, inserted {inserted}, "
        f"{duplicates} already stored"
    )
    return result


def _record_error(db_factory: DbFactory, source_id: int, reason: str) -> None:
    """Write the failure onto the source row so it is visible outside the log."""
    from ..database.models import RSSFeed

    with db_factory() as db:
        row = db.query(RSSFeed).filter(RSSFeed.id == source_id).first()
        if row is None:
            return
        # Column[...] vs value, as in src/sources/store.py.
        row.last_fetched = utcnow()  # type: ignore[assignment]
        row.last_error = reason  # type: ignore[assignment]
        row.error_count = int(row.error_count or 0) + 1  # type: ignore[assignment]


async def run_adapters(
    adapters: Sequence[SourceAdapter],
    since: datetime,
    db_factory: DbFactory = get_db,
) -> AdapterRunSummary:
    """Run adapters one after another. Sequential on purpose: these are guests
    on public APIs and the whole set is a handful of requests."""
    summary = AdapterRunSummary()
    for adapter in adapters:
        summary.results.append(await run_adapter(adapter, since, db_factory=db_factory))
    for line in summary.alerts:
        logger.error(f"SOURCE ALERT: {line}")
    return summary


def build_configured_adapters(feeds_dir: Path | str | None = None) -> list[SourceAdapter]:
    """
    Instantiate an adapter for every configured non-RSS source.

    RSS feeds were excluded here because ``fetch_all_active_feeds`` owned them.
    That path was closed on 2026-08-31 (backlog task 025) because it wrote
    articles without observations; RSS feeds are still excluded from *this*
    function, which only builds the non-RSS adapters named in config, and are
    now read through ``src.sources.rss_adapter.RSSAdapter`` instead.
    """
    adapters: list[SourceAdapter] = []
    for name in sorted(non_rss_adapter_names(feeds_dir)):
        factory = ADAPTER_FACTORIES.get(name)
        if factory is None:
            # Fail loudly: a config naming an adapter this build does not have
            # would otherwise be a source that silently never runs.
            raise ValueError(
                f"config/feeds/ declares adapter '{name}', which this build does not "
                f"implement (known: {', '.join(sorted(ADAPTER_FACTORIES)) or 'none'})"
            )
        try:
            adapters.append(factory())
        except FederalRegisterConfigError as exc:
            raise ValueError(f"adapter '{name}' is configured but unusable: {exc}")
    return adapters


def non_rss_adapter_names(feeds_dir: Path | str | None = None) -> set[str]:
    """Adapter names other than ``rss`` declared anywhere in ``config/feeds/``."""
    return {feed.adapter for feed in _configured_feeds(feeds_dir) if feed.adapter != "rss"}


def non_rss_source_urls(feeds_dir: Path | str | None = None) -> set[str]:
    """
    URLs in ``config/feeds/`` that are not RSS.

    ``src/rss/parallel_fetcher.py`` uses this to leave them alone: handing a
    JSON API endpoint to feedparser would produce a parse failure every run and
    eventually auto-deactivate the source.
    """
    return {feed.url for feed in _configured_feeds(feeds_dir) if feed.adapter != "rss"}


def _configured_feeds(feeds_dir: Path | str | None = None) -> Iterator:
    """Every configured feed, read from an absolute path by default."""
    directory = Path(feeds_dir) if feeds_dir is not None else DEFAULT_FEEDS_DIR
    return iter(FeedMatcher(str(directory)).all_feeds)


async def run_configured_adapters(
    since: datetime | None = None,
    feeds_dir: Path | str | None = None,
    db_factory: DbFactory = get_db,
) -> AdapterRunSummary:
    """Run every configured non-RSS source. Used by the pipeline's fetch stage."""
    adapters = build_configured_adapters(feeds_dir)
    if not adapters:
        return AdapterRunSummary()
    window_start = since or (utcnow() - timedelta(days=DEFAULT_LOOKBACK_DAYS))
    logger.info(
        f"Running {len(adapters)} non-RSS source adapter(s) since {window_start.isoformat()}"
    )
    return await run_adapters(adapters, window_start, db_factory=db_factory)
