"""
The auth command: credentials in the OS keychain.

Moved from the removed `estate` script on 2026-09-22 (backlog task 027): one
console script.
"""

from __future__ import annotations

import click

from ..config import credentials


@click.group(name="auth")
def auth() -> None:
    """Credentials in the OS keychain. A stored value is never printed."""


@auth.command(name="set")
@click.argument("name", type=click.Choice(sorted(credentials.KNOWN)))
@click.option(
    "--value",
    prompt="Value",
    hide_input=True,
    help="The credential. Prompted for, hidden, if not given -- prefer the prompt, so the "
    "value stays out of your shell history.",
)
def set_credential(name: str, value: str) -> None:
    """Store a credential. Overwrites any existing value under NAME."""
    username = credentials.KNOWN[name]
    try:
        credentials.write(username, value)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"stored '{name}' as keychain entry '{username}'")


@auth.command(name="status")
def status() -> None:
    """Which known credentials are set. Values are not shown."""
    for name, username in sorted(credentials.KNOWN.items()):
        state = "set" if credentials.is_set(username) else "not set"
        click.echo(f"{name:<12} {state:<8} ({username})")


@auth.command(name="clear")
@click.argument("name", type=click.Choice(sorted(credentials.KNOWN)))
def clear_credential(name: str) -> None:
    """Remove a credential from the keychain."""
    try:
        credentials.delete(credentials.KNOWN[name])
    except credentials.MissingCredential as exc:
        raise click.ClickException(str(exc))
    click.echo(f"removed '{name}'")
