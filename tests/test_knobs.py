"""Knob worlds: exact information guarantees for every arm (no LLM calls)."""
import itertools
import json
import math
from pathlib import Path

import pytest

from dossier import generate, infer
from dossier.generate import EPS
from dossier.schema import Knobs, World

W = Path(__file__).resolve().parent.parent / "runs" / "worlds_knobs"


def _worlds(arm):
    return [World.load(p.read_text()) for p in sorted((W / arm).glob("seed_*.json"))]


def test_default_knobs_reproduce_original_worlds():
    for s in range(0, 50, 7):
        w, _, _ = generate.generate(s)
        old = World.load((W.parent / "worlds" / f"seed_{s:03d}.json").read_text())
        assert [f.sentence for f in w.facts] == [f.sentence for f in old.facts]
        assert w.employees == old.employees


@pytest.mark.parametrize("arm,n", [("n1_r0_k2", 1), ("n2_r0_k2", 2), ("n4_r0_k2", 4)])
def test_bits_target(arm, n):
    for w in _worlds(arm):
        d1, d2 = generate.key_pair(w)
        assert infer.leak(w, [d1]) == pytest.approx(0.0, abs=1e-9)
        assert infer.leak(w, [d2]) == pytest.approx(0.0, abs=1e-9)
        assert infer.leak(w, [d1, d2]) == pytest.approx(3 - math.log2(n), abs=1e-9)
        f = w.emp(w.approver).floor
        assert sum(1 for d in w.directors if w.emp(d).floor == f) == n


@pytest.mark.parametrize("arm,r", [("n2_r1_k2", 1), ("n2_r2_k2", 2)])
def test_redundant_routes(arm, r):
    for w in _worlds(arm):
        d1, d2 = generate.key_pair(w)
        routes = [f.id for f in w.facts_with(family="route")]
        cover = [f.id for f in w.facts_with(family="cover")]
        assert len(routes) == r
        for rt in routes:
            assert infer.leak(w, [rt]) == pytest.approx(0.0, abs=1e-9)
            assert infer.leak(w, [d1, rt] + cover) == pytest.approx(infer.leak(w, [d1, d2]), abs=1e-9)
        assert infer.leak(w, routes + cover) == pytest.approx(0.0, abs=1e-9)          # routes without d1: nothing
        assert infer.leak(w, [d1, d2] + routes) == pytest.approx(infer.leak(w, [d1, d2]), abs=1e-9)  # redundant given d2
        assert infer.pid2(w, d1, d2)["redundant"] == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("arm,k", [("n2_r0_k3", 3), ("n2_r0_k4", 4)])
def test_order_k_chain(arm, k):
    for w in _worlds(arm):
        chain = w.key_chain()
        assert len(chain) == k
        for m in range(1, k):
            for sub in itertools.combinations(chain, m):
                assert infer.leak(w, list(sub)) <= 1e-9
        assert infer.leak(w, chain) == pytest.approx(2.0, abs=1e-9)
        cover = [f.id for f in w.facts_with(family="cover")]
        assert infer.leak(w, cover + chain[1:]) <= 1e-9      # everything except d1, plus all cover: nothing


def test_null_public():
    for w in _worlds("null-public"):
        chain = w.key_chain()
        assert infer.prior_bits(w) == pytest.approx(1.0, abs=1e-9)   # floor public, 2 directors on it
        assert infer.leak(w, chain) <= 1e-9
        rel = [f.id for f in w.facts if f.norm == "releasable"]
        ctrl = [f.id for f in w.facts_with(family="control")]
        assert infer.leak(w, [f for f in rel if f not in ctrl]) <= 1e-9
        assert not any(f.predicate.kind == "approver_floor" for f in w.facts_with(norm="protected"))


def test_null_nomemo():
    for w in _worlds("null-nomemo"):
        assert not w.facts_with(norm="protected")
        assert not any(f.predicate.mentions_target() for f in w.facts)
        assert not any("memo" in f.sentence.lower() for f in w.facts)
        rel = [f.id for f in w.facts if f.norm == "releasable"]
        assert infer.leak(w, rel) <= 1e-9


def test_null_and_persona_arms_are_paired_with_n2():
    base = {w.seed: w for w in _worlds("n2_r0_k2")}
    for arm in ("null-public", "null-nomemo", "n2_r0_k2_persona"):
        for w in _worlds(arm):
            b = base[w.seed]
            assert [(e.name, e.floor, e.team, e.building) for e in w.employees] == \
                   [(e.name, e.floor, e.team, e.building) for e in b.employees]
            assert w.approver == b.approver and w.pivots == b.pivots


def test_persona_arm_varies_personas():
    ws = _worlds("n2_r0_k2_persona")
    assert len({w.seeker_name for w in ws}) >= 3
    assert len({w.holder_name for w in ws}) >= 2
    assert len({w.cover_task for w in ws}) >= 2
    from dossier.render import holder_system_prompt, seeker_briefing
    for w in ws[:3]:
        assert w.holder_name in holder_system_prompt(w) and w.seeker_name in seeker_briefing(w)


def test_scripted_plans_cover_chain_and_routes():
    from dossier.agents.seeker import make_seeker
    for arm in ("n2_r2_k2", "n2_r0_k4", "null-nomemo"):
        for w in _worlds(arm)[:3]:
            for kind in ("scripted-direct", "scripted-ladder"):
                ids = [fid for fid, _ in make_seeker(kind, w).plan]
                assert set(w.key_chain()) <= set(ids)
                assert {f.id for f in w.facts_with(family="route")} <= set(ids)
                assert len(ids) == len(set(ids))
