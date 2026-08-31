"""
Tests for the migration that adds ``route_candidates`` (backlog task 015).

Weighted, like the observations migration's tests, towards the property that
would be silently lost if the model-driven creation were replaced by hand-written
DDL. Here that property is the unique constraint on
``(observation_hash, watch_id)``: a table created without it looks correct in
every way except that routing stops being idempotent, and the symptom is a
doubled candidate count on the second run rather than an error.
"""

import pytest
from sqlalchemy import create_engine, inspect, text

from src.database.migrations import add_route_candidates as mig
from src.database.models import Base, RouteCandidate


@pytest.fixture
def blank_engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")


@pytest.fixture
def corpus_engine(tmp_path):
    """A database that already has the rest of the schema, as the real one does."""
    engine = create_engine(f"sqlite:///{tmp_path / 'corpus.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE route_candidates"))
    return engine


class TestUpgrade:
    def test_it_creates_the_table(self, blank_engine):
        assert mig.upgrade(blank_engine) == ["route_candidates"]
        assert inspect(blank_engine).has_table("route_candidates")

    def test_it_is_a_no_op_when_the_table_exists(self, corpus_engine):
        mig.upgrade(corpus_engine)
        assert mig.upgrade(corpus_engine) == []

    def test_it_does_not_touch_articles_or_observations(self, corpus_engine):
        before = set(inspect(corpus_engine).get_table_names())
        mig.upgrade(corpus_engine)
        after = set(inspect(corpus_engine).get_table_names())
        assert after - before == {"route_candidates"}


class TestTheConstraintThatMakesRoutingIdempotent:
    def test_the_unique_constraint_is_present(self, blank_engine):
        mig.upgrade(blank_engine)
        constraints = inspect(blank_engine).get_unique_constraints("route_candidates")
        assert any(
            set(c["column_names"]) == {"observation_hash", "watch_id"} for c in constraints
        ), constraints

    def test_the_clause_index_check_is_present(self, blank_engine):
        mig.upgrade(blank_engine)
        names = {c["name"] for c in inspect(blank_engine).get_check_constraints("route_candidates")}
        assert "ck_route_clause_index" in names

    def test_the_model_and_the_migration_cannot_drift(self, blank_engine):
        """The migration creates from the model, so this is a tautology by design."""
        mig.upgrade(blank_engine)
        created = {c["name"] for c in inspect(blank_engine).get_columns("route_candidates")}
        assert created == {c.name for c in RouteCandidate.__table__.columns}


class TestDowngrade:
    def test_it_refuses_without_confirmation(self, blank_engine):
        mig.upgrade(blank_engine)
        with pytest.raises(SystemExit):
            mig.downgrade(blank_engine)
        assert inspect(blank_engine).has_table("route_candidates")

    def test_it_drops_the_table_when_confirmed(self, blank_engine):
        mig.upgrade(blank_engine)
        assert mig.downgrade(blank_engine, confirmed=True) == ["route_candidates"]
        assert not inspect(blank_engine).has_table("route_candidates")
