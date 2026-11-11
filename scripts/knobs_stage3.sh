#!/bin/bash
source /shared/allie/privacy/scripts/knobs_common.sh
echo "=== stage 3: LLM seekers (Opus strong, Haiku weak) vs Sonnet/Haiku holders, 10 questions -> runs/knobs_llm/<arm>"
for a in $LLM; do
  python -m dossier.run --worlds $W/$a --out runs/knobs_llm/$a --holders vanilla@claude-sonnet-5-5,vanilla@claude-haiku-5-5 --seekers llm-direct@claude-opus-5-5,llm-direct@claude-haiku-5-5 --seeds $(seeds10 $a) --workers 6 --turns 10
done
echo "=== STAGE 3 DONE $(date)"
