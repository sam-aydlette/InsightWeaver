"""
BriefDocument -- the single structured model every brief renderer consumes.

The pipeline already produces exactly this content as ``synthesis_data`` and
already stores it in ``narrative_syntheses.synthesis_data``. This module does
not reshape or reinterpret that content; it names it, so that a renderer can
take a document rather than an untyped nest of dicts, and so that a stored run
can be replayed without touching the pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class StoredBriefNotFound(LookupError):
    """Raised when ``--from-run`` names a synthesis id that is not stored."""

    def __init__(self, synthesis_id: int, available: list[int]) -> None:
        self.synthesis_id = synthesis_id
        self.available = available
        detail = ", ".join(str(i) for i in available) if available else "none"
        super().__init__(
            f"No stored brief with id {synthesis_id}. Most recent stored ids: {detail}"
        )


@dataclass(frozen=True)
class BriefDocument:
    """
    A rendered-brief-shaped view of one synthesis.

    ``situations``, ``thin_coverage``, ``meta_fractures`` and ``metadata`` are
    the synthesis payload verbatim. The remaining fields are provenance: which
    stored row this came from, and how many articles the run analyzed.
    """

    situations: list[dict[str, Any]] = field(default_factory=list)
    thin_coverage: list[dict[str, Any]] = field(default_factory=list)
    meta_fractures: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    articles_analyzed: int = 0
    synthesis_id: int | None = None
    analysis_run_id: int | None = None
    generated_at: str | None = None

    # -- construction ----------------------------------------------------

    @classmethod
    def from_synthesis_data(
        cls,
        synthesis_data: dict[str, Any] | None,
        *,
        articles_analyzed: int | None = None,
        synthesis_id: int | None = None,
        analysis_run_id: int | None = None,
        generated_at: str | None = None,
    ) -> BriefDocument:
        """Build a document from a raw ``synthesis_data`` payload."""
        data = synthesis_data or {}
        metadata = _as_dict(data.get("metadata"))
        if articles_analyzed is None:
            articles_analyzed = _as_int(metadata.get("articles_analyzed"))
        if generated_at is None:
            raw = metadata.get("generated_at")
            generated_at = raw if isinstance(raw, str) else None
        return cls(
            situations=_as_dict_list(data.get("situations")),
            thin_coverage=_as_dict_list(data.get("thin_coverage")),
            meta_fractures=_as_dict_list(data.get("meta_fractures")),
            metadata=metadata,
            articles_analyzed=articles_analyzed,
            synthesis_id=synthesis_id,
            analysis_run_id=analysis_run_id,
            generated_at=generated_at,
        )

    @classmethod
    def from_report(cls, report_data: dict[str, Any] | None) -> BriefDocument:
        """
        Build a document from the legacy pipeline ``report_result`` shape:
        ``{"synthesis_data": ..., "articles_analyzed": ..., "synthesis_id": ...}``.
        """
        report = report_data or {}
        raw_articles = report.get("articles_analyzed")
        return cls.from_synthesis_data(
            _as_dict(report.get("synthesis_data")),
            articles_analyzed=_as_int(raw_articles) if raw_articles is not None else None,
            synthesis_id=_as_optional_int(report.get("synthesis_id")),
        )

    def to_report(self) -> dict[str, Any]:
        """Round-trip back to the legacy ``report_result`` shape."""
        return {
            "success": True,
            "articles_analyzed": self.articles_analyzed,
            "synthesis_data": self.synthesis_data,
            "synthesis_id": self.synthesis_id,
        }

    # -- payload ---------------------------------------------------------

    @property
    def synthesis_data(self) -> dict[str, Any]:
        """The synthesis payload, in the shape the pipeline stores."""
        return {
            "situations": self.situations,
            "thin_coverage": self.thin_coverage,
            "meta_fractures": self.meta_fractures,
            "metadata": self.metadata,
        }

    def is_empty(self) -> bool:
        """True when no section carries anything worth rendering."""
        return not (self.situations or self.thin_coverage or self.meta_fractures)

    # -- named views over metadata --------------------------------------

    @property
    def decisions(self) -> list[dict[str, Any]]:
        """Decision-routing summary: what today's coverage moved."""
        return _as_dict_list(self.metadata.get("decision_routing"))

    @property
    def prediction_check(self) -> dict[str, Any]:
        """Pre-synthesis grading of open observables."""
        return _as_dict(self.metadata.get("prediction_check"))

    @property
    def clusters_analyzed(self) -> int:
        return _as_int(self.metadata.get("clusters_analyzed"))

    @property
    def clusters_thin(self) -> int:
        return _as_int(self.metadata.get("clusters_thin"))

    @property
    def clusters_total(self) -> int:
        return _as_int(self.metadata.get("clusters_total"))

    @property
    def analysis_threshold(self) -> str:
        threshold = self.metadata.get("analysis_threshold")
        return threshold if isinstance(threshold, str) else "3+ articles"

    @property
    def date_stamp(self) -> str:
        """
        Date this brief was generated, ``YYYY-MM-DD``, or empty when unknown.

        Taken from stored provenance, never from the clock -- rendering the same
        stored run tomorrow must produce the same bytes.
        """
        raw = self.generated_at or self.metadata.get("generated_at")
        if not isinstance(raw, str) or not raw.strip():
            return ""
        return raw.split("T", 1)[0].split(" ", 1)[0]

    @property
    def metadata_articles_analyzed(self) -> int:
        """Article count as the synthesis itself recorded it."""
        return _as_int(self.metadata.get("articles_analyzed"))

    @property
    def questions(self) -> list[dict[str, Any]]:
        """
        Every unresolved question raised across situations, in situation order,
        primary before secondary. Each entry carries ``situation_index`` (1-based)
        and ``role`` ("primary" or "secondary") alongside the question payload.
        """
        collected: list[dict[str, Any]] = []
        for index, situation in enumerate(self.situations, 1):
            futures = _as_dict(situation.get("where_this_goes"))
            unresolved = futures.get("unresolved_questions")
            if not isinstance(unresolved, dict):
                legacy = futures.get("unresolved_question")
                if isinstance(legacy, str) and legacy.strip():
                    collected.append({"situation_index": index, "role": "primary", "text": legacy})
                continue
            primary = _question_entry(unresolved.get("primary"))
            if primary:
                collected.append({"situation_index": index, "role": "primary", **primary})
            for raw in unresolved.get("secondary") or []:
                secondary = _question_entry(raw)
                if secondary:
                    collected.append({"situation_index": index, "role": "secondary", **secondary})
        return collected


