"""Devin API v3 client for creating and monitoring sessions."""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = f"{settings.devin_api_base}/v3/organizations/{settings.devin_org_id}"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.devin_api_key}",
        "Content-Type": "application/json",
    }


async def create_session(
    prompt: str,
    title: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Create a new Devin session and return {session_id, url}."""
    payload: dict = {"prompt": prompt}
    if title:
        payload["title"] = title
    if tags:
        payload["tags"] = tags

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/sessions",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Created Devin session %s: %s", data["session_id"], data["url"])
        return data


async def get_session(session_id: str) -> dict:
    """Retrieve current session details including status and pull_request info."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/sessions/{session_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def send_message(session_id: str, message: str) -> dict:
    """Send a follow-up message to a running session."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{BASE_URL}/sessions/{session_id}/messages",
            headers=_headers(),
            json={"message": message},
        )
        resp.raise_for_status()
        return resp.json()


async def list_sessions(
    limit: int = 20,
    status: Optional[str] = None,
) -> list[dict]:
    """List recent sessions, optionally filtered by status."""
    params: dict = {"limit": limit}
    if status:
        params["status"] = status

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/sessions",
            headers=_headers(),
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", data.get("sessions", []))
