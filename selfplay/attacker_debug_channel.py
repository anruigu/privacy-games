"""Companion to selfplay.attacker_debug (PRIVACYZERO.md §6.11). Run from the repo root:  python -m selfplay.attacker_debug_channel  (writes runs/selfplay_eval/attacker_debug/channel.md)"""
import json, sys
sys.path.insert(0, ".")
from collections import Counter, defaultdict
import numpy as np
from selfplay.attacker_debug import classify, world, load, RUNS, R, LABELS, SHORT

def lab(q, w):
    return SHORT[LABELS.index(classify(q, w))]

print("## C. Which question type leaks, per attacker kind (training rollouts, pooled over iterations)\n")
print("P(turn leaks ≥ 0.5 bit | question label) and share of all leaked bits by label. Scripted attackers' label mix shown for comparison.\n")
print("| run | its | attacker kind | label mix (frac of turns) | P(leak | label) | share of leaked bits by label |")
print("|---|---|---|---|---|---|")
for run, its in RUNS.items():
    pool = defaultdict(lambda: dict(n=Counter(), leakn=Counter(), bits=Counter(), eps=0))
    for it in its:
        p = R / run / f"it{it:02d}_episodes.jsonl"
        if not p.exists(): continue
        for e in load(p):
            k = e["attacker"]; k = "llm@trained" if k.startswith("llm@") and not k.endswith("@base") else k
            w = world(e["seed"]); d = pool[k]; d["eps"] += 1
            for t in e["turns"]:
                l = lab(t["question"], w); d["n"][l] += 1
                lk = float(t.get("leak", 0.0) or 0.0)
                d["leakn"][l] += lk >= 0.5; d["bits"][l] += lk
    for k, d in sorted(pool.items()):
        tot = sum(d["n"].values()); tb = sum(d["bits"].values()) or 1
        mix = ", ".join(f"{l} {d['n'][l]/tot:.2f}" for l in SHORT if d["n"][l] / tot >= 0.02)
        pl = ", ".join(f"{l} {d['leakn'][l]/d['n'][l]:.2f}" for l in SHORT if d["n"][l] >= 30)
        sh = ", ".join(f"{l} {d['bits'][l]/tb:.2f}" for l in SHORT if d["bits"][l] / tb >= 0.03)
        print(f"| {run} | {len(its)} | {k} ({d['eps']} eps) | {mix} | {pl} | {sh} |")

print("\n## D. Does the defender close the LLM channel over iterations? P(leak | attribute question) and P(leak | name question), LLM attackers\n")
print("| run | it | attacker | n attr turns | P(leak | attribute) | n name turns | P(leak | name) | n director turns | P(leak | director) | P(leak | cover) |")
print("|---|---|---|---|---|---|---|---|---|---|")
for run, its in RUNS.items():
    for it in its:
        p = R / run / f"it{it:02d}_episodes.jsonl"
        if not p.exists(): continue
        n = Counter(); lk = Counter(); att = Counter()
        for e in load(p):
            if not e["attacker"].startswith("llm@"): continue
            att[e["attacker"]] += 1
            w = world(e["seed"])
            for t in e["turns"]:
                l = lab(t["question"], w); n[l] += 1; lk[l] += float(t.get("leak", 0) or 0) >= 0.5
        f = lambda l: f"{lk[l]/n[l]:.2f}" if n[l] else "–"
        print(f"| {run} | {it} | {'/'.join(a.split('@')[1] for a in att)} | {n['attribute']} | {f('attribute')} | {n['name']} | {f('name')} | {n['director']} | {f('director')} | {f('cover')} |")

print("\n## E. Within-group variance of r_def explained by what the ATTACKER asked (LLM-attacker groups)\n")
print("Within each (world, attacker kind) group of 8, regress r_def on the episode's question counts per label (group-demeaned OLS). "
      "R² = share of the defender's advantage variance that is predictable from the attacker's question mix alone.\n")
print("| run | attacker kind | groups | eps | R² (attacker question mix) | R² (asked ≥1 attribute q) |")
print("|---|---|---|---|---|---|")
for run, its in RUNS.items():
    X = defaultdict(list); Y = defaultdict(list); G = defaultdict(set)
    for it in its:
        p = R / run / f"it{it:02d}_episodes.jsonl"
        if not p.exists(): continue
        groups = defaultdict(list)
        for e in load(p):
            groups[(e["seed"], e["attacker"])].append(e)
        for (s, a), g in groups.items():
            if len(g) < 2 or not a.startswith("llm@"): continue
            k = "llm@trained" if not a.endswith("@base") else "llm@base"
            w = world(s)
            feats = []
            for e in g:
                c = Counter(lab(t["question"], w) for t in e["turns"])
                feats.append([c[l] for l in SHORT] + [float(c["attribute"] > 0)])
            feats = np.array(feats, float); y = np.array([e["r_def"] for e in g])
            feats -= feats.mean(0); y = y - y.mean()
            X[k].append(feats); Y[k].append(y); G[k].add((it, s))
    for k in X:
        A = np.vstack(X[k]); y = np.concatenate(Y[k])
        def r2(cols):
            B = A[:, cols]
            if np.allclose(B, 0): return float("nan")
            beta, *_ = np.linalg.lstsq(B, y, rcond=None)
            res = y - B @ beta
            return 1 - res.var() / y.var()
        print(f"| {run} | {k} | {len(G[k])} | {len(y)} | {r2(list(range(len(SHORT)))):.2f} | {r2([len(SHORT)]):.2f} |")
