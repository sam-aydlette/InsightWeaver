"""
Tests for the migration that drops the briefing tables (backlog task 012).

This migration destroys data that cannot be reconstructed from what remains, so
the tests are weighted towards the guards rather than the drop: that it refuses
without the flag, that it captures before it drops, and that it cannot touch
``articles``. The live database held 55,249 articles when this was written and
their fate is task 014's decision, not this migration's.

Every fixture builds its own SQLite file. Nothing here opens the real database.
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, text

from src.database.migrations import drop_briefing_tables as mig

# A miniature of the real pre-012 schema: two tables that must survive and
# three that must not, including one foreign key into a survivor.
_SCHEMA = [
    """
    CREATE TABLE rss_feeds (
        id INTEGER NOT NULL PRIMARY KEY,
        url VARCHAR(500) NOT NULL,
        name VARCHAR(200) NOT NULL
    )
    """,
    """
    CREATE TABLE articles (
        id INTEGER NOT NULL PRIMARY KEY,
        feed_id INTEGER,
        guid VARCHAR(500) NOT NULL,
        title VARCHAR(500),
        FOREIGN KEY(feed_id) REFERENCES rss_feeds (id)
    )
    """,
    """
    CREATE TABLE questions (
        id INTEGER NOT NULL PRIMARY KEY,
        text TEXT NOT NULL,
        status VARCHAR(20) NOT NULL,
        first_asked_at DATETIME
    )
    """,
    "CREATE INDEX idx_question_status ON questions (status)",
    """
    CREATE TABLE predictions (
        id INTEGER NOT NULL PRIMARY KEY,
        question_id INTEGER NOT NULL,
        observable_text TEXT NOT NULL,
        FOREIGN KEY(question_id) REFERENCES questions (id)
    )
    """,
    """
    CREATE TABLE narrative_frames (
        id INTEGER NOT NULL PRIMARY KEY,
        label VARCHAR(200) NOT NULL
    )
    """,
]


@pytest.fixture
def db(tmp_path):
    """A database at the pre-012 shape, with rows in every table."""
    engine = create_engine(f"sqlite:///{tmp_path / 'pre012.db'}")
    with engine.begin() as conn:
        for stmt in _SCHEMA:
            conn.execute(text(stmt))
        conn.execute(text("INSERT INTO rss_feeds (id, url, name) VALUES (1, 'u', 'Feed')"))
        conn.execute(
            text("INSERT INTO articles (id, feed_id, guid, title) VALUES (1, 1, 'g', 'T')")
        )
        conn.execute(
            text(
                "INSERT INTO questions (id, text, status, first_asked_at)"
                " VALUES (1, 'Does it slip?', 'open', :t)"
            ),
            {"t": datetime(2026, 8, 1)},
        )
        conn.execute(
            text(
                "INSERT INTO predictions (id, question_id, observable_text)"
                " VALUES (1, 1, 'it slips')"
            )
        )
        conn.execute(text("INSERT INTO narrative_frames (id, label) VALUES (1, 'hawk')"))
    yield engine
    engine.dispose()


def _tables(engine):
    return set(inspect(engine).get_table_names())


class TestItRefusesWithoutTheFlag:
    def test_upgrade_without_confirmation_raises_and_changes_nothing(self, db):
        before = _tables(db)

        with pytest.raises(SystemExit) as exc:
            mig.upgrade(db)

        assert "--confirm" in str(exc.value)
        assert _tables(db) == before

    def test_the_refusal_names_the_command_that_would_work(self, db):
        with pytest.raises(SystemExit) as exc:
            mig.upgrade(db, confirmed=False)

        assert "drop_briefing_tables --confirm" in str(exc.value)

    def test_there_is_no_env_var_that_enables_it(self, db, monkeypatch):
        """
        A migration this destructive must not be enableable by ambient config.
        CONFIRM/FORCE/YES are the names a CI runner is most likely to already
        have set, so their presence must still not be enough.
        """
        for name in ("CONFIRM", "FORCE", "YES", "DROP_BRIEFING_TABLES"):
            monkeypatch.setenv(name, "1")

        with pytest.raises(SystemExit):
            mig.upgrade(db)

        assert "questions" in _tables(db)


class TestItProtectsTheCorpus:
    def test_articles_and_rss_feeds_are_never_in_the_drop_list(self):
        assert not mig.PROTECTED_TABLES & set(mig.BRIEFING_TABLES)

    def test_articles_survives_the_drop_with_its_rows(self, db):
        mig.upgrade(db, confirmed=True)

        assert "articles" in _tables(db)
        with db.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM articles")).scalar() == 1
            assert conn.execute(text("SELECT count(*) FROM rss_feeds")).scalar() == 1

    def test_the_guard_fires_if_the_lists_ever_overlap(self, monkeypatch):
        """The protection is asserted at runtime, not left to the list above."""
        monkeypatch.setattr(mig, "BRIEFING_TABLES", ("questions", "articles"))

        with pytest.raises(AssertionError, match="articles"):
            mig.upgrade(confirmed=True)


class TestTheDrop:
    def test_it_drops_every_briefing_table_present(self, db):
        mig.upgrade(db, confirmed=True)

        assert _tables(db) == {"articles", "rss_feeds"}

    def test_it_reports_the_rows_it_destroyed(self, db):
        counts = mig.upgrade(db, confirmed=True)

        assert counts["questions"] == 1
        assert counts["predictions"] == 1
        assert counts["narrative_frames"] == 1

    def test_absent_tables_are_not_an_error(self, tmp_path):
        """A database that never had the briefing tables migrates cleanly."""
        engine = create_engine(f"sqlite:///{tmp_path / 'bare.db'}")
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE articles (id INTEGER PRIMARY KEY)"))

            assert mig.upgrade(engine, confirmed=True) == {}
            assert _tables(engine) == {"articles"}
        finally:
            engine.dispose()


class TestCapture:
    def test_it_writes_a_dump_before_dropping(self, db, tmp_path):
        out, counts = mig.capture(db, tmp_path / "cap.sql")
        body = out.read_text()

        assert "CREATE TABLE questions" in body
        assert "Does it slip?" in body
        assert counts["questions"] == 1

    def test_the_dump_escapes_quotes_rather_than_corrupting_the_sql(self, db, tmp_path):
        with db.begin() as conn:
            conn.execute(
                text("INSERT INTO questions (id, text, status) VALUES (2, :t, 'open')"),
                {"t": "O'Brien's rule"},
            )

        body = mig.capture(db, tmp_path / "quotes.sql")[0].read_text()

        assert "O''Brien''s rule" in body

    def test_upgrade_leaves_a_dump_next_to_the_database(self, db, tmp_path):
        mig.upgrade(db, confirmed=True)

        dumps = list(tmp_path.glob("*.briefing-tables-*.sql"))
        assert len(dumps) == 1
        assert "CREATE TABLE questions" in dumps[0].read_text()


class TestReversibility:
    def test_downgrade_recreates_the_schema_empty(self, db, tmp_path):
        dump = mig.capture(db, tmp_path / "d.sql")[0]
        mig.upgrade(db, confirmed=True)
        assert "questions" not in _tables(db)

        mig.downgrade(db, dump)

        assert {"questions", "predictions", "narrative_frames"} <= _tables(db)
        with db.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM questions")).scalar() == 0

    def test_downgrade_without_a_dump_refuses_rather_than_guessing(self, db):
        with pytest.raises(SystemExit, match="capture file"):
            mig.downgrade(db)

    def test_restore_brings_the_rows_back(self, db, tmp_path):
        """
        The only path back to the data. Deliberately a separate verb from
        downgrade, so "reverse the migration" never silently means "reinstate
        the deleted product's data".
        """
        dump = mig.capture(db, tmp_path / "r.sql")[0]
        mig.upgrade(db, confirmed=True)

        mig.restore(db, dump)

        with db.connect() as conn:
            assert conn.execute(text("SELECT text FROM questions")).scalar() == "Does it slip?"
            assert conn.execute(text("SELECT count(*) FROM predictions")).scalar() == 1


class TestDumpPath:
    def test_it_lands_beside_the_sqlite_file_not_in_the_repo(self, tmp_path):
        path = mig.dump_path(f"sqlite:///{tmp_path / 'x.db'}")

        assert path.parent == tmp_path
        assert path.name.startswith("x.db.briefing-tables-")
