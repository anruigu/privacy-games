"""Thin cached Anthropic adapter with per-call spend logging and a hard budget.

Every call is cached on disk keyed by sha256(model, system, messages, max_tokens, effort).
Rerunning is free. Spend is appended to runs/spend.jsonl; new calls stop at BUDGET_USD.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

import anthropic

ROOT = Path(os.environ.get("DOSSIER_ROOT", Path(__file__).resolve().parent.parent))
CACHE_DIR = ROOT / "runs" / "cache"
SPEND_LOG = ROOT / "runs" / "spend.jsonl"
BUDGET_USD = float(os.environ.get("BUDGET_USD", "25"))

# $/MTok: input, output, cache_write, cache_read  (skill table, 2026-10-06)
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.125, 0.01),
}

MODELS = {
    "holder": os.environ.get("HOLDER_MODEL", "claude-opus-5-5"),
    "seeker": os.environ.get("SEEKER_MODEL", "claude-opus-5-5"),
    "judge": os.environ.get("JUDGE_MODEL", "claude-sonnet-5-5"),
    "parser_a": os.environ.get("PARSER_A_MODEL", "claude-sonnet-5-5"),
    "parser_b": os.environ.get("PARSER_B_MODEL", "claude-sonnet-5-5"),
}


class BudgetExceeded(RuntimeError):
    pass


class LLM:
    def __init__(self):
        self._client = None
        self._lock = threading.Lock()
        self._spent = self._load_spent()
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def client(self):
        if self._client is None:
            self._client = anthropic.Anthropic(max_retries=6, timeout=120.0)
        return self._client

    @staticmethod
    def _load_spent() -> float:
        if not SPEND_LOG.exists():
            return 0.0
        total = 0.0
        for line in SPEND_LOG.read_text().splitlines():
            try:
                total += json.loads(line)["usd"]
            except Exception:
                pass
        return total

    @property
    def spent(self) -> float:
        return self._spent

    @staticmethod
    def _key(model, system, messages, max_tokens, effort) -> str:
        blob = json.dumps({"m": model, "s": system, "msgs": messages, "mt": max_tokens, "e": effort},
                          sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode()).hexdigest()

    def chat(self, model: str, system: str, messages: list[dict], *, max_tokens: int = 4000,
             effort: str = "low", tag: str = "", cache_system: bool = False) -> dict:
        """Returns {"text", "stop_reason", "usage", "cached", "usd"}."""
        key = self._key(model, system, messages, max_tokens, effort)
        path = CACHE_DIR / f"{key}.json"
        if path.exists():
            d = json.loads(path.read_text())
            d["cached"] = True
            return d
        with self._lock:
            if self._spent >= BUDGET_USD:
                raise BudgetExceeded(f"spent ${self._spent:.2f} >= budget ${BUDGET_USD:.2f}")
        t0 = time.time()
        kwargs = dict(model=model, max_tokens=max_tokens, messages=messages,
                      output_config={"effort": effort})
        if cache_system and system:
            # explicit breakpoint on the (stable) system block; user turn varies per call
            kwargs["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        else:
            kwargs["cache_control"] = {"type": "ephemeral"}  # auto-cache the growing prefix
            if system:
                kwargs["system"] = system
        resp = self.client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if b.type == "text")
        u = resp.usage
        usage = {
            "input": u.input_tokens, "output": u.output_tokens,
            "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
        }
        usd = self._cost(model, usage)
        d = {"text": text, "stop_reason": resp.stop_reason, "usage": usage, "usd": usd,
             "model": model, "cached": False, "latency": time.time() - t0, "tag": tag}
        if resp.stop_reason == "refusal":
            d["refusal"] = getattr(getattr(resp, "stop_details", None), "category", None)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False))
        tmp.replace(path)
        with self._lock:
            self._spent += usd
            with SPEND_LOG.open("a") as fh:
                fh.write(json.dumps({"t": time.time(), "model": model, "tag": tag, "usd": usd,
                                     **usage}) + "\n")
        return d

    @staticmethod
    def _cost(model: str, usage: dict) -> float:
        pin, pout, pcw, pcr = PRICES.get(model, (10.0, 50.0, 12.5, 1.0))
        return (usage["input"] * pin + usage["output"] * pout + usage["cache_write"] * pcw
                + usage["cache_read"] * pcr) / 1e6


_singleton: LLM | None = None


def get_llm() -> LLM:
    global _singleton
    if _singleton is None:
        _singleton = LLM()
    return _singleton


def extract_json(text: str):
    """Best-effort: find the first JSON array/object in text."""
    import re
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1).strip()
    for opener, closer in (("[", "]"), ("{", "}")):
        i = text.find(opener)
        j = text.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"no JSON found in: {text[:200]!r}")
