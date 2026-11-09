"""Phase 8 / P5: one world split across two holders, run as a native 3-agent Sotopia episode.

Scores the exact metric over the UNION of both holders' disclosures, and each holder in isolation.
"""
from __future__ import annotations

from . import backend  # noqa: F401

import argparse
import asyncio
import json
import time
from pathlib import Path

from sotopia.agents import LLMAgent
from sotopia.database import EpisodeLog
from sotopia.database.evaluation_dimensions import SotopiaDimensions
from sotopia.envs.evaluators import EvaluationForAgents, RuleBasedTerminatedEvaluator
from sotopia.envs.parallel import ParallelSotopiaEnv
from sotopia.server import arun_one_episode

from .. import infer
from ..schema import World
from .evaluator import ExactLeakEvaluator, RecordingLLMEvaluator
from .from_sotopia import evaluator_record, transcript
from .run_s4 import AGENT_MODEL, EVAL_MODEL, _usage_log, custom
from .to_sotopia import TAG, codename, save_split_profiles

MAX_TURNS = 40  # 3 agents round-robin: 11 questions ≈ 33 agent-turns + slack


async def run_world(world: World, out: Path, sidecar: Path) -> dict:
    env_profile, (seeker_p, hA, hB), (A, B) = save_split_profiles(world, sidecar)
    nameA = f"{hA.first_name} {hA.last_name}"
    nameB = f"{hB.first_name} {hB.last_name}"
    union_eval = ExactLeakEvaluator(world, {nameA, nameB}, holder_key="agent_2")
    env = ParallelSotopiaEnv(
        env_profile=env_profile, model_name=custom(EVAL_MODEL), action_order="round-robin",
        evaluators=[RuleBasedTerminatedEvaluator(max_turn_number=MAX_TURNS, max_stale_turn=8)],  # first runs on 2026-11-09 used 4: stale rule cut episodes short
        terminal_evaluators=[RecordingLLMEvaluator(custom(EVAL_MODEL), EvaluationForAgents[SotopiaDimensions]), union_eval],
    )
    agents = [LLMAgent(agent_profile=seeker_p, model_name=custom(AGENT_MODEL)),
              LLMAgent(agent_profile=hA, model_name=custom(AGENT_MODEL)),
              LLMAgent(agent_profile=hB, model_name=custom(AGENT_MODEL))]
    tag = f"{TAG}-split:{codename(world)}:{int(time.time())}"
    t0 = time.time()
    await arun_one_episode(env=env, agent_list=agents, tag=tag, push_to_db=True)
    eps = EpisodeLog.find(EpisodeLog.tag == tag).all()
    if not eps:
        return {"seed": world.seed, "completed": False, "reason": "no EpisodeLog stored"}
    ep = eps[0]
    tr = transcript(ep)
    rec = evaluator_record(ep)
    # isolation scores: re-score each holder alone from the stored transcript (parser calls are cached)
    iso = {}
    for name in (nameA, nameB):
        e = ExactLeakEvaluator(world, name)
        from sotopia.messages import AgentAction
        msgs = [(t["speaker"], AgentAction(action_type="speak", argument=t["utterance"])) for t in tr if t["action"] == "speak"]
        iso[name] = {k: e.score(msgs)[k] for k in ("final_leak", "synergy_gap", "utility", "disclosed")}
    res = {"seed": world.seed, "tag": tag, "episode_pk": ep.pk, "completed": True, "wall": time.time() - t0,
           "sotopia_turns": len(ep.messages) - 1, "n_agents": len(ep.agents), "transcript": tr,
           "union": {k: rec[k] for k in ("final_leak", "synergy_gap", "utility", "violations", "disclosed")} if rec else None,
           "isolation": iso, "partition": {"A": A, "B": B}, "models": ep.models}
    with (out / "episodes.jsonl").open("a") as fh:
        fh.write(json.dumps(res) + "\n")
    print(f"seed={world.seed:03d} turns={res['sotopia_turns']} union_leak={res['union']['final_leak'] if rec else None} "
          f"iso={{ {nameA}: {iso[nameA]['final_leak']:.2f}, {nameB}: {iso[nameB]['final_leak']:.2f} }}", flush=True)
    return res


async def main(seeds, out: Path, worlds_dir: Path, parallel: int):
    out.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(parallel)

    async def one(s):
        async with sem:
            w = World.load((worlds_dir / f"seed_{s:03d}.json").read_text())
            try:
                return await run_world(w, out, out / "sidecar")
            except Exception as e:  # noqa
                print(f"seed={s:03d} ERROR {e!r}", flush=True)
                return {"seed": s, "completed": False, "reason": repr(e)}

    results = await asyncio.gather(*[one(s) for s in seeds])
    usd = sum(u["usd"] for u in _usage_log)
    (out / "usage.json").write_text(json.dumps({"calls": len(_usage_log), "usd": usd}))
    print(f"completed {sum(1 for r in results if r.get('completed'))}/{len(seeds)}; litellm spend ≈ ${usd:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-4")
    ap.add_argument("--out", type=Path, default=Path("runs/stage2_p5"))
    ap.add_argument("--worlds", type=Path, default=Path("runs/worlds"))
    ap.add_argument("--parallel", type=int, default=2)
    a = ap.parse_args()
    lo, hi = a.seeds.split("-"); seeds = list(range(int(lo), int(hi) + 1))
    asyncio.run(main(seeds, a.out, a.worlds, a.parallel))
