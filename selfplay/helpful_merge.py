"""Add helpfulness rows for new checkpoint tags without re-running the existing ones: runs the null-world grids for the
given tags, computes their rows, and merges them (by tag) into runs/selfplay_eval/helpfulness.{json,md}.

  LOCAL_LLM_URLS=... python -m selfplay.helpful_merge --tags rlvr_it01,drlvr_it03 --run-null
"""
import argparse, json
from . import helpful

ap = argparse.ArgumentParser(); ap.add_argument("--tags", required=True); ap.add_argument("--run-null", action="store_true"); ap.add_argument("--workers", type=int, default=8)
a = ap.parse_args()
questions = helpful.load_questions_all()
tags = a.tags.split(",")
if a.run_null:
    for t in tags:
        helpful.run_null(t, a.workers)
new = {t: helpful.checkpoint_row(t, questions) for t in tags}
rows = json.load(open(helpful.OUT / "helpfulness.json"))
rows = [r for r in rows if r["tag"] not in new] + list(new.values())
(helpful.OUT / "helpfulness.json").write_text(json.dumps(rows, indent=1))
md = helpful.table(rows)
(helpful.OUT / "helpfulness.md").write_text(md + "\n")
print(md)
