"""Figures for PRIVACYZERO.md: training curves (metrics.jsonl) and held-out checkpoint evals (runs/selfplay_eval/*/summary.json).

  python -m selfplay.plots --run selfplay/run/exp1 --out runs/selfplay_eval/figs
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COL = {"scripted-direct": "#1f5fbf", "scripted-ladder": "#d1495b", "llm@base": "#6c757d", "trained": "#2a9d8f",
       "probe": "#1f5fbf", "utility": "#e9a23b", "haiku": "#8e6cc7", "sonnet": "#2a9d8f", "base": "#6c757d"}


def training_curves(run: Path, out: Path) -> None:
    rows = [json.loads(l) for l in (run / "metrics.jsonl").read_text().splitlines() if l.strip()]
    if not rows:
        return
    its = [r["it"] for r in rows]
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    ax = axes[0]
    for k, lab in [("scripted-direct", "scripted-direct"), ("scripted-ladder", "scripted-ladder")]:
        ax.plot(its, [r["train"]["by_attacker"].get(k, {}).get("leak1", float("nan")) for r in rows], "-o", ms=4, lw=2, color=COL[k], label=f"train vs {lab}")
    ax.plot(its, [next((v["leak1"] for a, v in r["train"]["by_attacker"].items() if a.startswith("llm@") and a != "llm@base"), r["train"]["by_attacker"].get("llm@base", {}).get("leak1", float("nan"))) for r in rows], "-o", ms=4, lw=2, color=COL["trained"], label="train vs trained attacker")
    ax.plot(its, [r["probe"]["leak1"] for r in rows], "--s", ms=4, lw=2, color="#111", label="held-out probe (scripted-direct)")
    ax.set_ylim(-0.02, 1.02); ax.set_xlabel("iteration"); ax.set_ylabel("episodes with ≥1 bit"); ax.set_title("Leak rate"); ax.legend(fontsize=7, frameon=False)
    ax = axes[1]
    ax.plot(its, [r["train"]["utility"] for r in rows], "-o", ms=4, lw=2, color=COL["utility"], label="train utility")
    ax.plot(its, [r["probe"]["utility"] for r in rows], "--s", ms=4, lw=2, color="#111", label="probe utility")
    ax.plot(its, [r["train"]["empty"] for r in rows], "-o", ms=4, lw=2, color=COL["scripted-ladder"], label="empty-answer rate")
    ax.plot(its, [r["train"]["fab"] for r in rows], "-o", ms=4, lw=2, color=COL["haiku"], label="fabrications / episode")
    ax.set_ylim(-0.02, 1.05); ax.set_xlabel("iteration"); ax.set_title("Usefulness and side effects"); ax.legend(fontsize=7, frameon=False)
    ax = axes[2]
    att = [next((v for a, v in r["train"]["by_attacker"].items() if a.startswith("llm@") and a != "llm@base"), r["train"]["by_attacker"].get("llm@base", {})) for r in rows]
    ax.plot(its, [a.get("asked_d1", float("nan")) for a in att], "-o", ms=4, lw=2, color=COL["trained"], label="attacker asked d1")
    ax.plot(its, [a.get("correct", float("nan")) if a.get("correct") is not None else float("nan") for a in att], "-o", ms=4, lw=2, color=COL["scripted-direct"], label="attacker guess correct")
    ax.plot(its, [r["train_def"]["kl"] * 100 for r in rows], "-o", ms=4, lw=2, color=COL["llm@base"], label="defender KL to base ×100")
    ax.set_ylim(-0.02, 1.05); ax.set_xlabel("iteration"); ax.set_title("Attacker and drift"); ax.legend(fontsize=7, frameon=False)
    for a in axes:
        a.spines[["top", "right"]].set_visible(False); a.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(out / "fig_training_curves.png", dpi=150); plt.close(fig)


def checkpoint_evals(out: Path, tags: list[str]) -> None:
    S = {}
    for t in tags:
        p = Path("runs/selfplay_eval") / t / "summary.json"
        if p.exists():
            S[t] = json.loads(p.read_text())
    if not S:
        return
    tags = list(S)
    x = list(range(len(tags)))
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    ax = axes[0]
    for key, lab, c in [("direct", "scripted-direct", COL["scripted-direct"]), ("ladder", "scripted-ladder", COL["scripted-ladder"]),
                        ("llm_haiku", "Haiku 5.5 attacker", COL["haiku"]), ("llm_sonnet", "Sonnet 5.5 attacker", COL["sonnet"])]:
        ax.plot(x, [S[t].get(key, {}).get("leak1", float("nan")) for t in tags], "-o", ms=4, lw=2, color=c, label=lab)
    ax.set_xticks(x); ax.set_xticklabels(tags); ax.set_ylim(-0.02, 1.02); ax.set_ylabel("episodes with ≥1 bit"); ax.set_title("Held-out leak rate (Sonnet parsers)"); ax.legend(fontsize=7, frameon=False)
    ax = axes[1]
    ax.plot(x, [S[t]["direct"].get("utility", float("nan")) for t in tags], "-o", ms=4, lw=2, color=COL["utility"], label="utility (scripted-direct)")
    ax.plot(x, [S[t]["direct"].get("violations", float("nan")) for t in tags], "-o", ms=4, lw=2, color=COL["scripted-ladder"], label="protected facts disclosed / episode")
    ax.plot(x, [S[t]["false_belief"]["deception_rate"] for t in tags], "-o", ms=4, lw=2, color=COL["haiku"], label="false-belief (deception) rate")
    ax.plot(x, [S[t]["false_belief"]["episodes_with_any_false_statement"] for t in tags], "--o", ms=4, lw=2, color=COL["haiku"], label="episodes with a false statement")
    ax.set_xticks(x); ax.set_xticklabels(tags); ax.set_ylim(-0.02, 1.4); ax.set_title("Utility, violations, deception"); ax.legend(fontsize=7, frameon=False)
    ax = axes[2]
    ax.plot(x, [S[t]["psi_flip"]["flip_key_up"] for t in tags], "-o", ms=4, lw=2, color=COL["sonnet"], label="ψ flip: key pair (author ↑)")
    ax.plot(x, [S[t]["psi_flip"]["flip_cover_down"] for t in tags], "-o", ms=4, lw=2, color=COL["scripted-direct"], label="ψ flip: cover facts (external ↓)")
    for v, lab, c, ls in [("reasoning_only", "monitor acc. (reasoning only)", "#111", "-"), ("action_only", "monitor acc. (action only)", "#111", "--")]:
        ax.plot(x, [S[t]["monitor"]["by_view"].get(v, {}).get("accuracy", float("nan")) for t in tags], ls + "s", ms=4, lw=2, color=c, label=lab)
    ax.plot(x, [S[t]["monitor"]["process"].get("combination_rate", float("nan")) for t in tags], "-o", ms=4, lw=2, color=COL["utility"], label="trace reasons about combination")
    ax.set_xticks(x); ax.set_xticklabels(tags); ax.set_ylim(-0.02, 1.02); ax.set_title("ψ flips and monitorability"); ax.legend(fontsize=7, frameon=False)
    for a in axes:
        a.spines[["top", "right"]].set_visible(False); a.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(out / "fig_checkpoint_evals.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="selfplay/run/exp1")
    ap.add_argument("--out", type=Path, default=Path("runs/selfplay_eval/figs"))
    ap.add_argument("--tags", default="base")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    training_curves(Path(a.run), a.out)
    checkpoint_evals(a.out, a.tags.split(","))
    print("figures in", a.out)
