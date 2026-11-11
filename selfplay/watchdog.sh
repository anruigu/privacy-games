#!/bin/bash
# Host-side watchdog: if the pod was replaced (Kueue preemption) or the loop died, bring the servers back and
# resume the loop from state.json. Stops when selfplay/run/WATCHDOG_STOP exists. Log: selfplay/run/watchdog.log
cd /shared/allie/privacy
OUT=${1:-selfplay/run/exp1}
LOG=selfplay/run/watchdog.log
while [ ! -f selfplay/run/WATCHDOG_STOP ]; do
  POD=$(kubectl get pods -n fleet-train-jobs -l job-name=${JOB:-allie-privacyzero-a3} --field-selector=status.phase=Running -o name 2>/dev/null | head -1 | cut -d/ -f2)
  if [ -z "$POD" ]; then echo "$(date -u +%H:%M:%S) no running pod" >> $LOG; sleep 120; continue; fi
  if [ "$POD" != "$(cat selfplay/run/POD_NAME)" ]; then echo "$(date -u +%H:%M:%S) pod replaced: $POD" >> $LOG; echo $POD > selfplay/run/POD_NAME; fi
  RUNNING=$(timeout 30 kubectl exec -n fleet-train-jobs $POD -- bash -c 'ps aux | grep -c "selfplay.loo[p]"' 2>/dev/null)
  if [ "$RUNNING" = "0" ] && [ ! -f $OUT/DONE ]; then
    echo "$(date -u +%H:%M:%S) loop not running on $POD; relaunching (the loop reuses healthy servers, starts missing ones)" >> $LOG
    timeout 60 kubectl exec -n fleet-train-jobs $POD -- bash /shared/allie/privacy/selfplay/launch_prod.sh $OUT >> $LOG 2>&1
    sleep 600
  fi
  sleep 120
done
