"""Distillation baseline: a frontier model that does not leak (Opus 5.5 by default) plays the defender on the
training worlds, under exactly the student's system prompt, and the student (Qwen3-8B LoRA) is fit to its turns.

No oracle, no reward, no reweighting: every completed teacher turn is a training row (the "straightforward"
baseline against the oracle-guided warm start `sft_round2` and the RL checkpoints).

  (host) LOCAL_LLM_URLS=http://localhost:19000,... DOSSIER_SPEND_LOG=runs/spend_distill.jsonl BUDGET_USD=250 \
         python -m selfplay.distill collect --teacher claude-opus-5-5 --out runs/selfplay_sft/distill_opus_episodes.jsonl
  (host) python -m selfplay.distill build --episodes runs/selfplay_sft/distill_opus_episodes.jsonl \
         --out runs/selfplay_sft/distill_opus.jsonl --epochs 2
  (pod)  python -m selfplay.train_lora --data runs/selfplay_sft/distill_opus.jsonl --adapter-in "" \
         --adapter-out selfplay/run/distill/ckpt/distill_opus --lr 5e-5 --beta 0 --clip-eps 10      (= sft_round2 recipe)
  (host) python -m selfplay.eval_ckpt --lora distill_opus --tag distill_opus --run selfplay/run/distill

The training row has the same shape as the student's own samples (trace + visible answer): the trace is the API's
summarised thinking (`thinking.display = "summarized"`); asking the teacher to print its reasoning in the reply is
declined by the API (stop_reason refusal / reasoning_extraction). `--trace none` builds rows with an empty trace.
"""
from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dossier.llm import get_llm

from .episode import Cfg, run_episode
from .local_llm import LocalLLM
from .loop import load_worlds
from .parser_local import LocalParser

class TeacherRouter:
    """Drop-in for LocalLLM in run_episode: 'api@<model>' goes to the API teacher (dossier.llm, cached, budgeted),
    everything else (parser, LLM attackers) to the local vLLM replicas."""

    def __init__(self, local: LocalLLM, effort: str = "low"):
        self.local = local
        self.effort = effort
        self.n_teacher = 0
        self.n_format_fail = 0
        self.usd = 0.0

    def chat(self, model: str, system: str, messages: list[dict], *, max_tokens: int = 1024, temperature: float = 0.7,
             top_p: float = 0.95, thinking: bool = True, seed=None, stop=None, retries: int = 10) -> dict:
        if not model.startswith("api@"):
            return self.local.chat(model, system, messages, max_tokens=max_tokens, temperature=temperature, top_p=top_p,
                                   thinking=thinking, seed=seed, stop=stop, retries=retries)
        teacher = model.split("@", 1)[1]
        # the API's summarised thinking is the only reasoning surface available (asking the model to print its
        # reasoning is declined with stop_reason=refusal / reasoning_extraction)
        d = get_llm().chat(teacher, system, messages, max_tokens=max_tokens, effort=self.effort,
                           tag="distill_teacher", cache_system=True, thinking_display="summarized")
        answer = d["text"].strip()
        reasoning = (d.get("thinking") or "").strip()
        if not reasoning:
            self.n_format_fail += 1
        raw = f"<think>\n{reasoning}\n</think>\n\n{answer}"
        stop_reason = d.get("stop_reason")
        finish = "stop" if stop_reason in ("end_turn", "stop", "stop_sequence", None) else stop_reason
        self.n_teacher += 1
        self.usd += d.get("usd", 0.0) or 0.0
        return {"text": answer, "reasoning": reasoning, "raw": raw, "finish_reason": finish, "usage": d.get("usage", {}),
                "cached": d.get("cached", False)}


def collect(a):
    local = LocalLLM()                      # LOCAL_LLM_URLS
    router = TeacherRouter(local, effort=a.effort)
    parser = LocalParser(local)
    worlds = load_worlds(Path(a.worlds))
    if a.max_worlds:
        worlds = worlds[: a.max_worlds]
    rng = random.Random(a.seed)
    cfg = Cfg(def_max_tokens=a.max_tokens)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for l in out.open():
            try:
                e = json.loads(l); done.add((e["seed"], e["variant"]))
            except Exception:
                pass
    # two episodes per world: the two holder-prompt variants the student is trained with, attacker drawn 2:1
    # direct:ladder (same mix as the warm-start collection)
    jobs = []
    for w in worlds:
        for variant in ("vanilla", "ci"):
            att = rng.choice(["scripted-direct", "scripted-ladder", "scripted-direct"])
            if (w.seed, variant) not in done:
                jobs.append((w, variant, att))
    print(f"{len(worlds)} worlds, {len(jobs)} episodes to run ({len(done)} done)", flush=True)
    defender = f"api@{a.teacher}"
    n = 0; t0 = time.time()
    with out.open("a") as fh, ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(run_episode, w, defender, att, router, parser, cfg, random.Random(rng.random()), variant, False): (w, variant, att)
                for w, variant, att in jobs}
        for f in as_completed(futs):
            w, variant, att = futs[f]
            try:
                e = f.result()
            except Exception as ex_:  # noqa
                print("ERR", w.seed, variant, repr(ex_)[:200], flush=True); continue
            e["teacher"] = a.teacher
            fh.write(json.dumps(e, ensure_ascii=False) + "\n"); fh.flush(); n += 1
            if n % 25 == 0 or n == len(jobs):
                print(f"  {n}/{len(jobs)} seed={e['seed']} {variant} {att} leak={e['leak_bits']:.2f} util={e['utility']:.2f} "
                      f"teacher_calls={router.n_teacher} fmt_fail={router.n_format_fail} usd={router.usd:.2f} {time.time() - t0:.0f}s", flush=True)
    print("done", n, "teacher calls", router.n_teacher, "format failures", router.n_format_fail, f"usd {router.usd:.2f}")


