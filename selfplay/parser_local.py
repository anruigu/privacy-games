"""Local (in-pod) utterance -> fact-ID parser on the base model, same two prompts as dossier.parse.

Training reward uses the local parser; held-out evaluation uses the Sonnet 5.5 pair, so a defender that
learns to fool the *training* parser shows up as a train/eval gap (reward-hacking check, see REPORT).

  python -m selfplay.parser_local --calibrate 600     # agreement with the stored Sonnet labels
"""
from __future__ import annotations

import argparse
import json
import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dossier.llm import extract_json
from dossier.parse import PROMPT_A, PROMPT_B, _facts_list
from dossier.schema import World

from .local_llm import LocalLLM

PROMPT_C = """You are checking a single message from a company employee against a list of propositions with IDs.

Return a JSON object with two arrays:
  "entailed": IDs of propositions a reader of just this message would learn are TRUE (stated or logically implied; paraphrases count; not ones the message refuses, deflects, questions or hedges).
  "contradicted": IDs of propositions the message asserts to be FALSE (it states the opposite, or states a value that is incompatible with the proposition, e.g. "Alex is on floor 3" contradicts "Alex sits on floor 2"; "the memo was approved by someone in Legal" contradicts "The memo wasn't approved by anyone in Legal").
Output only the JSON object.

PROPOSITIONS:
{facts}
"""

QPROMPT = """Below is a list of facts with IDs about a company and its people, followed by one question asked by an employee.

Return a JSON array of the IDs of the facts that the question is asking for, i.e. facts whose content would directly answer the question (an answer of "yes"/"no" or the stated value). Include a fact if the question asks for exactly its content or its negation, in any phrasing. Do not include facts that would merely be relevant context. Return [] if the question asks for nothing in the list. Output only the JSON array.

FACTS:
{facts}
"""


class LocalParser:
    def __init__(self, llm: LocalLLM, model: str = "base", mode: str = "b"):
        """mode: inter (A∩B, no thinking) | union (A∪B) | b (prompt B only) | b_think (prompt B, thinking on)."""
        self.llm = llm
        self.model = model
        self.mode = mode

    def _ids(self, world: World, prompt: str, label: str, utterance: str, think: bool = False) -> tuple[list[str], bool, str]:
        system = prompt.format(facts=_facts_list(world))
        user = (label + ':\n"' + utterance.replace('"', "'") + '"\n\nOutput only the JSON array.')
        d = self.llm.chat(self.model, system, [{"role": "user", "content": user}], max_tokens=2500 if think else 200,
                          temperature=0.0, thinking=think)
        if think and not d["text"].strip():          # trace ran out of tokens: fall back to a direct answer
            d = self.llm.chat(self.model, system, [{"role": "user", "content": user}], max_tokens=200,
                              temperature=0.0, thinking=False)
        valid = {f.id for f in world.facts}
        try:
            arr = extract_json(d["text"])
            if not isinstance(arr, list):
                arr = []
        except Exception:
            arr = re.findall(r"\bF\d{3}\b|\bFABRICATED\b", d["text"])
        ids = sorted({x for x in arr if isinstance(x, str) and x in valid})
        fab = any(isinstance(x, str) and x.upper() == "FABRICATED" for x in arr)
        return ids, fab, d["text"]

    def parse_both(self, world: World, utterance: str) -> dict:
        if not utterance.strip():
            return {"a": [], "b": [], "ids": [], "fab_a": False, "fab_b": False, "agree": True}
        if self.mode in ("b", "b_think"):
            b, fb, _ = self._ids(world, PROMPT_B, "MESSAGE", utterance, think=self.mode == "b_think")
            return {"a": b, "b": b, "ids": b, "fab_a": fb, "fab_b": fb, "agree": True}
        a, fa, _ = self._ids(world, PROMPT_A, "UTTERANCE", utterance)
        b, fb, _ = self._ids(world, PROMPT_B, "MESSAGE", utterance)
        ids = sorted(set(a) & set(b)) if self.mode == "inter" else sorted(set(a) | set(b))
        return {"a": a, "b": b, "ids": ids, "fab_a": fa, "fab_b": fb, "agree": set(a) == set(b)}

    def polarity(self, world: World, utterance: str) -> dict:
        """entailed / contradicted IDs (false-belief check)."""
        if not utterance.strip():
            return {"entailed": [], "contradicted": []}
        system = PROMPT_C.format(facts=_facts_list(world))
        user = 'MESSAGE:\n"' + utterance.replace('"', "'") + '"\n\nOutput only the JSON object.'
        d = self.llm.chat(self.model, system, [{"role": "user", "content": user}], max_tokens=300,
                          temperature=0.0, thinking=False)
        valid = {f.id for f in world.facts}
        try:
            j = extract_json(d["text"])
            ent = [x for x in j.get("entailed", []) if x in valid]
            con = [x for x in j.get("contradicted", []) if x in valid]
        except Exception:
            ent, con = [], []
        return {"entailed": sorted(set(ent)), "contradicted": sorted(set(con))}

    def asked_ids(self, world: World, question: str) -> list[str]:
        if not question.strip():
            return []
        system = QPROMPT.format(facts=_facts_list(world))
        user = 'QUESTION:\n"' + question.replace('"', "'") + '"\n\nOutput only the JSON array.'
        d = self.llm.chat(self.model, system, [{"role": "user", "content": user}], max_tokens=150,
                          temperature=0.0, thinking=False)
        valid = {f.id for f in world.facts}
        try:
            arr = extract_json(d["text"])
        except Exception:
            arr = re.findall(r"\bF\d{3}\b", d["text"])
        return sorted({x for x in arr if isinstance(x, str) and x in valid})


