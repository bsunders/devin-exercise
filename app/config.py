"""Configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # Devin API
    devin_api_key: str = field(default_factory=lambda: os.environ.get("DEVIN_API_KEY", ""))
    devin_org_id: str = field(default_factory=lambda: os.environ.get("DEVIN_ORG_ID", ""))
    devin_api_base: str = "https://api.devin.ai"

    # GitHub
    github_token: str = field(default_factory=lambda: os.environ.get("GITHUB_TOKEN", ""))
    github_webhook_secret: str = field(
        default_factory=lambda: os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    )
    superset_repo: str = field(
        default_factory=lambda: os.environ.get("SUPERSET_REPO", "bsunders/superset")
    )

    # Polling
    poll_interval_seconds: int = 30
    max_poll_duration_seconds: int = 3600  # 1 hour max per session

    # Database
    db_path: str = field(
        default_factory=lambda: os.environ.get("DB_PATH", "data/remediation.db")
    )


settings = Settings()
