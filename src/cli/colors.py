"""
Terminal color palette - hacker aesthetic

The palette itself now lives in :mod:`src.utils.colors`. It moved out of the
CLI package because ``src/render`` needs it too, and a renderer importing
``src.cli`` inverts the layering: importing ``src.render`` would pull in
``src/cli/__init__.py`` -> ``app`` -> ``brief`` -> back into ``src.render``
mid-initialization. Renderers are below the CLI, so the palette is below both.

This module stays as the import site every existing CLI command already uses.
"""

from ..utils.colors import (
    ACCENT,
    EMPHASIS,
    ERROR,
    HEADER,
    MUTED,
    SUCCESS,
    WARNING,
    accent,
    colorize_confidence,
    colorize_priority,
    emphasis,
    error,
    header,
    muted,
    success,
    warning,
)

__all__ = [
    "ACCENT",
    "EMPHASIS",
    "ERROR",
    "HEADER",
    "MUTED",
    "SUCCESS",
    "WARNING",
    "accent",
    "colorize_confidence",
    "colorize_priority",
    "emphasis",
    "error",
    "header",
    "muted",
    "success",
    "warning",
]
