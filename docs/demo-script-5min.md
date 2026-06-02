# 5-Minute Demo Script — Security Remediation Pipeline with Devin
**Audience: VP Engineering + Senior ICs | Format: Loom screen recording with voiceover**

---

## PRE-RECORDING SETUP (do this 30+ minutes BEFORE you hit record)

### Step 1: Set up the pipeline (one-time)
```bash
# In your devin-exercise directory
source .env                                          # load tokens
./scripts/reset-demo.sh                              # clean slate
docker-compose down && docker-compose up --build     # restart fresh
./scripts/create-issues.sh                           # create 4 issues
curl -X POST http://localhost:8000/api/trigger-all   # launch Devin sessions
```

### Step 2: Wait for Devin to finish (~15-20 min)
- Check `http://localhost:8000` — dashboard will show sessions completing
- Check `https://github.com/bsunders/superset/pulls` — wait until 4 PRs are open
- **Don't record until all 4 PRs are open and dashboard shows "completed"**

### Step 3: Open these browser tabs (left to right, BEFORE recording)
1. **Dashboard** — `http://localhost:8000` (should show 4 completed, 4 PRs)
2. **GitHub Issues** — `https://github.com/bsunders/superset/issues` (4 issues with labels)
3. **Issue #1 detail** — click the Flask issue to get the URL
4. **PR: Flask** — the Flask upgrade PR (find in open PRs list)
5. **PR: Flask Files Changed** — same PR, click "Files changed" tab
6. **PR: eslint malware** — the eslint plugin rename PR
7. **PR: Paramiko** — the Paramiko investigation PR
8. **Devin session** — `https://app.devin.ai` → find one of the completed sessions (log in first)
9. **Code: main.py** — `https://github.com/bsunders/devin-exercise/blob/initial-setup/app/main.py`
10. **Code: devin_client.py** — `https://github.com/bsunders/devin-exercise/blob/initial-setup/app/devin_client.py`

**NOTE:** Tab URLs will use whatever issue/PR numbers get created in your run.
The numbers change each time you reset. Just navigate to them manually.

### Step 4: Hit record
- Loom screen + webcam
- Have this script open on a second monitor or printed

---

## 0:00–1:15 — WHAT: Problem Framing

### SCREEN: GitHub Issues page (tab 2)
*Show the 4 issues with `devin-remediate` labels visible*

**SAY:**
> "I'm going to show you how we can turn one of the most painful workflows in engineering — security vulnerability remediation — into a fully automated pipeline powered by Devin.
>
> Here's the reality: I took a fresh fork of Apache Superset — a real, production open-source project with over 60,000 stars — and ran a vulnerability scan. Within seconds, it found **4 real security issues**."

*Slowly scroll through the issues so viewers can read the titles*

> "We've got **CVE-2026-27205** — a vulnerability in Flask, the core web framework. **PYSEC-2026-113** — a PyArrow vulnerability. **CVE-2026-44405** — a cryptographic weakness in Paramiko, which handles SSH tunneling. And a **critical one** — an eslint plugin that shares its name with a known malware package on npm.
>
> Today, each of these is a ticket that sits in someone's backlog. An engineer has to pick it up, research the CVE, figure out the upgrade path, handle breaking changes, run the tests, and open a PR. That's **2 to 4 hours per vulnerability** — and most teams are dealing with dozens of these every quarter.
>
> **What if we could go from scan result to reviewable pull request in under 15 minutes, with zero engineer time?** That's what this system does."

**WHY THIS MATTERS:** *You're establishing the business pain. Every VP has a backlog of unfixed CVEs and knows the compliance pressure.*

---

## 1:15–1:45 — HOW (Part 1): The Dashboard

### SCREEN: Dashboard (tab 1)
*Show http://localhost:8000 — it should already show 4 completed sessions and 4 PRs*

**SAY:**
> "This is the observability dashboard — the single pane of glass for the entire pipeline. Across the top you can see the key metrics: **total issues tracked, sessions completed, PRs opened, and the overall success rate.**
>
> Below that is the task table. Each row is one vulnerability — you can see the issue number, the CVE ID, the current status, a direct link to the Devin session that worked on it, and the resulting pull request. This auto-refreshes every 15 seconds.
>
> If I were an engineering leader, this dashboard answers the question: **'Is this thing working, and where are we at?'**"

