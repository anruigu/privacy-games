## C. Which question type leaks, per attacker kind (training rollouts, pooled over iterations)

P(turn leaks ≥ 0.5 bit | question label) and share of all leaked bits by label. Scripted attackers' label mix shown for comparison.

| run | its | attacker kind | label mix (frac of turns) | P(leak | label) | share of leaked bits by label |
|---|---|---|---|---|---|
| exp2 | 4 | llm@base (272 eps) | name 0.12, attribute 0.33, yes/no name 0.08, assert name 0.05, director 0.07, cover 0.33 | name 0.49, attribute 0.57, yes/no name 0.85, assert name 0.86, key-chain 0.48, pivot 0.55, director 0.73, cover 0.36 | name 0.10, attribute 0.33, yes/no name 0.13, assert name 0.09, director 0.10, cover 0.22 |
| exp2 | 4 | llm@trained (168 eps) | name 0.11, attribute 0.41, yes/no name 0.09, assert name 0.03, key-chain 0.03, director 0.07, cover 0.25 | name 0.29, attribute 0.45, yes/no name 0.79, assert name 0.86, key-chain 0.44, director 0.66, cover 0.39 | name 0.07, attribute 0.38, yes/no name 0.16, assert name 0.06, director 0.11, cover 0.19 |
| exp2 | 4 | scripted-direct (688 eps) | key-chain 0.08, pivot 0.49, director 0.34, cover 0.09 | key-chain 0.49, pivot 0.08, director 0.03, cover 0.16 | key-chain 0.36, pivot 0.37, director 0.12, cover 0.14 |
| exp2 | 4 | scripted-ladder (408 eps) | key-chain 0.08, pivot 0.48, director 0.35, cover 0.09 | key-chain 0.18, pivot 0.23, director 0.16, cover 0.29 | key-chain 0.07, pivot 0.53, director 0.27, cover 0.13 |
| sp_s1 | 4 | llm@base (376 eps) | name 0.10, attribute 0.33, yes/no name 0.09, assert name 0.07, director 0.09, cover 0.31 | name 0.65, attribute 0.75, yes/no name 0.96, assert name 0.96, key-chain 0.59, director 0.84, cover 0.53 | name 0.09, attribute 0.33, yes/no name 0.12, assert name 0.10, director 0.11, cover 0.24 |
| sp_s1 | 4 | llm@trained (232 eps) | name 0.11, attribute 0.31, yes/no name 0.08, assert name 0.09, director 0.10, cover 0.30 | name 0.70, attribute 0.76, yes/no name 0.91, assert name 0.84, key-chain 0.91, director 0.85, cover 0.48 | name 0.11, attribute 0.32, yes/no name 0.11, assert name 0.11, director 0.12, cover 0.20 |
| sp_s1 | 4 | scripted-direct (576 eps) | key-chain 0.08, pivot 0.49, director 0.34, cover 0.09 | key-chain 0.51, pivot 0.05, director 0.01, cover 0.14 | key-chain 0.48, pivot 0.32, director 0.04, cover 0.17 |
| sp_s1 | 4 | scripted-ladder (352 eps) | key-chain 0.07, pivot 0.49, director 0.35, cover 0.09 | key-chain 0.17, pivot 0.23, director 0.12, cover 0.22 | key-chain 0.06, pivot 0.60, director 0.22, cover 0.12 |
| sp_s2 | 4 | llm@base (320 eps) | name 0.10, attribute 0.32, yes/no name 0.08, assert name 0.07, director 0.08, cover 0.33 | name 0.76, attribute 0.71, yes/no name 0.93, assert name 0.93, key-chain 0.82, director 0.83, cover 0.47 | name 0.10, attribute 0.32, yes/no name 0.12, assert name 0.10, director 0.10, cover 0.23 |
| sp_s2 | 4 | llm@trained (152 eps) | name 0.11, attribute 0.37, yes/no name 0.11, assert name 0.08, key-chain 0.02, director 0.09, cover 0.22 | name 0.57, attribute 0.58, yes/no name 0.75, assert name 0.79, key-chain 0.48, director 0.74, cover 0.54 | name 0.10, attribute 0.35, yes/no name 0.13, assert name 0.11, director 0.11, cover 0.18 |
| sp_s2 | 4 | scripted-direct (680 eps) | key-chain 0.08, pivot 0.49, director 0.35, cover 0.09 | key-chain 0.49, pivot 0.05, director 0.02, cover 0.15 | key-chain 0.42, pivot 0.35, director 0.07, cover 0.16 |
| sp_s2 | 4 | scripted-ladder (384 eps) | key-chain 0.08, pivot 0.49, director 0.34, cover 0.09 | key-chain 0.18, pivot 0.23, director 0.16, cover 0.26 | key-chain 0.06, pivot 0.55, director 0.27, cover 0.12 |
| dsp | 4 | llm@base (296 eps) | name 0.07, attribute 0.32, yes/no name 0.02, assert name 0.04, director 0.05, cover 0.49 | name 0.31, attribute 0.23, yes/no name 0.69, assert name 0.87, director 0.41, cover 0.37 | name 0.06, attribute 0.20, yes/no name 0.05, assert name 0.10, director 0.06, cover 0.51 |
| dsp | 4 | llm@trained (168 eps) | name 0.05, attribute 0.38, yes/no name 0.03, assert name 0.02, director 0.05, cover 0.46 | name 0.35, attribute 0.22, yes/no name 0.46, assert name 0.64, director 0.21, cover 0.41 | name 0.05, attribute 0.24, yes/no name 0.06, assert name 0.05, director 0.04, cover 0.54 |
| dsp | 4 | scripted-direct (680 eps) | key-chain 0.08, pivot 0.49, director 0.35, cover 0.09 | key-chain 0.29, pivot 0.07, director 0.04, cover 0.12 | key-chain 0.26, pivot 0.45, director 0.14, cover 0.15 |
| dsp | 4 | scripted-ladder (392 eps) | key-chain 0.08, pivot 0.49, director 0.35, cover 0.09 | key-chain 0.14, pivot 0.20, director 0.15, cover 0.20 | key-chain 0.06, pivot 0.54, director 0.28, cover 0.11 |
| dsp_s1 | 4 | llm@base (352 eps) | name 0.09, attribute 0.36, director 0.04, cover 0.47 | name 0.09, attribute 0.13, yes/no name 0.28, pivot 0.19, director 0.22, cover 0.24 | name 0.05, attribute 0.25, director 0.06, cover 0.59 |
| dsp_s1 | 4 | llm@trained (112 eps) | name 0.07, attribute 0.34, director 0.03, cover 0.52 | name 0.29, attribute 0.13, director 0.47, cover 0.25 | name 0.08, attribute 0.19, yes/no name 0.03, pivot 0.04, director 0.08, cover 0.56 |
| dsp_s1 | 4 | scripted-direct (728 eps) | key-chain 0.08, pivot 0.49, director 0.34, cover 0.09 | key-chain 0.21, pivot 0.05, director 0.03, cover 0.09 | key-chain 0.26, pivot 0.44, director 0.14, cover 0.16 |
| dsp_s1 | 4 | scripted-ladder (344 eps) | key-chain 0.08, pivot 0.48, director 0.35, cover 0.09 | key-chain 0.09, pivot 0.12, director 0.10, cover 0.12 | key-chain 0.06, pivot 0.52, director 0.31, cover 0.11 |
| dsp2 | 6 | llm@base (288 eps) | name 0.08, attribute 0.34, yes/no name 0.03, assert name 0.03, director 0.04, cover 0.46 | name 0.20, attribute 0.16, yes/no name 0.44, assert name 0.77, director 0.44, cover 0.29 | name 0.06, attribute 0.20, yes/no name 0.05, assert name 0.09, director 0.08, cover 0.50 |
| dsp2 | 6 | llm@trained (1296 eps) | name 0.06, attribute 0.33, assert name 0.02, director 0.05, cover 0.51 | name 0.21, attribute 0.21, yes/no name 0.58, assert name 0.68, key-chain 0.29, pivot 0.22, director 0.28, cover 0.27 | name 0.05, attribute 0.26, yes/no name 0.04, assert name 0.06, director 0.06, cover 0.52 |
| dsp2 | 6 | scripted-direct (440 eps) | key-chain 0.08, pivot 0.49, director 0.35, cover 0.09 | key-chain 0.35, pivot 0.09, director 0.04, cover 0.17 | key-chain 0.24, pivot 0.44, director 0.16, cover 0.16 |
| dsp2 | 6 | scripted-ladder (280 eps) | key-chain 0.07, pivot 0.50, director 0.34, cover 0.09 | key-chain 0.06, pivot 0.09, director 0.07, cover 0.11 | key-chain 0.04, pivot 0.56, director 0.27, cover 0.13 |
| rlvr | 6 | llm@base (726 eps) | name 0.09, attribute 0.32, yes/no name 0.08, assert name 0.08, director 0.10, cover 0.32 | name 0.62, attribute 0.68, yes/no name 0.85, assert name 0.81, key-chain 0.71, pivot 0.67, director 0.75, cover 0.50 | name 0.09, attribute 0.32, yes/no name 0.11, assert name 0.10, director 0.12, cover 0.24 |
| rlvr | 6 | scripted-direct (902 eps) | key-chain 0.07, pivot 0.49, director 0.35, cover 0.09 | key-chain 0.48, pivot 0.07, director 0.04, cover 0.13 | key-chain 0.34, pivot 0.38, director 0.14, cover 0.13 |
| rlvr | 6 | scripted-ladder (610 eps) | key-chain 0.08, pivot 0.49, director 0.35, cover 0.09 | key-chain 0.25, pivot 0.26, director 0.19, cover 0.32 | key-chain 0.08, pivot 0.53, director 0.27, cover 0.12 |
| drlvr | 4 | llm@base (568 eps) | name 0.08, attribute 0.33, yes/no name 0.03, assert name 0.03, director 0.05, cover 0.46 | name 0.18, attribute 0.17, yes/no name 0.48, assert name 0.62, key-chain 0.21, pivot 0.28, director 0.37, cover 0.34 | name 0.06, attribute 0.21, yes/no name 0.05, assert name 0.08, director 0.07, cover 0.52 |
| drlvr | 4 | scripted-direct (592 eps) | key-chain 0.07, pivot 0.50, director 0.34, cover 0.09 | key-chain 0.28, pivot 0.08, director 0.04, cover 0.13 | key-chain 0.25, pivot 0.46, director 0.15, cover 0.15 |
| drlvr | 4 | scripted-ladder (376 eps) | key-chain 0.08, pivot 0.49, director 0.35, cover 0.09 | key-chain 0.14, pivot 0.16, director 0.11, cover 0.19 | key-chain 0.07, pivot 0.53, director 0.28, cover 0.12 |

