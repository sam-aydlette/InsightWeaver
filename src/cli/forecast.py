"""
Forecast Command - A derived view over the predictions ledger and question
graph. No separate forecast engine; what you see here is exactly what the
synthesis has already committed to as falsifiable observables, organized
by whether each one has resolved.
"""

from datetime import datetime, timedelta

import click

from ..database.connection import get_db
from ..database.models import (
    PREDICTION_STATUS_CONTRADICTED,
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    Prediction,
    Question,
)
from .colors import accent, header, muted, success, warning


@click.command(name="forecast")
@click.option(
    "--days",
    "-d",
    type=int,
    default=60,
    help="Window for the resolved track record (default: 60 days).",
)
def forecast_command(days):
    """Show open observables and the recently-resolved record."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    with get_db() as session:
        open_preds = (
            session.query(Prediction)
            .filter(Prediction.status == PREDICTION_STATUS_OPEN)
            .order_by(Prediction.made_at.asc())
            .all()
        )
        resolved = (
            session.query(Prediction)
            .filter(
                Prediction.status.in_(
                    [PREDICTION_STATUS_TRIGGERED, PREDICTION_STATUS_CONTRADICTED]
                ),
                Prediction.resolved_at >= cutoff,
            )
            .order_by(Prediction.resolved_at.desc())
            .all()
        )

        click.echo(header("FORECAST"))
        click.echo(
            muted(
                "A derived view over the predictions ledger -- not a separate engine. "
                "What you see here is exactly what past syntheses committed to as "
                "falsifiable observables."
            )
        )
        click.echo("=" * 80)
        click.echo()

        click.echo(header("KNOWN UNKNOWNS"))
        click.echo(muted("Open observables -- explicit triggers, not yet resolved."))
        click.echo()
        if not open_preds:
            click.echo(muted("  No open observables."))
        else:
            for p in open_preds:
                _render_open_prediction(p)
        click.echo()

        click.echo(header(f"KNOWN KNOWNS (last {days} days)"))
        click.echo(muted("Observables later coverage triggered or contradicted."))
        click.echo()
        if not resolved:
            click.echo(muted("  No resolutions in this window."))
        else:
            triggered = [p for p in resolved if p.status == PREDICTION_STATUS_TRIGGERED]
            contradicted = [p for p in resolved if p.status == PREDICTION_STATUS_CONTRADICTED]
            for p in triggered:
                _render_resolved_prediction(p, success("triggered"))
            for p in contradicted:
                _render_resolved_prediction(p, warning("contradicted"))

        click.echo()
        click.echo(
            muted(
                "Note: the 'unknown unknowns' bucket has been removed by design. "
                "The tool does not fabricate observables it cannot ground in evidence."
            )
        )


def _question_tag(question: Question | None) -> str:
    if question is None:
        return ""
    return f"[Q{question.id}] "


def _render_open_prediction(p: Prediction) -> None:
    tag = _question_tag(p.question)
    click.echo(f"  {accent(f'P{p.id}')} {muted(tag)}{p.observable_text}")
    click.echo(f"      Trigger: {muted(p.trigger_condition)}")
    if p.question:
        click.echo(f"      Bears on: {muted(p.question.text)}")
    click.echo()


def _render_resolved_prediction(p: Prediction, status_label: str) -> None:
    tag = _question_tag(p.question)
    click.echo(f"  {accent(f'P{p.id}')} [{status_label}] {muted(tag)}{p.observable_text}")
    if p.resolution_note:
        click.echo(f"      {p.resolution_note}")
    click.echo()
