# Self-play fix log (PRIVACYZERO.md §6.11 follow-up, started 2026-11-17)

Goal: make the defender learn on the LLM-attacker channel so self-play has a chance to beat RL against fixed attackers.
Comparison metric: held-out Haiku / Sonnet ≥1-bit leak (the channel that never moved), scripted-direct leak, deception,
utility; plus P(leak | approver-attribute question) in the training rollouts (`selfplay.attacker_debug_channel`).
Baseline to beat: sft_round2 lineage, Haiku/Sonnet 0.65–1.00 at every RL checkpoint (warm start 0.95/0.95).

## Round 1 — hybrid advantage + protected key turns + 75 % LLM share (launched 2026-11-17, pod a11)

Diagnosis being fixed: turn-level advantage (group-normalised return-to-go at the same turn index) is wrongly signed on
LLM-attacker groups because the eight episodes are in different states at the same index.

Changes (`selfplay/loop.py --adv hybrid`, `selfplay/episode.py KEY_TURN_PROTECTED=1`, `selfplay/launch_rlvr.sh fx_*`):
1. `--adv hybrid`: per-turn credit for scripted groups (unchanged, it was the working signal), episode-level group
   advantage for LLM-attacker groups.
2. Turns that ask a PROTECTED fact (approver name / floor / team) count as key turns for the row cap, so the LLM
   channel is not crowded out of the 1,200 rows by the key-chain turns.
3. LLM attacker share raised to 75 % of worlds in both arms (fixed: base-prompted; self-play: trained adapter, updated
   every iteration), scripted-direct 15 %, ladder 10 %, 6 iterations, lr 3e-5, KL β 0.02, seeds 0 and 1.

Arms: fx_rlvr / fx_rlvr_s1 (fixed attackers), fx_sp / fx_sp_s1 (self-play). Evals at it01 / it03 / it05
(`runs/selfplay_eval/fx_*`). Orchestrator `selfplay/rlvr4_orchestrate.sh`, log `selfplay/run/rlvr_orchestrator.log`.

Result: pending.
