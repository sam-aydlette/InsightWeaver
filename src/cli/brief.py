"""
Brief command - what moved, what is due, what is watched, what went quiet.

Run by hand. The rendered bytes are a pure function of the database, ``--since``
and ``--as-of``: the same three give the same bytes, and the suite asserts it
by rendering twice. Each render is recorded in ``briefs`` unless ``--dry-run``
is given, and the default window opens at the ``as_of`` of the last brief
delivered before the start of today, so a second run the same morning
reproduces the first instead of reporting "nothing since ten minutes ago".

A Position that cannot be read is printed in the header with every problem the
loader found, DUE says its decisions are missing, the review banner is up, and
the brief still renders: the watches are in the database, and the header's job
is to say what the machinery could not do. Nothing here calls a model.

The header's source list is compact by default: a source that answered is
folded into a count, a source whose last attempt failed is always printed in
full. ``--verbose`` prints every source individually.

Added 2026-09-22 for backlog task 031; ``--verbose`` added 2026-09-24.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import click
from sqlalchemy.orm import Session

from ..brief import render, select_brief
from ..database.connection import get_db
from ..database.models import BriefRun
from ..position import PositionError, load_position
from ..utils import utcnow
from ..utils.cadence import InvalidCadence, parse_cadence
from .colors import muted

DEFAULT_WINDOW_DAYS = 7


def default_since(session: Session, as_of: datetime) -> datetime:
    """The ``as_of`` of the last brief delivered before today's start, else a week back."""
    day_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    previous = (
        session.query(BriefRun.as_of)
        .filter(BriefRun.as_of < day_start)
        .order_by(BriefRun.as_of.desc(), BriefRun.id.desc())
        .first()
    )
    return previous[0] if previous else as_of - timedelta(days=DEFAULT_WINDOW_DAYS)


def _parse_as_of(raw: str) -> datetime:
    """ISO 8601, to naive UTC, which is what every stored timestamp is."""
    try:
        value = datetime.fromisoformat(raw)
    except ValueError:
        raise click.ClickException(f"--as-of {raw!r} is not an ISO 8601 date-time")
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value


@click.command(name="brief")
@click.option(
    "--since",
    "since_raw",
    default=None,
    help="Window (7d, 2w). Default: since the last brief before today, else 7d.",
)
@click.option(
    "--as-of", "as_of_raw", default=None, help="Render as of this ISO 8601 moment. Default: now."
)
@click.option("--format", "fmt", type=click.Choice(["terminal", "md"]), default="terminal")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write the brief here instead of printing it.",
)
@click.option("--dry-run", is_flag=True, default=False, help="Render without recording the brief.")
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="List every source in the header, not just the ones that failed.",
)
def brief_command(since_raw, as_of_raw, fmt, output, dry_run, verbose):
    """Render the brief: header, MOVED, DUE, WATCHING, QUIET."""
    as_of = _parse_as_of(as_of_raw) if as_of_raw else utcnow()
    window = None
    if since_raw:
        try:
            window = parse_cadence(since_raw)
        except InvalidCadence as exc:
            raise click.ClickException(str(exc))

    position = None
    problem = None
    try:
        position = load_position(today=as_of.date())
    except (FileNotFoundError, PositionError) as exc:
        problem = str(exc)

    with get_db() as session:
        since = as_of - window if window is not None else default_since(session, as_of)
        brief = select_brief(
            session, as_of=as_of, since=since, position=position, position_problem=problem
        )
        text = render(brief, markdown=fmt == "md", verbose=verbose)

        # Deliver first, record second: a row for a brief nobody received
        # would move the next default window past a week nobody read.
        if output is not None:
            try:
                output.write_text(text, encoding="utf-8")
            except OSError as exc:
                raise click.ClickException(f"could not write {output}: {exc}")
            click.echo(muted(f"wrote {output}"))
        else:
            click.echo(text, nl=False)

        if not dry_run:
            session.add(
                BriefRun(
                    as_of=as_of,
                    since=since,
                    moved=len(brief.moved),
                    quiet=len(brief.quiet_watches),
                    rendered_sha=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                )
            )
