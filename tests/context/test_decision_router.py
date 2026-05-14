"""
Tests for the decision router and the synthesizer's decision-summary helper.
"""

import json

import pytest

from src.context.decision_router import DecisionRouter, RoutedEvidence
from src.context.synthesizer import NarrativeSynthesizer
from src.database.models import (
    DECISION_STATUS_DECIDED,
    DECISION_STATUS_OPEN,
    Decision,
    DecisionFactor,
)


def _make_decision(session, name="housing market", status=DECISION_STATUS_OPEN, factors=None):
    d = Decision(name=name, decision_type="housing", status=status)
    session.add(d)
    session.flush()
    factor_rows = []
    for fname in factors or ["interest rates"]:
        f = DecisionFactor(decision_id=d.id, name=fname, what_would_update_me="a Fed move")
        session.add(f)
        factor_rows.append(f)
    session.flush()
    return d, factor_rows


SITUATIONS = [
    {"title": "Fed signals caution", "narrative": "The Fed held rates steady."},
    {"title": "Unrelated sports news", "narrative": "A team won a game."},
]


class TestDecisionRouter:
    @pytest.fixture
    def router(self, mock_claude_client):
        return DecisionRouter(client=mock_claude_client)

    @pytest.mark.asyncio
    async def test_no_situations_returns_empty(self, router, test_session):
        assert await router.route_evidence([], test_session) == []

    @pytest.mark.asyncio
    async def test_no_open_decisions_returns_empty(self, router, test_session, mock_claude_client):
        result = await router.route_evidence(SITUATIONS, test_session)
        assert result == []
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_decided_decisions_are_ignored(self, router, test_session, mock_claude_client):
        _make_decision(test_session, status=DECISION_STATUS_DECIDED)
        test_session.commit()
        result = await router.route_evidence(SITUATIONS, test_session)
        assert result == []
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_routes_valid_evidence(self, router, test_session, mock_claude_client):
        _d, factors = _make_decision(test_session)
        test_session.commit()
        fid = factors[0].id

        mock_claude_client.analyze.return_value = json.dumps(
            {
                "evidence": [
                    {
                        "situation_index": 0,
                        "factor_id": fid,
                        "direction": "complicates",
                        "epistemic_status": "single_source",
                        "excerpt": "The Fed held rates steady.",
                    }
                ]
            }
        )

        result = await router.route_evidence(SITUATIONS, test_session)
        assert len(result) == 1
        assert result[0].factor_id == fid
        assert result[0].direction == "complicates"
        assert result[0].epistemic_status == "single_source"
        assert result[0].situation_index == 0

    @pytest.mark.asyncio
    async def test_invalid_factor_id_dropped(self, router, test_session, mock_claude_client):
        _make_decision(test_session)
        test_session.commit()
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "evidence": [
                    {
                        "situation_index": 0,
                        "factor_id": 99999,
                        "direction": "supports",
                        "epistemic_status": "consensus",
                        "excerpt": "x",
                    }
                ]
            }
        )
        result = await router.route_evidence(SITUATIONS, test_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_out_of_range_situation_index_dropped(
        self, router, test_session, mock_claude_client
    ):
        _d, factors = _make_decision(test_session)
        test_session.commit()
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "evidence": [
                    {
                        "situation_index": 99,
                        "factor_id": factors[0].id,
                        "direction": "supports",
                        "epistemic_status": "consensus",
                        "excerpt": "x",
                    }
                ]
            }
        )
        result = await router.route_evidence(SITUATIONS, test_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_bad_direction_defaults_neutral(self, router, test_session, mock_claude_client):
        _d, factors = _make_decision(test_session)
        test_session.commit()
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "evidence": [
                    {
                        "situation_index": 0,
                        "factor_id": factors[0].id,
                        "direction": "garbage",
                        "epistemic_status": "also garbage",
                        "excerpt": "The Fed held rates steady.",
                    }
                ]
            }
        )
        result = await router.route_evidence(SITUATIONS, test_session)
        assert len(result) == 1
        assert result[0].direction == "neutral"
        assert result[0].epistemic_status == "speculation"

    @pytest.mark.asyncio
    async def test_empty_excerpt_dropped(self, router, test_session, mock_claude_client):
        _d, factors = _make_decision(test_session)
        test_session.commit()
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "evidence": [
                    {
                        "situation_index": 0,
                        "factor_id": factors[0].id,
                        "direction": "supports",
                        "epistemic_status": "consensus",
                        "excerpt": "   ",
                    }
                ]
            }
        )
        result = await router.route_evidence(SITUATIONS, test_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_llm_failure_routes_nothing(self, router, test_session, mock_claude_client):
        _make_decision(test_session)
        test_session.commit()
        mock_claude_client.analyze.side_effect = RuntimeError("API down")
        result = await router.route_evidence(SITUATIONS, test_session)
        assert result == []


class TestBuildDecisionSummary:
    def test_empty_evidence(self, test_session):
        assert NarrativeSynthesizer._build_decision_summary([], test_session) == []

    def test_groups_by_decision(self, test_session):
        d, factors = _make_decision(
            test_session, name="housing", factors=["interest rates", "inventory"]
        )
        test_session.commit()

        routed = [
            RoutedEvidence(0, d.id, factors[0].id, "complicates", "single_source", "x"),
            RoutedEvidence(1, d.id, factors[1].id, "supports", "consensus", "y"),
        ]
        summary = NarrativeSynthesizer._build_decision_summary(routed, test_session)
        assert len(summary) == 1
        assert summary[0]["decision"] == "housing"
        factor_names = {f["name"] for f in summary[0]["factors"]}
        assert factor_names == {"interest rates", "inventory"}
        directions = {f["name"]: f["direction"] for f in summary[0]["factors"]}
        assert directions["interest rates"] == "complicates"
        assert directions["inventory"] == "supports"
