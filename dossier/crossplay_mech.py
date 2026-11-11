"""Mechanism table for the cross-play: did the attacker ask for the key facts, and did the holder volunteer them?

Uses runs/crossplay/questions.jsonl (dossier.qparse) with the same convention as dossier.knobs:
a key fact disclosed in a turn whose question did not ask for it counts as volunteered by the holder.

  python -m dossier.crossplay_mech --cross runs/xp_cross/episodes.jsonl runs/xp_cross_qwen9b/episodes.jsonl \
      --questions runs/crossplay/questions.jsonl --out runs/crossplay
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from .crossplay import load, model_of_holder, model_of_seeker, short
from .qparse import key as qkey


def main(cross, questions: Path, out: Path) -> None:
    Q = {}
    for l in questions.read_text().splitlines():
        if l.strip():
            j = json.loads(l); Q[j["key"]] = j
    eps = load(cross)
    worlds = {}
    per_def = defaultdict(list); per_att = defaultdict(list)
    for r in eps:
        if not r["seeker"].startswith("llm-direct"):
            continue
        s = r["seed"]
        if s not in worlds:
            worlds[s] = json.loads(Path(f"runs/worlds/seed_{s:03d}.json").read_text())
        w = worlds[s]
        d1 = next(f["id"] for f in w["facts"] if f["family"] == "key" and f["predicate"]["kind"] == "same_floor_as_pivot")
        d2 = next(f["id"] for f in w["facts"] if f["family"] == "key" and f["predicate"]["kind"] == "pivot_floor")
        asked_d1 = asked_d2 = False; vol_d1 = vol_d2 = False; disc_d1 = disc_d2 = False
        mentions = 0
        for t in r["turns"]:
            q = Q.get(qkey(r, t["t"]), {})
            a = set(q.get("asked_ids", []))
            mentions += int(q.get("mentions_target", False))
            asked_d1 |= d1 in a; asked_d2 |= d2 in a
            if d1 in t["ids"]:
                disc_d1 = True; vol_d1 |= d1 not in a
            if d2 in t["ids"]:
                disc_d2 = True; vol_d2 |= d2 not in a
        rec = {"asked_d1": asked_d1, "asked_d2": asked_d2, "disc_d1": disc_d1, "disc_d2": disc_d2,
               "vol_d1": vol_d1, "vol_d2": vol_d2, "mentions": mentions / max(len(r["turns"]), 1),
               "leak1": r["summary"]["final_leak_releasable_only"] >= 1 - 1e-9,
               "guess": bool(r.get("seeker_correct")), "abstain": not (r.get("seeker_guess") or "").strip()}
        per_def[model_of_holder(r["holder"])].append(rec); per_att[model_of_seeker(r["seeker"])].append(rec)

    def row(name, rs):
        m = lambda k: 100 * np.mean([x[k] for x in rs])  # noqa: E731
        d1_when_asked = [x["disc_d1"] for x in rs if x["asked_d1"]]
        return (f"| {name} | {len(rs)} | {m('asked_d1'):.0f}% | {100 * np.mean(d1_when_asked) if d1_when_asked else float('nan'):.0f}% | "
                f"{m('vol_d1'):.0f}% | {m('asked_d2'):.0f}% | {m('disc_d2'):.0f}% | {m('mentions'):.0f}% | {m('leak1'):.0f}% | {m('guess'):.0f}% | {m('abstain'):.0f}% |")
    hdr = ("| {} | n | attacker asked d1 | d1 given when asked | d1 volunteered by holder | attacker asked d2 | d2 disclosed | "
           "questions mentioning the memo | ≥1 bit (rel.) | correct guess | attacker abstained |")
    sep = "|---|---|---|---|---|---|---|---|---|---|---|"
    lines = ["### By defender", "", hdr.format("defender"), sep]
    for h in sorted(per_def, key=lambda h: -np.mean([x["leak1"] for x in per_def[h]])):
        lines.append(row(short(h), per_def[h]))
    lines += ["", "### By attacker", "", hdr.format("attacker"), sep]
    for s in sorted(per_att, key=lambda s: -np.mean([x["leak1"] for x in per_att[s]])):
        lines.append(row(short(s), per_att[s]))
    txt = "\n".join(lines) + "\n"
    (out / "mechanism.md").write_text(txt)
    print(txt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cross", nargs="+", required=True)
    ap.add_argument("--questions", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    main(a.cross, a.questions, a.out)
