"""Training curves of the RLVR / self-play arms (metrics.jsonl) with the held-out Sonnet-parser points overlaid.
python -m selfplay.rlvr_curves --out runs/selfplay_eval/figs/rlvr_curves.png"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ARMS = [  # run dir, label, colour, linestyle, held-out tag prefix, start tag
    ("exp2", "sft_round2 → exp2: fixed attackers at it 1–2 (hollow), trained attacker from it 3", "#8e6cc7", "-", "exp2_", "sft_round2"),
    ("rlvr", "sft_round2 → RLVR (fixed attackers)", "#d1495b", "-", "rlvr_", "sft_round2"),
    ("rlvr_s1", "sft_round2 → RLVR, seed 1", "#d1495b", "--", "rlvr_s1_", "sft_round2"),
    ("rlvr_s2", "sft_round2 → RLVR, seed 2", "#d1495b", ":", "rlvr_s2_", "sft_round2"),
    ("sp_s1", "sft_round2 → self-play, seed 1 (trained attacker from it 3)", "#8e6cc7", "--", "sp_s1_", "sft_round2"),
    ("sp_s2", "sft_round2 → self-play, seed 2", "#8e6cc7", ":", "sp_s2_", "sft_round2"),
    ("drlvr", "distill → RLVR", "#1f5fbf", "-", "drlvr_", "distill_opus_nll"),
    ("drlvr_s1", "distill → RLVR, seed 1", "#1f5fbf", "--", "drlvr_s1_", "distill_opus_nll"),
    ("dsp", "distill → self-play (25 % attacker)", "#2a9d8f", "-", "dsp_", "distill_opus_nll"),
    ("dsp_s1", "distill → self-play, seed 1", "#2a9d8f", "--", "dsp_s1_", "distill_opus_nll"),
    ("dsp2", "distill → self-play, 75 % attacker, every iter", "#e9a23b", "-", "dsp2_", "distill_opus_nll"),
]


def load(run):
    p = Path("selfplay/run") / run / "metrics.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def heldout(tag):
    p = Path("runs/selfplay_eval") / tag / "summary.json"
    return json.load(open(p)) if p.exists() else None


def main(out: Path):
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.9))
    a_probe, a_held, a_util, a_kl = axes
    for run, lab, col, ls, pre, start in ARMS:
        rows = load(run)
        if not rows:
            continue
        it = [r["it"] + 1 for r in rows]
        a_probe.plot([0] + it, [None] + [r["probe"]["leak1"] for r in rows], ls, marker="o", ms=3.5, lw=1.8, color=col, label=lab)
        a_util.plot(it, [r["train"]["utility"] for r in rows], ls, marker="o", ms=3.5, lw=1.8, color=col)
        a_kl.plot(it, [r["train_def"]["kl"] for r in rows], ls, marker="o", ms=3.5, lw=1.8, color=col)
        # held-out Sonnet-parser points (start + evaluated checkpoints)
        xs, ys = [0], [heldout(start)["direct"]["leak1"]]
        for r in rows:
            s = heldout(f"{pre}it{r['it']:02d}")
            if s:
                xs.append(r["it"] + 1); ys.append(s["direct"]["leak1"])
        a_held.plot(xs, ys, ls, marker="s", ms=4, lw=1.8, color=col)
        if run == "exp2":   # the attacker adapter was the base model until the end of iteration 2
            hollow = [(x, y) for x, y in zip(xs, ys) if 1 <= x <= 2]
            a_held.plot([x for x, _ in hollow], [y for _, y in hollow], "s", ms=7, mfc="white", mec=col, mew=1.8)
            a_probe.plot([1, 2], [rows[0]["probe"]["leak1"], rows[1]["probe"]["leak1"]], "o", ms=7, mfc="white", mec=col, mew=1.8)
            a_held.annotate("trained attacker\nenters here", (3, ys[xs.index(3)] if 3 in xs else 0.1), textcoords="offset points", xytext=(22, 30), fontsize=7, color=col,
                            arrowprops=dict(arrowstyle="->", color=col, lw=0.8))
    a_probe.set_title("training probe: ≥1 bit leaked\n(30 held-out worlds, scripted-direct, local parser)", fontsize=9)
    a_held.set_title("held-out eval: ≥1 bit leaked\n(50 worlds, scripted-direct, Sonnet 5.5 parsers)", fontsize=9)
    a_util.set_title("training utility\n(asked cover facts answered, mixed attackers)", fontsize=9)
    a_kl.set_title("KL of the update to the base model\n(> 1 = drift in the sft_round2 lineage)", fontsize=9)
    for ax in axes:
        ax.set_xlabel("RL iteration (0 = warm start)", fontsize=8); ax.tick_params(labelsize=8); ax.grid(alpha=0.25); ax.spines[["top", "right"]].set_visible(False)
    a_probe.set_ylim(0, 0.9); a_held.set_ylim(0, 0.75); a_util.set_ylim(0.3, 0.85)
    h, l = a_probe.get_legend_handles_labels()
    fig.legend(h, l, fontsize=7.5, frameon=False, loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.01))
    fig.tight_layout(rect=(0, 0.1, 1, 1)); out.parent.mkdir(parents=True, exist_ok=True); fig.savefig(out, dpi=200); print("saved", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="runs/selfplay_eval/figs/rlvr_curves.png")
    main(Path(ap.parse_args().out))
