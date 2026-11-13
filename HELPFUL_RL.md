# Removing the helpfulness regression in PrivacyZero

*Proposal + pre-registered experiments, 2026-11-13. Companion to `PRIVACYZERO.md` §6.7 (the regression) and
`EVAL.md`. Code: `selfplay/{episode,loop,warmstart,worlds}.py`, launch `selfplay/launch_h.sh`, orchestrator
`selfplay/h_orchestrate.sh`.*

## 1. The problem, and why the recipe produces it

§6.7 showed that every trained checkpoint pays for its lower leak with over-refusal: in null worlds, where the
relational question d1 carries no information about the approver, the base model answers 100 % and the shipped
`exp2_it01` 35 % (floor public) / 80 % (no memo); legitimate cover-fact requests answered fall from 83 % to 56–78 %.

Three things in the current recipe push that way, and each is fixable:

1. **The reward is asymmetric.** Completing a leak costs `1.5 · bits/available ≈ 1.5`; refusing a harmless fact
   costs `1/|asked facts| ≈ 0.09` of utility. A policy that cannot tell the two situations apart in context (Qwen3-8B
   could not follow even an explicit hint, §5) minimises expected loss by refusing every d1-shaped question. The
   defender is never told, through the reward, that *withholding a safe fact is a mistake of the same kind* as
   disclosing an unsafe one.
2. **The warm start is 4 : 1 refusals.** `warmstart.build` keeps 427 refusal turns × 4 against at most 427 safe
   key-fact disclosures, of which only ~80 come from null worlds. The "answer d1 when it is harmless" behaviour is
   the rarest thing in the SFT set, so `sft_round2` already answers d1 in only 60 % of no-memo worlds before RL
   starts.
3. **Null worlds are 20 % of the training pool** and are sampled without stratification, so an iteration of 48
   worlds has ~10 of them and the group-normalised advantage of a null-world refusal is small (there is little
   within-group contrast: the policy refuses in all 8 samples).

## 2. Techniques

| id | technique | implementation | what it changes |
|---|---|---|---|
| **T1 over-refusal penalty** | `R_def −= w_over · #(asked, non-PROTECTED facts the exact oracle would have disclosed but the defender withheld)`; `w_over = 0.5` | `episode.py`: per-turn `over_t` uses the same oracle rule as the guided hint (safe iff leak(D + f) ≤ 0.25); `Cfg.w_over`, `loop --w-over` | makes "refused a safe fact" cost 0.59 instead of 0.09 — a third of a completed leak, so the model still errs towards refusing when the two are close, but no longer for free. Computable exactly because the world model is exact. |
| **T2 null-heavy, stratified pool** | 40 % of each iteration's worlds drawn from a 300-world null-only pool (`runs/worlds_train_null`, seeds 5000+, public/no-memo 50/50, same order/redundancy/persona mixture, ψ mixture kept) | `worlds.py --null-only`, `loop --worlds-null --p-null 0.4` | every iteration contains ~19 worlds in which the d1/d2 questions must be answered; the group contrast that rewards answering exists in every batch |
| **T3 safe-answer replay (behaviour-cloning anchor)** | each iteration, 300 rows of no-regret *answers* from the oracle-guided rollouts (never refusals; 16 % key-fact turns, 23 % null worlds) are appended to the PG batch with advantage +0.5 | `warmstart build-anchor` → `runs/selfplay_sft/anchor_safe.jsonl` (9,961 rows); `loop --anchor-data --anchor-n 300 --anchor-adv 0.5` | a clipped likelihood term on helpful behaviour, i.e. RL + SFT mixing; the anchor is drawn from the base model's own answers, so it pulls towards the base's helpfulness rather than towards a different style |
| **T4 balanced warm start** | rebuild the SFT set: refusals × 3, *all* null-world safe key disclosures × 2 (954 rows), as many live safe key disclosures as refusals (419), other turns 1,238; 7,736 rows over 2 epochs (same lr/epochs as `sft_round2`) | `warmstart build --balanced --null-weight 2` → `runs/selfplay_sft/sft_h.jsonl` → adapter `sft_h` | "answer d1" and "refuse d1" appear with comparable weight; the choice has to come from the facts, not from the shape of the question |
| T5 constrained RL (adaptive `w_over`) | raise `w_over` whenever the null-world probe answers < 90 %, lower it otherwise (Lagrangian) | not run in wave 1; `--probe-null` already logs the probe every iteration so it can be added as a one-line controller | second wave, if T1 needs tuning |
| T6 answer-only RL / shorter trace | orthogonal (§6.5 item 2) | — | not in this study |

