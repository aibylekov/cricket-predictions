# Men + women retrain v3.1: side-by-side comparison

- generated: 2026-10-23T14:34:36
- harness: src/model/validation.walk_forward (expanding window, monthly blocks, train strictly before the block; MIN_TRAIN 100)
- script: `venv/Scripts/python.exe -m src.model.retrain_men_women`
- data: 275 league_keys in the completed set; league_key aliases applied (revise_l1.LEAGUE_KEY_ALIASES); U19 WWC 2025 duplicate ids 911/912 flagged, not dropped
- previous round (v3, pre-fix data): docs/model/retrain_men_women_report.md
- **production is NOT switched** by this report (payload.py still uses logistic_v2 per gender).

## 0. Models and evaluation set

| model | what it is |
|---|---|
| v2 per-gender (PRODUCTION) | logistic v2 (C=0.01, league dummies) refit on same-gender history only; what payload.py serves today |
| v3.1 pooled (CANDIDATE) | same spec as v3: the v2 pipeline on men+women history, plus is_female; league dummies per fold on the pooled train |
| form_favourite (bar) | the Phase-2 rule baseline |

Common set (scored by all): **5073** matches (3924 men, 1149 women), 2023-05-01 .. 2026-10-21. Completed matches in L3: 5286 (4036 men, 1250 women).

Pooled-only coverage (excluded from the comparisons): 101 matches {'female': 101}, of which WBBL 57.

## 1. Adoption rule verdict: **FAIL**

| check | measure | value [95% block-bootstrap CI] | result |
|---|---|---|---|
| Men: no degradation beyond noise | log_loss v3.1 - v2 (n=3924) | -0.0019 [-0.0033, -0.0005] | pass |
| Men: no degradation beyond noise | brier v3.1 - v2 | -0.0009 [-0.0016, -0.0002] | pass |
| Women: beat form_favourite | log_loss v3.1 - form (n=1149) | -0.0062 [-0.0212, +0.0099] | pass |
| Women: beat form_favourite | brier v3.1 - form | -0.0025 [-0.0095, +0.0049] | pass |
| WBBL: at least match form_favourite | log_loss v3.1 - form (n=80) | +0.0292 [-0.0133, +0.0421] | **FAIL** |
| WBBL: at least match form_favourite | brier v3.1 - form | +0.0146 [-0.0056, +0.0209] | **FAIL** |

Negative deltas mean the candidate is better. Men fail only if the delta is positive and its whole interval is above zero. Women and WBBL are judged on the point estimate; the interval is context. Intervals resample whole monthly blocks, 2000 reps.

For context, women v3.1 - v2: log_loss -0.0099 [-0.0247, +0.0012], brier -0.0046 [-0.0117, +0.0007].

## 2. Overall and per gender (common set)

### Overall

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 5073 | 0.5653 | 0.6781 | 0.2425 | 0.5399 |
| v3.1 pooled (CANDIDATE) | 5073 | 0.5717 | 0.6744 | 0.2408 | 0.5399 |
| form_favourite (bar) | 5073 | 0.5870 | 0.6803 | 0.2432 | 0.5399 |

### Men

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 3924 | 0.5489 | 0.6848 | 0.2457 | 0.5293 |
| v3.1 pooled (CANDIDATE) | 3924 | 0.5563 | 0.6829 | 0.2448 | 0.5293 |
| form_favourite (bar) | 3924 | 0.5726 | 0.6888 | 0.2473 | 0.5293 |

### Women

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 1149 | 0.6214 | 0.6551 | 0.2316 | 0.5762 |
| v3.1 pooled (CANDIDATE) | 1149 | 0.6240 | 0.6452 | 0.2270 | 0.5762 |
| form_favourite (bar) | 1149 | 0.6362 | 0.6514 | 0.2295 | 0.5762 |

## 3. Per league (common set; n >= 30, WBBL / IPL / Spring Challenge always)

