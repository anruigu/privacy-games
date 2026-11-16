#!/bin/bash
# Follow-up arms (2026-11-16): dsp2 on gpu 4; drlvr_s1 then dsp_s1 on gpu 5. Pod + replicas + port-forward must be up.
cd /shared/allie/privacy
NS=fleet-train-jobs; POD=$(cat selfplay/run/POD_NAME); LOG=selfplay/run/rlvr_orchestrator.log
log() { echo "$(date -u +'%m-%d %H:%M:%S') $*" >> $LOG; }
export DOSSIER_SPEND_LOG=runs/spend_rlvr.jsonl BUDGET_USD=160
export LOCAL_LLM_URLS=http://localhost:18000,http://localhost:18001,http://localhost:18002,http://localhost:18003
launch() { local arm=$1 gpu=$2; shift 2
  kubectl exec -n $NS $POD -- bash /shared/allie/privacy/selfplay/launch_rlvr.sh $arm $gpu >> $LOG 2>&1
  (setsid nohup bash -c "PREFIX=${arm}_ bash selfplay/eval_when_ready.sh $arm $*" > /dev/null 2>&1 < /dev/null &)
  log "launched $arm on gpu $gpu (evals: $*)"; }
launch dsp2 4 dsp2_def_it01 dsp2_def_it03 dsp2_def_it05
launch drlvr_s1 5 drlvr_s1_def_it01 drlvr_s1_def_it03
while [ ! -f selfplay/run/drlvr_s1/DONE ]; do sleep 120; [ -f selfplay/run/RLVR_STOP ] && exit 0; done
log "drlvr_s1 done"
launch dsp_s1 5 dsp_s1_def_it01 dsp_s1_def_it03
while [ ! -f selfplay/run/dsp_s1/DONE ] || [ ! -f selfplay/run/dsp2/DONE ]; do sleep 120; [ -f selfplay/run/RLVR_STOP ] && exit 0; done
log "follow-up arms done"
