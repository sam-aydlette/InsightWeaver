"""
Route command - link the window's observations to the live watches.

``route`` writes; ``route --dry-run`` computes the same report and writes
nothing. ``--rebuild`` discards every link for the live watches and routes the
whole corpus again, which is how a changed trigger reaches observations that
were stored before the change.

The unrouted clusters printed at the end are the point of running this by
hand: an observation that routes to nothing is usually noise, and a story that
several outlets carried and nothing caught is a watch that does not exist yet.

Added 2026-09-22 for backlog task 028.
"""

import click

from ..database.connection import get_db
from ..routing import RoutingReport, TriggerCompileError, route
from ..routing.route import CLUSTER_LIMIT
from ..utils import utcnow
from ..utils.cadence import InvalidCadence, parse_cadence
from .colors import accent, header, muted, warning

DEFAULT_WINDOW = "7d"


def render_report(report: RoutingReport) -> str:
    """The routing report as text. Kept as a function so tests can read it."""
    window = (
        "whole corpus (rebuild)"
        if report.rebuild
        else f"since {report.since.isoformat(timespec='minutes')}"
    )
    lines = [
        f"window: {window}",
        f"observations: {report.observations}, routed {report.routed}, unrouted {report.unrouted}",
        "",
    ]
    if not report.watches:
        lines.append("no live watches")
    for w in report.watches:
        lines.append(f"  {w.watch_id}: {w.new} new, {w.total} in window")
    if report.unrouted_by_source:
        lines.append("")
        lines.append("unrouted by source:")
        for source, count in report.unrouted_by_source:
            lines.append(f"  {count:>5}  {source}")
    if report.clustering_skipped:
        lines.append("")
        lines.append(
            f"clustering skipped: {report.clustering_skipped} unrouted observations exceed "
            f"the {CLUSTER_LIMIT} the pairwise grouper is sized for; narrow --since"
        )
    if report.clusters:
        lines.append("")
        lines.append("unrouted, largest clusters first:")
        for c in report.clusters:
            sources = ", ".join(c.sources)
            lines.append(f"  [{c.size}] {c.title[:80] or '(untitled)'}  ({sources})")
        if report.clusters_omitted:
            lines.append(f"  ... and {report.clusters_omitted} smaller cluster(s)")
    return "\n".join(lines)


@click.command(name="route")
@click.option("--since", "since_raw", default=DEFAULT_WINDOW, help="Window (7d, 2w).")
@click.option("--dry-run", is_flag=True, default=False, help="Report only; write nothing.")
@click.option(
    "--rebuild",
    is_flag=True,
    default=False,
    help="Discard every link for the live watches and route the whole corpus again.",
)
def route_command(since_raw, dry_run, rebuild):
    """Link observations to the watches whose triggers they match."""
    try:
        window = parse_cadence(since_raw)
    except InvalidCadence as exc:
        raise click.ClickException(str(exc))
    # One clock for the window and for liveness: naive UTC, as observed_at is.
    now = utcnow()
    since = now - window

    with get_db() as session:
        try:
            report = route(
                session, since=since, today=now.date(), write=not dry_run, rebuild=rebuild
            )
        except TriggerCompileError as exc:
            raise click.ClickException(str(exc))

        click.echo(header("ROUTE"))
        click.echo(render_report(report))
        click.echo()
        if dry_run:
            click.echo(muted("Nothing was written."))
        else:
            written = sum(w.new for w in report.watches)
            click.echo(accent(f"{written} link(s) written."))
        if report.watches and report.routed == 0:
            click.echo(warning("Nothing routed. Either the window is quiet or no trigger matches."))
