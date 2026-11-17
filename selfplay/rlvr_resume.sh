#!/bin/bash
# Host side: bring up a replacement pod (job_a7.yaml already applied), start the replicas + port-forward, then hand over to
# rlvr_orchestrate.sh, whose loops resume from each arm's state.json. usage: setsid nohup bash selfplay/rlvr_resume.sh &
cd /shared/allie/privacy
NS=fleet-train-jobs; JOB=${JOB:-allie-privacyzero-a7}; LOG=selfplay/run/rlvr_orchestrator.log
log() { echo "$(date -u +'%m-%d %H:%M:%S') $*" >> $LOG; }
log "resume: waiting for $JOB"
while true; do
  [ -f selfplay/run/RLVR_STOP ] && exit 0
  POD=$(kubectl get pods -n $NS -l job-name=$JOB -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
  PH=$(kubectl get pod -n $NS $POD -o jsonpath='{.status.phase}' 2>/dev/null)
  [ "$PH" = Running ] && [ -f selfplay/run/POD_READY ] && break
  sleep 30
done
echo $POD > selfplay/run/POD_NAME; log "pod $POD ready"
for i in 0 1 2 3; do kubectl exec -n $NS $POD -- bash -c "MAX_LORAS=12 bash /shared/allie/privacy/selfplay/start_vllm.sh $i $((8000+i))" >> $LOG 2>&1; done
for i in 0 1 2 3; do until kubectl exec -n $NS $POD -- curl -sf localhost:$((8000+i))/v1/models > /dev/null 2>&1; do sleep 20; [ -f selfplay/run/RLVR_STOP ] && exit 0; done; log "replica $i up"; done
pkill -f "kubectl port-forward -n $NS" 2>/dev/null
(setsid nohup bash -c "while true; do kubectl port-forward -n $NS $POD 18000:8000 18001:8001 18002:8002 18003:8003 >> selfplay/run/portforward.log 2>&1; sleep 3; done" > /dev/null 2>&1 < /dev/null &)
sleep 5; log "port-forward up; starting orchestrator"
exec bash ${ORCH:-selfplay/rlvr_orchestrate.sh}
