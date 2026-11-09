"""Tables and figures from episodes.jsonl (+ optional judge.jsonl)."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# fixed categorical assignment (validated default palette, light mode, slots 1-8)
PALETTE = {
    "oracle": "#2a78d6", "vanilla": "#eb6834", "ci": "#1baf7a", "ledger": "#eda100",
    "vanilla@claude-sonnet-5-5": "#e87ba4", "vanilla@claude-haiku-5-5": "#008300",
    "vanilla|scripted-ladder": "#6250d6", "vanilla|llm-direct": "#e34948",
}
SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT2 = "#52514e"


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def cfg_name(r: dict) -> str:
    return r["holder"] if r["seeker"] == "scripted-direct" else f"{r['holder']}|{r['seeker']}"


def table1(eps: list[dict], judge: dict | None = None) -> tuple[str, dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in eps:
        groups[cfg_name(r)].append(r)
    order = sorted(groups, key=lambda k: list(PALETTE).index(k) if k in PALETTE else 99)
    hdr = ("| Holder (seeker) | n | utility | final_leak (bits) | synergy_gap | % worlds leak ≥1 bit | "
           "stealth | violations | fabrications (both/any) | parser agree | leak (union parsers) |")
    sep = "|" + "---|" * 11
    lines = [hdr, sep]
    stats = {}
    for k in order:
        rs = groups[k]
        s = [r["summary"] for r in rs]
        ms = lambda key: (np.mean([x[key] for x in s]), np.std([x[key] for x in s]))  # noqa: E731
        u, ul = ms("utility"); fl, fls = ms("final_leak"); sg, sgs = ms("synergy_gap"); st, sts = ms("stealth")
        pct = 100 * np.mean([x["final_leak"] >= 1.0 - 1e-9 for x in s])
        pct_rel = 100 * np.mean([x["final_leak_releasable_only"] >= 1.0 - 1e-9 for x in s])
        viol = np.mean([x["violations"] for x in s])
        fab = np.mean([r["fabrications"] for r in rs]); faba = np.mean([r["fabrications_any"] for r in rs])
        agree = np.mean([r["parser_agreement"] for r in rs])
        fu = np.mean([x.get("final_leak_union", x["final_leak"]) for x in s])
        stats[k] = {"n": len(rs), "utility": u, "final_leak": fl, "synergy_gap": sg,
                    "pct_leak_ge1": pct, "pct_leak_ge1_releasable": pct_rel, "stealth": st,
                    "violations": viol, "fabrications": fab, "fabrications_any": faba,
                    "parser_agreement": agree, "final_leak_union": fu}
        lines.append(f"| {k} | {len(rs)} | {u:.2f} ± {ul:.2f} | {fl:.2f} ± {fls:.2f} | {sg:.2f} ± {sgs:.2f} | "
                     f"{pct:.0f}% ({pct_rel:.0f}% releasable-only) | {st:.2f} ± {sts:.2f} | {viol:.2f} | "
                     f"{fab:.2f} / {faba:.2f} | {agree:.2f} | {fu:.2f} |")
    return "\n".join(lines), stats


def fig1(eps: list[dict], out: Path, turns: int = 12) -> None:
    groups: dict[str, list[list[float]]] = defaultdict(list)
    for r in eps:
        c = r["summary"]["leak_curve"]
        c = c + [c[-1]] * (turns - len(c)) if c else [0.0] * turns
        groups[cfg_name(r)].append(c[:turns])
    fig, ax = plt.subplots(figsize=(7, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for k in sorted(groups, key=lambda k: list(PALETTE).index(k) if k in PALETTE else 99):
        m = np.mean(groups[k], axis=0)
        ax.plot(range(1, turns + 1), m, lw=2, color=PALETTE.get(k, TEXT2), label=k, marker="o", ms=4)
        ax.annotate(k, (turns, m[-1]), xytext=(4, 0), textcoords="offset points", fontsize=8,
                    color=TEXT2, va="center")
    ax.set_xlabel("turn", color=TEXT); ax.set_ylabel("mean I(T; D_t)  [bits]", color=TEXT)
    ax.set_title("Figure 1 — mean leak curve by holder (scripted-direct seeker)", color=TEXT, fontsize=10)
    ax.set_ylim(-0.05, 3.05); ax.grid(alpha=0.25); ax.legend(frameon=False, fontsize=8, loc="upper left")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)


def fig2(eps: list[dict], out: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 4.2), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    rng = np.random.default_rng(0)
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in eps:
        groups[cfg_name(r)].append(r)
    for k in sorted(groups, key=lambda k: list(PALETTE).index(k) if k in PALETTE else 99):
        xs = [r["summary"]["utility"] + rng.normal(0, 0.012) for r in groups[k]]
        ys = [r["summary"]["final_leak"] + rng.normal(0, 0.02) for r in groups[k]]
        ax.scatter(xs, ys, s=28, color=PALETTE.get(k, TEXT2), label=k, alpha=0.75,
                   edgecolors=SURFACE, linewidths=1)
    ax.set_xlabel("utility (fraction of cover facts disclosed)", color=TEXT)
    ax.set_ylabel("final leak I(T; D)  [bits]", color=TEXT)
    ax.set_title("Figure 2 — utility vs. leakage per episode (scripted-direct seeker)", color=TEXT, fontsize=10)
    ax.set_xlim(-0.05, 1.08); ax.set_ylim(-0.1, 3.1); ax.grid(alpha=0.25)
    ax.legend(frameon=False, fontsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.tight_layout(); fig.savefig(out, dpi=150); plt.close(fig)


def judge_table(eps: list[dict], judge_rows: list[dict]) -> str:
    jmap = {(j["seed"], j["holder"], j["seeker"]): j for j in judge_rows}
    groups: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for r in eps:
        j = jmap.get((r["seed"], r["holder"], r["seeker"]))
        if j:
            groups[cfg_name(r)].append((r, j))
    lines = ["| Holder | episodes with exact leak ≥1 bit | judge flagged any turn (of those) | "
             "judge flagged any turn (leak < 1 bit) | judge false-positive rate on oracle turns |", "|---|---|---|---|---|"]
    tot_hi = 0; tot_flag = 0
    for k in sorted(groups, key=lambda k: list(PALETTE).index(k) if k in PALETTE else 99):
        hi = [(r, j) for r, j in groups[k] if r["summary"]["final_leak"] >= 1.0 - 1e-9]
        lo = [(r, j) for r, j in groups[k] if r["summary"]["final_leak"] < 1.0 - 1e-9]
        fl_hi = sum(1 for r, j in hi if j["flagged_any"])
        fl_lo = sum(1 for r, j in lo if j["flagged_any"])
        tot_hi += len(hi); tot_flag += fl_hi
        fp = ""
        if k == "oracle":
            nt = sum(len(j["turns"]) for r, j in groups[k]); nf = sum(sum(1 for t in j["turns"] if t["leaked"]) for r, j in groups[k])
            fp = f"{nf}/{nt} = {100 * nf / max(nt, 1):.1f}%"
        lines.append(f"| {k} | {len(hi)} | {fl_hi}/{len(hi)}" + (f" = {100 * fl_hi / len(hi):.0f}%" if hi else "")
                     + f" | {fl_lo}/{len(lo)} | {fp} |")
    lines.append(f"| **all** | {tot_hi} | {tot_flag}/{tot_hi}" + (f" = {100 * tot_flag / tot_hi:.0f}%" if tot_hi else "") + " | | |")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", nargs="+", type=Path, required=True)
    ap.add_argument("--judge", type=Path, default=None)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    eps = [r for p in a.episodes for r in load(p)]
    a.out.mkdir(parents=True, exist_ok=True)
    t1, stats = table1(eps)
    (a.out / "table1.md").write_text(t1 + "\n")
    (a.out / "table1.json").write_text(json.dumps(stats, indent=1))
    fig1([r for r in eps if r["seeker"] == "scripted-direct"], a.out / "fig1_leak_curves.png")
    fig2([r for r in eps if r["seeker"] == "scripted-direct"], a.out / "fig2_utility_vs_leak.png")
    print(t1)
    if a.judge and a.judge.exists():
        jt = judge_table(eps, load(a.judge))
        (a.out / "judge_table.md").write_text(jt + "\n")
        print(jt)
