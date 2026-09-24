"""
Tests for the `adjudicate` CLI command (backlog task 029).

`get_db` is patched with a throwaway session and the registered adjudicator is
replaced with one whose client answers from a script. `--dry-run` is tested
with the client class itself patched to raise, which is the acceptance
criterion "without constructing a client" stated as a test.
"""

import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from src.cli.adjudicate import adjudicate_command
from src.database.models import Adjudication, Evidence
from src.evidence.claude_adjudicator import ClaudeAdjudicator
from src.llm.claude_client import ModelResponse

from ..evidence.stubs import add_observations, add_routes, add_watches


def _verdict(is_evidence=True) -> str:
    return json.dumps(
        {
            "is_evidence": is_evidence,
            "direction": "supports" if is_evidence else "none",
            "magnitude": 0.5,
            "satisfies_clause": 0 if is_evidence else -1,
            "confidence": 0.7,
            "rationale": "words",
        }
    )


class FakeClient:
    def __init__(self, *scripted):
        self.scripted = list(scripted)

    def analyze(self, system_prompt, user_message, **kwargs):  # noqa: ARG002
        item = self.scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        return ModelResponse(
            text=item,
            model="m",
            stop_reason="end_turn",
            input_tokens=50,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            audit_id="audit",
        )


@contextmanager
def _patched(session, *scripted):
    @contextmanager
    def _ctx():
        try:
            yield session
            session.flush()
        except Exception:
            session.rollback()
            raise

    adjudicator = ClaudeAdjudicator(FakeClient(*scripted))
    with (
        patch("src.cli.adjudicate.get_db", _ctx),
        patch("src.cli.adjudicate.resolve", return_value=adjudicator),
    ):
        yield


@pytest.fixture
def corpus(test_session):
    add_watches(test_session)
    add_observations(test_session)
    add_routes(test_session)
    return test_session


class TestRun:
    def test_asks_every_pending_pair_and_prints_the_totals(self, cli_runner, corpus):
        with _patched(corpus, _verdict(), _verdict(is_evidence=False)):
            result = cli_runner.invoke(adjudicate_command, [])

        assert result.exit_code == 0, result.output
        assert "asked 2: evidence 1, none 1, failed 0" in result.output
        assert "tokens: 100 in, 10 out" in result.output
        assert corpus.query(Adjudication).count() == 2
        assert corpus.query(Evidence).count() == 1

    def test_a_second_run_reports_nothing_pending(self, cli_runner, corpus):
        with _patched(corpus, _verdict(), _verdict()):
            cli_runner.invoke(adjudicate_command, [])
            result = cli_runner.invoke(adjudicate_command, [])

        assert result.exit_code == 0, result.output
        assert "asked 0" in result.output
        assert "No pending pairs" in result.output

    def test_a_failure_is_printed_and_recorded_and_the_command_still_exits_zero(
        self, cli_runner, corpus
    ):
        with _patched(corpus, "garbage", _verdict()):
            result = cli_runner.invoke(adjudicate_command, [])

        assert result.exit_code == 0, result.output
        assert "FAILED" in result.output
        assert "1 failed adjudication(s) are recorded, not retried" in result.output
        assert corpus.query(Adjudication).filter(Adjudication.outcome == "failed").count() == 1

    def test_limit_is_honoured_and_zero_is_refused(self, cli_runner, corpus):
        with _patched(corpus, _verdict(), _verdict()):
            result = cli_runner.invoke(adjudicate_command, ["--limit", "1"])
            zero = cli_runner.invoke(adjudicate_command, ["--limit", "0"])

        assert result.exit_code == 0, result.output
        assert "asked 1" in result.output
        assert zero.exit_code != 0

    def test_a_missing_key_exits_non_zero_naming_the_fix_and_writes_nothing(
        self, cli_runner, corpus, memory_keyring
    ):
        @contextmanager
        def _ctx():
            yield corpus

        with (
            patch("src.cli.adjudicate.get_db", _ctx),
            patch("src.cli.adjudicate.resolve", return_value=ClaudeAdjudicator()),
        ):
            result = cli_runner.invoke(adjudicate_command, [])

        assert result.exit_code != 0
        assert "insightweaver auth set anthropic" in result.output
        assert corpus.query(Adjudication).count() == 0


class TestDryRun:
    def test_prints_the_exact_text_and_never_constructs_a_client(self, cli_runner, corpus):
        def explode(*_args, **_kwargs):
            raise AssertionError("a client was constructed during --dry-run")

        @contextmanager
        def _ctx():
            yield corpus

        with (
            patch("src.cli.adjudicate.get_db", _ctx),
            patch("src.evidence.claude_adjudicator.ClaudeClient", explode),
        ):
            result = cli_runner.invoke(adjudicate_command, ["--dry-run"])

        assert result.exit_code == 0, result.output
        assert "[system]" in result.output and "[user]" in result.output
        assert "You judge whether one published item" in result.output
        assert "character estimate, not a count" in result.output
        assert "Nothing was sent." in result.output
        assert corpus.query(Adjudication).count() == 0
