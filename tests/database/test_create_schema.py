"""
The bootstrap for a fresh database (2026-09-23, backlog task 033).
"""

from sqlalchemy import create_engine, inspect

from src.database.migrations import add_monitor_tables, create_schema
from src.database.models import Base


def _blank(tmp_path):
    return create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")


def test_a_fresh_database_gets_every_declared_table(tmp_path):
    engine = _blank(tmp_path)

    created = create_schema.upgrade(engine)

    assert set(created) == set(Base.metadata.tables)
    assert set(inspect(engine).get_table_names()) == set(Base.metadata.tables)


def test_running_it_again_creates_nothing(tmp_path):
    engine = _blank(tmp_path)
    create_schema.upgrade(engine)

    assert create_schema.upgrade(engine) == []


def test_it_creates_only_what_is_absent_and_the_additive_migrations_still_run(tmp_path):
    engine = _blank(tmp_path)
    add_monitor_tables.upgrade(engine)  # an older database with some tables

    created = create_schema.upgrade(engine)

    assert "routes" not in created
    assert {"rss_feeds", "articles", "observations", "watches"} <= set(created)
    assert add_monitor_tables.upgrade(engine) == []
