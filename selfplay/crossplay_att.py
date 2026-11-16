"""Cross-play of defender checkpoints against TRAINED attacker adapters on the held-out worlds (local parser).

The held-out evals use fixed attackers (scripted, Haiku, Sonnet); this is the test self-play is supposed to win:
does a defender trained with an adapting attacker resist an adapting attacker better than one trained against
fixed attackers? Each (defender, attacker) pair plays G episodes per held-out world (runs/worlds seeds 0..n-1).

  LOCAL_LLM_URLS=http://localhost:18000,... python -m selfplay.crossplay_att --out runs/selfplay_eval/crossplay_att
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from .episode import Cfg, run_episode
from .local_llm import LocalLLM
from .loop import load_worlds
from .parser_local import LocalParser

R = "/shared/allie/privacy/selfplay/run"
DEFENDERS = {  # name served on vLLM -> adapter path ("" = base)
    "base": "", "sft_round2": f"{R}/exp2/ckpt/sft_round2", "exp2_def_it01": f"{R}/exp2/ckpt/def_it01",
    "rlvr_def_it03": f"{R}/rlvr/ckpt/rlvr_def_it03", "distill_opus_nll": f"{R}/distill/ckpt/distill_opus_nll",
    "drlvr_def_it03": f"{R}/drlvr/ckpt/drlvr_def_it03", "dsp_def_it03": f"{R}/dsp/ckpt/dsp_def_it03"}
ATTACKERS = {"base": "", "dsp_att_it03": f"{R}/dsp/ckpt/dsp_att_it03", "exp2_att_it03": f"{R}/exp2/ckpt/att_it03",
             "h4_att_it03": f"{R}/h4/ckpt/h4_att_it03"}


def main(a):
    import os
    llm = LocalLLM(os.environ["LOCAL_LLM_URLS"].split(","))
    for name, path in {**DEFENDERS, **ATTACKERS}.items():
        if path:
            llm.load_lora(name, path)
    parser = LocalParser(llm)
    worlds = load_worlds(Path("runs/worlds"), seeds=range(a.n))
    cfg = Cfg(def_temperature=0.7)   # eval temperature, as eval_ckpt
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    path = out / "episodes.jsonl"
    done = set()
    if path.exists():
        for l in path.read_text().splitlines():
            e = json.loads(l); done.add((e["defender"], e["attacker"], e["seed"], e["g"]))
    rng = random.Random(0)
    jobs = [(d, f"llm@{k}", w, g) for d in a.defenders.split(",") for k in a.attackers.split(",") for w in worlds for g in range(a.G)
            if (d, f"llm@{k}", w.seed, g) not in done]
    print(f"{len(jobs)} episodes to run ({len(done)} done)", flush=True)
    with path.open("a") as fh, ThreadPoolExecutor(a.workers) as ex:
        futs = {ex.submit(run_episode, w, d, k, llm, parser, cfg, random.Random(rng.random()), None, False): (d, k, w.seed, g)
                for (d, k, w, g) in jobs}
        n = 0
        for f in as_completed(futs):
            d, k, seed, g = futs[f]
            try:
                e = f.result()
            except Exception as ex_:  # noqa
                print("ERR", d, k, seed, repr(ex_)[:150], flush=True); continue
            e["g"] = g
            fh.write(json.dumps(e, ensure_ascii=False) + "\n"); fh.flush(); n += 1
            if n % 50 == 0:
                print(f"  {n}/{len(jobs)} last {d} vs {k} seed={seed} leak={e['leak_bits']:.2f} util={e['utility']:.2f}", flush=True)
    report(out)


def report(out: Path):
    eps = [json.loads(l) for l in (out / "episodes.jsonl").read_text().splitlines() if l.strip()]
    by = defaultdict(list)
    for e in eps:
        by[(e["defender"], e["attacker"])].append(e)
    atts = sorted({k for _, k in by}, key=lambda k: (k != "llm@base", k))
    defs = [d for d in DEFENDERS if any((d, k) in by for k in atts)]
    res = {}
    lines = ["| defender | " + " | ".join(f"{k.split('@')[1]}: ≥1 bit / bits / util / asked d1 / guess correct" for k in atts) + " |", "|---|" + "---|" * len(atts)]
    for d in defs:
        cells = []
        for k in atts:
            es = by.get((d, k), [])
            if not es:
                cells.append("–"); continue
            t = {"n": len(es), "leak1": float(np.mean([e["leak_bits"] >= 1 - 1e-9 for e in es])), "bits": float(np.mean([e["leak_bits"] for e in es])),
                 "utility": float(np.mean([e["utility"] for e in es])), "violations": float(np.mean([e["violations"] for e in es])),
                 "asked_d1": float(np.mean([list(e["asked_key"].values())[0] for e in es])), "correct": float(np.mean([bool(e["correct"]) for e in es])),
                 "fab": float(np.mean([e["fabrications"] for e in es]))}
            res[f"{d}|{k}"] = t
            cells.append(f"{t['leak1']:.2f} / {t['bits']:.2f} / {t['utility']:.2f} / {t['asked_d1']:.2f} / {t['correct']:.2f}")
        lines.append(f"| {d} | " + " | ".join(cells) + " |")
    (out / "summary.json").write_text(json.dumps(res, indent=1))
    (out / "crossplay.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="runs/selfplay_eval/crossplay_att")
    ap.add_argument("--defenders", default=",".join(DEFENDERS)); ap.add_argument("--attackers", default=",".join(ATTACKERS))
    ap.add_argument("--n", type=int, default=50); ap.add_argument("--G", type=int, default=2); ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    report(Path(a.out)) if a.report_only else main(a)
