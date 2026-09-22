"""
The client: keychain key, role-chosen model, and an audited send path.

No test here makes a network call. The SDK's ``messages.create`` is replaced
with a stub that returns a response-shaped object, so what is under test is
what the client does around the call: what it sends, what it records, what it
returns, and what it refuses. Synchronous since backlog task 029 (2026-09-22).
"""

import json
from types import SimpleNamespace

import pytest

from src.config import credentials
from src.config.settings import settings
from src.llm.claude_client import ROLES, ClaudeClient, ModelCallFailed, ModelResponse

# Not a credential: the SDK is stubbed and nothing here reaches a network.
FAKE_KEY = "sk-test"  # pragma: allowlist secret


@pytest.fixture
def audit_dir(tmp_path, monkeypatch):
    target = tmp_path / "llm-audit"
    monkeypatch.setattr(settings, "llm_audit_dir", target)
    return target


def _audit_events(audit_dir) -> list[dict]:
    return [
        json.loads(line)
        for file in sorted(audit_dir.glob("*.jsonl"))
        for line in file.read_text().splitlines()
    ]


def _response(*, text="answer", stop_reason="end_turn", model="served-model", thinking=True):
    blocks = []
    if thinking:
        blocks.append(SimpleNamespace(type="thinking", thinking="..."))
    blocks.append(SimpleNamespace(type="text", text=text))
    return SimpleNamespace(
        content=blocks,
        stop_reason=stop_reason,
        stop_details=None,
        model=model,
        usage=SimpleNamespace(
            input_tokens=11,
            output_tokens=7,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=None,
        ),
    )


@pytest.fixture
def client(audit_dir):
    return ClaudeClient("triage", api_key=FAKE_KEY, model="test-model")


def _stub_create(client, response=None, error=None):
    """Replace the SDK call; record what it was called with."""
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        if error is not None:
            raise error
        return response

    client.client.messages.create = create
    return calls


class TestConstruction:
    def test_the_key_comes_from_the_keychain(self, memory_keyring, audit_dir):
        credentials.write(credentials.ANTHROPIC, FAKE_KEY)

        assert ClaudeClient("triage").api_key == FAKE_KEY

    def test_no_key_in_the_keychain_fails_at_construction(self, memory_keyring, audit_dir):
        with pytest.raises(credentials.MissingCredential):
            ClaudeClient("triage")

    @pytest.mark.parametrize("role", sorted(ROLES))
    def test_the_model_is_chosen_by_role_from_settings(self, role, audit_dir, monkeypatch):
        monkeypatch.setattr(settings, ROLES[role], f"model-for-{role}")

        assert ClaudeClient(role, api_key=FAKE_KEY).model == f"model-for-{role}"

    def test_an_unknown_role_is_refused(self, audit_dir):
        with pytest.raises(ValueError, match="role"):
            ClaudeClient("summarise", api_key=FAKE_KEY)


