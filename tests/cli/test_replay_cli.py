"""
Tests for the `replay` CLI command (backlog task 014).

Two of these are the acceptance criteria stated as commands rather than as
functions, because that is how the criteria are written:

* :class:`TestCommitIsRequired` -- a replay without ``--commit`` writes nothing,
  proven by counting rows before and after, not by reading the code.
* :class:`TestOutputIsReproducible` -- the same prompt version twice prints the
  same bytes, and a different prompt version prints a visible diff.

Every adjudicator here is loaded through ``--adjudicator``, which is the
documented seam for a version that is not in the registry. No API key is set or
needed.
"""

from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.cli.replay import replay_command
from src.database.models import Evidence
from src.evidence import commit, rebuild

from ..evidence.stubs import KeywordAdjudicator, add_observations, add_watches

V1 = "tests.evidence.stubs:make_v1"
V2 = "tests.evidence.stubs:make_v2"


def _patch_db(session):
    @contextmanager
    def _ctx():
        try:
            yield session
            session.flush()
        except Exception:
            session.rollback()
            raise

    return patch("src.cli.replay.get_db", _ctx)


@pytest.fixture
def corpus(test_session):
    """
    A stored corpus with v1's evidence already committed.

    Built from tests/evidence/stubs.py rather than duplicated, so the CLI tests
    and the replay tests cannot drift apart about what the corpus contains.
    """
    add_watches(test_session)
    add_observations(test_session)
    commit(test_session, "v1", rebuild(test_session, KeywordAdjudicator("v1")))
    test_session.flush()
    return test_session


class TestCommitIsRequired:
    def test_a_replay_without_commit_writes_nothing(self, cli_runner, test_session, corpus):
        test_session.query(Evidence).delete()
        test_session.flush()
        assert test_session.query(Evidence).count() == 0

        with _patch_db(test_session):
            result = cli_runner.invoke(
                replay_command, ["--prompt-version", "v1", "--adjudicator", V1]
            )

        assert result.exit_code == 0, result.output
        assert test_session.query(Evidence).count() == 0
        assert "Nothing was written" in result.output

    def test_the_same_replay_with_commit_writes(self, cli_runner, test_session, corpus):
        test_session.query(Evidence).delete()
        test_session.flush()

        with _patch_db(test_session):
            result = cli_runner.invoke(
                replay_command, ["--prompt-version", "v1", "--adjudicator", V1, "--commit"]
            )

        assert result.exit_code == 0, result.output
        assert test_session.query(Evidence).count() > 0
        assert "committed v1" in result.output

    def test_a_changed_version_does_not_touch_the_stored_one_without_commit(
        self, cli_runner, test_session, corpus
    ):
        before = [
            (row.observation_hash, row.watch_id, row.direction, row.magnitude)
            for row in test_session.query(Evidence).all()
        ]

        with _patch_db(test_session):
            result = cli_runner.invoke(
                replay_command,
                ["--prompt-version", "v2", "--against", "v1", "--adjudicator", V2],
            )

        assert result.exit_code == 0, result.output
        after = [
            (row.observation_hash, row.watch_id, row.direction, row.magnitude)
            for row in test_session.query(Evidence).all()
        ]
        assert after == before


class TestOutputIsReproducible:
    def test_the_same_prompt_version_twice_prints_the_same_bytes(
        self, cli_runner, test_session, corpus
    ):
        with _patch_db(test_session):
            first = cli_runner.invoke(
                replay_command, ["--prompt-version", "v1", "--adjudicator", V1]
            )
            second = cli_runner.invoke(
                replay_command, ["--prompt-version", "v1", "--adjudicator", V1]
            )

        assert first.exit_code == second.exit_code == 0
        assert first.output == second.output
        assert "No difference from the stored evidence." in first.output

    def test_a_changed_prompt_version_prints_a_diff(self, cli_runner, test_session, corpus):
        with _patch_db(test_session):
            result = cli_runner.invoke(
                replay_command,
                ["--prompt-version", "v2", "--against", "v1", "--adjudicator", V2],
            )

        assert result.exit_code == 0, result.output
        assert "prompt-version=v2 against=v1" in result.output
        assert " changed" in result.output
        assert "was [supports" in result.output
        assert "now [contradicts" in result.output

    def test_the_diff_carries_no_timestamp_or_row_id(self, cli_runner, test_session, corpus):
        with _patch_db(test_session):
            result = cli_runner.invoke(
                replay_command,
                ["--prompt-version", "v2", "--against", "v1", "--adjudicator", V2],
            )
        assert "created_at" not in result.output
        assert "id=" not in result.output


class TestRefusals:
    def test_an_unregistered_prompt_version_fails_loudly(self, cli_runner, test_session, corpus):
        with _patch_db(test_session):
            result = cli_runner.invoke(replay_command, ["--prompt-version", "not-a-version"])

        assert result.exit_code != 0
        assert "no adjudicator is registered" in result.output

    def test_a_mislabelled_adjudicator_is_refused(self, cli_runner, test_session, corpus):
        """
        --prompt-version must be the name the adjudicator answers to.

        Otherwise the column that makes evidence reviewable records a name the
        thing that produced it never used.
        """
        with _patch_db(test_session):
            result = cli_runner.invoke(
                replay_command, ["--prompt-version", "v9", "--adjudicator", V1]
            )

        assert result.exit_code != 0
        assert "does not answer to" in result.output

    def test_prompt_version_is_required(self, cli_runner):
        result = cli_runner.invoke(replay_command, [])
        assert result.exit_code != 0
        assert "--prompt-version" in result.output

    def test_an_empty_observation_corpus_says_so(self, cli_runner, test_session):
        with _patch_db(test_session):
            result = cli_runner.invoke(replay_command, ["--prompt-version", "null-v0"])
        assert result.exit_code == 0
        assert "nothing to replay" in result.output


class TestRegisteredInTheApp:
    def test_replay_is_a_top_level_command(self):
        from src.cli.app import COMMAND_DISPATCH, cli

        assert COMMAND_DISPATCH["replay"] is replay_command
        assert "replay" in cli.commands

    def test_commit_is_a_flag_that_defaults_to_off(self):
        flag = next(p for p in replay_command.params if p.name == "do_commit")
        assert flag.is_flag is True
        assert flag.default is False
