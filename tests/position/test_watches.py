"""
Tests for the Watch loader and the watches table (backlog task 013).

The class that matters most here is :class:`TestNothingInvalidIsEverStored`. The
acceptance criterion is not "an invalid watch raises" -- it is that an invalid
watch is *not stored*, which is a claim about the database and has to be checked
against the database. Each case asserts the row count is unchanged across the
rejection, and the class ends by accepting a valid watch so that a suite which
passed because the write path was broken would fail.

Invariant 2 -- every Watch names a decision -- is enforced twice on purpose:
once by the loader and once by a CHECK constraint, tested separately below with
raw SQL that bypasses the loader entirely.
"""

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.database.models import Watch as WatchRow
from src.position import TriggerClause, WatchError, load_position, load_watches, sync_watches

from .conftest import ABSENT, TODAY

EXAMPLE_POSITION = Path(__file__).resolve().parents[2] / "config" / "position.example.yaml"
EXAMPLE_WATCHES = Path(__file__).resolve().parents[2] / "config" / "watches.example.yaml"


def _load(path, position):
    return load_watches(path, position=position, today=TODAY)


class TestLoadsValidWatches:
    def test_loads_one_watch(self, watches_file, watch_doc, position):
        (watch,) = _load(watches_file(watch_doc()), position)

        assert watch.id == "conmon-scope-expands"
        assert watch.belief == pytest.approx(0.35)
        assert watch.decision_key == "renew-authorization"
        assert watch.so_what.startswith("Scope expansion")
        assert watch.expires == date(2027, 3, 31)
        assert watch.staleness_alert_days == 30

    def test_days_to_expiry(self, watches_file, watch_doc, position):
        (watch,) = _load(watches_file(watch_doc()), position)
        assert watch.days_to_expiry(TODAY) == 211

    def test_triggers_are_structured_clauses(self, watches_file, watch_doc, position):
        (watch,) = _load(watches_file(watch_doc()), position)

        assert all(isinstance(clause, TriggerClause) for clause in watch.triggers)
        assert watch.triggers[0].entities == ("FedRAMP PMO",)
        assert watch.triggers[0].terms == ("continuous monitoring", "ConMon")
        assert watch.triggers[1].sources == ("Federal Register",)

    def test_triggers_json_omits_empty_fields(self, watches_file, watch_doc, position):
        (watch,) = _load(watches_file(watch_doc()), position)

        assert watch.triggers_json() == [
            {"terms": ["continuous monitoring", "ConMon"], "entities": ["FedRAMP PMO"]},
            {"terms": ["FedRAMP"], "sources": ["Federal Register"]},
        ]

    def test_staleness_accepts_a_cadence_string(self, watches_file, watch_doc, position):
        """
        ``2w`` goes through src/utils/cadence.py rather than a second parser.

        One interval grammar across the system; the cadence module survived task
        012 for exactly this.
        """
        (watch,) = _load(watches_file(watch_doc(staleness_alert_days="2w")), position)
        assert watch.staleness_alert_days == 14


class TestCheckedInExample:
    def test_example_watches_load_against_example_position(self):
        position = load_position(EXAMPLE_POSITION, today=TODAY)
        watches = load_watches(EXAMPLE_WATCHES, position=position, today=TODAY)

        assert len(watches) == 3
        assert {w.decision_key for w in watches} <= position.decision_keys
        assert all(w.triggers for w in watches)

    def test_example_watches_all_name_a_real_decision(self):
        position = load_position(EXAMPLE_POSITION, today=TODAY)
        watches = load_watches(EXAMPLE_WATCHES, position=position, today=TODAY)

        for watch in watches:
            assert position.decision(watch.decision_key) is not None


class TestMissingFile:
    def test_absent_watches_file_fails_fast(self, tmp_path, position):
        with pytest.raises(FileNotFoundError) as exc:
            load_watches(tmp_path / "nope.yaml", position=position, today=TODAY)
        assert "WATCHES_PATH" in str(exc.value)


