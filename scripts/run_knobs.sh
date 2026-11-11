#!/bin/bash
# Knob experiment grid (2026-11-11). Separate spend ledger so the live cross-play wave's $140 cap is untouched.
cd /shared/allie/privacy && . .venv/bin/activate && source /shared/allie/.research_env
export DOSSIER_SPEND_LOG=/shared/allie/privacy/runs/spend_knobs.jsonl BUDGET_USD=100
W=runs/worlds_knobs; O=runs/knobs
ALL="n1_r0_k2 n2_r0_k2 n4_r0_k2 n2_r1_k2 n2_r2_k2 n2_r0_k3 n2_r0_k4 null-public null-nomemo n2_r0_k2_persona"
LADDER="n2_r0_k2 n2_r1_k2 n2_r2_k2 null-public null-nomemo n2_r0_k2_persona"
LLM="n1_r0_k2 n2_r0_k2 n4_r0_k2 n2_r1_k2 n2_r2_k2 n2_r0_k3 n2_r0_k4 null-public"
seeds() { case $1 in n1*) echo 100-119;; n4*) echo 400-419;; *) echo 200-219;; esac; }
seeds10() { case $1 in n1*) echo 100-109;; n4*) echo 400-409;; *) echo 200-209;; esac; }
echo "=== stage 1: scripted-direct, 4 holders"
for a in $ALL; do
  python -m dossier.run --worlds $W/$a --out $O/$a --holders vanilla,vanilla@claude-sonnet-5-5,vanilla@claude-haiku-5-5,vanilla@google/gemini-3.8-flash --seekers scripted-direct --seeds $(seeds $a) --workers 6
done
echo "=== stage 2: scripted-ladder, 3 Claude holders"
for a in $LADDER; do
  python -m dossier.run --worlds $W/$a --out $O/$a --holders vanilla,vanilla@claude-sonnet-5-5,vanilla@claude-haiku-5-5 --seekers scripted-ladder --seeds $(seeds $a) --workers 6
done
echo "=== stage 3: LLM seekers (Opus 5.5 strong, Haiku 5.5 weak) vs Sonnet/Haiku holders, 10 questions"
for a in $LLM; do
  python -m dossier.run --worlds $W/$a --out $O/$a --holders vanilla@claude-sonnet-5-5,vanilla@claude-haiku-5-5 --seekers llm-direct@claude-opus-5-5,llm-direct@claude-haiku-5-5 --seeds $(seeds10 $a) --workers 6 --turns 10
done
echo "=== ALL DONE $(date)"
