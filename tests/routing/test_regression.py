"""
The routing gate: whole words route, look-alikes do not, and nothing else does.

A routing predicate that is too loose does not fail, it bills: every routed
pair becomes a model call. So the property is pinned with a number rather than
a dashboard. A thousand synthetic observations against five watches carry
exactly twenty planted whole-word matches and one hundred planted look-alikes
-- mostly the trigger term inside a longer word, in shouted and mixed case,
plus a few whole-word case variants of a shouted acronym -- and exactly the
twenty planted items must route, checked by identity and not by count.

Verified on 2026-09-22 (backlog task 028) by emptying ``LEFT_BOUNDARY`` and
``RIGHT_BOUNDARY`` in ``src/matching/entity_matcher.py`` and running this
file: it failed with 61 routed. Task 010 found a boundary
test that passed for the wrong reason -- shouted terms were rejected by
case-sensitivity before the anchors were consulted -- which is why the
look-alikes here include ``PRECISA`` and ``COMBAT`` in capitals, which only
the anchors reject, and not only ``precisa``.
"""

from datetime import date, datetime

from src.database.models import Observation, Route, Watch
from src.routing import route
from src.sources.base import RawItem
from src.sources.store import ensure_source, store_items

TODAY = date(2026, 9, 1)
SINCE = datetime(2026, 8, 1)

WATCHES = {
    "cisa-directive": ("CISA", "BOD"),
    "nist-baseline": ("NIST",),
    "fedramp-scope": ("FedRAMP", "continuous monitoring"),
    "omb-memo": ("OMB",),
    "hiring": ("compliance engineer",),
}

# One planted match per (watch, term), whole words, twenty in all.
PLANTED = [
    "CISA issued a directive today.",
    "The BOD requires patching within 30 days.",
    "CISA and BOD both appear here.",
    "A directive from CISA, again.",
    "NIST published the revision.",
    "The baseline is NIST's.",
    "NIST SP 800-53 changed.",
    "A NIST comment period opened.",
    "FedRAMP guidance was updated.",
    "Continuous monitoring scope grew.",
    "FedRAMP and continuous monitoring together.",
    "fedramp in lower case still counts.",
    "OMB released a memo.",
    "The OMB memorandum M-26-01.",
    "OMB, in a memo, said so.",
    "OMB guidance again.",
    "Hiring a compliance engineer.",
    "The compliance engineer role is open.",
    "A senior compliance engineer left.",
    "Compliance Engineer, capitalised, counts.",
]
assert len(PLANTED) == 20

# Look-alikes, in two kinds. The lower-case ones (``precisa``, ``combat``) are
# rejected by the case rule before the anchors are consulted, which is the
# trap task 010 found. The SHOUTED ones (``PRECISA``, ``COMBAT``, ``BODY``)
# contain the acronym exactly and are rejected by the anchors alone; without
# them, they route. The mixed-case terms are case-insensitive, so
# ``FedRAMPed`` and ``noncompliance engineering`` also rest on the anchors.
LOOKALIKES = [
    "precisa",
    "PRECISA",
    "Cisak said",
    "cisa lower is not the agency",
    "the body politic",
    "THE BODY POLITIC",
    "bodice",
    "administration",
    "the minister spoke",
    "NISTY WEATHER",
    "communist",
    "FedRAMPed through",
    "combat",
    "COMBAT READINESS",
    "OMBUDSMAN",
    "bombing",
    "thrombosis",
    "compliance engineers' union",
    "noncompliance engineering",
]


def _corpus(session):
    source = ensure_source(session, "Synthetic", "https://example.org/synthetic", "misc")
    items = []
    n = 0
    for text in PLANTED:
        items.append(_item(n, text))
        n += 1
    for i in range(100):
        items.append(_item(n, LOOKALIKES[i % len(LOOKALIKES)] + f" ({i})"))
        n += 1
    while n < 1000:
        items.append(_item(n, f"Filler item {n} about the county fair and {n * 31} pies."))
        n += 1
    store_items(session, source, items)
    session.flush()


def _item(n: int, text: str) -> RawItem:
    return RawItem(
        guid=f"s{n}",
        url=f"https://example.org/s{n}",
        title=text,
        normalized_content=f"{text} Body of item {n}.",
        published_date=datetime(2026, 8, 20),
    )


def _watches(session):
    for watch_id, terms in WATCHES.items():
        session.add(
            Watch(
                id=watch_id,
                claim=f"{watch_id} claim",
                belief=0.5,
                decision_key="d",
                so_what="because",
                triggers=[{"terms": list(terms)}],
                expires=date(2027, 1, 1),
                staleness_alert_days=30,
            )
        )
    session.flush()


def test_exactly_the_planted_whole_word_matches_route(test_session):
    _watches(test_session)
    _corpus(test_session)

    report = route(test_session, since=SINCE, today=TODAY)

    assert report.observations == 1000
    assert report.routed == 20
    planted_hashes = {
        h
        for h, payload in test_session.query(Observation.content_hash, Observation.payload)
        if payload["guid"] in {f"s{n}" for n in range(len(PLANTED))}
    }
    routed_hashes = {h for (h,) in test_session.query(Route.observation_hash)}
    assert routed_hashes == planted_hashes
    assert {w.watch_id: w.total for w in report.watches} == {
        "cisa-directive": 4,
        "nist-baseline": 4,
        "fedramp-scope": 4,
        "omb-memo": 4,
        "hiring": 4,
    }