## D. Does the defender close the LLM channel over iterations? P(leak | attribute question) and P(leak | name question), LLM attackers

| run | it | attacker | n attr turns | P(leak | attribute) | n name turns | P(leak | name) | n director turns | P(leak | director) | P(leak | cover) |
|---|---|---|---|---|---|---|---|---|---|
| exp2 | 0 | base | 398 | 0.67 | 149 | 0.53 | 109 | 0.84 | 0.46 |
| exp2 | 1 | base | 420 | 0.48 | 136 | 0.43 | 64 | 0.55 | 0.31 |
| exp2 | 2 | att_it01/base | 382 | 0.46 | 120 | 0.35 | 73 | 0.58 | 0.34 |
| exp2 | 3 | att_it01/base | 373 | 0.45 | 101 | 0.29 | 61 | 0.77 | 0.35 |
| sp_s1 | 0 | base | 551 | 0.72 | 211 | 0.61 | 149 | 0.85 | 0.44 |
| sp_s1 | 1 | base | 420 | 0.76 | 126 | 0.67 | 134 | 0.81 | 0.62 |
| sp_s1 | 2 | sp_s1_att_it01/base | 461 | 0.74 | 140 | 0.58 | 130 | 0.84 | 0.48 |
| sp_s1 | 3 | sp_s1_att_it01/base | 510 | 0.80 | 138 | 0.85 | 139 | 0.88 | 0.52 |
| sp_s2 | 0 | base | 257 | 0.74 | 84 | 0.60 | 68 | 0.69 | 0.44 |
| sp_s2 | 1 | base | 611 | 0.75 | 177 | 0.85 | 152 | 0.88 | 0.48 |
| sp_s2 | 2 | base/sp_s2_att_it01 | 392 | 0.59 | 132 | 0.64 | 74 | 0.80 | 0.55 |
| sp_s2 | 3 | base/sp_s2_att_it01 | 342 | 0.54 | 76 | 0.54 | 80 | 0.72 | 0.52 |
| dsp | 0 | base | 490 | 0.19 | 126 | 0.28 | 59 | 0.34 | 0.35 |
| dsp | 1 | base | 308 | 0.32 | 59 | 0.37 | 58 | 0.53 | 0.41 |
| dsp | 2 | dsp_att_it01/base | 326 | 0.26 | 41 | 0.44 | 57 | 0.23 | 0.43 |
| dsp | 3 | dsp_att_it01/base | 448 | 0.17 | 49 | 0.29 | 57 | 0.25 | 0.38 |
| dsp_s1 | 0 | base | 555 | 0.15 | 141 | 0.11 | 50 | 0.16 | 0.26 |
| dsp_s1 | 1 | base | 484 | 0.12 | 135 | 0.08 | 46 | 0.26 | 0.18 |
| dsp_s1 | 2 | base/dsp_s1_att_it01 | 308 | 0.11 | 70 | 0.20 | 56 | 0.21 | 0.24 |
| dsp_s1 | 3 | dsp_s1_att_it01/base | 295 | 0.14 | 51 | 0.24 | 28 | 0.61 | 0.27 |
| dsp2 | 0 | base | 992 | 0.16 | 238 | 0.20 | 129 | 0.44 | 0.29 |
| dsp2 | 1 | dsp2_att_it00 | 760 | 0.17 | 174 | 0.13 | 125 | 0.24 | 0.24 |
| dsp2 | 2 | dsp2_att_it01 | 880 | 0.19 | 126 | 0.28 | 117 | 0.26 | 0.34 |
| dsp2 | 3 | dsp2_att_it02 | 991 | 0.15 | 131 | 0.21 | 81 | 0.33 | 0.25 |
| dsp2 | 4 | dsp2_att_it03 | 675 | 0.25 | 159 | 0.18 | 131 | 0.34 | 0.27 |
| dsp2 | 5 | dsp2_att_it04 | 991 | 0.30 | 181 | 0.27 | 180 | 0.26 | 0.27 |
| rlvr | 0 | base | 461 | 0.72 | 155 | 0.68 | 130 | 0.82 | 0.59 |
| rlvr | 1 | base | 305 | 0.70 | 94 | 0.76 | 95 | 0.71 | 0.45 |
| rlvr | 2 | base | 442 | 0.72 | 133 | 0.56 | 159 | 0.82 | 0.45 |
| rlvr | 3 | base | 373 | 0.56 | 107 | 0.53 | 119 | 0.66 | 0.59 |
| rlvr | 4 | base | 379 | 0.70 | 87 | 0.68 | 121 | 0.61 | 0.47 |
| rlvr | 5 | base | 354 | 0.64 | 61 | 0.44 | 72 | 0.90 | 0.44 |
| drlvr | 0 | base | 546 | 0.18 | 128 | 0.27 | 49 | 0.39 | 0.35 |
| drlvr | 1 | base | 532 | 0.21 | 130 | 0.22 | 111 | 0.44 | 0.34 |
| drlvr | 2 | base | 417 | 0.20 | 99 | 0.13 | 76 | 0.30 | 0.38 |
| drlvr | 3 | base | 392 | 0.07 | 105 | 0.09 | 50 | 0.32 | 0.27 |

