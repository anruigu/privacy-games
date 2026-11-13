"""Transfer eval: base vs a checkpoint on the knob-study arms (structurally different worlds) with the Sonnet parsers.

  LOCAL_LLM_URLS=... python -m selfplay.transfer_eval --holders vanilla@local/base,vanilla@local/def_it01 --out runs/selfplay_eval/transfer
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from dossier.run import run_grid

ARMS = ["n2_r0_k2", "n2_r0_k2_persona", "n1_r0_k2", "n4_r0_k2", "n2_r1_k2", "n2_r2_k2", "n2_r0_k3", "n2_r0_k4", "null-public", "null-nomemo"]
ARM_DESC = {"n2_r0_k2": "2 directors on the approver's floor (2 bits), default persona", "n2_r0_k2_persona": "same worlds, random seeker/holder personas and cover task",
            "n1_r0_k2": "approver alone on the floor (3 bits)", "n4_r0_k2": "4 directors on the floor (1 bit)", "n2_r1_k2": "one redundant route to X's floor",
            "n2_r2_k2": "two redundant routes", "n2_r0_k3": "synergy chain of 3 facts", "n2_r0_k4": "synergy chain of 4 facts",
            "null-public": "approver's floor is public (key pair harmless)", "null-nomemo": "no memo, no secret at all"}


def table(eps):
    s = [e["summary"] for e in eps]
    if not s:
        return {}
    return {"n": len(eps), "leak1": float(np.mean([x["final_leak"] >= 1 - 1e-9 for x in s])), "bits": float(np.mean([x["final_leak"] for x in s])),
            "utility": float(np.mean([x["utility"] for x in s])), "violations": float(np.mean([x["violations"] for x in s])),
            "d1": float(np.mean([list(x["key_disclosed"].values())[0] for x in s])), "dk": float(np.mean([list(x["key_disclosed"].values())[-1] for x in s])),
            "chain_complete": float(np.mean([all(x["key_disclosed"].values()) for x in s]))}


def main(a):
    out = Path(a.out); holders = a.holders.split(","); seekers = a.seekers.split(",")
    res = {}
    for arm in ARMS:
        wd = Path("runs/worlds_knobs") / arm
        seeds = sorted(int(p.stem.split("_")[1]) for p in wd.glob("seed_*.json"))
        run_grid(wd, out / arm, holders, seekers, seeds, a.workers)
        eps = [json.loads(l) for l in (out / arm / "episodes.jsonl").read_text().splitlines() if l.strip()]
        for h in holders:
            for k in seekers:
                res[f"{arm}|{h}|{k}"] = table([e for e in eps if e["holder"] == h and e["seeker"] == k])
    (out / "summary.json").write_text(json.dumps(res, indent=1))
    short = {h: h.split("/")[-1] for h in holders}
    lines = ["| arm | worlds | " + " | ".join(f"{short[h]} {k.replace('scripted-', '')}: ≥1 bit / bits / util / viol" for k in seekers for h in holders) + " |",
             "|---|---|" + "---|" * (len(seekers) * len(holders))]
    for arm in ARMS:
        cells = []
        for k in seekers:
            for h in holders:
                t = res.get(f"{arm}|{h}|{k}", {})
                cells.append(f"{t.get('leak1', float('nan')):.2f} / {t.get('bits', float('nan')):.2f} / {t.get('utility', float('nan')):.2f} / {t.get('violations', float('nan')):.2f}" if t else "–")
        lines.append(f"| {arm} ({ARM_DESC[arm]}) | {res.get(f'{arm}|{holders[0]}|{seekers[0]}', {}).get('n', 0)} | " + " | ".join(cells) + " |")
    (out / "transfer.md").write_text("\n".join(lines) + "\n"); print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--holders", default="vanilla@local/base,vanilla@local/def_it01")
    ap.add_argument("--seekers", default="scripted-direct,scripted-ladder")
    ap.add_argument("--out", default="runs/selfplay_eval/transfer"); ap.add_argument("--workers", type=int, default=12)
    main(ap.parse_args())
