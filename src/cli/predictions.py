"""
Predictions Command - Inspect the predictions ledger and the tool's own
calibration track record.
"""

from datetime import timedelta

import click

from ..context.beat_scope import prediction_scope_filter
from ..database.connection import get_db
from ..database.models import (
    PREDICTION_AUTHOR_MODEL,
    PREDICTION_AUTHOR_OPERATOR,
    PREDICTION_OUTCOME_NO,
    PREDICTION_OUTCOME_YES,
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
            f"{accent(f'P{p.id}')}  [{p.author}]  "
            f"{muted(f'made {p.made_at.date().isoformat()} ({age_days}d ago)')}"
        )
        click.echo(f"  Observable: {p.observable_text}")
        click.echo(f"  Trigger: {muted(p.trigger_condition)}")
        if p.due_by is not None or p.confidence is not None:
            due = p.due_by.date().isoformat() if p.due_by else "no date"
            conf = f"{p.confidence:.0%}" if p.confidence is not None else "no confidence"
            click.echo(muted(f"  Staked at {conf}, resolving {due}"))
        click.echo(f"  Bears on: {muted(question_text)}")
        if show_resolution and p.outcome:
            click.echo(muted(f"  Outcome: {p.outcome} (recorded {_resolved_stamp(p)})"))
        if show_resolution and p.resolution_note:
            click.echo(f"  {p.resolution_note}")
        click.echo()


def _resolved_stamp(p: Prediction) -> str:
    """Resolution date, and how it sat against the due date."""
    if p.resolved_at is None:
        return "date unknown"
    stamp = p.resolved_at.date().isoformat()
    if p.due_by is None:
        return stamp
    delta = (p.resolved_at.date() - p.due_by.date()).days
    if delta > 0:
        return f"{stamp}, {delta}d after it came due"
    if delta < 0:
        return f"{stamp}, {-delta}d before it came due"
    return f"{stamp}, on the day"


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

    Split by author since 2026-08-27 (backlog task 011): the calibration figure
    counts operator predictions only. Model predictions are reported under
    their own heading and are never mixed in -- a track record blending the
    two measures nothing.
    """
    cutoff = utcnow() - timedelta(days=days)
    with get_db() as session:
        beat_id = resolve_beat_scope(session, beat_name)
        window = session.query(Prediction).filter(
            Prediction.made_at >= cutoff,
            prediction_scope_filter(session, beat_id),
        )
        if window.count() == 0:
            click.echo(
                muted(f"No predictions made in the last {days} days in {scope_label(beat_name)}.")
            )
            return

        click.echo(header(f"CALIBRATION RECORD (last {days} days, {scope_label(beat_name)})"))
        click.echo("=" * 80)
        click.echo()
        _render_operator_record(window)
        click.echo()
        _render_model_record(window)


def _status_counts(window) -> dict[str, int]:
    """Status tally for one slice of the ledger."""
    return {
        "open": window.filter(Prediction.status == PREDICTION_STATUS_OPEN).count(),
        "triggered": window.filter(Prediction.status == PREDICTION_STATUS_TRIGGERED).count(),
        "contradicted": window.filter(Prediction.status == PREDICTION_STATUS_CONTRADICTED).count(),
        "expired": window.filter(Prediction.status == PREDICTION_STATUS_EXPIRED).count(),
    }


def _render_operator_record(window) -> None:
    """
    The calibration figure. Operator predictions only.

    A plain hit rate on purpose -- how often the claim, as written, came true.
    No weighting or Brier-style aggregation; that is a later decision once
    there is real data to aggregate.
    """
    mine = window.filter(Prediction.author == PREDICTION_AUTHOR_OPERATOR)
    total = mine.count()

    click.echo(header("YOUR CALIBRATION (operator predictions only)"))
    if total == 0:
        click.echo(
            muted(
                "  You have staked nothing in this window. The calibration figure "
                'counts only claims you made: \'predict <question-id> "..." '
                "--by DATE --confidence N'."
            )
        )
        return

    right = mine.filter(Prediction.outcome == PREDICTION_OUTCOME_YES).count()
    wrong = mine.filter(Prediction.outcome == PREDICTION_OUTCOME_NO).count()
    counts = _status_counts(mine)
    resolved = right + wrong

    click.echo(f"  Claims staked:        {total}")
    click.echo(f"  {success('Came true')}:            {right}")
    click.echo(f"  {warning('Did not')}:              {wrong}")
    click.echo(f"  {muted('Still open')}:           {counts['open']}")
    if counts["expired"]:
        click.echo(f"  {muted('Expired unjudged')}:     {counts['expired']}")
    click.echo()
    if resolved:
        click.echo(f"  Hit rate: {right}/{resolved} = {right / resolved:.0%}.")
    else:
        click.echo(muted("  Nothing of yours has been resolved yet in this window."))


def _render_model_record(window) -> None:
    """
    The model's predictions, reported separately and never folded into the
    figure above. They stay in the ledger as prompts -- suggestions about what
    is worth holding an opinion on -- not as claims anyone staked.
    """
    theirs = window.filter(Prediction.author == PREDICTION_AUTHOR_MODEL)
    total = theirs.count()

    click.echo(header("MODEL PREDICTIONS (not counted toward your calibration)"))
    if total == 0:
        click.echo(muted("  The model made none in this window."))
        return

    counts = _status_counts(theirs)
    click.echo(
        muted(
            f"  {total} made | {counts['triggered']} triggered | "
            f"{counts['contradicted']} contradicted | {counts['open']} open | "
            f"{counts['expired']} expired"
        )
    )
    click.echo(
        muted(
            "  Reported for transparency only. These are the tool's own "
            "observables, not your judgement."
        )
    )