| league_key | gender | n | ll v2 | ll v3.1 | ll form | brier v2 | brier v3.1 | brier form | acc v2 | acc v3.1 | acc form |
|---|---|---|---|---|---|---|---|---|---|---|---|
| vitality blast | male | 485 | 0.6913 | 0.6913 | 0.6986 | 0.2490 | 0.2490 | 0.2520 | 0.518 | 0.530 | 0.579 |
| indian premier league (IPL) | male | 243 | 0.7258 | 0.7166 | 0.7112 | 0.2659 | 0.2614 | 0.2581 | 0.444 | 0.477 | 0.519 |
| syed mushtaq ali trophy | male | 154 | 0.6803 | 0.6801 | 0.7001 | 0.2436 | 0.2434 | 0.2524 | 0.539 | 0.571 | 0.565 |
| maharaja trophy ksca | male | 128 | 0.6976 | 0.6980 | 0.6805 | 0.2522 | 0.2525 | 0.2439 | 0.516 | 0.539 | 0.555 |
| bangladesh premier league | male | 126 | 0.6704 | 0.6702 | 0.6449 | 0.2379 | 0.2386 | 0.2267 | 0.595 | 0.579 | 0.619 |
| big bash league | male | 123 | 0.6605 | 0.6622 | 0.6802 | 0.2340 | 0.2347 | 0.2439 | 0.618 | 0.618 | 0.545 |
| csa challenge | male | 115 | 0.6926 | 0.6922 | 0.6776 | 0.2488 | 0.2478 | 0.2429 | 0.574 | 0.548 | 0.557 |
| pakistan super league | male | 108 | 0.6784 | 0.6706 | 0.6685 | 0.2428 | 0.2391 | 0.2383 | 0.537 | 0.546 | 0.583 |
| icc men s world cup | male | 104 | 0.6066 | 0.6061 | 0.6286 | 0.2096 | 0.2094 | 0.2191 | 0.663 | 0.654 | 0.702 |
| international league | male | 102 | 0.7498 | 0.7406 | 0.7412 | 0.2740 | 0.2705 | 0.2719 | 0.441 | 0.480 | 0.480 |
| vitality blast women | female | 99 | 0.6686 | 0.6673 | 0.6493 | 0.2379 | 0.2372 | 0.2283 | 0.606 | 0.646 | 0.646 |
| caribbean premier league | male | 94 | 0.6942 | 0.6935 | 0.6691 | 0.2504 | 0.2501 | 0.2382 | 0.511 | 0.489 | 0.564 |
| tamil nadu premier league | male | 94 | 0.6958 | 0.6953 | 0.6882 | 0.2513 | 0.2511 | 0.2473 | 0.511 | 0.521 | 0.574 |
| sa league | male | 92 | 0.7037 | 0.6968 | 0.7282 | 0.2550 | 0.2510 | 0.2651 | 0.500 | 0.565 | 0.554 |
| major league cricket | male | 86 | 0.6669 | 0.6622 | 0.6832 | 0.2368 | 0.2346 | 0.2448 | 0.663 | 0.651 | 0.581 |
| womens big bash league **(WBBL)** | female | 80 | 0.7071 | 0.7022 | 0.6729 | 0.2555 | 0.2545 | 0.2398 | 0.600 | 0.500 | 0.625 |
| super smash | male | 78 | 0.7129 | 0.7261 | 0.7341 | 0.2558 | 0.2625 | 0.2682 | 0.538 | 0.487 | 0.551 |
| icc under womens world cup | female | 69 | 0.6971 | 0.6118 | 0.6201 | 0.2518 | 0.2105 | 0.2161 | 0.536 | 0.710 | 0.710 |
| womens premier league | female | 66 | 0.7384 | 0.6945 | 0.7289 | 0.2702 | 0.2506 | 0.2661 | 0.545 | 0.515 | 0.530 |
| nepal premier league | male | 64 | 0.7162 | 0.7152 | 0.6776 | 0.2612 | 0.2611 | 0.2422 | 0.484 | 0.438 | 0.578 |
| delhi premier league | male | 60 | 0.6731 | 0.6710 | 0.6917 | 0.2400 | 0.2388 | 0.2479 | 0.633 | 0.633 | 0.583 |
| madhya pradesh league | male | 58 | 0.6785 | 0.6726 | 0.6698 | 0.2428 | 0.2400 | 0.2388 | 0.569 | 0.621 | 0.569 |
| icc womens world cup | female | 55 | 0.5425 | 0.5576 | 0.6073 | 0.1800 | 0.1871 | 0.2087 | 0.691 | 0.727 | 0.745 |
| spring challenge | female | 54 | 0.7036 | 0.7241 | 0.7044 | 0.2548 | 0.2652 | 0.2559 | 0.463 | 0.463 | 0.463 |
| legends league cricket | male | 52 | 0.7462 | 0.7520 | 0.7783 | 0.2748 | 0.2774 | 0.2877 | 0.365 | 0.423 | 0.519 |
| national cricket league | male | 52 | 0.6842 | 0.6847 | 0.6700 | 0.2457 | 0.2459 | 0.2397 | 0.519 | 0.519 | 0.538 |
| andhra premier league | male | 50 | 0.7095 | 0.7134 | 0.7188 | 0.2579 | 0.2597 | 0.2621 | 0.480 | 0.500 | 0.420 |
| kerala cricket league | male | 50 | 0.7017 | 0.7025 | 0.7204 | 0.2539 | 0.2541 | 0.2614 | 0.580 | 0.580 | 0.600 |
| womens super smash | female | 49 | 0.6590 | 0.6679 | 0.6772 | 0.2332 | 0.2375 | 0.2426 | 0.592 | 0.612 | 0.551 |
| icc women s world cup qualifier | female | 48 | 0.6030 | 0.5899 | 0.6303 | 0.2084 | 0.2011 | 0.2191 | 0.625 | 0.646 | 0.667 |
| lanka premier league | male | 47 | 0.7093 | 0.7068 | 0.7701 | 0.2581 | 0.2569 | 0.2872 | 0.383 | 0.489 | 0.340 |
| senior women s trophy | female | 46 | 0.6235 | 0.6403 | 0.5898 | 0.2169 | 0.2244 | 0.2025 | 0.609 | 0.630 | 0.630 |
| mumbai league | male | 40 | 0.7337 | 0.7434 | 0.7641 | 0.2699 | 0.2746 | 0.2832 | 0.475 | 0.450 | 0.425 |
| global canada | male | 39 | 0.7031 | 0.7088 | 0.6887 | 0.2546 | 0.2575 | 0.2473 | 0.564 | 0.564 | 0.590 |
| acc women s premier cup | female | 37 | 0.4981 | 0.5070 | 0.5726 | 0.1582 | 0.1626 | 0.1917 | 0.811 | 0.730 | 0.784 |
| pondicherry premier league | male | 36 | 0.6951 | 0.6924 | 0.6904 | 0.2510 | 0.2498 | 0.2478 | 0.444 | 0.444 | 0.444 |
| max competition | male | 35 | 0.6130 | 0.6018 | 0.5926 | 0.2107 | 0.2054 | 0.2030 | 0.771 | 0.771 | 0.686 |
| shpageeza cricket league | male | 35 | 0.6758 | 0.6739 | 0.6606 | 0.2414 | 0.2405 | 0.2344 | 0.657 | 0.571 | 0.657 |
| vitality blast women league | female | 35 | 0.7371 | 0.7334 | 0.7366 | 0.2700 | 0.2688 | 0.2692 | 0.543 | 0.457 | 0.514 |
| top end series | male | 31 | 0.7009 | 0.7109 | 0.7762 | 0.2537 | 0.2585 | 0.2870 | 0.516 | 0.516 | 0.516 |

