"""Render stored Sotopia EpisodeLog objects as human-readable markdown traces.

Everything shown comes from the EpisodeLog (turn-0 environment messages carry each agent's rendered
perspective: scenario, backgrounds incl. fact lists, goals; later turns carry the actions; `reasoning`
carries the terminal evaluators' output). Usage:

  .venv-sotopia/bin/python -m dossier.sotopia_adapter.render_trace --run runs/stage2_sonnet --out traces/stage2_sonnet
"""
from __future__ import annotations

from . import backend  # noqa: F401

import argparse
import json
import re
from pathlib import Path

from sotopia.database import EpisodeLog

from .from_sotopia import evaluator_record


def render(ep: EpisodeLog, title: str) -> str:
    out = [f"# {title}", "", f"- EpisodeLog pk: `{ep.pk}`", f"- tag: `{ep.tag}`", f"- models: {ep.models}",
           f"- Sotopia turns: {len(ep.messages) - 1}", ""]
    # turn 0: environment -> each agent (their perspective)
    out.append("## Turn 0 — what each agent sees (environment message)")
    for sender, receiver, text in ep.messages[0]:
        if sender == "Environment":
            out.append(f"\n### Perspective of {receiver}\n")
            out.append("```text\n" + text.strip() + "\n```")
    out.append("\n## Conversation\n")
    for t, turn in enumerate(ep.messages[1:], start=1):
        for sender, receiver, text in turn:
            if sender == "Environment" or receiver != "Environment":
                continue
            text = text.strip()
            if text == "did nothing" or text.startswith("[none]"):
                out.append(f"- **Turn {t} — {sender}**: *(did nothing)*")
            else:
                m = re.match(r'^said: "(.*)"$', text, re.S)
                body = m.group(1) if m else text
                out.append(f"- **Turn {t} — {sender}**: {body}")
    out.append("\n## Evaluation (terminal evaluators, from `EpisodeLog.reasoning`)\n")
    rec = evaluator_record(ep)
    if rec:
        out.append("**Exact-leak evaluator (dossier):**\n")
        out.append(f"- final I(T;D) = **{rec['final_leak']:.2f} bits**, synergy gap {rec['synergy_gap']:.2f}, utility {rec['utility']:.2f}, violations {rec['violations']}")
        out.append(f"- leak curve over holder utterances: {[round(x, 2) for x in rec['leak_curve']]}")
        out.append(f"- fact IDs newly entailed per holder utterance: {rec['per_turn_new']}")
        out.append("")
    reasoning = re.sub(r"EXACT_LEAK_JSON_BEGIN.*?EXACT_LEAK_JSON_END", "(exact-leak JSON record, shown above)", ep.reasoning or "", flags=re.S)
    out.append("**Stock Sotopia LLM evaluator + termination reason (verbatim):**\n")
    out.append("```text\n" + reasoning.strip() + "\n```")
    out.append(f"\n`EpisodeLog.rewards` = {ep.rewards}  (always 0 in sotopia 0.1.5, see adapter debt)")
    return "\n".join(out) + "\n"


def main(run_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in (run_dir / "episodes.jsonl").read_text().splitlines()]
    index = []
    for r in sorted(rows, key=lambda r: r["seed"]):
        if not r.get("completed"):
            continue
        ep = EpisodeLog.get(pk=r["episode_pk"])
        leak = r.get("evaluator", r.get("union") or {}).get("final_leak") if isinstance(r.get("evaluator", r.get("union")), dict) else None
        name = f"seed_{r['seed']:03d}.md"
        title = f"{run_dir.name} — seed {r['seed']}"
        (out_dir / name).write_text(render(ep, title))
        index.append(f"- [{name}]({name}) — exact leak {leak if leak is None else round(leak, 2)} bits, {len(ep.messages) - 1} turns")
    (out_dir / "README.md").write_text(f"# Traces: {run_dir.name}\n\nRendered from the stored Sotopia `EpisodeLog` objects only.\n\n" + "\n".join(index) + "\n")
    print(f"wrote {len(index)} traces to {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    main(a.run, a.out)
