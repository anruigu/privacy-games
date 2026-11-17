"""Companion to selfplay.attacker_debug (PRIVACYZERO.md §6.11). Run from the repo root:  python -m selfplay.attacker_debug_rows  (writes runs/selfplay_eval/attacker_debug/rows.md)"""
import json, sys
sys.path.insert(0, ".")
from collections import Counter, defaultdict
import numpy as np
from selfplay.attacker_debug import classify, world, load, RUNS, R, LABELS, SHORT

def lab(q, w): return SHORT[LABELS.index(classify(q, w))]

print("## F. Row-level advantage by question label and outcome (defender training rows actually written, pooled over iterations)\n")
print("leaked = the answer at that turn disclosed a PROTECTED fact (approver name / floor / team) or ≥0.5 bit by the parser. "
      "adv = turn-level group-normalised return-to-go advantage that the trainer saw (think tokens weighted 0.3).\n")
print("| run | attacker class | label | rows | leaked rows | mean adv leaked | mean adv clean | share of rows | key_turn frac |")
print("|---|---|---|---|---|---|---|---|---|")
for run, its in RUNS.items():
    agg = defaultdict(lambda: dict(n=0, nl=0, al=[], ac=[], kt=0))
    tot = 0
    for it in its:
        pe, pd = R / run / f"it{it:02d}_episodes.jsonl", R / run / f"it{it:02d}_def.jsonl"
        if not pe.exists() or not pd.exists(): continue
        idx = {}
        for e in load(pe):
            w = world(e["seed"]); prot = {f.id for f in w.facts if f.norm == "protected"}
            for t, (tu, s) in enumerate(zip(e["turns"], e["def_samples"])):
                leaked = bool(set(tu.get("ids") or []) & prot) or float(tu.get("leak") or 0) >= 0.5
                idx[(e["seed"], t, tu["question"].strip(), s["raw"])] = (e["attacker"], lab(tu["question"], w), leaked)
        for r in load(pd):
            if r.get("anchor"): continue
            us = [m["content"] for m in r["messages"] if m["role"] == "user"]
            k = (r["seed"], len(us) - 1, us[-1].strip(), r["raw"])
            if k not in idx: continue
            att, l, leaked = idx[k]
            cls = "llm (trained)" if att.startswith("llm@") and not att.endswith("@base") else ("llm (base)" if att.startswith("llm@") else att)
            d = agg[(cls, l)]; d["n"] += 1; d["nl"] += leaked; d["kt"] += bool(r.get("key_turn"))
            (d["al"] if leaked else d["ac"]).append(r["adv"]); tot += 1
    for (cls, l), d in sorted(agg.items()):
        if d["n"] < 20: continue
        print(f"| {run} | {cls} | {l} | {d['n']} | {d['nl']} | {np.mean(d['al']) if d['al'] else float('nan'):+.2f} | {np.mean(d['ac']) if d['ac'] else float('nan'):+.2f} | {d['n']/tot:.2f} | {d['kt']/d['n']:.2f} |")

print("\n## G. Most common attacker phrasings (normalised), base vs trained\n")
def norm(q, w):
    s = q.strip().lower()
    for e in w.employees: s = s.replace(e.name.lower(), "<name>")
    for b in ("building a", "building b"): s = s.replace(b, "building <x>")
    import re
    s = re.sub(r"floor \d", "floor <n>", s); s = re.sub(r"\b(finance|legal|operations|engineering)\b", "<team>", s)
    return s
for run, pairs in {"dsp2": [(0, "llm@base"), (5, "llm@dsp2_att_it04")], "exp2": [(1, "llm@base"), (3, "llm@att_it01")], "sp_s1": [(1, "llm@base"), (3, "llm@sp_s1_att_it01")]}.items():
    for it, att in pairs:
        c = Counter(); n = 0
        for e in load(R / run / f"it{it:02d}_episodes.jsonl"):
            if e["attacker"] != att: continue
            w = world(e["seed"])
            for t in e["turns"]: c[norm(t["question"], w)] += 1; n += 1
        print(f"\n**{run} it{it} {att}** ({n} questions, {len(c)} distinct):\n")
        for q, k in c.most_common(12): print(f"- {k/n:.3f}  {q}")

print("\n## H. One scripted-direct and one scripted-ladder question list (world 1305)\n")
for kind in ("scripted-direct", "scripted-ladder"):
    for e in load(R / "dsp2" / "it05_episodes.jsonl"):
        if e["attacker"] == kind:
            print(f"**{kind}**, world {e['seed']}:"); [print(f"  Q{t['t']}: {t['question']}") for t in e["turns"]]; break
