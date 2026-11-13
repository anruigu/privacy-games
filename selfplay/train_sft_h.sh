#!/bin/bash
# Train the balanced warm start (H5) inside the pod on one GPU. usage: train_sft_h.sh <gpu>
cd /shared/allie/privacy; mkdir -p selfplay/run/h5/ckpt
export CUDA_VISIBLE_DEVICES=$1 HOME=/tmp/home HF_HOME=/shared/allie/privacy/selfplay/hf PYTHONPATH=/shared/allie/privacy
PY=/shared/allie/Inferencebench-runs/loop-2x2-20261030/venv/bin/python
setsid nohup $PY -m selfplay.train_lora --data runs/selfplay_sft/sft_h.jsonl --adapter-in "" --adapter-out selfplay/run/h5/ckpt/sft_h --lr 5e-5 --beta 0 --clip-eps 10 >> selfplay/run/sft_h.log 2>&1 < /dev/null &
echo "sft_h training on gpu $1 pid $!"
