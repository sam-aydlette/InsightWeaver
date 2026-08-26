"""
Shared ``--beat`` handling for the ledger-reading commands.

``questions``, ``predictions`` and ``forecast`` read the commitment graph back
out. Once any beat has run, the graph holds more than one ledger, so those
commands have to say which one they mean. They answer the same way ``brief``
does: no ``--beat`` is your own ledger, ``--beat NAME`` is that subject's.

Added 2026-08-26 for backlog task 004 (read-side scoping).
"""

import click

from ..context.beat_scope import BeatNotRecorded, BeatTablesMissing, beat_id_by_name

# One decorator, so the flag reads and behaves identically on every command
# that carries it.
beat_option = click.option(
    "--beat",
    "beat_name",
    default=None,
    metavar="NAME",
    help="Read this beat's ledger instead of your own.",
)


def resolve_beat_scope(session, beat_name: str | None) -> int | None:
    """
    Turn a ``--beat NAME`` value into a beat id, or None for the default scope.

    An unrecognised name is an error listing the beats that have actually run,
    rather than an empty result set that would read as "you have nothing here".
    """
    if beat_name is None:
        return None
    try:
        return beat_id_by_name(session, beat_name)
    except (BeatTablesMissing, BeatNotRecorded) as exc:
        raise click.ClickException(str(exc))


def scope_label(beat_name: str | None) -> str:
    """How a heading names the ledger being shown."""
    return f"beat '{beat_name}'" if beat_name else "your ledger"
