#!/bin/bash
# Rolling restart of replicas (gpu=port-8000) in compiled mode; reloads the adapters named in the run's state.json.
# usage: restart_compiled.sh <run_dir> gpu [gpu ...]
RUN=$1; shift
cd /shared/allie/privacy
for g in "$@"; do
  port=$((8000+g))
  pkill -f "port ${port}$" ; pkill -f "port ${port} "; sleep 4
  EAGER=0 bash selfplay/start_vllm.sh $g $port
  for i in $(seq 1 120); do grep -q "Application startup complete" selfplay/run/vllm_$port.log && break; sleep 5; done
  for name in $(python3 -c "import json;s=json.load(open('$RUN/state.json'));print(' '.join(v for v in (s['def'],s['att']) if v!='base'))"); do
    curl -s -X POST localhost:$port/v1/load_lora_adapter -H "Content-Type: application/json" -d "{\"lora_name\":\"$name\",\"lora_path\":\"$(realpath $RUN)/ckpt/$name\"}" > /dev/null
  done
  echo "replica $port up (compiled), adapters reloaded"
done
