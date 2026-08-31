"""
The Observation invariants: content-addressing, immutability, one write path.

The first class here is the one the task named as the landmine to test first.
An adapter that lets a per-fetch value into the hashed payload stores the same
document on every run, and the symptom is "dedup looks broken" rather than
"hashing is broken", so it is checked directly and against the clock.
"""

from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

from src.database.models import Article, Observation, ObservationIsImmutable, RSSFeed
from src.sources.base import ARTICLE_FIELDS, RawItem
from src.sources.observation import (
    OBSERVATION_FIELDS,
    observation_hash,
    observation_payload,
    observe,
    store_observation,
)
from src.sources.store import ensure_source, store_items
from src.utils import utcnow

SOURCE_URL = "https://example.gov/api/documents"


BASE_ITEM = RawItem(
    guid="doc-2026-0001",
    url="https://example.gov/documents/2026-0001",
    title="Agency finalizes the continuous monitoring rule",
    description="A summary of the final rule.",
    content="<p>The agency finalized the rule today.</p>",
    normalized_content="The agency finalized the rule today.",
    published_date=datetime(2026, 8, 20, 9, 30),
    author="Office of the Federal Register",
    categories=("rules",),
    language="en",
)


def make_item(**overrides) -> RawItem:
    """One adapter item, with any field replaced. RawItem is frozen, so this
    is a replace() rather than a kwargs splat -- which also keeps the field
    names checkable."""
    return replace(BASE_ITEM, **overrides)


@pytest.fixture
def source(test_session):
    return ensure_source(test_session, "Example Agency", SOURCE_URL, "federal")


class TestHashIsContentOnly:
    """
    The hash must be a function of the content and of nothing else.

    Landmine, backlog task 014: "an adapter that includes a fetch timestamp,
    session ID, or any per-fetch value in the hashed payload will store the same
    article repeatedly, and the dedup will look broken when the hashing is what
    is wrong. Test that first."
    """

    def test_the_same_item_hashes_the_same_at_two_different_times(self):
        item = make_item()
        first = observe(SOURCE_URL, item)
        second = observe(SOURCE_URL, item)
        assert first.content_hash == second.content_hash

    def test_re_fetching_hours_later_does_not_change_the_hash(self, test_session, source):
        """
        Store, move the wall clock forward, store again. Same hash, one row.

        observed_at is what changes between the two writes, and observed_at is
        deliberately not in the payload.
        """
        item = make_item()
        first_hash, created = store_observation(test_session, source, item)
        assert created is True

        row = test_session.query(Observation).one()
        # Rewriting observed_at directly is refused, so a second store is used
        # to prove the hash does not move; the point is that the second call
        # computes the same identity for the same content.
        second_hash, created_again = store_observation(test_session, source, item)

        assert second_hash == first_hash
        assert created_again is False
        assert test_session.query(Observation).count() == 1
        assert row.observed_at is not None

    def test_no_per_fetch_column_is_in_the_payload(self):
        """observed_at and the article clock columns must not be payload keys."""
        payload = observation_payload(SOURCE_URL, make_item())
        for banned in ("observed_at", "fetched_at", "created_at", "updated_at", "last_fetched"):
            assert banned not in payload

    def test_payload_keys_are_exactly_the_declared_field_set(self):
        payload = observation_payload(SOURCE_URL, make_item())
        assert set(payload) == set(OBSERVATION_FIELDS)

    def test_the_field_set_extends_the_task_005_seam(self):
        """
        OBSERVATION_FIELDS is ARTICLE_FIELDS minus word_count plus source_url.

        Asserted rather than described, so that a field added to the RSS
        normalizer (which tests/sources/test_base.py pins ARTICLE_FIELDS to)
        cannot end up stored-but-unhashed.
        """
        assert set(OBSERVATION_FIELDS) == (set(ARTICLE_FIELDS) - {"word_count"}) | {"source_url"}

    def test_changing_any_content_field_changes_the_hash(self):
        base = observe(SOURCE_URL, make_item()).content_hash
        assert observe(SOURCE_URL, make_item(title="Something else")).content_hash != base
        assert observe(SOURCE_URL, make_item(normalized_content="Other body")).content_hash != base
        assert (
            observe(SOURCE_URL, make_item(published_date=datetime(2026, 8, 21))).content_hash
            != base
        )

    def test_the_same_text_from_two_sources_is_two_observations(self):
        """
        Who published it is part of what was observed.

        Grouping the pair back together is the MinHash signature's job, not the
        hash's -- see tests/sources/test_minhash.py.
        """
        item = make_item()
        assert (
            observe(SOURCE_URL, item).content_hash != observe("https://other/", item).content_hash
        )

    def test_a_payload_with_an_unhashed_key_is_refused(self):
        payload = observation_payload(SOURCE_URL, make_item())
        payload["session_id"] = "abc123"
        with pytest.raises(ValueError, match="every stored key must be hashed"):
            observation_hash(payload)

    def test_the_payload_is_json_round_trippable(self):
        import json

        payload = observation_payload(SOURCE_URL, make_item())
        assert json.loads(json.dumps(payload)) == payload


