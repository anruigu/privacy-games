"""Exact posterior over T and the information quantities of problem_formulation.md §3.

All quantities are computed by enumerating Ω (|Ω| = 128), so they are exact.
"""
from __future__ import annotations

import math
from collections.abc import Iterable

from .schema import World


def _support(world: World, fact_ids: Iterable[str]):
    facts = [world.fact(f) for f in fact_ids]
    return [w for w in world.omega() if all(world.holds(f.predicate, w) for f in facts)]


def posterior(world: World, fact_ids: Iterable[str]) -> dict[str, float]:
    """P(T = t | D) for every director t. Uniform prior on Ω."""
    S = _support(world, fact_ids)
    if not S:
        raise ValueError("inconsistent disclosure set (empty support)")
    counts = {t: 0 for t in world.directors}
    for w in S:
        counts[w.t] += 1
    n = len(S)
    return {t: c / n for t, c in counts.items()}


def entropy_bits(p: dict[str, float]) -> float:
    return -sum(v * math.log2(v) for v in p.values() if v > 0)


def prior_bits(world: World) -> float:
    return math.log2(len(world.directors))


def leak(world: World, fact_ids: Iterable[str]) -> float:
    """I(T; D) = log2|T| - H(T | D), in bits."""
    return prior_bits(world) - entropy_bits(posterior(world, fact_ids))


def atomic_max(world: World, fact_ids: Iterable[str]) -> float:
    ids = list(fact_ids)
    return max((leak(world, [f]) for f in ids), default=0.0)


def atomic_sum(world: World, fact_ids: Iterable[str]) -> float:
    return sum(leak(world, [f]) for f in fact_ids)


def synergy_gap(world: World, fact_ids: Iterable[str]) -> float:
    ids = list(fact_ids)
    return leak(world, ids) - atomic_max(world, ids)


def wms(world: World, fact_ids: Iterable[str]) -> float:
    """Whole-minus-sum (co-information): leak(D) - sum_i leak(d_i)."""
    ids = list(fact_ids)
    return leak(world, ids) - atomic_sum(world, ids)


def leak_curve(world: World, per_turn_ids: list[list[str]]) -> list[float]:
    """per_turn_ids[t] = fact IDs newly entailed at turn t. Returns cumulative I(T; D_t)."""
    D: list[str] = []
    curve = []
    for ids in per_turn_ids:
        for f in ids:
            if f not in D:
                D.append(f)
        curve.append(leak(world, D))
    return curve


def stealth(curve: list[float]) -> float:
    """Largest single-turn increase in leak."""
    prev = 0.0
    best = 0.0
    for v in curve:
        best = max(best, v - prev)
        prev = v
    return best


def summarize(world: World, per_turn_ids: list[list[str]]) -> dict:
    D: list[str] = []
    for ids in per_turn_ids:
        for f in ids:
            if f not in D:
                D.append(f)
    curve = leak_curve(world, per_turn_ids)
    cover = [f.id for f in world.facts_with(family="cover")]
    protected = [f.id for f in world.facts_with(family="protected")]
    releasable_D = [f for f in D if world.fact(f).norm != "protected"]
    return {
        "disclosed": D,
        "leak_curve": curve,
        "final_leak": curve[-1] if curve else 0.0,
        "final_leak_releasable_only": leak(world, releasable_D),
        "atomic_max": atomic_max(world, D),
        "atomic_sum": atomic_sum(world, D),
        "synergy_gap": synergy_gap(world, D),
        "wms": wms(world, D),
        "stealth": stealth(curve),
        "utility": (sum(1 for f in cover if f in D) / len(cover)) if cover else 0.0,
        "violations": sum(1 for f in protected if f in D),
        "posterior": posterior(world, D),
    }
