"""Phase 4: run the per-message secret judge on every holder turn of logged episodes."""
from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .judge import judge_utterance
from .llm import BudgetExceeded, get_llm
from .schema import World

_lock = threading.Lock()


def judge_episode(worlds_dir: Path, rec: dict) -> dict:
    w = World.load((worlds_dir / f"seed_{rec['seed']:03d}.json").read_text())
    turns = []
    for t in rec["turns"]:
        j = judge_utterance(w, t["answer"])
        turns.append({"t": t["t"], "leaked": j["leaked"], "severity": j["severity"], "reason": j["reason"],
                      "ids": t["ids"], "leak_after": t["leak"]})
    return {"seed": rec["seed"], "holder": rec["holder"], "seeker": rec["seeker"], "turns": turns,
            "flagged_any": any(x["leaked"] for x in turns),
            "max_severity": max((x["severity"] for x in turns), default=0),
            "final_leak": rec["summary"]["final_leak"]}


def main(episodes: list[Path], worlds: Path, out: Path, workers: int = 8) -> None:
    recs = [json.loads(l) for p in episodes for l in p.read_text().splitlines() if l.strip()]
    done = set()
    if out.exists():
        for l in out.read_text().splitlines():
            j = json.loads(l); done.add((j["seed"], j["holder"], j["seeker"]))
    todo = [r for r in recs if (r["seed"], r["holder"], r["seeker"]) not in done]
    print(f"{len(todo)} episodes to judge; spent ${get_llm().spent:.2f}")
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(judge_episode, worlds, r): r for r in todo}
        for f in as_completed(futs):
            try:
                j = f.result()
            except BudgetExceeded as e:
                print("BUDGET:", e); continue
            except Exception as e:  # noqa
                print("ERROR", repr(e)); continue
            with _lock, out.open("a") as fh:
                fh.write(json.dumps(j) + "\n")
            print(f"seed={j['seed']:03d} holder={j['holder']:8s} leak={j['final_leak']:.2f} flagged={j['flagged_any']} "
                  f"maxsev={j['max_severity']:.0f} spent=${get_llm().spent:.2f}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", nargs="+", type=Path, required=True)
    ap.add_argument("--worlds", type=Path, default=Path("runs/worlds"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    main(a.episodes, a.worlds, a.out, a.workers)
