"""
Tier 1 makes no model call, proved by making one impossible.

The import of ``src.llm`` and of the ``anthropic`` package is blocked for the
duration of the test with a meta-path finder that raises, every already-loaded
copy is evicted first, and the full routing path is then driven from a fresh
import. A routing tier that reached for a model, even lazily, would fail here.
"""

import importlib
import sys
from datetime import date, datetime

import pytest

from ..evidence.stubs import add_observations, add_watches

BLOCKED = ("src.llm", "anthropic")


class _Blocker:
    def find_spec(self, name, path=None, target=None):
        if name in BLOCKED or any(name.startswith(prefix + ".") for prefix in BLOCKED):
            raise ImportError(f"{name} is blocked: Tier 1 must not import it")
        return None


@pytest.fixture
def no_llm(monkeypatch):
    for name in list(sys.modules):
        if name in BLOCKED or any(name.startswith(prefix + ".") for prefix in BLOCKED):
            monkeypatch.delitem(sys.modules, name, raising=False)
    for name in list(sys.modules):
        if name.startswith("src.routing"):
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "meta_path", [_Blocker(), *sys.meta_path])
    yield


def test_the_full_routing_path_runs_with_the_model_client_unimportable(no_llm, test_session):
    with pytest.raises(ImportError):
        importlib.import_module("src.llm")

    routing = importlib.import_module("src.routing")
    add_watches(test_session)
    add_observations(test_session)

    report = routing.route(test_session, since=datetime(2026, 8, 1), today=date(2026, 9, 1))

    assert report.routed == 2
    assert not any(name.startswith("src.llm") for name in sys.modules)
