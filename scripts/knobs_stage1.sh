#!/bin/bash
source /shared/allie/privacy/scripts/knobs_common.sh
echo "=== stage 1: scripted-direct, 4 holders -> runs/knobs/<arm>"
for a in $ALL; do
  python -m dossier.run --worlds $W/$a --out runs/knobs/$a --holders vanilla,vanilla@claude-sonnet-5-5,vanilla@claude-haiku-5-5,vanilla@google/gemini-3.8-flash --seekers scripted-direct --seeds $(seeds $a) --workers 8
done
echo "=== STAGE 1 DONE $(date)"
