"""Drive dossier worlds through the Sotopia engine (Phase 7) and extract results (P2–P4).

Usage (sotopia venv):
  SOTOPIA_STORAGE_BACKEND=local CUSTOM_API_KEY=$ANTHROPIC_API_KEY \
  python -m dossier.sotopia_adapter.run_s4 --seeds 0-9 --out runs/stage2

Model routing: Sotopia generates actions with litellm structured output, which forces tool_choice;
Claude 5.x rejects forced tool choice, so we route through Anthropic's OpenAI-compatible endpoint via
Sotopia's own `custom/<model>@<base_url>` convention (a runner setting, no engine change).
"""
from __future__ import annotations

from . import backend  # noqa: F401  (must precede sotopia.database imports)

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import litellm
from sotopia.agents import LLMAgent
from sotopia.database import EpisodeLog
from sotopia.database.evaluation_dimensions import SotopiaDimensions
from sotopia.envs.evaluators import EvaluationForAgents, RuleBasedTerminatedEvaluator
from sotopia.envs.parallel import ParallelSotopiaEnv
from sotopia.server import arun_one_episode

from ..llm import PRICES
from ..schema import World
from .evaluator import ExactLeakEvaluator, RecordingLLMEvaluator
from .from_sotopia import evaluator_record, stock_secret_score, transcript
from .to_sotopia import TAG, codename, save_profiles

ANTHROPIC_OPENAI_BASE = "https://api.anthropic.com/v1/"
AGENT_MODEL = os.environ.get("S4_AGENT_MODEL", "claude-opus-5-5")
EVAL_MODEL = os.environ.get("S4_EVAL_MODEL", "claude-sonnet-5-5")
MAX_TURNS = 32  # 11 questions + 11 answers + slack for greetings/idle turns; Sotopia counts each agent action as a turn


def custom(model: str) -> str:
    return f"custom/{model}@{ANTHROPIC_OPENAI_BASE}"


_usage_log: list[dict] = []


class _UsageLogger(litellm.integrations.custom_logger.CustomLogger):
    def _rec(self, kwargs, response_obj):
        try:
            u = response_obj.usage
            base = kwargs.get("model", "").split("/")[-1]
            pin, pout, _, _ = PRICES.get(base, (10.0, 50.0, 0, 0))
            usd = (u.prompt_tokens * pin + u.completion_tokens * pout) / 1e6
            _usage_log.append({"model": base, "in": u.prompt_tokens, "out": u.completion_tokens, "usd": usd})
        except Exception:
            pass

    def log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._rec(kwargs, response_obj)

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._rec(kwargs, response_obj)


import litellm.integrations.custom_logger  # noqa: E402
litellm.callbacks = [_UsageLogger()]


async def run_world(world: World, out: Path, sidecar: Path) -> dict:
    env_profile, (seeker_p, holder_p), rel = save_profiles(world, sidecar)
    holder_name = f"{holder_p.first_name} {holder_p.last_name}"
    exact = ExactLeakEvaluator(world, holder_name, holder_key="agent_2")
    env = ParallelSotopiaEnv(
        env_profile=env_profile, model_name=custom(EVAL_MODEL), action_order="round-robin",
        evaluators=[RuleBasedTerminatedEvaluator(max_turn_number=MAX_TURNS, max_stale_turn=3)],
        terminal_evaluators=[RecordingLLMEvaluator(custom(EVAL_MODEL), EvaluationForAgents[SotopiaDimensions]), exact],
    )
    agents = [LLMAgent(agent_profile=seeker_p, model_name=custom(AGENT_MODEL)),
              LLMAgent(agent_profile=holder_p, model_name=custom(AGENT_MODEL))]
    tag = f"{TAG}:{codename(world)}:{int(time.time())}"
    t0 = time.time()
    await arun_one_episode(env=env, agent_list=agents, tag=tag, push_to_db=True)
    wall = time.time() - t0
    # ---- P4: everything below comes from the stored EpisodeLog only ----
    eps = [e for e in EpisodeLog.find(EpisodeLog.tag == tag).all()]
    if not eps:
        return {"seed": world.seed, "completed": False, "reason": "no EpisodeLog stored", "tag": tag}
    ep = eps[0]
    tr = transcript(ep)
    rec = evaluator_record(ep)
    secret = stock_secret_score(ep)
    n_holder = sum(1 for t in tr if t["speaker"] == holder_name and t["action"] == "speak")
    n_seeker = sum(1 for t in tr if t["speaker"] != holder_name and t["action"] == "speak")
    left = any(t["action"] == "leave" for t in tr)
    res = {"seed": world.seed, "tag": tag, "episode_pk": ep.pk, "completed": True, "wall": wall,
           "sotopia_turns": len(ep.messages) - 1, "holder_utterances": n_holder, "seeker_utterances": n_seeker,
           "left_early": left, "transcript": tr, "evaluator": rec, "stock_secret": secret,
           "rewards": ep.rewards, "models": ep.models, "in_log_evaluator_exact_leak": rec["final_leak"] if rec else None,
           "in_memory_evaluator_exact_leak": exact.last["final_leak"] if exact.last else None}
    with (out / "episodes.jsonl").open("a") as fh:
        fh.write(json.dumps(res) + "\n")
    print(f"seed={world.seed:03d} turns={res['sotopia_turns']} holder_utts={n_holder} left={left} "
          f"leak={res['in_log_evaluator_exact_leak']} secret={secret} wall={wall:.0f}s", flush=True)
    return res


async def main(seeds: list[int], out: Path, worlds_dir: Path, parallel: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    sidecar = out / "sidecar"
    sem = asyncio.Semaphore(parallel)

    async def one(s):
        async with sem:
            w = World.load((worlds_dir / f"seed_{s:03d}.json").read_text())
            try:
                return await run_world(w, out, sidecar)
            except Exception as e:  # noqa
                print(f"seed={s:03d} ERROR {e!r}", flush=True)
                return {"seed": s, "completed": False, "reason": repr(e)}

    results = await asyncio.gather(*[one(s) for s in seeds])
    usd = sum(u["usd"] for u in _usage_log)
    (out / "usage.json").write_text(json.dumps({"calls": len(_usage_log), "usd": usd, "rows": _usage_log}))
    print(f"completed {sum(1 for r in results if r.get('completed'))}/{len(seeds)}; litellm spend ≈ ${usd:.2f}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="0-9")
    ap.add_argument("--out", type=Path, default=Path("runs/stage2"))
    ap.add_argument("--worlds", type=Path, default=Path("runs/worlds"))
    ap.add_argument("--parallel", type=int, default=3)
    a = ap.parse_args()
    if "-" in a.seeds:
        lo, hi = a.seeds.split("-"); seeds = list(range(int(lo), int(hi) + 1))
    else:
        seeds = [int(x) for x in a.seeds.split(",")]
    asyncio.run(main(seeds, a.out, a.worlds, a.parallel))
