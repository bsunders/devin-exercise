#!/usr/bin/env bash
# Reset the demo environment: close PRs, close issues, wipe local DB.
# Usage: ./scripts/reset-demo.sh
#
# Requires: GITHUB_TOKEN env var with repo scope
# Optional: pass --keep-issues to only close PRs and wipe DB

set -euo pipefail

REPO="${SUPERSET_REPO:-bsunders/superset}"
API="https://api.github.com"
KEEP_ISSUES=false

for arg in "$@"; do
  case $arg in
    --keep-issues) KEEP_ISSUES=true ;;
  esac
done

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ERROR: GITHUB_TOKEN env var is required"
  exit 1
fi

HEADERS=(-H "Authorization: token $GITHUB_TOKEN" -H "Accept: application/vnd.github.v3+json")

echo "=== Closing open PRs ==="
PRS=$(curl -s "${HEADERS[@]}" "$API/repos/$REPO/pulls?state=open&per_page=100" | python3 -c "
import json,sys
for pr in json.load(sys.stdin):
    print(pr['number'])
" 2>/dev/null || true)

for pr in $PRS; do
  echo "  Closing PR #$pr..."
  curl -s -X PATCH "${HEADERS[@]}" "$API/repos/$REPO/pulls/$pr" \
    -d '{"state":"closed"}' > /dev/null
done
echo "  Closed $(echo "$PRS" | grep -c '[0-9]' || echo 0) PR(s)"

if [ "$KEEP_ISSUES" = false ]; then
  echo ""
  echo "=== Closing issues labeled 'devin-remediate' ==="
  ISSUES=$(curl -s "${HEADERS[@]}" "$API/repos/$REPO/issues?labels=devin-remediate&state=open&per_page=100" | python3 -c "
import json,sys
for issue in json.load(sys.stdin):
    if 'pull_request' not in issue:
        print(issue['number'])
" 2>/dev/null || true)

  for issue in $ISSUES; do
    echo "  Closing issue #$issue..."
    curl -s -X PATCH "${HEADERS[@]}" "$API/repos/$REPO/issues/$issue" \
      -d '{"state":"closed"}' > /dev/null
  done
  echo "  Closed $(echo "$ISSUES" | grep -c '[0-9]' || echo 0) issue(s)"
fi

echo ""
echo "=== Deleting branches created by Devin ==="
BRANCHES=$(curl -s "${HEADERS[@]}" "$API/repos/$REPO/branches?per_page=100" | python3 -c "
import json,sys
for b in json.load(sys.stdin):
    if b['name'].startswith('devin/'):
        print(b['name'])
" 2>/dev/null || true)

for branch in $BRANCHES; do
  echo "  Deleting branch $branch..."
  curl -s -X DELETE "${HEADERS[@]}" "$API/repos/$REPO/git/refs/heads/$branch" > /dev/null
done
echo "  Deleted $(echo "$BRANCHES" | grep -c '[0-9a-z]' || echo 0) branch(es)"

echo ""
echo "=== Wiping local database ==="
DB_PATH="${DB_PATH:-data/remediation.db}"
if [ -f "$DB_PATH" ]; then
  rm "$DB_PATH"
  echo "  Deleted $DB_PATH"
else
  echo "  No database found at $DB_PATH"
fi

echo ""
echo "=== Demo reset complete ==="
echo "You can now restart the orchestrator and re-trigger issues."
echo ""
echo "Quick re-run:"
echo "  docker-compose down && docker-compose up --build"
echo "  curl -X POST http://localhost:8000/api/trigger-all"
