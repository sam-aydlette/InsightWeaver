"""
Brief Report Terminal Formatter -- compatibility surface.

The formatting itself moved to :mod:`src.render`: one document model
(:class:`~src.render.document.BriefDocument`) and one renderer per medium.
Nothing here formats anything; it adapts the legacy ``report_data`` dict shape
onto a ``BriefDocument`` and delegates, so there is exactly one place that
decides what a brief looks like.
"""

from typing import Any

from ..render._text import clean_citations
from ..render.document import BriefDocument
from ..render.markdown import MarkdownRenderer
from ..render.terminal import TerminalRenderer

__all__ = [
    "BriefFormatter",
    "clean_citations",
]


class BriefFormatter:
    """Legacy adapter: takes the pipeline's ``report_data`` dict, delegates."""

    def __init__(self, max_width: int = 80):
        self.max_width = max_width
        self._terminal = TerminalRenderer(max_width)
        self._markdown = MarkdownRenderer()

    def format_report(self, report_data: dict[str, Any]) -> str:
        return self._terminal.render(BriefDocument.from_report(report_data))

    def format_one_line_summary(self, report_data: dict[str, Any]) -> str:
        return self._terminal.render_one_line_summary(BriefDocument.from_report(report_data))

    def format_markdown(self, report_data: dict[str, Any]) -> str:
        return self._markdown.render(BriefDocument.from_report(report_data))
