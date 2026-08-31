"""
Fixtures for the replay harness, built from :mod:`tests.evidence.stubs`.

**Nothing here makes an LLM call and nothing here needs an API key.** The whole
point of the harness is that adjudication is pluggable and that the replay
machinery can be exercised without the stochastic part; a suite that needed a
key to test the reproducibility of a replay would be testing the wrong thing.
"""

import pytest

from .stubs import add_observations, add_watches


@pytest.fixture
def watches(test_session):
    return add_watches(test_session)


@pytest.fixture
def source(test_session):
    return add_observations(test_session)


@pytest.fixture
def observations(test_session, source):
    return source
