"""Thin OpenAI-compatible client for the in-pod vLLM servers (round-robin over replicas).

chat() returns {"text", "reasoning", "raw", "finish_reason", "usage"}; Qwen3 thinking is split on
</think> so callers see the visible answer as text and the trace as reasoning (kept for the monitor eval).
"""
from __future__ import annotations

import itertools
import os
import threading
import time

import requests


class LocalLLM:
    def __init__(self, base_urls: list[str] | None = None, timeout: float = 600.0):
        urls = base_urls or os.environ.get("LOCAL_LLM_URLS", "http://localhost:8000").split(",")
        self.urls = [u.rstrip("/") for u in urls]
        self._rr = itertools.cycle(range(len(self.urls)))
        self._lock = threading.Lock()
        self.timeout = timeout
        self.n_calls = 0
        self.n_tokens_out = 0
        self.lora_dir: str | None = None     # if set, a 404 "model does not exist" triggers a load from lora_dir/<name>

    def _next(self) -> str:
        with self._lock:
            return self.urls[next(self._rr)]

    def chat(self, model: str, system: str, messages: list[dict], *, max_tokens: int = 1024,
             temperature: float = 0.7, top_p: float = 0.95, thinking: bool = True, seed: int | None = None,
             stop: list[str] | None = None, retries: int = 10) -> dict:
        msgs = ([{"role": "system", "content": system}] if system else []) + messages
        body = {"model": model, "messages": msgs, "max_tokens": max_tokens, "temperature": temperature,
                "top_p": top_p, "chat_template_kwargs": {"enable_thinking": thinking}}
        if seed is not None:
            body["seed"] = seed
        if stop:
            body["stop"] = stop
        last = None
        for k in range(retries):
            url = self._next()
            try:
                r = requests.post(url + "/v1/chat/completions", json=body, timeout=self.timeout)
                if r.status_code == 404 and "does not exist" in r.text and self.lora_dir and model != "base":
                    requests.post(url + "/v1/load_lora_adapter", json={"lora_name": model, "lora_path": f"{self.lora_dir}/{model}"}, timeout=300)
                    raise RuntimeError(f"adapter {model} was not loaded on {url}; loaded, retrying")
                if r.status_code != 200:
                    raise RuntimeError(f"{r.status_code} {r.text[:300]}")
                j = r.json()
                break
            except Exception as e:  # noqa
                last = e
                time.sleep(min(2 ** k, 20))
        else:
            raise RuntimeError(f"local llm failed after {retries} tries: {last!r}")
        ch = j["choices"][0]
        raw = ch["message"].get("content") or ""
        reasoning = ch["message"].get("reasoning_content") or ""
        text = raw
        if thinking:
            if "</think>" in raw:
                reasoning, text = raw.split("</think>", 1)
                reasoning = reasoning.replace("<think>", "", 1).strip()
            elif "<think>" in raw:          # truncated inside the trace
                reasoning, text = raw.replace("<think>", "", 1), ""
        u = j.get("usage", {})
        with self._lock:
            self.n_calls += 1
            self.n_tokens_out += u.get("completion_tokens", 0) or 0
        return {"text": text.strip(), "reasoning": reasoning.strip(), "raw": raw,
                "finish_reason": ch.get("finish_reason"), "usage": u}

    # ---- LoRA management (VLLM_ALLOW_RUNTIME_LORA_UPDATING=1) ----
    def load_lora(self, name: str, path: str) -> None:
        for u in self.urls:
            # replace, never keep a stale adapter of the same name (a retrained checkpoint reuses its name)
            requests.post(u + "/v1/unload_lora_adapter", json={"lora_name": name}, timeout=60)
            r = requests.post(u + "/v1/load_lora_adapter", json={"lora_name": name, "lora_path": path}, timeout=300)
            if r.status_code != 200 and "already" not in r.text:
                raise RuntimeError(f"load_lora {name} on {u}: {r.status_code} {r.text[:200]}")

    def unload_lora(self, name: str) -> None:
        for u in self.urls:
            requests.post(u + "/v1/unload_lora_adapter", json={"lora_name": name}, timeout=60)

    def models(self) -> list[str]:
        out = []
        for u in self.urls:
            try:
                out.append([m["id"] for m in requests.get(u + "/v1/models", timeout=10).json()["data"]])
            except Exception as e:  # noqa
                out.append(repr(e))
        return out

    def wait_ready(self, timeout: float = 1800) -> None:
        t0 = time.time()
        for u in self.urls:
            while True:
                try:
                    if requests.get(u + "/v1/models", timeout=5).status_code == 200:
                        break
                except Exception:
                    pass
                if time.time() - t0 > timeout:
                    raise TimeoutError(u)
                time.sleep(5)
