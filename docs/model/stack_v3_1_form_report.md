# v3.1 + form-anchored stacker: side-by-side comparison

- generated: 2026-10-23T15:07:36
- script: `venv/Scripts/python.exe -m src.model.stack_form` (scheme in its docstring)
- harness: src/model/validation.walk_forward, monthly blocks, train strictly before the block
- **production is NOT switched** (payload.py still serves logistic_v2 per gender).

## 0. Stacker and walk-forward scheme

`p_final = sigmoid(b0 + b1*logit(p_v3.1) + b2*form_gap_tourn + b3*form_gap_last5 + b4*is_female)`, logistic regression, C=1.0. A missing form gap counts as 0.

1. Level 1: v3.1 runs through the harness once; each match's p_v3.1 comes from a model trained only on matches before its month.
2. Level 2: for month M the stacker is fit only on level-1 predictions and results of matches before the first day of M, then applied to month M's level-1 predictions.
3. Cold start: under 200 earlier level-1 rows, p_v3.1 passes through unchanged. In the common set that is 209 matches (0 WBBL).

Common set (all predictors score): **5039** matches (3924 men, 1115 women, WBBL 80), 2023-05-01 .. 2026-10-21.

## 1. Adoption bar verdict: **FAIL**

| check | measure | value [95% block-bootstrap CI] | result |
|---|---|---|---|
| WBBL: match or beat form | log_loss stack - form (n=80) | +0.0192 [-0.0545, +0.0464] | **FAIL** |
| WBBL: match or beat form | brier stack - form | +0.0097 [-0.0261, +0.0228] | **FAIL** |
| Men: no degradation beyond noise | log_loss stack - v2 (n=3924) | -0.0064 [-0.0100, -0.0032] | pass |
| Men: no degradation beyond noise | brier stack - v2 | -0.0029 [-0.0045, -0.0015] | pass |
| Women: no regression vs v3.1 | log_loss stack - v3.1 (n=1115) | +0.0012 [-0.0058, +0.0089] | **FAIL** |
| Women: no regression vs v3.1 | brier stack - v3.1 | +0.0004 [-0.0029, +0.0041] | **FAIL** |

Negative deltas mean the stacked model is better. WBBL and women are judged on the point estimate; men fail only if the whole interval is above zero.

Context: men stack - v3.1 log_loss -0.0046 [-0.0084, -0.0014]; women stack - form log_loss -0.0052 [-0.0173, +0.0081]; WBBL stack - v3.1 log_loss -0.0107 [-0.0450, +0.0037].

## 2. Overall and per gender (common set)

### Overall

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 5039 | 0.5648 | 0.6782 | 0.2425 | 0.5392 |
| v3.1 pooled | 5039 | 0.5696 | 0.6749 | 0.2410 | 0.5392 |
| v3.1 + form stacker (CANDIDATE) | 5039 | 0.5779 | 0.6715 | 0.2394 | 0.5392 |
| form_favourite (bar) | 5039 | 0.5862 | 0.6807 | 0.2434 | 0.5392 |

### Men

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 3924 | 0.5489 | 0.6848 | 0.2457 | 0.5293 |
| v3.1 pooled | 3924 | 0.5548 | 0.6831 | 0.2449 | 0.5293 |
| v3.1 + form stacker (CANDIDATE) | 3924 | 0.5650 | 0.6784 | 0.2427 | 0.5293 |
| form_favourite (bar) | 3924 | 0.5726 | 0.6888 | 0.2473 | 0.5293 |

### Women

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 1115 | 0.6206 | 0.6548 | 0.2314 | 0.5740 |
| v3.1 pooled | 1115 | 0.6215 | 0.6459 | 0.2273 | 0.5740 |
| v3.1 + form stacker (CANDIDATE) | 1115 | 0.6233 | 0.6471 | 0.2277 | 0.5740 |
| form_favourite (bar) | 1115 | 0.6341 | 0.6522 | 0.2298 | 0.5740 |

## 3. Per league (common set; n >= 30, WBBL / IPL / Spring Challenge always)