**WHY THIS MATTERS:** *You're showing observability — one of the three deliverables they asked for. Keep it brief — the dashboard speaks for itself.*

---

## 1:45–2:15 — HOW (Part 2): How the Pipeline Works

### SCREEN: Stay on Dashboard, or briefly show the terminal

**SAY:**
> "Let me explain how this pipeline gets triggered. There are three modes:
>
> **One** — a GitHub webhook. When someone adds the `devin-remediate` label to any issue, the webhook fires and a Devin session starts automatically. This is the production mode.
>
> **Two** — manual trigger. I can hit this button on the dashboard, or run a curl command from the CLI. This kicks off Devin sessions for every open issue with that label. That's what I used to launch the 4 sessions you see here.
>
> **Three** — the built-in scanner. It clones the repo, runs `pip-audit` and `npm audit`, and files GitHub issues automatically. Full end-to-end from scan to Devin session in one API call.
>
> Under the hood, for each issue, the orchestrator calls the **Devin REST API** with a detailed prompt that includes the CVE ID, the affected package, the current version, the fix version, and specific remediation instructions tailored to this codebase."

**WHY THIS MATTERS:** *You're showing event-driven architecture — another key requirement. The three trigger modes show flexibility.*

---

## 2:15–3:15 — HOW (Part 3): What Devin Actually Did — The PRs

### SCREEN: PR: Flask (tab 4)
*Show the PR description*

**SAY:**
> "Now let's look at what Devin actually produced. This is the Flask upgrade PR. Devin upgraded Flask from 2.3.3 to 3.1.3 — but here's the interesting part."

### SCREEN: PR: Flask Files Changed (tab 5)
*Show the diff — three files changed*

> "Look at the diff. It's not just a version bump. Devin found that **Flask 3.x removed the `flask.escape` function** — a breaking change. It traced the usage to a test file, and migrated the import to `markupsafe.escape`. That's the kind of thing that breaks CI if you just bump the version blindly.
>
> Devin also checked for other Flask 3.x breaking APIs — `JSONEncoder`, `before_first_request`, `flask.Markup` — and confirmed none of them were used in the codebase. That's engineer-level analysis, not just find-and-replace."

### SCREEN: PR: eslint malware (tab 6)
*Show the PR summary*

> "Here's an even more impressive one. The eslint malware package — Devin didn't just delete it. It realized that Superset has a **local plugin** with the same name as the malware package. So instead of removing functionality, it **renamed the plugin** to `eslint-plugin-superset-i18n`, updated all the ESLint configs, and preserved every lint rule. Zero functional changes, supply-chain risk eliminated."

### SCREEN: PR: Paramiko (tab 7)
*Show the investigation table and DSSKey shim section*

> "And for Paramiko — there was no simple version bump available at first glance. Devin **researched the CVE**, found that paramiko 5.0.0 fixed it, but discovered that `sshtunnel` — a downstream dependency — still references a class that was removed in paramiko 4.0. So Devin **wrote a compatibility shim** and documented the risk. This is the kind of remediation that would take a senior engineer 2-3 hours of investigation."

**WHY THIS MATTERS:** *This is the money section. Each PR demonstrates a different level of complexity that goes beyond what any bump bot can do. Spend the most time here.*

---

## 3:15–3:50 — HOW (Part 4): Architecture Walkthrough

### SCREEN: main.py on GitHub (tab 9)
*Scroll through the key sections*

**SAY:**
> "Quick architecture walkthrough. The entire system is about **400 lines of Python** in a FastAPI app.
>
> The main orchestrator handles webhook events, manual triggers, and runs a background poller that checks Devin session status every 30 seconds."

### SCREEN: devin_client.py on GitHub (tab 10)

> "The Devin client is a thin wrapper around the v3 REST API — `create_session`, `get_session`, `list_sessions`. The prompt template is where the real leverage is — we give Devin the CVE context, the affected files, and specific instructions for this codebase.
>
> State tracking uses SQLite — lightweight, zero-config, perfect for this use case. The whole thing ships as a single Docker container — `docker-compose up` and you're running."

**WHY THIS MATTERS:** *Senior ICs will care about the code quality and architecture decisions. Keep it fast — they can read the code later.*

---

## 3:50–4:30 — WHY: Devin as Core Primitive

### SCREEN: Stay on code, or switch back to Dashboard

