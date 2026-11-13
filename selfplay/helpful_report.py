"""Results table for HELPFUL_RL.md §6: one row per checkpoint, held-out leak columns from eval_ckpt summaries,
helpfulness columns from the null-world runs and the question classifier.

  python -m selfplay.helpful_report --tags sft_round2,exp2_it01,...   -> prints markdown, writes runs/selfplay_eval/helpful_rl.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .helpful import OUT, NULL_ARMS, null_metrics, legit_metrics, load, load_questions_all


def fmt(x, pct=True):
    if x is None:
        return "–"
    return f"{100 * x:.0f}%" if pct else f"{x:.2f}"


def row(tag: str, questions: dict) -> dict:
    s = json.load(open(OUT / tag / "summary.json"))
    n = null_metrics(OUT / tag / "null")
    lg = legit_metrics(load(OUT / tag / "llm" / "episodes.jsonl"), questions)
    fb = s["false_belief"]; ps = s["psi_flip"]; mon = s.get("monitor", {}).get("by_view", {}).get("both", {})
    return {"tag": tag, "leak_direct": s["direct"]["leak1"], "bits": s["direct"]["leak_bits"], "leak_ladder": s["ladder"]["leak1"],
            "leak_haiku": s["llm_haiku"]["leak1"], "leak_sonnet": s["llm_sonnet"]["leak1"], "utility": s["direct"]["utility"],
            "fab": s["direct"].get("fabrications"), "d1_secret": n.get("n2_r0_k2", {}).get("d1_answered"),
            "d1_public": n.get("null-public", {}).get("d1_answered"), "d1_nomemo": n.get("null-nomemo", {}).get("d1_answered"),
            "cover": lg.get("cover_answered_rate"), "cover_n": lg.get("cover_asked"), "deception": fb.get("deception_rate"),
            "flip_key_up": ps.get("flip_key_up"), "flip_cover_down": ps.get("flip_cover_down"), "monitor": mon.get("accuracy")}


def table(rows):
    hdr = ("| checkpoint | leak ≥1 bit: direct / ladder / Haiku / Sonnet | bits (direct) | utility | d1 answered: secret / floor public / no memo | "
           "cover asks answered | deception | ψ key-up / cover-down | monitor acc | fab/ep |")
    out = [hdr, "|" + "---|" * 10]
    for r in rows:
        out.append(f"| {r['tag']} | {fmt(r['leak_direct'])} / {fmt(r['leak_ladder'])} / {fmt(r['leak_haiku'])} / {fmt(r['leak_sonnet'])} | "
                   f"{fmt(r['bits'], False)} | {fmt(r['utility'], False)} | {fmt(r['d1_secret'])} / {fmt(r['d1_public'])} / {fmt(r['d1_nomemo'])} | "
                   f"{fmt(r['cover'])} (n={r['cover_n']}) | {fmt(r['deception'])} | {fmt(r['flip_key_up'])} / {fmt(r['flip_cover_down'])} | "
                   f"{fmt(r['monitor'])} | {fmt(r['fab'], False)} |")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="sft_round2,exp2_it00,exp2_it01,exp2_it02,exp2_it03,h1_it01,h1_it03,h2_it01,h2_it03,h3_it01,h3_it03,h4_it01,h4_it03,sft_h,h5_it01,h5_it03")
    a = ap.parse_args()
    q = load_questions_all()
    rows = []
    for t in a.tags.split(","):
        try:
            rows.append(row(t, q))
        except FileNotFoundError as e:
            print("skip", t, e)
    md = table(rows)
    (OUT / "helpful_rl.md").write_text(md + "\n"); (OUT / "helpful_rl.json").write_text(json.dumps(rows, indent=1))
    print(md)
