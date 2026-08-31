"""
Watch command - what is being monitored, and for which decision.

Two subcommands and deliberately no third:

``watch sync`` reads the hand-authored Position and watch files and makes the
table match them. It takes no arguments describing a watch, because it is not a
way to write one -- it is the file's only route into the database.

``watch list`` shows what is stored: each watch, its belief, the decision it
serves, and how long until it expires.

**There is no ``watch add``.** It would satisfy no acceptance criterion in
backlog task 013 and it is the seam through which auto-generated watches
arrive: once a command can take ``--claim`` and ``--belief`` from a caller, the
caller can be a model, and invariant 6 -- the system never authors its own
watches -- is then a convention rather than a property. The check that this
stays true is in ``tests/cli/test_watch_cli.py``, asserting on the registered
subcommands and their parameters rather than on anyone's intentions.

Added 2026-08-31 for backlog task 013.
"""

from datetime import date

import click

from ..database.connection import get_db
from ..database.models import Watch as WatchRow
from ..position import PositionError, WatchError, load_position, load_watches, sync_watches
from .colors import accent, error, header, muted, warning


def _load_from_files(today: date | None = None):
    """
    Position and watches, validated together, or a ClickException naming why not.

    The two files are loaded as a pair because a watch is only valid against a
    Position: ``so_what.decision`` has to name a decision that exists.
    """
    try:
        position = load_position(today=today)
        watches = load_watches(position=position, today=today)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc))
    except (PositionError, WatchError) as exc:
        raise click.ClickException(str(exc))
    return position, watches


def _echo_warnings(position) -> None:
    """Print the Position's drift warnings. They warn; they never block."""
    for note in position.warnings:
        click.echo(warning(f"  ! {note}"))


def _expiry_phrase(expires: date, today: date) -> str:
    days = (expires - today).days
    if days < 0:
        return f"{expires.isoformat()} (expired {-days}d ago)"
    if days == 0:
        return f"{expires.isoformat()} (expires today)"
    return f"{expires.isoformat()} ({days}d to expiry)"


@click.group(name="watch")
def watch_command():
    """Pre-registered watches: what is monitored, and for which decision."""
    pass


@watch_command.command(name="sync")
def sync_watch_set():
    """Make the watches table match the hand-authored files."""
    position, watches = _load_from_files()

    click.echo(header("WATCH SYNC"))
    click.echo(muted(f"position: {position.path}"))
    click.echo(muted(f"watches:  {watches[0].source_path if watches else 'none'}"))
    if position.warnings:
        click.echo()
        click.echo(warning("Position warnings (nothing was rejected on these):"))
        _echo_warnings(position)
    click.echo()

    with get_db() as session:
        summary = sync_watches(session, watches)

    for label in ("added", "updated", "removed"):
        ids = summary[label]
        if ids:
            click.echo(f"  {label}: {', '.join(sorted(ids))}")
    if not any(summary.values()):
        click.echo(muted("  no change"))
    click.echo()
    click.echo(muted(f"{len(watches)} watch(es) now match {position.path.name}'s decisions."))


@watch_command.command(name="list")
def list_watches():
    """Show each watch, its belief, its decision, and days to expiry."""
    today = date.today()

    # The decision *names* come from Position, which may not be present on this
    # machine -- it lives in a private repo. The keys are stored on the row, so
    # the listing degrades to keys rather than failing.
    names: dict[str, str] = {}
    position_note = None
    try:
        position = load_position()
        names = {d.key: d.name for d in position.decisions}
    except (FileNotFoundError, PositionError) as exc:
        position_note = str(exc).splitlines()[0]

    with get_db() as session:
        rows = session.query(WatchRow).order_by(WatchRow.expires).all()

        if not rows:
            click.echo(muted("No watches stored. Run 'watch sync' to load the checked-in files."))
            return

        click.echo(header("WATCHES"))
        click.echo(
            muted(
                "Every watch names a decision. A watch that named none would not be "
                "monitoring, and the loader refuses to store one."
            )
        )
        if position_note:
            click.echo(error(f"Position unreadable, showing decision keys only: {position_note}"))
        click.echo("=" * 80)

        for row in rows:
            click.echo(accent(row.id))
            click.echo(f"  claim:    {row.claim}")
            click.echo(f"  belief:   {row.belief:.2f}")
            decision = names.get(row.decision_key)
            suffix = f" -- {decision}" if decision else ""
            click.echo(f"  decision: {row.decision_key}{suffix}")
            click.echo(f"  so what:  {row.so_what}")
            click.echo(f"  expires:  {_expiry_phrase(row.expires, today)}")
            click.echo(
                muted(f"  stale after {row.staleness_alert_days}d of silence")
                + muted(f"  |  {len(row.triggers or [])} trigger clause(s)")
            )
            click.echo()
