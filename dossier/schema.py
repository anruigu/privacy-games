"""World, Fact and predicate types for the dossier game.

Design (see problem_formulation.md §4): the seeker's hypothesis space is
Ω = T × Z where T is the approver (one of 8 directors) and Z is the vector of
latent floors of the pivot employees (|Z| = 4^n_pivots; |Ω| = 128 for 2 pivots).

Predicates are stored as small structured dicts (not callables) so a World is
JSON-serialisable and can be shipped to the Sotopia sidecar unchanged.

Knobs (2026-11-11): n_floor (joint-bits target), redundancy (extra releasable routes to the
key latent), order (length of the synergy chain), null worlds, persona diversity. Default
Knobs() reproduces the original generator exactly.
"""
from __future__ import annotations

import itertools
import json
from typing import Literal

from pydantic import BaseModel, Field

FLOORS = [1, 2, 3, 4]
TEAMS = ["Engineering", "Finance", "Legal", "Operations"]
BUILDINGS = ["A", "B"]

Norm = Literal["public", "releasable", "protected"]
Kind = Literal["direct", "relational"]
Family = Literal["public", "key", "cover", "control", "protected", "route"]

PredKind = Literal[
    "true",              # constant: fact about a variable independent of Ω
    "same_floor_as_pivot",  # floor(T) == z[pivot]
    "pivot_floor",       # z[pivot] == floor
    "not_team",          # team(T) != team
    "approver_is",       # T == emp
    "approver_floor",    # floor(T) == floor
    "approver_team",     # team(T) == team
    "pivot_same_floor",  # z[pivot] == z[pivot2]          (order-k chain links)
    "pivot_floor_eq_emp",  # z[pivot] == floor(emp), emp has a public floor (redundant routes; null analog of d1)
]

DEFAULT_SEEKER_NAME = "Jordan Reyes"
DEFAULT_SEEKER_ROLE = "a coordinator in Facilities"
DEFAULT_HOLDER_NAME = "Sam Okafor"
DEFAULT_HOLDER_ROLE = "the executive assistant to the leadership team"


class Employee(BaseModel):
    id: str            # "E0".."E9"
    name: str
    floor: int
    team: str
    building: str
    oncall: bool
    is_director: bool  # approval candidate (member of T's support)
    is_pivot: bool     # floor is latent to the seeker


class Predicate(BaseModel):
    kind: PredKind
    pivot: str | None = None
    pivot2: str | None = None
    emp: str | None = None
    floor: int | None = None
    team: str | None = None

    def mentions_target(self) -> bool:
        return self.kind in ("same_floor_as_pivot", "not_team", "approver_is", "approver_floor", "approver_team")


class Fact(BaseModel):
    id: str                 # "F017"
    predicate: Predicate
    sentence: str           # surface realisation (holder would say this)
    question: str           # seeker question form
    norm: Norm
    kind: Kind
    family: Family
    chain: int | None = None   # position in the key chain: 1 = the target-relational fact ... k = the floor fact


class Knobs(BaseModel):
    n_floor: int | None = None          # directors (incl. approver) on the approver's floor -> joint bits = 3 - log2(n_floor)
    redundancy: int = 0                 # extra releasable routes to z[X] (0, 1, 2)
    order: int = 2                      # synergy order k: number of releasable facts needed before any bit arrives
    null: Literal["none", "public", "nomemo"] = "none"
    personas: bool = False

    @property
    def is_default(self) -> bool:
        return self == Knobs()

    def tag(self) -> str:
        if self.null != "none":
            base = f"null-{self.null}"
        else:
            base = f"n{self.n_floor if self.n_floor else 'x'}_r{self.redundancy}_k{self.order}"
        return base + ("_persona" if self.personas else "")


class Omega(BaseModel):
    """One joint hypothesis: approver id + latent floor per pivot."""
    t: str
    z: dict[str, int]


class World(BaseModel):
    seed: int
    company: str
    employees: list[Employee]
    approver: str                  # employee id (the true T)
    pivots: list[str]              # employee ids (len 2 by default; order-1 for order >= 3)
    facts: list[Fact]
    cover_task: str = Field(default="")
    knobs: Knobs = Field(default_factory=Knobs)
    seeker_name: str = DEFAULT_SEEKER_NAME
    seeker_role: str = DEFAULT_SEEKER_ROLE
    holder_name: str = DEFAULT_HOLDER_NAME
    holder_role: str = DEFAULT_HOLDER_ROLE
    psi: str = "default"           # recipient-norm variant (selfplay.worlds): default | author | external

    # ---- convenience ----
    def emp(self, eid: str) -> Employee:
        return self._by_id[eid]

    @property
    def _by_id(self) -> dict[str, Employee]:
        return {e.id: e for e in self.employees}

    @property
    def directors(self) -> list[str]:
        return [e.id for e in self.employees if e.is_director]

    @property
    def true_z(self) -> dict[str, int]:
        return {p: self.emp(p).floor for p in self.pivots}

    @property
    def has_memo(self) -> bool:
        return self.knobs.null != "nomemo"

    def fact(self, fid: str) -> Fact:
        return self._facts_by_id[fid]

    @property
    def _facts_by_id(self) -> dict[str, Fact]:
        return {f.id: f for f in self.facts}

    def facts_with(self, **kw) -> list[Fact]:
        out = []
        for f in self.facts:
            if all(getattr(f, k) == v for k, v in kw.items()):
                out.append(f)
        return out

    def key_chain(self) -> list[str]:
        """Key fact ids ordered by chain position (d1 ... dk)."""
        ks = self.facts_with(family="key")
        if any(f.chain is None for f in ks):   # worlds generated before the chain field: d1 relational, d2 floor
            rank = {"same_floor_as_pivot": 1, "pivot_floor_eq_emp": 1, "pivot_same_floor": 2, "pivot_floor": 3}
            ks = sorted(ks, key=lambda f: rank[f.predicate.kind])
        else:
            ks = sorted(ks, key=lambda f: f.chain)
        return [f.id for f in ks]

    # ---- hypothesis space ----
    def omega(self) -> list[Omega]:
        states = []
        for t in self.directors:
            for zs in itertools.product(FLOORS, repeat=len(self.pivots)):
                states.append(Omega(t=t, z=dict(zip(self.pivots, zs))))
        return states

    def holds(self, pred: Predicate, w: Omega) -> bool:
        k = pred.kind
        if k == "true":
            return True
        if k == "same_floor_as_pivot":
            return self.emp(w.t).floor == w.z[pred.pivot]
        if k == "pivot_floor":
            return w.z[pred.pivot] == pred.floor
        if k == "not_team":
            return self.emp(w.t).team != pred.team
        if k == "approver_is":
            return w.t == pred.emp
        if k == "approver_floor":
            return self.emp(w.t).floor == pred.floor
        if k == "approver_team":
            return self.emp(w.t).team == pred.team
        if k == "pivot_same_floor":
            return w.z[pred.pivot] == w.z[pred.pivot2]
        if k == "pivot_floor_eq_emp":
            return w.z[pred.pivot] == self.emp(pred.emp).floor
        raise ValueError(k)

    def true_omega(self) -> Omega:
        return Omega(t=self.approver, z=self.true_z)

    def check_consistent(self) -> None:
        """Every fact must hold in the true world."""
        w = self.true_omega()
        for f in self.facts:
            assert self.holds(f.predicate, w), f"fact {f.id} false in true world: {f.sentence}"

    def dump(self) -> str:
        return self.model_dump_json(indent=1)

    @classmethod
    def load(cls, s: str) -> "World":
        return cls.model_validate_json(s)
