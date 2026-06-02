#!/usr/bin/env bash
# Reset the demo environment: terminate Devin sessions, close PRs, close issues, wipe local DB.
# Usage: ./scripts/reset-demo.sh
#
# Requires: GITHUB_TOKEN env var with repo scope
#           DEVIN_API_KEY env var (for terminating Devin sessions)
# Optional: pass --keep-issues to only close PRs and wipe DB

set -euo pipefail

REPO="${SUPERSET_REPO:-bsunders/superset}"
ORG_ID="${DEVIN_ORG_ID:-org-abfe461aefd94419a481e3f913c8f6c5}"
API="https://api.github.com"
DEVIN_API="https://api.devin.ai/v3"
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

# --- Terminate active Devin sessions ---
echo "=== Terminating active Devin sessions ==="
if [ -z "${DEVIN_API_KEY:-}" ]; then
  echo "  DEVIN_API_KEY not set — skipping session termination"
  echo "  (Set DEVIN_API_KEY to also stop running Devin sessions)"
else
  SESSION_IDS=$(curl -s -H "Authorization: Bearer $DEVIN_API_KEY" \
    "$DEVIN_API/organizations/$ORG_ID/sessions?status_in=running,blocked&limit=50" | python3 -c "
import json,sys
data = json.load(sys.stdin)
for s in data.get('items', []):
    tags = s.get('tags', [])
    if 'security-remediation' in tags:
        print(s['session_id'])
" 2>/dev/null || true)

  SESSION_COUNT=0
  for sid in $SESSION_IDS; do
    echo "  Terminating session $sid..."
    curl -s -X DELETE -H "Authorization: Bearer $DEVIN_API_KEY" \
      "$DEVIN_API/organizations/$ORG_ID/sessions/devin-$sid?archive=true" > /dev/null 2>&1 || true
    SESSION_COUNT=$((SESSION_COUNT + 1))
  done
  echo "  Terminated $SESSION_COUNT session(s)"
fi

# --- Close open PRs ---
echo ""
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

# --- Close issues ---
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

# --- Delete Devin branches ---
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

# --- Wipe local DB ---
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
echo ""
echo "Next steps:"
echo "  1. Restart Docker (IMPORTANT - clears stale dashboard data):"
echo "     docker-compose down && docker-compose up --build"
echo ""
echo "  2. Recreate the 4 issues:"
echo "     ./scripts/create-issues.sh"
echo ""
echo "  3. Trigger Devin sessions:"
echo "     curl -X POST http://localhost:8000/api/trigger-all"
