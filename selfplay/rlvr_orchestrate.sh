#!/bin/bash
# Host orchestrator for the RLVR-vs-self-play arms (launch_rlvr.sh). rlvr on gpu 4; drlvr then dsp on gpu 5.
# Evals (held-out, Sonnet parser) queue per arm on a separate ledger. Stop: touch selfplay/run/RLVR_STOP (loops finish their iteration).
cd /shared/allie/privacy
NS=fleet-train-jobs; POD=$(cat selfplay/run/POD_NAME); LOG=selfplay/run/rlvr_orchestrator.log
log() { echo "$(date -u +'%m-%d %H:%M:%S') $*" >> $LOG; }
export DOSSIER_SPEND_LOG=runs/spend_rlvr.jsonl BUDGET_USD=120
export LOCAL_LLM_URLS=http://localhost:18000,http://localhost:18001,http://localhost:18002,http://localhost:18003
launch() {  # $1 arm $2 gpu $3.. eval checkpoints
  local arm=$1 gpu=$2; shift 2
  kubectl exec -n $NS $POD -- bash /shared/allie/privacy/selfplay/launch_rlvr.sh $arm $gpu >> $LOG 2>&1
  (setsid nohup bash -c "PREFIX=${arm}_ bash selfplay/eval_when_ready.sh $arm $*" > /dev/null 2>&1 < /dev/null &)
  log "launched $arm on gpu $gpu (evals: $*)"
}
launch rlvr  4 rlvr_def_it01 rlvr_def_it02 rlvr_def_it03 rlvr_def_it05
launch drlvr 5 drlvr_def_it01 drlvr_def_it03
while [ ! -f selfplay/run/drlvr/DONE ]; do
  sleep 120
  [ -f selfplay/run/RLVR_STOP ] && { log "RLVR_STOP"; exit 0; }
  PH=$(kubectl get pod -n $NS $POD -o jsonpath='{.status.phase}' 2>/dev/null); [ "$PH" != Running ] && { log "pod gone ($PH)"; exit 1; }
done
log "drlvr done"
launch dsp 5 dsp_def_it01 dsp_def_it03
while [ ! -f selfplay/run/dsp/DONE ] || [ ! -f selfplay/run/rlvr/DONE ]; do sleep 120; [ -f selfplay/run/RLVR_STOP ] && exit 0; done
log "all arms done"
