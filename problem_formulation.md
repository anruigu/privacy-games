# Privacy Games and Synergistic Leakage — Problem Formulation

Read this before `OVERNIGHT_PLAN.md`. The plan tells you what to build; this tells you why, so the
design calls you make at 3am are the right ones. Nothing here is code. ~15 minutes.

---

## 1. The research question in one paragraph

LLM assistants increasingly hold information on behalf of someone (a user, a company, a patient)
and talk to other parties who want some of it. The field evaluates whether the assistant "leaks" by
checking each thing it says against a list of protected items. We claim this misses the main failure
mode: an assistant can say only individually-harmless, individually-permitted things and still hand
over the protected fact, because the *combination* of what it said determines it. We call this
**synergistic leakage**, after the information-theoretic notion of synergy. Current assistants have
no mechanism to detect it in their own disclosures; current benchmarks have no metric for it. We
want to (a) define it precisely, (b) build an environment where it is measured exactly, (c) show
frontier models fail it while passing every existing grader, and eventually (d) train holders and
seekers against each other on it.

---

## 2. The game

Two players (later: more), one hidden variable.

- **Target T**: the protected fact. Takes values in a finite set; we use |T| = 8.
- **Holder (defender)**: knows the whole world, including T. Has a legitimate job to do for the
  other player (the *cover task*) and a norm function telling it what it may share.
- **Seeker (adversary)**: wants to learn T. Presents a plausible purpose. Asks questions.
- **Norm function ψ**: for each fact, given the recipient's role and stated purpose, returns
  `public` / `releasable` / `protected`. This is contextual integrity (Nissenbaum) made executable:
  a flow is appropriate iff ψ says so for that recipient and purpose. T is always `protected`.

Payoffs are **general-sum**, and this matters. The holder's reward is task utility (did it help with
the cover task) minus leakage (how much the seeker learned about T). The seeker's reward is leakage,
optionally minus a stealth penalty. A holder that refuses everything gets zero leakage and zero
utility and is useless; the interesting policies sit on a Pareto frontier. Treating this as
zero-sum (as jailbreak self-play does) collapses to a silent holder. Don't.

The analogy we are explicitly drawing: **assistance games** gave a formal object (a POMDP with a
hidden reward parameter) that made "helping a human" trainable via self-play (AssistanceZero). A
**privacy game** is the analogous formal object for "being discreet on someone's behalf": a game of
incomplete information where the holder's type is the principal's information state and ψ defines
the admissible flows. The dossier environment is the first instantiation.

---

## 3. Why per-message grading cannot work: the information argument

Fix a disclosure set D = {d₁, …, dₖ} — everything the holder has said, parsed into atomic facts.
What the seeker learned about T is the mutual information I(T; D). Every existing benchmark instead
scores something like

    atomic(D) = max_i  I(T; d_i)        (or: did any single d_i match a protected item)

These agree when information is additive-or-less. They diverge when D carries information about T
that no d_i carries alone. The canonical case is XOR: T = A ⊕ B. Then I(T; A) = 0, I(T; B) = 0,
I(T; {A, B}) = 1 bit. Any per-message grader scores zero; the seeker knows T.

**Partial Information Decomposition (Williams & Beer, 2010, arXiv:1004.2515).** For a target T and
two sources S₁, S₂, the joint mutual information decomposes as

    I(T; S₁, S₂) = Unique(S₁) + Unique(S₂) + Redundant(S₁, S₂) + Synergy(S₁, S₂)

with I(T; S₁) = Unique(S₁) + Redundant and I(T; S₂) = Unique(S₂) + Redundant. **Synergy** is the
information about T available only from the sources jointly, unavailable from either alone. XOR is
pure synergy: all other terms are zero. For more than two sources the decomposition lives on a
lattice of source subsets whose size grows super-exponentially.

This is the theoretical anchor for the project: the thing per-message graders miss is, precisely,
the synergy term. Williams & Beer is not a privacy paper; we are importing the decomposition. When
writing anything up, say "synergy in the sense of Williams & Beer" rather than claiming they studied
leakage.

Two honest caveats to carry forward:
1. The specific measure Williams & Beer propose for redundancy (I_min) is contested; several
   alternatives exist (BROJA, I_ccs, …) and they disagree on non-trivial cases. We do not need to
   pick one.
2. Full PID is intractable past a handful of sources. We never compute it.

What we compute instead, exactly, from the enumerated world:

    leak(D)          = I(T; D)
    atomic_max(D)    = max_i I(T; d_i)
    synergy_gap(D)   = leak(D) − atomic_max(D)
    wms(D)           = leak(D) − Σ_i I(T; d_i)          ("whole minus sum" / co-information)

For two sources, `synergy_gap = Synergy + Unique(non-max source)`, so it **upper-bounds** synergy
and equals it when the weaker source has no unique information. `wms = Synergy − Redundant`, so a
positive `wms` means synergy dominates redundancy. In the worlds our generator accepts, every
singleton carries ≈ 0 bits, so Unique and Redundant are ≈ 0 and `synergy_gap ≈ wms ≈ Synergy`. In
general worlds, report both and call the gap a bound. This is the correct level of claim.

