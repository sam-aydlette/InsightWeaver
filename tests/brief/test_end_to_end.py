"""
The morning, end to end, against a committed golden file.

Recorded fixtures go through the real commands -- ``watch sync``, ``ingest``,
``route``, ``adjudicate`` with a scripted model client, ``brief`` -- and the
rendered bytes are compared with ``tests/brief/golden/``. Nothing here opens a
socket or reads a key.

The clock is frozen at ``NOW`` by replacing the ``datetime`` class that
``src.utils.utcnow`` reads, which every column default and every command's
window goes through. Without that, ``last_fetched``, the belief ledger and the
evidence timestamps would carry the wall clock into the golden file.

To regenerate the golden files after a deliberate change to the brief, run
``make golden`` and read the diff before committing it. A golden that changes
by accident is the test doing its job.

Added 2026-09-22 for backlog task 031.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from click.testing import CliRunner

from src.cli.adjudicate import adjudicate_command
from src.cli.brief import brief_command
from src.cli.ingest import ingest_command
from src.cli.route import route_command
from src.cli.watch import watch_command
from src.database.models import Adjudication, BriefRun, Evidence, Observation, Route
from src.evidence.claude_adjudicator import ClaudeAdjudicator
from src.llm.claude_client import ModelCallFailed, ModelResponse
from src.position import load_position, load_watches
from src.rss.fetcher import RSSFetcher
from src.sources.federal_register import (
    FederalRegisterAdapter,
    FederalRegisterFilter,
    FederalRegisterQuery,
)
from src.sources.rss_adapter import RSSAdapter
from tests.sources.conftest import json_responder, make_client

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
GOLDEN = HERE / "golden"
FR_WEEK = HERE.parent / "sources" / "fixtures" / "federal_register_week.json"

# A Monday morning after the recorded Federal Register week (2026-08-17 to 21).
NOW = datetime(2026, 8, 24, 6, 0)
AS_OF = NOW.isoformat()
UPDATE_GOLDEN = "INSIGHTWEAVER_UPDATE_GOLDEN"


class _FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: ARG003 - the signature datetime.now has
        return NOW.replace(tzinfo=UTC) if tz is not None else NOW


@pytest.fixture
def frozen_clock(monkeypatch):
    monkeypatch.setattr("src.utils.datetime", _FrozenDatetime)
    return NOW


@pytest.fixture
def private_files(monkeypatch):
    """Point the loaders at the fixture Position and watches, dated at NOW."""
    position_path, watches_path = FIXTURES / "position.yaml", FIXTURES / "watches.yaml"
    monkeypatch.setattr("src.config.settings.settings.position_path", position_path)
    monkeypatch.setattr("src.config.settings.settings.watches_path", watches_path)
    # `watch sync` dates expiry from the wall clock; hold it at NOW as the
    # other commands are held, or this test would rot on 2026-09-15.
    monkeypatch.setattr(
        "src.cli.watch.load_position",
        lambda **kw: load_position(position_path, today=kw.get("today") or NOW.date()),
    )
    monkeypatch.setattr(
        "src.cli.watch.load_watches",
        lambda **kw: load_watches(
            watches_path, position=kw["position"], today=kw.get("today") or NOW.date()
        ),
    )


@contextmanager
def patch_db(session):
    """Every command's ``get_db`` yields the one test session."""

    @contextmanager
    def _ctx():
        try:
            yield session
            session.flush()
        except Exception:
            session.rollback()
            raise

    patches = [
        patch(f"src.cli.{m}.get_db", _ctx)
        for m in ("ingest", "route", "adjudicate", "brief", "watch")
    ]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


def _feed_reader(content: bytes | None, error: Exception | None = None):
    """An RSSFetcher whose one HTTP call returns ``content`` or raises ``error``."""
    fetcher = RSSFetcher()
    response = MagicMock()
    response.content = content
    response.raise_for_status = MagicMock()
    getter = AsyncMock(return_value=response, side_effect=error)
    return fetcher, patch.object(fetcher.session, "get", getter)


def _adapters():
    """The four sources: recorded, recorded, empty, unreachable."""
    with open(FR_WEEK, encoding="utf-8") as handle:
        week = json.load(handle)
    fr = FederalRegisterAdapter(
        source_filter=FederalRegisterFilter(
            queries=(FederalRegisterQuery(name="week", agencies=("personnel-management-office",)),),
            per_page=100,
            max_pages=1,
        ),
        client=make_client(json_responder(week)),
        requests_per_second=0,
    )
    weekly, weekly_patch = _feed_reader((FIXTURES / "compliance_weekly.xml").read_bytes())
    newsroom, newsroom_patch = _feed_reader((FIXTURES / "agency_newsroom.xml").read_bytes())
    broken, broken_patch = _feed_reader(None, httpx.ConnectError("connection refused"))
    adapters = [
        fr,
        RSSAdapter(
            "Compliance Weekly", "https://example.com/compliance-weekly.xml", "news", weekly
        ),
        RSSAdapter("Agency Newsroom", "https://example.com/newsroom.xml", "news", newsroom),
        RSSAdapter("Broken Feed", "https://example.com/broken.xml", "news", broken),
    ]
    return adapters, (weekly_patch, newsroom_patch, broken_patch), (weekly, newsroom, broken)


