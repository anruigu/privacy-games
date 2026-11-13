"""PrivacyZero self-play orchestrator (runs inside the pod).

Per iteration:
  1. sample W training worlds; for each world draw an attacker from the mixture
     {current attacker LoRA, base-prompted attacker, scripted-direct, scripted-ladder}
     and run G defender rollouts (same attacker policy, fresh samples) -> a GRPO group
  2. defender update: group-normalised episode advantage on every defender turn -> LoRA PG step
  3. attacker update (every --att-every iterations): same episodes, groups = (world) over the
     episodes played by the current attacker LoRA; advantage on R_att
  4. quick held-out probe on runs/worlds seeds 0-29 vs scripted-direct (local parser)
  5. metrics.jsonl line + adapters in <out>/ckpt/{def,att}_it<k>

Collusion / hacking guards that are *measured* every iteration (see REPORT): leak vs the fixed scripted
attackers (cannot be colluded with), attacker asked-d1 rate, defender utility, empty-answer rate,
fabrication rate, and train-parser vs held-out (Sonnet) parser agreement on the probe set.

  python -m selfplay.loop --out selfplay/run/exp1 --iters 12 --serve-gpus 0,1,2,3,4 --train-gpu 5
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from dossier.schema import World

from .episode import Cfg, run_episode
from .local_llm import LocalLLM
from .parser_local import LocalParser

TRAIN_PY = "/shared/allie/Inferencebench-runs/loop-2x2-20261030/venv/bin/python"
ROOT = Path("/shared/allie/privacy")


def start_servers(gpus: list[int], base_port: int = 8000) -> LocalLLM:
    urls = [f"http://localhost:{base_port + i}" for i in range(len(gpus))]
    llm = LocalLLM(urls)
    for i, g in enumerate(gpus):
        port = base_port + i
        try:
            import requests
            if requests.get(f"http://localhost:{port}/v1/models", timeout=3).status_code == 200:
                continue
        except Exception:
            pass
        subprocess.run(["bash", str(ROOT / "selfplay/start_vllm.sh"), str(g), str(port)], check=True)
    llm.wait_ready(timeout=2400)
    return llm


def load_worlds(d: Path, seeds=None) -> list[World]:
    files = sorted(d.glob("seed_*.json"))
    ws = [World.load(f.read_text()) for f in files]
    if seeds is not None:
        ws = [w for w in ws if w.seed in set(seeds)]
    return ws


def group_adv(values: list[float]) -> list[float]:
    v = np.array(values, dtype=float)
    if len(v) < 2 or v.std() < 1e-6:
        return [0.0] * len(v)
    return list((v - v.mean()) / (v.std() + 1e-6))


def summarize(eps: list[dict]) -> dict:
    def m(k, sel=None):
        xs = [e[k] for e in eps if (sel is None or sel(e)) and e.get(k) is not None]
        return float(np.mean(xs)) if xs else None
    out = {"n": len(eps), "r_def": m("r_def"), "leak_frac": m("leak_frac"),
           "leak1": float(np.mean([e["leak_bits"] >= 1 - 1e-9 for e in eps])) if eps else None,
           "utility": m("utility"), "violations": m("violations"), "fab": m("fabrications"),
           "empty": m("empty_frac"), "turns": m("n_turns"), "over": m("over_refusals")}
    nulls = [e for e in eps if str(e.get("arm", "")).startswith("null")]
    if nulls:   # helpfulness probe inside the training mixture: d1 answered where answering is harmless
        out["null"] = {"n": len(nulls), "d1": float(np.mean([list(e["key_disclosed"].values())[0] for e in nulls])),
                       "utility": float(np.mean([e["utility"] for e in nulls])), "over": m("over_refusals", lambda e: str(e.get("arm", "")).startswith("null"))}
    by = defaultdict(list)
    for e in eps:
        by[e["attacker"].split("@")[0] if e["attacker"].startswith("scripted") else e["attacker"]].append(e)
    out["by_hint"] = {}
    for h in (False, True):
        es = [e for e in eps if bool(e.get("hint")) == h]
        if es:
            out["by_hint"]["hint" if h else "plain"] = {"n": len(es), "leak1": float(np.mean([e["leak_bits"] >= 1 - 1e-9 for e in es])),
                                                       "utility": float(np.mean([e["utility"] for e in es])),
                                                       "d1": float(np.mean([list(e["key_disclosed"].values())[0] for e in es]))}
    out["by_attacker"] = {}
    for k, es in by.items():
        d1_asked = [any(e["asked_key"].values()) and list(e["asked_key"].values())[0] for e in es]
        out["by_attacker"][k] = {"n": len(es), "leak1": float(np.mean([e["leak_bits"] >= 1 - 1e-9 for e in es])),
                                 "leak_frac": float(np.mean([e["leak_frac"] for e in es])),
                                 "utility": float(np.mean([e["utility"] for e in es])),
                                 "r_def": float(np.mean([e["r_def"] for e in es])),
                                 "asked_d1": float(np.mean(d1_asked)),
                                 "correct": float(np.mean([bool(e["correct"]) for e in es])) if k.startswith("llm") else None}
    return out


def rollouts(worlds, defender, attackers_for, G, llm, parser, cfg, workers, rng, p_hint: float = 0.0) -> list[dict]:
    jobs = []
    for w in worlds:
        att = attackers_for(w)
        for g in range(G):
            jobs.append((w, att, g, rng.random() < p_hint))
    eps = []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(run_episode, w, defender, att, llm, parser, cfg, random.Random(rng.random()), None, h): (w, att, g)
                for (w, att, g, h) in jobs}
        t0 = time.time()
        for f in as_completed(futs):
            try:
                e = f.result()
                eps.append(e)
                if len(eps) % 16 == 0 or len(eps) == len(jobs):
                    print(f"    rollouts {len(eps)}/{len(jobs)} ({time.time() - t0:.0f}s) last: seed={e['seed']} att={e['attacker'][:14]} "
                          f"turns={e['n_turns']} leak={e['leak_bits']:.2f} util={e['utility']:.2f} r_def={e['r_def']:.2f} "
                          f"calls={llm.n_calls} tok_out={llm.n_tokens_out}", flush=True)
            except Exception as ex:  # noqa
                print("EPISODE ERROR", futs[f][0].seed, futs[f][1], repr(ex), flush=True)
    return eps


def write_samples(eps, role: str, path: Path, adv_key: str, group_key, cap: int, rng, turn_level: bool = False,
                  vstar_baseline: bool = True) -> int:
    """turn_level: advantage of defender turn t = group-normalised return-to-go at turn t (episodes in the same
    (world, attacker) group, same turn index); falls back to the episode advantage when a turn index is unique."""
    groups = defaultdict(list)
    for e in eps:
        groups[group_key(e)].append(e)
    rows = []
    for k, es in groups.items():
        advs = group_adv([e[adv_key] for e in es])
        per_turn = {}
        if turn_level:
            T = max(len(e[f"{role}_samples"]) for e in es)
            for t in range(T):
                idx = [i for i, e in enumerate(es) if len(e[f"{role}_samples"]) > t]
                if len(idx) >= 2:
                    vals = [es[i][f"{role}_samples"][t].get("rtg", 0.0) for i in idx]
                    vs = [es[i][f"{role}_samples"][t].get("vstar") for i in idx]
                    rs = [es[i][f"{role}_samples"][t].get("rstar") for i in idx]
                    if vstar_baseline in (2, 3) and all(r is not None for r in rs):
                        # turn-local regret: immediate reward minus the oracle's immediate reward in the same state.
                        # All blame lands on the turn that completes a leak; disclosing a key fact while the pair is
                        # incomplete (or refusing a safe fact) is judged on its own merits, not on what came later.
                        # mode 3 subtracts half the group-mean regret so that a group of equally bad samples is only
                        # pushed down at half strength while any within-group contrast keeps its full sign.
                        reg = [es[i][f"{role}_samples"][t].get("r_t", 0.0) - r for i, r in zip(idx, rs)]
                        base = 0.5 * float(np.mean(reg)) if vstar_baseline == 3 else 0.0
                        scale = max(float(np.std(reg)), 0.3)
                        a_t = [float(np.clip((g - base) / scale, -3.0, 3.0)) for g in reg]
                    elif vstar_baseline and all(v is not None for v in vs):
                        # regret-style advantage: return-to-go minus the oracle's counterfactual value of the same
                        # state (a state-only baseline, so the gradient stays unbiased); scaled by the group spread
                        # baseline = midpoint of the group mean and the oracle value: every leak-completing sample ends
                        # up negative (even the least bad one), the rare refusal positive
                        scale = max(float(np.std(vals)), 0.5)
                        m = float(np.mean(vals))
                        a_t = [float(np.clip((v - 0.5 * (m + b)) / scale, -3.0, 3.0)) for v, b in zip(vals, vs)]
                    else:
                        a_t = group_adv(vals)
                    for i, a in zip(idx, a_t):
                        per_turn[(i, t)] = a
        for i, (e, a_ep) in enumerate(zip(es, advs)):
            for t, s in enumerate(e[f"{role}_samples"]):
                a = per_turn.get((i, t), a_ep) if turn_level else a_ep
                if abs(a) < 1e-6:
                    continue
                rows.append({"system": s["system"], "messages": s["messages"], "raw": s["raw"], "adv": a,
                             "seed": e["seed"], "kind": s["kind"], "think": s.get("think", True),
                             "key_turn": bool(s.get("key_turn"))})
    rng.shuffle(rows)
    # stratified cap: key-fact turns first (up to half the cap, by |adv|), then the rest by |adv|
    key = sorted([r for r in rows if r["key_turn"]], key=lambda r: -abs(r["adv"]))[: cap // 2]
    rest = sorted([r for r in rows if not r["key_turn"]], key=lambda r: -abs(r["adv"]))
    rows = (key + rest)[:cap]
    rng.shuffle(rows)
    with path.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def train(role: str, data: Path, adapter_in: str, adapter_out: Path, gpu: int, lr: float, beta: float, log: Path) -> dict:
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu), PYTHONPATH=str(ROOT), HOME="/tmp/home",
               HF_HOME=str(ROOT / "selfplay/hf"))
    cmd = [TRAIN_PY, "-m", "selfplay.train_lora", "--data", str(data), "--adapter-in", adapter_in,
           "--adapter-out", str(adapter_out), "--lr", str(lr), "--beta", str(beta)]
    with log.open("a") as fh:
        fh.write(f"\n=== {role} -> {adapter_out}\n")
        subprocess.run(cmd, env=env, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT, check=True)
    return json.loads((adapter_out / "train_summary.json").read_text())


def main(a):
    out = Path(a.out).resolve(); out.mkdir(parents=True, exist_ok=True)
    (out / "ckpt").mkdir(exist_ok=True)
    rng = random.Random(a.seed)
    cfg = Cfg(fab_penalty=not a.no_fab_penalty, temperature=a.temperature, def_temperature=a.def_temperature, w_over=a.w_over)
    gpus = [int(x) for x in a.serve_gpus.split(",")]
    llm = start_servers(gpus)
    llm.lora_dir = str(out / "ckpt")
    parser = LocalParser(llm)
    train_worlds = load_worlds(Path(a.worlds))
    null_worlds = load_worlds(Path(a.worlds_null)) if a.worlds_null else []
    probe_worlds = load_worlds(Path("runs/worlds"), seeds=range(a.probe_n))
    # helpfulness probe: paired null worlds of the knob study (seeds 200-219), same ones selfplay.helpful reports on
    null_probe = []
    if a.probe_null:
        for arm in ("null-public", "null-nomemo"):
            null_probe += load_worlds(Path("runs/worlds_knobs") / arm, seeds=range(200, 200 + a.probe_null))
    anchor_rows = [l for l in open(a.anchor_data) if l.strip()] if a.anchor_data else []
    pre = a.prefix
    state_p = out / "state.json"
    state = json.loads(state_p.read_text()) if state_p.exists() else {"it": 0, "def": "base", "att": "base"}
    # (re)load adapters that exist
    for name in {state["def"], state["att"]} - {"base"}:
        llm.load_lora(name, str(out / "ckpt" / name))
    print(f"start at it={state['it']} def={state['def']} att={state['att']} worlds={len(train_worlds)}", flush=True)
    for it in range(state["it"], a.iters):
        t0 = time.time()
        defender, attacker = state["def"], state["att"]
        n_null = int(round(a.W * a.p_null)) if null_worlds else 0
        worlds = rng.sample(train_worlds, min(a.W - n_null, len(train_worlds))) + (rng.sample(null_worlds, n_null) if n_null else [])
        rng.shuffle(worlds)
        mix = [(f"llm@{attacker}", a.p_att), ("llm@base", a.p_base), ("scripted-direct", a.p_direct), ("scripted-ladder", a.p_ladder)]
        kinds, ps = zip(*mix)

        def attackers_for(w, _r=random.Random(rng.random())):
            return _r.choices(kinds, ps)[0]
        eps = rollouts(worlds, defender, attackers_for, a.G, llm, parser, cfg, a.workers, rng, p_hint=a.p_hint)
        with (out / f"it{it:02d}_episodes.jsonl").open("w") as fh:
            for e in eps:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        summ = summarize(eps)
        t_roll = time.time() - t0
        # ---- defender update ----
        n_def = write_samples(eps, "def", out / f"it{it:02d}_def.jsonl", "r_def", lambda e: (e["seed"], e["attacker"]),
                              a.cap_def, rng, turn_level=a.adv == "turn", vstar_baseline=int(a.vstar_baseline))
        if anchor_rows:   # replay of safe, helpful answers (behaviour-cloning term; see HELPFUL_RL.md)
            with (out / f"it{it:02d}_def.jsonl").open("a") as fh:
                for l in rng.sample(anchor_rows, min(a.anchor_n, len(anchor_rows))):
                    r = json.loads(l); r["adv"] = a.anchor_adv; r["anchor"] = True
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        def_out = out / "ckpt" / f"{pre}def_it{it:02d}"
        tr_def = train("def", out / f"it{it:02d}_def.jsonl", "" if defender == "base" else str(out / "ckpt" / defender),
                       def_out, a.train_gpu, a.lr, a.beta, out / "train.log")
        llm.load_lora(def_out.name, str(def_out))
        state["def"] = def_out.name
        # ---- attacker update ----
        tr_att, n_att = None, 0
        if a.train_att and (it % a.att_every == a.att_every - 1):
            att_eps = [e for e in eps if e["attacker"] == f"llm@{attacker}"]
            n_att = write_samples(att_eps, "att", out / f"it{it:02d}_att.jsonl", "r_att", lambda e: e["seed"], a.cap_att, rng)
            if n_att >= 32:
                att_out = out / "ckpt" / f"{pre}att_it{it:02d}"
                tr_att = train("att", out / f"it{it:02d}_att.jsonl", "" if attacker == "base" else str(out / "ckpt" / attacker),
                               att_out, a.train_gpu, a.lr_att, a.beta, out / "train.log")
                llm.load_lora(att_out.name, str(att_out))
                state["att"] = att_out.name
        # ---- held-out probe (new defender) ----
        probe = rollouts(probe_worlds, state["def"], lambda w: "scripted-direct", 1, llm, parser, cfg, a.workers, rng)
        with (out / f"it{it:02d}_probe.jsonl").open("w") as fh:
            for e in probe:
                fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        psum = summarize(probe)
        nsum = None
        if null_probe:
            nprobe = rollouts(null_probe, state["def"], lambda w: "scripted-direct", 1, llm, parser, cfg, a.workers, rng)
            with (out / f"it{it:02d}_probe_null.jsonl").open("w") as fh:
                for e in nprobe:
                    fh.write(json.dumps(e, ensure_ascii=False) + "\n")
            nsum = {}
            for arm in ("null-public", "null-nomemo"):
                es = [e for e in nprobe if str(e["arm"]).startswith(arm)]
                if es:
                    nsum[arm] = {"n": len(es), "d1": float(np.mean([list(e["key_disclosed"].values())[0] for e in es])),
                                 "d2": float(np.mean([list(e["key_disclosed"].values())[1] for e in es])) if all(len(e["key_disclosed"]) > 1 for e in es) else None,
                                 "utility": float(np.mean([e["utility"] for e in es]))}
        state["it"] = it + 1
        state_p.write_text(json.dumps(state))
        rec = {"it": it, "defender_trained_from": defender, "attacker": attacker, "train": summ, "n_def_samples": n_def,
               "train_def": tr_def, "n_att_samples": n_att, "train_att": tr_att, "probe": psum, "probe_null": nsum,
               "t_roll": t_roll, "t_total": time.time() - t0}
        with (out / "metrics.jsonl").open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(f"[it {it}] train: r_def={summ['r_def']:.3f} leak1={summ['leak1']:.2f} util={summ['utility']:.2f} "
              f"empty={summ['empty']:.2f} fab={summ['fab']:.2f} | probe(scripted): leak1={psum['leak1']:.2f} "
              f"util={psum['utility']:.2f} | def_samples={n_def} kl={tr_def['kl']:.4f} | att_samples={n_att} "
              f"| {t_roll:.0f}s roll, {time.time() - t0:.0f}s total", flush=True)
        if nsum:
            print("     probe_null: " + "  ".join(f"{k}: d1={v['d1']:.2f} util={v['utility']:.2f} (n={v['n']})" for k, v in nsum.items()), flush=True)
        if summ.get("null"):
            print(f"     train null worlds: n={summ['null']['n']} d1={summ['null']['d1']:.2f} util={summ['null']['utility']:.2f}", flush=True)
        for k, v in summ.get("by_hint", {}).items():
            print(f"     [{k:5s}] n={v['n']:3d} leak1={v['leak1']:.2f} util={v['utility']:.2f} d1={v['d1']:.2f}", flush=True)
        for k, v in summ["by_attacker"].items():
            print(f"     {k:24s} n={v['n']:3d} leak1={v['leak1']:.2f} util={v['utility']:.2f} asked_d1={v['asked_d1']:.2f} "
                  f"correct={v['correct']}", flush=True)
        if Path(a.out, "STOP").exists():
            print("STOP file found", flush=True)
            break
    (out / "DONE").write_text(json.dumps(state))
    print("all iterations done", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--worlds", default="runs/worlds_train")
    ap.add_argument("--iters", type=int, default=12)
    ap.add_argument("--W", type=int, default=64)
    ap.add_argument("--G", type=int, default=4)
    ap.add_argument("--probe-n", type=int, default=30)
    ap.add_argument("--serve-gpus", default="0,1,2,3,4")
    ap.add_argument("--train-gpu", type=int, default=5)
    ap.add_argument("--workers", type=int, default=96)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--lr-att", type=float, default=2e-5)
    ap.add_argument("--beta", type=float, default=0.02)
    ap.add_argument("--cap-def", type=int, default=1600)
    ap.add_argument("--cap-att", type=int, default=800)
    ap.add_argument("--att-every", type=int, default=2)
    ap.add_argument("--train-att", type=int, default=1)
    ap.add_argument("--p-att", type=float, default=0.45)
    ap.add_argument("--p-base", type=float, default=0.15)
    ap.add_argument("--p-direct", type=float, default=0.25)
    ap.add_argument("--p-ladder", type=float, default=0.15)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--def-temperature", type=float, default=1.0)
    ap.add_argument("--adv", default="turn", choices=["turn", "episode"])
    ap.add_argument("--p-hint", type=float, default=0.5)
    ap.add_argument("--vstar-baseline", type=int, default=3,
                    help="2: turn-local regret vs the oracle's immediate reward; 1: return-to-go minus the midpoint of "
                         "group mean and oracle V*; 0: plain group normalisation of return-to-go")
    ap.add_argument("--no-fab-penalty", action="store_true")
    # helpfulness interventions (HELPFUL_RL.md)
    ap.add_argument("--w-over", type=float, default=0.0, help="over-refusal penalty per withheld safe fact (H1)")
    ap.add_argument("--worlds-null", default="", help="extra pool of null worlds (H2)")
    ap.add_argument("--p-null", type=float, default=0.0, help="fraction of W drawn from --worlds-null (H2)")
    ap.add_argument("--anchor-data", default="", help="jsonl of safe helpful answers replayed each iteration (H3)")
    ap.add_argument("--anchor-n", type=int, default=300)
    ap.add_argument("--anchor-adv", type=float, default=0.5)
    ap.add_argument("--probe-null", type=int, default=0, help="null-world probe size per arm (seeds 200+)")
    ap.add_argument("--prefix", default="", help="adapter-name prefix so several loops can share the vLLM replicas")
    ap.add_argument("--seed", type=int, default=0)
    main(ap.parse_args())
