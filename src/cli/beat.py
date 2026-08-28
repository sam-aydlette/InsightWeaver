"""
Beat Command - test a beat's sources against events that actually happened.

``insightweaver beat coverage NAME`` runs the beat's declared
``coverage_probes`` against the stored corpus and reports, per probe, whether an
article the beat's own sources carried would have shown the operator the event,
and which source that was.

It exits non-zero when a probe went unmatched, so it can gate a release the way
a test does. It also exits non-zero when *nothing was measured* -- no probes
declared, or every probe inconclusive -- because "no evidence of a gap" and "no
evidence" are the same green tick and only one of them is good news. That
conflation is the whole reason backlog task 010 exists.

No model is called and nothing is written. Added 2026-08-27.
"""

import click

from ..config.beats import BeatNotFound, BeatValidationError, load_beat
from ..context.coverage_probe import (
    STATUS_INCONCLUSIVE,
    STATUS_MATCHED,
    STATUS_UNMATCHED,
    CoverageReport,
    ProbeResult,
    run_coverage_probes,
)
from ..database.connection import SessionLocal
from .colors import accent, error, header, muted, success, warning

# Exit codes. Distinct on purpose: a gate that fails and a gate that could not
# run are different alarms, and collapsing them would let a rotted probe set
# read as a broken beat (or, worse, the reverse).
EXIT_OK = 0
EXIT_UNMATCHED = 1
EXIT_NOTHING_MEASURED = 2

_STATUS_STYLE = {
    STATUS_MATCHED: success,
    STATUS_UNMATCHED: error,
    STATUS_INCONCLUSIVE: warning,
}


@click.group(name="beat")
def beat_command():
    """Inspect a beat's configuration against the corpus."""
    pass


@beat_command.command(name="coverage")
@click.argument("name")
@click.option(
    "--show",
    type=click.Choice(["all", "problems"]),
    default="all",
    help="'problems' prints only the probes that did not pass.",
)
def coverage(name, show):
    """
    Check whether this beat's sources can see events that actually happened.

    Each probe in the beat's `coverage_probes` names a real past event and the
    words any report of it would carry. A probe passes only when a feed this
    beat subscribes to carried a matching article inside the probe's window.

    Exits 1 if any probe is unmatched, 2 if nothing could be measured.
    """
    try:
        beat = load_beat(name)
    except (BeatNotFound, BeatValidationError) as exc:
        raise click.ClickException(str(exc))

    if not beat.coverage_probes:
        click.echo(error(f"Beat '{beat.name}' declares no coverage_probes."))
        click.echo(
            muted(
                "Nothing was measured. An article count tells you ingestion is running;\n"
                "only a probe tells you it reaches this domain. Name three things that\n"
                "actually happened in this beat's subject this month and declare them in\n"
                f"{beat.config_path} under 'coverage_probes'."
            )
        )
        raise SystemExit(EXIT_NOTHING_MEASURED)

    # Read-only by construction: this session is never committed, because the
    # corpus is shared and a question about it must not alter it.
    session = SessionLocal()
    try:
        report = run_coverage_probes(session, beat)
    finally:
        session.rollback()
        session.close()

    _print_report(report, beat.config_path, show)
    code = _exit_code(report)
    if code != EXIT_OK:
        raise SystemExit(code)


def _exit_code(report: CoverageReport) -> int:
    """
    The verdict, as a shell sees it.

    ``EXIT_NOTHING_MEASURED`` for an all-inconclusive run is the load-bearing
    case: with no probe answered there is no evidence the beat reaches anything,
    and exiting 0 there would hand a gate the same green tick a real pass gets.
    """
    if report.unmatched:
        return EXIT_UNMATCHED
    if not report.conclusive:
        return EXIT_NOTHING_MEASURED
    return EXIT_OK


def _print_report(report: CoverageReport, config_path: str, show: str) -> None:
    click.echo(header(f"COVERAGE PROBES - beat '{report.beat_name}'"))
    click.echo("=" * 80)
    span = (
        f"{report.earliest.date().isoformat()} to {report.latest.date().isoformat()}"
        if report.earliest and report.latest
        else "no dated articles"
    )
    click.echo(muted(f"  sources: {len(report.feed_names)} feeds | corpus span: {span}"))
    click.echo(muted(f"  probes declared in {config_path}"))
    click.echo()

    for result in report.results:
        if show == "problems" and result.matched:
            continue
        _print_result(result)

    _print_summary(report)


def _print_result(result: ProbeResult) -> None:
    style = _STATUS_STYLE[result.status]
    start, end = result.window
    click.echo(f"{style(f'[{result.status}]')} {accent(result.probe.what)}")
    click.echo(muted(f"  event {result.probe.date.isoformat()} | window {start} .. {end}"))
    click.echo(muted(f"  requires {result.probe.describe()}"))
    click.echo(muted(f"  {result.articles_in_window} article(s) from this beat's feeds in window"))

    if result.status == STATUS_MATCHED:
        click.echo(muted(f"  {result.match_count} matching article(s); earliest shown"))
        for match in result.matches:
            click.echo(
                f"    {success('seen by')} {accent(match.feed_name)} "
                f"{muted(f'({match.published_day})')}"
            )
            click.echo(muted(f"      {match.title}"))
    elif result.status == STATUS_UNMATCHED:
        click.echo(error("    no article from this beat's feeds matched"))
        if result.missing_terms:
            click.echo(muted(f"      closest article lacked: {', '.join(result.missing_terms)}"))
        for group in result.unsatisfied_groups:
            click.echo(muted(f"      closest article lacked any of: {', '.join(group)}"))
        if result.elsewhere:
            click.echo(
                warning(
                    f"    but {result.elsewhere_count} article(s) elsewhere in the corpus "
                    f"matched, outside this beat's sources:"
                )
            )
            for match in result.elsewhere:
                click.echo(f"      {accent(match.feed_name)} {muted(f'({match.published_day})')}")
                click.echo(muted(f"        {match.title}"))
            click.echo(muted("      the sources are reachable; this beat's list is what missed."))
        else:
            click.echo(muted("      and no feed anywhere in the corpus carried it either."))
    else:
        click.echo(warning(f"    {result.reason}"))
        click.echo(muted("      neither a pass nor a failure; still counted below."))
    click.echo()


def _print_summary(report: CoverageReport) -> None:
    """
    The counts, with the denominator always the number of probes declared.

    Printed as `matched + unmatched + inconclusive of N declared` so the
    arithmetic is visible. A probe set decaying out of retention has to show up
    here as a shrinking number of *answered* probes rather than as a clean sweep
    of the few that still match.
    """
    click.echo("=" * 80)
    matched, unmatched, inconclusive = (
        len(report.matched),
        len(report.unmatched),
        len(report.inconclusive),
    )
    click.echo(
        f"{success(f'{matched} matched')} + {error(f'{unmatched} unmatched')} + "
        f"{warning(f'{inconclusive} inconclusive')} of {report.total} probe(s) declared"
    )

    if unmatched:
        click.echo(
            error(
                f"FAIL: {unmatched} event(s) this beat claims to cover left no trace "
                f"in its sources."
            )
        )
    elif not report.conclusive:
        click.echo(
            warning(
                "NOT MEASURED: every probe was inconclusive. This is not a pass -- the "
                "corpus could not answer a single one of them."
            )
        )
    else:
        click.echo(success(f"PASS: {matched} of {report.total} probe(s) answered, none missed."))

    if inconclusive and not unmatched and report.conclusive:
        click.echo(
            muted(
                f"  {inconclusive} probe(s) could not be answered and are counted above, "
                f"not dropped."
            )
        )
