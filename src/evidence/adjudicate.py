"""
The adjudication run: every routed pair without an answer, one call each.

Reads ``routes`` joined to ``observations`` and the watches, minus the pairs
this prompt version has already answered -- a row in ``adjudications``, or an
``evidence`` row committed by ``replay`` for the same version. Writes one
``adjudications`` row per pair asked, whatever the answer, and an ``evidence``
row when the answer was evidence. Run twice, the second run asks nothing.

**Which pairs.** Every routed pair. Expiry is Tier 1's gate: ``route`` links
only watches live on the day it runs, so a routed pair is one that was live
when it was routed, and adjudication and replay both read exactly that set
with no date-dependent filter of their own (decided 2026-09-22 after review;
the two tiers had briefly disagreed). Retirement and resolution join the gate
in backlog task 030.

**Progress survives interruption.** Each pair's ledger row is committed as
soon as it is written, so a run interrupted at pair forty keeps thirty-nine
answers and the tokens they cost. The pair in flight at the interruption has
no row: its call may already have been billed, the audit log has the request,
and it will be asked again next run. That single re-ask is the one place the
never-retried rule bends, and it bends only under Ctrl-C.

Added 2026-09-22 for backlog task 029.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from ..database.models import Adjudication, Evidence, Observation, Route, Watch
from .adjudicator import ObservationView
from .claude_adjudicator import ClaudeAdjudicator
from .prompt import build_messages, estimate_tokens

__all__ = ["AdjudicationRun", "Pair", "dry_run", "pending_pairs", "run"]


@dataclass(frozen=True)
class Pair:
    view: ObservationView
    watch: Watch


@dataclass
class AdjudicationRun:
    prompt_version: str
    asked: int = 0
    evidence: int = 0
    none: int = 0
    failed: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    failures: list[tuple[str, str, str]] = field(default_factory=list)  # (hash, watch, error)


def _answered(db: Session, prompt_version: str) -> set[tuple[str, str]]:
    """Pairs this version has already answered, by ledger row or by committed evidence."""
    ledger = db.query(Adjudication.observation_hash, Adjudication.watch_id).filter(
        Adjudication.prompt_version == prompt_version
    )
    committed = db.query(Evidence.observation_hash, Evidence.watch_id).filter(
        Evidence.prompt_version == prompt_version
    )
    return {(str(h), str(w)) for h, w in ledger.all()} | {
        (str(h), str(w)) for h, w in committed.all()
    }


def pending_pairs(db: Session, prompt_version: str, *, limit: int | None = None) -> list[Pair]:
    """Routed pairs with no answer under this version, in a fixed order."""
    if limit is not None and limit < 1:
        raise ValueError(f"limit must be at least 1, got {limit}")
    done = _answered(db, prompt_version)
    watches = {str(w.id): w for w in db.query(Watch).all()}
    rows = (
        db.query(Route.observation_hash, Route.watch_id, Observation.payload)
        .join(Observation, Observation.content_hash == Route.observation_hash)
        .order_by(Route.observation_hash, Route.watch_id)
        .all()
    )
    pairs = []
    for content_hash, watch_id, payload in rows:
        if (str(content_hash), str(watch_id)) in done:
            continue
        view = ObservationView(content_hash=str(content_hash), payload=dict(payload))
        pairs.append(Pair(view=view, watch=watches[str(watch_id)]))
        if limit is not None and len(pairs) >= limit:
            break
    return pairs


def run(
    db: Session, adjudicator: ClaudeAdjudicator, *, limit: int | None = None
) -> AdjudicationRun:
    """
    Ask the model about every pending pair and record every outcome.

    The client is built before the first pair, so a missing key raises here
    with nothing written. Each pair is committed as it is answered.
    """
    adjudicator.client()
    result = AdjudicationRun(prompt_version=adjudicator.prompt_version)
    for pair in pending_pairs(db, adjudicator.prompt_version, limit=limit):
        judgement = adjudicator.judge(pair.view, pair.watch)
        verdict = judgement.verdict
        result.asked += 1
        result.input_tokens += judgement.input_tokens
        result.output_tokens += judgement.output_tokens
        db.add(
            Adjudication(
                observation_hash=pair.view.content_hash,
                watch_id=judgement.watch_id,
                prompt_version=adjudicator.prompt_version,
                outcome=judgement.outcome,
                error=judgement.error,
                audit_id=judgement.audit_id,
                input_tokens=judgement.input_tokens,
                output_tokens=judgement.output_tokens,
                confidence=verdict.confidence if verdict else None,
                satisfies_clause=verdict.satisfies_clause if verdict else None,
                rationale=verdict.rationale if verdict else None,
            )
        )
        if judgement.error is not None:
            result.failed += 1
            result.failures.append((pair.view.content_hash, judgement.watch_id, judgement.error))
        elif verdict is not None and verdict.is_evidence:
            result.evidence += 1
            db.add(
                Evidence(
                    observation_hash=pair.view.content_hash,
                    watch_id=judgement.watch_id,
                    direction=verdict.direction,
                    magnitude=verdict.magnitude,
                    prompt_version=adjudicator.prompt_version,
                    rationale=verdict.rationale,
                )
            )
        else:
            result.none += 1
        db.commit()
    return result


def dry_run(
    db: Session, prompt_version: str, *, limit: int = 3
) -> list[tuple[Pair, str, str, int]]:
    """The exact text the first ``limit`` pending pairs would send, with an estimate."""
    out = []
    for pair in pending_pairs(db, prompt_version, limit=limit):
        system, user = build_messages(pair.view, pair.watch)
        out.append((pair, system, user, estimate_tokens(system, user)))
    return out
