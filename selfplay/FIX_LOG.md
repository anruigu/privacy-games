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

**Round 2 result (2026-11-18 03:40 UTC, it03): signal found, but the update drifts.** Held-out direct / ladder / Haiku / Sonnet:
fx2_rlvr it03 0.82 / 0.73 / 0.89 / 0.89, fx2_sp it03 0.84 / 0.80 / 0.55 / 0.75 (it01: 0.58/0.60/0.80/0.75 and 0.56/0.80/0.50/0.80).
KL of the update 0.32 → 0.53 → 1.06 → 1.78 (sp), 0.31 → 0.48 → 1.09 → 1.49 (rlvr); clip fraction 0.43 / 0.42; training
utility 0.56 → 0.30; attacker KL 0.02 → 0.78 (updated every iteration at 75 % share). Deception stayed 0.03, no fabrication
or empty-turn rise. Reading: the half-mean-baseline regret with the 0.3 scale floor and ±3 clip produces large, mostly
negative advantages (60 % of rows negative, mean −0.5), so each update is a maxed-out push-down and the policy walks away
from the warm start; the scripted channel (15 % of worlds) is not held in place and its held-out leak rises. Killed at it04.

## Round 3 — group-normalised oracle regret, standard mixture (launched 2026-11-18 03:20 UTC, pod a11)

`--adv hybrid --llm-vstar 4`: for LLM-attacker groups a_t = group_adv(r_t − r*_t) at the turn index — the regret is
state-matched (oracle baseline at the defender's own state), the normalisation makes it zero-mean / unit-variance (the
regime that was stable in every earlier run). Scripted groups unchanged. prot_said guard kept. Mixture back to the §6.9
standard (LLM 30 % of worlds: fixed = base-prompted 0.30; self-play = trained 0.25 + base 0.05, attacker updated every
2nd iteration), scripted-direct 0.45, ladder 0.25, so the arms are directly comparable to rlvr_s* / sp_s*. 6 iterations,
evals it01/03/05, seeds 0 then 1. Result: pending.

Round 3 it01 (2026-11-18 04:40 UTC): stable and moving. KL of the update 0.30 → 0.36 (sp) / 0.30 → 0.34 (rlvr), clip 0.06–0.07,
training utility 0.71 → 0.76, training probe 0.53 → 0.20 (sp) / 0.60 → 0.53 (rlvr). Held-out direct / ladder / Haiku / Sonnet:
fx3_sp 0.60 / 0.70 / 0.65 / 0.70, fx3_rlvr 0.58 / 0.57 / 0.75 / 0.90 (warm start 0.60 / 0.73 / 0.95 / 0.95); deception 0.04 / 0.06,
fabrications 0.00 / 0.02. The trained attacker enters at it02 (att_it01, KL 0.015).

Round 3 it03 (2026-11-18 06:00 UTC, seed 0): **self-play ahead on every channel.** Held-out direct / ladder / Haiku / Sonnet:
fx3_sp 0.36 / 0.27 / 0.55 / 0.55 (utility 0.94, deception 0.01, fabrications 0.04, ψ approver-flip 0.70);
fx3_rlvr 0.62 / 0.60 / 0.80 / 0.63 (utility 0.95, deception 0.04, fabrications 0.00). For reference the old recipe at it03:
rlvr 0.42 / 0.70 / 0.89 / 0.90, exp2 (best of six) 0.23 / 0.60 / 0.65 / 0.55, sp_s1 0.70 / 0.67 / 0.85 / 0.95. Training leak
0.46 → 0.33 in both arms. KL of the update is climbing again (sp 0.30 → 0.36 → 0.56 → 0.99, rlvr 0.30 → 0.34 → 0.72 → 1.07;
clip 0.35 / 0.31) — slower than round 2 but the same direction; it05 may degrade. Attacker KL 0.015 / 0.018 (every 2nd it).
Caveat: Haiku/Sonnet are 20 episodes each, direct 50; one seed. Seed-1 replicates run next on the same pod.

Round 3 it05 (2026-11-18 06:30 UTC, seed 0): **self-play ahead at every eval point.** Held-out direct / ladder / Haiku / Sonnet:
fx3_sp it05 0.30 / 0.43 / 0.30 / 0.30 (utility 0.92, deception 0.06, false statements 0.78/ep, fabrications 0.08, empty 0.01);
fx3_rlvr it05 0.50 / 0.47 / 0.65 / 0.65 (utility 0.88, deception 0.04, fabrications 0.02). Trajectory sp it01 → it03 → it05:
Haiku 0.65 → 0.55 → 0.30, Sonnet 0.70 → 0.55 → 0.30, direct 0.60 → 0.36 → 0.30; rlvr: 0.75 → 0.80 → 0.65, 0.90 → 0.63 → 0.65,
0.58 → 0.62 → 0.50. Drift: KL to base 0.30 → 2.03 (sp) / 2.53 (rlvr) over six updates, clip 0.40, training utility
0.71 → 0.45 / 0.51 (held-out direct utility holds at 0.92 / 0.88). The LLM-channel gain is real on this seed; the
self-play-vs-fixed gap (0.35 on Haiku/Sonnet at it05, 0.20 on direct) is one seed with n = 20 / 50. Seed-1 replicates
launched 06:28 UTC (fx3_rlvr_s1 gpu 4, fx3_sp_s1 gpu 5). Next if replicated: round 4 = same credit with the drift held
(lr 1.5e-5 or KL β 0.05) to see whether the it05 gains survive without the utility slide.