Everything else is held fixed at the `exp2` recipe: start from `sft_round2`, W = 48 worlds × G = 8 samples,
attacker mixture 45 % scripted-direct / 25 % ladder / 25 % attacker LoRA / 5 % base, `--vstar-baseline 0`
(plain group normalisation), guided exploration 25 %, lr 3e-5, 4 iterations (it00–it03; `exp2` peaked at it01–it02
and drifted at it03).

## 3. Experiments (one pod, arms share the vLLM replicas; adapter names carry the arm prefix)

| arm | start | T1 | T2 | T3 | T4 | question it answers |
|---|---|---|---|---|---|---|
| control = `exp2` it00–it03 (already run) | sft_round2 | | | | | the regression as measured in §6.7 |
| **h1** | sft_round2 | ✓ | | | | is the reward asymmetry alone the cause? |
| **h2** | sft_round2 | | ✓ | | | is it the data mixture alone? |
| **h3** | sft_round2 | | | ✓ | | does anchoring to the base's answers hold helpfulness without hurting leak? |
| **h4** | sft_round2 | ✓ | ✓ | ✓ | | the combined recipe from the same warm start |
| **h5** | **sft_h** | ✓ | ✓ | ✓ | ✓ | does the regression come partly from the warm start? (h5 vs h4) |

Measured per checkpoint, all held out, same tooling as §6:
leak (% worlds ≥ 1 bit, bits) vs scripted-direct / ladder / Haiku / Sonnet attackers; **null-world d1/d2 answered**
(floor public, no memo; seeds 200–219) — now also probed inside the loop every iteration (`probe_null` in
`metrics.jsonl`, 20 + 20 worlds); utility; cover facts answered when asked; the three regression checks (false
belief / deception, ψ flips, monitorability); fabrications and corrected false non-target statements.

Evals run automatically for `it01` and `it03` of each arm (`eval_when_ready.sh`, tags `h1_it01` … `h5_it03`),
then `python -m selfplay.helpful --tags base,sft_round2,exp2_it01,h1_it01,… --run-null`.

## 4. Predictions (written before the runs)

* **P1** h1 recovers most of the null-world answer rate (≥ 80 % in both null arms vs 35 / 80 % for `exp2_it01`)
  at a leak cost of ≤ 10 points (0.30 → ≤ 0.40 of worlds), because the oracle-defined penalty is exactly the
  signal the policy was missing and is applied per turn. If instead leak returns to ≥ 0.6, the policy cannot
  separate the two situations in context and the fix has to come from data (T2/T4) or a stronger base.
* **P2** h2 alone moves the null rate less than h1 (the within-group contrast is still weak when the policy
  refuses in all 8 samples) but keeps leak lowest of the single-factor arms.
* **P3** h3 alone keeps cover-fact helpfulness (≥ 80 % answered) and utility (≥ 0.97) but does little for null-world
  d1, since key-fact answers are only 16 % of the anchor set.
* **P4** h4 ≥ max(h1, h2, h3) on helpfulness with leak within 5 points of `exp2_it02`; h5 ≥ h4 on null-world d1
  at it00 (the warm start itself should answer ≥ 85 % in null worlds, vs 60–90 % for `sft_round2`).
* **P5** None of the arms changes deception (≤ 5 %) or monitor accuracy (≥ 0.95); T1 could raise fabrications if the
  policy learns to "answer" with invented content — the fabrication penalty (0.5 / turn) and the anchor's exact
  answers are the guards, and the fabrication rate is reported for every arm.
* **Decision rule.** Ship the checkpoint with the lowest leak among those with null-world d1 ≥ 80 % in both arms,
  cover asks ≥ 75 %, deception ≤ 5 %, ψ `flip_key_up` ≥ 0.70. If no arm meets it, the next wave is T5 (adaptive
  `w_over`) on the best arm's recipe.

## 5. Compute / status

Job `allie-privacyzero-a6` (Kueue `training-lq`, q0, 6 × B300: 4 vLLM replicas + 2 training GPUs). The cluster was
full at submission (23 of 24 B300 nodes fully allocated); the host orchestrator (`selfplay/h_orchestrate.sh`,
log `selfplay/run/h_orchestrator.log`) waits for the pod, starts the replicas, and runs the queues
`sft_h → h5 → h2` and `h1 → h4 → h3`, ~1.5 h per arm, ~5.5 h total once admitted. Stop everything with
`touch selfplay/run/H_STOP; touch selfplay/run/POD_STOP; kubectl delete job -n fleet-train-jobs allie-privacyzero-a6`.

## 6. Results

*(filled in as the arms complete)*
