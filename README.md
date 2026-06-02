# Devin Security Remediation Pipeline

An event-driven automation that scans [Apache Superset](https://github.com/apache/superset) for security vulnerabilities, files GitHub Issues, and uses the [Devin API](https://docs.devin.ai/api-reference/overview) to autonomously remediate them — producing pull requests, status tracking, and a live observability dashboard.

## Architecture

```
Scanner (pip-audit / npm audit)
    │
    ▼
GitHub Issues (labeled "devin-remediate")
    │
    ▼ (webhook or manual trigger)
FastAPI Orchestrator
    │
    ▼
Devin API → Devin Sessions → Pull Requests
    │
    ▼
Observability Dashboard (metrics, status, PR links)
```

### Components

| Component | File | Purpose |
|-----------|------|---------|
| **Orchestrator** | `app/main.py` | FastAPI app: webhook receiver, manual triggers, dashboard, background poller |
| **Scanner** | `app/scanner.py` | Runs `pip-audit` / `npm audit`, parses findings, creates GitHub Issues |
| **Devin Client** | `app/devin_client.py` | Devin API v3 wrapper: create sessions, poll status |
| **GitHub Client** | `app/github_client.py` | GitHub API wrapper: create issues, manage labels |
| **Models** | `app/models.py` | SQLite state tracking: tasks, metrics, scan history |
| **Dashboard** | `templates/dashboard.html` | Live HTML dashboard with auto-refresh |

## Quick Start (Docker)

### 1. Clone and configure

```bash
git clone https://github.com/bsunders/devin-exercise.git
cd devin-exercise
cp .env.example .env
```

Edit `.env` with your credentials:

```env
DEVIN_API_KEY=cog_your_key_here        # Settings → Service Users → API key
DEVIN_ORG_ID=org-your_org_id           # Same page, org ID
GITHUB_TOKEN=ghp_your_token_here       # GitHub PAT with repo scope
SUPERSET_REPO=bsunders/superset        # Your Superset fork
```

### 2. Run with Docker

```bash
docker-compose up --build
```

The dashboard is now available at **http://localhost:8000**.

### 3. Trigger the pipeline

**Option A: Manual trigger (recommended for demos)**

```bash
# Trigger remediation for all open issues labeled "devin-remediate"
curl -X POST http://localhost:8000/api/trigger-all

# Trigger a specific issue
curl -X POST http://localhost:8000/api/trigger/1
```

**Option B: Run a fresh vulnerability scan**

```bash
curl -X POST http://localhost:8000/api/scan
```

This will clone the repo, run `pip-audit` + `npm audit`, and create GitHub Issues automatically.

**Option C: GitHub webhook (production mode)**

1. In your repo settings → Webhooks, add:
   - URL: `https://your-domain/webhook/github` (use `ngrok` for local dev)
   - Content type: `application/json`
   - Secret: match your `GITHUB_WEBHOOK_SECRET`
   - Events: Issues
2. Any issue labeled `devin-remediate` will automatically trigger a Devin session.

## Running Without Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# Export env vars from .env or source it
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Observability dashboard (HTML) |
| `GET` | `/health` | Health check |
| `GET` | `/api/metrics` | Pipeline metrics (JSON) |
| `GET` | `/api/tasks` | All tracked tasks (JSON) |
| `POST` | `/api/scan` | Run vulnerability scan + create issues |
| `POST` | `/api/trigger/{issue_number}` | Trigger Devin for a specific issue |
| `POST` | `/api/trigger-all` | Trigger Devin for all open labeled issues |
| `POST` | `/webhook/github` | GitHub webhook receiver |

## Observability

The dashboard at `http://localhost:8000` shows:

- **Total Issues** — vulnerabilities found by scanner
- **Sessions Running** — active Devin sessions working on fixes
- **Completed / Failed** — success and failure counts
- **PRs Opened** — tangible output (linked to GitHub)
- **Success Rate** — percentage of issues successfully remediated
- **Avg Time to PR** — mean time from issue creation to PR

The pipeline auto-polls Devin session status every 30 seconds and updates the dashboard in real-time (15s auto-refresh).

## Issues Targeted

These real vulnerabilities were found in the Superset fork:

| Finding | Severity | Package | Fix |
|---------|----------|---------|-----|
| CVE-2026-27205 | High | flask 2.3.3 | → 3.1.3 |
| PYSEC-2026-113 | High | pyarrow 20.0.0 | → 23.0.1 |
| CVE-2026-44405 | High | paramiko 3.5.1 | Investigate |
| GHSA-55h3-fm53-wq99 | Critical | eslint-plugin-i18n-strings | Remove |

## Why Devin?

Traditional tools (Dependabot, Renovate) can bump version numbers, but they cannot:

- Understand downstream code that breaks when a dependency API changes
- Remove a compromised package and migrate its functionality to a safe alternative
- Run the project's test suite and fix test failures caused by the upgrade
- Write a meaningful PR description explaining the security impact

Devin treats each vulnerability as a full engineering task — reading the codebase, making targeted changes, verifying with tests, and producing a reviewable PR. This pipeline turns that into a scalable, automated workflow.

## License

MIT
