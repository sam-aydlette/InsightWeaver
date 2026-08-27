"""
The operator's side of the ledger: stake a claim, then record the outcome.

Every other ledger command reads. These two write, and they are the reason the
graph is a calibration instrument rather than a reading list -- the thing being
calibrated is the operator's judgment, and until these existed the operator had
no way to stake anything.

Both commands are pure local database work: no API key, no network call.

Added 2026-08-27 for backlog task 011.
"""

from datetime import datetime

import click

from ..database.connection import get_db
from ..database.models import (
    PREDICTION_AUTHOR_OPERATOR,
    PREDICTION_OUTCOME_NO,
    PREDICTION_OUTCOME_YES,
    PREDICTION_STATUS_CONTRADICTED,
    PREDICTION_STATUS_OPEN,
    PREDICTION_STATUS_TRIGGERED,
    QUESTION_STATUS_OPEN,
    Prediction,
    Question,
)
from ..utils import utcnow
from .colors import accent, header, muted, success, warning

# The failure this command exists to prevent, stated once so both the help text
# and the rejection message can quote it.
_WHY_DATE_REQUIRED = (
    "A claim with no resolution date can never come due, so it can never be "
    "graded. That is how the ledger accumulated 25 predictions phrased "
    "'X would signal Y' and graded none of them."
)

_WHY_CONFIDENCE_REQUIRED = (
    "A stake with an unstated confidence is a non-commitment in a different "
    "costume. There is deliberately no default."
)

# yes/no is the operator's verdict; the status vocabulary the model's check
# pass already uses is reused so `predictions triggered|contradicted` and
# `forecast` keep working unchanged rather than growing a parallel view.
_OUTCOME_STATUS = {
    PREDICTION_OUTCOME_YES: PREDICTION_STATUS_TRIGGERED,
    PREDICTION_OUTCOME_NO: PREDICTION_STATUS_CONTRADICTED,
}


@click.command(name="predict")
@click.argument("question_id", type=int)
@click.argument("claim")
@click.option(
    "--by",
    "due_by",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    metavar="YYYY-MM-DD",
    help=f"Required. When this claim resolves. {_WHY_DATE_REQUIRED}",
)
@click.option(
    "--confidence",
    "confidence",
    type=float,
    default=None,
    metavar="0.0-1.0",
    help=f"Required. Your stated probability. {_WHY_CONFIDENCE_REQUIRED}",
)
def predict_command(question_id, claim, due_by, confidence):
    """
    Stake a falsifiable claim on a question, with a date and a confidence.

    Both --by and --confidence are rejected at entry when missing. Nothing is
    stored on a rejection.
    """
    text = (claim or "").strip()
    if not text:
        raise click.UsageError("A prediction needs a claim. Nothing was stored.")

    if due_by is None:
        raise click.UsageError(
            f"--by is required. {_WHY_DATE_REQUIRED} "
            "Give a resolution date, e.g. --by 2026-12-31. Nothing was stored."
        )

    if confidence is None:
        raise click.UsageError(
            f"--confidence is required. {_WHY_CONFIDENCE_REQUIRED} "
            "Give a probability, e.g. --confidence 0.7. Nothing was stored."
        )

    if not 0.0 <= confidence <= 1.0:
        raise click.UsageError(
            f"--confidence must be between 0.0 and 1.0; got {confidence}. Nothing was stored."
        )

    now = utcnow()
    if due_by.date() < now.date():
        raise click.UsageError(
            f"--by {due_by.date().isoformat()} is in the past. A claim that was "
            "already resolvable when you made it is not a forecast. Nothing was stored."
        )

    with get_db() as session:
        question = session.query(Question).filter_by(id=question_id).first()
        if question is None:
            raise click.UsageError(
                f"Question Q{question_id} not found. Declare it first with "
                "'questions add'. Nothing was stored."
            )
        if question.status != QUESTION_STATUS_OPEN:
            raise click.UsageError(
                f"Q{question_id} is {question.status}, not open. Nothing was stored."
            )

        prediction = Prediction(
            question_id=question.id,
            observable_text=text,
            # The trigger for an operator claim is the operator, on the date
            # they named. Recorded explicitly so the column keeps meaning the
            # same thing it does for model predictions: what makes this
            # gradeable.
            trigger_condition=(f"Operator judgement on or after {due_by.date().isoformat()}."),
            made_at=now,
            made_in_synthesis_id=None,
            author=PREDICTION_AUTHOR_OPERATOR,
            due_by=due_by,
            confidence=float(confidence),
            status=PREDICTION_STATUS_OPEN,
        )
        session.add(prediction)
        session.commit()

        days_out = (due_by.date() - now.date()).days
        click.echo(
            success(
                f"Staked P{prediction.id} on Q{question.id} at "
                f"{confidence:.0%}, resolving {due_by.date().isoformat()} ({days_out}d out)."
            )
        )
        click.echo(muted(f"  Claim:    {text}"))
        click.echo(muted(f"  Bears on: {question.text}"))
        click.echo(muted(f"  Record the outcome with: resolve {prediction.id} --outcome yes|no"))


