#!/bin/bash
# Entry point for the self-play pod: stage the base model into the shared HF cache, then idle for kubectl exec.
set -x
mkdir -p /tmp/home
export HOME=/tmp/home HF_HOME=/shared/allie/privacy/selfplay/hf
nvidia-smi -L
PY=/shared/allie/wsr-pilot-20261103/venv-vllm/bin/python
$PY -c "import vllm, torch; print('vllm', vllm.__version__, 'torch', torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
$PY - <<'PYEOF'
from huggingface_hub import snapshot_download
for m in ["Qwen/Qwen3-8B"]:
    p = snapshot_download(m, allow_patterns=["*.json", "*.safetensors", "*.txt", "*.jinja"])
    print("staged", m, p)
PYEOF
echo READY > /shared/allie/privacy/selfplay/run/POD_READY
while [ ! -f /shared/allie/privacy/selfplay/run/POD_STOP ]; do sleep 30; done