class ScriptedClient:
    """
    Answers by the watch named in the prompt. Deterministic and offline: the
    NIST pair is evidence, the death-benefits form is evidence, the
    court-ordered form is refused so that QUIET has a failed adjudication to
    print, and anything else is not evidence.
    """

    def __init__(self):
        self.calls = 0

    def analyze(self, system_prompt, user_message, **kwargs):  # noqa: ARG002
        self.calls += 1
        watch_id = user_message.split("CLAIM (watch ", 1)[1].split(")", 1)[0]
        title = user_message.split("\ntitle: ", 1)[1].split("\n", 1)[0]
        if watch_id == "opm-benefit-forms-change" and "Court-Ordered" in title:
            raise ModelCallFailed(
                "Model declined the request (category: scripted)",
                audit_id=f"audit-{self.calls}",
                outcome="answered",
                input_tokens=900,
                output_tokens=2,
                stop_reason="refusal",
            )
        evidence = watch_id in ("nist-site-rules-loosen", "opm-benefit-forms-change")
        body = {
            "is_evidence": evidence,
            "direction": "supports" if evidence else "none",
            "magnitude": {"nist-site-rules-loosen": 0.8, "opm-benefit-forms-change": 0.55}.get(
                watch_id, 0.0
            ),
            "satisfies_clause": 0 if evidence else -1,
            "confidence": 0.9,
            "rationale": "scripted",
        }
        return ModelResponse(
            text=json.dumps(body),
            model="scripted",
            stop_reason="end_turn",
            input_tokens=1000,
            output_tokens=40,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
            audit_id=f"audit-{self.calls}",
        )


def _compare(path: Path, actual: str) -> None:
    if os.environ.get(UPDATE_GOLDEN):
        path.write_text(actual, encoding="utf-8")
        return
    assert path.exists(), f"{path} is missing; run 'make golden' and review the file it writes"
    assert actual == path.read_text(encoding="utf-8"), (
        f"{path.name} differs from the rendered brief; if the change is intended, "
        f"run 'make golden' and read the diff"
    )


def test_the_morning_end_to_end(test_session, frozen_clock, private_files):
    cli_runner = CliRunner()
    adapters, http_patches, fetchers = _adapters()
    with patch_db(test_session):
        sync = cli_runner.invoke(watch_command, ["sync"])
        assert sync.exit_code == 0, sync.output

        with (
            http_patches[0],
            http_patches[1],
            http_patches[2],
            patch("src.cli.ingest.build_configured_adapters", return_value=adapters),
        ):
            ingest = cli_runner.invoke(ingest_command, ["--since", "7d"])
        for fetcher in fetchers:
            asyncio.run(fetcher.close())
        assert ingest.exit_code == 0, ingest.output
        assert "UNREACHABLE Broken Feed" in ingest.output

        route = cli_runner.invoke(route_command, ["--since", "7d"])
        assert route.exit_code == 0, route.output

        client = ScriptedClient()
        with patch("src.cli.adjudicate.resolve", return_value=ClaudeAdjudicator(client)):
            adjudicate = cli_runner.invoke(adjudicate_command, [])
        assert adjudicate.exit_code == 0, adjudicate.output

        args = ["--as-of", AS_OF, "--since", "7d"]
        first = cli_runner.invoke(brief_command, args)
        second = cli_runner.invoke(brief_command, args)
        markdown = cli_runner.invoke(brief_command, [*args, "--format", "md", "--dry-run"])

    for result in (first, second, markdown):
        assert result.exit_code == 0, result.output

    # The corpus the golden rests on, so a drift is diagnosable from the failure.
    assert test_session.query(Observation).count() == 8  # six documents, two feed items
    # The DFARS notice is dated midnight on the window's first day and the
    # window opens at 06:00, so seven observations are in it; none of the
    # seven matches the DFARS watch. NIST routes twice, the two OPM forms once.
    assert test_session.query(Route).count() == 4
    assert client.calls == 4
    assert test_session.query(Adjudication).count() == 4
    assert test_session.query(Evidence).count() == 3
    assert test_session.query(BriefRun).count() == 2  # the dry run wrote no row

    assert first.output == second.output, "the same inputs must render the same bytes"
    _compare(GOLDEN / "brief.txt", first.output)
    _compare(GOLDEN / "brief.md", markdown.output)


def test_the_frozen_clock_is_what_the_commands_read(frozen_clock):
    from src.utils import utcnow

    assert utcnow() == NOW
    assert utcnow().date() == date(2026, 8, 24)
