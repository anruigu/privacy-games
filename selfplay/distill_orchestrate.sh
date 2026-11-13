#!/bin/bash
# Host-side orchestrator for the distillation baseline (selfplay/distill.py):
#   wait for the teacher collection -> build the SFT sets -> train each variant on the first free GPU
#   (the 1-GPU pod allie-privacyzero-distill, or an a6 training GPU once the helpfulness arms release it)
#   -> held-out eval (eval_ckpt) per checkpoint -> null-world helpfulness + transfer eval.
#   setsid nohup bash selfplay/distill_orchestrate.sh > /dev/null 2>&1 &      stop: touch selfplay/run/distill/STOP
cd /shared/allie/privacy
NS=fleet-train-jobs
D=selfplay/run/distill
LOG=$D/orchestrator.log
log() { echo "$(date -u +%m-%d\ %H:%M:%S) $*" >> $LOG; }
stop_requested() { [ -f $D/STOP ]; }
export LOCAL_LLM_URLS=http://localhost:19000,http://localhost:19001,http://localhost:19002,http://localhost:19003
export DOSSIER_SPEND_LOG=runs/spend_distill.jsonl BUDGET_USD=250
PYV=/shared/allie/Inferencebench-runs/loop-2x2-20261030/venv/bin/python     # training venv (torch 2.13 + peft), inside the pods
log "orchestrator start"

# 1. collection
until grep -q COLLECT_EXIT $D/collect.log 2>/dev/null; do stop_requested && exit 0; sleep 60; done
N=$(wc -l < runs/selfplay_sft/distill_opus_episodes.jsonl)
log "collection finished with $N episodes ($(tail -1 $D/collect.log))"
if [ "$N" -lt 1100 ]; then
  log "fewer than 1100 episodes: re-running collect once"
  bash selfplay/distill_collect.sh >> $D/collect.log 2>&1
  N=$(wc -l < runs/selfplay_sft/distill_opus_episodes.jsonl); log "collection now $N episodes"
fi

# 2. SFT sets
source .venv/bin/activate; source /shared/allie/.research_env 2>/dev/null
python -m selfplay.distill build --episodes runs/selfplay_sft/distill_opus_episodes.jsonl --out runs/selfplay_sft/distill_opus.jsonl --epochs 2 > $D/build.log 2>&1
python -m selfplay.distill build --episodes runs/selfplay_sft/distill_opus_episodes.jsonl --out runs/selfplay_sft/distill_opus_nothink.jsonl --epochs 2 --trace none > $D/build_nothink.log 2>&1
log "built: $(wc -l < runs/selfplay_sft/distill_opus.jsonl) rows (summary trace), $(wc -l < runs/selfplay_sft/distill_opus_nothink.jsonl) rows (no trace)"

# 3. training queue: name | data | trainer
QUEUE=("distill_opus|runs/selfplay_sft/distill_opus.jsonl|lora"
       "distill_opus_nothink|runs/selfplay_sft/distill_opus_nothink.jsonl|lora"
       "distill_opus_nll|runs/selfplay_sft/distill_opus.jsonl|sft")
