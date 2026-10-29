#!/usr/bin/env bash
# Commit any changed project files every 20 minutes (generated data folders are git-ignored).
cd "$(dirname "$0")/.."
while true; do
  if [ -n "$(git status --porcelain)" ]; then
    git add -A && git commit -q -m "Auto-save $(date '+%Y-%m-%d %H:%M')

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" && echo "$(date '+%H:%M') committed"
  else
    echo "$(date '+%H:%M') nothing to commit"
  fi
  sleep 1200
done