def _question_entry(raw: Any) -> dict[str, Any] | None:
    """Normalize one question to a dict, or None when it carries no text."""
    if isinstance(raw, str):
        return {"text": raw} if raw.strip() else None
    if isinstance(raw, dict):
        text = raw.get("text")
        return dict(raw) if isinstance(text, str) and text.strip() else None
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _as_optional_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def load_stored_brief(synthesis_id: int) -> BriefDocument:
    """
    Load a stored brief by ``narrative_syntheses.id``.

    Read-only and offline: no pipeline stage runs, no feed is fetched and no
    Claude call is made. Raises :class:`StoredBriefNotFound` if the id is not
    stored, listing recent ids so the caller can correct it.
    """
    from sqlalchemy.orm import Session

    from ..database.connection import get_db
    from ..database.models import NarrativeSynthesis

    db: Session
    with get_db() as db:
        # Annotated because src.database.models is excluded from type checking,
        # so the ORM class arrives here as Any.
        row: Any = (
            db.query(NarrativeSynthesis).filter(NarrativeSynthesis.id == synthesis_id).first()
        )
        if row is None:
            # Bound to list[Any] rather than unpacked in the comprehension: the
            # column arrives untyped for the same reason `row` does, so mypy
            # infers the rows of a single-column query as Never and rejects the
            # tuple unpack. Indexing an Any row keeps the runtime identical.
            recent: list[Any] = (
                db.query(NarrativeSynthesis.id)
                .order_by(NarrativeSynthesis.id.desc())
                .limit(10)
                .all()
            )
            raise StoredBriefNotFound(synthesis_id, [int(entry[0]) for entry in recent])

        generated_at = row.generated_at.isoformat() if row.generated_at else None
        return BriefDocument.from_synthesis_data(
            _as_dict(row.synthesis_data),
            articles_analyzed=_as_int(row.articles_analyzed),
            synthesis_id=row.id,
            analysis_run_id=row.analysis_run_id,
            generated_at=generated_at,
        )
