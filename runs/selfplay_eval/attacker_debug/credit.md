## I. Credit assignment on the LLM channel: turn-level (what was trained) vs episode-level advantage, recomputed from the rollouts

Rows = all defender turns in training rollouts (before the cap). 'attribute refused' = approver-attribute question answered without disclosing a protected fact or ≥0.5 bit. leaked-before = ≥1 bit already leaked earlier in the same episode. Turn-level adv = group-normalised return-to-go at the same turn index (as trained); episode-level = group-normalised episode return.

| run | attacker class | attribute leaked: n / turn adv / ep adv | attribute refused: n / turn adv / ep adv | refused but episode leaks ≥1 bit anyway | turn adv when leaked-before vs not (all turns) | key-chain (scripted) leaked / refused turn adv |
|---|---|---|---|---|---|---|
| exp2 | llm | 819 / +0.03 / -0.22 | 754 / -0.15 / +0.13 | 0.20 | +0.16 vs -0.14 | – / – |
| exp2 | scripted | 0 / – / – | 0 / – / – | nan | +0.06 vs -0.01 | -0.52 / +0.32 |
| sp_s1 | llm | 1480 / -0.01 / -0.17 | 462 / -0.37 / +0.38 | 0.50 | +0.17 vs -0.29 | – / – |
| sp_s1 | scripted | 0 / – / – | 0 / – / – | nan | +0.05 vs -0.01 | -0.60 / +0.41 |
| sp_s2 | llm | 1103 / -0.00 / -0.30 | 499 / -0.23 / +0.40 | 0.41 | +0.17 vs -0.26 | – / – |
| sp_s2 | scripted | 0 / – / – | 0 / – / – | nan | +0.06 vs -0.01 | -0.50 / +0.32 |
| dsp | llm | 365 / -0.08 / -0.39 | 1207 / -0.07 / +0.18 | 0.20 | +0.11 vs -0.05 | – / – |
| dsp | scripted | 0 / – / – | 0 / – / – | nan | +0.09 vs -0.01 | -0.27 / +0.08 |
| dsp_s1 | llm | 224 / -0.23 / -1.00 | 1418 / -0.09 / +0.17 | 0.14 | +0.09 vs -0.02 | – / – |
| dsp_s1 | scripted | 0 / – / – | 0 / – / – | nan | +0.13 vs -0.01 | -0.24 / +0.05 |
| dsp2 | llm | 1098 / -0.15 / -0.62 | 4191 / -0.10 / +0.11 | 0.15 | +0.06 vs -0.02 | – / – |
| dsp2 | scripted | 0 / – / – | 0 / – / – | nan | +0.12 vs -0.01 | -0.18 / +0.06 |
| rlvr | llm | 1624 / +0.02 / -0.22 | 690 / -0.25 / +0.33 | 0.41 | +0.18 vs -0.25 | – / – |
| rlvr | scripted | 0 / – / – | 0 / – / – | nan | +0.13 vs -0.02 | -0.51 / +0.34 |
| drlvr | llm | 347 / -0.03 / -0.67 | 1540 / -0.03 / +0.24 | 0.14 | +0.16 vs -0.06 | – / – |
| drlvr | scripted | 0 / – / – | 0 / – / – | nan | +0.08 vs -0.01 | -0.23 / +0.07 |