| league_key | gender | n | ll v2 | ll v3.1 | ll stack | ll form | brier v2 | brier v3.1 | brier stack | brier form |
|---|---|---|---|---|---|---|---|---|---|---|
| vitality blast | male | 485 | 0.6913 | 0.6916 | 0.6887 | 0.6986 | 0.2490 | 0.2491 | 0.2477 | 0.2520 |
| indian premier league (IPL) | male | 243 | 0.7258 | 0.7174 | 0.7017 | 0.7112 | 0.2659 | 0.2618 | 0.2542 | 0.2581 |
| syed mushtaq ali trophy | male | 154 | 0.6803 | 0.6800 | 0.6797 | 0.7001 | 0.2436 | 0.2434 | 0.2432 | 0.2524 |
| maharaja trophy ksca | male | 128 | 0.6976 | 0.6978 | 0.6850 | 0.6805 | 0.2522 | 0.2524 | 0.2460 | 0.2439 |
| bangladesh premier league | male | 126 | 0.6704 | 0.6704 | 0.6615 | 0.6449 | 0.2379 | 0.2387 | 0.2343 | 0.2267 |
| big bash league | male | 123 | 0.6605 | 0.6622 | 0.6769 | 0.6802 | 0.2340 | 0.2347 | 0.2419 | 0.2439 |
| csa challenge | male | 115 | 0.6926 | 0.6928 | 0.6840 | 0.6776 | 0.2488 | 0.2481 | 0.2454 | 0.2429 |
| pakistan super league | male | 108 | 0.6784 | 0.6698 | 0.6628 | 0.6685 | 0.2428 | 0.2387 | 0.2352 | 0.2383 |
| icc men s world cup | male | 104 | 0.6066 | 0.6063 | 0.6092 | 0.6286 | 0.2096 | 0.2095 | 0.2093 | 0.2191 |
| international league | male | 102 | 0.7498 | 0.7402 | 0.7105 | 0.7412 | 0.2740 | 0.2703 | 0.2581 | 0.2719 |
| vitality blast women | female | 99 | 0.6705 | 0.6681 | 0.6634 | 0.6493 | 0.2388 | 0.2376 | 0.2352 | 0.2283 |
| caribbean premier league | male | 94 | 0.6942 | 0.6927 | 0.6678 | 0.6691 | 0.2504 | 0.2498 | 0.2375 | 0.2382 |
| tamil nadu premier league | male | 94 | 0.6958 | 0.6962 | 0.6880 | 0.6882 | 0.2513 | 0.2515 | 0.2475 | 0.2473 |
| sa league | male | 92 | 0.7037 | 0.6965 | 0.7159 | 0.7282 | 0.2550 | 0.2509 | 0.2609 | 0.2651 |
| major league cricket | male | 86 | 0.6669 | 0.6628 | 0.6705 | 0.6832 | 0.2368 | 0.2349 | 0.2387 | 0.2448 |
| womens big bash league **(WBBL)** | female | 80 | 0.7080 | 0.7029 | 0.6922 | 0.6729 | 0.2558 | 0.2548 | 0.2495 | 0.2398 |
| super smash | male | 78 | 0.7129 | 0.7263 | 0.7098 | 0.7341 | 0.2558 | 0.2626 | 0.2582 | 0.2682 |
| womens premier league | female | 66 | 0.7376 | 0.6944 | 0.7053 | 0.7289 | 0.2699 | 0.2506 | 0.2557 | 0.2661 |
| nepal premier league | male | 64 | 0.7162 | 0.7150 | 0.6926 | 0.6776 | 0.2612 | 0.2609 | 0.2499 | 0.2422 |
| delhi premier league | male | 60 | 0.6731 | 0.6704 | 0.6773 | 0.6917 | 0.2400 | 0.2386 | 0.2419 | 0.2479 |
| madhya pradesh league | male | 58 | 0.6785 | 0.6721 | 0.6707 | 0.6698 | 0.2428 | 0.2397 | 0.2391 | 0.2388 |
| icc womens world cup | female | 55 | 0.5462 | 0.5582 | 0.5625 | 0.6073 | 0.1815 | 0.1874 | 0.1879 | 0.2087 |
| spring challenge | female | 54 | 0.7022 | 0.7232 | 0.7097 | 0.7044 | 0.2543 | 0.2647 | 0.2580 | 0.2559 |
| legends league cricket | male | 52 | 0.7462 | 0.7543 | 0.7348 | 0.7783 | 0.2748 | 0.2785 | 0.2696 | 0.2877 |
| national cricket league | male | 52 | 0.6842 | 0.6842 | 0.6798 | 0.6700 | 0.2457 | 0.2457 | 0.2437 | 0.2397 |
| andhra premier league | male | 50 | 0.7095 | 0.7134 | 0.7163 | 0.7188 | 0.2579 | 0.2597 | 0.2609 | 0.2621 |
| kerala cricket league | male | 50 | 0.7017 | 0.7022 | 0.7045 | 0.7204 | 0.2539 | 0.2540 | 0.2549 | 0.2614 |
| womens super smash | female | 49 | 0.6609 | 0.6680 | 0.6628 | 0.6772 | 0.2342 | 0.2375 | 0.2351 | 0.2426 |
| icc women s world cup qualifier | female | 48 | 0.6060 | 0.5908 | 0.5987 | 0.6303 | 0.2096 | 0.2015 | 0.2046 | 0.2191 |
| lanka premier league | male | 47 | 0.7093 | 0.7068 | 0.7260 | 0.7701 | 0.2581 | 0.2569 | 0.2662 | 0.2872 |
| senior women s trophy | female | 46 | 0.6295 | 0.6422 | 0.6252 | 0.5898 | 0.2197 | 0.2254 | 0.2177 | 0.2025 |
| mumbai league | male | 40 | 0.7337 | 0.7416 | 0.7485 | 0.7641 | 0.2699 | 0.2737 | 0.2769 | 0.2832 |
| global canada | male | 39 | 0.7031 | 0.7088 | 0.6842 | 0.6887 | 0.2546 | 0.2575 | 0.2455 | 0.2473 |
| acc women s premier cup | female | 37 | 0.5034 | 0.5088 | 0.5254 | 0.5726 | 0.1603 | 0.1633 | 0.1709 | 0.1917 |
| pondicherry premier league | male | 36 | 0.6951 | 0.6936 | 0.6969 | 0.6904 | 0.2510 | 0.2504 | 0.2520 | 0.2478 |
| icc under womens world cup | female | 35 | 0.6902 | 0.6032 | 0.6171 | 0.6129 | 0.2482 | 0.2064 | 0.2129 | 0.2127 |
| max competition | male | 35 | 0.6130 | 0.6039 | 0.5962 | 0.5926 | 0.2107 | 0.2064 | 0.2035 | 0.2030 |
| shpageeza cricket league | male | 35 | 0.6758 | 0.6730 | 0.6739 | 0.6606 | 0.2414 | 0.2400 | 0.2404 | 0.2344 |
| vitality blast women league | female | 35 | 0.7385 | 0.7340 | 0.7457 | 0.7366 | 0.2705 | 0.2691 | 0.2736 | 0.2692 |
| top end series | male | 31 | 0.7009 | 0.7086 | 0.7288 | 0.7762 | 0.2537 | 0.2574 | 0.2667 | 0.2870 |

