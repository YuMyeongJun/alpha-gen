#!/usr/bin/env bash
# Alpha-Gen ops watch loop for Cursor /loop integration (bash).
# Emits a fixed sentinel every N seconds (default 5 minutes).

set -euo pipefail

INTERVAL_SEC="${ALPHA_GEN_WATCH_INTERVAL_SEC:-300}"
PROMPT='alpha-gen ops watch: MCP health_check, get_safety_policy, get_worker_status 요약. 이상 시 alpha-gen-incident skill 적용.'

while true; do
  sleep "${INTERVAL_SEC}"
  payload=$(python -c "import json; print(json.dumps({'prompt': '''${PROMPT}'''}, ensure_ascii=False))")
  printf 'AGENT_LOOP_TICK_ALPHA_GEN_OPS %s\n' "${payload}"
done
