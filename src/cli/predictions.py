"""
Predictions Command - Inspect the predictions ledger and the tool's own
calibration track record.
"""

from datetime import timedelta

import click

from ..context.beat_scope import prediction_scope_filter
from ..database.connection import get_db
from ..database.models import (
    PREDICTION_STATUS_CONTRADICTED,
    PREDICTION_STATUS_EXPIRED,
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    Prediction,
)
from ..utils import utcnow
from .colors import accent, header, muted, success, warning
from .scope import beat_option, resolve_beat_scope, scope_label


@click.group(name="predictions")
def predictions_command():
    """Inspect the predictions ledger and calibration record."""
    pass


def _print_predictions(rows, show_resolution: bool):
    now = utcnow()
    for p in rows:
        age_days = (now - p.made_at).days
        question_text = p.question.text if p.question else "(unknown question)"
        click.echo(
            f"{accent(f'P{p.id}')}  {muted(f'made {p.made_at.date().isoformat()} ({age_days}d ago)')}"
        )
        click.echo(f"  Observable: {p.observable_text}")
        click.echo(f"  Trigger: {muted(p.trigger_condition)}")
        click.echo(f"  Bears on: {muted(question_text)}")
        if show_resolution and p.resolution_note:
            click.echo(f"  {p.resolution_note}")
        click.echo()


@predictions_command.command(name="open")
@click.option("--limit", "-n", type=int, default=50)
@beat_option
def open_predictions(limit, beat_name):
    """
    List predictions still waiting on coverage.

    Scoped: without --beat this is your own ledger only.
    """
    with get_db() as session:
        beat_id = resolve_beat_scope(session, beat_name)
        rows = (
            session.query(Prediction)
            .filter(
                Prediction.status == PREDICTION_STATUS_OPEN,
                prediction_scope_filter(session, beat_id),
            )
            .order_by(Prediction.made_at.asc())
            .limit(limit)
            .all()
        )
        if not rows:
            click.echo(muted("No open predictions in " + scope_label(beat_name) + "."))
            return
        click.echo(header(f"OPEN PREDICTIONS ({len(rows)} shown, {scope_label(beat_name)})"))
        click.echo("=" * 80)
        _print_predictions(rows, show_resolution=False)


@predictions_command.command(name="triggered")
@click.option("--limit", "-n", type=int, default=50)
@beat_option
def triggered_predictions(limit, beat_name):
    """
    List predictions whose observable showed up in later coverage.

    Scoped: without --beat this is your own ledger only.
    """
    with get_db() as session:
        beat_id = resolve_beat_scope(session, beat_name)
        rows = (
            session.query(Prediction)
            .filter(
                Prediction.status == PREDICTION_STATUS_TRIGGERED,
                prediction_scope_filter(session, beat_id),
            )
            .order_by(Prediction.resolved_at.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            click.echo(muted("No triggered predictions yet in " + scope_label(beat_name) + "."))
            return
        click.echo(header(f"TRIGGERED PREDICTIONS ({len(rows)} shown, {scope_label(beat_name)})"))
        click.echo("=" * 80)
        _print_predictions(rows, show_resolution=True)


@predictions_command.command(name="contradicted")
@click.option("--limit", "-n", type=int, default=50)
@beat_option
def contradicted_predictions(limit, beat_name):
    """
    List predictions later coverage explicitly went against.

    Scoped: without --beat this is your own ledger only.
    """
    with get_db() as session:
        beat_id = resolve_beat_scope(session, beat_name)
        rows = (
            session.query(Prediction)
            .filter(
                Prediction.status == PREDICTION_STATUS_CONTRADICTED,
                prediction_scope_filter(session, beat_id),
            )
            .order_by(Prediction.resolved_at.desc())
            .limit(limit)
            .all()
        )
        if not rows:
            click.echo(muted("No contradicted predictions yet in " + scope_label(beat_name) + "."))
            return
        click.echo(
            header(f"CONTRADICTED PREDICTIONS ({len(rows)} shown, {scope_label(beat_name)})")
        )
        click.echo("=" * 80)
        _print_predictions(rows, show_resolution=True)


@predictions_command.command(name="track-record")
@click.option("--days", "-d", type=int, default=90, help="Window in days (default: 90).")
@beat_option
def track_record(days, beat_name):
    """
    Show the tool's calibration record over a rolling window.

    Scoped, and this is the case that matters most: a calibration number is
    only meaningful for one ledger. Mixing a beat's resolved observables into
    your own hit rate would corrupt the one figure the tool exists to be
    honest about.
    """
    cutoff = utcnow() - timedelta(days=days)
    with get_db() as session:
        beat_id = resolve_beat_scope(session, beat_name)
        window = session.query(Prediction).filter(
            Prediction.made_at >= cutoff,
            prediction_scope_filter(session, beat_id),
        )
        total = window.count()
        if total == 0:
            click.echo(
                muted(f"No predictions made in the last {days} days in {scope_label(beat_name)}.")
            )
            return

        counts = {
            "open": window.filter(Prediction.status == PREDICTION_STATUS_OPEN).count(),
            "triggered": window.filter(Prediction.status == PREDICTION_STATUS_TRIGGERED).count(),
            "contradicted": window.filter(
                Prediction.status == PREDICTION_STATUS_CONTRADICTED
            ).count(),
            "expired": window.filter(Prediction.status == PREDICTION_STATUS_EXPIRED).count(),
        }
        resolved = counts["triggered"] + counts["contradicted"]

        click.echo(header(f"CALIBRATION RECORD (last {days} days, {scope_label(beat_name)})"))
        click.echo("=" * 80)
        click.echo(f"  Predictions made:     {total}")
        click.echo(f"  {success('Triggered')}:            {counts['triggered']}")
        click.echo(f"  {warning('Contradicted')}:         {counts['contradicted']}")
        click.echo(f"  {muted('Still open')}:           {counts['open']}")
        click.echo(f"  {muted('Expired (no signal)')}:  {counts['expired']}")
        click.echo()
        if resolved:
            hit_rate = counts["triggered"] / resolved
            click.echo(
                f"  Of {resolved} resolved predictions, "
                f"{hit_rate:.0%} were triggered rather than contradicted."
            )
        else:
            click.echo(muted("  No predictions resolved yet in this window."))