## 4. WBBL explicit

### WBBL (n=80)

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 80 | 0.6000 | 0.7080 | 0.2558 | 0.5625 |
| v3.1 pooled | 80 | 0.4875 | 0.7029 | 0.2548 | 0.5625 |
| v3.1 + form stacker (CANDIDATE) | 80 | 0.4750 | 0.6922 | 0.2495 | 0.5625 |
| form_favourite (bar) | 80 | 0.6250 | 0.6729 | 0.2398 | 0.5625 |

### WBBL by season

| season | n | ll v2 | ll v3.1 | ll stack | ll form | brier v2 | brier v3.1 | brier stack | brier form |
|---|---|---|---|---|---|---|---|---|---|
| 2023 | 1 | 0.4236 | 0.5628 | 0.5620 | 0.4780 | 0.1193 | 0.1852 | 0.1849 | 0.1444 |
| 2024 | 40 | 0.7249 | 0.7086 | 0.6937 | 0.6882 | 0.2632 | 0.2576 | 0.2503 | 0.2472 |
| 2025 | 39 | 0.6980 | 0.7006 | 0.6940 | 0.6623 | 0.2518 | 0.2537 | 0.2504 | 0.2347 |

### WBBL calibration (5 buckets of 20%; P(home win))

| bucket | n v2 | pred v2 | actual v2 | n v3.1 | pred v3.1 | actual v3.1 | n stack | pred stack | actual stack | n form | pred form | actual form |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0-20% | 0 | - | - | 0 | - | - | 0 | - | - | 0 | - | - |
| 20-40% | 3 | 0.368 | 1.000 | 3 | 0.391 | 1.000 | 0 | - | - | 14 | 0.354 | 0.500 |
| 40-60% | 52 | 0.528 | 0.558 | 69 | 0.513 | 0.536 | 70 | 0.525 | 0.557 | 45 | 0.486 | 0.489 |
| 60-80% | 25 | 0.681 | 0.520 | 8 | 0.652 | 0.625 | 10 | 0.628 | 0.600 | 21 | 0.645 | 0.762 |
| 80-100% | 0 | - | - | 0 | - | - | 0 | - | - | 0 | - | - |

