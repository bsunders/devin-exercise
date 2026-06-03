"""FastAPI application: webhook receiver, orchestrator, dashboard, and manual triggers."""

import asyncio
import hashlib
import hmac
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app import devin_client, github_client, models, scanner
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REMEDIATION_LABEL = "devin-remediate"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize DB and start background poller on startup."""
    models.init_db()
    logger.info("Database initialized")
    # Start the background session poller
    task = asyncio.create_task(poll_sessions_loop())
    yield
    task.cancel()


app = FastAPI(
    title="Devin Security Remediation Pipeline",
    description="Event-driven automation for vulnerability remediation using Devin",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_devin_prompt(issue: dict) -> str:
    """Build a detailed prompt for Devin from a GitHub issue."""
    return f"""You are working on the repository https://github.com/{settings.superset_repo}.

## Task
Fix the following security/code-quality issue:

**Issue #{issue['number']}:** {issue['title']}

{issue['body']}

## Instructions
1. Clone the repository and create a new branch for this fix.
2. Analyze the vulnerability or issue described above.
3. Make the necessary code changes to remediate it:
   - For dependency upgrades: update the version pin in the requirements file or package.json, then check for any breaking API changes in downstream code.
   - For package removals: remove the package and migrate any functionality it provided.
   - For code quality fixes: make the code changes described in the issue.
4. Run relevant tests to verify the fix doesn't break anything.
5. Create a pull request with a clear description that references issue #{issue['number']}.
   - Use the PR title format: `fix(security): {issue['title']}`
   - Link the issue: "Fixes #{issue['number']}"

## Important
- Do NOT skip tests. Run the relevant test suite.
- If a dependency upgrade causes breaking changes, fix them.
- Keep the PR focused on this single issue.
"""


# ---------------------------------------------------------------------------
# GitHub Webhook
# ---------------------------------------------------------------------------

def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook HMAC signature."""
    if not settings.github_webhook_secret:
        return True  # Skip verification if no secret configured
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    """Receive GitHub issue webhook events and trigger Devin sessions."""
    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not verify_github_signature(payload, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    event_type = request.headers.get("X-GitHub-Event", "")
    data = json.loads(payload)

    if event_type == "issues":
        action = data.get("action", "")
        issue = data.get("issue", {})
        labels = [l["name"] for l in issue.get("labels", [])]

        # Trigger on issue opened or labeled with our label
        if action in ("opened", "labeled") and REMEDIATION_LABEL in labels:
            logger.info(
                "Webhook: issue #%s '%s' — triggering remediation",
                issue["number"], issue["title"],
            )
            background_tasks.add_task(trigger_remediation, issue)
            return {"status": "triggered", "issue": issue["number"]}

    return {"status": "ignored", "event": event_type}


# ---------------------------------------------------------------------------
# Manual triggers
# ---------------------------------------------------------------------------

@app.post("/api/scan")
async def trigger_scan(background_tasks: BackgroundTasks) -> dict:
    """Manually trigger a vulnerability scan and issue creation."""
    repo_path = f"/tmp/superset-scan"
    background_tasks.add_task(_run_scan, repo_path)
    return {"status": "scan_started", "repo": settings.superset_repo}


async def _run_scan(repo_path: str) -> None:
    """Run the scanner in the background."""
    import subprocess
    # Shallow clone for scanning
    if not __import__("os").path.exists(f"{repo_path}/.git"):
        subprocess.run(
            ["git", "clone", "--depth=1",
             f"https://github.com/{settings.superset_repo}.git", repo_path],
            timeout=300,
        )
    issues = await scanner.scan_and_file_issues(repo_path)
    logger.info("Scan complete: %d issues filed", len(issues))


@app.post("/api/trigger/{issue_number}")
async def trigger_single_issue(
    issue_number: int,
    background_tasks: BackgroundTasks,
) -> dict:
    """Manually trigger remediation for a specific issue number."""
    # Check if already tracked
    existing = models.get_task_by_issue(issue_number)
    if existing and existing["session_status"] in ("running", "completed"):
        return {
            "status": "already_tracked",
            "session_id": existing.get("session_id"),
            "session_status": existing["session_status"],
        }

    issue = await github_client.get_issue(issue_number)
    background_tasks.add_task(trigger_remediation, issue)
    return {"status": "triggered", "issue": issue_number, "title": issue["title"]}


@app.post("/api/load-issues")
async def load_open_issues() -> dict:
    """Import open GitHub issues with devin-remediate label into the dashboard (without triggering Devin)."""
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{settings.superset_repo}/issues",
            headers={
                "Authorization": f"token {settings.github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={"labels": REMEDIATION_LABEL, "state": "open"},
        )
        resp.raise_for_status()
        issues = resp.json()

    loaded = 0
    skipped = 0
    for issue in issues:
        if "pull_request" in issue:
            continue
        existing = models.get_task_by_issue(issue["number"])
        if existing:
            skipped += 1
            continue

        cve_id = None
        for word in issue["title"].split():
            if word.startswith(("CVE-", "PYSEC-", "GHSA-")):
                cve_id = word.rstrip(":")
                break

        models.create_task(
            issue_number=issue["number"],
            issue_url=issue["html_url"],
            issue_title=issue["title"],
            cve_id=cve_id,
            status="open",
        )
        loaded += 1

    return {"status": "loaded", "loaded": loaded, "skipped": skipped, "total": len(issues)}


@app.post("/api/trigger-all")
async def trigger_all_issues(background_tasks: BackgroundTasks) -> dict:
    """Trigger remediation for ALL open issues with the devin-remediate label."""
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{settings.superset_repo}/issues",
            headers={
                "Authorization": f"token {settings.github_token}",
                "Accept": "application/vnd.github.v3+json",
            },
            params={"labels": REMEDIATION_LABEL, "state": "open"},
        )
        resp.raise_for_status()
        issues = resp.json()

    triggered = []
    for issue in issues:
        existing = models.get_task_by_issue(issue["number"])
        if existing and existing["session_status"] in ("running", "completed"):
            continue
        background_tasks.add_task(trigger_remediation, issue)
        triggered.append(issue["number"])

    return {"status": "triggered", "issues": triggered, "total": len(triggered)}


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------

