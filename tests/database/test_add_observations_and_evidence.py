"""
Tests for the migration that adds observations and evidence (backlog task 014).

Weighted, like the watches migration's tests, towards the properties that would
be silently lost if the model-driven creation were ever replaced by hand-written
DDL. For ``observations`` that is not only the CHECK constraints but the BEFORE
UPDATE trigger: a table created without it looks correct in every way except the
one that matters.

The other thing asserted here is what the migration does *not* do. It must not
touch ``articles``.
"""

import pytest
from sqlalchemy import create_engine, inspect, text

from src.database.migrations import add_observations_and_evidence as mig
from src.database.models import Base, Evidence, Observation


@pytest.fixture
def blank_engine(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")


@pytest.fixture
def corpus_engine(tmp_path):
    """A database that already has articles in it, as the real one does."""
    engine = create_engine(f"sqlite:///{tmp_path / 'corpus.db'}")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE evidence"))
        conn.execute(text("DROP TABLE observations"))
        conn.execute(
            text("INSERT INTO articles (guid, title) VALUES ('legacy-1', 'A pre-rewrite row')")
        )
    return engine


class TestUpgrade:
    def test_creates_both_tables(self, blank_engine):
        assert mig.upgrade(blank_engine) == ["observations", "evidence"]
        inspector = inspect(blank_engine)
        assert inspector.has_table("observations")
        assert inspector.has_table("evidence")

    def test_is_idempotent(self, blank_engine):
        mig.upgrade(blank_engine)
        assert mig.upgrade(blank_engine) == []

    def test_columns_match_the_models(self, blank_engine):
        mig.upgrade(blank_engine)
        inspector = inspect(blank_engine)
        assert {c["name"] for c in inspector.get_columns("observations")} == set(
            Observation.__table__.columns.keys()
        )
        assert {c["name"] for c in inspector.get_columns("evidence")} == set(
            Evidence.__table__.columns.keys()
        )

    def test_the_immutability_trigger_is_in_the_created_database(self, blank_engine):
        """
        Created from the model, so the trigger rides along. This is the reason
        the DDL is not written out in the migration.
        """
        mig.upgrade(blank_engine)
        with blank_engine.connect() as conn:
            triggers = conn.execute(
                text(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='observations'"
                )
            ).fetchall()
        assert [row[0] for row in triggers] == ["observations_are_immutable"]

    def test_evidence_records_the_prompt_version_and_refuses_a_blank_one(self, blank_engine):
        mig.upgrade(blank_engine)
        with blank_engine.connect() as conn:
            ddl = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='evidence'")
            ).scalar_one()

        assert "prompt_version" in ddl
        assert "ck_evidence_prompt_version_present" in ddl
        assert "ck_evidence_direction" in ddl
        assert "ck_evidence_magnitude_range" in ddl
        assert "_evidence_observation_watch_version_uc" in ddl

    def test_observations_ddl_carries_the_hash_prefix_check(self, blank_engine):
        mig.upgrade(blank_engine)
        with blank_engine.connect() as conn:
            ddl = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='observations'")
            ).scalar_one()
        assert "ck_observations_hash_prefix" in ddl


class TestArticlesAreUntouched:
    def test_the_migration_does_not_change_the_articles_table(self, corpus_engine):
        """
        The 55,249-row corpus is not migrated, not rewritten, not dropped.

        Task 014's out-of-scope list says so by name, and the reason the tables
        coexist is in src/database/models.py.
        """
        with corpus_engine.connect() as conn:
            before_ddl = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'")
            ).scalar_one()
            before_rows = conn.execute(text("SELECT count(*) FROM articles")).scalar_one()

        mig.upgrade(corpus_engine)

        with corpus_engine.connect() as conn:
            after_ddl = conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name='articles'")
            ).scalar_one()
            after_rows = conn.execute(text("SELECT count(*) FROM articles")).scalar_one()

        assert after_ddl == before_ddl
        assert after_rows == before_rows == 1

    def test_the_downgrade_leaves_articles_alone_too(self, corpus_engine):
        mig.upgrade(corpus_engine)
        mig.downgrade(corpus_engine, confirmed=True)
        with corpus_engine.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM articles")).scalar_one() == 1


class TestDowngrade:
    def test_refuses_without_confirm(self, blank_engine):
        mig.upgrade(blank_engine)
        with pytest.raises(SystemExit) as exc:
            mig.downgrade(blank_engine)
        assert "--confirm" in str(exc.value)
        assert inspect(blank_engine).has_table("observations")

    def test_drops_both_with_confirm_in_dependency_order(self, blank_engine):
        mig.upgrade(blank_engine)
        assert mig.downgrade(blank_engine, confirmed=True) == ["evidence", "observations"]
        inspector = inspect(blank_engine)
        assert not inspector.has_table("observations")
        assert not inspector.has_table("evidence")

    def test_is_idempotent(self, blank_engine):
        mig.upgrade(blank_engine)
        mig.downgrade(blank_engine, confirmed=True)
        assert mig.downgrade(blank_engine, confirmed=True) == []


class TestCommandLine:
    def test_up_then_down_with_confirm(self, blank_engine, monkeypatch):
        monkeypatch.setattr(mig, "engine", blank_engine)
        assert mig.main([]) == 0
        assert inspect(blank_engine).has_table("observations")
        assert mig.main(["--down", "--confirm"]) == 0
        assert not inspect(blank_engine).has_table("observations")

    def test_down_without_confirm_exits_with_the_help(self, blank_engine, monkeypatch):
        monkeypatch.setattr(mig, "engine", blank_engine)
        mig.main([])
        with pytest.raises(SystemExit):
            mig.main(["--down"])
        assert inspect(blank_engine).has_table("observations")
