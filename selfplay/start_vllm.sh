#!/bin/bash
# usage: start_vllm.sh <gpu> <port> [extra args]   (run inside the pod; fully detached)
GPU=$1; PORT=$2; shift 2
EAGER=${EAGER-0}   # default: torch.compile + CUDA graphs (patched triton); EAGER=1 for --enforce-eager
V=/shared/allie/wsr-pilot-20261103/venv-vllm
RUN=/shared/allie/privacy/selfplay/run
mkdir -p /tmp/home $RUN
cd $RUN
CUDA_VISIBLE_DEVICES=$GPU HOME=/tmp/home HF_HOME=/shared/allie/privacy/selfplay/hf VLLM_ALLOW_RUNTIME_LORA_UPDATING=1 \
  setsid nohup $V/bin/python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-8B --served-model-name base \
  --enable-lora --max-loras ${MAX_LORAS-8} --max-lora-rank 32 --max-model-len 8192 --gpu-memory-utilization 0.85 \
  --port $PORT --dtype bfloat16 $([ "$EAGER" = 1 ] && echo --enforce-eager) --disable-log-requests "$@" > vllm_$PORT.log 2>&1 < /dev/null &
echo "started gpu=$GPU port=$PORT pid=$!"
