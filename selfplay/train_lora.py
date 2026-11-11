"""LoRA policy-gradient update for one role from a rollouts file (runs in the torch-2.13 training venv, 1 GPU).

Loss per sample  = -A * mean_t min(r_t, clip(r_t, 1-eps, 1+eps))   r_t = pi(y_t)/pi_old(y_t)   (PPO clip; pi_old =
                   the adapter the servers sampled from, log-probs cached in a first no-grad pass)
                 + beta * KL_k3(pi || pi_ref)   (ref = base model, adapter disabled; log-ratio clamped to [-5, 5])
One epoch, but ~40 optimiser steps per iteration, so the clip matters: without it the k3 KL blew up (>100) on
samples the policy had already moved away from.

  python -m selfplay.train_lora --data it3_def.jsonl --adapter-in ckpt/def_it2 --adapter-out ckpt/def_it3
"""
from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer

IM_END = "<|im_end|>"
W_THINK = 0.3


def build(tok, row: dict, max_len: int):
    msgs = [{"role": "system", "content": row["system"]}] + row["messages"]
    prompt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=row.get("think", True))
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    c_ids = tok(row["raw"] + IM_END, add_special_tokens=False)["input_ids"]
    if len(p_ids) + len(c_ids) > max_len:
        keep = max_len - len(c_ids)
        if keep < 256:
            return None
        p_ids = p_ids[-keep:]       # truncate from the left (oldest history) only in the pathological case
    ids = torch.tensor(p_ids + c_ids)
    mask = torch.zeros(len(ids), dtype=torch.bool)
    mask[len(p_ids):] = True
    # token weights over the completion: the visible answer (after </think>) carries the decision, the trace is
    # down-weighted (w_think) so the gradient concentrates on the tokens that determine the reward
    w = torch.ones(len(c_ids))
    raw = row["raw"]
    if "</think>" in raw:
        n_think = len(tok(raw.split("</think>", 1)[0] + "</think>", add_special_tokens=False)["input_ids"])
        w[:min(n_think, len(c_ids))] = W_THINK
    return ids, mask, w


def logprobs(model, ids, mask):
    out = model(input_ids=ids[None], use_cache=False)
    logits = out.logits[0, :-1].float()
    tgt = ids[1:]
    lp = torch.log_softmax(logits, -1).gather(-1, tgt[:, None])[:, 0]
    m = mask[1:]
    return lp[m]


def main(a):
    global W_THINK
    W_THINK = a.w_think
    torch.manual_seed(a.seed)
    random.seed(a.seed)
    dev = "cuda"
    tok = AutoTokenizer.from_pretrained(a.base)
    model = AutoModelForCausalLM.from_pretrained(a.base, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(dev)
    model.gradient_checkpointing_enable()
    model.config.use_cache = False
    if a.adapter_in and Path(a.adapter_in).exists():
        model = PeftModel.from_pretrained(model, a.adapter_in, is_trainable=True)
        print("loaded adapter", a.adapter_in)
    else:
        cfg = LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM",
                         target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])
        model = get_peft_model(model, cfg)
    model.enable_input_require_grads()
    model.print_trainable_parameters()
    rows = [json.loads(l) for l in open(a.data) if l.strip()]
    rows = [r for r in rows if abs(r["adv"]) > 1e-6]
    random.shuffle(rows)
    if a.max_samples:
        rows = rows[:a.max_samples]
    print(f"{len(rows)} samples with nonzero advantage")
    t0 = time.time()
    # cache old-policy log-probs (the adapter we start from == the one the servers sampled with)
    built = []
    n_skipped = 0
    model.eval()
    with torch.no_grad():
        for row in rows:
            b = build(tok, row, a.max_len)
            if b is None:
                n_skipped += 1
                continue
            ids, mask, w = b[0].to(dev), b[1].to(dev), b[2].to(dev)
            built.append((row, ids, mask, w, logprobs(model, ids, mask).detach()))
    print(f"cached old log-probs for {len(built)} samples ({time.time() - t0:.0f}s)", flush=True)
    rows = built
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0, betas=(0.9, 0.99))
    n_steps = math.ceil(len(rows) / a.accum)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(1, min(5, n_steps // 4 + 1))))
    model.train()
    stats = {"loss": 0.0, "pg": 0.0, "kl": 0.0, "clipfrac": 0.0, "tokens": 0, "n": 0, "skipped": n_skipped}
    t0 = time.time()
    for i, (row, ids, mask, w, lp_old) in enumerate(rows):
        lp = logprobs(model, ids, mask)
        ratio = torch.exp(lp - lp_old)
        clipped = torch.clamp(ratio, 1 - a.clip_eps, 1 + a.clip_eps)
        adv = row["adv"]
        w = w[: lp.shape[0]]
        pg = -(w * torch.minimum(ratio * adv, clipped * adv)).sum() / w.sum()
        stats["clipfrac"] += float(((ratio - 1).abs() > a.clip_eps).float().mean())
        kl = torch.zeros((), device=dev)
        if a.beta > 0:
            with torch.no_grad(), model.disable_adapter():
                lp_ref = logprobs(model, ids, mask)
            d = torch.clamp(lp_ref - lp, -5.0, 5.0)
            kl = (torch.exp(d) - d - 1).mean()          # k3 estimator of KL(pi || ref), bounded
        loss = (pg + a.beta * kl) / a.accum
        loss.backward()
        stats["loss"] += loss.item() * a.accum; stats["pg"] += pg.item(); stats["kl"] += kl.item()
        stats["tokens"] += int(mask.sum()); stats["n"] += 1
        if (i + 1) % a.accum == 0 or i == len(rows) - 1:
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], a.clip)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
        if (i + 1) % 50 == 0:
            n = stats["n"]
            print(f"  {i + 1}/{len(rows)} loss={stats['loss'] / n:.4f} pg={stats['pg'] / n:.4f} kl={stats['kl'] / n:.5f} "
                  f"clipfrac={stats['clipfrac'] / n:.3f} tok/sample={stats['tokens'] / n:.0f} {time.time() - t0:.0f}s", flush=True)
    out = Path(a.adapter_out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    n = max(stats["n"], 1)
    summ = {"n": stats["n"], "skipped": stats["skipped"], "loss": stats["loss"] / n, "pg": stats["pg"] / n,
            "kl": stats["kl"] / n, "clipfrac": stats["clipfrac"] / n, "tokens_per_sample": stats["tokens"] / n, "wall": time.time() - t0,
            "lr": a.lr, "beta": a.beta, "data": a.data}
    (out / "train_summary.json").write_text(json.dumps(summ, indent=1))
    print("saved", out, json.dumps(summ))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-8B")
    ap.add_argument("--data", required=True)
    ap.add_argument("--adapter-in", default="")
    ap.add_argument("--adapter-out", required=True)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--beta", type=float, default=0.02)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--accum", type=int, default=32)
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--clip-eps", type=float, default=0.2)
    ap.add_argument("--w-think", type=float, default=0.3)
    ap.add_argument("--max-len", type=int, default=6144)
    ap.add_argument("--max-samples", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    main(ap.parse_args())
