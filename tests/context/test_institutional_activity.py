"""
Tests for the institutional activity ledger.

Three properties carry the feature and each is pinned here:

* the reported signal is the **delta** against a trailing average, never a
  flat count -- an office that appears every day is not news;
* an entity with no mentions and no history **does not appear**, because
  declaring it was a hypothesis that has not paid out;
* an entity that has been active and is now quiet **does appear**, because
  silence is information and dropping it is the same class of bug as a
  standing question vanishing on a quiet day.

Nothing here creates a row about a person, and nothing can: `sync_entities`
refuses any kind outside org / program / document_type.
"""

import pytest

from src.config.beats import CoverageEntity
from src.context.institutional_activity import (
    MOVEMENT_DOWN,
    MOVEMENT_FIRST_RUN,
    MOVEMENT_UNCHANGED,
    MOVEMENT_UP,
    TRAILING_WINDOW,
    UnsupportedEntityKind,
    classify_movement,
    observe_activity,
    record_mentions,
    sync_entities,
)
from src.database.models import Beat, BeatEntity, EntityMention

PMO = CoverageEntity("org", "FedRAMP PMO", ("FedRAMP Program Management Office",))
CISA = CoverageEntity("org", "CISA")
CMMC = CoverageEntity("program", "CMMC")


@pytest.fixture
def beat_id(test_session):
    beat = Beat(name="test-beat", description="A beat.", config_path="/tmp/test-beat.json")
    test_session.add(beat)
    test_session.commit()
    return beat.id


def run_once(session, beat_id, entities, texts):
    """Observe one run and record it, the way the synthesizer does."""
    observation = observe_activity(session, beat_id, entities, texts)
    record_mentions(
        session,
        observation.counts_by_entity_id,
        beat_run_id=None,
        synthesis_id=None,
        items_scanned=observation.items_scanned,
    )
    session.commit()
    return observation


def by_name(observation):
    return {entity.name: entity for entity in observation.entities}


class TestClassifyMovement:
    """
    The delta rule in isolation. A move must clear two bars: at least one whole
    item, and at least half the baseline. The first stops noise around zero,
    the second stops noise around a large baseline.
    """

    def test_no_baseline_is_a_first_run(self):
        assert classify_movement(6, None) == MOVEMENT_FIRST_RUN

    def test_a_large_jump_over_a_small_baseline_is_movement(self):
        assert classify_movement(6, 1.0) == MOVEMENT_UP

    def test_a_drop_to_silence_from_an_active_baseline_is_movement(self):
        assert classify_movement(0, 4.0) == MOVEMENT_DOWN

    def test_sitting_on_the_baseline_is_unchanged(self):
        assert classify_movement(3, 3.0) == MOVEMENT_UNCHANGED

    def test_a_sub_item_drift_around_zero_is_not_movement(self):
        """An average of 0.2 going to 0 is arithmetic, not news."""
        assert classify_movement(0, 0.2) == MOVEMENT_UNCHANGED

    def test_a_small_wobble_on_a_large_baseline_is_not_movement(self):
        assert classify_movement(12, 11.0) == MOVEMENT_UNCHANGED

    def test_a_proportionate_move_on_a_large_baseline_is_movement(self):
        assert classify_movement(20, 11.0) == MOVEMENT_UP


class TestSyncEntities:
    def test_creates_one_row_per_declared_entity(self, test_session, beat_id):
        ids = sync_entities(test_session, beat_id, [PMO, CMMC])
        test_session.commit()

        rows = test_session.query(BeatEntity).all()
        assert len(rows) == 2
        assert set(ids) == {"org:FedRAMP PMO", "program:CMMC"}
        assert {row.kind for row in rows} == {"org", "program"}

    def test_is_idempotent_across_runs(self, test_session, beat_id):
        first = sync_entities(test_session, beat_id, [PMO])
        test_session.commit()
        second = sync_entities(test_session, beat_id, [PMO])
        test_session.commit()

        assert first == second
        assert test_session.query(BeatEntity).count() == 1

    def test_aliases_are_refreshed_from_the_config(self, test_session, beat_id):
        sync_entities(test_session, beat_id, [CoverageEntity("org", "CISA", ("old",))])
        test_session.commit()
        sync_entities(test_session, beat_id, [CoverageEntity("org", "CISA", ("new",))])
        test_session.commit()

        row = test_session.query(BeatEntity).one()
        assert row.aliases == ["new"]

    def test_an_entity_dropped_from_the_config_keeps_its_row(self, test_session, beat_id):
        """Deleting it would silently rewrite the record of what was observed."""
        sync_entities(test_session, beat_id, [PMO, CMMC])
        test_session.commit()
        sync_entities(test_session, beat_id, [PMO])
        test_session.commit()

        assert test_session.query(BeatEntity).count() == 2

    def test_a_kind_outside_the_closed_set_is_refused(self, test_session, beat_id):
        """
        The loader already refuses a `coverage.people` key. This is the last
        check before a row is written, and a row is the thing that outlives the
        run.
        """
        with pytest.raises(UnsupportedEntityKind, match="and nothing else"):
            sync_entities(test_session, beat_id, [CoverageEntity("person", "Anyone")])


