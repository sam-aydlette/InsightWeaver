"""
Brief rendering.

One document model (:class:`BriefDocument`) and one renderer per output
medium. Nothing in this package fetches, synthesizes, or calls Claude -- a
``BriefDocument`` is either handed over by the pipeline or loaded from a
stored ``narrative_syntheses`` row, and rendering it is pure.
"""

from .document import BriefDocument, StoredBriefNotFound, load_stored_brief
from .email import EmailDeliveryError, EmailRenderer
from .html import HTMLRenderer
from .markdown import MarkdownRenderer
from .terminal import TerminalRenderer, clean_citations

__all__ = [
    "BriefDocument",
    "EmailDeliveryError",
    "EmailRenderer",
    "HTMLRenderer",
    "MarkdownRenderer",
    "StoredBriefNotFound",
    "TerminalRenderer",
    "clean_citations",
    "load_stored_brief",
]
