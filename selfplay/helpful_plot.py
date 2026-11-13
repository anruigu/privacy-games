"""Discrimination plot for HELPFUL_RL.md: does a checkpoint answer the harmless question (null worlds) while
withholding the same question when the secret is live?  x = d1 answered in null worlds (mean of floor-public and
no-memo), y = d1 answered with the secret present (n2_r0_k2), scripted-direct, Sonnet parsers, seeds 200-219.
A context-blind policy sits on the diagonal; the ideal is the bottom-right corner.

  python -m selfplay.helpful_plot            -> runs/selfplay_eval/figs/helpful_discrimination.{png,pdf}
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .helpful import OUT, NULL_ARMS, null_metrics, REF_HOLDERS

ARMS = {"exp2": ("control: exp2 recipe", "#5b6b7a"), "h1": ("h1 over-refusal penalty", "#1f77b4"),
        "h2": ("h2 null-heavy pool", "#ff7f0e"), "h3": ("h3 safe-answer anchor", "#2ca02c"),
        "h4": ("h4 all three", "#9467bd"), "h5": ("h5 all three + balanced warm start", "#d62728")}
STARTS = {"base": "base Qwen3-8B", "sft_round2": "warm start (sft_round2)", "sft_h": "balanced warm start (sft_h)"}


def point(tag: str):
    n = null_metrics(OUT / tag / "null")
    if not all(a in n for a in NULL_ARMS):
        return None
    x = 0.5 * (n["null-public"]["d1_answered"] + n["null-nomemo"]["d1_answered"])
    return x, n["n2_r0_k2"]["d1_answered"]


def ref_point(name: str):
    from .helpful import reference_row
    r = reference_row(name, REF_HOLDERS[name], {}, False)
    n = r.get("null", {})
    if not all(a in n for a in NULL_ARMS):
        return None
    return 0.5 * (n["null-public"]["d1_answered"] + n["null-nomemo"]["d1_answered"]), n["n2_r0_k2"]["d1_answered"]


def main():
    fig, ax = plt.subplots(figsize=(8.5, 7))
    ax.plot([0, 1], [0, 1], ls=":", color="#999", lw=1)
    ax.text(0.99, 0.10, "ideal corner: answers when harmless,\nwithholds when it would leak", fontsize=9, color="#444", ha="right", va="bottom")
    ax.text(0.22, 0.27, "context-blind: answers both equally", fontsize=9, color="#777", rotation=40, ha="center", va="bottom")
    pts = {}
    for s, lab in STARTS.items():
        p = point(s)
        if p:
            pts[s] = p
            ax.scatter(*p, s=90, marker="s", color="#333", zorder=5)
            ax.annotate(lab, p, xytext=(6, -12 if s == "base" else 6), textcoords="offset points", fontsize=9)
    for arm, (lab, col) in ARMS.items():
        its = ["it00", "it01", "it02", "it03"] if arm == "exp2" else ["it01", "it03"]
        seq = [(it, point(f"{arm}_{it}")) for it in its]
        seq = [(it, p) for it, p in seq if p]
        if not seq:
            continue
        start = pts.get("sft_h" if arm == "h5" else "sft_round2")
        xs = ([start[0]] if start else []) + [p[0] for _, p in seq]
        ys = ([start[1]] if start else []) + [p[1] for _, p in seq]
        ax.plot(xs, ys, color=col, lw=1.5, alpha=0.8, zorder=3)
        ax.scatter([p[0] for _, p in seq], [p[1] for _, p in seq], color=col, s=55, zorder=4, label=lab)
        for j, (it, p) in enumerate(seq):
            dx, dy = {"h1": (6, 6), "h2": (-6, 6), "h3": (-6, -12), "h4": (6, -12), "h5": (6, 6), "exp2": (6, 4)}[arm]
            if arm in ("h1", "h2", "h3", "h4") and j == 1:
                dy = -dy if dy > 0 else dy - 8
            ax.annotate(f"{arm} {it}", p, xytext=(dx, dy), textcoords="offset points", fontsize=7.5, color=col,
                        ha="left" if dx > 0 else "right")
    for name in REF_HOLDERS:
        p = ref_point(name)
        if p:
            ax.scatter(*p, marker="^", s=70, color="#8c564b", zorder=5)
            ax.annotate(name, p, xytext=(6, -3), textcoords="offset points",
                        fontsize=8, color="#8c564b")
    ax.set_xlim(-0.02, 1.05); ax.set_ylim(-0.02, 1.05)
    ax.set_xlabel("Answers the relational question when it is harmless\n(no secret: approver's floor public or no memo; share of worlds)")
    ax.set_ylabel("Answers the same question when it completes the leak\n(secret present; share of worlds)")
    ax.set_title("Helpfulness vs privacy per checkpoint (scripted-direct attacker, held-out worlds)", fontsize=11)
    ax.legend(loc="upper left", fontsize=8.5, frameon=False, bbox_to_anchor=(0.0, 0.92))
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(alpha=0.25)
    out = OUT / "figs"; out.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(out / "helpful_discrimination.png", dpi=170); fig.savefig(out / "helpful_discrimination.pdf")
    print("wrote", out / "helpful_discrimination.png")
    for k, p in sorted({**pts, **{f"{a}_{i}": point(f"{a}_{i}") for a in ARMS for i in ("it00", "it01", "it02", "it03")}}.items()):
        if p:
            print(f"{k:12s} harmless {p[0]:.2f}  leaking {p[1]:.2f}  gap {p[0]-p[1]:+.2f}")


if __name__ == "__main__":
    main()