class TestFirstRun:
    def test_a_mentioned_entity_has_no_baseline_yet(self, test_session, beat_id):
        observation = run_once(test_session, beat_id, [PMO], ["The FedRAMP PMO issued guidance."])

        reading = by_name(observation)["FedRAMP PMO"]
        assert reading.count == 1
        assert reading.trailing_average is None
        assert reading.prior_runs == 0
        assert reading.movement == MOVEMENT_FIRST_RUN

    def test_an_unmentioned_entity_does_not_appear(self, test_session, beat_id):
        observation = run_once(test_session, beat_id, [PMO, CMMC], ["The FedRAMP PMO acted."])

        assert set(by_name(observation)) == {"FedRAMP PMO"}
        assert observation.never_observed == 1

    def test_the_unmentioned_entity_is_still_written_to_the_ledger(self, test_session, beat_id):
        """
        Zeroes are recorded even when they are not rendered. Without them the
        trailing average would average only the days something happened, and
        would always read as "normal".
        """
        run_once(test_session, beat_id, [PMO, CMMC], ["The FedRAMP PMO acted."])

        rows = test_session.query(EntityMention).all()
        assert sorted(row.item_count for row in rows) == [0, 1]
        assert all(row.items_scanned == 1 for row in rows)


class TestDeltaAgainstTrailingAverage:
    def test_a_spike_reports_the_baseline_it_departed_from(self, test_session, beat_id):
        for _ in range(3):
            run_once(test_session, beat_id, [PMO], ["The FedRAMP PMO issued guidance."])

        observation = run_once(
            test_session,
            beat_id,
            [PMO],
            ["FedRAMP PMO one."] * 6,
        )

        reading = by_name(observation)["FedRAMP PMO"]
        assert reading.count == 6
        assert reading.trailing_average == 1.0
        assert reading.prior_runs == 3
        assert reading.movement == MOVEMENT_UP

    def test_a_steady_entity_is_reported_unchanged_not_dropped(self, test_session, beat_id):
        for _ in range(3):
            run_once(test_session, beat_id, [CISA], ["CISA acted.", "CISA again."])

        observation = run_once(test_session, beat_id, [CISA], ["CISA acted.", "CISA again."])

        reading = by_name(observation)["CISA"]
        assert reading.count == 2
        assert reading.trailing_average == 2.0
        assert reading.movement == MOVEMENT_UNCHANGED

    def test_an_entity_that_goes_quiet_after_being_active_still_appears(
        self, test_session, beat_id
    ):
        """Silence is information. This is the case the feature exists for."""
        for _ in range(3):
            run_once(test_session, beat_id, [CISA], ["CISA acted.", "CISA again.", "CISA more."])

        observation = run_once(test_session, beat_id, [CISA], ["Nothing relevant today."])

        reading = by_name(observation)["CISA"]
        assert reading.count == 0
        assert reading.trailing_average == 3.0
        assert reading.movement == MOVEMENT_DOWN

    def test_an_entity_active_only_in_the_past_still_appears(self, test_session, beat_id):
        """
        History, not just this run, decides whether an entity is listed. One
        past mention is enough to make today's silence worth stating.
        """
        run_once(test_session, beat_id, [CMMC], ["CMMC rule lands."])
        observation = run_once(test_session, beat_id, [CMMC], ["Nothing relevant."])

        assert "CMMC" in by_name(observation)
        assert observation.never_observed == 0

    def test_the_average_is_taken_over_the_trailing_window_only(self, test_session, beat_id):
        """A long-ago burst must not anchor the baseline forever."""
        run_once(test_session, beat_id, [CISA], ["CISA."] * 10)
        for _ in range(TRAILING_WINDOW):
            run_once(test_session, beat_id, [CISA], ["Nothing."])

        observation = run_once(test_session, beat_id, [CISA], ["CISA acted."])

        reading = by_name(observation)["CISA"]
        assert reading.prior_runs == TRAILING_WINDOW
        assert reading.trailing_average == 0.0

    def test_a_zero_run_pulls_the_average_down(self, test_session, beat_id):
        run_once(test_session, beat_id, [CISA], ["CISA.", "CISA again."])
        run_once(test_session, beat_id, [CISA], ["Nothing."])

        observation = run_once(test_session, beat_id, [CISA], ["Nothing again."])

        assert by_name(observation)["CISA"].trailing_average == 1.0


class TestOrdering:
    def test_entities_are_ordered_by_kind_then_name_never_by_count(self, test_session, beat_id):
        """
        Ordering by magnitude would make this a leaderboard, and activity is
        not significance. `CISA` is mentioned three times as often as
        `FedRAMP PMO` and still sorts after it.
        """
        entities = [PMO, CISA, CMMC]
        texts = ["CISA.", "CISA.", "CISA.", "FedRAMP PMO.", "CMMC."]

        observation = run_once(test_session, beat_id, entities, texts)

        assert [entity.name for entity in observation.entities] == [
            "CISA",
            "FedRAMP PMO",
            "CMMC",
        ]


class TestPayload:
    def test_as_dict_is_json_shaped_and_carries_the_window(self, test_session, beat_id):
        observation = run_once(test_session, beat_id, [PMO, CMMC], ["FedRAMP PMO acted."])

        payload = observation.as_dict()

        assert payload["window"] == TRAILING_WINDOW
        assert payload["items_scanned"] == 1
        assert payload["never_observed"] == 1
        assert payload["entities"] == [
            {
                "kind": "org",
                "name": "FedRAMP PMO",
                "count": 1,
                "trailing_average": None,
                "prior_runs": 0,
                "movement": MOVEMENT_FIRST_RUN,
            }
        ]

    def test_no_payload_key_names_a_person_or_a_role(self, test_session, beat_id):
        """
        A blunt structural check: the rendered payload carries kinds, names,
        counts and averages. There is no field a per-individual record could
        be smuggled through.
        """
        payload = run_once(test_session, beat_id, [PMO], ["FedRAMP PMO acted."]).as_dict()

        assert set(payload) == {"window", "items_scanned", "never_observed", "entities"}
        assert set(payload["entities"][0]) == {
            "kind",
            "name",
            "count",
            "trailing_average",
            "prior_runs",
            "movement",
        }