## E. Within-group variance of r_def explained by what the ATTACKER asked (LLM-attacker groups)

Within each (world, attacker kind) group of 8, regress r_def on the episode's question counts per label (group-demeaned OLS). R² = share of the defender's advantage variance that is predictable from the attacker's question mix alone.

| run | attacker kind | groups | eps | R² (attacker question mix) | R² (asked ≥1 attribute q) |
|---|---|---|---|---|---|
| exp2 | llm@base | 34 | 272 | 0.22 | 0.06 |
| exp2 | llm@trained | 21 | 168 | 0.14 | 0.07 |
| sp_s1 | llm@base | 47 | 376 | 0.07 | 0.02 |
| sp_s1 | llm@trained | 29 | 232 | 0.25 | 0.21 |
| sp_s2 | llm@base | 40 | 320 | 0.21 | 0.11 |
| sp_s2 | llm@trained | 19 | 152 | 0.07 | 0.01 |
| dsp | llm@base | 37 | 296 | 0.02 | 0.00 |
| dsp | llm@trained | 21 | 168 | 0.05 | 0.02 |
| dsp_s1 | llm@base | 44 | 352 | 0.02 | 0.01 |
| dsp_s1 | llm@trained | 14 | 112 | 0.10 | 0.01 |
| dsp2 | llm@base | 36 | 288 | 0.02 | 0.00 |
| dsp2 | llm@trained | 162 | 1296 | 0.01 | 0.01 |
| rlvr | llm@base | 92 | 726 | 0.15 | 0.07 |
| drlvr | llm@base | 71 | 568 | 0.03 | 0.00 |
