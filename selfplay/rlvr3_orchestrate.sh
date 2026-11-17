#!/bin/bash
# Seed study for the sft_round2 lineage (2026-11-17): gpu 4: sp_s1 -> rlvr_s1; gpu 5: sp_s2 -> rlvr_s2. Pod/replicas/port-forward up (rlvr_resume.sh).
cd /shared/allie/privacy
NS=fleet-train-jobs; POD=$(cat selfplay/run/POD_NAME); LOG=selfplay/run/rlvr_orchestrator.log
log() { echo "$(date -u +'%m-%d %H:%M:%S') $*" >> $LOG; }
export DOSSIER_SPEND_LOG=runs/spend_rlvr.jsonl BUDGET_USD=220
export LOCAL_LLM_URLS=http://localhost:18000,http://localhost:18001,http://localhost:18002,http://localhost:18003
launch() { local arm=$1 gpu=$2; shift 2
  kubectl exec -n $NS $POD -- bash /shared/allie/privacy/selfplay/launch_rlvr.sh $arm $gpu >> $LOG 2>&1
  (setsid nohup bash -c "PREFIX=${arm}_ bash selfplay/eval_when_ready.sh $arm $*" > /dev/null 2>&1 < /dev/null &)
  log "launched $arm on gpu $gpu (evals: $*)"; }
queue() { local gpu=$1; shift; for arm in "$@"; do launch $arm $gpu ${arm}_def_it01 ${arm}_def_it03; while [ ! -f selfplay/run/$arm/DONE ]; do sleep 120; [ -f selfplay/run/RLVR_STOP ] && exit 0; done; log "$arm done"; done; }
queue 4 sp_s1 rlvr_s1 &
queue 5 sp_s2 rlvr_s2 &
wait; log "seed study arms done"
