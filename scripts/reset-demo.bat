@echo off
REM Reset the demo environment: close PRs, close issues, wipe local DB.
REM Usage: scripts\reset-demo.bat [--keep-issues]
REM
REM Requires: GITHUB_TOKEN env var with repo scope
REM Tip: run "set GITHUB_TOKEN=ghp_..." or load from .env first

setlocal enabledelayedexpansion

if "%SUPERSET_REPO%"=="" set "SUPERSET_REPO=bsunders/superset"
set "API=https://api.github.com"
set "KEEP_ISSUES=false"

if "%~1"=="--keep-issues" set "KEEP_ISSUES=true"

if "%GITHUB_TOKEN%"=="" (
    echo ERROR: GITHUB_TOKEN env var is required
    echo Run: set GITHUB_TOKEN=ghp_your_token_here
    exit /b 1
)

set "AUTH=Authorization: token %GITHUB_TOKEN%"
set "ACCEPT=Accept: application/vnd.github.v3+json"

echo === Closing open PRs ===
set "PR_COUNT=0"
for /f "delims=" %%i in ('curl -s -H "%AUTH%" -H "%ACCEPT%" "%API%/repos/%SUPERSET_REPO%/pulls?state=open&per_page=100" ^| python -c "import json,sys;[print(pr['number']) for pr in json.load(sys.stdin)]" 2^>nul') do (
    echo   Closing PR #%%i...
    curl -s -X PATCH -H "%AUTH%" -H "%ACCEPT%" "%API%/repos/%SUPERSET_REPO%/pulls/%%i" -d "{\"state\":\"closed\"}" >nul
    set /a PR_COUNT+=1
)
echo   Closed !PR_COUNT! PR(s)

if "%KEEP_ISSUES%"=="false" (
    echo.
    echo === Closing issues labeled 'devin-remediate' ===
    set "ISSUE_COUNT=0"
    for /f "delims=" %%i in ('curl -s -H "%AUTH%" -H "%ACCEPT%" "%API%/repos/%SUPERSET_REPO%/issues?labels=devin-remediate&state=open&per_page=100" ^| python -c "import json,sys;[print(i['number']) for i in json.load(sys.stdin) if 'pull_request' not in i]" 2^>nul') do (
        echo   Closing issue #%%i...
        curl -s -X PATCH -H "%AUTH%" -H "%ACCEPT%" "%API%/repos/%SUPERSET_REPO%/issues/%%i" -d "{\"state\":\"closed\"}" >nul
        set /a ISSUE_COUNT+=1
    )
    echo   Closed !ISSUE_COUNT! issue(s)
)

echo.
echo === Deleting branches created by Devin ===
set "BRANCH_COUNT=0"
for /f "delims=" %%b in ('curl -s -H "%AUTH%" -H "%ACCEPT%" "%API%/repos/%SUPERSET_REPO%/branches?per_page=100" ^| python -c "import json,sys;[print(b['name']) for b in json.load(sys.stdin) if b['name'].startswith('devin/')]" 2^>nul') do (
    echo   Deleting branch %%b...
    curl -s -X DELETE -H "%AUTH%" -H "%ACCEPT%" "%API%/repos/%SUPERSET_REPO%/git/refs/heads/%%b" >nul
    set /a BRANCH_COUNT+=1
)
echo   Deleted !BRANCH_COUNT! branch(es)

echo.
echo === Wiping local database ===
if "%DB_PATH%"=="" set "DB_PATH=data\remediation.db"
if exist "%DB_PATH%" (
    del "%DB_PATH%"
    echo   Deleted %DB_PATH%
) else (
    echo   No database found at %DB_PATH%
)

echo.
echo === Demo reset complete ===
echo You can now restart the orchestrator and re-trigger issues.
echo.
echo Quick re-run:
echo   docker-compose down ^&^& docker-compose up --build
echo   curl -X POST http://localhost:8000/api/trigger-all

endlocal
