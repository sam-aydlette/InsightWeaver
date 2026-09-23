"""
The brief: what moved, what is due, what is watched, what went quiet.

Two modules. :mod:`select` reads the database and the Position into plain
data, pure in ``(db, as_of, since, position)``; :mod:`render` turns that data
into text and adds nothing. No model call happens on this path, and nothing
here reads a clock: ``as_of`` is an argument, so the same inputs give the
same bytes, which a test asserts by rendering twice.

Added 2026-09-22 for backlog task 031.
"""

from .render import render
from .select import HORIZON_DAYS, REVIEW_BANNER_DAYS, Brief, select_brief

__all__ = ["HORIZON_DAYS", "REVIEW_BANNER_DAYS", "Brief", "render", "select_brief"]
