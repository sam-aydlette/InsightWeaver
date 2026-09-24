"""
The audit log: written before the send, one file per day, JSON lines.
"""

import json
from pathlib import Path

import pytest

from src.config.settings import settings
from src.llm import audit


@pytest.fixture
def audit_dir(tmp_path, monkeypatch):
    target = tmp_path / "llm-audit"
    monkeypatch.setattr(settings, "llm_audit_dir", target)
    return target


def _lines(directory: Path) -> list[dict]:
    files = sorted(directory.glob("*.jsonl"))
    assert files, "no audit file was written"
    return [json.loads(line) for file in files for line in file.read_text().splitlines()]


class TestRecordRequest:
    def test_writes_the_whole_request_and_its_hash(self, audit_dir):
        request = {"model": "m", "system": "s", "messages": [{"role": "user", "content": "hi"}]}

        entry_id = audit.record_request("triage", request)

        (line,) = _lines(audit_dir)
        assert line["id"] == entry_id
        assert line["event"] == "request"
        assert line["role"] == "triage"
        assert line["request"] == request
        assert len(line["payload_sha256"]) == 64
        assert line["at"]

    def test_the_same_request_has_the_same_hash_and_a_different_id(self, audit_dir):
        request = {"model": "m", "messages": []}

        first = audit.record_request("triage", request)
        second = audit.record_request("triage", dict(reversed(list(request.items()))))

        a, b = _lines(audit_dir)
        assert first != second
        assert a["payload_sha256"] == b["payload_sha256"]

    def test_creates_the_directory(self, audit_dir):
        assert not audit_dir.exists()
        audit.record_request("triage", {})
        assert audit_dir.is_dir()


class TestRecordResponseAndError:
    def test_response_and_error_share_the_request_id(self, audit_dir):
        entry_id = audit.record_request("synthesis", {"model": "m"})
        audit.record_response(
            entry_id, model="m", stop_reason="end_turn", usage={"input_tokens": 3}
        )
        audit.record_error(entry_id, RuntimeError("boom"))

        request, response, error = _lines(audit_dir)
        assert request["id"] == response["id"] == error["id"] == entry_id
        assert response["event"] == "response"
        assert response["usage"] == {"input_tokens": 3}
        assert response["stop_reason"] == "end_turn"
        assert error["event"] == "error"
        assert error["error"] == "RuntimeError: boom"
