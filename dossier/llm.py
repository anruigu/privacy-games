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

try:
    import openai
except ImportError:  # sotopia venv may not have it
    openai = None

ROOT = Path(os.environ.get("DOSSIER_ROOT", Path(__file__).resolve().parent.parent))
CACHE_DIR = ROOT / "runs" / "cache"
SPEND_LOG = Path(os.environ.get("DOSSIER_SPEND_LOG", ROOT / "runs" / "spend.jsonl"))
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


OPENROUTER_BASE = "https://openrouter.ai/api/v1"
_OR_PRICES_PATH = ROOT / "runs" / "openrouter_prices.json"


def openrouter_prices() -> dict[str, tuple[float, float]]:
    """{model_id: ($/MTok in, $/MTok out)} fetched once from OpenRouter and cached on disk."""
    if _OR_PRICES_PATH.exists():
        return {k: tuple(v) for k, v in json.loads(_OR_PRICES_PATH.read_text()).items()}
    import urllib.request
    req = urllib.request.Request(OPENROUTER_BASE + "/models",
                                 headers={"Authorization": "Bearer " + os.environ.get("OPENROUTER_API_KEY", "")})
    data = json.load(urllib.request.urlopen(req, timeout=60))["data"]
    out = {m["id"]: (float(m["pricing"].get("prompt", 0)) * 1e6, float(m["pricing"].get("completion", 0)) * 1e6)
           for m in data if "pricing" in m}
    _OR_PRICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OR_PRICES_PATH.write_text(json.dumps(out))
    return out


def is_anthropic(model: str) -> bool:
    return model.startswith("claude-")


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

    @property
    def or_client(self):
        if getattr(self, "_or_client", None) is None:
            assert openai is not None, "pip install openai"
            self._or_client = openai.OpenAI(base_url=OPENROUTER_BASE, api_key=os.environ["OPENROUTER_API_KEY"],
                                            max_retries=6, timeout=180.0)
        return self._or_client

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
        local = model.startswith("local/")     # local adapters are retrained under the same name: never replay them
        if path.exists() and not local:
            d = json.loads(path.read_text())
            d["cached"] = True
            return d
        with self._lock:
            if self._spent >= BUDGET_USD:
                raise BudgetExceeded(f"spent ${self._spent:.2f} >= budget ${BUDGET_USD:.2f}")
        t0 = time.time()
        if is_anthropic(model):
            d = self._chat_anthropic(model, system, messages, max_tokens, effort, cache_system)
        elif model.startswith("local/"):
            d = self._chat_local(model, system, messages, max_tokens)
        else:
            d = self._chat_openrouter(model, system, messages, max_tokens)
        d.update({"model": model, "cached": False, "latency": time.time() - t0, "tag": tag})
        usd = d["usd"]
        if not local:
            tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
            tmp.write_text(json.dumps(d, ensure_ascii=False))
            tmp.replace(path)
        with self._lock:
            self._spent += usd
            with SPEND_LOG.open("a") as fh:
                fh.write(json.dumps({"t": time.time(), "model": model, "tag": tag, "usd": usd,
                                     **d["usage"]}) + "\n")
        return d

    def _chat_anthropic(self, model, system, messages, max_tokens, effort, cache_system) -> dict:
        kwargs = dict(model=model, max_tokens=max_tokens, messages=messages,
                      output_config={"effort": effort})
        if cache_system and system:
            kwargs["system"] = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        else:
            kwargs["cache_control"] = {"type": "ephemeral"}
            if system:
                kwargs["system"] = system
        resp = self.client.messages.create(**kwargs)
        text = "".join(b.text for b in resp.content if b.type == "text")
        u = resp.usage
        usage = {"input": u.input_tokens, "output": u.output_tokens,
                 "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0}
        d = {"text": text, "stop_reason": resp.stop_reason, "usage": usage, "usd": self._cost(model, usage)}
        if resp.stop_reason == "refusal":
            d["refusal"] = getattr(getattr(resp, "stop_details", None), "category", None)
        return d

    def _chat_openrouter(self, model, system, messages, max_tokens) -> dict:
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        # reasoning models burn max_tokens on hidden reasoning; ask for low effort and give headroom
        resp = self.or_client.chat.completions.create(
            model=model, messages=msgs, max_tokens=max(max_tokens, 8000),
            extra_body={"reasoning": {"effort": "low"}})
        choice = resp.choices[0]
        text = choice.message.content or ""
        extra = {}
        for fld in ("refusal", "reasoning"):
            v = getattr(choice.message, fld, None)
            if v:
                extra[fld] = str(v)[:500]
        u = resp.usage
        cached = 0
        det = getattr(u, "prompt_tokens_details", None)
        if det is not None:
            cached = getattr(det, "cached_tokens", 0) or 0
        usage = {"input": (u.prompt_tokens or 0) - cached, "output": u.completion_tokens or 0,
                 "cache_write": 0, "cache_read": cached}
        pin, pout = openrouter_prices().get(model, (10.0, 50.0))
        usd = ((usage["input"] + usage["cache_read"]) * pin + usage["output"] * pout) / 1e6
        return {"text": text, "stop_reason": choice.finish_reason, "usage": usage, "usd": usd,
                "provider": getattr(resp, "provider", None), **extra}

    def _chat_local(self, model, system, messages, max_tokens) -> dict:
        """OpenAI-compatible vLLM endpoint(s) (LOCAL_LLM_URLS, comma-separated); model 'local/<served name>'.
        Qwen3 thinking is split on </think>: visible answer -> text, trace -> reasoning. Cost 0."""
        import requests
        urls = os.environ.get("LOCAL_LLM_URLS", "http://localhost:8000").split(",")
        url = urls[int(hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest(), 16) % len(urls)]
        body = {"model": model.split("/", 1)[1], "max_tokens": max_tokens,
                "messages": ([{"role": "system", "content": system}] if system else []) + messages,
                "temperature": float(os.environ.get("LOCAL_TEMPERATURE", "0.7")), "top_p": 0.95,
                "chat_template_kwargs": {"enable_thinking": os.environ.get("LOCAL_THINKING", "1") == "1"}}
        last = None
        i0 = urls.index(url)
        for k in range(8):
            url = urls[(i0 + k) % len(urls)]        # rotate replicas on failure (one may be restarting)
            try:
                r = requests.post(url.rstrip("/") + "/v1/chat/completions", json=body, timeout=420)
                if r.status_code != 200:
                    raise RuntimeError(f"{r.status_code} {r.text[:200]}")
                j = r.json(); break
            except Exception as e:  # noqa
                last = e; time.sleep(min(2 ** k, 20))
        else:
            raise RuntimeError(f"local llm failed: {last!r}")
        ch = j["choices"][0]
        raw = ch["message"].get("content") or ""
        reasoning, text = "", raw
        if "</think>" in raw:
            reasoning, text = raw.split("</think>", 1)
            reasoning = reasoning.replace("<think>", "", 1).strip()
        elif "<think>" in raw:
            reasoning, text = raw.replace("<think>", "", 1).strip(), ""
        u = j.get("usage", {})
        usage = {"input": u.get("prompt_tokens", 0), "output": u.get("completion_tokens", 0), "cache_write": 0, "cache_read": 0}
        return {"text": text.strip(), "reasoning": reasoning, "raw": raw, "stop_reason": ch.get("finish_reason"),
                "usage": usage, "usd": 0.0}

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
