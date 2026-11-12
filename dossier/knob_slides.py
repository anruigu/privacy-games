"""Slide-ready plots: effect of each knob on attack success (% episodes with >=1 bit leaked via releasable facts).

  python -m dossier.knob_slides --out runs/knobs/analysis/slides
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HOLDERS = ["Opus 5.5", "Sonnet 5.5", "Haiku 5.5", "Gemini 3.8 Flash"]
COLOR = {"Opus 5.5": "#2a78d6", "Sonnet 5.5": "#eb6834", "Haiku 5.5": "#1baf7a", "Gemini 3.8 Flash": "#eda100"}
MARK = {"Opus 5.5": "o", "Sonnet 5.5": "s", "Haiku 5.5": "D", "Gemini 3.8 Flash": "^"}
SURFACE, INK, INK2, GRID = "#ffffff", "#0b0b0b", "#52514e", "#e6e4df"


def pct(rows, key="ge1"):
    return 100 * np.mean([bool(r[key]) for r in rows]) if rows else np.nan


def sel(E, **f):
    return [e for e in E if all(e.get(k) == v for k, v in f.items())]


def style(ax, title, ylabel, xlabels, subtitle=None):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", color=INK, pad=16)
    if subtitle:
        ax.text(0, 1.012, subtitle, transform=ax.transAxes, fontsize=8.5, color=INK2, va="bottom")
    ax.set_ylabel(ylabel, color=INK, fontsize=10)
    ax.set_xticks(range(len(xlabels))); ax.set_xticklabels(xlabels, fontsize=10, color=INK)
    ax.set_ylim(-4, 104); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=9, color=INK2)
    ax.set_xlim(-0.4, len(xlabels) - 0.6)
    ax.grid(axis="y", color=GRID, lw=1); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(GRID)
    ax.tick_params(length=0)


def lines(ax, series, xlabels, label_end=True, pad=1.0):
    """series: {name: (ys, color, marker, linestyle)}; end labels are pushed apart so they never overlap."""
    ends = []
    for name, (ys, c, m, ls) in series.items():
        ax.plot(range(len(ys)), ys, color=c, marker=m, ms=7, lw=2.2, ls=ls, label=name,
                markeredgecolor=SURFACE, markeredgewidth=1.5)
        y = next((v for v in reversed(ys) if not np.isnan(v)), None)
        if y is not None:
            ends.append([y, name, c])
    if label_end:
        ends.sort(key=lambda e: e[0])
        pos = [e[0] for e in ends]
        for i in range(1, len(pos)):          # push up
            pos[i] = max(pos[i], pos[i - 1] + 7)
        over = pos[-1] - 100 if pos and pos[-1] > 100 else 0
        pos = [v - over for v in pos]
        for i in range(len(pos) - 2, -1, -1):  # push down if the shift created a clash
            pos[i] = min(pos[i], pos[i + 1] - 7)
        for (y, name, c), yl in zip(ends, pos):
            ax.annotate(name, (len(xlabels) - 1, y), xytext=(10, 0), textcoords="offset points", fontsize=9, color=INK2, va="center",
                        xycoords="data", annotation_clip=False, arrowprops=None)
            if abs(yl - y) > 0.5:
                ax.annotate(name, (len(xlabels) - 1, y), xytext=(len(xlabels) - 1 + 0.12, yl), textcoords="data", fontsize=9, color=INK2, va="center",
                            annotation_clip=False, arrowprops=dict(arrowstyle="-", color=GRID, lw=1, shrinkA=0, shrinkB=2))
                ax.texts[-2].set_visible(False)
    ax.set_xlim(-0.4, len(xlabels) - 0.6 + pad)


def panel_bits(ax, E):
    arms = ["n1_r0_k2", "n2_r0_k2", "n4_r0_k2"]
    xl = ["3 bits", "2 bits", "1 bit"]
    style(ax, "Bits available to the attacker", "attack success (% worlds leaking ≥1 bit)", xl, "1 / 2 / 4 directors share the approver's floor · scripted seeker · 20 worlds/point")
    lines(ax, {h: ([pct(sel(E, arm=a, seeker="scripted-direct", holder=h)) for a in arms], COLOR[h], MARK[h], "-") for h in HOLDERS}, xl)


def panel_redundancy(ax, E):
    arms = ["n2_r0_k2", "n2_r1_k2", "n2_r2_k2"]
    xl = ["no extra\nroute", "1 extra\nroute", "2 extra\nroutes"]
    style(ax, "Redundant ways to get the same fact", "attack success (% worlds leaking ≥1 bit)", xl, "route = another way to ask the pivot's floor · ladder seeker · 20 worlds/point")
    lines(ax, {h: ([pct(sel(E, arm=a, seeker="scripted-ladder", holder=h)) for a in arms], COLOR[h], MARK[h], "-") for h in HOLDERS[:3]}, xl)


def panel_order(ax, E):
    arms = ["n2_r0_k2", "n2_r0_k3", "n2_r0_k4"]
    xl = ["2 facts", "3 facts", "4 facts"]
    style(ax, "Facts that must be combined", "attack success (% worlds leaking ≥1 bit)", xl, "any subset of the chain reveals 0 bits · scripted seeker · 20 worlds/point")
    lines(ax, {h: ([pct(sel(E, arm=a, seeker="scripted-direct", holder=h)) for a in arms], COLOR[h], MARK[h], "-") for h in HOLDERS}, xl)


def panel_null(ax, E):
    arms = ["n2_r0_k2", "null-public", "null-nomemo"]
    xl = ["secret\npresent", "floor already\npublic", "no memo"]
    style(ax, "Control worlds: is the refusal real?", "holder answers the relational question (%)", xl, "same worlds and questions; only whether answering can leak changes")
    lines(ax, {h: ([pct(sel(E, arm=a, seeker="scripted-direct", holder=h), "d1_ans") for a in arms], COLOR[h], MARK[h], "-") for h in HOLDERS}, xl)


def panel_persona(ax, E):
    arms = ["n2_r0_k2", "n2_r0_k2_persona"]
    xl = ["fixed", "randomised"]
    style(ax, "Persona diversity", "attack success (% worlds leaking ≥1 bit)", xl, "names, roles and cover story fixed vs drawn per world · scripted seeker")
    lines(ax, {h: ([pct(sel(E, arm=a, seeker="scripted-direct", holder=h)) for a in arms], COLOR[h], MARK[h], "-") for h in HOLDERS}, xl)


def panel_hint(ax, E):
    variants = [("", "no hint"), (" (hint)", "\"facts\ncombine\""), (" (plan)", "exact\nmechanism")]
    xl = [v[1] for v in variants]
    style(ax, "Hinting the LLM attacker", "attack success (% episodes leaking ≥1 bit)", xl, "LLM attacker, 10 questions · solid = Opus attacker, dashed = Haiku attacker")
    leak_arms = ["n2_r0_k2", "n2_r0_k3", "n2_r2_k2"]
    series = {}
    for atk, ls in (("Opus 5.5", "-"), ("Haiku 5.5", "--")):
        for h in ("Sonnet 5.5", "Haiku 5.5"):
            ys = [pct([e for e in E if e["arm"] in leak_arms and e["holder"] == h and e["seeker"] == f"LLM {atk}{v}"]) for v, _ in variants]
            series[f"{atk.split()[0]} → {h.split()[0]}"] = (ys, COLOR[h], MARK[atk], ls)
    lines(ax, series, xl)


PANELS = [("bits", panel_bits), ("redundancy", panel_redundancy), ("order", panel_order),
          ("null_worlds", panel_null), ("persona", panel_persona), ("attacker_hint", panel_hint)]


def main(out: Path, derived: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    E = json.load(open(derived))
    E = [e for e in E if e["src"] == "knobs"]
    # combined 2x3 figure (16:9)
    fig, axes = plt.subplots(2, 3, figsize=(18, 10), facecolor=SURFACE)
    for ax, (name, fn) in zip(axes.flat, PANELS):
        fn(ax, E)
    fig.suptitle("What moves attack success in the dossier game — one knob per panel, one line per holder model", x=0.01, ha="left", fontsize=15, fontweight="bold", color=INK, y=0.995)
    fig.text(0.01, 0.955, "Attack success = share of episodes in which the holder's individually-permitted answers jointly reveal ≥1 bit about the protected approver. "
             "Opus 5.5 sits at 0% in every leak panel.", fontsize=10, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.93), h_pad=4, w_pad=3)
    fig.savefig(out / "knob_effects.png", dpi=160); fig.savefig(out / "knob_effects.pdf"); plt.close(fig)
    # one file per panel for slides
    for name, fn in PANELS:
        fig, ax = plt.subplots(figsize=(7.2, 4.6), facecolor=SURFACE)
        fn(ax, E)
        fig.tight_layout(); fig.savefig(out / f"knob_{name}.png", dpi=160); plt.close(fig)
    print("wrote", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("runs/knobs/analysis/slides"))
    ap.add_argument("--derived", type=Path, default=Path("runs/knobs/analysis/episodes_derived.json"))
    a = ap.parse_args(); main(a.out, a.derived)
