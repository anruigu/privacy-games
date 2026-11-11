#!/bin/bash
source /shared/allie/privacy/scripts/knobs_common.sh
echo "=== stage 2: scripted-ladder, 3 Claude holders -> runs/knobs_ladder/<arm>"
for a in $LADDER; do
  python -m dossier.run --worlds $W/$a --out runs/knobs_ladder/$a --holders vanilla,vanilla@claude-sonnet-5-5,vanilla@claude-haiku-5-5 --seekers scripted-ladder --seeds $(seeds $a) --workers 6
done
echo "=== STAGE 2 DONE $(date)"
