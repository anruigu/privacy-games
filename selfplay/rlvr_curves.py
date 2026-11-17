"""Training curves of the RLVR / self-play arms (metrics.jsonl) with the held-out Sonnet-parser points overlaid,
one figure per warm-start lineage. Thin lines = individual seeds, thick = mean over seeds per condition.

  python -m selfplay.rlvr_curves --lineage sft     --out runs/selfplay_eval/figs/rlvr_curves_sft.png
  python -m selfplay.rlvr_curves --lineage distill --out runs/selfplay_eval/figs/rlvr_curves_distill.png
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

LS = {0: "-", 1: "--", 2: ":"}
# run dir, condition, seed, held-out tag prefix
LINEAGES = {
    "sft": {"start": "sft_round2", "start_label": "warm start A: sft_round2 (oracle-guided self-distillation)",
            "conds": {"self-play (trained attacker, 25 % of episodes, updated every 2nd iteration)": "#8e6cc7",
                      "RLVR: fixed attackers only (scripted + base-prompted LLM)": "#d1495b"},
            "short": {"self-play (trained attacker, 25 % of episodes, updated every 2nd iteration)": "self-play",
                      "RLVR: fixed attackers only (scripted + base-prompted LLM)": "RLVR (fixed attackers)"},
            "runs": [("exp2", "self-play (trained attacker, 25 % of episodes, updated every 2nd iteration)", 0, "exp2_"),
                     ("sp_s1", "self-play (trained attacker, 25 % of episodes, updated every 2nd iteration)", 1, "sp_s1_"),
                     ("sp_s2", "self-play (trained attacker, 25 % of episodes, updated every 2nd iteration)", 2, "sp_s2_"),
                     ("rlvr", "RLVR: fixed attackers only (scripted + base-prompted LLM)", 0, "rlvr_"),
                     ("rlvr_s1", "RLVR: fixed attackers only (scripted + base-prompted LLM)", 1, "rlvr_s1_"),
                     ("rlvr_s2", "RLVR: fixed attackers only (scripted + base-prompted LLM)", 2, "rlvr_s2_")],
            "ylim": (0, 0.9), "note_x": 3},
    "distill": {"start": "distill_opus_nll", "start_label": "warm start B: distill_opus_nll (Opus 5.5 distillation, plain NLL)",
                "conds": {"RLVR: fixed attackers only": "#1f5fbf",
                          "self-play, 25 % trained attacker, every 2nd iteration": "#2a9d8f",
                          "self-play, 75 % trained attacker, every iteration": "#e9a23b"},
                "short": {"RLVR: fixed attackers only": "RLVR", "self-play, 25 % trained attacker, every 2nd iteration": "self-play 25 %",
                          "self-play, 75 % trained attacker, every iteration": "self-play 75 %"},
                "runs": [("drlvr", "RLVR: fixed attackers only", 0, "drlvr_"), ("drlvr_s1", "RLVR: fixed attackers only", 1, "drlvr_s1_"),
                         ("dsp", "self-play, 25 % trained attacker, every 2nd iteration", 0, "dsp_"), ("dsp_s1", "self-play, 25 % trained attacker, every 2nd iteration", 1, "dsp_s1_"),
                         ("dsp2", "self-play, 75 % trained attacker, every iteration", 0, "dsp2_")],
                "ylim": (0, 0.5), "note_x": 3},
}


def load(run):
    p = Path("selfplay/run") / run / "metrics.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def heldout(tag):
    p = Path("runs/selfplay_eval") / tag / "summary.json"
    return json.load(open(p)) if p.exists() else None


def main(out: Path, lineage: str):
    L = LINEAGES[lineage]
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.9))
    a_probe, a_held, a_util, a_kl = axes
    series = defaultdict(lambda: defaultdict(dict))   # cond -> panel -> {x: [vals over seeds]}
    start_leak = heldout(L["start"])["direct"]["leak1"]
    for run, cond, seed, pre in L["runs"]:
        rows = load(run)
        if not rows:
            continue
        col, ls = L["conds"][cond], LS[seed]
        it = [r["it"] + 1 for r in rows]
        kw = dict(lw=1.3, alpha=0.75, color=col, ls=ls, marker="o", ms=3)
        a_probe.plot(it, [r["probe"]["leak1"] for r in rows], **kw)
        a_util.plot(it, [r["train"]["utility"] for r in rows], **kw)
        a_kl.plot(it, [r["train_def"]["kl"] for r in rows], **kw)
        xs, ys = [0], [start_leak]
        for r in rows:
            s = heldout(f"{pre}it{r['it']:02d}")
            if s:
                xs.append(r["it"] + 1); ys.append(s["direct"]["leak1"])
        a_held.plot(xs, ys, lw=1.3, alpha=0.75, color=col, ls=ls, marker="s", ms=3.5, label=f"{L['short'][cond]}, seed {seed}")
        if cond.startswith("self-play") and "every 2nd" in cond:   # attacker adapter = base until the end of iteration 2
            hx = [x for x in xs if 1 <= x <= 2]; hy = [ys[xs.index(x)] for x in hx]
            a_held.plot(hx, hy, "s", ms=6.5, mfc="white", mec=col, mew=1.4, alpha=0.9)
        for panel, vals in (("probe", [r["probe"]["leak1"] for r in rows]), ("util", [r["train"]["utility"] for r in rows]),
                            ("kl", [r["train_def"]["kl"] for r in rows])):
            for x, v in zip(it, vals):
                series[cond][panel].setdefault(x, []).append(v)
        for x, v in zip(xs, ys):
            series[cond]["held"].setdefault(x, []).append(v)
    # condition means (thick)
    for cond, col in L["conds"].items():
        for panel, ax in (("probe", a_probe), ("held", a_held), ("util", a_util), ("kl", a_kl)):
            d = series[cond][panel]
            if not d:
                continue
            n = max(len(v) for v in d.values())
            xs = sorted(x for x in d if len(d[x]) == n)
            ax.plot(xs, [float(np.mean(d[x])) for x in xs], lw=3.2, color=col, alpha=0.95, solid_capstyle="round", marker="o" if panel == "held" else None, ms=5,
                    label=f"{cond} — mean of {n} seed{'s' if n > 1 else ''}" if panel == "held" else None)
    a_held.axhline(start_leak, color="#6c757d", lw=0.8, ls="-.", alpha=0.7)
    a_held.text(a_held.get_xlim()[1] if False else 4.2, start_leak + 0.012, "warm start", fontsize=7, color="#6c757d", ha="left")
    if lineage == "sft":
        a_held.text(0.1, 0.86, "hollow = iterations before the trained attacker exists (self-play runs);\nthick = mean over seeds at iterations evaluated for every seed", fontsize=6.5, color="#8e6cc7", va="top")
    a_probe.set_title("training probe: ≥1 bit leaked\n(30 held-out worlds, local parser)", fontsize=9)
    a_held.set_title("held-out eval: ≥1 bit leaked\n(50 worlds, scripted-direct, Sonnet 5.5 parsers)", fontsize=9)
    a_util.set_title("training utility\n(asked cover facts answered, mixed attackers)", fontsize=9)
    a_kl.set_title("KL of the update to the base model", fontsize=9)
    for ax in axes:
        ax.set_xlabel("RL iteration (0 = warm start)", fontsize=8); ax.tick_params(labelsize=8); ax.grid(alpha=0.25); ax.spines[["top", "right"]].set_visible(False)
    a_probe.set_ylim(*L["ylim"]); a_held.set_ylim(*L["ylim"])
    h, l = a_held.get_legend_handles_labels()
    means = [(hh, ll) for hh, ll in zip(h, l) if "mean" in ll]; seeds = [(hh, ll) for hh, ll in zip(h, l) if "mean" not in ll]
    fig.legend([x for x, _ in means] + [x for x, _ in seeds], [y for _, y in means] + [y for _, y in seeds], fontsize=7, frameon=False,
               loc="lower center", ncol=3 if lineage == "sft" else 4, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(L["start_label"], fontsize=10, x=0.01, ha="left", y=0.995)
    fig.tight_layout(rect=(0, 0.13, 1, 0.96)); out.parent.mkdir(parents=True, exist_ok=True); fig.savefig(out, dpi=200); print("saved", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--lineage", default="sft", choices=list(LINEAGES)); ap.add_argument("--out", default="")
    a = ap.parse_args()
    main(Path(a.out or f"runs/selfplay_eval/figs/rlvr_curves_{a.lineage}.png"), a.lineage)
