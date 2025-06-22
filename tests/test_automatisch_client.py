import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import shared.automatisch_client as ac


@pytest.mark.asyncio
async def test_create_flow():
    with patch.object(ac, "httpx", autospec=True) as mock_httpx:
        mock_client = AsyncMock()
        response = MagicMock()
        response.json.return_value = {"id": 1}
        response.raise_for_status.return_value = None
        mock_client.post.return_value = response
        mock_httpx.AsyncClient.return_value = mock_client

        client = ac.AutomatischClient(base_url="http://x", api_key="key")
        result = await client.create_flow({"a": 1})

        mock_client.post.assert_awaited_with("/flows", json={"a": 1})
        assert result == {"id": 1}


@pytest.mark.asyncio
async def test_run_and_get_runs():
    with patch.object(ac, "httpx", autospec=True) as mock_httpx:
        mock_client = AsyncMock()
        post_resp = MagicMock()
        post_resp.json.return_value = {"run": 1}
        post_resp.raise_for_status.return_value = None
        get_resp = MagicMock()
        get_resp.json.return_value = [{"id": 1}]
        get_resp.raise_for_status.return_value = None
        mock_client.post.return_value = post_resp
        mock_client.get.return_value = get_resp
        mock_httpx.AsyncClient.return_value = mock_client

        client = ac.AutomatischClient(base_url="http://x", api_key="key")
        run = await client.run_flow(3, {"a": 2})
        runs = await client.get_runs(3)

        mock_client.post.assert_awaited_with("/flows/3/runs", json={"a": 2})
        mock_client.get.assert_awaited_with("/flows/3/runs")
        assert run == {"run": 1}
        assert runs == [{"id": 1}]