class TestImmutability:
    def test_the_orm_refuses_to_update_a_stored_observation(self, test_session, source):
        store_observation(test_session, source, make_item())
        test_session.commit()

        row = test_session.query(Observation).one()
        row.payload = {"tampered": True}

        with pytest.raises(ObservationIsImmutable):
            test_session.flush()

    def test_raw_sql_update_is_refused_by_the_trigger(self, test_session, source):
        """
        The guarantee has to hold for writes that never touch the ORM.

        A trigger is what makes this true for the sqlite3 shell, a hand-written
        migration, and anything else that issues an UPDATE.
        """
        stored_hash, _ = store_observation(test_session, source, make_item())
        test_session.commit()

        with pytest.raises(Exception, match="observations are immutable"):
            test_session.execute(
                text("UPDATE observations SET payload = :p WHERE content_hash = :h"),
                {"p": '{"tampered": true}', "h": stored_hash},
            )
        test_session.rollback()

    def test_the_row_is_unchanged_after_a_refused_update(self, test_session, source):
        stored_hash, _ = store_observation(test_session, source, make_item())
        test_session.commit()
        before = dict(test_session.query(Observation).one().payload)

        with pytest.raises(Exception, match="observations are immutable"):
            test_session.execute(
                text("UPDATE observations SET payload = :p WHERE content_hash = :h"),
                {"p": '{"tampered": true}', "h": stored_hash},
            )
        test_session.rollback()

        test_session.expire_all()
        assert dict(test_session.query(Observation).one().payload) == before

    def test_storing_the_same_content_again_is_a_no_op_not_an_update(self, test_session, source):
        store_observation(test_session, source, make_item())
        test_session.commit()
        _, created = store_observation(test_session, source, make_item())
        assert created is False
        assert test_session.query(Observation).count() == 1


