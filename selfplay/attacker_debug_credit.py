"""Companion to selfplay.attacker_debug (PRIVACYZERO.md §6.11). Run from the repo root:  python -m selfplay.attacker_debug_credit  (writes runs/selfplay_eval/attacker_debug/credit.md)"""
import json, sys
sys.path.insert(0, ".")
from collections import defaultdict
import numpy as np
from selfplay.attacker_debug import classify, world, load, RUNS, R, LABELS, SHORT
from selfplay.loop import group_adv
def lab(q, w): return SHORT[LABELS.index(classify(q, w))]

print("## I. Credit assignment on the LLM channel: turn-level (what was trained) vs episode-level advantage, recomputed from the rollouts\n")
print("Rows = all defender turns in training rollouts (before the cap). 'attribute refused' = approver-attribute question answered without disclosing a protected fact or ≥0.5 bit. "
      "leaked-before = ≥1 bit already leaked earlier in the same episode. Turn-level adv = group-normalised return-to-go at the same turn index (as trained); episode-level = group-normalised episode return.\n")
print("| run | attacker class | attribute leaked: n / turn adv / ep adv | attribute refused: n / turn adv / ep adv | refused but episode leaks ≥1 bit anyway | turn adv when leaked-before vs not (all turns) | key-chain (scripted) leaked / refused turn adv |")
print("|---|---|---|---|---|---|---|")
for run, its in RUNS.items():
    S = defaultdict(lambda: defaultdict(list))
    for it in its:
        p = R / run / f"it{it:02d}_episodes.jsonl"
        if not p.exists(): continue
        groups = defaultdict(list)
        for e in load(p): groups[(e["seed"], e["attacker"])].append(e)
        for (s, a), g in groups.items():
            if len(g) < 2: continue
            cls = "llm" if a.startswith("llm@") else "scripted"
            w = world(s); prot = {f.id for f in w.facts if f.norm == "protected"}
            ep_adv = group_adv([e["r_def"] for e in g])
            T = max(len(e["def_samples"]) for e in g)
            for t in range(T):
                idx = [i for i, e in enumerate(g) if len(e["def_samples"]) > t]
                if len(idx) < 2: continue
                ta = group_adv([g[i]["def_samples"][t].get("rtg", 0.0) for i in idx])
                for i, av in zip(idx, ta):
                    e = g[i]; tu = e["turns"][t]
                    l = lab(tu["question"], w)
                    leaked = bool(set(tu.get("ids") or []) & prot) or float(tu.get("leak") or 0) >= 0.5
                    before = sum(float(x.get("leak") or 0) for x in e["turns"][:t]) >= 1 - 1e-9
                    ep_leak = e["leak_bits"] >= 1 - 1e-9
                    d = S[cls]
                    d["all_before" if before else "all_not"].append(av)
                    if l == "attribute":
                        d["attr_leak_t" if leaked else "attr_ref_t"].append(av)
                        d["attr_leak_e" if leaked else "attr_ref_e"].append(ep_adv[i])
                        if not leaked: d["attr_ref_eplk"].append(ep_leak)
                    if l == "key-chain" and cls == "scripted":
                        d["kc_leak_t" if leaked else "kc_ref_t"].append(av)
    for cls, d in sorted(S.items()):
        m = lambda k: f"{np.mean(d[k]):+.2f}" if d[k] else "–"
        print(f"| {run} | {cls} | {len(d['attr_leak_t'])} / {m('attr_leak_t')} / {m('attr_leak_e')} | {len(d['attr_ref_t'])} / {m('attr_ref_t')} / {m('attr_ref_e')} | "
              f"{np.mean(d['attr_ref_eplk']) if d['attr_ref_eplk'] else float('nan'):.2f} | {m('all_before')} vs {m('all_not')} | {m('kc_leak_t')} / {m('kc_ref_t')} |")