**SAY:**
> "So why Devin specifically? Why not Dependabot, Renovate, or a custom script?
>
> **Dependabot can bump a version number. Devin understands what breaks when you do.**
>
> Traditional tools operate at the dependency graph level — they see version A needs to become version B. But they have no understanding of your codebase. When Flask removed `flask.escape`, Dependabot would open a PR that breaks your CI. Devin found the breaking import, fixed it, and verified the test suite.
>
> When the eslint package was flagged as malware, a scanner would tell you to remove it. Devin understood it was a **local plugin with the same name**, and chose to rename instead of delete — preserving your team's custom lint rules.
>
> When paramiko needed a major version jump, Devin didn't just bump and pray. It researched the CVE, found the fix, identified the downstream compatibility issue, and **wrote a shim**. That's engineering judgment.
>
> **Devin isn't a helper in this system — it's the entire remediation engine.** The orchestrator just manages the workflow. That's the key insight: you can treat Devin as a programmable engineer that scales horizontally. Four CVEs, four parallel sessions, four PRs — all produced simultaneously."

**WHY THIS MATTERS:** *This is the "why Devin" pitch. Use specific examples from the PRs — concrete beats abstract.*

---

## 4:30–5:00 — WHEN: Next Steps

### SCREEN: Dashboard (tab 1)

**SAY:**
> "If I were rolling this out in a real customer engagement, here's how I'd extend it:
>
> **First** — connect to existing security tooling. Replace the built-in scanner with webhooks from Snyk, SonarQube, or GitHub's own Dependabot alerts. The orchestrator doesn't care where findings come from — it just needs an issue with a label.
>
> **Second** — add Slack and PagerDuty integration. When a PR is ready for review, notify the team. When a session fails, escalate.
>
> **Third** — expand beyond security. The same event-driven, issue-to-PR pattern works for **any ticket-to-code workflow**: Jira ticket remediation, code quality debt burndown, deprecated API migration, even automated test generation.
>
> The ROI math is simple: if your team handles **50 CVEs per quarter at 3 hours each, that's 150 engineer-hours**. This system handles them in minutes. That's like getting an extra engineer focused purely on security — except they work 24/7 and never context-switch.
>
> The code is open source, runs in a single Docker container, and the README has full setup instructions. Happy to go deeper on any of this."

**WHY THIS MATTERS:** *End with a concrete roadmap and ROI number. VPs think in headcount and quarters.*

---

## KEY NUMBERS TO DROP NATURALLY

| Number | Where to mention it |
|--------|-------------------|
| **4 real CVEs found** | Problem framing (0:00) |
| **4 PRs produced, zero human code** | After showing the PRs (3:15) |
| **~400 lines of Python** | Architecture section (3:15) |
| **Sub-15-minute** end-to-end | Problem framing or close |
| **150 engineer-hours/quarter saved** | ROI in closing (4:30) |
| **2-4 hours per CVE manually** | Problem framing (0:00) |

---

## RECORDING TIPS

- **Set up ONCE, then record.** Don't reset right before recording — let Devin finish first so all 4 PRs are ready. You're presenting results, not waiting for them live.
- **Pace yourself.** 5 minutes feels short but you have plenty of material. Don't rush.
- **Pause on each PR for 5-10 seconds** so viewers can read the summary.
- **Move your mouse to highlight** what you're talking about — the diff lines, the metrics cards, the session links.
- **Don't read PR descriptions verbatim** — summarize the key insight from each.
- **Keep your webcam on** (Loom default) — it builds trust with the VP audience.
- **If something is still loading**, talk through it: "While this loads, what's happening is..."
- **Practice once** with the script open on a second monitor, then record for real.

---

## BETWEEN PRACTICE RUNS (only if you want to start fresh)

```bash
# Full reset — will take ~20 min before you can record again
./scripts/reset-demo.sh
docker-compose down && docker-compose up --build
./scripts/create-issues.sh
curl -X POST http://localhost:8000/api/trigger-all
# Wait 15-20 min for Devin sessions to finish and PRs to appear
```

```cmd
REM Windows equivalent
scripts\reset-demo.bat
docker-compose down && docker-compose up --build
scripts\create-issues.bat
curl -X POST http://localhost:8000/api/trigger-all
REM Wait 15-20 min for Devin sessions to finish and PRs to appear
```
