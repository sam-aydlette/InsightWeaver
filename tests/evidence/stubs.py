"""
Stub adjudicators and corpus builders for the replay harness.

**Nothing here makes an LLM call and nothing here needs an API key.** The whole
point of the harness is that adjudication is pluggable and that the replay
machinery can be exercised without the stochastic part; a suite that needed a
key to test the reproducibility of a replay would be testing the wrong thing.
The stubs below are ordinary Python objects with a ``prompt_version`` and an
``adjudicate`` method, which is the entire contract.

This is a plain module rather than a conftest so that both tests/evidence/ and
tests/cli/test_replay_cli.py can build the same corpus from one definition.
pytest refuses to register one conftest under two names, and a second copy of
the corpus would let the two suites drift.
"""

from datetime import date, datetime

from src.database.models import Watch
from src.evidence import Verdict
from src.sources.base import RawItem
from src.sources.store import ensure_source, store_items

SOURCE_URL = "https://example.gov/api/documents"


class KeywordAdjudicator:
    """
    A deterministic stand-in: emits a verdict when a watch's terms appear.

    This is a *test* adjudicator and lives in the test tree on purpose. It is
    not shipped, because a shipped rule that guessed a direction from a keyword
    would write fabricated judgements into the table whose reason for existing
    is to make judgements reviewable. What it does have is the property under
    test: the same inputs give the same outputs, every time.
    """

    def __init__(self, prompt_version: str, direction: str = "supports", scale: float = 1.0):
        self.prompt_version = prompt_version
        self.direction = direction
        self.scale = scale

    def adjudicate(self, observation, watches):
        verdicts = []
        haystack = f"{observation.title} {observation.text}".lower()
        for watch in sorted(watches, key=lambda w: w.id):
            terms = [
                term.lower()
                for clause in (watch.triggers or [])
                for term in clause.get("terms", [])
            ]
            hits = [term for term in terms if term in haystack]
            if not hits:
                continue
            verdicts.append(
                Verdict(
                    watch_id=watch.id,
                    direction=self.direction,
                    magnitude=round(min(1.0, self.scale * len(hits) / max(1, len(terms))), 4),
                    rationale=f"matched {len(hits)} of {len(terms)} term(s)",
                )
            )
        return verdicts


class CountingAdjudicator:
    """Not deterministic: its magnitude drifts with every call. Used to prove
    the harness notices, rather than assuming nobody will ever write one."""

    def __init__(self, prompt_version: str):
        self.prompt_version = prompt_version
        self.calls = 0

    def adjudicate(self, observation, watches):  # noqa: ARG002
        self.calls += 1
        if not watches:
            return []
        return [
            Verdict(
                watch_id=sorted(w.id for w in watches)[0],
                direction="supports",
                magnitude=min(1.0, self.calls / 10),
            )
        ]


def make_v1() -> KeywordAdjudicator:
    """Factory used by the CLI tests via --adjudicator."""
    return KeywordAdjudicator("v1")


def make_v2() -> KeywordAdjudicator:
    """A 'changed prompt': same matching, opposite direction, half magnitude."""
    return KeywordAdjudicator("v2", direction="contradicts", scale=0.5)


WATCH_ROWS = (
    {
        "id": "conmon-scope-expands",
        "claim": "Continuous monitoring scope expands before the assessment window.",
        "belief": 0.35,
        "decision_key": "renew-authorization",
        "so_what": "Scope expansion moves renewal past the point where lapsing is cheaper.",
        "triggers": [{"terms": ["continuous monitoring", "conmon"]}],
        "expires": date(2027, 3, 31),
        "staleness_alert_days": 30,
    },
    {
        "id": "hiring-market-tightens",
        "claim": "Compliance engineers get harder to hire.",
        "belief": 0.5,
        "decision_key": "hire-engineer",
        "so_what": "A tighter market moves the hiring decision forward.",
        "triggers": [{"terms": ["compliance engineer"]}],
        "expires": date(2026, 12, 15),
        "staleness_alert_days": 45,
    },
)

CORPUS_ITEMS = (
    RawItem(
        guid="doc-1",
        url="https://example.gov/1",
        title="Agency expands continuous monitoring scope",
        normalized_content="The agency expanded continuous monitoring requirements today.",
        published_date=datetime(2026, 8, 20, 9, 0),
    ),
    RawItem(
        guid="doc-2",
        url="https://example.gov/2",
        title="Hiring notice",
        normalized_content="The office is seeking a compliance engineer for the program.",
        published_date=datetime(2026, 8, 21, 9, 0),
    ),
    RawItem(
        guid="doc-3",
        url="https://example.gov/3",
        title="Persimmons ripen after the first frost",
        normalized_content="Fall fruit guidance for the county extension office.",
        published_date=datetime(2026, 8, 22, 9, 0),
    ),
    RawItem(
        guid="doc-4",
        url="https://example.gov/4",
        title="Notice of meeting",
        normalized_content="A routine notice with no bearing on any watch.",
        published_date=datetime(2026, 8, 23, 9, 0),
    ),
)


def add_watches(session):
    """Two watches whose trigger terms two of the four corpus items match."""
    rows = [Watch(**fields) for fields in WATCH_ROWS]
    session.add_all(rows)
    session.flush()
    return rows


def add_observations(session):
    """Four observations, written through the one adapter store path."""
    source = ensure_source(session, "Example Agency", SOURCE_URL, "federal")
    store_items(session, source, list(CORPUS_ITEMS))
    session.flush()
    return source
