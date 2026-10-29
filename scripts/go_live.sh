#!/usr/bin/env bash
# Decision Ladder: go live on Nebius Token Factory in one command (macOS / Linux).
#   bash scripts/go_live.sh
set -u
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
$PY -c 'import sys; assert sys.version_info >= (3,10)' || { echo "Python 3.10+ required"; exit 1; }
if [ -z "${NEBIUS_API_KEY:-}" ]; then read -rsp "Nebius Token Factory API key (hidden): " NEBIUS_API_KEY; echo; export NEBIUS_API_KEY; fi
if [ -z "${TAVILY_API_KEY:-}" ]; then read -rsp "Tavily API key (optional, Enter to skip): " T; echo; [ -n "$T" ] && export TAVILY_API_KEY="$T"; fi
echo "== 1/4 models";  $PY -m decision_ladder models || exit 1
echo "== 2/4 smoke";   $PY -m decision_ladder smoke; SMOKE=$?
echo "== 3/4 eval";    $PY -m decision_ladder eval
[ $SMOKE -ne 0 ] && echo "Smoke test had failures: see smoke_report.json"
echo "== 4/4 serving on http://localhost:8000"
$PY -m decision_ladder serve 8000
