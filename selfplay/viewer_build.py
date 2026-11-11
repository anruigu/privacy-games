"""Export episodes into the static trace viewer (viewer/site): index.json + data/<dataset>.json.gz

  python -m selfplay.viewer_build --out viewer/site
"""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

from dossier import infer
from dossier.schema import World

WORLD_CACHE: dict[tuple, dict] = {}


def world_view(wd: str, seed: int, psi: str | None = None) -> dict:
    key = (wd, seed, psi)
    if key not in WORLD_CACHE:
        p = Path(wd) / (f"seed_{seed:03d}_{psi}.json" if psi else f"seed_{seed:03d}.json")
        w = World.load(p.read_text())
        chain = w.key_chain()
        WORLD_CACHE[key] = {
            "seed": seed, "company": w.company, "holder": f"{w.holder_name}, {w.holder_role}",
            "seeker": f"{w.seeker_name}, {w.seeker_role}", "cover_task": w.cover_task, "psi": w.psi, "arm": w.knobs.tag(),
            "approver": w.emp(w.approver).name, "key_chain": chain, "available_bits": round(infer.available_bits(w), 3),
            "facts": [{"id": f.id, "norm": f.norm, "family": f.family, "sentence": f.sentence,
                       "key": f.id in chain, "route": f.family == "route"} for f in w.facts],
        }
    return WORLD_CACHE[key]


def from_eval(rec: dict, source: str) -> dict:
    """dossier.run episode record (held-out evals, cross-play)."""
    wd = rec.get("worlds_dir", "runs/worlds")
    wv = world_view(wd, rec["seed"], rec.get("psi") if "psi_eval" in wd else None)
    s = rec["summary"]
    turns = [{"t": t["t"], "question": t["question"], "asked": [t["asked_fid"]] if t.get("asked_fid") else [],
              "answer": t["answer"], "reasoning": t.get("reasoning") or "", "ids": t["ids"], "new_ids": t.get("new_ids", []),
              "leak": round(t["leak"], 3), "judge": None} for t in rec["turns"]]
    return {"id": f"{source}:{rec['seed']}:{rec['holder']}:{rec['seeker']}" + (f":{rec['psi']}" if rec.get("psi") else ""),
            "source": source, "seed": rec["seed"], "holder": rec["holder"], "seeker": rec["seeker"], "psi": rec.get("psi", wv["psi"]),
            "world": wv, "turns": turns,
            "summary": {"leak_bits": round(s["final_leak"], 3), "available_bits": round(s.get("available_bits", wv["available_bits"]), 3),
                        "utility": round(s["utility"], 3), "violations": s["violations"],
                        "key_disclosed": s.get("key_disclosed") or {k: (k in s.get("disclosed", [])) for k in wv["key_chain"]},
                        "guess": rec.get("seeker_guess"), "correct": rec.get("seeker_correct"),
                        "fabrications": rec.get("fabrications", 0)}}


def from_selfplay(rec: dict, source: str) -> dict:
    """selfplay.episode record (training rollouts)."""
    wv = world_view("runs/worlds_train" if rec["seed"] >= 1000 else "runs/worlds", rec["seed"])
    turns = [{"t": t["t"], "question": t["question"], "asked": t["asked"], "answer": t["answer"], "reasoning": t.get("reasoning") or "",
              "ids": t["ids"], "new_ids": t["new_ids"], "leak": round(t["leak"], 3), "judge": None} for t in rec["turns"]]
    return {"id": f"{source}:{rec['seed']}:{rec['defender']}:{rec['attacker']}:{'guided' if rec.get('hint') else 'plain'}:{rec['variant']}",
            "source": source, "seed": rec["seed"], "holder": rec["defender"] + (" (oracle-guided sampling)" if rec.get("hint") else ""),
            "seeker": rec["attacker"], "psi": rec.get("psi", "default"), "world": wv, "turns": turns,
            "summary": {"leak_bits": round(rec["leak_bits"], 3), "available_bits": round(rec["available_bits"], 3),
                        "utility": round(rec["utility"], 3), "violations": rec["violations"], "key_disclosed": rec["key_disclosed"],
                        "guess": rec.get("guess"), "correct": rec.get("correct"), "fabrications": rec.get("fabrications", 0),
                        "r_def": round(rec["r_def"], 3)}}


def load(p: str) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()]


