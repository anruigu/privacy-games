## these are just for further context if you need it. They're not the definitive research scoping.

## key reference paper

If you wanna look at games of information assymetry/partial information/optimal negotiation 
“We could also draw on information synergy from Williams and Beer: [https://arxiv.org/pdf/1004.2515](https://arxiv.org/pdf/1004.2515) (https://arxiv.org/pdf/1004.2515%5D(https://arxiv.org/pdf/1004.2515)). This is information about a target that is available jointly from multiple sources but unavailable from either alone. The clean example is XOR: either bit alone tells you nothing about the answer, but together they determine it. Several weak clues crossing a confidence threshold doesn't establish that structure



## old proposal:

Modern assistants aggregate long-horizon memories across chats, RAG fetches, documents, drafts, tools, calendars, and devices. Yet, despite these privacy-critical applications, our prior work on contextual integrity (ConfAIde [1]; AI-Liedar [8]) shows frontier models routinely misjudge what to share, adding confidential details to misaddressed emails, or inserting sensitive info in shared docs. Other works show models transmit passwords and credentials in tool calls when it seems instrumental [10]. This poses a critical open question about strategic behavior: will models trade private information for goals, deceive, or sabotage by sharing others’ data when incentives favor disclosure? Our preliminary tests indicate privacy compromises under exactly these pressures.

We will build the first longitudinal, multi-objective benchmark tracing information flows among multiple AI assistants (representing different entities) over extended, constraint-laden interactions, far beyond single-turn tests. We simulate scenarios with:
- Intersecting secrets across actors and sources.
- Longitudinal leakage across turns and sessions.
- Compositional profiles with many facts and competing objectives (e.g., maximize financial user benefit, preserve social trust, meet task constraints). We model heterogeneous trust relationships, access policies, and asymmetric incentives across organizations and roles, making disclosure choices path-dependent and history-sensitive. The benchmark records provenance, disclosure justifications, and downstream consequences to enable causal analysis.

We pair the dataset with a comprehensive evaluation suite and two attack families with concrete measurement protocols:
(1) Mutation-based fuzzing (single turn): start from safe drafts and generate variants that nudge specificity (e.g., “be precise”), swap recipients (e.g., HR), manipulate stakes and time pressure, and add cross-linguistic prompts. We score leaks via exact strings (e.g., “Wednesday 2:00 p.m.”), semantic-category violations (treatment type, prior-event linkage), and implicit cues (landmarks, role hints enabling reconstruction).
(2) Foot-in-the-door (multi-turn): implement incremental disclosure ladders, escalating from duration to weekday, category, linkage, and exact timing. We track monotonic leak curves and run both targeted extraction (specific secrets) and untargeted disclosure maximization (optimize specificity bits).

We will implement this via multi-agent simulations using our SOTOPIA-S4 framework [7] with diverse personas (negotiators, claims adjusters, HR, etc.). Parallel attackers pursue different strategies; we measure information gain and log trajectories. We then train a unified red-teamer with multi-step reinforcement learning and auto-generated process rewards, using the multi-agent traces as training data. To broaden coverage, we add style-diversity rewards and subspace projection. The corpus will contain 100,000+ trajectories spanning successful and failed privacy violations. As in our ConfAIde evaluations [1], current models underperform humans in strategic communication; our red-teamer learns from the collective intelligence of specialized agents (semantic manipulation, contextual framing, incremental disclosure).

Finally, we will train a trade-off optimizer that makes better privacy–utility decisions from observed disclosure patterns and outcomes across scenarios and user types. We will compare against baselines—SFT on human-annotated decisions, DPO for preference learning, and RLVR with verifiable compliance metrics—showing that outcome-based privacy outperforms static policy optimization. Grounded in privacy economics [9], our approach adapts to heterogeneous privacy valuations and preferences (based on  Acquisti’s field experiments [9]). Accordingly, the system will learn and adapt to individual privacy preferences across contexts.