@click.command(name="resolve")
@click.argument("prediction_id", type=int)
@click.option(
    "--outcome",
    type=click.Choice([PREDICTION_OUTCOME_YES, PREDICTION_OUTCOME_NO]),
    required=True,
    help="Did the claim, as written, come true?",
)
@click.option(
    "--note",
    required=True,
    help="What settled it. Required: an outcome with no reason is not calibration data.",
)
def resolve_command(prediction_id, outcome, note):
    """
    Record the outcome of a prediction. You resolve; the tool does not.

    Auto-resolving from coverage is deliberately absent: a tool that grades its
    operator's calls using the corpus that produced them is measuring agreement
    with itself.
    """
    now = utcnow()
    with get_db() as session:
        prediction = session.query(Prediction).filter_by(id=prediction_id).first()
        if prediction is None:
            raise click.UsageError(f"Prediction P{prediction_id} not found. Nothing was changed.")

        if prediction.status != PREDICTION_STATUS_OPEN:
            when = (
                prediction.resolved_at.date().isoformat() if prediction.resolved_at else "unknown"
            )
            verdict = f" as '{prediction.outcome}'" if prediction.outcome else ""
            raise click.UsageError(
                f"P{prediction.id} is already {prediction.status}{verdict} "
                f"(recorded {when}). A resolved prediction is not editable. "
                "Nothing was changed."
            )

        prediction.outcome = outcome
        prediction.status = _OUTCOME_STATUS[outcome]
        # Separate from due_by on purpose: how late you graded it is itself
        # calibration data.
        prediction.resolved_at = now
        prediction.resolution_note = note
        question_text = prediction.question.text if prediction.question else None
        session.commit()

        click.echo(success(f"P{prediction.id} resolved: {outcome}."))
        click.echo(muted(f"  Claim: {prediction.observable_text}"))
        if question_text:
            click.echo(muted(f"  Bears on: {question_text}"))
        click.echo(muted(f"  Note: {note}"))
        click.echo(muted(f"  {_timing_phrase(prediction.due_by, now)}"))


def _timing_phrase(due_by: datetime | None, resolved_at: datetime) -> str:
    """How the resolution date sits against the due date."""
    if due_by is None:
        return f"Resolved {resolved_at.date().isoformat()} (no due date on record)."
    delta = (resolved_at.date() - due_by.date()).days
    stamp = f"Due {due_by.date().isoformat()}, resolved {resolved_at.date().isoformat()}"
    if delta > 0:
        return f"{stamp} -- {delta}d late."
    if delta < 0:
        return f"{stamp} -- {-delta}d early, before it came due."
    return f"{stamp} -- on the day."


def render_due_prediction(p: Prediction, now: datetime) -> None:
    """One line-block for a prediction awaiting the operator's verdict."""
    overdue = (now.date() - p.due_by.date()).days if p.due_by else None
    when = p.due_by.date().isoformat() if p.due_by else "no due date"
    lateness = f" ({overdue}d ago)" if overdue else ""
    click.echo(f"  {accent(f'P{p.id}')} {warning('due ' + when)}{muted(lateness)}")
    click.echo(f"      {p.observable_text}")
    if p.confidence is not None:
        click.echo(muted(f"      You said: {p.confidence:.0%}"))
    click.echo(muted(f"      resolve {p.id} --outcome yes|no --note '...'"))
    click.echo()


def due_predictions_header(count: int) -> None:
    """Heading for the awaiting-verdict block, shared by `forecast --due`."""
    click.echo(header(f"AWAITING YOUR VERDICT ({count})"))
    click.echo(
        muted("Your claims whose resolution date has passed. You grade these; nothing else does.")
    )
    click.echo()
