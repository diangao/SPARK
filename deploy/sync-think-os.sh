#!/bin/bash
# Think OS Git Sync Script
# Pulls latest changes and pushes any local changes to daily logs
# Add to cron: */5 * * * * /opt/spark/deploy/sync-think-os.sh >> /var/log/think-os-sync.log 2>&1

THINK_OS_PATH="${THINK_OS_PATH:-/root/think-os}"
cd "$THINK_OS_PATH"

# Configure git (first run)
git config user.email "spark@bot.local"
git config user.name "Spark Bot"

# Pull latest changes (merge, not rebase - avoids getting stuck)
echo "[$(date)] Pulling..."
git pull --no-rebase || {
    echo "[$(date)] Pull failed, attempting to resolve..."
    # Accept remote version on conflict
    git checkout --theirs .
    git add -A
    git commit -m "Spark auto-sync: resolve conflict" || true
}

# Only sync daily logs and learned.md (not state.json which changes constantly)
DAILY_CHANGES=$(git status --porcelain memory/timeline/daily/ memory/spark/learned.md 2>/dev/null)

if [[ -n "$DAILY_CHANGES" ]]; then
    echo "[$(date)] Daily log changes detected, pushing..."
    git add memory/timeline/daily/ memory/spark/learned.md
    git commit -m "Spark auto-sync"
    git push || echo "[$(date)] Push failed"
else
    echo "[$(date)] No daily log changes"
fi
