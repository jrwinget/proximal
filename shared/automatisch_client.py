from __future__ import annotations

import os
from typing import Any, Dict

import httpx


class AutomatischClient:
    """Simplified async client for the Automatisch REST API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        self.base_url = base_url or os.getenv("AUTOMATISCH_BASE_URL", "")
        self.api_key = api_key or os.getenv("AUTOMATISCH_API_KEY", "")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def create_flow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = await self._client.post("/flows", json=payload)
        response.raise_for_status()
        return response.json()

    async def run_flow(
        self, flow_id: int, payload: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        response = await self._client.post(f"/flows/{flow_id}/runs", json=payload or {})
        response.raise_for_status()
        return response.json()

    async def get_runs(self, flow_id: int) -> Dict[str, Any]:
        response = await self._client.get(f"/flows/{flow_id}/runs")
        response.raise_for_status()
        return response.json()
