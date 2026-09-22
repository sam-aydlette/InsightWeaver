"""
Credentials live in the OS keychain, and nowhere else.

Read through ``keyring``, under one service name (``settings.keyring_service``)
and one username per credential. Nothing here reads an environment variable or
a file, and nothing here falls back to one: a credential that is not in the
keychain raises :class:`MissingCredential` at the point it is needed, with the
command that sets it in the message. ``ANTHROPIC_API_KEY`` in ``.env`` was the
previous home and was removed on 2026-09-22 (backlog task 026) rather than kept
as a fallback, because a fallback is a second place a secret can live and the
whole point of a keychain is that there is one.

Every credential this system will ever hold is read-only by construction: an
API key that can only submit prompts, an OAuth refresh token minted against
read-only scopes, a finance aggregator access URL for a protocol with no write
operations. Adding a credential here that could move money, send mail or write
to an external service is a change to that property and needs its own task.

Lookups are lazy. Importing this module touches no keychain; only
:func:`read` does, and the first thing that calls it is the constructor of a
model client. The test suite therefore never needs a keychain, and CI -- which
has none -- runs the same tests as a laptop by installing an in-memory backend.
"""

from __future__ import annotations

import keyring
from keyring.errors import PasswordDeleteError

from src.config.settings import settings

__all__ = [
    "ANTHROPIC",
    "KNOWN",
    "MissingCredential",
    "delete",
    "is_set",
    "read",
    "write",
]

# The username under which each credential is stored. The short name on the
# left is what the operator types (``estate auth set anthropic``); the value on
# the right is the keychain entry, and it never changes once something is
# stored under it.
ANTHROPIC = "anthropic_api_key"
KNOWN: dict[str, str] = {"anthropic": ANTHROPIC}


class MissingCredential(RuntimeError):
    """A credential this operation needs is not in the keychain."""

    def __init__(self, username: str) -> None:
        self.username = username
        short = next((k for k, v in KNOWN.items() if v == username), username)
        super().__init__(
            f"no credential '{username}' in the keychain under service "
            f"'{settings.keyring_service}'. Set it once with: estate auth set {short}"
        )


def read(username: str) -> str:
    """The stored value, or :class:`MissingCredential`. Never an empty string."""
    value = keyring.get_password(settings.keyring_service, username)
    if not value:
        raise MissingCredential(username)
    return value


def write(username: str, value: str) -> None:
    """Store ``value``. A blank value is refused, not stored as an empty secret."""
    if not value or not value.strip():
        raise ValueError(f"refusing to store a blank value for '{username}'")
    keyring.set_password(settings.keyring_service, username, value.strip())


def delete(username: str) -> None:
    """Remove the entry. Removing one that is absent is an error, not a no-op."""
    try:
        keyring.delete_password(settings.keyring_service, username)
    except PasswordDeleteError:
        raise MissingCredential(username)


def is_set(username: str) -> bool:
    """Whether a non-empty value is stored. Never returns the value."""
    return bool(keyring.get_password(settings.keyring_service, username))
