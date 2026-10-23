# Men + women retrain: side-by-side comparison

- generated: 2026-10-23T14:25:46
- harness: src/model/validation.walk_forward (expanding window, monthly blocks, train strictly before the block; MIN_TRAIN 100)
- script: `venv/Scripts/python.exe -m src.model.retrain_men_women`
- **production is NOT switched** by this report (payload.py still uses logistic_v2 per gender).

## 0. Models and evaluation set

| model | what it is |
|---|---|
| v2 per-gender (PRODUCTION) | logistic v2 (C=0.01, league dummies) refit on same-gender history only; what payload.py serves today |
| v3 pooled (CANDIDATE) | same pipeline on men+women history, plus is_female; league dummies per fold on the pooled train |
| v3 interact (sensitivity) | v3 pooled + is_female x every base feature; reported, not a candidate |
| form_favourite (bar) | the Phase-2 rule baseline |

Common set (scored by all four): **5073** matches (3924 men, 1149 women), 2023-05-01 .. 2026-10-21. Completed matches in L3: 5286 (4036 men, 1250 women).

Pooled-only coverage (excluded from all comparisons): 101 matches {'female': 101}, of which WBBL 57. v2 cannot score them (fewer than 100 same-gender train matches at the time).

## 1. Adoption rule verdict: **PASS**

| check | measure | value [95% block-bootstrap CI] | result |
|---|---|---|---|
| Men: no degradation beyond noise | log_loss v3 - v2 (n=3924) | -0.0019 [-0.0033, -0.0005] | pass |
| Men: no degradation beyond noise | brier v3 - v2 | -0.0009 [-0.0016, -0.0002] | pass |
| Women: beat form_favourite | log_loss v3 - form (n=1149) | -0.0077 [-0.0237, +0.0087] | pass |
| Women: beat form_favourite | brier v3 - form | -0.0032 [-0.0107, +0.0044] | pass |

Negative deltas mean the candidate is better. Men fail only if the delta is positive and its whole interval is above zero. Women pass on the point estimate, per the rule; the interval is shown for context. Intervals resample whole monthly blocks (39 men's blocks, 33 women's), 2000 reps.

For context, women v3 - v2 per-gender: log_loss -0.0102 [-0.0246, +0.0008], brier -0.0047 [-0.0117, +0.0005].

## 2. Overall and per gender (common set)

### Overall

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 5073 | 0.5653 | 0.6780 | 0.2425 | 0.5399 |
| v3 pooled (CANDIDATE) | 5073 | 0.5715 | 0.6743 | 0.2407 | 0.5399 |
| v3 interact (sensitivity) | 5073 | 0.5638 | 0.6774 | 0.2421 | 0.5399 |
| form_favourite (bar) | 5073 | 0.5858 | 0.6805 | 0.2433 | 0.5399 |

### Men

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 3924 | 0.5497 | 0.6849 | 0.2457 | 0.5293 |
| v3 pooled (CANDIDATE) | 3924 | 0.5568 | 0.6830 | 0.2448 | 0.5293 |
| v3 interact (sensitivity) | 3924 | 0.5497 | 0.6845 | 0.2456 | 0.5293 |
| form_favourite (bar) | 3924 | 0.5726 | 0.6888 | 0.2473 | 0.5293 |

### Women

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 1149 | 0.6188 | 0.6546 | 0.2314 | 0.5762 |
| v3 pooled (CANDIDATE) | 1149 | 0.6214 | 0.6444 | 0.2267 | 0.5762 |
| v3 interact (sensitivity) | 1149 | 0.6118 | 0.6530 | 0.2302 | 0.5762 |
| form_favourite (bar) | 1149 | 0.6310 | 0.6521 | 0.2299 | 0.5762 |

## 3. Per league (common set; n >= 30, WBBL / IPL / Spring Challenge always)