# Every rejection the acceptance criteria name, as (label, watch overrides).
# ``ABSENT`` removes the field entirely.
REJECTIONS = [
    ("so_what empty string", {"so_what": ""}, "is empty"),
    ("so_what whitespace only", {"so_what": "   \t  "}, "is empty"),
    ("so_what absent", {"so_what": ABSENT}, "'so_what' is required"),
    ("so_what is bare prose", {"so_what": "it matters for the renewal"}, "must be a mapping"),
    (
        "so_what.because blank",
        {"so_what": {"decision": "renew-authorization", "because": "  "}},
        "because is required",
    ),
    (
        "so_what.decision blank",
        {"so_what": {"decision": "", "because": "it moves the renewal"}},
        "decision is required",
    ),
    (
        "so_what names no decision in the Position",
        {"so_what": {"decision": "buy-a-boat", "because": "it moves the renewal"}},
        "names no decision",
    ),
    ("belief above 1.0", {"belief": 1.4}, "outside [0.0, 1.0]"),
    ("belief below 0.0", {"belief": -0.1}, "outside [0.0, 1.0]"),
    ("belief is prose", {"belief": "fairly likely"}, "must be a number"),
    ("belief absent", {"belief": ABSENT}, "'belief' is required"),
    ("expires in the past", {"expires": date(2026, 1, 1)}, "is in the past"),
    ("expires absent", {"expires": ABSENT}, "'expires' is required"),
    ("expires is not a date", {"expires": "soon"}, "is not a date"),
    ("staleness_alert_days zero", {"staleness_alert_days": 0}, "at least 1"),
    ("staleness_alert_days negative", {"staleness_alert_days": -5}, "at least 1"),
    ("staleness_alert_days absent", {"staleness_alert_days": ABSENT}, "is required"),
    (
        "staleness_alert_days is prose",
        {"staleness_alert_days": "when it goes quiet"},
        "not an interval",
    ),
    ("claim blank", {"claim": "   "}, "'claim' is required"),
    ("id absent", {"id": ABSENT}, "'id' is required"),
    ("id is not a slug", {"id": "Watch The Renewal"}, "is not a slug"),
    ("triggers absent", {"triggers": ABSENT}, "'triggers' is required"),
    ("triggers empty", {"triggers": []}, "never fires"),
    ("triggers is prose", {"triggers": "anything about FedRAMP"}, "is prose"),
    (
        "trigger clause is a sentence",
        {"triggers": ["watch for anything that changes the scope"]},
        "not the sentence",
    ),
    ("trigger clause constrains nothing", {"triggers": [{}]}, "constrains nothing"),
    (
        "trigger field is prose",
        {"triggers": [{"terms": "continuous monitoring"}]},
        "must be a list of terms",
    ),
    (
        "trigger clause has an unknown field",
        {"triggers": [{"terms": ["FedRAMP"], "vibe": ["ominous"]}]},
        "unknown field",
    ),
    ("unknown watch field", {"urgency": "high"}, "unknown field"),
]


class TestNothingInvalidIsEverStored:
    """
    Rejection is a claim about the table, so it is checked against the table.

    A loader that raised and then wrote anyway would pass a `pytest.raises`
    suite. The row count is what makes these bite.
    """

    @pytest.mark.parametrize(
        ("label", "overrides", "expected"),
        REJECTIONS,
        ids=[case[0] for case in REJECTIONS],
    )
    def test_rejected_and_not_stored(
        self, label, overrides, expected, watches_file, watch_doc, position, test_session
    ):
        before = test_session.query(WatchRow).count()
        path = watches_file(watch_doc(**overrides))

        # Deliberately not `pytest.raises`. The claim under test is about the
        # table, so the row count has to be asserted whether or not the loader
        # raised -- a loader that quietly accepted this watch must fail on the
        # count, not on a missing exception, so the failure names the real
        # problem.
        raised = None
        try:
            sync_watches(test_session, _load(path, position))
            test_session.commit()
        except WatchError as exc:
            raised = exc

        assert test_session.query(WatchRow).count() == before, f"{label}: was stored"
        assert raised is not None, f"{label}: accepted a watch that must be rejected"
        assert expected in str(raised), f"{label}: unhelpful error {raised}"

    def test_a_valid_watch_is_accepted(self, watches_file, watch_doc, position, test_session):
        """
        The control. Without it every case above could pass on a broken writer.
        """
        assert test_session.query(WatchRow).count() == 0

        watches = _load(watches_file(watch_doc()), position)
        sync_watches(test_session, watches)
        test_session.commit()

        assert test_session.query(WatchRow).count() == 1
        row = test_session.query(WatchRow).one()
        assert row.decision_key == "renew-authorization"
        assert row.triggers[0]["terms"] == ["continuous monitoring", "ConMon"]

    def test_one_bad_watch_stores_none_of_the_others(
        self, watches_file, watch_doc, position, test_session
    ):
        """
        A file is applied whole or not at all.

        Storing the good half leaves the table in a state that matches no file,
        which is the state nobody can debug six months later.
        """
        good = watch_doc(id="good-one")
        bad = watch_doc(id="bad-one", so_what={"decision": "buy-a-boat", "because": "no"})

        with pytest.raises(WatchError):
            watches = _load(watches_file(good, bad), position)
            sync_watches(test_session, watches)

        assert test_session.query(WatchRow).count() == 0


