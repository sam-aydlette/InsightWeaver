"""
Terminal color palette - hacker aesthetic

One palette module. It used to be split across this file and
``src/utils/colors.py`` because ``src/render`` needed the palette too, and a
renderer importing ``src.cli`` would have inverted the layering. ``src/render``
was deleted 2026-08-31 (backlog task 012), so the split had no reason left and
was merged back here 2026-09-22 (backlog task 027). ``success``, ``emphasis``,
``colorize_priority`` and ``colorize_confidence`` were dropped in the same
merge: no caller anywhere in ``src/`` used them.
"""

import click

# Color constants
ACCENT = "bright_green"
HEADER = "cyan"
WARNING = "yellow"
ERROR = "red"
MUTED = "bright_black"


def header(text: str) -> str:
    """Style section header (cyan, bold)"""
    return click.style(text, fg=HEADER, bold=True)


def accent(text: str) -> str:
    """Style primary accent text (bright green)"""
    return click.style(text, fg=ACCENT)


def warning(text: str) -> str:
    """Style warning message (yellow)"""
    return click.style(text, fg=WARNING)


def error(text: str) -> str:
    """Style error message (red)"""
    return click.style(text, fg=ERROR)


def muted(text: str) -> str:
    """Style secondary/muted text (gray)"""
    return click.style(text, fg=MUTED)


__all__ = [
    "ACCENT",
    "ERROR",
    "HEADER",
    "MUTED",
    "WARNING",
    "accent",
    "error",
    "header",
    "muted",
    "warning",
]
