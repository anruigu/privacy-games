"""Quick throughput probe: N concurrent chat requests against one server."""
import sys, time, json, requests
from concurrent.futures import ThreadPoolExecutor
url, n, mt = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
body = {"model": "base", "messages": [{"role": "user", "content": "Write a 400-word story about a lighthouse keeper."}],
        "max_tokens": mt, "temperature": 0.7, "chat_template_kwargs": {"enable_thinking": False}}
def one(_):
    r = requests.post(url + "/v1/chat/completions", json=body, timeout=600).json()
    return r["usage"]["completion_tokens"]
t0 = time.time()
with ThreadPoolExecutor(n) as ex:
    toks = list(ex.map(one, range(n)))
dt = time.time() - t0
print(f"{url} n={n} max_tokens={mt}: {sum(toks)} tokens in {dt:.1f}s = {sum(toks)/dt:.0f} tok/s; per-seq {sum(toks)/n/dt:.1f} tok/s")
