"""
Fixtures for the Position and Watch loaders.

Every test writes its own YAML into ``tmp_path``. Nothing here reads the
operator's real Position -- it is not in this repository and must not be
required to run the suite.

``TODAY`` is frozen rather than ``date.today()``. The expiry rules are
date-relative, so a suite that used the wall clock would start failing on the
day the fixture dates went past, which is the kind of test failure that teaches
nothing.
"""

from datetime import date
from pathlib import Path

import pytest
import yaml

from src.position import load_position

TODAY = date(2026, 9, 1)


def _position_doc() -> dict:
    return {
        "version": 1,
        "reviewed": date(2026, 8, 31),
        "decisions": [
            {
                "key": "renew-authorization",
                "name": "Renew the authorization or let it lapse",
                "deadline": date(2027, 3, 31),
                "stake": "Two engineer-quarters against 40% of federal revenue.",
            },
            {
                "key": "hire-engineer",
                "name": "Hire a compliance engineer",
                "deadline": date(2026, 12, 15),
                "stake": "A missed deadline nobody owns.",
            },
        ],
    }


def _watch_doc(**overrides) -> dict:
    """One valid watch, with any field replaced. ``None`` removes the field."""
    watch = {
        "id": "conmon-scope-expands",
        "claim": "Continuous monitoring scope expands before the assessment window.",
        "belief": 0.35,
        "so_what": {
            "decision": "renew-authorization",
            "because": "Scope expansion moves renewal past the point where lapsing is cheaper.",
        },
        "triggers": [
            {"entities": ["FedRAMP PMO"], "terms": ["continuous monitoring", "ConMon"]},
            {"sources": ["Federal Register"], "terms": ["FedRAMP"]},
        ],
        "expires": date(2027, 3, 31),
        "staleness_alert_days": 30,
    }
    for key, value in overrides.items():
        if value is _ABSENT:
            watch.pop(key, None)
        else:
            watch[key] = value
    return watch


class _Absent:
    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<absent>"


_ABSENT = _Absent()
ABSENT = _ABSENT


@pytest.fixture
def write_yaml(tmp_path):
    """Write a document (or raw text) to ``tmp_path`` and hand back the path."""

    def _write(name: str, document) -> Path:
        target = tmp_path / name
        if isinstance(document, str):
            target.write_text(document, encoding="utf-8")
        else:
            target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        return target

    return _write


@pytest.fixture
def position_doc():
    return _position_doc()


@pytest.fixture
def watch_doc():
    return _watch_doc


@pytest.fixture
def position(write_yaml, position_doc):
    """A loaded, valid Position with two decisions."""
    return load_position(write_yaml("position.yaml", position_doc), today=TODAY)


@pytest.fixture
def watches_file(write_yaml):
    """Writes a watches file from a list of watch dicts."""

    def _write(*watches) -> Path:
        return write_yaml("watches.yaml", {"version": 1, "watches": list(watches)})

    return _write
