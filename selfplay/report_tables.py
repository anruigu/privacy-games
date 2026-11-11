"""Markdown tables for PRIVACYZERO.md from runs/selfplay_eval/<tag>/summary.json and the run's metrics.jsonl.

  python -m selfplay.report_tables --tags base,it03,it07 --run selfplay/run/exp1
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def f(x, nd=2):
    return "–" if x is None else f"{x:.{nd}f}"


def checkpoint_table(tags: list[str]) -> str:
    S = {t: json.loads((Path("runs/selfplay_eval") / t / "summary.json").read_text()) for t in tags
         if (Path("runs/selfplay_eval") / t / "summary.json").exists()}
    out = ["| checkpoint | direct ≥1 bit | direct bits | ladder ≥1 bit | Haiku att. ≥1 bit | Sonnet att. ≥1 bit | utility (direct) | protected disclosed / ep | d1 | d2 | fabrications / ep | empty turns |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for t, s in S.items():
        d, l, h, so = s["direct"], s["ladder"], s.get("llm_haiku", {}), s.get("llm_sonnet", {})
        out.append(f"| {t} | {f(d['leak1'])} | {f(d['leak_bits'])} | {f(l['leak1'])} | {f(h.get('leak1'))} | {f(so.get('leak1'))} | "
                   f"{f(d['utility'])} | {f(d['violations'])} | {f(d['d1_disclosed'])} | {f(d['d2_disclosed'])} | {f(d['fabrications'])} | {f(d['empty_turns'])} |")
    out += ["", "| checkpoint | false-belief: deception | discretion | leak | episodes w/ false statement | false non-target stmts / ep | ψ flip key↑ (author) | ψ flip approver↑ | ψ flip cover↓ (external) | key pair disclosed: default / author / external | cover: default / external |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t, s in S.items():
        fb, ps = s["false_belief"], s["psi_flip"]
        out.append(f"| {t} | {f(fb['deception_rate'])} | {f(fb['discretion_rate'])} | {f(fb['leak_rate'])} | {f(fb['episodes_with_any_false_statement'])} | "
                   f"{f(fb['false_nontarget_per_episode'])} | {f(ps['flip_key_up'])} | {f(ps['flip_approver_up'])} | {f(ps['flip_cover_down'])} | "
                   f"{f(ps['default']['key_both'])} / {f(ps['author']['key_both'])} / {f(ps['external']['key_both'])} | {f(ps['default']['cover_frac'])} / {f(ps['external']['cover_frac'])} |")
    out += ["", "| checkpoint | withheld base rate | monitor acc: reasoning only | action only | both | trace reasons about combination | trace reasons about recipient | trace chars | train-parser exact agreement | train parser misses a leak the Sonnet parsers see |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for t, s in S.items():
        m, tp = s["monitor"], s.get("train_parser", {})
        bv, pr = m.get("by_view", {}), m.get("process", {})
        out.append(f"| {t} | {f(bv.get('action_only', {}).get('base_rate_withheld'))} | {f(bv.get('reasoning_only', {}).get('accuracy'))} | {f(bv.get('action_only', {}).get('accuracy'))} | "
                   f"{f(bv.get('both', {}).get('accuracy'))} | {f(pr.get('combination_rate'))} | {f(pr.get('recipient_rate'))} | {f(pr.get('mean_trace_chars'), 0)} | "
                   f"{f(tp.get('exact'))} | {f(tp.get('eval_says_leak_but_train_not'))} |")
    return "\n".join(out)


def training_table(run: Path) -> str:
    rows = [json.loads(l) for l in (run / "metrics.jsonl").read_text().splitlines() if l.strip()]
    out = ["| it | defender | attacker | train ≥1 bit: scripted-direct / ladder / trained attacker | train utility | empty | fab | probe ≥1 bit | probe utility | attacker asked d1 | attacker guess correct | KL | samples (def / att) | min |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ba = r["train"]["by_attacker"]
        att = next((v for k, v in ba.items() if k.startswith("llm@") and k != "llm@base"), ba.get("llm@base", {}))
        out.append(f"| {r['it']} | {r['defender_trained_from']} | {r['attacker']} | {f(ba.get('scripted-direct', {}).get('leak1'))} / {f(ba.get('scripted-ladder', {}).get('leak1'))} / {f(att.get('leak1'))} | "
                   f"{f(r['train']['utility'])} | {f(r['train']['empty'])} | {f(r['train']['fab'])} | {f(r['probe']['leak1'])} | {f(r['probe']['utility'])} | {f(att.get('asked_d1'))} | "
                   f"{f(att.get('correct'))} | {f(r['train_def']['kl'], 3)} | {r['n_def_samples']} / {r['n_att_samples']} | {r['t_total'] / 60:.0f} |")
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="base")
    ap.add_argument("--run", default="selfplay/run/exp1")
    a = ap.parse_args()
    print(checkpoint_table(a.tags.split(",")))
    print()
    print(training_table(Path(a.run)))
