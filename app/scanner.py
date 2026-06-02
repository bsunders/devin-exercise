"""Vulnerability scanner that runs pip-audit / npm audit and files GitHub issues."""

import json
import logging
import subprocess
from dataclasses import dataclass
from typing import Optional

from app import github_client

logger = logging.getLogger(__name__)

REMEDIATION_LABEL = "devin-remediate"


@dataclass
class Finding:
    package: str
    version: str
    vuln_id: str
    severity: str
    fix_version: Optional[str]
    ecosystem: str  # "python" or "npm"
    description: str = ""


def run_pip_audit(requirements_path: str = "requirements/base.txt") -> list[Finding]:
    """Run pip-audit against a requirements file and parse findings."""
    try:
        result = subprocess.run(
            ["pip-audit", "-r", requirements_path, "--no-deps", "-f", "json", "-o", "-"],
            capture_output=True, text=True, timeout=120,
        )
        # pip-audit returns non-zero when vulns are found
        output = result.stdout or result.stderr
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            # Try to find JSON in the output
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("[") or line.startswith("{"):
                    try:
                        data = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue
            else:
                logger.warning("Could not parse pip-audit JSON output")
                return _run_pip_audit_text(requirements_path)

        findings = []
        dependencies = data if isinstance(data, list) else data.get("dependencies", [])
        for dep in dependencies:
            for vuln in dep.get("vulns", []):
                findings.append(Finding(
                    package=dep["name"],
                    version=dep["version"],
                    vuln_id=vuln.get("id", "UNKNOWN"),
                    severity="high",  # pip-audit doesn't provide severity
                    fix_version=vuln.get("fix_versions", [None])[0] if vuln.get("fix_versions") else None,
                    ecosystem="python",
                    description=vuln.get("description", ""),
                ))
        logger.info("pip-audit found %d vulnerabilities", len(findings))
        return findings

    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.error("pip-audit failed: %s", exc)
        return []


def _run_pip_audit_text(requirements_path: str) -> list[Finding]:
    """Fallback: parse pip-audit text output."""
    try:
        result = subprocess.run(
            ["pip-audit", "-r", requirements_path, "--no-deps"],
            capture_output=True, text=True, timeout=120,
        )
        output = result.stdout + result.stderr
        findings = []
        for line in output.splitlines():
            line = line.strip()
            # Format: "name  version  vuln_id  fix_versions"
            parts = line.split()
            if len(parts) >= 3 and parts[2].startswith(("CVE-", "PYSEC-", "GHSA-")):
                fix_ver = parts[3] if len(parts) > 3 else None
                findings.append(Finding(
                    package=parts[0],
                    version=parts[1],
                    vuln_id=parts[2],
                    severity="high",
                    fix_version=fix_ver,
                    ecosystem="python",
                ))
        return findings
    except Exception as exc:
        logger.error("pip-audit text fallback failed: %s", exc)
        return []


def run_npm_audit(package_dir: str = "superset-frontend") -> list[Finding]:
    """Run npm audit and parse findings."""
    try:
        result = subprocess.run(
            ["npm", "audit", "--json"],
            capture_output=True, text=True, timeout=120,
            cwd=package_dir,
        )
        data = json.loads(result.stdout)
        findings = []
        for name, vuln in data.get("vulnerabilities", {}).items():
            severity = vuln.get("severity", "unknown")
            if severity in ("critical", "high"):
                findings.append(Finding(
                    package=name,
                    version=vuln.get("range", "unknown"),
                    vuln_id=vuln.get("via", [{}])[0].get("url", "") if isinstance(vuln.get("via", [None])[0], dict) else "",
                    severity=severity,
                    fix_version=vuln.get("fixAvailable", {}).get("version") if isinstance(vuln.get("fixAvailable"), dict) else None,
                    ecosystem="npm",
                    description=vuln.get("title", ""),
                ))
        logger.info("npm audit found %d high/critical vulnerabilities", len(findings))
        return findings

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as exc:
        logger.error("npm audit failed: %s", exc)
        return []


def build_issue_body(finding: Finding) -> str:
    """Build a structured GitHub issue body for a finding."""
    fix_info = f"**Fix version:** `{finding.fix_version}`" if finding.fix_version else "**Fix version:** No fix available yet"
    return f"""## Security Vulnerability: {finding.vuln_id}

**Package:** `{finding.package}` (current: `{finding.version}`)
**Severity:** {finding.severity.upper()}
**Ecosystem:** {finding.ecosystem}
{fix_info}

### Description
{finding.description or 'See vulnerability database for details.'}

### Remediation Instructions
{"Upgrade `" + finding.package + "` from `" + finding.version + "` to `" + finding.fix_version + "` in the project dependencies. Update any code that may break due to API changes in the new version. Run the test suite to verify nothing is broken." if finding.fix_version else "Investigate whether this package can be replaced with a safe alternative, or pin to a version without the vulnerability if one exists. If the package is unused, remove it."}

### Acceptance Criteria
- [ ] Vulnerability `{finding.vuln_id}` is no longer reported by scanner
- [ ] All existing tests pass
- [ ] PR links back to this issue

---
*Auto-generated by Security Remediation Pipeline*
_Label: `{REMEDIATION_LABEL}`_
"""


async def scan_and_file_issues(
    repo_path: str,
    dry_run: bool = False,
) -> list[dict]:
    """Run scans, create GitHub issues for findings, return created issues."""
    await github_client.ensure_label_exists(REMEDIATION_LABEL)

    # Run scanners
    python_findings = run_pip_audit(f"{repo_path}/requirements/base.txt")
    npm_findings = run_npm_audit(f"{repo_path}/superset-frontend")
    all_findings = python_findings + npm_findings

    if not all_findings:
        logger.info("No vulnerabilities found!")
        return []

    created_issues = []
    for finding in all_findings:
        title = f"[{finding.severity.upper()}] {finding.vuln_id}: Upgrade {finding.package} ({finding.ecosystem})"
        body = build_issue_body(finding)

        if dry_run:
            logger.info("[DRY RUN] Would create issue: %s", title)
            created_issues.append({"title": title, "finding": finding})
            continue

        try:
            issue = await github_client.create_issue(
                title=title,
                body=body,
                labels=[REMEDIATION_LABEL],
            )
            created_issues.append(issue)
        except Exception as exc:
            logger.error("Failed to create issue for %s: %s", finding.vuln_id, exc)

    logger.info("Created %d issues from %d findings", len(created_issues), len(all_findings))
    return created_issues