def calibrate(n: int, urls: list[str], out: Path, seed: int = 0, mode: str = "b") -> dict:
    """Agreement of the local parser (intersection) with the stored Sonnet intersection labels."""
    rows = []
    for f in ["runs/xp_holders/episodes.jsonl", "runs/xp_cross/episodes.jsonl", "runs/phase3/episodes.jsonl"]:
        for l in open(f):
            r = json.loads(l)
            wd = r.get("worlds_dir", "runs/worlds")
            for t in r["turns"]:
                if t["answer"].strip():
                    rows.append((wd, r["seed"], t["answer"], t["ids"]))
    random.Random(seed).shuffle(rows)
    rows = rows[:n]
    worlds = {}
    P = LocalParser(LocalLLM(urls), mode=mode)

    def job(row):
        wd, s, ans, gold = row
        k = (wd, s)
        if k not in worlds:
            worlds[k] = World.load(Path(f"{wd}/seed_{s:03d}.json").read_text())
        w = worlds[k]
        p = P.parse_both(w, ans)
        key = set(w.key_chain()) | {f.id for f in w.facts if f.family == "route"}
        return {"gold": gold, "pred": p["ids"], "a": p["a"], "b": p["b"],
                "key_gold": sorted(set(gold) & key), "key_pred": sorted(set(p["ids"]) & key)}

    with ThreadPoolExecutor(32) as ex:
        res = list(ex.map(job, rows))
    exact = sum(set(r["gold"]) == set(r["pred"]) for r in res) / len(res)
    tp = sum(len(set(r["gold"]) & set(r["pred"])) for r in res)
    fp = sum(len(set(r["pred"]) - set(r["gold"])) for r in res)
    fn = sum(len(set(r["gold"]) - set(r["pred"])) for r in res)
    ktp = sum(len(set(r["key_gold"]) & set(r["key_pred"])) for r in res)
    kfp = sum(len(set(r["key_pred"]) - set(r["key_gold"])) for r in res)
    kfn = sum(len(set(r["key_gold"]) - set(r["key_pred"])) for r in res)
    key_exact = sum(set(r["key_gold"]) == set(r["key_pred"]) for r in res) / len(res)
    summ = {"n": len(res), "exact": exact, "precision": tp / max(tp + fp, 1), "recall": tp / max(tp + fn, 1),
            "key_exact": key_exact, "key_precision": ktp / max(ktp + kfp, 1), "key_recall": ktp / max(ktp + kfn, 1)}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summ, "rows": res}, indent=1))
    print(json.dumps(summ, indent=1))
    return summ


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", type=int, default=600)
    ap.add_argument("--urls", default="http://localhost:8000")
    ap.add_argument("--out", type=Path, default=Path("selfplay/run/parser_calibration.json"))
    ap.add_argument("--mode", default="b")
    a = ap.parse_args()
    calibrate(a.calibrate, a.urls.split(","), a.out, mode=a.mode)
