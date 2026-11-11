cd /shared/allie/privacy && . .venv/bin/activate && source /shared/allie/.research_env 2>/dev/null
export DOSSIER_SPEND_LOG=/shared/allie/privacy/runs/spend_knobs.jsonl BUDGET_USD=100
W=runs/worlds_knobs
ALL="n1_r0_k2 n2_r0_k2 n4_r0_k2 n2_r1_k2 n2_r2_k2 n2_r0_k3 n2_r0_k4 null-public null-nomemo n2_r0_k2_persona"
LADDER="n2_r0_k2 n2_r1_k2 n2_r2_k2 null-public null-nomemo n2_r0_k2_persona"
LLM="n2_r0_k2 n2_r0_k3 n2_r0_k4 n1_r0_k2 n4_r0_k2 n2_r1_k2 n2_r2_k2 null-public"
seeds() { case $1 in n1*) echo 100-119;; n4*) echo 400-419;; *) echo 200-219;; esac; }
seeds10() { case $1 in n1*) echo 100-109;; n4*) echo 400-409;; *) echo 200-209;; esac; }
