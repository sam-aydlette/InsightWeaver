"""
Ingest command - every configured source through the adapter path.

One command, all feeds in ``config/feeds/``, one store path. The profile-driven
selection that used to pick a subset went with the profile (backlog task 027);
curation is editing that directory, as ``SOURCES.md`` says. A source row is
registered the first time its adapter runs, so adding a feed to config is
enough -- the "added to config, never reached the database" trap recorded in
tasks 020 and 025 has no path left.

Three outcomes per source stay distinct, as the runner keeps them: fetched
(with how many were new), unreachable (an error, printed loudly), and went
silent (zero items from a source that has produced items before). None of them
stops the run; the brief carries the state. The exit code is non-zero when the
command cannot run at all (a bad option, no sources, nothing matched) and when
no source could be read, which is a broken machine rather than a quiet morning.

Added 2026-09-22 for backlog task 028.
"""

import asyncio
from datetime import timedelta

import click

from ..database.connection import get_db
from ..sources.runner import DEFAULT_LOOKBACK_DAYS, build_configured_adapters, run_adapters
from ..utils import utcnow
from ..utils.cadence import InvalidCadence, parse_cadence
from .colors import accent, error, header, muted, warning

# Five in flight at once. With 78 RSS feeds configured on 2026-09-22 that is
# sixteen batches in the worst case where every feed runs to its timeout; a
# feed that answers normally takes about a second. Few enough to remain a
# polite guest of each host.
CONCURRENCY = 5


def _since(raw: str | None) -> timedelta:
    if raw is None:
        return timedelta(days=DEFAULT_LOOKBACK_DAYS)
    try:
        return parse_cadence(raw)
    except InvalidCadence as exc:
        raise click.ClickException(str(exc))


@click.command(name="ingest")
@click.option(
    "--since",
    "since_raw",
    default=None,
    help=f"How far back to ask each source (7d, 2w). Default {DEFAULT_LOOKBACK_DAYS}d.",
)
@click.option(
    "--source",
    "source_filter",
    default=None,
    help="Only sources whose name contains this text (case-insensitive).",
)
def ingest_command(since_raw, source_filter):
    """Fetch every configured source and store what is new."""
    window_start = utcnow() - _since(since_raw)

    try:
        adapters = build_configured_adapters(include_rss=True)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if source_filter:
        needle = source_filter.lower()
        adapters = [a for a in adapters if needle in a.name.lower()]
    if not adapters:
        raise click.ClickException(
            "no sources to ingest: nothing matched"
            if source_filter
            else "no sources configured under config/feeds/"
        )

    click.echo(header("INGEST"))
    click.echo(
        muted(f"{len(adapters)} source(s) since {window_start.isoformat(timespec='minutes')}")
    )
    click.echo()

    summary = asyncio.run(
        run_adapters(adapters, window_start, db_factory=get_db, concurrency=CONCURRENCY)
    )

    for result in summary.results:
        if result.error:
            click.echo(f"{error('UNREACHABLE')} {result.source}: {result.error}")
        elif result.went_silent:
            click.echo(
                f"{warning('WENT SILENT')} {result.source}: zero items, but it has "
                f"produced items before"
            )
        else:
            click.echo(
                f"{accent(result.source)}: fetched {result.fetched}, "
                f"inserted {result.inserted}, {result.duplicates} already stored"
            )

    click.echo()
    click.echo(
        muted(
            f"{summary.successful_sources} of {summary.total_sources} source(s) read; "
            f"{summary.total_articles} new article(s)"
        )
    )
    if summary.alerts:
        click.echo()
        for line in summary.alerts:
            click.echo(warning(f"SOURCE ALERT: {line}"))

    if summary.successful_sources == 0:
        raise click.ClickException("no source could be read")
