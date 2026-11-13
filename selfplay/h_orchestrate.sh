#!/bin/bash
# Host-side orchestrator for the helpfulness arms (HELPFUL_RL.md): waits for the pod, starts the vLLM replicas,
# runs the arms on the free training GPUs, keeps a port-forward up and queues the held-out evals.
#   setsid nohup bash selfplay/h_orchestrate.sh > /dev/null 2>&1 &      stop: touch selfplay/run/H_STOP
cd /shared/allie/privacy
LOG=selfplay/run/h_orchestrator.log
NS=fleet-train-jobs
log() { echo "$(date -u +%m-%d\ %H:%M:%S) $*" >> $LOG; }
log "orchestrator start"
# 1. wait for the pod
while true; do
  [ -f selfplay/run/H_STOP ] && { log "H_STOP"; exit 0; }
  POD=$(kubectl get pods -n $NS -l job-name=allie-privacyzero-a6 -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
  PH=$(kubectl get pod -n $NS $POD -o jsonpath='{.status.phase}' 2>/dev/null)
  if [ "$PH" = Running ] && [ -f selfplay/run/POD_READY ]; then break; fi
  sleep 60
done
echo $POD > selfplay/run/POD_NAME
log "pod $POD ready"
NGPU=$(kubectl get pod -n $NS $POD -o jsonpath='{.spec.containers[0].resources.limits.nvidia\.com/gpu}')
if [ "$NGPU" -ge 8 ]; then SERVE="0,1,2,3,4"; TRAIN=(5 6 7); else SERVE="0,1,2,3"; TRAIN=(4 5); fi
log "gpus=$NGPU serve=$SERVE train=${TRAIN[*]}"
# 2. replicas
IFS=, read -ra SG <<< "$SERVE"
for i in "${!SG[@]}"; do
  kubectl exec -n $NS $POD -- bash -c "MAX_LORAS=12 bash /shared/allie/privacy/selfplay/start_vllm.sh ${SG[$i]} $((8000+i))" >> $LOG 2>&1
done
for i in "${!SG[@]}"; do
  until kubectl exec -n $NS $POD -- curl -sf localhost:$((8000+i))/v1/models > /dev/null 2>&1; do sleep 20; [ -f selfplay/run/H_STOP ] && exit 0; done
  log "replica $i up"
done
# 3. port-forward (18000.. -> 8000..) for the host-side evals
pkill -f "kubectl port-forward -n $NS" 2>/dev/null
(setsid nohup bash -c "while true; do kubectl port-forward -n $NS $POD 18000:8000 18001:8001 18002:8002 18003:8003 18004:8004 >> selfplay/run/portforward.log 2>&1; sleep 3; done" > /dev/null 2>&1 < /dev/null &)
URLS=""; for i in "${!SG[@]}"; do URLS="$URLS,http://localhost:$((18000+i))"; done; export LOCAL_LLM_URLS=${URLS#,}
log "LOCAL_LLM_URLS=$LOCAL_LLM_URLS"
# 4. arms: per training GPU a queue; sft_h (warm start for h5) runs first on the first GPU
sed -i "s/--serve-gpus 0,1,2,3,4/--serve-gpus $SERVE/" selfplay/launch_h.sh
if [ ${#TRAIN[@]} -ge 3 ]; then Q0="sft_h h5"; Q1="h1 h3"; Q2="h4 h2"; else Q0="sft_h h5 h2"; Q1="h1 h4 h3"; Q2=""; fi
QUEUES=("$Q0" "$Q1" "$Q2")
declare -A CUR
launch() {  # $1 arm $2 gpu
  if [ "$1" = sft_h ]; then kubectl exec -n $NS $POD -- bash /shared/allie/privacy/selfplay/train_sft_h.sh $2 >> $LOG 2>&1
  else kubectl exec -n $NS $POD -- bash /shared/allie/privacy/selfplay/launch_h.sh $1 $2 >> $LOG 2>&1
       (setsid nohup bash -c "PREFIX=${1}_ bash selfplay/eval_when_ready.sh $1 ${1}_def_it01 ${1}_def_it03" > /dev/null 2>&1 < /dev/null &)
  fi
  log "launched $1 on gpu $2"; CUR[$2]=$1
}
finished() {  # $1 arm
  if [ "$1" = sft_h ]; then [ -f selfplay/run/h5/ckpt/sft_h/train_summary.json ]; else [ -f selfplay/run/$1/DONE ]; fi
}
for i in "${!TRAIN[@]}"; do
  q=(${QUEUES[$i]}); [ ${#q[@]} -gt 0 ] && { launch ${q[0]} ${TRAIN[$i]}; QUEUES[$i]="${q[*]:1}"; }
done
while true; do
  sleep 120
  [ -f selfplay/run/H_STOP ] && { log "H_STOP"; exit 0; }
  PH=$(kubectl get pod -n $NS $POD -o jsonpath='{.status.phase}' 2>/dev/null)
  [ "$PH" != Running ] && { log "pod gone ($PH); stopping"; exit 1; }
  busy=0
  for i in "${!TRAIN[@]}"; do
    g=${TRAIN[$i]}; a=${CUR[$g]}
    if [ -n "$a" ] && finished $a; then
      log "finished $a on gpu $g"; CUR[$g]=""
      q=(${QUEUES[$i]}); [ ${#q[@]} -gt 0 ] && { launch ${q[0]} $g; QUEUES[$i]="${q[*]:1}"; }
    fi
    [ -n "${CUR[$g]}" ] && busy=1
  done
  [ $busy = 0 ] && { log "all arms done"; break; }
done
