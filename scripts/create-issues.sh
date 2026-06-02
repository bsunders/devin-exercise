#!/usr/bin/env bash
# Create the 4 security issues in the Superset fork.
# Usage: ./scripts/create-issues.sh
#
# Requires: GITHUB_TOKEN env var with repo scope

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/create_issues.py"
