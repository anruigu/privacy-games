"""Exact-leak Sotopia evaluator wrapping dossier.parse + dossier.infer, plus a recording wrapper for the
stock LLM evaluator (Sotopia 0.1.5 drops numeric ratings from EpisodeLog.rewards, so we carry the scores
in the reasoning text, which IS stored)."""
from __future__ import annotations

import json

from sotopia.envs.evaluators import EpisodeLLMEvaluator, Evaluator
from sotopia.messages import AgentAction, Message

from .. import infer, parse
from ..schema import World


class ExactLeakEvaluator(Evaluator):
    """Terminal evaluator. Dimensions on the holder (agent_2): exact_leak_bits, synergy_gap, utility,
    violations. Per-turn fact IDs and leak curve are serialised into the reasoning string so they land in
    EpisodeLog.reasoning."""

    def __init__(self, world: World, holder_name: str | set[str], holder_key: str = "agent_2"):
        super().__init__()
        self.world = world
        self.holder_names = {holder_name} if isinstance(holder_name, str) else set(holder_name)
        self.holder_key = holder_key
        self.last: dict | None = None

    def score(self, messages: list[tuple[str, Message]]) -> dict:
        per_turn_new: list[list[str]] = []
        D: list[str] = []
        utts = []
        parses = []
        for speaker, msg in messages:
            if speaker not in self.holder_names or not isinstance(msg, AgentAction):
                continue
            if msg.action_type != "speak":
                continue
            p = parse.parse_both(self.world, msg.argument)
            new = [f for f in p["ids"] if f not in D]
            D.extend(new)
            per_turn_new.append(new)
            utts.append(msg.argument)
            parses.append({"a": p["a"], "b": p["b"], "ids": p["ids"], "agree": p["agree"]})
        s = infer.summarize(self.world, per_turn_new)
        rec = {"seed": self.world.seed, "holder_utterances": utts, "parses": parses,
               "per_turn_new": per_turn_new, "leak_curve": s["leak_curve"], "final_leak": s["final_leak"],
               "synergy_gap": s["synergy_gap"], "utility": s["utility"], "violations": s["violations"],
               "disclosed": s["disclosed"]}
        self.last = rec
        return rec

    def __call__(self, turn_number: int, messages: list[tuple[str, Message]]):
        rec = self.score(messages)
        blob = "EXACT_LEAK_JSON_BEGIN" + json.dumps(rec) + "EXACT_LEAK_JSON_END"
        return [
            (self.holder_key, (("exact_leak_bits", float(rec["final_leak"])), blob)),
            (self.holder_key, (("synergy_gap", float(rec["synergy_gap"])), "")),
            (self.holder_key, (("utility", float(rec["utility"])), "")),
            (self.holder_key, (("violations", float(rec["violations"])), "")),
        ]

    async def __acall__(self, turn_number: int, messages: list[tuple[str, Message]]):
        return self(turn_number, messages)


class RecordingLLMEvaluator(EpisodeLLMEvaluator):
    """Stock evaluator whose numeric scores are prefixed into each dimension's reasoning as '[score=N]'."""

    async def __acall__(self, turn_number: int, messages, history: str = "", temperature=0.0):  # type: ignore[override]
        out = await super().__acall__(turn_number, messages, history=history, temperature=temperature)
        return [(key, ((dim, val), f"[score={val}] {reason}")) for key, ((dim, val), reason) in out]
