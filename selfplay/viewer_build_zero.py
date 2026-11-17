"""Export the RLVR-vs-self-play study (PRIVACYZERO.md §6.9) into a static trace viewer: privacy-zero.flt.build

  python -m selfplay.viewer_build_zero --out viewer/site_zero
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import json
import shutil
from pathlib import Path

from selfplay.viewer_build import from_eval, from_selfplay, load

EVALS = [
    ("base", "Qwen3-8B base (held-out)"),
    ("sft_round2", "Warm start A: sft_round2, oracle-guided self-distillation (held-out)"),
    ("exp2_it01", "A → self-play run exp2, iteration 1 — the shipped checkpoint; attacker was still base (held-out)"),
    ("rlvr_it01", "A → RLVR (fixed attackers), iteration 1 — seed replicate of exp2_it01, leaks 0.64 (held-out)"),
    ("rlvr_it03", "A → RLVR (fixed attackers), iteration 3 (held-out)"),
    ("distill_opus_nll", "Warm start B: distill_opus_nll, Opus 5.5 distillation, plain NLL (held-out)"),
    ("drlvr_it03", "B → RLVR (fixed attackers), iteration 3 (held-out)"),
    ("drlvr_s1_it03", "B → RLVR, seed 1, iteration 3 (held-out)"),
    ("dsp_it03", "B → self-play, 25 % trained attacker, iteration 3 (held-out)"),
    ("dsp_s1_it03", "B → self-play, seed 1, iteration 3 (held-out)"),
    ("dsp2_it05", "B → self-play, 75 % trained attacker updated every iteration, iteration 5 (held-out)"),
]
TRAIN = [("rlvr", "00", "A → RLVR training rollouts, iteration 0"), ("rlvr", "05", "A → RLVR training rollouts, iteration 5 (drifted)"),
         ("drlvr", "03", "B → RLVR training rollouts, iteration 3"), ("dsp2", "05", "B → self-play training rollouts, iteration 5 (75 % vs the trained attacker)")]


def main(out: Path) -> None:
    (out / "data").mkdir(parents=True, exist_ok=True)
    for f in ("app.js", "index.html", "style.css", "server.py"):
        shutil.copy(Path("viewer/site") / f, out / f)
    datasets = []

    def add(ds_id, title, desc, eps):
        with gzip.open(out / "data" / f"{ds_id}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(eps, fh, ensure_ascii=False)
        datasets.append({"id": ds_id, "title": title, "description": desc, "n": len(eps)}); print(ds_id, len(eps))

    for tag, title in EVALS:
        eps = []
        for sub in ("direct", "ladder", "llm", "psi"):
            p = f"runs/selfplay_eval/{tag}/{sub}/episodes.jsonl"
            if Path(p).exists():
                eps += [from_eval(r, f"eval_{tag}_{sub}") for r in load(p)]
        if eps:
            add(f"eval_{tag}", title, "50 original worlds × scripted-direct, 30 × scripted-ladder, 20 × Haiku/Sonnet attackers, 20 paired ψ worlds × scripted-psi. Parser: Sonnet 5.5 intersection.", eps)
    p = "runs/selfplay_eval/crossplay_att/episodes.jsonl"
    if Path(p).exists():
        add("crossplay_trained_attackers", "Cross-play: every defender vs the trained attacker adapters",
            "7 defenders × 4 LLM attackers (base-prompted; dsp_att_it03 from the distilled self-play run; exp2_att_it03 and h4_att_it03 from the sft_round2 lineage) on the 50 held-out worlds, 2 episodes each. Training parser (local Qwen3-8B). Self-play's claimed benefit — robustness to an adapting attacker — is not visible here.",
            [from_selfplay(r, "crossplay_att") for r in load(p)])
    for run, it, title in TRAIN:
        p = f"selfplay/run/{run}/it{it}_episodes.jsonl"
        if Path(p).exists():
            add(f"train_{run}_it{it}", title, "48 training worlds × G = 8 defender samples at T = 1.0; attacker drawn per world from the mixture; a quarter of the rollouts were oracle-guided at sampling time (the hint is not stored). Training parser.", [from_selfplay(r, f"train_{run}_it{it}") for r in load(p)])
    (out / "index.json").write_text(json.dumps({"datasets": datasets, "generated": datetime.datetime.utcnow().isoformat() + "Z",
                                                "title": "PrivacyZero — RLVR vs self-play (PRIVACYZERO.md §6.9)"}, indent=1))
    print("index written:", len(datasets), "datasets")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, default=Path("viewer/site_zero")); main(ap.parse_args().out)
