"""
Credentials: keychain only, lazy, and never defaulted.
"""

import pytest

from src.config.settings import settings
from src.estate import credentials


class TestRead:
    def test_a_stored_value_is_returned(self, memory_keyring):
        memory_keyring.store[(settings.keyring_service, credentials.ANTHROPIC)] = "sk-test"
        assert credentials.read(credentials.ANTHROPIC) == "sk-test"

    def test_a_missing_value_raises_naming_the_fix(self, memory_keyring):
        with pytest.raises(credentials.MissingCredential) as excinfo:
            credentials.read(credentials.ANTHROPIC)
        assert "estate auth set anthropic" in str(excinfo.value)

    def test_an_empty_stored_value_is_missing_not_empty(self, memory_keyring):
        memory_keyring.store[(settings.keyring_service, credentials.ANTHROPIC)] = ""
        with pytest.raises(credentials.MissingCredential):
            credentials.read(credentials.ANTHROPIC)

    def test_the_environment_is_not_consulted(self, memory_keyring, monkeypatch):
        """
        There is no ANTHROPIC_API_KEY fallback. A key in the environment and
        none in the keychain is a missing key.
        """
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        with pytest.raises(credentials.MissingCredential):
            credentials.read(credentials.ANTHROPIC)


class TestWriteAndDelete:
    def test_write_then_read_round_trips_stripped(self, memory_keyring):
        credentials.write(credentials.ANTHROPIC, "  sk-test \n")
        assert credentials.read(credentials.ANTHROPIC) == "sk-test"

    @pytest.mark.parametrize("blank", ["", "   ", "\n"])
    def test_a_blank_value_is_refused_not_stored(self, memory_keyring, blank):
        with pytest.raises(ValueError, match="blank"):
            credentials.write(credentials.ANTHROPIC, blank)
        assert not credentials.is_set(credentials.ANTHROPIC)

    def test_delete_removes_the_entry(self, memory_keyring):
        credentials.write(credentials.ANTHROPIC, "sk-test")
        credentials.delete(credentials.ANTHROPIC)
        assert not credentials.is_set(credentials.ANTHROPIC)

    def test_deleting_an_absent_entry_is_an_error(self, memory_keyring):
        with pytest.raises(credentials.MissingCredential):
            credentials.delete(credentials.ANTHROPIC)


def test_importing_the_module_touches_no_keychain(monkeypatch):
    """
    Lookups are lazy. Reloading the module with a keyring that explodes on
    contact must succeed; only read() may reach the backend.
    """
    import importlib

    import keyring

    def explode(*_args, **_kwargs):
        raise AssertionError("keychain touched at import time")

    monkeypatch.setattr(keyring, "get_password", explode)
    importlib.reload(credentials)
