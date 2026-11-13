#!/bin/bash
# Entry point for the 1-GPU distillation training pod: idle for kubectl exec until selfplay/run/distill/POD_STOP.
set -x
mkdir -p /tmp/home
export HOME=/tmp/home HF_HOME=/shared/allie/privacy/selfplay/hf
nvidia-smi -L
echo READY > /shared/allie/privacy/selfplay/run/distill/POD_READY
while [ ! -f /shared/allie/privacy/selfplay/run/distill/POD_STOP ]; do sleep 30; done
