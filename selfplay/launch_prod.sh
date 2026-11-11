#!/bin/bash
# Production self-play run (inside the pod). usage: launch_prod.sh <out> [extra loop args]
OUT=$1; shift
cd /shared/allie/privacy
V=/shared/allie/wsr-pilot-20261103/venv-vllm/bin/python
PYTHONPATH=/shared/allie/privacy HOME=/tmp/home setsid nohup $V -m selfplay.loop --out $OUT --iters 14 --W 48 --G 8 \
  --probe-n 30 --cap-def 1200 --cap-att 600 --att-every 2 --workers 160 --serve-gpus 0,1,2,3,4 --train-gpu 5 \
  --lr 5e-5 --lr-att 3e-5 --p-direct 0.45 --p-ladder 0.25 --p-att 0.25 --p-base 0.05 --p-hint 0.5 "$@" \
  >> $OUT.log 2>&1 < /dev/null &
echo "launched $OUT pid=$!"
