@echo off
REM Create the 4 security issues in the Superset fork.
REM Usage: scripts\create-issues.bat
REM
REM Requires: GITHUB_TOKEN env var with repo scope
REM Tip: run "set GITHUB_TOKEN=ghp_..." or load from .env first

python "%~dp0create_issues.py"
if errorlevel 1 (
    echo.
    echo Script failed. Make sure GITHUB_TOKEN is set and python is on PATH.
    exit /b 1
)