REFUSAL_KEYS = ("can't", "cannot", "can’t", "not able", "unable", "sorry", "don't", "won't", "not something", "unfortunately")


def build(a):
    rows = []
    eps = []
    stats = Counter()
    for path in a.episodes:
        for l in open(path):
            e = json.loads(l); eps.append(e)
            for s in e["def_samples"]:
                stats["turns"] += 1
                if not s["text"].strip():
                    stats["empty"] += 1; continue
                if s["finish"] != "stop":
                    stats["truncated"] += 1; continue
                if "</think>" not in s["raw"] or s["raw"].startswith("<think>\n\n</think>"):
                    stats["no_trace"] += 1
                    if a.require_trace:
                        continue
                if a.oracle_filter and s.get("rstar") is not None and s["r_t"] - s["rstar"] < -0.05:
                    stats["oracle_dropped"] += 1; continue
                key = bool(s.get("key_turn"))
                low = s["text"].lower()
                refusal = key and not low.startswith("yes") and any(k in low for k in REFUSAL_KEYS)
                raw = s["raw"] if a.trace == "summary" else "<think>\n\n</think>\n\n" + s["text"].strip()
                rows.append({"system": s["system"], "messages": s["messages"], "raw": raw, "adv": 1.0, "seed": e["seed"],
                             "kind": "answer", "think": True, "key_turn": key, "refusal": refusal,
                             "null": str(e.get("arm", "")).startswith("null"), "variant": e.get("variant"), "teacher": e.get("teacher")})
                stats["kept"] += 1; stats["key_turn"] += int(key); stats["refusal"] += int(refusal)
    rng = random.Random(0)
    out = rows * a.epochs
    rng.shuffle(out)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    # teacher behaviour on the training worlds (training parser labels), for the report
    live = [e for e in eps if not str(e.get("arm", "")).startswith("null")]
    null = [e for e in eps if str(e.get("arm", "")).startswith("null")]
    def mean(xs):
        return sum(xs) / len(xs) if xs else float("nan")
    summ = {"episodes": len(eps), "live_worlds": len(live), "null_worlds": len(null), **stats,
            "unique_rows": len(rows), "rows": len(out), "epochs": a.epochs,
            "teacher_leak1_live": mean([e["leak_bits"] >= 1 - 1e-9 for e in live]),
            "teacher_bits_live": mean([e["leak_bits"] for e in live]),
            "teacher_utility_live": mean([e["utility"] for e in live]),
            "teacher_utility_null": mean([e["utility"] for e in null]),
            "teacher_violations": mean([e["violations"] for e in eps]),
            "teacher_over_refusals": mean([e["over_refusals"] for e in eps]),
            "teacher_fabrications": mean([e["fabrications"] for e in eps]),
            "teacher_d1_live": mean([list(e["key_disclosed"].values())[0] for e in live if e["key_disclosed"]]),
            "teacher_dk_live": mean([list(e["key_disclosed"].values())[-1] for e in live if e["key_disclosed"]]),
            "by_attacker": {k: {"n": sum(1 for e in live if e["attacker"] == k),
                                "leak1": mean([e["leak_bits"] >= 1 - 1e-9 for e in live if e["attacker"] == k]),
                                "utility": mean([e["utility"] for e in live if e["attacker"] == k])}
                            for k in sorted({e["attacker"] for e in live})}}
    Path(a.out).with_suffix(".summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", required=True); c.add_argument("--worlds", default="runs/worlds_train")
    c.add_argument("--teacher", default="claude-opus-5-5"); c.add_argument("--effort", default="low")
    c.add_argument("--workers", type=int, default=24); c.add_argument("--max-tokens", type=int, default=1500)
    c.add_argument("--max-worlds", type=int, default=0); c.add_argument("--seed", type=int, default=0)
    b = sub.add_parser("build")
    b.add_argument("--episodes", nargs="+", required=True); b.add_argument("--out", required=True)
    b.add_argument("--epochs", type=int, default=2); b.add_argument("--oracle-filter", action="store_true")
    b.add_argument("--require-trace", action="store_true")
    b.add_argument("--trace", default="summary", choices=["summary", "none"], help="none: rows keep the answer only (empty <think> block)")
    a = ap.parse_args()
    {"collect": collect, "build": build}[a.cmd](a)