## 4. WBBL explicit

### WBBL, common set (n=80)

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 80 | 0.6000 | 0.7071 | 0.2555 | 0.5625 |
| v3.1 pooled (CANDIDATE) | 80 | 0.5000 | 0.7022 | 0.2545 | 0.5625 |
| form_favourite (bar) | 80 | 0.6250 | 0.6729 | 0.2398 | 0.5625 |

### WBBL by season

| season | n | ll v2 | ll v3.1 | ll form | brier v2 | brier v3.1 | brier form |
|---|---|---|---|---|---|---|---|
| 2023 | 1 | 0.4236 | 0.5628 | 0.4780 | 0.1193 | 0.1852 | 0.1444 |
| 2024 | 40 | 0.7249 | 0.7086 | 0.6882 | 0.2632 | 0.2576 | 0.2472 |
| 2025 | 39 | 0.6962 | 0.6992 | 0.6623 | 0.2511 | 0.2530 | 0.2347 |

WBBL v3.1 - form: log_loss +0.0292 [-0.0133, +0.0421], brier +0.0146 [-0.0056, +0.0209].
WBBL v3.1 - v2: log_loss -0.0050 [-0.0218, +0.0115], brier -0.0010 [-0.0081, +0.0060].

WBBL on every match the candidate scores (n=137, by season {2023: 58, 2024: 40, 2025: 39}; includes matches v2 cannot score): v3.1 log_loss 0.6994 / brier 0.2531 / acc 0.518 vs form log_loss 0.6738 / brier 0.2400 / acc 0.613; v3.1 - form log_loss +0.0255 [-0.0157, +0.0453].

### WBBL calibration (5 buckets of 20%; P(home win))

