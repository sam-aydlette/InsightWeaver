"""
Tests for `insightweaver brief --from-run` -- the render-only path.

The point of these tests is what does NOT happen: no pipeline stage runs, no
API key is required, and the same stored id renders the same bytes. The
pipeline entry point is replaced with a fuse that fails the test if it is ever
awaited.
"""

from unittest.mock import MagicMock

import pytest

from src.cli.brief import brief_group
from src.render.document import BriefDocument, StoredBriefNotFound
from src.render.email import EmailDeliveryError
from tests.render.conftest import SYNTHESIS_DATA
from tests.render.test_html import external_resource_hits


@pytest.fixture
def stored_document() -> BriefDocument:
    return BriefDocument.from_synthesis_data(
        SYNTHESIS_DATA,
        articles_analyzed=42,
        synthesis_id=176,
        analysis_run_id=15,
        generated_at="2026-05-15T10:43:37.873249",
    )


@pytest.fixture
def pipeline_fuse(monkeypatch):
    """Blow up if anything reaches for the pipeline."""

    async def _fuse(*args, **kwargs):
        raise AssertionError("the render-only path must not invoke the pipeline")

    monkeypatch.setattr("src.cli.brief.run_pipeline", _fuse)


@pytest.fixture
def stored_brief(monkeypatch, stored_document):
    monkeypatch.setattr("src.cli.brief.load_stored_brief", lambda _id: stored_document)
    return stored_document


@pytest.fixture
def no_api_key(monkeypatch):
    """ANTHROPIC_API_KEY unset, as on a machine with no Claude access."""
    settings = MagicMock()
    settings.anthropic_api_key = ""
    monkeypatch.setattr("src.cli.brief.settings", settings)
    return settings


class TestRendersWithoutThePipeline:
    def test_terminal_render_needs_no_api_key(
        self, cli_runner, stored_brief, pipeline_fuse, no_api_key
    ):
        result = cli_runner.invoke(brief_group, ["--from-run", "176"])
        assert result.exit_code == 0, result.output
        assert "INTELLIGENCE BRIEF" in result.output
        assert "Procurement rule change lands[1]" in result.output

    def test_rendering_twice_is_byte_identical(
        self, cli_runner, stored_brief, pipeline_fuse, no_api_key
    ):
        first = cli_runner.invoke(brief_group, ["--from-run", "176"])
        second = cli_runner.invoke(brief_group, ["--from-run", "176"])
        assert first.exit_code == second.exit_code == 0
        assert first.output == second.output

    def test_quiet_render(self, cli_runner, stored_brief, pipeline_fuse, no_api_key):
        result = cli_runner.invoke(brief_group, ["--from-run", "176", "--quiet"])
        assert result.exit_code == 0, result.output
        assert "Situations analyzed:" in result.output
        assert "Articles: 42 | Clusters: 5" in result.output

    def test_unknown_id_reports_available_ids(
        self, cli_runner, monkeypatch, pipeline_fuse, no_api_key
    ):
        def _missing(synthesis_id):
            raise StoredBriefNotFound(synthesis_id, [189, 188])

        monkeypatch.setattr("src.cli.brief.load_stored_brief", _missing)
        result = cli_runner.invoke(brief_group, ["--from-run", "999"])
        assert result.exit_code != 0
        assert "189, 188" in result.output


class TestHTMLFormat:
    def test_writes_a_self_contained_file(
        self, cli_runner, stored_brief, pipeline_fuse, no_api_key, tmp_path
    ):
        target = tmp_path / "brief.html"
        result = cli_runner.invoke(
            brief_group, ["--from-run", "176", "--format", "html", "--output", str(target)]
        )
        assert result.exit_code == 0, result.output
        html = target.read_text(encoding="utf-8")
        assert html.startswith("<!DOCTYPE html>")
        # tests/render/test_html.py holds the exhaustive self-containment scan;
        # this checks the CLI wrote that same page rather than something else.
        assert external_resource_hits(html) == []
        assert "<style>" in html

    def test_rewriting_produces_the_same_bytes(
        self, cli_runner, stored_brief, pipeline_fuse, no_api_key, tmp_path
    ):
        first, second = tmp_path / "a.html", tmp_path / "b.html"
        for target in (first, second):
            assert (
                cli_runner.invoke(
                    brief_group,
                    ["--from-run", "176", "--format", "html", "--output", str(target)],
                ).exit_code
                == 0
            )
        assert first.read_bytes() == second.read_bytes()

    def test_defaults_to_the_data_directory(
        self, cli_runner, stored_brief, pipeline_fuse, no_api_key, monkeypatch, tmp_path
    ):
        monkeypatch.setattr("src.cli.brief.settings", MagicMock(data_dir=tmp_path))
        result = cli_runner.invoke(brief_group, ["--from-run", "176", "--format", "html"])
        assert result.exit_code == 0, result.output
        assert (tmp_path / "briefs" / "brief-176.html").exists()


class TestEmailFormat:
    def test_sends_and_reports_the_recipient(
        self, cli_runner, stored_brief, pipeline_fuse, no_api_key, monkeypatch
    ):
        sent = []

        def _send(self, doc, **kwargs):
            sent.append(doc)
            return "reader@example.test"

        monkeypatch.setattr("src.render.email.EmailRenderer.send", _send)
        result = cli_runner.invoke(brief_group, ["--from-run", "176", "--format", "email"])
        assert result.exit_code == 0, result.output
        assert "reader@example.test" in result.output
        assert sent[0].synthesis_id == 176

    def test_failure_exits_non_zero_with_a_clear_message(
        self, cli_runner, stored_brief, pipeline_fuse, no_api_key, monkeypatch
    ):
        def _fail(self, doc, **kwargs):
            raise EmailDeliveryError("missing environment variable(s): SMTP_SERVER")

        monkeypatch.setattr("src.render.email.EmailRenderer.send", _fail)
        result = cli_runner.invoke(brief_group, ["--from-run", "176", "--format", "email"])
        assert result.exit_code != 0
        assert "SMTP_SERVER" in result.output


class TestMarkdownSave:
    def test_save_writes_markdown(
        self, cli_runner, stored_brief, pipeline_fuse, no_api_key, tmp_path
    ):
        target = tmp_path / "brief.md"
        result = cli_runner.invoke(brief_group, ["--from-run", "176", "--save", str(target)])
        assert result.exit_code == 0, result.output
        assert target.read_text().startswith("# Intelligence Brief")


class TestFormatRequiresFromRun:
    def test_html_without_from_run_is_rejected(self, cli_runner, pipeline_fuse, no_api_key):
        result = cli_runner.invoke(brief_group, ["--format", "html"])
        assert result.exit_code != 0
        assert "--from-run" in result.output

    def test_output_without_from_run_is_rejected(self, cli_runner, pipeline_fuse, no_api_key):
        result = cli_runner.invoke(brief_group, ["--output", "x.html"])
        assert result.exit_code != 0
        assert "--from-run" in result.output

    def test_live_path_still_requires_an_api_key(self, cli_runner, pipeline_fuse, no_api_key):
        result = cli_runner.invoke(brief_group, [])
        assert result.exit_code != 0
        assert "ANTHROPIC_API_KEY not configured" in result.output