def main(out: Path) -> None:
    (out / "data").mkdir(parents=True, exist_ok=True)
    datasets = []

    def add(ds_id, title, desc, eps):
        with gzip.open(out / "data" / f"{ds_id}.json.gz", "wt", encoding="utf-8") as fh:
            json.dump(eps, fh, ensure_ascii=False)
        datasets.append({"id": ds_id, "title": title, "description": desc, "n": len(eps)})
        print(ds_id, len(eps))

    # held-out evals of checkpoints (Sonnet double parser)
    for tag, title in [("base", "Qwen3-8B baseline (held-out)"), ("it07_drift", "PrivacyZero it07, lr 1e-4 branch (held-out)"),
                       ("it10", "PrivacyZero it10, turn-local regret (held-out)"), ("sft_guided", "Warm start round 1 (held-out)"),
                       ("sft_round2", "Warm start round 2: first checkpoint passing the checks (held-out)")]:
        eps = []
        for sub in ("direct", "ladder", "llm", "psi"):
            p = f"runs/selfplay_eval/{tag}/{sub}/episodes.jsonl"
            if Path(p).exists():
                eps += [from_eval(r, f"eval_{tag}_{sub}") for r in load(p)]
        if eps:
            add(f"eval_{tag}", title, "50 original worlds × scripted-direct, 30 × scripted-ladder, 20 × Haiku/Sonnet attackers, 20 paired ψ worlds × scripted-psi. Parser: Sonnet 5.5 intersection.", eps)
    # cross-play: 14 holders vs scripted seeker; 6 LLM attackers vs 14 defenders
    xp = load("runs/xp_holders/episodes.jsonl")
    add("crossplay_holders", "Cross-play: 14 models as holder vs scripted-direct seeker", "EVAL.md Table 1 episodes (50 worlds per model). Open-weight models leak in 88–100 % of worlds, flagships 0 %.", [from_eval(r, "xp_holders") for r in xp])
    xc = load("runs/xp_cross/episodes.jsonl") + load("runs/xp_cross_qwen9b/episodes.jsonl")
    add("crossplay_attackers", "Cross-play: LLM attackers vs LLM defenders", "EVAL.md §2 episodes (10 worlds per cell; attacker asks 10 questions then guesses).", [from_eval(r, "xp_cross") for r in xc])
    # training rollouts (guided vs plain) from the self-play loop
    for it in ("00", "10"):
        p = f"selfplay/run/exp1/it{it}_episodes.jsonl"
        if Path(p).exists():
            eps = [from_selfplay(r, f"train_it{it}") for r in load(p)]
            add(f"train_it{it}", f"Self-play training rollouts, iteration {int(it)}", "Defender T=1.0, training parser (local Qwen3-8B). Half the rollouts are oracle-guided (the oracle's verdict was appended to the live user turn at sampling time; it is not shown here).", eps)
    # oracle-guided rollouts used for the expert-iteration warm start
    p = "runs/selfplay_sft/guided_round2.jsonl"
    if Path(p).exists():
        add("guided_round2", "Oracle-guided rollouts (base model; warm-start data)", "Base Qwen3-8B, T=0.9, vs scripted attackers on the training worlds, with the oracle's verdict appended to each live user turn at sampling time (the verdict is not stored). Oracle-consistent turns from these episodes form the warm-start SFT set.", [from_selfplay(r, "guided_round2") for r in load(p)])
    # Sotopia traces (markdown)
    traces = []
    for d in sorted(Path("traces").glob("stage2*")):
        for f in sorted(d.glob("seed_*.md")):
            traces.append({"id": f"{d.name}/{f.name}", "title": f"{d.name} / {f.stem}", "markdown": f.read_text()})
    with gzip.open(out / "data" / "sotopia.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(traces, fh, ensure_ascii=False)
    datasets.append({"id": "sotopia", "title": "SOTOPIA-S4 renders (Stage 2)", "description": "Rendered Sotopia episodes from the portability check (P1–P5).", "n": len(traces), "kind": "markdown"})
    (out / "index.json").write_text(json.dumps({"datasets": datasets, "generated": __import__("datetime").datetime.utcnow().isoformat() + "Z"}, indent=1))
    print("index written:", len(datasets), "datasets")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", type=Path, default=Path("viewer/site")); a = ap.parse_args(); main(a.out)
