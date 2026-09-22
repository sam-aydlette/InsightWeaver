"""
Adjudicate command - one structured model call per routed pair, every outcome recorded.

``adjudicate`` asks about every routed pair on a live watch that the current
prompt version has not answered, records each answer in ``adjudications`` and
each piece of evidence in ``evidence``, and prints the totals. Run again, it
asks nothing. ``--dry-run`` prints the exact text the first pairs would send
and a character-based token estimate, and never constructs a client, so it
needs no keychain entry.

A failed call is printed and left in the ledger; it is not retried and it does
not fail the command, because the brief's QUIET section is where a failure is
meant to be read. Exit is non-zero only when the command itself could not run.

Added 2026-09-22 for backlog task 029.
"""

import click

from ..config.credentials import MissingCredential
from ..database.connection import get_db
from ..evidence import resolve
from ..evidence.adjudicate import dry_run, run
from ..evidence.claude_adjudicator import PROMPT_VERSION, ClaudeAdjudicator
from ..llm.claude_client import ModelCallFailed
from .colors import accent, error, header, muted, warning


@click.command(name="adjudicate")
@click.option(
    "--dry-run",
    "dry_run_flag",
    is_flag=True,
    default=False,
    help="Print what would be sent; call nothing.",
)
@click.option("--limit", type=click.IntRange(min=1), default=None, help="At most this many pairs.")
def adjudicate_command(dry_run_flag: bool, limit: int | None) -> None:
    """Ask the model whether each routed observation is evidence for its watch."""
    if dry_run_flag:
        with get_db() as session:
            previews = dry_run(session, PROMPT_VERSION, limit=limit if limit is not None else 3)
        click.echo(header("ADJUDICATE --dry-run"))
        if not previews:
            click.echo(muted("No pending pairs: everything routed has been adjudicated."))
            return
        for pair, system, user, estimate in previews:
            click.echo(accent(f"--- {pair.view.content_hash} / {pair.watch.id}"))
            click.echo(muted("[system]"))
            click.echo(system)
            click.echo(muted("[user]"))
            click.echo(user)
            click.echo(muted(f"~{estimate} input tokens (character estimate, not a count)"))
            click.echo()
        click.echo(muted("Nothing was sent."))
        return

    adjudicator = resolve(PROMPT_VERSION)
    assert isinstance(adjudicator, ClaudeAdjudicator)
    try:
        with get_db() as session:
            result = run(session, adjudicator, limit=limit)
    except MissingCredential as exc:
        raise click.ClickException(str(exc))
    except ModelCallFailed as exc:
        # Only a misconfiguration reaches here; call failures are recorded per pair.
        raise click.ClickException(
            f"the API rejected the request, so the run stopped with nothing recorded for the "
            f"pair it hit and later pairs: {exc}"
        )

    click.echo(header("ADJUDICATE"))
    click.echo(f"prompt version: {result.prompt_version}")
    click.echo(
        f"asked {result.asked}: evidence {result.evidence}, none {result.none}, "
        f"failed {result.failed}"
    )
    click.echo(muted(f"tokens: {result.input_tokens} in, {result.output_tokens} out"))
    if result.asked == 0:
        click.echo(muted("No pending pairs: everything routed has been adjudicated."))
    for content_hash, watch_id, why in result.failures:
        click.echo(f"{error('FAILED')} {content_hash} / {watch_id}: {why}")
    if result.failed:
        click.echo(warning(f"{result.failed} failed adjudication(s) are recorded, not retried."))
