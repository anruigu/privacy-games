"""What did the self-play attacker learn, and why does the defender not get better against it?

Part A (attacker): regex taxonomy of attacker questions per attacker checkpoint, from the cross-play episodes
(7 defenders x 4 attackers) and from the training rollouts of the self-play runs (attacker checkpoints over iterations).
Part B (defender signal): per run / iteration / attacker kind, how much within-group contrast the defender's return has
(group = (world, attacker kind), G = 8), i.e. how much gradient the trained-attacker episodes can contribute.

  python -m selfplay.attacker_debug --out runs/selfplay_eval/attacker_debug
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from selfplay.loop import group_adv, load_worlds

R = Path("selfplay/run")
RUNS = {  # run -> iterations with a trained attacker present (p_att > 0 and state att != base)
    "exp2": [0, 1, 2, 3], "sp_s1": [0, 1, 2, 3], "sp_s2": [0, 1, 2, 3], "dsp": [0, 1, 2, 3], "dsp_s1": [0, 1, 2, 3],
    "dsp2": [0, 1, 2, 3, 4, 5], "rlvr": [0, 1, 2, 3, 4, 5], "drlvr": [0, 1, 2, 3],
}


def load(p):
    out = []
    for l in open(p):
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out


_W = {}


def world(seed):
    if seed not in _W:
        for d in ("runs/worlds", "runs/worlds_train", "runs/worlds_train_null"):
            f = next(iter(Path(d).glob(f"seed_{seed:03d}.json")), None) or next(iter(Path(d).glob(f"seed_{seed}.json")), None)
            if f and f.exists():
                from selfplay.loop import World
                _W[seed] = World.load(f.read_text()); break
        else:
            raise KeyError(seed)
    return _W[seed]


def classify(q: str, w) -> str:
    """One label per attacker message (first match wins)."""
    s = q.strip().lower()
    if not s:
        return "empty"
    names = [e.name.lower() for e in w.employees]
    directors = [e.name.lower() for e in w.employees if e.is_director]
    pivots = [w.emp(p).name.lower() for p in w.pivots]
    memo = "memo" in s or "approv" in s or "sign" in s
    is_q = "?" in s
    if memo and not is_q and any(d in s for d in directors):
        return "assert: 'the memo was approved by <name>'"
    if memo and re.search(r"\bwho\b|\bwhom\b|\bname\b|which director|which of the", s) and not re.search(r"floor|building|team", s):
        return "ask approver NAME directly"
    if memo and any(d in s for d in directors) and is_q:
        return "yes/no: 'did <director> approve?'"
    if memo and re.search(r"floor|building|team|department", s) and not any(p in s for p in pivots):
        return "ask approver ATTRIBUTE (floor / building / team)"
    if memo and any(p in s for p in pivots):
        return "key-chain: approver vs pivot (same floor as X?)"
    if any(p in s for p in pivots):
        return "pivot facts (transferred person's floor / team / building)"
    if any(d in s for d in directors):
        return "director facts (where does <director> sit, on call?)"
    return "other / cover task"


def episode_feats(e):
    w = world(e["seed"])
    qs = [t["question"] for t in e["turns"]]
    labs = [classify(q, w) for q in qs]
    seen, rep = set(), 0
    for q in qs:
        k = q.strip().lower()
        rep += k in seen
        seen.add(k)
    att_empty = sum(1 for q in qs if not q.strip())
    return dict(labels=labs, n_q=len(qs), repeats=rep, mean_len=float(np.mean([len(q) for q in qs])) if qs else 0.0,
                leak1=float(e["leak_bits"] >= 1 - 1e-9), bits=float(e["leak_bits"]), leak_frac=float(e["leak_frac"]),
                correct=float(bool(e.get("correct"))), guess_given=float(bool(e.get("guess"))),
                asked_key_any=float(any(e["asked_key"].values())), asked_key_all=float(all(e["asked_key"].values())),
                key_disc_any=float(any(e["key_disclosed"].values())), r_att=float(e["r_att"]), r_def=float(e["r_def"]),
                utility=float(e["utility"]), empty_q=att_empty / max(len(qs), 1))


def agg(feats):
    n = len(feats)
    lab = Counter(l for f in feats for l in f["labels"])
    tot = sum(lab.values())
    out = {k: float(np.mean([f[k] for f in feats])) for k in ("n_q", "repeats", "mean_len", "leak1", "bits", "leak_frac", "correct",
                                                               "asked_key_any", "asked_key_all", "key_disc_any", "r_att", "r_def", "utility", "empty_q")}
    out["n"] = n
    out["labels"] = {k: v / tot for k, v in lab.items()}
    return out


LABELS = ["ask approver NAME directly", "ask approver ATTRIBUTE (floor / building / team)", "yes/no: 'did <director> approve?'",
          "assert: 'the memo was approved by <name>'", "key-chain: approver vs pivot (same floor as X?)",
          "pivot facts (transferred person's floor / team / building)", "director facts (where does <director> sit, on call?)",
          "other / cover task", "empty"]
SHORT = ["name", "attribute", "yes/no name", "assert name", "key-chain", "pivot", "director", "cover", "empty"]


def table_a(rows, title, md):
    md.append(f"\n### {title}\n")
    md.append("| attacker | n eps | " + " | ".join(SHORT) + " | repeats/ep | len | ≥1 bit | bits | guess ok | asked key (any/all) | r_att |")
    md.append("|---|---|" + "---|" * len(SHORT) + "---|---|---|---|---|---|---|")
    for name, a in rows:
        md.append(f"| {name} | {a['n']} | " + " | ".join(f"{a['labels'].get(l, 0):.2f}" for l in LABELS) +
                  f" | {a['repeats']:.1f} | {a['mean_len']:.0f} | {a['leak1']:.2f} | {a['bits']:.2f} | {a['correct']:.2f} | {a['asked_key_any']:.2f}/{a['asked_key_all']:.2f} | {a['r_att']:.2f} |")


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    md = ["# Attacker debug: what the self-play attacker learned, and the defender's signal against it\n",
          "Question labels (regex, first match): name = asks who approved; attribute = asks the approver's floor/building/team; "
          "yes/no name = 'did <director> approve?'; assert name = a statement 'the memo was approved by <name>'; key-chain = approver vs a "
          "transferred person; pivot = the transferred person's own floor/team/building; director = facts about a named director; cover = anything else.\n"]
    # ---------- A1: cross-play ----------
    xp = load("runs/selfplay_eval/crossplay_att/episodes.jsonl")
    by_att = defaultdict(list); by_att_def = defaultdict(list)
    for e in xp:
        f = episode_feats(e); by_att[e["attacker"]].append(f); by_att_def[(e["attacker"], e["defender"])].append(f)
    table_a([(k.split("@")[1], agg(v)) for k, v in sorted(by_att.items())], "A1. Cross-play, all 7 defenders pooled (50 held-out worlds × G 2 each)", md)
    for d in ["base", "sft_round2", "distill_opus_nll", "drlvr_def_it03", "dsp_def_it03"]:
        table_a([(k[0].split("@")[1], agg(v)) for k, v in sorted(by_att_def.items()) if k[1] == d], f"A1.{d}: cross-play vs defender {d}", md)
    # ---------- A2: training rollouts over iterations ----------
    sig = {}
    for run, its in RUNS.items():
        rows = []
        for it in its:
            p = R / run / f"it{it:02d}_episodes.jsonl"
            if not p.exists():
                continue
            eps = load(p)
            kinds = defaultdict(list)
            for e in eps:
                kinds[e["attacker"]].append(e)
            for k, es in sorted(kinds.items()):
                feats = [episode_feats(e) for e in es]
                a = agg(feats)
                # defender signal: group = (seed, attacker kind); advantage of r_def within the group
                groups = defaultdict(list)
                for e in es:
                    groups[e["seed"]].append(e)
                advs, zero_groups, stds, keyturn_rows = [], 0, [], 0
                for s, g in groups.items():
                    ad = group_adv([x["r_def"] for x in g]); advs += [abs(x) for x in ad]
                    sd = float(np.std([x["r_def"] for x in g])); stds.append(sd); zero_groups += sd < 1e-6
                sig[(run, it, k)] = dict(n=len(es), leak1=a["leak1"], bits=a["bits"], r_def=a["r_def"], util=a["utility"],
                                         std_rdef=float(np.mean(stds)), zero_frac=zero_groups / max(len(groups), 1),
                                         mean_abs_adv=float(np.mean(advs)) if advs else 0.0, groups=len(groups),
                                         r_att=a["r_att"], std_ratt=float(np.mean([np.std([x["r_att"] for x in g]) for g in groups.values()])))
                if k.startswith("llm@"):
                    rows.append((f"it{it} {k.split('@')[1]}", a))
        if rows:
            table_a(rows, f"A2.{run}: training rollouts, LLM attackers by iteration (48 train worlds × G 8; the attacker kind is drawn per world)", md)
    # ---------- B: defender signal per attacker kind ----------
    md.append("\n## B. Defender signal by attacker kind (training rollouts)\n")
    md.append("Group = (world, attacker kind), G = 8 defender samples. zero-adv groups = fraction of groups whose eight r_def values are identical "
              "(no gradient at all from that world); mean |adv| = mean absolute group-normalised advantage over episodes; std r_def = mean within-group std.\n")
    md.append("| run | it | attacker kind | eps | groups | ≥1 bit | bits | mean r_def | std r_def | zero-adv groups | mean abs adv | mean r_att | std r_att |")
    md.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for (run, it, k), s in sorted(sig.items()):
        md.append(f"| {run} | {it} | {k} | {s['n']} | {s['groups']} | {s['leak1']:.2f} | {s['bits']:.2f} | {s['r_def']:.2f} | {s['std_rdef']:.2f} | {s['zero_frac']:.2f} | {s['mean_abs_adv']:.2f} | {s['r_att']:.2f} | {s['std_ratt']:.2f} |")
    # ---------- B2: share of defender training rows by attacker kind ----------
    md.append("\n### B2. Share of the defender's training rows (after the 1,200-row cap) by attacker kind\n")
    md.append("| run | it | " + " | ".join(["llm@trained", "llm@base", "scripted-direct", "scripted-ladder"]) + " | rows | mean abs adv (trained / scripted-direct) |")
    md.append("|---|---|---|---|---|---|---|---|")
    for run, its in RUNS.items():
        for it in its:
            pe, pd = R / run / f"it{it:02d}_episodes.jsonl", R / run / f"it{it:02d}_def.jsonl"
            if not pe.exists() or not pd.exists():
                continue
            key2kind = {}
            for e in load(pe):
                q0 = e["turns"][0]["question"] if e["turns"] else ""
                key2kind[(e["seed"], q0.strip())] = e["attacker"]
            cnt, adv = Counter(), defaultdict(list)
            for r in load(pd):
                if r.get("anchor"):
                    continue
                q0 = next((m["content"] for m in r["messages"] if m["role"] == "user"), "").strip()
                k = key2kind.get((r["seed"], q0), "?")
                kk = "llm@trained" if k.startswith("llm@") and not k.endswith("@base") else k
                cnt[kk] += 1; adv[kk].append(abs(r["adv"]))
            tot = sum(cnt.values())
            md.append(f"| {run} | {it} | " + " | ".join(f"{cnt.get(c, 0) / max(tot, 1):.2f}" for c in ["llm@trained", "llm@base", "scripted-direct", "scripted-ladder"]) +
                      f" | {tot} | {np.mean(adv['llm@trained']) if adv['llm@trained'] else float('nan'):.2f} / {np.mean(adv['scripted-direct']) if adv['scripted-direct'] else float('nan'):.2f} |")
    (out / "attacker_debug.md").write_text("\n".join(md) + "\n")
    json.dump({f"{k[0]}|{k[1]}|{k[2]}": v for k, v in sig.items()}, open(out / "signal.json", "w"), indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, default=Path("runs/selfplay_eval/attacker_debug"))
    main(ap.parse_args().out)
