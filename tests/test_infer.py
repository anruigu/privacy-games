import math

import pytest

from dossier import generate, infer
from dossier.generate import EPS, key_pair

SEEDS = list(range(50))


@pytest.fixture(scope="module")
def worlds():
    out = {}
    for s in SEEDS:
        w, tries, _ = generate.generate(s)
        assert w is not None, f"seed {s} not accepted"
        out[s] = w
    return out


def test_uniform_prior(worlds):
    for w in worlds.values():
        assert infer.leak(w, []) == pytest.approx(0.0, abs=1e-12)
        p = infer.posterior(w, [])
        assert all(abs(v - 1 / 8) < 1e-12 for v in p.values())


def test_protected_approver_full_bits(worlds):
    for w in worlds.values():
        fid = next(f.id for f in w.facts if f.predicate.kind == "approver_is")
        assert infer.leak(w, [fid]) == pytest.approx(math.log2(8), abs=1e-9)


def test_parity_pair(worlds):
    for w in worlds.values():
        d1, d2 = key_pair(w)
        assert infer.leak(w, [d1]) <= EPS
        assert infer.leak(w, [d2]) <= EPS
        assert infer.leak(w, [d1, d2]) >= 1.0
        # in this generator both singletons are exactly 0
        assert infer.leak(w, [d1]) == pytest.approx(0.0, abs=1e-9)
        assert infer.leak(w, [d2]) == pytest.approx(0.0, abs=1e-9)


def test_monotone(worlds):
    import random
    for w in list(worlds.values())[:10]:
        ids = [f.id for f in w.facts]
        rng = random.Random(w.seed)
        D = []
        prev = 0.0
        for fid in rng.sample(ids, len(ids)):
            D.append(fid)
            cur = infer.leak(w, D)
            assert cur >= prev - 1e-9
            prev = cur


def test_synergy_gap_nonneg_and_key_pair(worlds):
    for w in worlds.values():
        d1, d2 = key_pair(w)
        assert infer.synergy_gap(w, [d1, d2]) >= 0
        assert infer.synergy_gap(w, [d1, d2]) == pytest.approx(infer.leak(w, [d1, d2]), abs=1e-9)
        assert infer.wms(w, [d1, d2]) == pytest.approx(infer.leak(w, [d1, d2]), abs=1e-9)
        ids = [f.id for f in w.facts]
        assert infer.synergy_gap(w, ids) >= -1e-9


def test_cover_zero_bits(worlds):
    for w in worlds.values():
        cover = [f.id for f in w.facts if f.family == "cover"]
        assert len(cover) == 8
        for c in cover:
            assert infer.leak(w, [c]) == pytest.approx(0.0, abs=1e-9)
        assert infer.leak(w, cover) == pytest.approx(0.0, abs=1e-9)


def test_control_is_atomic(worlds):
    for w in worlds.values():
        c = next(f.id for f in w.facts if f.family == "control")
        assert infer.leak(w, [c]) > EPS


def test_stealth():
    assert infer.stealth([0, 0, 0, 2.0, 2.0]) == 2.0
    assert infer.stealth([0.5, 1.0, 1.2]) == 0.5


def test_roundtrip_json(worlds):
    from dossier.schema import World
    w = worlds[0]
    w2 = World.load(w.dump())
    assert w2 == w
