"""
The seam a prompt version plugs into, and the vocabulary it may return.

Adjudication is the one stochastic tier in this system. Everything either side
of it is deterministic and unit-testable; the tier itself can only be reviewed
by holding its inputs fixed and looking at what a different prompt does to its
outputs. This module is the shape of that seam. **It does not contain the
adjudication prompt** -- that is backlog task 016, and deliberately not here.

Three properties are enforced rather than documented:

1. **An adjudicator sees observations and watches, nothing else.** The argument
   is an :class:`ObservationView`, which carries a content hash and the stored
   payload -- not an ORM row, not a database session, not the clock. That is
   what makes "Evidence is a pure function of (Observations, prompt version)"
   checkable instead of aspirational.
2. **An adjudicator names its own prompt version**, and the replay harness
   writes that name onto every row it produces. A version that came from a
   command-line flag while the model came from somewhere else is how a
   mislabelled corpus happens.
3. **A verdict is validated on construction.** Direction is two-valued and
   magnitude is bounded; a bad one raises where it was built rather than at the
   CHECK constraint several layers later, though the CHECK constraint is there
   too.

**On the shipped adjudicator.** :class:`NullAdjudicator` returns no verdicts.
It exists so the harness is runnable and testable before task 016 supplies
something real, and it is honest: an adjudicator that guessed a direction from a
keyword match would put fabricated judgements in a table whose entire purpose is
to make judgements reviewable. Registering a real one is
:func:`register`; running an unregistered one for a one-off is
``--adjudicator module:attr`` on the CLI.

Added 2026-08-31 for backlog task 014.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "Adjudicator",
    "DIRECTIONS",
    "NULL_PROMPT_VERSION",
    "NullAdjudicator",
    "ObservationView",
    "UnknownPromptVersion",
    "Verdict",
    "known_prompt_versions",
    "load_adjudicator",
    "register",
    "resolve",
]

# Two values, no 'neutral'. See src/database/models.py::Evidence.
DIRECTIONS: tuple[str, ...] = ("supports", "contradicts")

NULL_PROMPT_VERSION = "null-v0"


@dataclass(frozen=True)
class ObservationView:
    """
    Everything an adjudicator is allowed to see about one observation.

    The payload is the stored payload, verbatim. Nothing derived, nothing
    fetched, no session.
    """

    content_hash: str
    payload: dict[str, Any]

    @property
    def title(self) -> str:
        return str(self.payload.get("title") or "")

    @property
    def text(self) -> str:
        return str(self.payload.get("normalized_content") or self.payload.get("description") or "")


@dataclass(frozen=True)
class Verdict:
    """One adjudicated link from the observation to a watch."""

    watch_id: str
    direction: str
    magnitude: float
    rationale: str = field(default="")

    def __post_init__(self) -> None:
        if self.direction not in DIRECTIONS:
            raise ValueError(
                f"verdict direction must be one of {DIRECTIONS}, got {self.direction!r}"
            )
        if not 0.0 <= self.magnitude <= 1.0:
            raise ValueError(f"verdict magnitude must be in [0, 1], got {self.magnitude}")
        if not str(self.watch_id).strip():
            raise ValueError("a verdict must name the watch it bears on")


@runtime_checkable
class Adjudicator(Protocol):
    """What a prompt version has to look like to be replayable."""

    prompt_version: str

    def adjudicate(self, observation: ObservationView, watches: Sequence[Any]) -> list[Verdict]:
        """
        The verdicts this observation supports, for the watches given.

        Must be a pure function of its arguments. Returning ``[]`` is normal and
        is the common case -- most observations bear on no watch.
        """
        ...


class NullAdjudicator:
    """
    The adjudicator that finds nothing. See the module docstring.

    Useful for more than bootstrapping: replaying it against a stored prompt
    version shows every row that version produced, as a removal, which is a
    quick way to see what a version is actually claiming.
    """

    prompt_version = NULL_PROMPT_VERSION

    def adjudicate(self, observation: ObservationView, watches: Sequence[Any]) -> list[Verdict]:  # noqa: ARG002
        return []


class UnknownPromptVersion(KeyError):
    """Raised when no adjudicator is registered for a requested prompt version."""

    def __init__(self, version: str, known: Sequence[str]) -> None:
        self.version = version
        self.known = list(known)
        super().__init__(
            f"no adjudicator is registered for prompt version {version!r} "
            f"(registered: {', '.join(self.known) or 'none'}). Register one with "
            f"src.evidence.adjudicator.register(), or pass "
            f"--adjudicator module:attr to name one directly."
        )

    def __str__(self) -> str:
        return self.args[0]


_REGISTRY: dict[str, Callable[[], Adjudicator]] = {
    NULL_PROMPT_VERSION: NullAdjudicator,
}


def register(version: str, factory: Callable[[], Adjudicator]) -> None:
    """
    Bind a prompt version to the adjudicator that implements it.

    Re-registering a version is refused. Two builds of "v3" that disagree would
    make every stored ``prompt_version`` ambiguous, which is the one thing the
    column exists to prevent.
    """
    if version in _REGISTRY:
        raise ValueError(
            f"prompt version {version!r} is already registered; a version identifies "
            f"one adjudicator, and rebinding it would make stored evidence ambiguous"
        )
    _REGISTRY[version] = factory


def known_prompt_versions() -> list[str]:
    """Every registered prompt version, sorted."""
    return sorted(_REGISTRY)


def resolve(version: str) -> Adjudicator:
    """The adjudicator for ``version``, or :class:`UnknownPromptVersion`."""
    factory = _REGISTRY.get(version)
    if factory is None:
        raise UnknownPromptVersion(version, known_prompt_versions())
    return factory()


def load_adjudicator(path: str) -> Adjudicator:
    """
    Import ``module:attr`` and call it, for an adjudicator not in the registry.

    The escape hatch for a prompt version under development and for the test
    suite's stubs. It is explicit on the command line rather than read from the
    environment, so that a replay whose adjudicator did not come from the
    registry says so in the shell history.
    """
    if ":" not in path:
        raise ValueError(f"adjudicator path must be 'module:attr', got {path!r}")
    module_name, _, attr = path.partition(":")
    module = importlib.import_module(module_name)
    try:
        factory = getattr(module, attr)
    except AttributeError:
        raise ValueError(f"{module_name} has no attribute {attr!r}")
    adjudicator = factory() if callable(factory) else factory
    if not isinstance(adjudicator, Adjudicator):
        raise TypeError(
            f"{path} did not produce an Adjudicator "
            f"(needs a 'prompt_version' attribute and an 'adjudicate' method)"
        )
    return adjudicator