| bucket | n v2 | pred v2 | actual v2 | n v3.1 | pred v3.1 | actual v3.1 | n form | pred form | actual form |
|---|---|---|---|---|---|---|---|---|---|
| 0-20% | 0 | - | - | 0 | - | - | 0 | - | - |
| 20-40% | 3 | 0.371 | 1.000 | 3 | 0.391 | 1.000 | 14 | 0.354 | 0.500 |
| 40-60% | 51 | 0.526 | 0.549 | 69 | 0.513 | 0.536 | 45 | 0.486 | 0.489 |
| 60-80% | 26 | 0.679 | 0.538 | 8 | 0.653 | 0.625 | 21 | 0.645 | 0.762 |
| 80-100% | 0 | - | - | 0 | - | - | 0 | - | - |

### WBBL calibration (deciles, non-empty buckets)

| bucket | n v2 | pred v2 | actual v2 | n v3.1 | pred v3.1 | actual v3.1 | n form | pred form | actual form |
|---|---|---|---|---|---|---|---|---|---|
| 30- 40% | 3 | 0.371 | 1.000 | 3 | 0.391 | 1.000 | 14 | 0.354 | 0.500 |
| 40- 50% | 16 | 0.467 | 0.312 | 26 | 0.464 | 0.538 | 27 | 0.445 | 0.407 |
| 50- 60% | 35 | 0.554 | 0.657 | 43 | 0.542 | 0.535 | 18 | 0.548 | 0.611 |
| 60- 70% | 19 | 0.659 | 0.632 | 7 | 0.643 | 0.571 | 19 | 0.635 | 0.737 |
| 70- 80% | 7 | 0.736 | 0.286 | 1 | 0.717 | 1.000 | 2 | 0.740 | 1.000 |

## 5. Confidence-band distribution (framing.BAND_CONFIG: confident >= 0.65, moderate >= 0.55)

| slice | model | confident n / share / acc | moderate n / share / acc | close_call n / share / acc |
|---|---|---|---|---|
| all | v2 per-gender (PRODUCTION) | 752 / 14.8% / 67.6% | 2138 / 42.1% / 58.4% | 2183 / 43.0% / 50.9% |
| all | v3.1 pooled (CANDIDATE) | 747 / 14.7% / 70.3% | 2197 / 43.3% / 57.9% | 2129 / 42.0% / 51.8% |
| male | v2 per-gender (PRODUCTION) | 446 / 11.4% / 66.1% | 1673 / 42.6% / 57.4% | 1805 / 46.0% / 49.8% |
| male | v3.1 pooled (CANDIDATE) | 526 / 13.4% / 66.7% | 1668 / 42.5% / 56.7% | 1730 / 44.1% / 51.2% |
| female | v2 per-gender (PRODUCTION) | 306 / 26.6% / 69.6% | 465 / 40.5% / 61.9% | 378 / 32.9% / 56.3% |
| female | v3.1 pooled (CANDIDATE) | 221 / 19.2% / 78.7% | 529 / 46.0% / 61.8% | 399 / 34.7% / 54.1% |
| wbbl | v2 per-gender (PRODUCTION) | 21 / 26.2% / 52.4% | 29 / 36.2% / 55.2% | 30 / 37.5% / 70.0% |
| wbbl | v3.1 pooled (CANDIDATE) | 3 / 3.8% / 66.7% | 36 / 45.0% / 50.0% | 41 / 51.2% / 48.8% |

## 6. v3.1 coefficients (full-data fit, interpretation only)

- intercept +0.1707; is_female +0.0488; WBBL dummy -0.0059
- leagues with a dummy (>= 50 matches): 28

| feature | coef (standardized) |
|---|---|
| home_matches_in_window_last5 | +0.1624 |
| away_matches_in_window_last5 | -0.1315 |
| away_win_pct_tourn | -0.1230 |
| is_neutral_venue | +0.1184 |
| home_win_pct_last5 | +0.1177 |
| away_phase_missing | +0.1053 |
| home_phase_missing | -0.0963 |
| gap_win_pct_tourn | +0.0854 |
| home_win_pct_tourn | +0.0762 |
| gap_avg_margin_last5 | +0.0758 |
| away_rr_middle_last5 | -0.0738 |
| home_rr_middle_last5 | +0.0721 |
| away_win_pct_last5 | -0.0578 |
| away_rr_death_last5 | +0.0530 |
| home_rr_death_last5 | -0.0530 |
