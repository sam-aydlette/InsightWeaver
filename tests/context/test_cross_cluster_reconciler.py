"""
Tests for the cross-cluster reconciler.
"""

import json

import pytest

from src.context.cross_cluster_reconciler import CrossClusterReconciler

SITUATIONS = [
    {
        "title": "Immigration debate intensifies",
        "coverage_frame": {
            "narrative_layers": "labor scarcity vs cultural identity",
            "fractures": "Whether the labor pool is constrained.",
        },
    },
    {
        "title": "Industrial policy push",
        "coverage_frame": {
            "narrative_layers": "domestic capacity vs trade efficiency",
            "fractures": "Whether the workforce can absorb new factories.",
        },
    },
    {
        "title": "Sports news",
        "coverage_frame": {
            "narrative_layers": "team rivalry storyline",
            "fractures": "Which coach is to blame.",
        },
    },
]


class TestReconciler:
    @pytest.fixture
    def reconciler(self, mock_claude_client):
        return CrossClusterReconciler(client=mock_claude_client)

    @pytest.mark.asyncio
    async def test_too_few_situations_returns_empty(self, reconciler, mock_claude_client):
        result = await reconciler.reconcile(SITUATIONS[:1])
        assert result == []
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_frame_data_returns_empty(self, reconciler, mock_claude_client):
        result = await reconciler.reconcile([{"title": "x"}, {"title": "y"}])
        assert result == []
        mock_claude_client.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_meta_fracture(self, reconciler, mock_claude_client):
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "meta_fractures": [
                    {
                        "name": "labor capacity fracture",
                        "description": "Disagreement over whether the labor pool is constrained.",
                        "situation_indices": [0, 1],
                        "shared_point": "Whether the workforce can absorb new demand.",
                    }
                ]
            }
        )
        result = await reconciler.reconcile(SITUATIONS)
        assert len(result) == 1
        mf = result[0]
        assert mf["name"] == "labor capacity fracture"
        assert mf["situation_indices"] == [0, 1]
        assert "workforce" in mf["shared_point"]

    @pytest.mark.asyncio
    async def test_out_of_range_indices_filtered(self, reconciler, mock_claude_client):
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "meta_fractures": [
                    {
                        "name": "phantom fracture",
                        "description": "x",
                        "situation_indices": [0, 99, 1],
                        "shared_point": "x",
                    }
                ]
            }
        )
        result = await reconciler.reconcile(SITUATIONS)
        # Out-of-range filtered out; 0 and 1 remain (length still >= 2).
        assert result[0]["situation_indices"] == [0, 1]

    @pytest.mark.asyncio
    async def test_single_index_meta_fracture_dropped(self, reconciler, mock_claude_client):
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "meta_fractures": [
                    {
                        "name": "x",
                        "description": "x",
                        "situation_indices": [0],
                        "shared_point": "x",
                    }
                ]
            }
        )
        result = await reconciler.reconcile(SITUATIONS)
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_required_fields_dropped(self, reconciler, mock_claude_client):
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "meta_fractures": [
                    {
                        "name": "",
                        "description": "x",
                        "situation_indices": [0, 1],
                        "shared_point": "x",
                    },
                    {
                        "name": "x",
                        "description": "x",
                        "situation_indices": [0, 1],
                        "shared_point": "",
                    },
                ]
            }
        )
        result = await reconciler.reconcile(SITUATIONS)
        assert result == []

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self, reconciler, mock_claude_client):
        mock_claude_client.analyze.side_effect = RuntimeError("down")
        result = await reconciler.reconcile(SITUATIONS)
        assert result == []

    @pytest.mark.asyncio
    async def test_dedupes_situation_indices(self, reconciler, mock_claude_client):
        mock_claude_client.analyze.return_value = json.dumps(
            {
                "meta_fractures": [
                    {
                        "name": "x",
                        "description": "x",
                        "situation_indices": [0, 0, 1, 1],
                        "shared_point": "x",
                    }
                ]
            }
        )
        result = await reconciler.reconcile(SITUATIONS)
        assert result[0]["situation_indices"] == [0, 1]