async def trigger_remediation(issue: dict) -> None:
    """Create a Devin session to remediate a GitHub issue."""
    issue_number = issue["number"]
    issue_url = issue["html_url"]
    issue_title = issue["title"]

    # Extract CVE ID from title if present
    cve_id = None
    for word in issue_title.split():
        if word.startswith(("CVE-", "PYSEC-", "GHSA-")):
            cve_id = word.rstrip(":")
            break

    # Reuse existing task record if loaded via load-issues, otherwise create new
    existing = models.get_task_by_issue(issue_number)
    if existing and existing["session_status"] in ("open", "pending"):
        task_id = existing["id"]
    else:
        task_id = models.create_task(
            issue_number=issue_number,
            issue_url=issue_url,
            issue_title=issue_title,
            cve_id=cve_id,
        )

    # Build prompt and create Devin session
    prompt = build_devin_prompt(issue)
    try:
        session = await devin_client.create_session(
            prompt=prompt,
            title=f"Fix: {issue_title}",
            tags=["security-remediation", cve_id or "code-quality"],
        )
        models.update_task_session(
            task_id=task_id,
            session_id=session["session_id"],
            session_url=session["url"],
        )
        logger.info(
            "Devin session created for issue #%s: %s",
            issue_number, session["url"],
        )
    except Exception as exc:
        logger.error("Failed to create Devin session for issue #%s: %s", issue_number, exc)
        models.update_task_status(task_id, "failed", error_message=str(exc))


# ---------------------------------------------------------------------------
# Background poller
# ---------------------------------------------------------------------------

async def poll_sessions_loop() -> None:
    """Periodically check status of running Devin sessions."""
    while True:
        try:
            await poll_running_sessions()
        except Exception as exc:
            logger.error("Polling error: %s", exc)
        await asyncio.sleep(settings.poll_interval_seconds)


async def poll_running_sessions() -> None:
    """Check all running sessions and update their status."""
    running_tasks = models.get_running_tasks()
    for task in running_tasks:
        session_id = task["session_id"]
        if not session_id:
            continue

        try:
            session = await devin_client.get_session(session_id)
            status = session.get("status", "unknown")

            if status in ("finished", "stopped"):
                # Check for PR
                pr_url = session.get("pull_request", {}).get("url") if session.get("pull_request") else None
                pr_number = session.get("pull_request", {}).get("number") if session.get("pull_request") else None
                models.update_task_status(
                    task_id=task["id"],
                    status="completed" if pr_url else "completed",
                    pr_url=pr_url,
                    pr_number=pr_number,
                )
                logger.info(
                    "Session %s completed. PR: %s",
                    session_id, pr_url or "none",
                )
            elif status == "failed":
                error = session.get("status_info", "Unknown error")
                models.update_task_status(
                    task_id=task["id"],
                    status="failed",
                    error_message=str(error),
                )
                logger.warning("Session %s failed: %s", session_id, error)

        except Exception as exc:
            logger.error("Error polling session %s: %s", session_id, exc)


# ---------------------------------------------------------------------------
# Dashboard & API
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Render the observability dashboard."""
    tasks = models.get_all_tasks()
    metrics = models.get_metrics()
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "tasks": tasks,
            "metrics": metrics,
            "repo": settings.superset_repo,
        },
    )


@app.get("/api/metrics")
async def api_metrics() -> dict:
    """Return pipeline metrics as JSON."""
    return models.get_metrics()


@app.get("/api/tasks")
async def api_tasks() -> list[dict]:
    """Return all tracked tasks."""
    return models.get_all_tasks()


@app.post("/api/reset")
async def reset_dashboard() -> dict:
    """Clear all tasks from the dashboard database."""
    count = models.reset_db()
    logger.info("Dashboard reset: %d tasks cleared", count)
    return {"status": "reset", "tasks_cleared": count}


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "repo": settings.superset_repo}
