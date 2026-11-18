#!/bin/bash
# Round 5 / exploitability (2026-11-18): best-response attackers vs frozen defenders, no API evals (cross-play afterwards).
cd /shared/allie/privacy
NS=fleet-train-jobs; POD=$(cat selfplay/run/POD_NAME); LOG=selfplay/run/rlvr_orchestrator.log
log() { echo "$(date -u +'%m-%d %H:%M:%S') $*" >> $LOG; }
launch() { local arm=$1 gpu=$2; kubectl exec -n $NS $POD -- bash /shared/allie/privacy/selfplay/launch_rlvr.sh $arm $gpu >> $LOG 2>&1; log "launched $arm on gpu $gpu"; }
queue() { local gpu=$1; shift; for arm in "$@"; do launch $arm $gpu; while [ ! -f selfplay/run/$arm/DONE ]; do sleep 120; [ -f selfplay/run/RLVR_STOP ] && exit 0; done; log "$arm done"; done; }
queue 4 br_sft_round2 br_fx3_sp_it05 br_fx3_sp_s1_it05 &
queue 5 br_fx3_rlvr_it05 br_fx3_rlvr_s1_it05 br_exp2_it01 &
wait; log "round 5 best-response arms done"
