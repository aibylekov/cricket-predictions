# Hybrid form-anchored stacker: side-by-side comparison

- generated: 2026-10-26T18:22:13
- script: `venv/Scripts/python.exe -m src.model.stack_hybrid` (scheme in its docstring)
- previous rounds: docs/model/stack_v3_1_form_report.md (global), docs/model/stack_per_gender_report.md (per-gender)
- **adopted as production 2026-10-26**: payload.py serves this model as `stacked_hybrid_v4` (src/model/stacked_hybrid.py).

## 0. Scheme, checks and caveat

Men's matches get the **global stacker** (v3.1 logit, tournament form gap, last-5 form gap, is_female; fit on all genders). Women's matches get the **women-only stacker** (same inputs minus the flag; fit on women's matches only). C=1.0. For month M both are fit only on level-1 v3.1 out-of-sample predictions for matches before the first day of M; under 200 earlier rows (all rows for the men's part, women's rows for the women's part) v3.1 passes through (in the common set: men 209, women 109, WBBL 1).

**Selection caveat:** this candidate was chosen after the per-gender round showed which stacker wins for each gender. Its rows equal the parents' rows by construction (routing check: men max |hybrid - global| = 0.0e+00, women max |hybrid - per-gender| = 0.0e+00). The men's and women's checks below are therefore met partly by selection; the clean out-of-sample test is the live WBBL 2026 season.

Women's component stability: 25 fits from 2024-08; sign flips logit 0, form_tourn 2, form_last5 0 (limit 2).

Leakage (scrambled current-block labels, blocks 2026-06, 2026-07, 2026-10, n=639): max |diff| v3.1 0.0e+00, hybrid 0.0e+00 -> pass.

Common set: **5039** matches (3924 men, 1115 women; WBBL 80, IPL 243), 2023-05-01 .. 2026-10-21.

## 1. Adoption bar verdict: **PASS**

| check | measure | value [95% block-bootstrap CI] | result |
|---|---|---|---|
| WBBL: match or beat form | log_loss hybrid - form (n=80) | +0.0162 [-0.0283, +0.0360] | match (CI includes 0) |
| WBBL: match or beat form | brier hybrid - form (n=80) | +0.0080 [-0.0133, +0.0177] | match (CI includes 0) |
| Men: no regression vs global stacker | log_loss hybrid - global (n=3924) | +0.0000 [+0.0000, +0.0000] | pass |
| Men: no regression vs global stacker | brier hybrid - global (n=3924) | +0.0000 [+0.0000, +0.0000] | pass |
| Women: no regression vs v3.1 | log_loss hybrid - v3.1 (n=1115) | -0.0059 [-0.0127, +0.0008] | pass |
| Women: no regression vs v3.1 | brier hybrid - v3.1 (n=1115) | -0.0030 [-0.0058, -0.0002] | pass |

Negative deltas mean the hybrid is better. WBBL passes when the interval includes or lies below zero; men and women are judged on the point estimate.

**Context** (log_loss deltas): overall hybrid - global -0.0016 [-0.0032, +0.0000]; overall hybrid - v2 (production) -0.0082 [-0.0125, -0.0045]; women hybrid - form -0.0122 [-0.0266, +0.0036]; WBBL hybrid - v2 -0.0189 [-0.0314, -0.0015]; IPL hybrid - form -0.0095 [-0.0265, +0.0090].

Same WBBL rule applied to earlier models: global stacker - form +0.0192 [-0.0545, +0.0464]; v3.1 - form +0.0299 [-0.0132, +0.0436] (both would also 'match' at n=80).

## 2. Overall and per gender (common set)

