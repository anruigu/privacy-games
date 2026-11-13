#!/bin/bash
# Launch one helpfulness arm inside the pod (HELPFUL_RL.md). usage: launch_h.sh <arm> <train_gpu>
# arms: h1 penalty | h2 nullpool | h3 anchor | h4 combined | h5 combined from the balanced warm start (sft_h)
ARM=$1; GPU=$2
cd /shared/allie/privacy
RUN=selfplay/run/$ARM; mkdir -p $RUN/ckpt
COMMON="--out $RUN --iters 4 --W 48 --G 8 --cap-def 1200 --cap-att 600 --att-every 2 --probe-n 30 --serve-gpus 0,1,2,3,4 --train-gpu $GPU --prefix ${ARM}_ --vstar-baseline 0 --p-hint 0.25 --lr 3e-5 --lr-att 3e-5 --p-direct 0.45 --p-ladder 0.25 --p-att 0.25 --p-base 0.05 --probe-null 20 --workers 64"
case $ARM in
  h1) EXTRA="--w-over 0.5" ;;
  h2) EXTRA="--worlds-null runs/worlds_train_null --p-null 0.4" ;;
  h3) EXTRA="--anchor-data runs/selfplay_sft/anchor_safe.jsonl --anchor-n 300 --anchor-adv 0.5" ;;
  h4|h5) EXTRA="--w-over 0.5 --worlds-null runs/worlds_train_null --p-null 0.4 --anchor-data runs/selfplay_sft/anchor_safe.jsonl --anchor-n 300 --anchor-adv 0.5" ;;
  *) echo "unknown arm $ARM"; exit 1 ;;
esac
START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2
if [ "$ARM" = h5 ]; then START=sft_h; SRC=/shared/allie/privacy/selfplay/run/h5/ckpt/sft_h; fi
[ -e $RUN/ckpt/${ARM}_$START ] || ln -s $SRC $RUN/ckpt/${ARM}_$START
[ -f $RUN/state.json ] || echo "{\"it\": 0, \"def\": \"${ARM}_$START\", \"att\": \"base\"}" > $RUN/state.json
export HOME=/tmp/home HF_HOME=/shared/allie/privacy/selfplay/hf PYTHONPATH=/shared/allie/privacy VLLM_ALLOW_RUNTIME_LORA_UPDATING=1
V=/shared/allie/wsr-pilot-20261103/venv-vllm
setsid nohup $V/bin/python -m selfplay.loop $COMMON $EXTRA >> selfplay/run/$ARM.log 2>&1 < /dev/null &
echo "launched $ARM on train gpu $GPU pid $!"
