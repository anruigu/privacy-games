"""Episode loop. Logs one JSON record per episode to <out>/episodes.jsonl."""
from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import infer, parse
from .agents.holder import make_holder
from .agents.seeker import make_seeker
from .llm import MODELS, BudgetExceeded, get_llm
from .schema import World

TURN_BUDGET = 12
_write_lock = threading.Lock()


def load_world(worlds_dir: Path, seed: int) -> World:
    return World.load((worlds_dir / f"seed_{seed:03d}.json").read_text())


def run_episode(world: World, holder_kind: str, seeker_kind: str, turn_budget: int = TURN_BUDGET) -> dict:
    holder = make_holder(holder_kind, world)
    seeker = make_seeker(seeker_kind, world)
    history: list[dict] = []       # holder-facing history
    seeker_hist: list[dict] = []   # seeker-facing history
    D: list[str] = []              # scored disclosure set (parser intersection)
    D_union: list[str] = []        # sensitivity: union of the two parsers
    D_truth: list[str] = []        # oracle ground truth (empty for LLM holders)
    turns = []
    per_turn_new: list[list[str]] = []
    t0 = time.time()
    for t in range(turn_budget):
        asked_fid, question = seeker.next_question(seeker_hist)
        if question is None or not question.strip():
            break  # scripted plan exhausted, or LLM seeker chose to stop asking
        ledger_ids = [f for f in D if world.fact(f).norm != "public"]
        answer, truth_ids, user_content = holder.reply(question, asked_fid, history, ledger_ids)
        p = parse.parse_both(world, answer)
        new = [f for f in p["ids"] if f not in D]
        D.extend(new)
        D_union.extend(f for f in sorted(set(p["a"]) | set(p["b"])) if f not in D_union)
        per_turn_new.append(new)
        for f in truth_ids:
            if f not in D_truth:
                D_truth.append(f)
        lk = infer.leak(world, D)
        turns.append({
            "t": t, "asked_fid": asked_fid, "question": question, "user_content": user_content,
            "answer": answer, "parse_a": p["a"], "parse_b": p["b"], "ids": p["ids"],
            "agree": p["agree"], "fab_a": p["fab_a"], "fab_b": p["fab_b"],
            "truth_ids": truth_ids, "new_ids": new, "leak": lk,
        })
        history.append({"user_content": user_content, "answer": answer})
        seeker_hist.append({"question": question, "answer": answer})
    summary = infer.summarize(world, per_turn_new)
    summary["final_leak_union"] = infer.leak(world, D_union)
    summary["disclosed_union"] = D_union
    rec = {
        "seed": world.seed, "holder": holder_kind, "seeker": seeker_kind,
        "holder_model": getattr(holder, "model", None),
        "n_turns": len(turns), "turns": turns, "summary": summary,
        "parser_agreement": (sum(1 for x in turns if x["agree"]) / len(turns)) if turns else 1.0,
        "fabrications": sum(1 for x in turns if x["fab_a"] and x["fab_b"]),
        "fabrications_any": sum(1 for x in turns if x["fab_a"] or x["fab_b"]),
        "truth_disclosed": D_truth,
        "wall": time.time() - t0,
    }
    if seeker_kind == "llm-direct":
        guess = seeker.final_guess(seeker_hist)
        rec["seeker_guess"] = guess
        rec["seeker_correct"] = world.emp(world.approver).name.lower() in guess.lower()
    return rec


def _done_keys(path: Path) -> set[tuple]:
    keys = set()
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                r = json.loads(line)
                keys.add((r["seed"], r["holder"], r["seeker"]))
            except Exception:
                pass
    return keys


def run_grid(worlds_dir: Path, out: Path, holders: list[str], seekers: list[str], seeds: list[int],
             workers: int = 8, turn_budget: int = TURN_BUDGET) -> None:
    out.mkdir(parents=True, exist_ok=True)
    path = out / "episodes.jsonl"
    done = _done_keys(path)
    jobs = [(s, h, k) for k in seekers for h in holders for s in seeds if (s, h, k) not in done]
    print(f"{len(jobs)} episodes to run ({len(done)} already done); spent so far ${get_llm().spent:.2f}")
    llm = get_llm()

    def job(s, h, k):
        w = load_world(worlds_dir, s)
        return run_episode(w, h, k, turn_budget)

    n_ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(job, *j): j for j in jobs}
        for fut in as_completed(futs):
            j = futs[fut]
            try:
                rec = fut.result()
            except BudgetExceeded as e:
                print("BUDGET:", e)
                continue
            except Exception as e:  # noqa
                print("ERROR", j, repr(e))
                continue
            with _write_lock:
                with path.open("a") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_ok += 1
            s = rec["summary"]
            print(f"seed={j[0]:03d} holder={j[1]:8s} seeker={j[2]:15s} turns={rec['n_turns']:2d} "
                  f"util={s['utility']:.2f} leak={s['final_leak']:.2f} gap={s['synergy_gap']:.2f} "
                  f"viol={s['violations']} agree={rec['parser_agreement']:.2f} spent=${llm.spent:.2f}",
                  flush=True)
    print(f"done: {n_ok}/{len(jobs)} episodes; total spent ${llm.spent:.2f}")


def parse_seeds(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--worlds", type=Path, default=Path("runs/worlds"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--holders", default="oracle,vanilla,ci,ledger")
    ap.add_argument("--seekers", default="scripted-direct")
    ap.add_argument("--seeds", default="0-49")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--turns", type=int, default=TURN_BUDGET)
    a = ap.parse_args()
    run_grid(a.worlds, a.out, a.holders.split(","), a.seekers.split(","), parse_seeds(a.seeds),
             a.workers, a.turns)
