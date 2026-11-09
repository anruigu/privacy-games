"""Sotopia profiles + episode log -> recovered world facts, transcript, per-turn utterances.

Nothing here reads the sidecar: P1 is tested on the profiles alone. The sidecar is needed only
to rebuild predicates (i.e. a scoring-capable World), which is `load_sidecar_world`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from sotopia.database import AgentProfile, EnvironmentProfile, EpisodeLog

from ..schema import World
from .to_sotopia import LINE_RE

CODENAME_RE = re.compile(r"^dossier-seed-(\d{3})$")
SAID_RE = re.compile(r'^said: "(.*)"$', re.S)


def parse_fact_lines(text: str) -> dict[str, tuple[str, str]]:
    """'[F017] (RELEASABLE) sentence' lines -> {id: (norm, sentence)}"""
    out = {}
    for line in text.splitlines():
        m = LINE_RE.match(line.strip())
        if m:
            out[m.group(1)] = (m.group(2).lower(), m.group(3))
    return out


def recover(env: EnvironmentProfile, seeker: AgentProfile, holder: AgentProfile) -> dict:
    """Recover every schema-level quantity the round-trip test checks, from profiles only."""
    m = CODENAME_RE.match(env.codename)
    seed = int(m.group(1)) if m else None
    holder_facts = parse_fact_lines(holder.public_info)
    holder_facts.update(parse_fact_lines(holder.secret))
    seeker_facts = parse_fact_lines(seeker.public_info)
    # T: the protected 'approver_is' sentence
    approver_name = None
    for fid, (norm, sent) in holder_facts.items():
        mm = re.match(r"^The memo was approved by (.+)\.$", sent)
        if norm == "protected" and mm:
            approver_name = mm.group(1)
    pivots = sorted(re.match(r"^(.+?) recently transferred in;", s).group(1)
                    for _, (n, s) in holder_facts.items() if "recently transferred in" in s)
    return {
        "seed": seed,
        "norms": {fid: norm for fid, (norm, _) in holder_facts.items()},
        "sentences": {fid: s for fid, (_, s) in holder_facts.items()},
        "holder_fact_ids": set(holder_facts),
        "seeker_fact_ids": set(seeker_facts),
        "public_fact_ids": {fid for fid, (n, _) in holder_facts.items() if n == "public"},
        "approver_name": approver_name,
        "pivot_names": pivots,
    }


def world_view(world: World) -> dict:
    """Same quantities computed from the original World, for equality testing."""
    return {
        "seed": world.seed,
        "norms": {f.id: f.norm for f in world.facts},
        "sentences": {f.id: f.sentence for f in world.facts},
        "holder_fact_ids": {f.id for f in world.facts},
        "seeker_fact_ids": {f.id for f in world.facts if f.norm == "public"},
        "public_fact_ids": {f.id for f in world.facts if f.norm == "public"},
        "approver_name": world.emp(world.approver).name,
        "pivot_names": sorted(world.emp(p).name for p in world.pivots),
    }


def load_sidecar_world(sidecar_dir: Path, codename: str) -> World:
    return World.load((sidecar_dir / f"{codename}.world.json").read_text())


def transcript(ep: EpisodeLog) -> list[dict]:
    """Ordered agent utterances from the stored episode log only.

    EpisodeLog.messages[t] is a list of (sender, receiver, text). Agent actions have receiver
    'Environment' and text 'said: "..."' / 'left the conversation' / 'did nothing'.
    """
    turns = []
    k = 0
    for t, turn in enumerate(ep.messages):
        for sender, receiver, text in turn:
            if sender == "Environment" or receiver != "Environment":
                continue
            m = SAID_RE.match(text.strip())
            if m:
                turns.append({"k": k, "sotopia_turn": t, "speaker": sender, "action": "speak",
                              "utterance": m.group(1)})
                k += 1
            elif text.startswith("[leave]") or text.strip() == "left the conversation":
                turns.append({"k": k, "sotopia_turn": t, "speaker": sender, "action": "leave", "utterance": ""})
                k += 1
            # 'did nothing' / [none] are skipped
    return turns


def evaluator_record(ep: EpisodeLog) -> dict | None:
    """Our evaluator stores a JSON blob inside EpisodeLog.reasoning (between EXACT_LEAK_JSON markers)."""
    m = re.search(r"EXACT_LEAK_JSON_BEGIN(.*?)EXACT_LEAK_JSON_END", ep.reasoning or "", re.S)
    return json.loads(m.group(1)) if m else None


def stock_secret_score(ep: EpisodeLog) -> dict[str, float | None]:
    """Stock evaluator 'secret' score per agent, read from the reasoning text the recording wrapper wrote."""
    out: dict[str, float | None] = {"agent_1": None, "agent_2": None}
    cur = None
    for line in (ep.reasoning or "").splitlines():
        if line.startswith("Agent 1 comments"):
            cur = "agent_1"
        elif line.startswith("Agent 2 comments"):
            cur = "agent_2"
        m = re.match(r"^secret: \[score=([-\d.]+)\]", line.strip())
        if m and cur:
            out[cur] = float(m.group(1))
    return out
