"""
Shared test fixtures for all InsightWeaver tests
"""

import keyring
import keyring.backend
import pytest
from keyring.errors import PasswordDeleteError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base


class MemoryKeyring(keyring.backend.KeyringBackend):
    """A keyring that forgets everything when the test ends. See memory_keyring."""

    priority = 1  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.store.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.store[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self.store:
            raise PasswordDeleteError(f"{service}/{username} is not stored")
        del self.store[(service, username)]


@pytest.fixture
def memory_keyring():
    """
    An in-memory keyring backend for the duration of one test.

    Shared here rather than in tests/config/ because the model client in
    tests/llm/ reads the keychain too. Every test that touches credentials uses
    it, so the suite never reads or writes the operator's real keychain and runs
    identically on CI, which has none. (2026-09-22, backlog task 026.)
    """
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(previous)


@pytest.fixture
def test_engine(tmp_path):
    """Create temporary SQLite database with all tables."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def test_session(test_engine):
    """Database session for tests."""
    Session = sessionmaker(bind=test_engine)
    session = Session()
    yield session
    session.close()
