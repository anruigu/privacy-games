"""Expert-iteration warm start, round 2: collect oracle-guided rollouts at scale, build an SFT set with the
refusal turns up-weighted, train from the base model.

  (pod)  python -m selfplay.warmstart collect --out runs/selfplay_sft/guided_round2.jsonl --worlds runs/worlds_train --G 2
  (host) python -m selfplay.warmstart build --episodes runs/selfplay_sft/guided_round2.jsonl --out runs/selfplay_sft/sft_round2.jsonl --refusal-weight 4 --epochs 2
  (pod)  python -m selfplay.train_lora --data runs/selfplay_sft/sft_round2.jsonl --adapter-in "" --adapter-out .../sft_round2 --lr 5e-5 --beta 0 --clip-eps 10
"""
from __future__ import annotations

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .episode import Cfg, run_episode
from .local_llm import LocalLLM
from .loop import load_worlds
from .parser_local import LocalParser


def collect(a):
    llm = LocalLLM([f"http://localhost:{8000 + i}" for i in range(a.n_servers)])
    parser = LocalParser(llm)
    worlds = load_worlds(Path(a.worlds))
    rng = random.Random(a.seed)
    cfg = Cfg(def_temperature=a.temperature)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    jobs = [(w, rng.choice(["scripted-direct", "scripted-ladder", "scripted-direct"]), g) for w in worlds for g in range(a.G)]
    n = 0
    with out.open("a") as fh, ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(run_episode, w, a.model, att, llm, parser, cfg, random.Random(rng.random()), None, True): (w, att) for w, att, g in jobs}
        for f in as_completed(futs):
            try:
                e = f.result()
            except Exception as ex_:  # noqa
                print("ERR", futs[f][0].seed, repr(ex_)[:120], flush=True); continue
            fh.write(json.dumps(e, ensure_ascii=False) + "\n"); n += 1
            if n % 50 == 0:
                print(f"  {n}/{len(jobs)} leak={e['leak_bits']:.2f} util={e['utility']:.2f}", flush=True)
    print("done", n)


def build(a):
    rows = []; stats = {"turns": 0, "kept": 0, "refusal": 0, "key_safe": 0}
    for path in a.episodes:
        for l in open(path):
            e = json.loads(l)
            if not e.get("hint"):
                continue
            for s in e["def_samples"]:
                stats["turns"] += 1
                if s.get("rstar") is None or not s["text"].strip() or s["finish"] != "stop":
                    continue
                if s["r_t"] - s["rstar"] < -0.05:
                    continue
                key = bool(s.get("key_turn"))
                low = s["text"].lower()
                refusal = key and not low.startswith("yes") and any(k in low for k in ("can't", "cannot", "can’t", "not able", "unable", "sorry", "don't", "won't", "not something", "unfortunately"))
                row = {"system": s["system"], "messages": s["messages"], "raw": s["raw"], "adv": 1.0, "seed": e["seed"],
                       "kind": "answer", "think": True, "key_turn": key, "refusal": refusal}
                rows.append(row); stats["kept"] += 1; stats["refusal"] += int(refusal); stats["key_safe"] += int(key and not refusal)
    rng = random.Random(0)
    ref = [r for r in rows if r["refusal"]]; keysafe = [r for r in rows if r["key_turn"] and not r["refusal"]]
    rest = [r for r in rows if not r["key_turn"]]
    rng.shuffle(keysafe); rng.shuffle(rest)
    keysafe = keysafe[: max(len(ref), 200)]
    rest = rest[: 2 * len(ref) + 400]
    out = ref * a.refusal_weight + keysafe + rest
    out = out * a.epochs
    rng.shuffle(out)
    with open(a.out, "w") as fh:
        for r in out:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(stats, "-> refusals", len(ref), "x", a.refusal_weight, "| key-safe", len(keysafe), "| other", len(rest), "| epochs", a.epochs, "| rows", len(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", required=True); c.add_argument("--worlds", default="runs/worlds_train"); c.add_argument("--G", type=int, default=2)
    c.add_argument("--model", default="base"); c.add_argument("--workers", type=int, default=160); c.add_argument("--n-servers", type=int, default=5)
    c.add_argument("--temperature", type=float, default=0.9); c.add_argument("--seed", type=int, default=0)
    b = sub.add_parser("build")
    b.add_argument("--episodes", nargs="+", required=True); b.add_argument("--out", required=True)
    b.add_argument("--refusal-weight", type=int, default=4); b.add_argument("--epochs", type=int, default=2)
    a = ap.parse_args()
    {"collect": collect, "build": build}[a.cmd](a)