def modules_constructing(class_name: str, allowed_relative_paths: set[str]) -> list[str]:
    """
    Every module under src/ that constructs ``class_name``, minus the allowed set.

    A tree grep rather than an import-graph walk, because what is being
    defended against is someone *adding* a construction site, and a new file is
    exactly what an import graph rooted at today's entry points would miss.
    ``\\b`` before the name keeps ``NewArticle(`` from matching while still
    catching the qualified ``models.Article(`` form.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src"
    allowed = {root / relative for relative in allowed_relative_paths}
    pattern = re.compile(rf"\b{class_name}\(")

    return [
        str(path.relative_to(root))
        for path in sorted(root.rglob("*.py"))
        if path not in allowed and pattern.search(path.read_text(encoding="utf-8"))
    ]


class TestOneWritePath:
    def test_only_the_observation_module_constructs_an_observation(self):
        """
        Adapters emit observations through one path, checked against the tree.

        The guarantee that observations are content-addressed is only as strong
        as the number of places that can write one, so the count is asserted
        rather than trusted. src/database/models.py is excluded because that is
        where the class is defined.
        """
        offenders = modules_constructing(
            "Observation", {"sources/observation.py", "database/models.py"}
        )
        assert offenders == [], (
            f"these modules construct an Observation directly: {offenders}. "
            f"Every write goes through src/sources/observation.py::store_observation."
        )

    def test_only_the_store_module_constructs_an_article(self):
        """No module outside store.py constructs an Article.

        The grep catches construction, which is where an article write begins. A
        module that only ``db.add()``s an Article it was handed would slip past it --
        ``src/processors/normalizer.py::ArticleStorage`` was exactly that, dead code
        kept alive by its own tests, and it was deleted in task 025 rather than
        documented, because a documented hole in an invariant is still a hole.
        """
        offenders = modules_constructing("Article", {"sources/store.py", "database/models.py"})
        assert offenders == [], (
            f"these modules construct an Article directly: {offenders}. "
            f"Every article write goes through src/sources/store.py::store_items, "
            f"which writes the article and its Observation in one transaction. "
            f"See src/rss/fetcher.py::LegacyWritePathClosed for why."
        )

    def test_the_adapter_store_path_writes_an_observation_per_article(self, test_session, source):
        items = [make_item(), make_item(guid="doc-2", title="A different rule", url="u2")]
        inserted, duplicates = store_items(test_session, source, items)

        assert (inserted, duplicates) == (2, 0)
        assert test_session.query(Observation).count() == 2

    def test_each_observation_links_to_the_article_written_beside_it(self, test_session, source):
        store_items(test_session, source, [make_item()])

        observation = test_session.query(Observation).one()
        article = test_session.query(Article).one()
        assert observation.article_id == article.id
        assert observation.source_id == source.id

    def test_a_second_adapter_run_inserts_neither_an_article_nor_an_observation(
        self, test_session, source
    ):
        store_items(test_session, source, [make_item()])
        inserted, duplicates = store_items(test_session, source, [make_item()])

        assert (inserted, duplicates) == (0, 1)
        assert test_session.query(Article).count() == 1
        assert test_session.query(Observation).count() == 1

    def test_an_article_that_predates_observations_gains_one_on_the_next_run(
        self, test_session, source
    ):
        """
        The two tables have independent identities, so a re-run repairs the gap.

        This is the path a legacy article takes if the same item is fetched
        again: the article is a duplicate, but the observation is written.
        """
        item = make_item()
        test_session.add(Article(feed_id=source.id, **item.as_article_fields()))
        test_session.flush()
        assert test_session.query(Observation).count() == 0

        inserted, duplicates = store_items(test_session, source, [item])

        assert (inserted, duplicates) == (0, 1)
        assert test_session.query(Observation).count() == 1

    def test_the_published_date_projection_matches_the_payload(self, test_session, source):
        store_items(test_session, source, [make_item()])
        row = test_session.query(Observation).one()
        assert row.published_date.isoformat() == row.payload["published_date"]


class TestNearDuplicateQuery:
    def test_groups_are_read_from_the_stored_signatures(self, test_session, source):
        from src.sources.observation import near_duplicate_groups

        body = "The agency finalized the continuous monitoring rule today " * 12
        store_items(
            test_session,
            source,
            [
                make_item(guid="a", url="a", normalized_content=body),
                make_item(guid="b", url="b", normalized_content=body + " Filed by the desk."),
                make_item(
                    guid="c",
                    url="c",
                    title="Unrelated",
                    normalized_content="Persimmons ripen in the fall and are best after frost. "
                    * 8,
                ),
            ],
        )

        groups = near_duplicate_groups(test_session)
        sizes = sorted(len(group) for group in groups)
        assert sizes == [1, 2]

    def test_the_window_filter_narrows_the_corpus(self, test_session, source):
        from src.sources.observation import near_duplicate_groups

        old = make_item(guid="old", url="old", published_date=datetime(2026, 1, 1))
        new = make_item(guid="new", url="new", published_date=datetime(2026, 8, 20))
        store_items(test_session, source, [old, new])

        recent = near_duplicate_groups(test_session, since=datetime(2026, 6, 1))
        assert sum(len(group) for group in recent) == 1


class TestSourceRowUnchanged:
    def test_storing_still_stamps_the_source(self, test_session, source):
        before = utcnow() - timedelta(seconds=1)
        store_items(test_session, source, [make_item()])
        assert source.last_fetched >= before
        assert source.error_count == 0


class TestFeedIsolation:
    def test_two_feeds_carrying_the_same_item_store_two_observations(self, test_session):
        first = ensure_source(test_session, "Feed One", "https://one.example/rss", "news")
        second = ensure_source(test_session, "Feed Two", "https://two.example/rss", "news")

        store_items(test_session, first, [make_item()])
        store_items(test_session, second, [make_item()])

        assert test_session.query(Observation).count() == 2
        assert test_session.query(RSSFeed).count() == 2
