"""
Route command - which observations are candidate evidence for which watch.

``--dry-run`` is the reporting mode and it writes no ``route_candidates`` rows.
It answers the question this tier exists to make answerable: of the last N
observations, how many would each watch send to the adjudicator, which clause
of which watch is doing the sending, and -- the part that is easy to leave out
and is the whole coverage-gap signal -- how many matched nothing, and what were
they about.

**Read the unrouted number first.** A high one is the expected, healthy state:
most of what a feed publishes is not evidence about anything you have
pre-registered a claim on, and if it were, the architecture would not be doing
its job. A *low* one means a trigger is too loose, and a trigger that is too
loose does not fail -- it bills, because the adjudicator is the only tier that
calls a model and it runs on whatever this one hands it.

The coverage-gap report is written to disk in both modes, because it is a report
derived from the corpus rather than a change to it, and because the mode you
would run to find a gap is the dry run. Its path is printed. Backlog task 021
reads it.

Added 2026-08-31 for backlog task 015.
"""

from datetime import date

import click

from ..database.connection import get_db
from ..database.models import Observation, Watch
from ..routing import (
    TriggerCompileError,
    compile_watches,
    gap_report,
    persist,
    route,
    write_gap_report,
)
from .colors import accent, header, muted, warning

# Why a default at all: near-duplicate clustering of the unrouted set is
# pairwise, so it is quadratic in the number of observations that matched
# nothing -- which is most of them. 500 is a few days of ingestion and runs in
# about a second. --limit 0 means every stored observation and is the honest
# spelling of "I know what I am asking for".
_DEFAULT_LIMIT = 500


def _clause_lines(compiled, per_clause) -> list[str]:
    """One line per trigger clause that fired, so a wide trigger is attributable."""
    lines = []
    for watch in compiled:
        for clause in watch.clauses:
            count = per_clause.get((watch.watch_id, clause.index), 0)
            if count:
                lines.append(f"      clause {clause.index}: {count:>6}  {clause.describe()}")
    return lines


@click.command(name="route")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Report what would route and write no route_candidates rows.",
)
@click.option(
    "--limit",
    type=int,
    default=_DEFAULT_LIMIT,
    show_default=True,
    help="Consider the last N observations. 0 means all of them.",
)
@click.option(
    "--gaps-out",
    type=click.Path(dir_okay=False),
    default=None,
    help="Where to write the unrouted cluster report. Defaults to data/routing/.",
)
@click.option(
    "--no-gaps",
    is_flag=True,
    default=False,
    help="Skip the unrouted clustering. Faster, and loses the coverage-gap signal.",
)
def route_command(dry_run, limit, gaps_out, no_gaps):
    """Route observations to watches with compiled, deterministic predicates."""
    today = date.today()

    with get_db() as session:
        stored = session.query(Observation).count()
        if stored == 0:
            click.echo(
                warning(
                    "No observations are stored, so there is nothing to route. Tier 1 reads "
                    "'observations' and never 'articles'; the 55,249 legacy rows are the "
                    "pre-rewrite archive. See src/database/models.py."
                )
            )
            return

        watch_rows = session.query(Watch).all()
        if not watch_rows:
            click.echo(
                warning(
                    "No watches are stored. Routing with no watches routes nothing, which is "
                    "correct and useless. Run 'watch sync' first."
                )
            )
            return

        try:
            report = route(session, limit=limit or None, today=today)
            compiled = compile_watches(
                [row for row in watch_rows if row.expires is None or row.expires >= today]
            )
        except TriggerCompileError as exc:
            raise click.ClickException(str(exc))

        click.echo(header("ROUTE" + (" (dry run)" if dry_run else "")))
        click.echo(
            muted(
                f"{report.considered} of {stored} stored observation(s), newest first, "
                f"against {len(report.watch_ids)} live watch(es)."
            )
        )
        if report.expired_watch_ids:
            click.echo(
                muted(f"  skipped {len(report.expired_watch_ids)} expired: ")
                + muted(", ".join(report.expired_watch_ids))
            )
        click.echo("=" * 80)

        for watch_id in report.watch_ids:
            count = report.per_watch[watch_id]
            share = count / report.considered if report.considered else 0.0
            click.echo(f"  {accent(watch_id):<48} {count:>6}  ({share:6.2%})")
        click.echo()
        for line in _clause_lines(compiled, report.per_clause):
            click.echo(muted(line))

        click.echo()
        click.echo(
            f"  {'routed':<48} {report.routed_count:>6}  "
            f"({report.routed_count / report.considered:6.2%} of considered)"
        )
        click.echo(
            f"  {'unrouted':<48} {report.unrouted_count:>6}  "
            f"({report.unrouted_count / report.considered:6.2%} of considered)"
        )
        click.echo(
            muted(
                f"  {len(report.links)} link(s), fan-out {report.fan_out:.2f} "
                f"adjudications per observation considered."
            )
        )

        if not no_gaps:
            payload = gap_report(session, report)
            path = write_gap_report(payload, gaps_out)
            clusters = payload["clusters"]
            multi = [c for c in clusters if c["size"] > 1]
            click.echo()
            click.echo(header("UNROUTED CLUSTERS"))
            click.echo(
                muted(
                    f"{len(clusters)} cluster(s), {len(multi)} with more than one member. "
                    f"A large one is a story the environment thought mattered and no watch "
                    f"can see."
                )
            )
            for cluster in clusters[:10]:
                terms = ", ".join(term for term, _ in cluster["terms"][:5])
                click.echo(f"  {cluster['size']:>4}  {cluster['representative_title'][:60]}")
                click.echo(muted(f"        {terms}"))
            if payload["gap_terms"]:
                top = ", ".join(f"{t} ({n})" for t, n in payload["gap_terms"][:12])
                click.echo()
                click.echo(muted(f"  gap terms: {top}"))
            click.echo()
            click.echo(muted(f"  written to {path}"))

        click.echo()
        if dry_run:
            click.echo(
                muted("Nothing was written to route_candidates. Re-run without ")
                + accent("--dry-run")
                + muted(" to record these links.")
            )
            return

        written = persist(session, report)
        click.echo(
            f"routed: {written['inserted']} link(s) inserted, "
            f"{written['already_linked']} already present"
        )
