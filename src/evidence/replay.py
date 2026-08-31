"""
Rebuilding Evidence from Observations, and diffing it against what is stored.

This is the mechanism the whole task exists for. Observations are immutable and
content-addressed; Evidence is a pure function of (Observations, prompt
version). Given both, "what did this prompt change do" stops being a matter of
opinion and becomes a diff.

**Reading order matters and is fixed.** Observations are read in content-hash
order, watches in id order, and the output is sorted by ``(observation, watch)``.
A replay whose output order depended on a query plan would produce a different
byte stream on a database with different statistics, and the reproducibility
claim would be false in a way nobody would notice.

**What is compared against what.** ``--prompt-version X`` computes X's output.
The baseline defaults to the stored rows *for X*, which makes a plain replay a
reproducibility check: a deterministic adjudicator must produce an empty diff.
``--against Y`` compares X's output to Y's stored rows instead, which is the
"what did my prompt change do" view.

**Committing is separate from diffing, and narrower.** :func:`commit` writes
only for the target prompt version, and it refuses outright if the target
version already has a row for a key with a different verdict -- that means the
same version produced two different answers, and quietly overwriting the first
one would erase the evidence of the very problem the harness exists to surface.

Added 2026-08-31 for backlog task 014.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..database.models import Evidence, Observation, Watch
from .adjudicator import Adjudicator, ObservationView

logger = logging.getLogger(__name__)

__all__ = [
    "EvidenceRow",
    "NondeterministicReplay",
    "ReplayDiff",
    "commit",
    "diff",
    "format_diff",
    "rebuild",
    "stored_evidence",
]


@dataclass(frozen=True, order=True)
class EvidenceRow:
    """One evidence verdict, without its surrogate id or its clock."""

    observation_hash: str
    watch_id: str
    direction: str
    magnitude: float
    rationale: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return (self.observation_hash, self.watch_id)

    def describe(self) -> str:
        suffix = f"  {self.rationale}" if self.rationale else ""
        return f"{self.direction} {self.magnitude:.3f}{suffix}"


class NondeterministicReplay(RuntimeError):
    """
    Raised when a prompt version produces a verdict differing from its own
    stored row.

    This is the failure the harness is built to catch, so it is loud and it
    stops the commit. See :func:`commit`.
    """


@dataclass
class ReplayDiff:
    """What changed between a replay's output and a stored baseline."""

    added: list[EvidenceRow] = field(default_factory=list)
    removed: list[EvidenceRow] = field(default_factory=list)
    changed: list[tuple[EvidenceRow, EvidenceRow]] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (self.added or self.removed or self.changed)

    @property
    def counts(self) -> dict[str, int]:
        return {
            "added": len(self.added),
            "removed": len(self.removed),
            "changed": len(self.changed),
        }


def rebuild(
    db: Session,
    adjudicator: Adjudicator,
    limit: int | None = None,
) -> list[EvidenceRow]:
    """
    Run ``adjudicator`` over the stored observations and return what it produced.

    Reads observations and watches. Writes nothing, ever -- committing is
    :func:`commit`, and keeping them separate is what makes a diff safe to run
    against a corpus you care about.
    """
    watches = db.query(Watch).order_by(Watch.id).all()
    query = db.query(Observation.content_hash, Observation.payload).order_by(
        Observation.content_hash
    )
    if limit is not None:
        query = query.limit(limit)

    rows: list[EvidenceRow] = []
    for content_hash, payload in query.all():
        view = ObservationView(content_hash=content_hash, payload=dict(payload or {}))
        for verdict in adjudicator.adjudicate(view, watches):
            rows.append(
                EvidenceRow(
                    observation_hash=content_hash,
                    watch_id=verdict.watch_id,
                    direction=verdict.direction,
                    magnitude=verdict.magnitude,
                    rationale=verdict.rationale,
                )
            )
    return sorted(rows)


def stored_evidence(db: Session, prompt_version: str) -> list[EvidenceRow]:
    """The evidence already stored for one prompt version, in the same order."""
    rows = (
        db.query(
            Evidence.observation_hash,
            Evidence.watch_id,
            Evidence.direction,
            Evidence.magnitude,
            Evidence.rationale,
        )
        .filter(Evidence.prompt_version == prompt_version)
        .all()
    )
    return sorted(EvidenceRow(row[0], row[1], row[2], float(row[3]), row[4] or "") for row in rows)


