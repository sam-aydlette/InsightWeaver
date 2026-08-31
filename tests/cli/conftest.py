"""
CLI-specific test fixtures.

The ``mock_api_key`` / ``mock_no_api_key`` fixtures were removed by backlog
task 012: both patched ``src.cli.brief.settings``, and the brief command is
gone. Nothing surviving in the CLI reads an API key.
"""

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Click CLI test runner."""
    return CliRunner()
