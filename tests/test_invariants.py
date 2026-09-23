"""
Two of the six invariants that are properties of the tree rather than of a
run, pinned by scanning the tree (2026-09-23, backlog task 033).

1. Nothing sends. The only modules that open an outbound connection are the
   two fetchers and the model client, and nothing listens, mails or posts.
3. Evidence is deleted by ``replay --commit`` and nothing else.

Like ``tests/test_reachability.py`` these match tokens, not behaviour; they
are guards against habit, and a new fetcher or a new delete is added to the
allowlist here in the same change that adds it, with its reason.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"

# Modules allowed to import an HTTP client. The model API is reached through
# the anthropic SDK, which owns its own transport, so src/llm/ is not here.
OUTBOUND = {"sources/federal_register.py", "rss/fetcher.py"}

# Anything that would send, serve or listen. A hit is a design change.
FORBIDDEN_IMPORTS = re.compile(
    r"^\s*(?:import|from)\s+(smtplib|socketserver|http\.server|socket|asyncio\.streams|"
    r"flask|fastapi|uvicorn|aiohttp|websockets|requests)\b",
    re.MULTILINE,
)
HTTP_CLIENT_IMPORT = re.compile(r"^\s*(?:import|from)\s+httpx\b", re.MULTILINE)
# A query over Evidence that ends in .delete(, across the lines a formatter
# spreads it over, or a core delete(Evidence) statement.
EVIDENCE_DELETE = re.compile(r"query\(Evidence\)[\s\S]{0,500}?\.delete\(|delete\(Evidence\b")


def _sources() -> dict[str, str]:
    return {
        str(p.relative_to(SRC)): p.read_text(encoding="utf-8") for p in sorted(SRC.rglob("*.py"))
    }


def test_nothing_sends_serves_or_listens():
    offenders = [
        f"{name}: {match.group(1)}"
        for name, text in _sources().items()
        for match in FORBIDDEN_IMPORTS.finditer(text)
    ]
    assert offenders == [], f"a module imports something that sends or listens: {offenders}"


def test_only_the_two_fetchers_open_an_http_client():
    with_client = {name for name, text in _sources().items() if HTTP_CLIENT_IMPORT.search(text)}
    assert with_client == OUTBOUND


def test_only_replay_deletes_evidence():
    deleters = {name for name, text in _sources().items() if EVIDENCE_DELETE.search(text)}
    assert deleters == {"evidence/replay.py"}
