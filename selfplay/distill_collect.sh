#!/bin/bash
# Host side: teacher (Opus 5.5) plays the defender on runs/worlds_train; parser on the pod replicas via the
# dedicated port-forward 19000-19003 (selfplay/run/distill/portforward.log). Resume-safe (skips done episodes).
cd /shared/allie/privacy
source .venv/bin/activate; source /shared/allie/.research_env 2>/dev/null
export LOCAL_LLM_URLS=http://localhost:19000,http://localhost:19001,http://localhost:19002,http://localhost:19003
export DOSSIER_SPEND_LOG=runs/spend_distill.jsonl BUDGET_USD=250
TEACHER=${TEACHER:-claude-opus-5-5}; NAME=${NAME:-distill_opus}
python -m selfplay.distill collect --teacher $TEACHER --out runs/selfplay_sft/${NAME}_episodes.jsonl --workers ${WORKERS:-24}
echo "COLLECT_EXIT $?"
