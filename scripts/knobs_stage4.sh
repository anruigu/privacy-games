#!/bin/bash
# Hinted-seeker eval (2026-11-12): does telling the attacker that combinable facts exist change strategy/success?
source /shared/allie/privacy/scripts/knobs_common.sh
export BUDGET_USD=160
echo "=== stage 4a: llm-hint (generic) Opus/Haiku seekers vs Sonnet/Haiku holders -> runs/knobs_llm_hint/<arm>"
for a in n2_r0_k2 n2_r0_k3 n2_r2_k2 null-public; do
  python -m dossier.run --worlds $W/$a --out runs/knobs_llm_hint/$a --holders vanilla@claude-sonnet-5-5,vanilla@claude-haiku-5-5 --seekers llm-hint@claude-opus-5-5,llm-hint@claude-haiku-5-5 --seeds $(seeds10 $a) --workers 8 --turns 10
done
echo "=== stage 4b: llm-plan (structural) on k2, k3"
for a in n2_r0_k2 n2_r0_k3; do
  python -m dossier.run --worlds $W/$a --out runs/knobs_llm_hint/$a --holders vanilla@claude-sonnet-5-5,vanilla@claude-haiku-5-5 --seekers llm-plan@claude-opus-5-5,llm-plan@claude-haiku-5-5 --seeds $(seeds10 $a) --workers 8 --turns 10
done
echo "=== STAGE 4 DONE $(date)"