### Overall

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 5039 | 0.5648 | 0.6782 | 0.2425 | 0.5392 |
| v3.1 pooled | 5039 | 0.5696 | 0.6749 | 0.2410 | 0.5392 |
| global stacker (men's benchmark) | 5039 | 0.5779 | 0.6715 | 0.2394 | 0.5392 |
| per-gender stacker | 5039 | 0.5825 | 0.6706 | 0.2390 | 0.5392 |
| hybrid: global men / women-only women (CANDIDATE) | 5039 | 0.5805 | 0.6699 | 0.2386 | 0.5392 |
| form_favourite (bar) | 5039 | 0.5862 | 0.6807 | 0.2434 | 0.5392 |

### Men

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 3924 | 0.5489 | 0.6848 | 0.2457 | 0.5293 |
| v3.1 pooled | 3924 | 0.5548 | 0.6831 | 0.2449 | 0.5293 |
| global stacker (men's benchmark) | 3924 | 0.5650 | 0.6784 | 0.2427 | 0.5293 |
| per-gender stacker | 3924 | 0.5675 | 0.6793 | 0.2431 | 0.5293 |
| hybrid: global men / women-only women (CANDIDATE) | 3924 | 0.5650 | 0.6784 | 0.2427 | 0.5293 |
| form_favourite (bar) | 3924 | 0.5726 | 0.6888 | 0.2473 | 0.5293 |

### Women

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 1115 | 0.6206 | 0.6548 | 0.2314 | 0.5740 |
| v3.1 pooled | 1115 | 0.6215 | 0.6459 | 0.2273 | 0.5740 |
| global stacker (men's benchmark) | 1115 | 0.6233 | 0.6471 | 0.2277 | 0.5740 |
| per-gender stacker | 1115 | 0.6350 | 0.6400 | 0.2243 | 0.5740 |
| hybrid: global men / women-only women (CANDIDATE) | 1115 | 0.6350 | 0.6400 | 0.2243 | 0.5740 |
| form_favourite (bar) | 1115 | 0.6341 | 0.6522 | 0.2298 | 0.5740 |

## 3. WBBL and IPL explicit

### WBBL (n=80)

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 80 | 0.6000 | 0.7080 | 0.2558 | 0.5625 |
| v3.1 pooled | 80 | 0.4875 | 0.7029 | 0.2548 | 0.5625 |
| global stacker (men's benchmark) | 80 | 0.4750 | 0.6922 | 0.2495 | 0.5625 |
| per-gender stacker | 80 | 0.5750 | 0.6891 | 0.2478 | 0.5625 |
| hybrid: global men / women-only women (CANDIDATE) | 80 | 0.5750 | 0.6891 | 0.2478 | 0.5625 |
| form_favourite (bar) | 80 | 0.6250 | 0.6729 | 0.2398 | 0.5625 |

### IPL (n=243)

| model | n | accuracy | log_loss | brier | home rate |
|---|---|---|---|---|---|
| v2 per-gender (PRODUCTION) | 243 | 0.4444 | 0.7258 | 0.2659 | 0.4979 |
| v3.1 pooled | 243 | 0.4691 | 0.7174 | 0.2618 | 0.4979 |
| global stacker (men's benchmark) | 243 | 0.4938 | 0.7017 | 0.2542 | 0.4979 |
| per-gender stacker | 243 | 0.4979 | 0.7008 | 0.2538 | 0.4979 |
| hybrid: global men / women-only women (CANDIDATE) | 243 | 0.4938 | 0.7017 | 0.2542 | 0.4979 |
| form_favourite (bar) | 243 | 0.5185 | 0.7112 | 0.2581 | 0.4979 |

### WBBL by season

| season | n | ll v2 | ll v3.1 | ll glob | ll pg | ll hyb | ll form | brier v2 | brier v3.1 | brier glob | brier pg | brier hyb | brier form |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2023 | 1 | 0.4236 | 0.5628 | 0.5620 | 0.5628 | 0.5628 | 0.4780 | 0.1193 | 0.1852 | 0.1849 | 0.1852 | 0.1852 | 0.1444 |
| 2024 | 40 | 0.7249 | 0.7086 | 0.6937 | 0.6950 | 0.6950 | 0.6882 | 0.2632 | 0.2576 | 0.2503 | 0.2507 | 0.2507 | 0.2472 |
| 2025 | 39 | 0.6980 | 0.7006 | 0.6940 | 0.6863 | 0.6863 | 0.6623 | 0.2518 | 0.2537 | 0.2504 | 0.2466 | 0.2466 | 0.2347 |

### WBBL calibration (5 buckets of 20%; P(home win))

| bucket | n v2 | pred v2 | act v2 | n v3.1 | pred v3.1 | act v3.1 | n glob | pred glob | act glob | n pg | pred pg | act pg | n hyb | pred hyb | act hyb | n form | pred form | act form |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0-20% | 0 | - | - | 0 | - | - | 0 | - | - | 0 | - | - | 0 | - | - | 0 | - | - |
| 20-40% | 3 | 0.368 | 1.000 | 3 | 0.391 | 1.000 | 0 | - | - | 5 | 0.371 | 0.800 | 5 | 0.371 | 0.800 | 14 | 0.354 | 0.500 |
| 40-60% | 52 | 0.528 | 0.558 | 69 | 0.513 | 0.536 | 70 | 0.525 | 0.557 | 63 | 0.517 | 0.508 | 63 | 0.517 | 0.508 | 45 | 0.486 | 0.489 |
| 60-80% | 25 | 0.681 | 0.520 | 8 | 0.652 | 0.625 | 10 | 0.628 | 0.600 | 12 | 0.686 | 0.750 | 12 | 0.686 | 0.750 | 21 | 0.645 | 0.762 |
| 80-100% | 0 | - | - | 0 | - | - | 0 | - | - | 0 | - | - | 0 | - | - | 0 | - | - |

### WBBL calibration (deciles, non-empty buckets; P(home win))

| bucket | n v2 | pred v2 | act v2 | n v3.1 | pred v3.1 | act v3.1 | n glob | pred glob | act glob | n pg | pred pg | act pg | n hyb | pred hyb | act hyb | n form | pred form | act form |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30- 40% | 3 | 0.368 | 1.000 | 3 | 0.391 | 1.000 | 0 | - | - | 5 | 0.371 | 0.800 | 5 | 0.371 | 0.800 | 14 | 0.354 | 0.500 |
| 40- 50% | 16 | 0.467 | 0.312 | 27 | 0.465 | 0.556 | 17 | 0.478 | 0.706 | 26 | 0.464 | 0.423 | 26 | 0.464 | 0.423 | 27 | 0.445 | 0.407 |
| 50- 60% | 36 | 0.555 | 0.667 | 42 | 0.544 | 0.524 | 53 | 0.541 | 0.509 | 37 | 0.554 | 0.568 | 37 | 0.554 | 0.568 | 18 | 0.548 | 0.611 |
| 60- 70% | 17 | 0.660 | 0.647 | 7 | 0.643 | 0.571 | 10 | 0.628 | 0.600 | 9 | 0.658 | 0.778 | 9 | 0.658 | 0.778 | 19 | 0.635 | 0.737 |
| 70- 80% | 8 | 0.726 | 0.250 | 1 | 0.713 | 1.000 | 0 | - | - | 3 | 0.772 | 0.667 | 3 | 0.772 | 0.667 | 2 | 0.740 | 1.000 |

## 4. Per league (common set; n >= 30, WBBL / IPL / Spring Challenge always)

| league_key | gender | n | ll v2 | ll v3.1 | ll glob | ll pg | ll hyb | ll form |
|---|---|---|---|---|---|---|---|---|
| vitality blast | male | 485 | 0.6913 | 0.6916 | 0.6887 | 0.6885 | 0.6887 | 0.6986 |
| indian premier league **(IPL)** | male | 243 | 0.7258 | 0.7174 | 0.7017 | 0.7008 | 0.7017 | 0.7112 |
| syed mushtaq ali trophy | male | 154 | 0.6803 | 0.6800 | 0.6797 | 0.6789 | 0.6797 | 0.7001 |
| maharaja trophy ksca | male | 128 | 0.6976 | 0.6978 | 0.6850 | 0.6837 | 0.6850 | 0.6805 |
| bangladesh premier league | male | 126 | 0.6704 | 0.6704 | 0.6615 | 0.6676 | 0.6615 | 0.6449 |
| big bash league | male | 123 | 0.6605 | 0.6622 | 0.6769 | 0.6776 | 0.6769 | 0.6802 |
| csa challenge | male | 115 | 0.6926 | 0.6928 | 0.6840 | 0.6836 | 0.6840 | 0.6776 |
| pakistan super league | male | 108 | 0.6784 | 0.6698 | 0.6628 | 0.6670 | 0.6628 | 0.6685 |
| icc men s world cup | male | 104 | 0.6066 | 0.6063 | 0.6092 | 0.6158 | 0.6092 | 0.6286 |
| international league | male | 102 | 0.7498 | 0.7402 | 0.7105 | 0.7104 | 0.7105 | 0.7412 |
| vitality blast women | female | 99 | 0.6705 | 0.6681 | 0.6634 | 0.6611 | 0.6611 | 0.6493 |
| caribbean premier league | male | 94 | 0.6942 | 0.6927 | 0.6678 | 0.6663 | 0.6678 | 0.6691 |
| tamil nadu premier league | male | 94 | 0.6958 | 0.6962 | 0.6880 | 0.6874 | 0.6880 | 0.6882 |
| sa league | male | 92 | 0.7037 | 0.6965 | 0.7159 | 0.7112 | 0.7159 | 0.7282 |
| major league cricket | male | 86 | 0.6669 | 0.6628 | 0.6705 | 0.6729 | 0.6705 | 0.6832 |
| womens big bash league **(WBBL)** | female | 80 | 0.7080 | 0.7029 | 0.6922 | 0.6891 | 0.6891 | 0.6729 |
| super smash | male | 78 | 0.7129 | 0.7263 | 0.7098 | 0.7082 | 0.7098 | 0.7341 |
| womens premier league | female | 66 | 0.7376 | 0.6944 | 0.7053 | 0.7062 | 0.7062 | 0.7289 |
| nepal premier league | male | 64 | 0.7162 | 0.7150 | 0.6926 | 0.6929 | 0.6926 | 0.6776 |
| delhi premier league | male | 60 | 0.6731 | 0.6704 | 0.6773 | 0.6777 | 0.6773 | 0.6917 |
| madhya pradesh league | male | 58 | 0.6785 | 0.6721 | 0.6707 | 0.6732 | 0.6707 | 0.6698 |
| icc womens world cup | female | 55 | 0.5462 | 0.5582 | 0.5625 | 0.5579 | 0.5579 | 0.6073 |
| spring challenge | female | 54 | 0.7022 | 0.7232 | 0.7097 | 0.7105 | 0.7105 | 0.7044 |
| legends league cricket | male | 52 | 0.7462 | 0.7543 | 0.7348 | 0.7326 | 0.7348 | 0.7783 |
| national cricket league | male | 52 | 0.6842 | 0.6842 | 0.6798 | 0.6788 | 0.6798 | 0.6700 |
| andhra premier league | male | 50 | 0.7095 | 0.7134 | 0.7163 | 0.7131 | 0.7163 | 0.7188 |
| kerala cricket league | male | 50 | 0.7017 | 0.7022 | 0.7045 | 0.7045 | 0.7045 | 0.7204 |
| womens super smash | female | 49 | 0.6609 | 0.6680 | 0.6628 | 0.6608 | 0.6608 | 0.6772 |
| icc women s world cup qualifier | female | 48 | 0.6060 | 0.5908 | 0.5987 | 0.5775 | 0.5775 | 0.6303 |
| lanka premier league | male | 47 | 0.7093 | 0.7068 | 0.7260 | 0.7311 | 0.7260 | 0.7701 |
| senior women s trophy | female | 46 | 0.6295 | 0.6422 | 0.6252 | 0.6051 | 0.6051 | 0.5898 |
| mumbai league | male | 40 | 0.7337 | 0.7416 | 0.7485 | 0.7427 | 0.7485 | 0.7641 |
| global canada | male | 39 | 0.7031 | 0.7088 | 0.6842 | 0.6820 | 0.6842 | 0.6887 |
| acc women s premier cup | female | 37 | 0.5034 | 0.5088 | 0.5254 | 0.4922 | 0.4922 | 0.5726 |
| pondicherry premier league | male | 36 | 0.6951 | 0.6936 | 0.6969 | 0.6962 | 0.6969 | 0.6904 |
| icc under womens world cup | female | 35 | 0.6902 | 0.6032 | 0.6171 | 0.6011 | 0.6011 | 0.6129 |
| max competition | male | 35 | 0.6130 | 0.6039 | 0.5962 | 0.6045 | 0.5962 | 0.5926 |
| shpageeza cricket league | male | 35 | 0.6758 | 0.6730 | 0.6739 | 0.6778 | 0.6739 | 0.6606 |
| vitality blast women league | female | 35 | 0.7385 | 0.7340 | 0.7457 | 0.7686 | 0.7686 | 0.7366 |
| top end series | male | 31 | 0.7009 | 0.7086 | 0.7288 | 0.7216 | 0.7288 | 0.7762 |

## 5. Confidence-band distribution (confident >= 0.65, moderate >= 0.55)

| slice | model | confident n / share / acc | moderate n / share / acc | close_call n / share / acc |
|---|---|---|---|---|
| all | v2 per-gender (PRODUCTION) | 732 / 14.5% / 67.3% | 2134 / 42.3% / 58.3% | 2173 / 43.1% / 51.0% |
| all | v3.1 pooled | 724 / 14.4% / 70.9% | 2186 / 43.4% / 57.6% | 2129 / 42.3% / 51.6% |
| all | global stacker (men's benchmark) | 549 / 10.9% / 71.2% | 2020 / 40.1% / 61.2% | 2470 / 49.0% / 52.0% |
| all | hybrid: global men / women-only women (CANDIDATE) | 667 / 13.2% / 72.0% | 1991 / 39.5% / 60.2% | 2381 / 47.3% / 52.3% |
| male | v2 per-gender (PRODUCTION) | 446 / 11.4% / 66.1% | 1673 / 42.6% / 57.4% | 1805 / 46.0% / 49.8% |
| male | v3.1 pooled | 513 / 13.1% / 67.3% | 1672 / 42.6% / 56.6% | 1739 / 44.3% / 50.9% |
| male | global stacker (men's benchmark) | 338 / 8.6% / 67.5% | 1513 / 38.6% / 60.3% | 2073 / 52.8% / 51.9% |
| male | hybrid: global men / women-only women (CANDIDATE) | 338 / 8.6% / 67.5% | 1513 / 38.6% / 60.3% | 2073 / 52.8% / 51.9% |
| female | v2 per-gender (PRODUCTION) | 286 / 25.7% / 69.2% | 461 / 41.3% / 61.8% | 368 / 33.0% / 56.8% |
| female | v3.1 pooled | 211 / 18.9% / 79.6% | 514 / 46.1% / 60.7% | 390 / 35.0% / 54.6% |
| female | global stacker (men's benchmark) | 211 / 18.9% / 77.3% | 507 / 45.5% / 63.7% | 397 / 35.6% / 52.6% |
| female | hybrid: global men / women-only women (CANDIDATE) | 329 / 29.5% / 76.6% | 478 / 42.9% / 59.8% | 308 / 27.6% / 55.2% |
| wbbl | v2 per-gender (PRODUCTION) | 22 / 27.5% / 50.0% | 27 / 33.8% / 59.3% | 31 / 38.8% / 67.7% |
| wbbl | v3.1 pooled | 3 / 3.8% / 66.7% | 35 / 43.8% / 51.4% | 42 / 52.5% / 45.2% |
| wbbl | global stacker (men's benchmark) | 3 / 3.8% / 66.7% | 26 / 32.5% / 61.5% | 51 / 63.7% / 39.2% |
| wbbl | hybrid: global men / women-only women (CANDIDATE) | 8 / 10.0% / 62.5% | 36 / 45.0% / 52.8% | 36 / 45.0% / 61.1% |
| ipl | v2 per-gender (PRODUCTION) | 13 / 5.3% / 53.8% | 106 / 43.6% / 42.5% | 124 / 51.0% / 45.2% |
| ipl | v3.1 pooled | 15 / 6.2% / 53.3% | 104 / 42.8% / 43.3% | 124 / 51.0% / 49.2% |
| ipl | global stacker (men's benchmark) | 1 / 0.4% / 0.0% | 78 / 32.1% / 48.7% | 164 / 67.5% / 50.0% |
| ipl | hybrid: global men / women-only women (CANDIDATE) | 1 / 0.4% / 0.0% | 78 / 32.1% / 48.7% | 164 / 67.5% / 50.0% |

## 6. Band honesty, hybrid (promise = band floor; honest = hit rate >= promise)

| slice | band | promise | n | mean stated p_max | hit rate [95% Wilson] | honest |
|---|---|---|---|---|---|---|
| male | confident | 0.65 | 338 | 0.695 | 0.675 [0.623, 0.722] | yes |
| male | moderate | 0.55 | 1513 | 0.587 | 0.603 [0.579, 0.628] | yes |
| male | close_call | 0.50 | 2073 | 0.524 | 0.519 [0.498, 0.541] | yes |
| female | confident | 0.65 | 329 | 0.726 | 0.766 [0.717, 0.808] | yes |
| female | moderate | 0.55 | 478 | 0.592 | 0.598 [0.554, 0.641] | yes |
| female | close_call | 0.50 | 308 | 0.525 | 0.552 [0.496, 0.607] | yes |
| wbbl | confident | 0.65 | 8 | 0.715 | 0.625 [0.306, 0.863] | **no** |
| wbbl | moderate | 0.55 | 36 | 0.588 | 0.528 [0.370, 0.680] | **no** |
| wbbl | close_call | 0.50 | 36 | 0.526 | 0.611 [0.449, 0.752] | yes |
| ipl | confident | 0.65 | 1 | 0.653 | 0.000 [0.000, 0.793] | **no** |
| ipl | moderate | 0.55 | 78 | 0.580 | 0.487 [0.379, 0.596] | **no** |
| ipl | close_call | 0.50 | 164 | 0.522 | 0.500 [0.424, 0.576] | yes |

Men and women are the bar slices; WBBL and IPL are shown for context (small n).
