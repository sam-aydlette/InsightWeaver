"""
Institutional activity: what a beat's declared institutions did this run,
against what they usually do.

The signal is the **delta**, never the count. "FedRAMP PMO: 6" is noise -- the
PMO appears most days and a flat tally reproduces that fact every morning
without adding anything. "FedRAMP PMO appeared in 6 items this run, against a
trailing average of 1" is the observation worth a brief line. Everything in
this module exists to turn the first into the second.

Three rules follow from that, and each is load-bearing:

* **Zeroes are recorded.** A run in which an office said nothing is an
  observation about that office. Omitting it would average only over the days
  something happened, and the average would always say "normal".
* **Silence is reported when it is unusual.** An entity that has been active
  and is quiet appears, because the absence is the finding. Dropping it is the
  same class of bug as a standing question vanishing on a quiet day.
* **An entity nobody has ever mentioned does not appear at all.** Declaring an
  entity is a hypothesis about where news comes from; a hypothesis that has
  never paid out is a note about the config, not a line in the brief.

A count is an observation, not a verdict. Nothing here scores, ranks or
interprets: no "most active", no significance, no ordering by magnitude. The
tool's north star is that no entity stores a truth value, and activity is not
importance.

Added 2026-08-26 for backlog task 006.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..config.beats import CoverageEntity
from ..database.models import ENTITY_KINDS, BeatEntity, EntityMention
from ..utils import utcnow
from .entity_matcher import compile_entities, count_item_mentions

logger = logging.getLogger(__name__)

__all__ = [
    "MOVEMENT_DOWN",
    "MOVEMENT_FIRST_RUN",
    "MOVEMENT_UNCHANGED",
    "MOVEMENT_UP",
    "TRAILING_WINDOW",
    "ActivityObservation",
    "EntityActivity",
    "observe_activity",
    "record_mentions",
    "sync_entities",
]

# How many previous recorded runs the trailing average is taken over. Short on
# purpose: a beat runs daily and a month-long baseline would smother a real
# move under history nobody remembers.
TRAILING_WINDOW = 5

# What counts as movement. A change must clear both bars: at least one whole
# item (so an average of 0.2 drifting to 0 is not "news"), and at least half
# the baseline (so 12 against an average of 11 is not "news" either).
MIN_ABSOLUTE_MOVE = 1.0
MIN_RELATIVE_MOVE = 0.5

MOVEMENT_UP = "up"
MOVEMENT_DOWN = "down"
MOVEMENT_UNCHANGED = "unchanged"
MOVEMENT_FIRST_RUN = "first_run"


class UnsupportedEntityKind(ValueError):
    """
    Raised when something other than an org, program or document type reaches
    the write path.

    The loader already refuses a ``coverage.people`` key, so this cannot happen
    through configuration. It is checked again here because this is the last
    point before a row is written, and a row is the thing that outlives the
    run. A caller that has to route around this check is asking for the design
    the task forbids.
    """


@dataclass(frozen=True)
class EntityActivity:
    """One entity's reading for one run: this run's count against its baseline."""

    kind: str
    name: str
    count: int
    trailing_average: float | None  # None on the first run an entity is observed
    prior_runs: int  # how many recorded runs the average is taken over
    movement: str

    def as_dict(self) -> dict[str, Any]:
        """The shape stored in synthesis metadata and read by the renderers."""
        return {
            "kind": self.kind,
            "name": self.name,
            "count": self.count,
            "trailing_average": self.trailing_average,
            "prior_runs": self.prior_runs,
            "movement": self.movement,
        }


@dataclass(frozen=True)
class ActivityObservation:
    """
    One run's institutional activity: what to render, and what to write.

    ``entities`` is the rendered view -- only entities with something to say.
    ``counts_by_entity_id`` is the ledger view -- every declared entity,
    zeroes included, so the baseline stays honest.
    """

    entities: tuple[EntityActivity, ...]
    counts_by_entity_id: dict[int, int]
    items_scanned: int
    never_observed: int  # declared entities with no mentions and no history

    def as_dict(self) -> dict[str, Any]:
        """The ``metadata["institutional_activity"]`` payload."""
        return {
            "window": TRAILING_WINDOW,
            "items_scanned": self.items_scanned,
            "never_observed": self.never_observed,
            "entities": [entity.as_dict() for entity in self.entities],
        }


def sync_entities(
    session: Session, beat_id: int, entities: Iterable[CoverageEntity]
) -> dict[str, int]:
    """
    Get or create the ``beat_entities`` rows for a beat's coverage block.

    Returns ``{CoverageEntity.key: beat_entities.id}``. Aliases are refreshed
    from the config on every run, because the config is authoritative for what
    an entity is called; the row exists only to give its history somewhere to
    hang. Entities dropped from the config keep their rows and their past
    counts -- deleting them would silently rewrite the record of what was
    observed.
    """
    ids: dict[str, int] = {}
    for entity in entities:
        if entity.kind not in ENTITY_KINDS:
            raise UnsupportedEntityKind(
                f"Cannot record a '{entity.kind}' entity: a beat tracks "
                f"{', '.join(ENTITY_KINDS)} and nothing else."
            )
        row = (
            session.query(BeatEntity)
            .filter(
                BeatEntity.beat_id == beat_id,
                BeatEntity.kind == entity.kind,
                BeatEntity.name == entity.name,
            )
            .first()
        )
        if row is None:
            row = BeatEntity(
                beat_id=beat_id,
                kind=entity.kind,
                name=entity.name,
                aliases=list(entity.aliases),
            )
            session.add(row)
            session.flush()
            logger.info(f"Registered beat entity '{entity.name}' ({entity.kind}) as id {row.id}")
        elif list(row.aliases or []) != list(entity.aliases):
            row.aliases = list(entity.aliases)
            row.updated_at = utcnow()
        ids[entity.key] = int(row.id)
    return ids


def _trailing_counts(session: Session, entity_id: int) -> list[int]:
    """
    This entity's last :data:`TRAILING_WINDOW` recorded counts, most recent
    first. Zero rows included -- see the module docstring.
    """
    rows: list[Any] = (
        session.query(EntityMention.item_count)
        .filter(EntityMention.entity_id == entity_id)
        .order_by(EntityMention.observed_at.desc(), EntityMention.id.desc())
        .limit(TRAILING_WINDOW)
        .all()
    )
    return [int(row[0] or 0) for row in rows]


def classify_movement(count: int, trailing_average: float | None) -> str:
    """
    How this run's count sits against the baseline.

    Returns :data:`MOVEMENT_FIRST_RUN` when there is no baseline yet -- on day
    one everything is a first run and the section is honestly uninformative,
    which is expected and must not be tuned away.
    """
    if trailing_average is None:
        return MOVEMENT_FIRST_RUN
    delta = count - trailing_average
    threshold = max(MIN_ABSOLUTE_MOVE, MIN_RELATIVE_MOVE * trailing_average)
    if delta >= threshold:
        return MOVEMENT_UP
    if -delta >= threshold:
        return MOVEMENT_DOWN
    return MOVEMENT_UNCHANGED


def observe_activity(
    session: Session,
    beat_id: int,
    entities: Sequence[CoverageEntity],
    texts: Sequence[str],
) -> ActivityObservation:
    """
    Count this run's mentions and read them against each entity's baseline.

    Reads history and registers entities; writes no mention rows. Those are
    written by :func:`record_mentions` once the run has a ``beat_runs`` id, so
    a run that fails after this point leaves no half-recorded baseline behind.
    """
    entity_ids = sync_entities(session, beat_id, entities)
    counts = count_item_mentions(compile_entities(entities), texts)

    readings: list[EntityActivity] = []
    counts_by_entity_id: dict[int, int] = {}
    never_observed = 0

    for entity in entities:
        count = counts.get(entity.key, 0)
        entity_id = entity_ids[entity.key]
        counts_by_entity_id[entity_id] = count

        history = _trailing_counts(session, entity_id)
        trailing_average = (sum(history) / len(history)) if history else None

        # "Has this ever been seen" is asked of the counts, not of the rows:
        # every entity gets a row every run, so the presence of rows says only
        # that the beat has run before.
        ever_observed = count > 0 or any(history)
        if not ever_observed:
            never_observed += 1
            continue

        readings.append(
            EntityActivity(
                kind=entity.kind,
                name=entity.name,
                count=count,
                trailing_average=(
                    round(trailing_average, 2) if trailing_average is not None else None
                ),
                prior_runs=len(history),
                movement=classify_movement(count, trailing_average),
            )
        )

    # Alphabetical within kind, never by count: ordering by magnitude would
    # make this a leaderboard, and activity is not significance.
    readings.sort(key=lambda reading: (ENTITY_KINDS.index(reading.kind), reading.name.lower()))

    return ActivityObservation(
        entities=tuple(readings),
        counts_by_entity_id=counts_by_entity_id,
        items_scanned=len(texts),
        never_observed=never_observed,
    )


def record_mentions(
    session: Session,
    counts_by_entity_id: dict[int, int],
    *,
    beat_run_id: int | None,
    synthesis_id: int | None,
    items_scanned: int | None = None,
) -> int:
    """
    Write this run's counts, one row per entity including the zeroes.

    Added to the caller's session without committing: the mention rows belong
    to the same transaction as the synthesis and the ``beat_runs`` row, so a
    stored run is either fully recorded or does not exist.
    """
    observed_at = utcnow()
    for entity_id, count in sorted(counts_by_entity_id.items()):
        session.add(
            EntityMention(
                entity_id=entity_id,
                beat_run_id=beat_run_id,
                synthesis_id=synthesis_id,
                item_count=count,
                items_scanned=items_scanned,
                observed_at=observed_at,
            )
        )
    return len(counts_by_entity_id)
