"""Select Sotopia's local JSON storage backend rooted under /shared (no Redis / RedisJSON available).

Import this module BEFORE any `sotopia.database` import. This is a runner setting, not an engine patch:
it uses Sotopia's own public LocalJSONBackend and the module-level singleton it reads.
"""
from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SOTOPIA_STORAGE_BACKEND", "local")
DB_DIR = Path(os.environ.get("DOSSIER_SOTOPIA_DB", str(Path(__file__).resolve().parents[2] / "runs" / "sotopia_db")))
DB_DIR.mkdir(parents=True, exist_ok=True)

import sotopia.database.storage_backend as _sb  # noqa: E402

# sotopia.database constructs the default backend (~/.sotopia/data) at import time; replace it with ours.
_sb._storage_backend = _sb.LocalJSONBackend(str(DB_DIR))