mkdir -p $D/ckpt
declare -A CUR          # slot -> job name
declare -A SLOT_POD SLOT_GPU
free_slots() {           # sets FREE to the idle slots that exist; slots: dpod (distill pod gpu 0), a6g4, a6g5
  FREE=""
  if [ -f $D/POD_READY ]; then
    DPOD=$(kubectl get pods -n $NS -l job-name=allie-privacyzero-distill -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    DPH=$(kubectl get pod -n $NS $DPOD -o jsonpath='{.status.phase}' 2>/dev/null)
    [ -n "$DPOD" ] && [ "$DPH" = Running ] && { SLOT_POD[dpod]=$DPOD; SLOT_GPU[dpod]=0; FREE="$FREE dpod"; }
  fi
  A6=$(cat selfplay/run/POD_NAME 2>/dev/null)
  if [ -n "$A6" ] && [ "$(kubectl get pod -n $NS $A6 -o jsonpath='{.status.phase}' 2>/dev/null)" = Running ]; then
    grep -q "finished h2 on gpu 4" selfplay/run/h_orchestrator.log 2>/dev/null && { SLOT_POD[a6g4]=$A6; SLOT_GPU[a6g4]=4; FREE="$FREE a6g4"; }
    grep -q "finished h3 on gpu 5" selfplay/run/h_orchestrator.log 2>/dev/null && { SLOT_POD[a6g5]=$A6; SLOT_GPU[a6g5]=5; FREE="$FREE a6g5"; }
  fi
}
spawn_eval() {   # $1 name: held-out eval as soon as the adapter lands (host side, a6 replicas through the dedicated port-forward)
  local name=$1
  (setsid nohup bash -c "cd /shared/allie/privacy; source .venv/bin/activate; source /shared/allie/.research_env 2>/dev/null
     while [ ! -f $D/ckpt/$name/train_summary.json ]; do sleep 120; done; sleep 30
     echo \"\$(date -u +%H:%M:%S) evaluating $name\" >> $D/eval_queue.log
     python -m selfplay.eval_ckpt --lora $name --tag $name --run $D --workers 12 > runs/selfplay_eval_$name.log 2>&1
     echo \"\$(date -u +%H:%M:%S) done $name: \$(tail -1 runs/selfplay_eval_$name.log)\" >> $D/eval_queue.log
     python -m selfplay.helpful --tags $name --run-null > $D/helpful_$name.log 2>&1
     echo \"\$(date -u +%H:%M:%S) helpful done $name\" >> $D/eval_queue.log
     touch $D/EVAL_DONE_$name" > /dev/null 2>&1 < /dev/null &)
}
launch() {   # $1 slot $2 "name|data|trainer"
  local slot=$1; IFS='|' read -r name data trainer <<< "$2"
  local pod=${SLOT_POD[$slot]} gpu=${SLOT_GPU[$slot]}
  [ -z "$pod" ] && { log "launch $name: slot $slot has no pod, skipping"; return 1; }
  if [ -f $D/train_$name.log ]; then      # already launched by an earlier orchestrator run: adopt it
    log "adopting $name (train log exists) on $slot"; CUR[$slot]=$name; spawn_eval $name; return 0
  fi
  local mod="selfplay.train_lora"; local extra="--adapter-in '' --lr 5e-5 --beta 0 --clip-eps 10"
  [ "$trainer" = sft ] && { mod="selfplay.train_sft"; extra="--adapter-in '' --lr 5e-5"; }
  timeout 90 kubectl exec -n $NS $pod -- bash -c "cd /shared/allie/privacy && export CUDA_VISIBLE_DEVICES=$gpu HOME=/tmp/home HF_HOME=/shared/allie/privacy/selfplay/hf PYTHONPATH=/shared/allie/privacy && setsid nohup $PYV -m $mod --data $data --adapter-out $D/ckpt/$name $extra >> $D/train_$name.log 2>&1 < /dev/null & disown; echo launched" >> $LOG 2>&1
  log "launched $name on $slot ($pod gpu $gpu)"; CUR[$slot]=$name
  spawn_eval $name
}
running() { [ -n "$1" ] && [ ! -f $D/ckpt/$1/train_summary.json ]; }
while true; do
  stop_requested && { log "STOP"; exit 0; }
  free_slots
  for s in $FREE; do
    if running "${CUR[$s]}"; then continue; fi
    [ -n "${CUR[$s]}" ] && { log "finished ${CUR[$s]} on $s"; CUR[$s]=""; }
    [ ${#QUEUE[@]} -gt 0 ] && { launch $s "${QUEUE[0]}"; QUEUE=("${QUEUE[@]:1}"); }
  done
  busy=0; for s in "${!CUR[@]}"; do running "${CUR[$s]}" && busy=1; done
  [ ${#QUEUE[@]} -eq 0 ] && [ $busy = 0 ] && break
  sleep 120
done
log "all training done"

# 4. transfer eval for the primary checkpoint once its held-out eval is in
until [ -f $D/EVAL_DONE_distill_opus ]; do stop_requested && exit 0; sleep 120; done
python - <<'EOF' >> $LOG 2>&1
import os
from pathlib import Path
from selfplay.helpful import ensure_loaded
ensure_loaded("distill_opus", Path("selfplay/run/distill/ckpt/distill_opus"), os.environ["LOCAL_LLM_URLS"].split(","))
EOF
python -m selfplay.transfer_eval --holders vanilla@local/base,vanilla@local/distill_opus --out runs/selfplay_eval/transfer_distill --workers 12 > $D/transfer.log 2>&1
log "transfer eval done: $(tail -1 $D/transfer.log | cut -c1-120)"
for n in distill_opus_nothink distill_opus_nll; do until [ -f $D/EVAL_DONE_$n ]; do stop_requested && exit 0; sleep 120; done; done
log "ALL DONE"
touch $D/ALL_DONE
