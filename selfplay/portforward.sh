#!/bin/bash
# keep a port-forward to the pod's vLLM replicas alive (host side): 1800x -> 800x
while true; do
  POD=$(cat /shared/allie/privacy/selfplay/run/POD_NAME)
  kubectl port-forward -n fleet-train-jobs $POD 18000:8000 18001:8001 18002:8002 18003:8003 18004:8004 >> /shared/allie/privacy/selfplay/run/portforward.log 2>&1
  echo "port-forward exited $(date -u +%H:%M:%S), restarting" >> /shared/allie/privacy/selfplay/run/portforward.log
  sleep 3
done
