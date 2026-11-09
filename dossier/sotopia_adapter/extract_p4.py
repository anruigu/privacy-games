"""P3/P4: from the stored Sotopia EpisodeLog objects ONLY, reconstruct turns, fact IDs and leak curve;
re-score the transcript with the Stage-1 scorer and compare; draw the Sotopia-extracted leak-curve figure.

Run in the sotopia venv (it imports dossier.parse/infer, i.e. the Stage-1 scorer, directly).
"""
from __future__ import annotations

from . import backend  # noqa: F401

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from sotopia.database import EpisodeLog  # noqa: E402

from .. import infer, parse  # noqa: E402
from ..schema import World  # noqa: E402
from .from_sotopia import evaluator_record, stock_secret_score, transcript  # noqa: E402


def main(run_dir: Path, worlds_dir: Path) -> None:
    runs = [json.loads(l) for l in (run_dir / "episodes.jsonl").read_text().splitlines()]
    rows = []
    curves = []
    for r in runs:
        if not r.get("completed"):
            continue
        ep = EpisodeLog.get(pk=r["episode_pk"])          # stored object only
        tr = transcript(ep)
        rec = evaluator_record(ep)
        sec = stock_secret_score(ep)
        holder = "Sam Okafor"
        # Stage-1 scorer applied directly to the extracted transcript (predicates from the world file)
        world = World.load((worlds_dir / f"seed_{r['seed']:03d}.json").read_text())
        per_turn = []
        D: list[str] = []
        for t in tr:
            if t["speaker"] != holder or t["action"] != "speak":
                continue
            p = parse.parse_both(world, t["utterance"])
            new = [f for f in p["ids"] if f not in D]
            D.extend(new); per_turn.append(new)
        s1 = infer.summarize(world, per_turn)
        rows.append({"seed": r["seed"], "pk": ep.pk, "n_turns": len(ep.messages) - 1,
                     "holder_utts": sum(1 for t in tr if t["speaker"] == holder and t["action"] == "speak"),
                     "evaluator_final_leak": rec["final_leak"] if rec else None,
                     "stage1_final_leak": s1["final_leak"], "stage1_synergy_gap": s1["synergy_gap"],
                     "stage1_utility": s1["utility"], "stock_secret_holder": sec["agent_2"],
                     "match": rec is not None and abs(rec["final_leak"] - s1["final_leak"]) <= 0.01,
                     "per_turn_ids_in_log": rec["per_turn_new"] if rec else None,
                     "leak_curve_in_log": rec["leak_curve"] if rec else None,
                     "reasoning_excerpt": (ep.reasoning or "")[:600]})
        if rec:
            curves.append((r["seed"], rec["leak_curve"]))
    (run_dir / "p3_p4_check.json").write_text(json.dumps(rows, indent=1))
    n_match = sum(1 for x in rows if x["match"])
    print(f"P3: {n_match}/{len(rows)} episodes match Stage-1 scorer within 0.01 bits")
    for x in rows:
        print(f"seed={x['seed']:03d} turns={x['n_turns']} holder_utts={x['holder_utts']} eval={x['evaluator_final_leak']} "
              f"stage1={x['stage1_final_leak']:.3f} util={x['stage1_utility']:.2f} secret={x['stock_secret_holder']} match={x['match']}")
    # figure from stored-log data only
    fig, ax = plt.subplots(figsize=(7, 4.2), facecolor="#fcfcfb"); ax.set_facecolor("#fcfcfb")
    T = max((len(c) for _, c in curves), default=1)
    import numpy as np
    M = np.array([c + [c[-1]] * (T - len(c)) for _, c in curves]) if curves else np.zeros((1, 1))
    for s, c in curves:
        ax.plot(range(1, len(c) + 1), c, color="#2a78d6", alpha=0.25, lw=1)
    ax.plot(range(1, T + 1), M.mean(axis=0), color="#2a78d6", lw=2, marker="o", ms=4, label="mean (Sotopia-native, Opus 5.5 holder)")
    ax.set_xlabel("holder utterance #"); ax.set_ylabel("I(T; D_t) [bits]"); ax.set_ylim(-0.05, 3.05); ax.grid(alpha=0.25)
    ax.set_title("Sotopia-extracted leak curves (from stored EpisodeLog only)", fontsize=10); ax.legend(frameon=False, fontsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout(); fig.savefig(run_dir / "fig_sotopia_leak_curves.png", dpi=150)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=Path("runs/stage2"))
    ap.add_argument("--worlds", type=Path, default=Path("runs/worlds"))
    a = ap.parse_args()
    main(a.run, a.worlds)
