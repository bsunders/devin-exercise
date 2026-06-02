"""SQLite database models for tracking remediation tasks."""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional


DB_PATH = os.environ.get("DB_PATH", "data/remediation.db")


def get_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tasks (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_number    INTEGER NOT NULL,
            issue_url       TEXT NOT NULL,
            issue_title     TEXT NOT NULL,
            cve_id          TEXT,
            severity        TEXT,
            package_name    TEXT,
            session_id      TEXT,
            session_url     TEXT,
            session_status  TEXT DEFAULT 'pending',
            pr_url          TEXT,
            pr_number       INTEGER,
            error_message   TEXT,
            created_at      TEXT NOT NULL,
            started_at      TEXT,
            completed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS scan_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type       TEXT NOT NULL,
            findings_count  INTEGER DEFAULT 0,
            issues_created  INTEGER DEFAULT 0,
            started_at      TEXT NOT NULL,
            completed_at    TEXT
        );
    """)
    conn.commit()
    conn.close()


def create_task(
    issue_number: int,
    issue_url: str,
    issue_title: str,
    cve_id: Optional[str] = None,
    severity: Optional[str] = None,
    package_name: Optional[str] = None,
) -> int:
    conn = get_db()
    cursor = conn.execute(
        """INSERT INTO tasks (issue_number, issue_url, issue_title, cve_id,
           severity, package_name, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (issue_number, issue_url, issue_title, cve_id, severity, package_name,
         datetime.now(timezone.utc).isoformat()),
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id  # type: ignore[return-value]


def update_task_session(task_id: int, session_id: str, session_url: str) -> None:
    conn = get_db()
    conn.execute(
        """UPDATE tasks SET session_id = ?, session_url = ?,
           session_status = 'running', started_at = ?
           WHERE id = ?""",
        (session_id, session_url, datetime.now(timezone.utc).isoformat(), task_id),
    )
    conn.commit()
    conn.close()


def update_task_status(
    task_id: int,
    status: str,
    pr_url: Optional[str] = None,
    pr_number: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    conn = get_db()
    conn.execute(
        """UPDATE tasks SET session_status = ?, pr_url = ?, pr_number = ?,
           error_message = ?, completed_at = ?
           WHERE id = ?""",
        (status, pr_url, pr_number, error_message,
         datetime.now(timezone.utc).isoformat() if status in ("completed", "failed") else None,
         task_id),
    )
    conn.commit()
    conn.close()


def get_all_tasks() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_running_tasks() -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE session_status = 'running'"
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_task_by_issue(issue_number: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM tasks WHERE issue_number = ?", (issue_number,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_metrics() -> dict:
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE session_status = 'pending'"
    ).fetchone()[0]
    running = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE session_status = 'running'"
    ).fetchone()[0]
    completed = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE session_status = 'completed'"
    ).fetchone()[0]
    failed = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE session_status = 'failed'"
    ).fetchone()[0]
    prs = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE pr_url IS NOT NULL"
    ).fetchone()[0]

    # Average time to completion (for completed tasks)
    avg_row = conn.execute("""
        SELECT AVG(
            (julianday(completed_at) - julianday(started_at)) * 24 * 60
        ) as avg_minutes
        FROM tasks
        WHERE session_status = 'completed' AND started_at IS NOT NULL
    """).fetchone()
    avg_minutes = round(avg_row[0], 1) if avg_row[0] else None

    conn.close()
    return {
        "total": total,
        "pending": pending,
        "running": running,
        "completed": completed,
        "failed": failed,
        "prs_opened": prs,
        "success_rate": round(completed / total * 100, 1) if total > 0 else 0,
        "avg_time_to_pr_minutes": avg_minutes,
    }
