"""
Replay command - rebuild Evidence from Observations and show what changed.

``--commit`` is required to persist, and that is the whole shape of this
command. A replay that wrote by default would destroy the before-state at
exactly the moment you wanted to compare against it: you would have run the
thing that answers "what did my prompt change do" and, in answering, made the
question unanswerable. Printing the diff and requiring one more flag costs a
keystroke and preserves the property the harness exists to provide.

Three ways to use it:

  replay --prompt-version v1
      Recompute v1 and diff against v1's stored rows. An empty diff is the
      reproducibility check: a deterministic adjudicator changes nothing.

  replay --prompt-version v2 --against v1
      Diff v2's output against v1's stored rows. This is the prompt-change
      review.

  replay --prompt-version v2 --commit
      Make the stored rows for v2 equal what v2 just produced. Touches no other
      version's rows, and refuses if v2 disagrees with itself.

Added 2026-08-31 for backlog task 014.
"""

import click

from ..database.connection import get_db
from ..database.models import Observation, Watch
from ..evidence import (
    NondeterministicReplay,
    UnknownPromptVersion,
    commit,
    diff,
    format_diff,
    load_adjudicator,
    rebuild,
    resolve,
    stored_evidence,
)
from .colors import accent, header, muted, warning


def _adjudicator_for(prompt_version: str, path: str | None):
    """
    The adjudicator to run, and a check that it is the one being labelled.

    A ``--adjudicator`` whose own ``prompt_version`` disagrees with
    ``--prompt-version`` is refused rather than reconciled. The label written on
    every evidence row has to be the name the adjudicator answers to, or the
    column is decoration.
    """
    try:
        adjudicator = load_adjudicator(path) if path else resolve(prompt_version)
    except UnknownPromptVersion as exc:
        raise click.ClickException(str(exc))
    except (ImportError, TypeError, ValueError) as exc:
        raise click.ClickException(f"could not load adjudicator {path!r}: {exc}")

    if adjudicator.prompt_version != prompt_version:
        raise click.ClickException(
            f"the adjudicator loaded from {path!r} calls itself "
            f"{adjudicator.prompt_version!r}, but --prompt-version says "
            f"{prompt_version!r}. Refusing to label its output with a name it does "
            f"not answer to."
        )
    return adjudicator


@click.command(name="replay")
@click.option(
    "--prompt-version",
    required=True,
    help="The adjudication prompt version to run and to label its output with.",
)
@click.option(
    "--against",
    default=None,
    help="Diff against this version's stored evidence instead of --prompt-version's.",
)
@click.option(
    "--adjudicator",
    "adjudicator_path",
    default=None,
    help="Load 'module:attr' instead of the registered adjudicator for this version.",
)
@click.option("--limit", type=int, default=None, help="Replay only the first N observations.")
@click.option(
    "--commit",
    "do_commit",
    is_flag=True,
    default=False,
    help="Persist the replayed evidence. Without this, nothing is written.",
)
def replay_command(prompt_version, against, adjudicator_path, limit, do_commit):
    """Rebuild Evidence from Observations and print the diff. Writes only with --commit."""
    baseline_version = against or prompt_version
    adjudicator = _adjudicator_for(prompt_version, adjudicator_path)

    with get_db() as session:
        observations = session.query(Observation).count()
        watches = session.query(Watch).count()

        if observations == 0:
            click.echo(
                warning(
                    "No observations are stored, so there is nothing to replay. "
                    "Evidence is rebuilt from observations alone; the 55,249 legacy "
                    "'articles' rows are not observations. See src/database/models.py."
                )
            )
            return

        replayed = rebuild(session, adjudicator, limit=limit)
        baseline = stored_evidence(session, baseline_version)
        result = diff(replayed, baseline)

        click.echo(header("REPLAY"))
        click.echo(format_diff(result, prompt_version, baseline_version, observations, watches))
        click.echo()

        if not do_commit:
            click.echo(
                muted(
                    "Nothing was written. Re-run with "
                    + accent("--commit")
                    + muted(" to persist this version's evidence.")
                )
            )
            return

        try:
            written = commit(session, prompt_version, replayed)
        except NondeterministicReplay as exc:
            raise click.ClickException(str(exc))

        click.echo(
            f"committed {prompt_version}: {written['inserted']} inserted, "
            f"{written['deleted']} deleted"
        )
