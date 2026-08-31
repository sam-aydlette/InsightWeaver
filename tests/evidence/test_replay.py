"""
The replay proof: deterministic, diffable, and writes nothing without --commit.

Backlog task 014's central acceptance criterion is that a replay is
reproducible. It is worthless otherwise, and -- the task's own warning -- it
breaks in the direction of looking fine, so the reproducibility is asserted
directly here on the rows and again in tests/cli/test_replay_cli.py on the
printed bytes.
"""

import pytest

from src.database.models import Evidence
from src.evidence import (
    NULL_PROMPT_VERSION,
    NondeterministicReplay,
    NullAdjudicator,
    ObservationView,
    UnknownPromptVersion,
    Verdict,
    commit,
    diff,
    format_diff,
    known_prompt_versions,
    load_adjudicator,
    rebuild,
    register,
    resolve,
    stored_evidence,
)

from .stubs import CountingAdjudicator, KeywordAdjudicator


class TestReplayIsDeterministic:
    def test_the_same_prompt_version_twice_produces_identical_rows(
        self, test_session, watches, observations
    ):
        first = rebuild(test_session, KeywordAdjudicator("v1"))
        second = rebuild(test_session, KeywordAdjudicator("v1"))

        assert first == second
        assert first, "the fixture corpus should produce some evidence"

    def test_a_fresh_adjudicator_instance_gives_the_same_answer(
        self, test_session, watches, observations
    ):
        """Determinism must be a property of the version, not of one object."""
        assert rebuild(test_session, KeywordAdjudicator("v1")) == rebuild(
            test_session, KeywordAdjudicator("v1")
        )

    def test_the_diff_of_a_version_against_itself_is_empty(
        self, test_session, watches, observations
    ):
        replayed = rebuild(test_session, KeywordAdjudicator("v1"))
        commit(test_session, "v1", replayed)

        again = rebuild(test_session, KeywordAdjudicator("v1"))
        assert diff(again, stored_evidence(test_session, "v1")).is_empty

    def test_row_order_is_stable_and_sorted(self, test_session, watches, observations):
        rows = rebuild(test_session, KeywordAdjudicator("v1"))
        assert rows == sorted(rows)
        assert [r.key for r in rows] == sorted(r.key for r in rows)

    def test_the_formatted_diff_is_byte_identical_across_runs(
        self, test_session, watches, observations
    ):
        def render():
            replayed = rebuild(test_session, KeywordAdjudicator("v1"))
            result = diff(replayed, stored_evidence(test_session, "v1"))
            return format_diff(result, "v1", "v1", 4, 2)

        assert render() == render()


class TestAChangedPromptVersionShowsADiff:
    def test_a_changed_version_produces_a_visible_diff(self, test_session, watches, observations):
        commit(test_session, "v1", rebuild(test_session, KeywordAdjudicator("v1")))

        v2 = rebuild(test_session, KeywordAdjudicator("v2", direction="contradicts", scale=0.5))
        result = diff(v2, stored_evidence(test_session, "v1"))

        assert not result.is_empty
        assert result.changed, "same keys, different verdicts, so these are changes"
        assert not result.added and not result.removed
        for old, new in result.changed:
            assert old.direction == "supports"
            assert new.direction == "contradicts"

    def test_a_version_that_finds_nothing_shows_every_row_as_removed(
        self, test_session, watches, observations
    ):
        stored = rebuild(test_session, KeywordAdjudicator("v1"))
        commit(test_session, "v1", stored)

        result = diff(rebuild(test_session, NullAdjudicator()), stored_evidence(test_session, "v1"))
        assert len(result.removed) == len(stored)
        assert not result.added and not result.changed

    def test_the_diff_text_names_what_moved(self, test_session, watches, observations):
        commit(test_session, "v1", rebuild(test_session, KeywordAdjudicator("v1")))
        v2 = rebuild(test_session, KeywordAdjudicator("v2", direction="contradicts", scale=0.5))
        text = format_diff(diff(v2, stored_evidence(test_session, "v1")), "v2", "v1", 4, 2)

        assert "prompt-version=v2 against=v1" in text
        assert "changed" in text
        assert "was [supports" in text
        assert "now [contradicts" in text


class TestNothingIsWrittenWithoutCommit:
    def test_rebuild_writes_no_evidence(self, test_session, watches, observations):
        before = test_session.query(Evidence).count()
        rows = rebuild(test_session, KeywordAdjudicator("v1"))

        assert rows
        assert test_session.query(Evidence).count() == before == 0

    def test_diffing_writes_no_evidence(self, test_session, watches, observations):
        rows = rebuild(test_session, KeywordAdjudicator("v1"))
        diff(rows, stored_evidence(test_session, "v1"))
        assert test_session.query(Evidence).count() == 0

    def test_commit_is_what_writes(self, test_session, watches, observations):
        rows = rebuild(test_session, KeywordAdjudicator("v1"))
        written = commit(test_session, "v1", rows)

        assert written["inserted"] == len(rows)
        assert test_session.query(Evidence).count() == len(rows)