| league_key | gender | n | ll v2 | ll v3 | ll form | brier v2 | brier v3 | brier form | acc v2 | acc v3 | acc form |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vitality blast | male | 485 | 0.6913 | 0.6915 | 0.6986 | 0.2490 | 0.2491 | 0.2520 | 0.518 | 0.526 | 0.579 |
| indian premier league (IPL) | male | 243 | 0.7258 | 0.7169 | 0.7112 | 0.2659 | 0.2615 | 0.2581 | 0.449 | 0.486 | 0.519 |
| syed mushtaq ali trophy | male | 154 | 0.6803 | 0.6799 | 0.7001 | 0.2436 | 0.2434 | 0.2524 | 0.539 | 0.571 | 0.565 |
| maharaja trophy ksca | male | 128 | 0.6975 | 0.6983 | 0.6805 | 0.2522 | 0.2526 | 0.2439 | 0.516 | 0.531 | 0.555 |
| bangladesh premier league | male | 126 | 0.6704 | 0.6694 | 0.6449 | 0.2379 | 0.2382 | 0.2267 | 0.595 | 0.587 | 0.619 |
| big bash league | male | 123 | 0.6605 | 0.6620 | 0.6802 | 0.2340 | 0.2346 | 0.2439 | 0.618 | 0.610 | 0.545 |
| csa challenge | male | 115 | 0.6926 | 0.6915 | 0.6776 | 0.2488 | 0.2475 | 0.2429 | 0.574 | 0.548 | 0.557 |
| pakistan super league | male | 108 | 0.6784 | 0.6716 | 0.6685 | 0.2429 | 0.2396 | 0.2383 | 0.537 | 0.546 | 0.583 |
| icc men s world cup | male | 104 | 0.6067 | 0.6066 | 0.6286 | 0.2097 | 0.2095 | 0.2191 | 0.663 | 0.654 | 0.702 |
| international league | male | 102 | 0.7498 | 0.7410 | 0.7412 | 0.2740 | 0.2707 | 0.2719 | 0.441 | 0.480 | 0.480 |
| caribbean premier league | male | 94 | 0.6942 | 0.6932 | 0.6691 | 0.2504 | 0.2500 | 0.2382 | 0.511 | 0.489 | 0.564 |
| tamil nadu premier league | male | 94 | 0.6958 | 0.6953 | 0.6882 | 0.2513 | 0.2510 | 0.2473 | 0.511 | 0.521 | 0.574 |
| sa league | male | 92 | 0.7037 | 0.6965 | 0.7282 | 0.2550 | 0.2509 | 0.2651 | 0.500 | 0.565 | 0.554 |
| major league cricket | male | 86 | 0.6669 | 0.6621 | 0.6832 | 0.2368 | 0.2345 | 0.2448 | 0.663 | 0.674 | 0.581 |
| womens big bash league **(WBBL)** | female | 80 | 0.7102 | 0.7015 | 0.6729 | 0.2566 | 0.2542 | 0.2398 | 0.575 | 0.500 | 0.625 |
| super smash | male | 78 | 0.7129 | 0.7262 | 0.7341 | 0.2558 | 0.2625 | 0.2682 | 0.538 | 0.487 | 0.551 |
| womens premier league | female | 66 | 0.7333 | 0.6950 | 0.7289 | 0.2679 | 0.2509 | 0.2661 | 0.545 | 0.530 | 0.530 |
| nepal premier league | male | 64 | 0.7162 | 0.7155 | 0.6776 | 0.2612 | 0.2612 | 0.2422 | 0.484 | 0.438 | 0.578 |
| delhi premier league | male | 60 | 0.6731 | 0.6711 | 0.6917 | 0.2400 | 0.2389 | 0.2479 | 0.633 | 0.650 | 0.583 |
| madhya pradesh league | male | 58 | 0.6784 | 0.6728 | 0.6698 | 0.2428 | 0.2401 | 0.2388 | 0.569 | 0.621 | 0.569 |
| icc womens world cup | female | 55 | 0.5426 | 0.5556 | 0.6073 | 0.1803 | 0.1864 | 0.2087 | 0.709 | 0.727 | 0.745 |
| spring challenge | female | 54 | 0.7012 | 0.7227 | 0.7044 | 0.2537 | 0.2645 | 0.2559 | 0.444 | 0.481 | 0.463 |
| legends league cricket | male | 52 | 0.7462 | 0.7519 | 0.7783 | 0.2748 | 0.2774 | 0.2877 | 0.365 | 0.423 | 0.519 |
| national cricket league | male | 52 | 0.6842 | 0.6849 | 0.6700 | 0.2457 | 0.2461 | 0.2397 | 0.519 | 0.519 | 0.538 |
| andhra premier league | male | 50 | 0.7096 | 0.7124 | 0.7188 | 0.2579 | 0.2592 | 0.2621 | 0.500 | 0.500 | 0.420 |
| kerala cricket league | male | 50 | 0.7017 | 0.7025 | 0.7204 | 0.2539 | 0.2541 | 0.2614 | 0.580 | 0.580 | 0.600 |
| women s vitality blast | female | 50 | 0.6772 | 0.6728 | 0.6540 | 0.2420 | 0.2399 | 0.2307 | 0.620 | 0.620 | 0.620 |
| vitality blast women | female | 49 | 0.6578 | 0.6506 | 0.6594 | 0.2336 | 0.2299 | 0.2337 | 0.571 | 0.571 | 0.571 |
| womens super smash | female | 49 | 0.6591 | 0.6679 | 0.6772 | 0.2332 | 0.2375 | 0.2426 | 0.612 | 0.612 | 0.551 |
| icc women s world cup qualifier | female | 48 | 0.6021 | 0.5890 | 0.6303 | 0.2080 | 0.2007 | 0.2191 | 0.625 | 0.646 | 0.667 |
| lanka premier league | male | 47 | 0.7093 | 0.7068 | 0.7701 | 0.2581 | 0.2569 | 0.2872 | 0.383 | 0.489 | 0.340 |
| senior women s trophy | female | 46 | 0.6248 | 0.6410 | 0.5898 | 0.2175 | 0.2248 | 0.2025 | 0.609 | 0.652 | 0.630 |
| mumbai league | male | 40 | 0.7338 | 0.7428 | 0.7641 | 0.2700 | 0.2743 | 0.2832 | 0.475 | 0.475 | 0.425 |
| global canada | male | 39 | 0.7031 | 0.7088 | 0.6887 | 0.2546 | 0.2575 | 0.2473 | 0.564 | 0.564 | 0.590 |
| acc women s premier cup | female | 37 | 0.4926 | 0.5043 | 0.5726 | 0.1562 | 0.1616 | 0.1917 | 0.838 | 0.757 | 0.784 |
| pondicherry premier league | male | 36 | 0.6951 | 0.6931 | 0.6904 | 0.2510 | 0.2501 | 0.2478 | 0.444 | 0.444 | 0.444 |
| icc women s under world cup | female | 35 | 0.6936 | 0.6059 | 0.6162 | 0.2500 | 0.2077 | 0.2142 | 0.543 | 0.714 | 0.714 |
| max competition | male | 35 | 0.6130 | 0.6019 | 0.5926 | 0.2107 | 0.2054 | 0.2030 | 0.771 | 0.771 | 0.686 |
| shpageeza cricket league | male | 35 | 0.6757 | 0.6736 | 0.6606 | 0.2413 | 0.2403 | 0.2344 | 0.657 | 0.571 | 0.657 |
| vitality blast women league | female | 35 | 0.7393 | 0.7345 | 0.7366 | 0.2709 | 0.2693 | 0.2692 | 0.543 | 0.486 | 0.514 |
| icc under womens world cup | female | 34 | 0.7054 | 0.6228 | 0.6243 | 0.2558 | 0.2158 | 0.2181 | 0.529 | 0.676 | 0.706 |
| top end series | male | 31 | 0.7009 | 0.7099 | 0.7762 | 0.2537 | 0.2580 | 0.2870 | 0.516 | 0.516 | 0.516 |

