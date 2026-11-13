"""Plain supervised fine-tuning of a LoRA on rows {system, messages, raw, think} (token-level NLL, answer tokens
weighted 1, trace tokens w_think). Same data format, tokenisation and LoRA config as train_lora.py, but without the
importance ratio: used for the distillation baseline (selfplay/distill.py) as a check that the objective choice
(ratio-weighted, as in sft_round2, vs. plain NLL) does not drive the result.

  python -m selfplay.train_sft --data runs/selfplay_sft/distill_opus.jsonl --adapter-out selfplay/run/distill/ckpt/distill_opus_nll
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

from . import train_lora
from .train_lora import build, logprobs


def main(a):
    train_lora.W_THINK = a.w_think
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
    random.shuffle(rows)
    if a.max_samples:
        rows = rows[:a.max_samples]
    print(f"{len(rows)} rows", flush=True)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0, betas=(0.9, 0.99))
    n_steps = math.ceil(len(rows) / a.accum)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / max(1, min(5, n_steps // 4 + 1))))
    model.train()
    stats = {"loss": 0.0, "nll_answer": 0.0, "tokens": 0, "n": 0, "skipped": 0}
    t0 = time.time()
    for i, row in enumerate(rows):
        b = build(tok, row, a.max_len)
        if b is None:
            stats["skipped"] += 1
            continue
        ids, mask, w = b[0].to(dev), b[1].to(dev), b[2].to(dev)
        lp = logprobs(model, ids, mask)
        w = w[: lp.shape[0]]
        loss = -(w * lp).sum() / w.sum()
        (loss / a.accum).backward()
        ans = w >= 1.0 - 1e-6
        stats["loss"] += loss.item(); stats["n"] += 1; stats["tokens"] += int(mask.sum())
        stats["nll_answer"] += float(-(lp[ans]).mean()) if ans.any() else 0.0
        if (i + 1) % a.accum == 0 or i == len(rows) - 1:
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], a.clip)
            opt.step(); sched.step(); opt.zero_grad(set_to_none=True)
        if (i + 1) % 50 == 0:
            n = stats["n"]
            print(f"  {i + 1}/{len(rows)} loss={stats['loss'] / n:.4f} nll_answer={stats['nll_answer'] / n:.4f} "
                  f"tok/sample={stats['tokens'] / n:.0f} {time.time() - t0:.0f}s", flush=True)
    out = Path(a.adapter_out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    n = max(stats["n"], 1)
    summ = {"n": stats["n"], "skipped": stats["skipped"], "loss": stats["loss"] / n, "nll_answer": stats["nll_answer"] / n,
            "tokens_per_sample": stats["tokens"] / n, "wall": time.time() - t0, "lr": a.lr, "objective": "nll",
            "w_think": a.w_think, "data": a.data}
    (out / "train_summary.json").write_text(json.dumps(summ, indent=1))
    print("saved", out, json.dumps(summ))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="Qwen/Qwen3-8B")
    ap.add_argument("--data", required=True)
    ap.add_argument("--adapter-in", default="")
    ap.add_argument("--adapter-out", required=True)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--accum", type=int, default=32)
    ap.add_argument("--clip", type=float, default=1.0)
    ap.add_argument("--w-think", type=float, default=0.3)
    ap.add_argument("--max-len", type=int, default=6144)
    ap.add_argument("--max-samples", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    main(ap.parse_args())
