#!/bin/bash
# Host side: evaluate checkpoints as they appear. usage: eval_when_ready.sh exp1 def_it03 def_it06 ...
RUN=$1; shift
cd /shared/allie/privacy
source .venv/bin/activate; source /shared/allie/.research_env 2>/dev/null
export LOCAL_LLM_URLS=${LOCAL_LLM_URLS:-http://localhost:18000,http://localhost:18001,http://localhost:18002,http://localhost:18003,http://localhost:18004}
export DOSSIER_SPEND_LOG=${DOSSIER_SPEND_LOG:-runs/spend_selfplay.jsonl} BUDGET_USD=${BUDGET_USD:-250}
for L in "$@"; do
  while [ ! -f selfplay/run/$RUN/ckpt/$L/train_summary.json ]; do sleep 120; done
  sleep 30
  TAG=${PREFIX:-}${L##*def_}
  echo "$(date -u +%H:%M:%S) evaluating $L -> $TAG" >> selfplay/run/eval_queue.log
  python -m selfplay.eval_ckpt --lora $L --tag $TAG --run selfplay/run/$RUN --workers 12 > runs/selfplay_eval_$TAG.log 2>&1
  echo "$(date -u +%H:%M:%S) done $L: $(tail -1 runs/selfplay_eval_$TAG.log)" >> selfplay/run/eval_queue.log
done
