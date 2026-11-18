#!/bin/bash
# Launch one RLVR-vs-self-play arm inside the pod. usage: launch_rlvr.sh <arm> <train_gpu>
#   rlvr   sft_round2       -> RL vs FIXED attackers only (scripted-direct / ladder / base-prompted LLM), no attacker training, 6 iters
#   drlvr  distill_opus_nll -> same fixed-attacker RL, 4 iters
#   dsp    distill_opus_nll -> self-play (exp2 recipe: attacker LoRA trained every 2nd iter, 25 % of episodes), 4 iters
# Everything else is the exp2 / HELPFUL_RL recipe (W 48, G 8, cap 1200, plain group normalisation, p_hint 0.25, lr 3e-5).
# In exp2 the attacker share of the mixture (0.25) played the *base* attacker until att_it01 existed, so the fixed-attacker
# arms keep the same LLM-attacker exposure by moving that share to --p-base.
ARM=$1; GPU=$2
cd /shared/allie/privacy
RUN=selfplay/run/$ARM; mkdir -p $RUN/ckpt
COMMON="--out $RUN --W 48 --G 8 --cap-def 1200 --cap-att 600 --att-every 2 --probe-n 30 --serve-gpus 0,1,2,3 --train-gpu $GPU --prefix ${ARM}_ --vstar-baseline 0 --p-hint 0.25 --lr 3e-5 --lr-att 3e-5 --p-direct 0.45 --p-ladder 0.25 --probe-null 20 --workers 64"
FIXED="--train-att 0 --p-att 0.0 --p-base 0.30"
SELFPLAY="--train-att 1 --p-att 0.25 --p-base 0.05"
case $ARM in
  rlvr)  EXTRA="--iters 6 $FIXED";    START=sft_round2;       SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  drlvr) EXTRA="--iters 4 $FIXED";    START=distill_opus_nll; SRC=/shared/allie/privacy/selfplay/run/distill/ckpt/distill_opus_nll ;;
  dsp)   EXTRA="--iters 4 $SELFPLAY"; START=distill_opus_nll; SRC=/shared/allie/privacy/selfplay/run/distill/ckpt/distill_opus_nll ;;
  # follow-ups 2026-11-16: strong self-play dose (attacker 75 % of episodes, updated every iteration) and seed replicates
  dsp2)     EXTRA="--iters 6 --train-att 1 --p-att 0.75 --p-base 0.0 --p-direct 0.15 --p-ladder 0.10 --att-every 1"; START=distill_opus_nll; SRC=/shared/allie/privacy/selfplay/run/distill/ckpt/distill_opus_nll ;;
  drlvr_s1) EXTRA="--iters 4 $FIXED --seed 1";    START=distill_opus_nll; SRC=/shared/allie/privacy/selfplay/run/distill/ckpt/distill_opus_nll ;;
  dsp_s1)   EXTRA="--iters 4 $SELFPLAY --seed 1"; START=distill_opus_nll; SRC=/shared/allie/privacy/selfplay/run/distill/ckpt/distill_opus_nll ;;
  # 2026-11-17: seeds for the sft_round2 lineage (sp_* = self-play with the exp2 recipe, rlvr_s* = fixed attackers)
  sp_s1)    EXTRA="--iters 4 $SELFPLAY --seed 1"; START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  sp_s2)    EXTRA="--iters 4 $SELFPLAY --seed 2"; START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  rlvr_s1)  EXTRA="--iters 4 $FIXED --seed 1";    START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  rlvr_s2)  EXTRA="--iters 4 $FIXED --seed 2";    START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  # 2026-11-17 §6.11 fix round 1: hybrid advantage (per-turn credit for scripted groups, episode-level for LLM-attacker groups),
  # protected-fact questions count as key turns for the row cap, LLM attacker share 75 % in BOTH arms (fixed = base-prompted,
  # self-play = trained adapter updated every iteration), 6 iterations
  fx_rlvr)    EXTRA="--iters 6 --adv hybrid --train-att 0 --p-att 0.0 --p-base 0.75 --p-direct 0.15 --p-ladder 0.10";                            START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx_sp)      EXTRA="--iters 6 --adv hybrid --train-att 1 --p-att 0.75 --p-base 0.0 --p-direct 0.15 --p-ladder 0.10 --att-every 1";              START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx_rlvr_s1) EXTRA="--iters 6 --adv hybrid --train-att 0 --p-att 0.0 --p-base 0.75 --p-direct 0.15 --p-ladder 0.10 --seed 1";                   START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx_sp_s1)   EXTRA="--iters 6 --adv hybrid --train-att 1 --p-att 0.75 --p-base 0.0 --p-direct 0.15 --p-ladder 0.10 --att-every 1 --seed 1";     START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  # round 2: as fx_* but LLM-attacker groups get turn-local oracle regret (r_t − r*_t, half-mean baseline, --llm-vstar 3) instead of the episode advantage
  fx2_rlvr)    EXTRA="--iters 6 --adv hybrid --llm-vstar 3 --train-att 0 --p-att 0.0 --p-base 0.75 --p-direct 0.15 --p-ladder 0.10";                        START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx2_sp)      EXTRA="--iters 6 --adv hybrid --llm-vstar 3 --train-att 1 --p-att 0.75 --p-base 0.0 --p-direct 0.15 --p-ladder 0.10 --att-every 1";          START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx2_rlvr_s1) EXTRA="--iters 6 --adv hybrid --llm-vstar 3 --train-att 0 --p-att 0.0 --p-base 0.75 --p-direct 0.15 --p-ladder 0.10 --seed 1";               START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx2_sp_s1)   EXTRA="--iters 6 --adv hybrid --llm-vstar 3 --train-att 1 --p-att 0.75 --p-base 0.0 --p-direct 0.15 --p-ladder 0.10 --att-every 1 --seed 1"; START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  # round 3: group-normalised oracle regret for LLM groups (--llm-vstar 4), standard mixture (LLM 30 %: fixed = base-prompted 0.30;
  # self-play = trained 0.25 + base 0.05, attacker every 2nd iteration as exp2), protected key turns, 6 iterations
  fx3_rlvr)    EXTRA="--iters 6 --adv hybrid --llm-vstar 4 $FIXED";              START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx3_sp)      EXTRA="--iters 6 --adv hybrid --llm-vstar 4 $SELFPLAY";           START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx3_rlvr_s1) EXTRA="--iters 6 --adv hybrid --llm-vstar 4 $FIXED --seed 1";     START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx3_sp_s1)   EXTRA="--iters 6 --adv hybrid --llm-vstar 4 $SELFPLAY --seed 1";  START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  # round 4: round-3 credit with drift held (lr 1.5e-5, beta 0.05) and, for self-play, a faster-learning attacker (lr-att 1e-4, every iteration)
  fx4_rlvr)    EXTRA="--iters 6 --adv hybrid --llm-vstar 4 --lr 1.5e-5 --beta 0.05 $FIXED";                                                 START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx4_sp)      EXTRA="--iters 6 --adv hybrid --llm-vstar 4 --lr 1.5e-5 --beta 0.05 $SELFPLAY --lr-att 1e-4 --att-every 1";                  START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx4_rlvr_s1) EXTRA="--iters 6 --adv hybrid --llm-vstar 4 --lr 1.5e-5 --beta 0.05 $FIXED --seed 1";                                        START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  fx4_sp_s1)   EXTRA="--iters 6 --adv hybrid --llm-vstar 4 --lr 1.5e-5 --beta 0.05 $SELFPLAY --lr-att 1e-4 --att-every 1 --seed 1";         START=sft_round2; SRC=/shared/allie/privacy/selfplay/run/exp2/ckpt/sft_round2 ;;
  *) echo "unknown arm $ARM"; exit 1 ;;
esac
[ -e $RUN/ckpt/${ARM}_$START ] || ln -s $SRC $RUN/ckpt/${ARM}_$START
[ -f $RUN/state.json ] || echo "{\"it\": 0, \"def\": \"${ARM}_$START\", \"att\": \"base\"}" > $RUN/state.json
export HOME=/tmp/home HF_HOME=/shared/allie/privacy/selfplay/hf PYTHONPATH=/shared/allie/privacy VLLM_ALLOW_RUNTIME_LORA_UPDATING=1
case $ARM in fx_*|fx2_*|fx3_*|fx4_*) export KEY_TURN_PROTECTED=1 ;; esac
V=/shared/allie/wsr-pilot-20261103/venv-vllm
setsid nohup $V/bin/python -m selfplay.loop $COMMON $EXTRA >> selfplay/run/$ARM.log 2>&1 < /dev/null &
echo "launched $ARM on train gpu $GPU pid $!"
