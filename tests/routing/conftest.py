"""
Shared fixtures for the Tier 1 routing tests.

Observations here are built through the real write path
(``src.sources.observation.store_observation``), not by inserting rows. A test
corpus assembled by hand is a corpus whose hashes, minhash signatures and
payload shape are whatever the test author assumed, and the routing code reads
all three.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from src.database.models import RSSFeed
from src.sources.base import RawItem
from src.sources.observation import store_observation

TODAY = date(2026, 8, 31)


class WatchRow:
    """
    The three attributes :func:`src.routing.router.route` reads off a watch.

    Deliberately not a :class:`src.database.models.Watch`: the router must not
    quietly grow a dependency on a column it was not given, and this fails loudly
    if it does.
    """

    def __init__(self, watch_id: str, triggers, expires: date = date(2027, 1, 1)):
        self.id = watch_id
        self.triggers = triggers
        self.expires = expires


@pytest.fixture
def feed(test_session):
    """One stored feed, so observations have a source to belong to."""

    def _feed(name="FedScoop", url=None):
        row = RSSFeed(
            url=url or f"https://example.test/{name.lower().replace(' ', '-')}", name=name
        )
        test_session.add(row)
        test_session.flush()
        return row

    return _feed


@pytest.fixture
def observe(test_session, feed):
    """
    Store one observation with the given title and body. Returns its hash.

    ``observed_at`` is left to the insert default. It cannot be set afterwards:
    observations are immutable, and both the ORM guard and a SQLite trigger
    refuse the UPDATE. Tests here therefore assert on *how many* of the last N
    were considered rather than on which -- ``utcnow()`` has microsecond
    resolution, so insertion order and ``observed_at`` order agree, but that is
    a property of the clock and not something a test should lean on.
    """
    default_feed: list[RSSFeed] = []
    counter = [0]

    def _observe(title, body="", *, source=None, published=None):
        if source is None:
            if not default_feed:
                default_feed.append(feed())
            source = default_feed[0]
        counter[0] += 1
        item = RawItem(
            guid=f"guid-{counter[0]}",
            url=f"https://example.test/item/{counter[0]}",
            title=title,
            normalized_content=body,
            published_date=published or datetime(2026, 8, 20) + timedelta(minutes=counter[0]),
        )
        content_hash, _ = store_observation(test_session, source, item)
        return content_hash

    return _observe
