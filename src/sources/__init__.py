"""
Source adapters: ingestion generalized beyond RSS.

Added 2026-08-26 for backlog task 005. The seam is deliberately narrow --
an adapter turns *some upstream* into :class:`~src.sources.base.RawItem`
values that carry exactly the field set ``RSSFetcher.normalize_article()``
already produces. Everything downstream of the ``articles`` table
(deduplication, filtering, clustering, frames, questions, predictions,
synthesis) is untouched and has no idea an adapter exists.

Amended 2026-08-31 (backlog task 014): the same store path now also writes an
immutable, content-addressed :class:`~src.database.models.Observation` for every
item, through :mod:`src.sources.observation` and nowhere else. ``minhash``
carries the near-duplicate signature written beside it.

See ``SOURCES.md`` at the repository root for the recorded basis of use for
each configured source.
"""

from .base import ARTICLE_FIELDS, RawItem, SourceAdapter, SourceUnavailable, content_hash
from .federal_register import FederalRegisterAdapter, FederalRegisterFilter, FederalRegisterQuery
from .minhash import group_near_duplicates, signature, similarity
from .observation import (
    OBSERVATION_FIELDS,
    ObservationRecord,
    near_duplicate_groups,
    observation_hash,
    observe,
    store_observation,
)
from .rss_adapter import RSSAdapter
from .runner import IngestResult, build_configured_adapters, run_adapter, run_configured_adapters
from .store import ensure_source, store_items

__all__ = [
    "ARTICLE_FIELDS",
    "OBSERVATION_FIELDS",
    "FederalRegisterAdapter",
    "FederalRegisterFilter",
    "FederalRegisterQuery",
    "IngestResult",
    "ObservationRecord",
    "RSSAdapter",
    "RawItem",
    "SourceAdapter",
    "SourceUnavailable",
    "build_configured_adapters",
    "content_hash",
    "ensure_source",
    "group_near_duplicates",
    "near_duplicate_groups",
    "observation_hash",
    "observe",
    "run_adapter",
    "run_configured_adapters",
    "signature",
    "similarity",
    "store_items",
    "store_observation",
]
