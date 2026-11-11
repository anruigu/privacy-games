"""Print the per-iteration table of a self-play run: python -m selfplay.status selfplay/run/exp1"""
import json, sys
from pathlib import Path
d = Path(sys.argv[1])
rows = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip()] if (d / "metrics.jsonl").exists() else []
print(f"{'it':>3} {'r_def':>6} {'leak1':>6} {'util':>5} {'empty':>5} {'fab':>5} | {'probe_leak1':>11} {'probe_util':>10} | {'vs_att':>6} {'vs_dir':>6} {'vs_lad':>6} {'askd1':>5} {'guess':>5} | {'kl':>7} {'n_def':>5} {'n_att':>5} {'min':>4}")
for r in rows:
    t, p, ba = r["train"], r["probe"], r["train"]["by_attacker"]
    att = next((v for k, v in ba.items() if k.startswith("llm@") and k != "llm@base"), None) or ba.get("llm@base", {})
    print(f"{r['it']:>3} {t['r_def']:>6.3f} {t['leak1']:>6.2f} {t['utility']:>5.2f} {t['empty']:>5.2f} {t['fab']:>5.2f} | "
          f"{p['leak1']:>11.2f} {p['utility']:>10.2f} | {att.get('leak1', float('nan')):>6.2f} "
          f"{ba.get('scripted-direct', {}).get('leak1', float('nan')):>6.2f} {ba.get('scripted-ladder', {}).get('leak1', float('nan')):>6.2f} "
          f"{att.get('asked_d1', float('nan')):>5.2f} {(att.get('correct') if att.get('correct') is not None else float('nan')):>5.2f} | "
          f"{r['train_def']['kl']:>7.4f} {r['n_def_samples']:>5} {r['n_att_samples']:>5} {r['t_total'] / 60:>4.0f}")
