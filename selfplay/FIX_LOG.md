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

Iteration-0 sanity check (2026-11-17 22:30 UTC): 38 min per iteration; 1,200 rows with 896–929 from LLM-attacker episodes;
row-level advantage on approver-attribute questions now refused +0.23 (fx_sp) / +0.70 (fx_rlvr) vs leaked +0.00 / −0.12
(was −0.15…−0.37 vs ≈0 under turn-level); name questions refused +0.9 / +0.6 vs leaked −0.36 / −0.06. KL of the first
update 0.33 in both arms (same as earlier runs). Waiting for the it01 held-out evals.

**Round 1 result (2026-11-18 00:50 UTC, 4 iterations each): FAILED.** Held-out ≥1-bit leak (direct / ladder / Haiku / Sonnet):
fx_rlvr it01 0.62 / 0.77 / 0.90 / 0.90, it03 0.80 / 0.80 / 0.80 / 0.75; fx_sp it01 0.66 / 0.60 / 0.85 / 0.95, it03 0.76 / 0.80 / 0.90 / 0.90;
warm start 0.60 / 0.73 / 0.95 / 0.95. Training leak flat (0.56–0.77), utility flat (0.5), KL 0.24–0.33 per update, deception
0.06–0.07 (from 0.04). Training-time P(leak | approver-attribute question) 0.69 → 0.65 (sp) and 0.67 → 0.66 (rlvr).
Why: the episode advantage is correctly signed but diffuse — against a persistent LLM attacker a single refusal rarely
changes the episode outcome (the attacker asks the protected attributes 3–4 times per episode and the defender leaks on
another turn), so the per-row contrast on the decisive turns is ≈0 (+0.08 vs −0.00 after a decisive-turn mask on it01
rollouts), while the other nine rows of each episode carry the same advantage as noise. The scripted channel lost its
share of the batch (15 % of worlds) and drifted up. Arms killed after it04 / it03; seed-1 replicates not run.

Side findings: (i) "Which building does the approver sit in?" is a reward blind spot — building is not a fact in the
world, so the parser/oracle cannot charge it, and the attacker asks it freely (answered "Building A" at zero cost);
(ii) the oracle counts no new bits for a repeated confirmation of an already-leaked name, so under a regret signal those
turns would come out positive — guarded in round 2 (`prot_said` → advantage capped at 0).

## Round 2 — turn-local oracle regret for LLM groups (launched 2026-11-18 00:27 UTC, pod a11)

Changes on top of round 1 (`--adv hybrid --llm-vstar 3`, commit da49325): LLM-attacker groups get per-turn advantage
a_t = (r_t − r*_t) − ½·mean_group(r_t − r*_t), scaled by max(std, 0.3), clipped ±3 — the oracle's immediate reward in
the same state is the baseline, so credit is state-matched and never depends on what the attacker asks later. Scripted
groups keep the plain per-turn group credit. Answers that state a protected fact get advantage ≤ 0. Offline on fx_sp it01
rollouts (after the 1,200 cap, 522 LLM rows): leaked attribute turns −1.48, leaked name turns −1.57, leaked cover turns
−1.44, clean turns ≈ 0 (−0.24 … +0.54). Same mixture as round 1 (75 % LLM worlds), 6 iterations, evals it01/03/05.
Arms fx2_rlvr / fx2_sp (seed 0) now; fx2_*_s1 queued after them. Result: pending.

Round 2 it01 (2026-11-18 02:20 UTC): first movement on the LLM channel. Held-out direct / ladder / Haiku / Sonnet:
fx2_rlvr 0.58 / 0.60 / 0.80 / 0.75, fx2_sp 0.56 / 0.80 / 0.50 / 0.80 (warm start 0.60 / 0.73 / 0.95 / 0.95); utility 0.97–0.99,
deception 0.03, fabrications 0.04, no empty turns. Training probe 0.63/0.57 → 0.40 in both arms. Caution: KL of the update
0.32 → 0.53 (sp) and 0.31 → 0.48 (rlvr), clip fraction 0.07 → 0.19 / 0.15 — the drift signature the regret mode showed in §5.
Advantages are mostly negative (59–61 % of rows), which is the push-down regime. Running to it03.
