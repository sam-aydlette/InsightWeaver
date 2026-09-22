"""
The belief ledger: append-only, operator-written, and the one definition of live.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.database.models import LedgerIsAppendOnly, Watch, WatchBelief
from src.position.ledger import (
    LedgerError,
    current_beliefs,
    live_clause,
    open_clause,
    record_belief,
    resolve_watch,
)

TODAY = date(2026, 9, 1)


def _watch(session, watch_id="w", belief=0.35, expires=date(2027, 3, 31)) -> Watch:
    row = Watch(
        id=watch_id,
        claim="A claim.",
        belief=belief,
        decision_key="d",
        so_what="because",
        triggers=[{"terms": ["x"]}],
        expires=expires,
        staleness_alert_days=30,
    )
    session.add(row)
    session.flush()
    return row


class TestRecordBelief:
    def test_a_principal_row_is_appended_with_its_note_and_time(self, test_session):
        _watch(test_session)
        when = datetime(2026, 9, 1, 9, 0)

        row = record_belief(
            test_session, "w", 0.6, source="principal", note="  the memo landed ", observed_at=when
        )

        assert (row.belief, row.source, row.note, row.observed_at) == (
            0.6,
            "principal",
            "the memo landed",
            when,
        )

    @pytest.mark.parametrize("belief", [-0.1, 1.5, "0.5", True])
    def test_a_belief_outside_the_unit_interval_or_not_a_number_is_refused(
        self, test_session, belief
    ):
        _watch(test_session)
        with pytest.raises(LedgerError):
            record_belief(test_session, "w", belief, source="principal", note="why")

    @pytest.mark.parametrize("note", [None, "", "   "])
    def test_an_operator_belief_without_a_note_is_refused(self, test_session, note):
        _watch(test_session)
        with pytest.raises(LedgerError, match="note"):
            record_belief(test_session, "w", 0.5, source="principal", note=note)

    def test_an_unknown_source_is_refused(self, test_session):
        _watch(test_session)
        with pytest.raises(LedgerError, match="source"):
            record_belief(test_session, "w", 0.5, source="model", note="n")

    def test_an_unknown_watch_is_refused(self, test_session):
        with pytest.raises(LedgerError, match="no watch"):
            record_belief(test_session, "nope", 0.5, source="principal", note="n")

    def test_a_retired_or_resolved_watch_takes_no_new_belief(self, test_session):
        retired = _watch(test_session, "r")
        retired.retired_at = datetime(2026, 8, 1)
        resolved = _watch(test_session, "s")
        resolve_watch(test_session, "s", outcome="yes", note="it happened")

        with pytest.raises(LedgerError, match="retired"):
            record_belief(test_session, "r", 0.5, source="principal", note="n")
        with pytest.raises(LedgerError, match="resolved"):
            record_belief(test_session, "s", 0.5, source="principal", note="n")
        assert resolved.outcome == "yes"

    def test_an_orphaned_ledger_row_is_named_not_a_key_error(self, test_session):
        """SQLite is not enforcing the foreign key; a hand delete must fail by name."""
        _watch(test_session)
        record_belief(test_session, "w", 0.5, source="principal", note="n")
        test_session.execute(text("DELETE FROM watches WHERE id = 'w'"))

        with pytest.raises(LedgerError, match="belongs to watch 'w', which does not exist"):
            current_beliefs(test_session)


class TestAppendOnly:
    def test_the_orm_refuses_an_update(self, test_session):
        _watch(test_session)
        row = record_belief(test_session, "w", 0.5, source="principal", note="n")

        row.belief = 0.9
        with pytest.raises(LedgerIsAppendOnly):
            test_session.flush()
        test_session.rollback()

    def test_the_orm_refuses_a_delete(self, test_session):
        _watch(test_session)
        row = record_belief(test_session, "w", 0.5, source="principal", note="n")

        test_session.delete(row)
        with pytest.raises(LedgerIsAppendOnly):
            test_session.flush()
        test_session.rollback()

    @pytest.mark.parametrize(
        "statement",
        [
            "UPDATE watch_beliefs SET belief = 0.9",
            "DELETE FROM watch_beliefs",
        ],
    )
    def test_the_database_refuses_raw_sql_too(self, test_session, statement):
        """The trigger, not the ORM, is what stops a sqlite3 shell."""
        _watch(test_session)
        record_belief(test_session, "w", 0.5, source="principal", note="n")
        test_session.commit()

        with pytest.raises(IntegrityError, match="append-only"):
            test_session.execute(text(statement))
        test_session.rollback()
        assert test_session.query(WatchBelief).count() == 1


class TestCurrentBeliefs:
    def test_the_latest_row_wins_and_the_registration_value_is_kept(self, test_session):
        _watch(test_session, belief=0.35)
        record_belief(
            test_session, "w", 0.5, source="file", note=None, observed_at=datetime(2026, 8, 1)
        )
        record_belief(
            test_session, "w", 0.7, source="principal", note="n", observed_at=datetime(2026, 8, 2)
        )

        current = current_beliefs(test_session)["w"]

        assert (current.belief, current.source, current.registered) == (0.7, "principal", 0.35)
        assert current.observed_at == datetime(2026, 8, 2)

    def test_two_rows_at_the_same_instant_resolve_by_id_and_a_back_dated_row_is_not_current(
        self, test_session
    ):
        _watch(test_session)
        same = datetime(2026, 9, 1, 9, 0)
        record_belief(test_session, "w", 0.6, source="principal", note="a", observed_at=same)
        record_belief(test_session, "w", 0.2, source="file", note=None, observed_at=same)
        assert current_beliefs(test_session)["w"].belief == 0.2

        record_belief(
            test_session, "w", 0.9, source="principal", note="b", observed_at=datetime(2026, 8, 1)
        )
        assert current_beliefs(test_session)["w"].belief == 0.2

    def test_a_watch_with_no_ledger_row_reads_as_its_registration_belief(self, test_session):
        _watch(test_session, belief=0.35)

        current = current_beliefs(test_session)["w"]

        assert (current.belief, current.source, current.registered) == (0.35, "file", 0.35)


class TestResolve:
    def test_resolution_is_recorded_once(self, test_session):
        _watch(test_session)

        row = resolve_watch(test_session, "w", outcome="no", note="deviation published")

        assert (row.outcome, row.resolution_note) == ("no", "deviation published")
        assert row.resolved_at is not None
        with pytest.raises(LedgerError, match="resolved"):
            resolve_watch(test_session, "w", outcome="yes", note="changed my mind")

    def test_a_retired_watch_can_still_be_graded(self, test_session):
        """A claim often settles after it has left the file; grading it is allowed."""
        _watch(test_session).retired_at = datetime(2026, 8, 1)

        row = resolve_watch(test_session, "w", outcome="yes", note="settled after retirement")

        assert row.outcome == "yes"

    @pytest.mark.parametrize("outcome, note", [("maybe", "n"), ("yes", ""), ("yes", "  ")])
    def test_a_bad_outcome_or_blank_note_is_refused(self, test_session, outcome, note):
        _watch(test_session)
        with pytest.raises(LedgerError):
            resolve_watch(test_session, "w", outcome=outcome, note=note)


class TestLiveness:
    def test_live_means_open_and_not_expired(self, test_session):
        _watch(test_session, "live")
        _watch(test_session, "expired", expires=date(2026, 1, 1))
        _watch(test_session, "retired").retired_at = datetime(2026, 8, 1)
        _watch(test_session, "resolved")
        resolve_watch(test_session, "resolved", outcome="yes", note="n")
        test_session.flush()

        live = {i for (i,) in test_session.query(Watch.id).filter(live_clause(TODAY))}
        open_ = {i for (i,) in test_session.query(Watch.id).filter(open_clause())}

        assert live == {"live"}
        assert open_ == {"live", "expired"}


def test_only_sync_and_the_two_commands_write_belief_or_resolution():
    """
    The writers, by construction and by name: the ledger functions themselves,
    ``sync_watches`` (file beliefs), and the ``believe`` and ``resolve``
    commands. Any other module that constructs a ledger row, calls the ledger
    functions, assigns the resolution columns, or bulk-updates them fails here.
    A ``class WatchBelief(`` statement is a definition, not a construction, and
    is excluded by the lookbehind rather than by exempting its whole file.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src"
    patterns = [
        re.compile(r"(?<!class )\bWatchBelief\("),
        re.compile(r"\brecord_belief\("),
        re.compile(r"\bresolve_watch\("),
        re.compile(r"\.resolved_at\s*=|\.outcome\s*=|\.resolution_note\s*=|\.retired_at\s*="),
        re.compile(r"\.update\([^)]*(resolved_at|outcome|resolution_note|retired_at)"),
    ]
    allowed = {
        root / "position" / "ledger.py",  # the functions themselves
        root / "position" / "watches.py",  # sync: file beliefs, retire and restore
        root / "cli" / "watch.py",  # believe and resolve
    }
    offenders = [
        str(p.relative_to(root))
        for p in sorted(root.rglob("*.py"))
        if p not in allowed and any(pat.search(p.read_text()) for pat in patterns)
    ]
    assert offenders == [], f"belief or resolution written outside the allowed writers: {offenders}"
