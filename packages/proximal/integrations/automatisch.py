from __future__ import annotations
import os
import httpx


def trigger_workflow(workflow_id: str, payload: dict) -> bool:
    """Trigger an Automatisch workflow if the base URL is configured."""
    base = os.getenv("AUTOMATISCH_URL")
    if not base:
        return False
    url = f"{base}/api/v1/workflows/{workflow_id}/runs"
    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()
        return True
    except Exception:
        return False
