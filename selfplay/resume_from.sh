#!/bin/bash
# usage: resume_from.sh <it> <def_adapter> <att_adapter>   (host) — writes state in the pod, relaunches the loop, restarts the watchdog
cd /shared/allie/privacy
POD=$(cat selfplay/run/POD_NAME)
timeout 60 kubectl exec -n fleet-train-jobs $POD -- bash -c "cd /shared/allie/privacy/selfplay/run/exp1 && python3 -c \"import json; json.dump({'it': $1, 'def': '$2', 'att': '$3'}, open('state.json','w'))\" && cat state.json && bash /shared/allie/privacy/selfplay/launch_prod.sh selfplay/run/exp1"
rm -f selfplay/run/WATCHDOG_STOP
(setsid nohup bash selfplay/watchdog.sh selfplay/run/exp1 > /dev/null 2>&1 < /dev/null &)
sleep 1; echo "watchdogs: $(pgrep -fc 'watchdog.s[h]')"
