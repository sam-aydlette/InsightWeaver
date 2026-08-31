"""
Tests for the migration that adds the watches table (backlog task 013).

The migration builds the table from the model, so the tests are weighted
towards the properties that would be silently lost if someone later replaced it
with hand-written DDL: that the CHECK constraints exist in the created table,
and that the way down -- which does lose rows -- refuses without the flag.

Every fixture builds its own SQLite file. Nothing here opens the real database.
"""

import pytest
from sqlalchemy import create_engine, inspect, text

from src.database.migrations import add_watches_table as mig
from src.database.models import Watch


@pytest.fixture
def blank_engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")


class TestUpgrade:
    def test_creates_the_table(self, blank_engine):
        assert mig.upgrade(blank_engine) is True
        assert inspect(blank_engine).has_table("watches")

    def test_is_idempotent(self, blank_engine):
        mig.upgrade(blank_engine)
        assert mig.upgrade(blank_engine) is False

    def test_columns_match_the_model(self, blank_engine):
        mig.upgrade(blank_engine)
        created = {c["name"] for c in inspect(blank_engine).get_columns("watches")}
        assert created == set(Watch.__table__.columns.keys())

    def test_carries_the_seven_fields_the_spec_names(self, blank_engine):
        mig.upgrade(blank_engine)
        created = {c["name"] for c in inspect(blank_engine).get_columns("watches")}
        assert {
            "id",
            "claim",
            "belief",
            "so_what",
            "triggers",
            "expires",
            "staleness_alert_days",
        } <= created

    def test_check_constraints_are_in_the_created_ddl(self, blank_engine):
        """
        Invariant 2 is enforced at the storage layer, so the DDL has to carry it.

        Read from sqlite_master rather than from the model: the question is what
        the migration actually created, not what it intended to.
        """
        mig.upgrade(blank_engine)
        with blank_engine.connect() as conn:
            ddl = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='watches'")
            ).scalar()

        assert "ck_watches_so_what_present" in ddl
        assert "ck_watches_decision_present" in ddl
        assert "ck_watches_belief_range" in ddl
        assert "ck_watches_staleness_min" in ddl

    def test_touches_nothing_else(self, blank_engine):
        """Additive means additive: it creates one table and no others."""
        mig.upgrade(blank_engine)
        assert inspect(blank_engine).get_table_names() == ["watches"]


class TestDowngrade:
    def test_refuses_without_confirm(self, blank_engine):
        mig.upgrade(blank_engine)
        with pytest.raises(SystemExit) as exc:
            mig.downgrade(blank_engine)
        assert "--confirm" in str(exc.value)
        assert inspect(blank_engine).has_table("watches")

    def test_drops_with_confirm(self, blank_engine):
        mig.upgrade(blank_engine)
        assert mig.downgrade(blank_engine, confirmed=True) is True
        assert not inspect(blank_engine).has_table("watches")

    def test_drop_on_a_missing_table_is_a_no_op(self, blank_engine):
        assert mig.downgrade(blank_engine, confirmed=True) is False