## 4. WBBL explicit

### WBBL, all seasons in the common set (n=80)

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 80 | 0.5750 | 0.7102 | 0.2566 | 0.5625 |
| v3 pooled (CANDIDATE) | 80 | 0.5000 | 0.7015 | 0.2542 | 0.5625 |
| v3 interact (sensitivity) | 80 | 0.5250 | 0.7343 | 0.2660 | 0.5625 |
| form_favourite (bar) | 80 | 0.6250 | 0.6729 | 0.2398 | 0.5625 |

WBBL on every match the candidate scores (n=137, by season {2023: 58, 2024: 40, 2025: 39}; includes the matches v2 cannot score): v3 log_loss 0.6990 / brier 0.2529 / acc 0.518 vs form log_loss 0.6738 / brier 0.2400 / acc 0.613; v3 - form log_loss +0.0251 [-0.0158, +0.0452].

### WBBL by season

| season | n | ll v2 | ll v3 | ll form | brier v2 | brier v3 | brier form |
|---|---|---|---|---|---|---|---|
| 2023 | 1 | 0.4236 | 0.5628 | 0.4780 | 0.1193 | 0.1852 | 0.1444 |
| 2024 | 40 | 0.7270 | 0.7069 | 0.6882 | 0.2635 | 0.2568 | 0.2472 |
| 2025 | 39 | 0.7004 | 0.6996 | 0.6623 | 0.2530 | 0.2532 | 0.2347 |

WBBL v3 - form: log_loss +0.0286 [-0.0141, +0.0424], brier +0.0143 [-0.0060, +0.0211].
WBBL v3 - v2: log_loss -0.0087 [-0.0226, +0.0105], brier -0.0025 [-0.0079, +0.0066].