class TestOtherRejections:
    def test_duplicate_ids_are_rejected(self, watches_file, watch_doc, position):
        with pytest.raises(WatchError, match="duplicate watch id"):
            _load(watches_file(watch_doc(), watch_doc()), position)

    def test_empty_file_is_rejected(self, write_yaml, position):
        with pytest.raises(WatchError, match="empty"):
            _load(write_yaml("watches.yaml", "# nothing here\n"), position)

    def test_malformed_yaml_is_rejected(self, write_yaml, position):
        with pytest.raises(WatchError, match="not valid YAML"):
            _load(write_yaml("watches.yaml", "watches: [\n  - id: x\n"), position)

    def test_every_problem_is_reported_at_once(self, watches_file, watch_doc, position):
        path = watches_file(watch_doc(belief=3.0, so_what=ABSENT, staleness_alert_days=0))
        with pytest.raises(WatchError) as exc:
            _load(path, position)
        assert len(exc.value.problems) == 3

    def test_error_names_the_known_decision_keys(self, watches_file, watch_doc, position):
        path = watches_file(watch_doc(so_what={"decision": "buy-a-boat", "because": "no"}))
        with pytest.raises(WatchError) as exc:
            _load(path, position)
        assert "renew-authorization" in str(exc.value)


class TestSync:
    def test_sync_adds_updates_and_removes(self, watches_file, watch_doc, position, test_session):
        first = _load(watches_file(watch_doc(id="a"), watch_doc(id="b")), position)
        summary = sync_watches(test_session, first)
        test_session.commit()
        assert sorted(summary["added"]) == ["a", "b"]

        # The file is authoritative: "b" is gone and "a" moved.
        second = _load(watches_file(watch_doc(id="a", belief=0.9)), position)
        summary = sync_watches(test_session, second)
        test_session.commit()

        assert summary["updated"] == ["a"]
        assert summary["removed"] == ["b"]
        assert test_session.query(WatchRow).count() == 1
        assert test_session.query(WatchRow).one().belief == pytest.approx(0.9)


class TestSchemaEnforcesInvariantTwo:
    """
    The constraints, exercised with raw SQL so the loader is out of the picture.

    Invariant 2 is enforced in the schema, which means a row inserted by hand
    through sqlite3 has to fail the same way a bad YAML file does. This is the
    half of the enforcement the loader tests cannot reach.
    """

    def _insert(self, session, **overrides):
        row = {
            "id": "x",
            "claim": "a claim",
            "belief": 0.5,
            "decision_key": "renew-authorization",
            "so_what": "it moves the renewal",
            "triggers": "[]",
            "expires": "2027-03-31",
            "staleness_alert_days": 30,
        }
        row.update(overrides)
        session.execute(
            text(
                "INSERT INTO watches (id, claim, belief, decision_key, so_what, triggers,"
                " expires, staleness_alert_days) VALUES (:id, :claim, :belief, :decision_key,"
                " :so_what, :triggers, :expires, :staleness_alert_days)"
            ),
            row,
        )

    def test_blank_so_what_is_refused_by_the_database(self, test_session):
        with pytest.raises(IntegrityError):
            self._insert(test_session, so_what="   ")
        test_session.rollback()
        assert test_session.query(WatchRow).count() == 0

    def test_null_so_what_is_refused_by_the_database(self, test_session):
        with pytest.raises(IntegrityError):
            self._insert(test_session, so_what=None)
        test_session.rollback()

    def test_blank_decision_key_is_refused_by_the_database(self, test_session):
        with pytest.raises(IntegrityError):
            self._insert(test_session, decision_key="")
        test_session.rollback()

    def test_out_of_range_belief_is_refused_by_the_database(self, test_session):
        with pytest.raises(IntegrityError):
            self._insert(test_session, belief=1.5)
        test_session.rollback()

    def test_zero_staleness_is_refused_by_the_database(self, test_session):
        with pytest.raises(IntegrityError):
            self._insert(test_session, staleness_alert_days=0)
        test_session.rollback()

    def test_a_good_row_still_inserts(self, test_session):
        self._insert(test_session)
        test_session.commit()
        assert test_session.query(WatchRow).count() == 1
