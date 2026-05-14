"""
CLI-specific test fixtures
"""

from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_api_key(monkeypatch):
    """Mock API key as configured for the brief command."""
    mock = MagicMock()
    mock.anthropic_api_key = "test-api-key"
    monkeypatch.setattr("src.cli.brief.settings", mock)


@pytest.fixture
def mock_no_api_key(monkeypatch):
    """Mock API key as not configured."""
    mock = MagicMock()
    mock.anthropic_api_key = None
    monkeypatch.setattr("src.cli.brief.settings", mock)
