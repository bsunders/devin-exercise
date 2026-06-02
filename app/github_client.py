"""GitHub API client for creating issues and reading repo data."""

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"token {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
    }


async def create_issue(
    title: str,
    body: str,
    labels: Optional[list[str]] = None,
) -> dict:
    """Create a GitHub issue in the target Superset fork."""
    payload: dict = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{settings.superset_repo}/issues",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        logger.info("Created issue #%s: %s", data["number"], data["html_url"])
        return data


async def add_label(issue_number: int, label: str) -> None:
    """Add a label to an existing issue."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{settings.superset_repo}/issues/{issue_number}/labels",
            headers=_headers(),
            json={"labels": [label]},
        )
        resp.raise_for_status()


async def get_issue(issue_number: int) -> dict:
    """Get issue details."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{settings.superset_repo}/issues/{issue_number}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def ensure_label_exists(label: str, color: str = "d73a4a") -> None:
    """Create the label if it doesn't exist."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{settings.superset_repo}/labels/{label}",
            headers=_headers(),
        )
        if resp.status_code == 404:
            await client.post(
                f"{GITHUB_API}/repos/{settings.superset_repo}/labels",
                headers=_headers(),
                json={
                    "name": label,
                    "color": color,
                    "description": "Automated remediation by Devin",
                },
            )
            logger.info("Created label '%s'", label)