### WBBL calibration (5 buckets of 20%; P(home win))

| bucket | n v2 | pred v2 | actual v2 | n v3 | pred v3 | actual v3 | n form | pred form | actual form |
|---|---|---|---|---|---|---|---|---|---|
| 0-20% | 0 | - | - | 0 | - | - | 0 | - | - |
| 20-40% | 1 | 0.341 | 1.000 | 3 | 0.393 | 1.000 | 14 | 0.354 | 0.500 |
| 40-60% | 43 | 0.526 | 0.512 | 69 | 0.516 | 0.536 | 45 | 0.486 | 0.489 |
| 60-80% | 36 | 0.678 | 0.611 | 8 | 0.655 | 0.625 | 21 | 0.645 | 0.762 |
| 80-100% | 0 | - | - | 0 | - | - | 0 | - | - |

### WBBL calibration (deciles, as the harness prints them)

| bucket | n v2 | pred v2 | actual v2 | n v3 | pred v3 | actual v3 |
|---|---|---|---|---|---|---|
| 30- 40% | 1 | 0.341 | 1.000 | 3 | 0.393 | 1.000 |
| 40- 50% | 14 | 0.468 | 0.429 | 26 | 0.467 | 0.538 |
| 50- 60% | 29 | 0.554 | 0.552 | 43 | 0.545 | 0.535 |
| 60- 70% | 22 | 0.641 | 0.727 | 7 | 0.645 | 0.571 |
| 70- 80% | 14 | 0.735 | 0.429 | 1 | 0.719 | 1.000 |

## 5. Confidence-band distribution (framing.BAND_CONFIG: confident >= 0.65, moderate >= 0.55)

| slice | model | confident n / share / acc | moderate n / share / acc | close_call n / share / acc |
|---|---|---|---|---|
| all | v2 per-gender (PRODUCTION) | 767 / 15.1% / 67.5% | 2141 / 42.2% / 58.4% | 2165 / 42.7% / 50.8% |
| all | v3 pooled (CANDIDATE) | 755 / 14.9% / 70.7% | 2210 / 43.6% / 57.6% | 2108 / 41.6% / 51.8% |
| male | v2 per-gender (PRODUCTION) | 443 / 11.3% / 66.1% | 1675 / 42.7% / 57.3% | 1806 / 46.0% / 50.1% |
| male | v3 pooled (CANDIDATE) | 522 / 13.3% / 66.7% | 1672 / 42.6% / 56.9% | 1730 / 44.1% / 51.2% |
| female | v2 per-gender (PRODUCTION) | 324 / 28.2% / 69.4% | 466 / 40.6% / 62.2% | 359 / 31.2% / 54.6% |
| female | v3 pooled (CANDIDATE) | 233 / 20.3% / 79.8% | 538 / 46.8% / 59.9% | 378 / 32.9% / 54.5% |
| wbbl | v2 per-gender (PRODUCTION) | 23 / 28.7% / 47.8% | 35 / 43.8% / 68.6% | 22 / 27.5% / 50.0% |
| wbbl | v3 pooled (CANDIDATE) | 3 / 3.8% / 66.7% | 37 / 46.2% / 48.6% | 40 / 50.0% / 50.0% |

## 6. Sensitivity: v3 interact (not a candidate)

- Men v3_interact - v2: log_loss -0.0004 [-0.0016, +0.0008], brier -0.0001 [-0.0007, +0.0005]
- Women v3_interact - form: log_loss +0.0009 [-0.0211, +0.0263], brier +0.0003 [-0.0096, +0.0117]

## 7. Candidate coefficients (full-data fit, interpretation only)

- intercept +0.1709; is_female +0.0502; WBBL dummy -0.0064
- leagues with a dummy (>= 50 matches): 27

| feature | coef (standardized) |
|---|---|
| home_matches_in_window_last5 | +0.1615 |
| away_matches_in_window_last5 | -0.1324 |
| away_win_pct_tourn | -0.1264 |
| is_neutral_venue | +0.1216 |
| home_win_pct_last5 | +0.1168 |
| away_phase_missing | +0.1035 |
| home_phase_missing | -0.0966 |
| home_win_pct_tourn | +0.0818 |
| gap_win_pct_tourn | +0.0782 |
| gap_avg_margin_last5 | +0.0760 |
| away_rr_middle_last5 | -0.0742 |
| home_rr_middle_last5 | +0.0729 |
| away_win_pct_last5 | -0.0577 |
| away_rr_death_last5 | +0.0526 |
| lg_syed_mushtaq_ali_trophy | +0.0523 |