def diff(replayed: Sequence[EvidenceRow], baseline: Sequence[EvidenceRow]) -> ReplayDiff:
    """
    What ``replayed`` says that ``baseline`` does not, keyed by (observation, watch).

    A key present in both with a different verdict is ``changed`` rather than an
    add and a remove, because the interesting question about a prompt change is
    which judgements it revised, not how many rows moved.
    """
    left = {row.key: row for row in replayed}
    right = {row.key: row for row in baseline}

    result = ReplayDiff()
    for key in sorted(left.keys() | right.keys()):
        new, old = left.get(key), right.get(key)
        if old is None and new is not None:
            result.added.append(new)
        elif new is None and old is not None:
            result.removed.append(old)
        elif new != old and new is not None and old is not None:
            result.changed.append((old, new))
    return result


def commit(
    db: Session,
    prompt_version: str,
    replayed: Sequence[EvidenceRow],
) -> dict[str, int]:
    """
    Make the stored evidence for ``prompt_version`` equal ``replayed``.

    Inserts what is missing and deletes what the replay did not produce, both
    scoped to this one prompt version -- no other version's rows are read or
    touched. Evidence is derived, so deleting a derived row that the current
    definition no longer produces is correct; observations are not derived, and
    nothing here can touch one.

    Refuses, before writing anything, if a key exists for this version with a
    different verdict. See :class:`NondeterministicReplay`.
    """
    current = stored_evidence(db, prompt_version)
    against_self = diff(replayed, current)

    if against_self.changed:
        detail = "\n".join(
            f"  {old.observation_hash} / {old.watch_id}: "
            f"stored [{old.describe()}] -> replayed [{new.describe()}]"
            for old, new in against_self.changed[:10]
        )
        raise NondeterministicReplay(
            f"prompt version {prompt_version!r} produced {len(against_self.changed)} "
            f"verdict(s) that differ from its own stored rows. Evidence is supposed to "
            f"be a pure function of (observations, prompt version), so this means either "
            f"the adjudicator is not deterministic or the version label is being reused "
            f"for two different adjudicators. Nothing was written.\n{detail}"
        )

    for row in against_self.added:
        db.add(
            Evidence(
                observation_hash=row.observation_hash,
                watch_id=row.watch_id,
                direction=row.direction,
                magnitude=row.magnitude,
                prompt_version=prompt_version,
                rationale=row.rationale or None,
            )
        )

    deleted = 0
    for row in against_self.removed:
        deleted += (
            db.query(Evidence)
            .filter(
                Evidence.prompt_version == prompt_version,
                Evidence.observation_hash == row.observation_hash,
                Evidence.watch_id == row.watch_id,
            )
            .delete(synchronize_session=False)
        )
    db.flush()

    written = {"inserted": len(against_self.added), "deleted": deleted}
    logger.info(
        f"replay --commit {prompt_version}: inserted {written['inserted']}, "
        f"deleted {written['deleted']}"
    )
    return written


def format_diff(
    result: ReplayDiff,
    prompt_version: str,
    baseline_version: str,
    observations: int,
    watches: int,
) -> str:
    """
    The diff as text, deterministic to the byte.

    No timestamps, no row ids, no counts of anything that varies between two
    runs over the same corpus -- a report that changed between identical runs
    could not be used to prove that the runs were identical.
    """
    lines = [
        f"replay: prompt-version={prompt_version} against={baseline_version}",
        f"corpus: {observations} observation(s), {watches} watch(es)",
        (
            f"diff: {result.counts['added']} added, "
            f"{result.counts['removed']} removed, "
            f"{result.counts['changed']} changed"
        ),
    ]
    if result.is_empty:
        lines.append("")
        lines.append("No difference from the stored evidence.")
        return "\n".join(lines)

    for row in result.added:
        lines.append(f"+ {row.observation_hash} / {row.watch_id}: {row.describe()}")
    for row in result.removed:
        lines.append(f"- {row.observation_hash} / {row.watch_id}: {row.describe()}")
    for old, new in result.changed:
        lines.append(f"~ {old.observation_hash} / {old.watch_id}:")
        lines.append(f"    was [{old.describe()}]")
        lines.append(f"    now [{new.describe()}]")
    return "\n".join(lines)
