"""
The documentation names only things that exist.

A public repository's README is read more often than its code, and a command,
option, make target or path that the docs name and the tree lacks is a lie
the reader finds first. Every `insightweaver ...` invocation, every `make ...`
target and every backticked repository path in the documents below is checked
against the click group, the Makefile and the file system.

Added 2026-09-23 for backlog tasks 032 and 033.
"""

from __future__ import annotations

import re
from pathlib import Path

import click
import pytest

from src.cli.app import cli

ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS = [
    "README.md",
    "GETTING_STARTED.md",
    "CONTRIBUTING.md",
    "docs/CONCEPTS.md",
    "docs/PLAN.md",
    "SOURCES.md",
    *sorted(str(p.relative_to(ROOT)) for p in (ROOT / ".claude" / "skills").glob("*/SKILL.md")),
]

# `insightweaver` followed by words and options up to the end of the line or a
# closing backtick, pipe or quote. The text between is parsed as a command.
_INVOCATION = re.compile(
    r"insightweaver\s+([a-z][a-z0-9 ._/-]*(?:\s+--?[a-z][a-z0-9-]*(?:[ =][^\s`|\"')]+)?)*)"
)
# `make x` in a code span or a code block; "make the" in prose is not a target.
_MAKE = re.compile(r"(?:`|^\s*)make\s+([a-z][a-z0-9-]*)", re.MULTILINE)
# Paths in the tree. `data/` is runtime output and is gitignored, so it is not checked.
_PATH = re.compile(
    r"`((?:(?:src|tests|config|docs|backlog|\.claude|\.github)/[^`\s]+)"
    r"|(?:Makefile|pyproject\.toml|[A-Z_]+\.md|requirements[a-z-]*\.txt|\.env\.example|\.pre-commit-config\.yaml))`"
)
# docs/PLAN.md lists what task 027 deleted, by path, on purpose.
_PATHS_CHECKED = [d for d in DOCUMENTS if d != "docs/PLAN.md"]
_OPTION = re.compile(r"^--?[a-z]")


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _resolve(tokens: list[str]) -> tuple[click.Command, list[str]]:
    """Walk the group tree; return the command reached and the leftover tokens."""
    command: click.Command = cli
    while tokens and isinstance(command, click.Group):
        sub = command.commands.get(tokens[0])
        if sub is None:
            break
        command = sub
        tokens = tokens[1:]
    return command, tokens


def _options(command: click.Command) -> set[str]:
    names = {opt for param in command.params for opt in param.opts}
    names |= {opt for param in cli.params for opt in param.opts}  # group options such as --debug
    return names | {"--help"}


def _invocations(text: str) -> list[tuple[str, list[str]]]:
    found = []
    for match in _INVOCATION.finditer(text):
        tokens = match.group(1).split()
        if tokens[0] in ("is", "now", "exposes", "run,", "on"):  # prose, not a command
            continue
        found.append((match.group(0), tokens))
    return found


@pytest.mark.parametrize("document", DOCUMENTS)
def test_every_named_command_and_option_exists(document):
    problems = []
    for literal, tokens in _invocations(_read(document)):
        command, rest = _resolve(tokens)
        if command is cli:
            problems.append(f"{literal!r}: {tokens[0]!r} is not a command")
            continue
        if isinstance(command, click.Group) and rest and not _OPTION.match(rest[0]):
            problems.append(f"{literal!r}: {rest[0]!r} is not a subcommand of {command.name}")
            continue
        for token in rest:
            if _OPTION.match(token) and token.split("=")[0] not in _options(command):
                problems.append(f"{literal!r}: {command.name} has no option {token}")
    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize("document", DOCUMENTS)
def test_every_named_make_target_exists(document):
    targets = set(re.findall(r"^([a-z][a-z0-9-]*):", _read("Makefile"), re.MULTILINE))
    named = set(_MAKE.findall(_read(document)))
    assert named <= targets, f"{document} names make targets that do not exist: {named - targets}"


@pytest.mark.parametrize("document", _PATHS_CHECKED)
def test_every_named_repository_path_exists(document):
    missing = []
    for path in _PATH.findall(_read(document)):
        if any(ch in path for ch in "*<>{}") or path.endswith("/..."):
            continue
        candidate = ROOT / path.split("::")[0].rstrip("/")
        if not candidate.exists():
            missing.append(path)
    assert missing == [], f"{document} names paths that do not exist: {missing}"


def test_the_onboarding_skill_transcribes_and_syncs():
    """Invariant 6 at the seam where it is easiest to break (backlog task 032)."""
    text = _read(".claude/skills/onboard/SKILL.md")
    assert text.startswith("---\nname: onboard\n")
    assert "insightweaver watch sync" in text
    assert "watch add" not in text.replace("`watch add`", "")  # named only as what does not exist
    assert "never fill a field yourself" in text


def _table_rows() -> list[str]:
    readme = _read("README.md")
    table = readme[readme.index("## Commands") : readme.index("## Sources")]
    return [line.split("`")[1] for line in table.splitlines() if line.startswith("| `")]


def test_the_commands_table_in_the_readme_matches_the_cli():
    """Every command the group registers is in the README's commands table, and no other."""
    assert {row.split()[0] for row in _table_rows()} == set(cli.commands)


def test_every_option_in_the_commands_table_exists():
    """`brief [--since] [--as-of]` style rows: each bracketed option belongs to that command."""
    problems = []
    for row in _table_rows():
        tokens = row.replace("[", " ").replace("]", " ").replace("/", " ").split()
        command, rest = _resolve(tokens)
        for token in rest:
            if _OPTION.match(token) and token not in _options(command):
                problems.append(f"{row!r}: {command.name} has no option {token}")
    assert problems == [], "\n".join(problems)