class TestSend:
    def test_returns_text_and_usage(self, client):
        _stub_create(client, _response())

        result = client.analyze("sys", "hello")

        assert isinstance(result, ModelResponse)
        assert result.text == "answer"
        assert result.model == "served-model"
        assert result.stop_reason == "end_turn"
        assert (result.input_tokens, result.output_tokens) == (11, 7)
        assert result.cache_creation_input_tokens == 0  # None from the API reads as zero

    def test_effort_goes_in_output_config_not_extra_body(self, client):
        calls = _stub_create(client, _response())

        client.analyze("sys", "hello", effort="low", max_tokens=99)

        (sent,) = calls
        assert sent["output_config"] == {"effort": "low"}
        assert "extra_body" not in sent
        assert sent["max_tokens"] == 99
        assert sent["model"] == "test-model"
        assert sent["messages"] == [{"role": "user", "content": "hello"}]

    def test_a_schema_goes_in_output_config_format_as_a_request_parameter(self, client):
        """Structured output is a request parameter, not a parsing convention."""
        calls = _stub_create(client, _response(text='{"ok": true}'))
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}

        client.analyze("sys", "hello", output_schema=schema)

        (sent,) = calls
        assert sent["output_config"] == {
            "effort": "high",
            "format": {"type": "json_schema", "schema": schema},
        }

    def test_an_invalid_effort_is_refused_before_anything_is_sent(self, client, audit_dir):
        calls = _stub_create(client, _response())

        with pytest.raises(ValueError, match="effort"):
            client.analyze("sys", "hello", effort="maximum")

        assert calls == []
        assert not audit_dir.exists()

    def test_text_is_selected_by_block_type_not_position(self, client):
        """2026-08-26: content[0] is a ThinkingBlock on thinking models."""
        _stub_create(client, _response(thinking=True))

        assert client.analyze("sys", "hello").text == "answer"

    def test_a_refusal_is_raised_not_returned_as_empty(self, client):
        _stub_create(client, _response(stop_reason="refusal"))

        with pytest.raises(ModelCallFailed, match="declined") as excinfo:
            client.analyze("sys", "hello")

        # The failure carries what the audit log recorded: the id and the cost.
        assert excinfo.value.audit_id
        assert (excinfo.value.input_tokens, excinfo.value.output_tokens) == (11, 7)
        assert excinfo.value.stop_reason == "refusal"

    def test_an_api_error_is_a_typed_failure_carrying_its_audit_id(self, client):
        _stub_create(client, error=ConnectionError("no route"))

        with pytest.raises(ModelCallFailed, match="ConnectionError: no route") as excinfo:
            client.analyze("sys", "hello")

        assert excinfo.value.audit_id
        assert (excinfo.value.input_tokens, excinfo.value.output_tokens) == (0, 0)
        assert excinfo.value.misconfigured is False

    def test_a_rejected_request_is_marked_as_a_misconfiguration(self, client):
        import anthropic
        import httpx2

        request = httpx2.Request("POST", "https://api.example/v1/messages")
        rejected = anthropic.BadRequestError(
            "invalid schema", response=httpx2.Response(400, request=request), body=None
        )
        _stub_create(client, error=rejected)

        with pytest.raises(ModelCallFailed) as excinfo:
            client.analyze("sys", "hello")

        assert excinfo.value.misconfigured is True


class TestAudit:
    def test_request_is_logged_before_the_send_and_response_after(self, client, audit_dir):
        calls = _stub_create(client, _response())

        result = client.analyze("sys", "hello", effort="medium")

        request, response = _audit_events(audit_dir)
        assert request["event"] == "request"
        assert request["id"] == result.audit_id
        assert request["role"] == "triage"
        assert request["request"] == calls[0]
        assert response["event"] == "response"
        assert response["id"] == result.audit_id
        assert response["usage"]["input_tokens"] == 11
        assert response["stop_reason"] == "end_turn"
        assert response["model"] == "served-model"

    def test_a_failed_send_leaves_the_request_and_an_error_line(self, client, audit_dir):
        _stub_create(client, error=ConnectionError("no route"))

        with pytest.raises(ModelCallFailed):
            client.analyze("sys", "hello")

        request, error = _audit_events(audit_dir)
        assert request["event"] == "request"
        assert error["event"] == "error"
        assert error["id"] == request["id"]
        assert "no route" in error["error"]

    def test_a_refusal_is_audited_as_a_response_before_it_is_raised(self, client, audit_dir):
        _stub_create(client, _response(stop_reason="refusal"))

        with pytest.raises(ModelCallFailed):
            client.analyze("sys", "hello")

        _request, response = _audit_events(audit_dir)
        assert response["stop_reason"] == "refusal"


def test_only_the_client_constructs_a_model_request():
    """
    One module builds requests. Checked against the tree, not intentions, the
    same way tests/sources/test_observation.py checks the observation write path.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "src"
    pattern = re.compile(r"\bAnthropic\(|messages\.create\(")
    offenders = [
        str(p.relative_to(root))
        for p in sorted(root.rglob("*.py"))
        if p != root / "llm" / "claude_client.py" and pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == [], f"model requests are constructed outside the client: {offenders}"