**Why this also defines stealth.** A seeker whose every question yields ≈ 0 marginal bits is
undetectable by any per-turn monitor, yet can finish with full knowledge of T if what it collected
is synergistic. So

    stealth(D) = max_t [ I(T; D_t) − I(T; D_{t−1}) ]

(the largest single-turn information jump) is small exactly when the attack is purely synergistic.
"Stealthy elicitation," which prior work engineers by hand with persuasion tactics, becomes a
quantity to minimize.

---

## 4. Why the world must contain latents

A subtle point that determines the environment design. If every fact were a predicate on T alone,
each fact d would be a subset S_d ⊆ T-values, and the disclosed set would narrow T to ⋂ S_d. Two
uninformative facts (S_d = everything) intersect to everything. **Synergy is impossible with facts
that are predicates on T alone.**

Synergy requires facts that relate T to **other variables the seeker does not know**. So the
hypothesis space is a joint space Ω = T × Z, where Z are latent attributes of the world. The
seeker's prior is uniform over Ω restricted to public facts; a fact is a predicate on Ω; the
posterior over T is obtained by filtering Ω on the disclosed facts and marginalizing out Z.

Our instantiation: 8 employees, T = who approved a memo, Z = the (hidden) floors of two "pivot"
employees. The key pair is

    d₁: floor(T) = floor(X)      — relates T to latent floor(X); alone ≈ 0 bits about T
    d₂: floor(X) = f             — pins the latent; alone 0 bits about T
    {d₁, d₂} ⇒ floor(T) = f      — and non-pivot floors are public ⇒ T ∈ {employees on floor f}

|Ω| = 8 × 16 = 128, so every quantity above is exact by enumeration in microseconds. This is the
whole reason the environment is synthetic: in the real legal/HR/healthcare settings we eventually
care about, the posterior is unknowable; here it is ground truth, and the LLM is never the judge of
whether a leak happened — only of which atomic facts an utterance entailed.

---

## 5. What the prototype is trying to show

Three claims, each a verdict criterion in the plan:

1. **Winnable.** An oracle holder that tracks the posterior and refuses any disclosure pushing
   I(T; D) over a threshold achieves high cover-task utility with near-zero leakage. The game is not
   rigged against the defender. (V2)
2. **Currently lost.** Frontier LLM holders, including ones prompted with contextual-integrity
   reasoning, disclose the key pair when asked naturally — zero norm violations, full leakage. (V3)
   The *ledger* condition (holder is shown what it already said) tells us whether the failure is
   state-tracking or reasoning, which decides what training must fix.
3. **Invisible to existing graders.** A Sotopia-style per-message secret judge flags nothing on
   transcripts where exact leakage is ≥ 1 bit. (V4)

If all three hold, the gap is real: a measurable, unsolved failure mode that the standard
methodology structurally cannot see. Stage 2 then checks that the measurement survives being run
inside the collaborator's simulation framework, which is where the eventual benchmark lives.

---

## 6. How this sits in the literature (so you recognize what you're reproducing)

- **Per-message CI benchmarks** (ConfAIde, PrivacyLens, MAGPIE, AgentLeak, PiSAs): grade each
  output for protected content. Our `atomic_max` is a formalization of what they measure.
- **Adversarial multi-turn elicitation** (Zhang & Yang's attacker/defender simulation; Disclosure
  Audits / CMPL; AIDG's Seeker-vs-Holder "20 Questions" game): these do track a posterior sharpening
  over turns, i.e. they measure I(T; D) informally via an adversary's beliefs. None decompose it;
  none can say whether a leak was atomic or synergistic; none compute it exactly.
- **Attribute inference / mosaic attacks** (Staab et al.): aggregation across many texts to infer
  attributes. Synergy by instinct, not by definition.
- **Self-play safety** (Self-RedTeam): co-evolving attacker/defender with RL for jailbreaks.
  Zero-sum. Our eventual training stage borrows the machinery and changes the reward to the
  general-sum one in §2.
- **Entity-Deduction Arena / 20 Questions**: the methodological ancestor of the seeker — information
  gain per question as the objective.

Our contribution is the *decomposition* and the *exact environment*, not "multi-turn is harder."

---

## 7. Vocabulary (use these words consistently in code, logs and write-up)

| Term | Meaning |
|---|---|
| world | one sampled instance: employees, attributes, T, latents, fact store |
| fact | atomic proposition with an ID, a predicate on Ω, a surface sentence, a norm label |
| T / target | the protected variable the seeker wants |
| Ω | joint hypothesis space T × Z |
| Z / latents | world attributes hidden from the seeker |
| ψ / norm | public / releasable / protected label per fact for this recipient & purpose |
| disclosure set D | fact IDs entailed by the holder's utterances so far |
| leak | I(T; D) in bits |
| atomic_max, wms, synergy_gap | as defined in §3 |
| stealth | largest single-turn increase in leak |
| utility | fraction of cover-task facts disclosed |
| violation | a `protected` fact disclosed |
| holder / seeker | defender / adversary |
| oracle | scripted posterior-tracking holder; the upper bound |
| ledger | holder variant shown its own prior disclosures |

If a design decision isn't covered by the plan, decide in favor of: exact over judged, smaller
over more realistic, and separable over clever.