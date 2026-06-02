#!/bin/bash
# Auto-sync: regenerate dashboards and commit+push whenever Claude stops.
# Runs as a Stop hook — only acts if there are uncommitted changes.
set -e
cd /home/user/Analista

# Nothing to do if working tree is clean
if git status --short | grep -q .; then
    python main.py analyze 2>/dev/null || true
    git add docs/over25_dashboard.html docs/football_dashboard.html docs/today_dashboard.html \
            *.py 2>/dev/null || true
    if ! git diff --cached --quiet; then
        git commit -m "chore: auto-sync dashboards and code changes"
        git push origin main 2>/dev/null || true
    fi
fi