class TestCommitBehaviour:
    def test_every_committed_row_records_the_prompt_version(
        self, test_session, watches, observations
    ):
        commit(test_session, "v1", rebuild(test_session, KeywordAdjudicator("v1")))
        versions = {row.prompt_version for row in test_session.query(Evidence).all()}
        assert versions == {"v1"}

    def test_committing_twice_inserts_nothing_the_second_time(
        self, test_session, watches, observations
    ):
        rows = rebuild(test_session, KeywordAdjudicator("v1"))
        commit(test_session, "v1", rows)
        second = commit(test_session, "v1", rebuild(test_session, KeywordAdjudicator("v1")))

        assert second == {"inserted": 0, "deleted": 0}
        assert test_session.query(Evidence).count() == len(rows)

    def test_committing_a_second_version_leaves_the_first_alone(
        self, test_session, watches, observations
    ):
        v1_rows = rebuild(test_session, KeywordAdjudicator("v1"))
        commit(test_session, "v1", v1_rows)
        commit(
            test_session,
            "v2",
            rebuild(test_session, KeywordAdjudicator("v2", direction="contradicts", scale=0.5)),
        )

        assert stored_evidence(test_session, "v1") == sorted(v1_rows)
        assert len(stored_evidence(test_session, "v2")) == len(v1_rows)

    def test_commit_deletes_rows_the_version_no_longer_produces(
        self, test_session, watches, observations
    ):
        commit(test_session, "v1", rebuild(test_session, KeywordAdjudicator("v1")))
        assert test_session.query(Evidence).count() > 0

        written = commit(test_session, "v1", [])
        assert written["inserted"] == 0
        assert written["deleted"] > 0
        assert test_session.query(Evidence).count() == 0

    def test_a_nondeterministic_version_is_refused_and_writes_nothing(
        self, test_session, watches, observations
    ):
        drifting = CountingAdjudicator("drifty")
        commit(test_session, "drifty", rebuild(test_session, drifting))
        before = test_session.query(Evidence).count()
        assert before > 0

        with pytest.raises(NondeterministicReplay, match="not deterministic"):
            commit(test_session, "drifty", rebuild(test_session, drifting))

        assert test_session.query(Evidence).count() == before

    def test_evidence_rows_are_rebuilt_from_observations_alone(
        self, test_session, watches, observations
    ):
        """
        Every evidence row points at a stored observation, by hash.

        Nothing in the replay path reads the articles table; this asserts the
        result, and the observation hashes are the only join key that exists.
        """
        from src.database.models import Observation

        commit(test_session, "v1", rebuild(test_session, KeywordAdjudicator("v1")))
        hashes = {row[0] for row in test_session.query(Observation.content_hash).all()}
        for row in test_session.query(Evidence).all():
            assert row.observation_hash in hashes


class TestRebuildScope:
    def test_limit_narrows_the_corpus(self, test_session, watches, observations):
        everything = rebuild(test_session, KeywordAdjudicator("v1"))
        assert len(rebuild(test_session, KeywordAdjudicator("v1"), limit=1)) <= len(everything)

    def test_an_empty_watch_set_produces_no_evidence(self, test_session, observations):
        assert rebuild(test_session, KeywordAdjudicator("v1")) == []

    def test_the_adjudicator_sees_only_the_stored_payload(
        self, test_session, watches, observations
    ):
        seen = []

        class Recorder:
            prompt_version = "recorder"

            def adjudicate(self, observation, watches):  # noqa: ARG002
                seen.append(observation)
                return []

        rebuild(test_session, Recorder())
        assert seen
        assert all(isinstance(view, ObservationView) for view in seen)
        assert all(set(view.payload) and view.content_hash.startswith("sha256:") for view in seen)


class TestVerdictValidation:
    def test_direction_must_be_in_the_vocabulary(self):
        with pytest.raises(ValueError, match="direction must be one of"):
            Verdict(watch_id="w", direction="maybe", magnitude=0.5)

    def test_magnitude_is_bounded(self):
        with pytest.raises(ValueError, match="magnitude must be in"):
            Verdict(watch_id="w", direction="supports", magnitude=1.5)

    def test_a_verdict_must_name_a_watch(self):
        with pytest.raises(ValueError, match="must name the watch"):
            Verdict(watch_id="  ", direction="supports", magnitude=0.5)


class TestAdjudicatorRegistry:
    def test_the_null_adjudicator_is_registered_and_finds_nothing(self):
        adjudicator = resolve(NULL_PROMPT_VERSION)
        assert adjudicator.prompt_version == NULL_PROMPT_VERSION
        assert adjudicator.adjudicate(ObservationView("sha256:x", {}), []) == []

    def test_an_unregistered_version_fails_loudly_and_names_what_is_known(self):
        with pytest.raises(UnknownPromptVersion, match="no adjudicator is registered"):
            resolve("does-not-exist")

    def test_rebinding_a_version_is_refused(self):
        with pytest.raises(ValueError, match="already registered"):
            register(NULL_PROMPT_VERSION, NullAdjudicator)

    def test_the_registry_ships_no_llm_adjudicator(self):
        """
        The adjudication prompt is backlog task 016, not this task.

        Asserted so that a shipped placeholder cannot quietly become the thing
        producing evidence.
        """
        assert known_prompt_versions() == [NULL_PROMPT_VERSION]

    def test_an_adjudicator_can_be_loaded_by_path(self):
        adjudicator = load_adjudicator("tests.evidence.stubs:make_v1")
        assert adjudicator.prompt_version == "v1"

    def test_a_bad_path_is_refused(self):
        with pytest.raises(ValueError, match="module:attr"):
            load_adjudicator("no_colon_here")

    def test_a_path_to_a_non_adjudicator_is_refused(self):
        with pytest.raises(TypeError, match="did not produce an Adjudicator"):
            load_adjudicator("tests.evidence.stubs:SOURCE_URL")

    def test_replay_needs_no_api_key(self, test_session, watches, observations, monkeypatch):
        """
        The harness must run with no ANTHROPIC_API_KEY set.

        Out of scope for this task by name: "Any LLM call: replay must work with
        no ANTHROPIC_API_KEY, driven by a stub adjudicator in tests."
        """
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        assert rebuild(test_session, KeywordAdjudicator("v1"))