### WBBL calibration (deciles, non-empty buckets; P(home win))

| bucket | n v2 | pred v2 | actual v2 | n v3.1 | pred v3.1 | actual v3.1 | n stack | pred stack | actual stack | n form | pred form | actual form |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30- 40% | 3 | 0.368 | 1.000 | 3 | 0.391 | 1.000 | 0 | - | - | 14 | 0.354 | 0.500 |
| 40- 50% | 16 | 0.467 | 0.312 | 27 | 0.465 | 0.556 | 17 | 0.478 | 0.706 | 27 | 0.445 | 0.407 |
| 50- 60% | 36 | 0.555 | 0.667 | 42 | 0.544 | 0.524 | 53 | 0.541 | 0.509 | 18 | 0.548 | 0.611 |
| 60- 70% | 17 | 0.660 | 0.647 | 7 | 0.643 | 0.571 | 10 | 0.628 | 0.600 | 19 | 0.635 | 0.737 |
| 70- 80% | 8 | 0.726 | 0.250 | 1 | 0.713 | 1.000 | 0 | - | - | 2 | 0.740 | 1.000 |

## 5. Confidence-band distribution (confident >= 0.65, moderate >= 0.55)

| slice | model | confident n / share / acc | moderate n / share / acc | close_call n / share / acc |
|---|---|---|---|---|
| all | v2 per-gender (PRODUCTION) | 732 / 14.5% / 67.3% | 2134 / 42.3% / 58.3% | 2173 / 43.1% / 51.0% |
| all | v3.1 pooled | 724 / 14.4% / 70.9% | 2186 / 43.4% / 57.6% | 2129 / 42.3% / 51.6% |
| all | v3.1 + form stacker (CANDIDATE) | 549 / 10.9% / 71.2% | 2020 / 40.1% / 61.2% | 2470 / 49.0% / 52.0% |
| male | v2 per-gender (PRODUCTION) | 446 / 11.4% / 66.1% | 1673 / 42.6% / 57.4% | 1805 / 46.0% / 49.8% |
| male | v3.1 pooled | 513 / 13.1% / 67.3% | 1672 / 42.6% / 56.6% | 1739 / 44.3% / 50.9% |
| male | v3.1 + form stacker (CANDIDATE) | 338 / 8.6% / 67.5% | 1513 / 38.6% / 60.3% | 2073 / 52.8% / 51.9% |
| female | v2 per-gender (PRODUCTION) | 286 / 25.7% / 69.2% | 461 / 41.3% / 61.8% | 368 / 33.0% / 56.8% |
| female | v3.1 pooled | 211 / 18.9% / 79.6% | 514 / 46.1% / 60.7% | 390 / 35.0% / 54.6% |
| female | v3.1 + form stacker (CANDIDATE) | 211 / 18.9% / 77.3% | 507 / 45.5% / 63.7% | 397 / 35.6% / 52.6% |
| wbbl | v2 per-gender (PRODUCTION) | 22 / 27.5% / 50.0% | 27 / 33.8% / 59.3% | 31 / 38.8% / 67.7% |
| wbbl | v3.1 pooled | 3 / 3.8% / 66.7% | 35 / 43.8% / 51.4% | 42 / 52.5% / 45.2% |
| wbbl | v3.1 + form stacker (CANDIDATE) | 3 / 3.8% / 66.7% | 26 / 32.5% / 61.5% | 51 / 63.7% / 39.2% |

## 6. Sensitivity: stacker without the gender term (not the candidate)

- overall log_loss 0.6705 / brier 0.2389; men 0.6781 / 0.2426; women 0.6438 / 0.2261; WBBL 0.6917 / 0.2493
- WBBL no-gender stack - form: log_loss +0.0187 [-0.0447, +0.0418], brier +0.0095 [-0.0207, +0.0206]

## 7. Stacker coefficients (raw scale)

37 monthly fits; 215 matches passed through at cold start.

| fit | block | n_train | intercept | logit(p_v3.1) | form_gap_tourn | form_gap_last5 | is_female |
|---|---|---|---|---|---|---|---|
| first | 2023-08 | 215 | -0.1433 | +0.0543 | +0.8981 | -0.3294 | +0.5955 |
| last | 2026-10 | 5120 | +0.0596 | +0.4419 | +0.5300 | +0.2145 | +0.1178 |
