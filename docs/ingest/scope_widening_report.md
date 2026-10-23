# Report: Spring Challenge 2026 ingest + T20 women scope (2026-10-23)

Status: built, leakage suite green. Reports reviewed 2026-10-23; the decisions below
are applied (section "Decisions applied").

Companion files:
- `docs/ingest/spring_challenge_2026_merge_report.md` (+ `.json`) - staging/merge report
- `docs/ingest/entity_watch_t20_women_scope.md` - new teams / venues / tournaments, dedupe, league_key groups
- `src/data/merge_staging_dump.py`, `src/data/entity_watch.py` - the two new scripts

## A. Ingest

Dump inspection: the 8 files are phpMyAdmin per-table exports with CREATE TABLE under
alias names (`m`, `bat`, `bowl`, `fld`, `p`, `tps`, `team`, `tp`), ALTER TABLE
(PK / indexes / AUTO_INCREMENT) and INSERT. No DROP / TRUNCATE / DELETE. They were
NOT sourced into cricket_raw (that would have created junk alias tables); they were
loaded into staging db `cricket_sc` and merged by id.

| table | staged | id overlap | identical | changed | inserted | cricket_raw after |
|---|---|---|---|---|---|---|
| cricket__matches | 21 | 0 | 0 | 0 | 21 | 8,923 |
| cricket__player_batting_scores | 341 | 0 | 0 | 0 | 341 | 163,942 |
| cricket__player_bowling_scores | 341 | 0 | 0 | 0 | 341 | 161,422 |
| cricket__player_fielding_scores | 341 | 0 | 0 | 0 | 341 | 158,877 |
| cricket__players | 639 | 0 | 0 | 0 | 639 | 357,523 |
| cricket__team_play_stats | 40 | 0 | 0 | 0 | 40 | 16,558 |
| cricket__teams | 9 | 9 | 9 | 0 | 0 | 1,285 |
| cricket__tournament_points | 9 | 0 | 0 | 0 | 9 | 1,998 |

No column drift between dump and cricket_raw. Same id space confirmed: the 9 teams are
byte-identical duplicates; every other staged id is above the local max id (the site DB
moved on between the July snapshot and this dump: local matches max id 8920, dump
10078-10098).

`land_l0 --force --tables <7 tables>` re-landed exactly those tables (cricket__teams
untouched); all Parquet row counts match MariaDB. `land_l0` gained a `--tables` option
that carries the other tables' manifest entries forward.

**Gap:** the dump has no `cricket__tournaments` file and cricket_raw has no row for
tournament 1906 (T20 Spring Challenge 2026). L1 warns, dim_tournament has no row,
`league_key` is NULL for those 21 matches (NULL-safe downstream; the Spring Challenge
league window will not include 2026 until the row arrives). Please export the
`cricket__tournaments` row for id 1906 (and ideally the whole table) the same way.

## B. Scope widening

- L1 scope is `format='t20' AND gender IN ('male','female')` (`build_l1 --genders`,
  default male,female). `gender` is in dim_match, the L2 dim_match view, L3
  (`gender` column after league_key) and the payload (`match.gender`,
  `venue_stats.sample_format` = "T20 men" / "T20 women").
- **venue_stats is gender-scoped** (venue_key, gender, as_of_date): WBBL plays at BBL
  grounds, so a mixed sample would have dragged men's venue numbers down. Men's venue
  snapshots are unchanged (3,695). The leakage test and the payload sample-range helper
  recount with the same gender filter.
- **Team dedupe is now exact-name WITHIN match gender.** The first rebuild exposed a
  defect the men-only scope could not: the source reuses club names across genders
  without a "Women" suffix. Women's Barbados Royals (132/316), Trinbago Knight Riders
  (134/318), Guyana Amazon Warriors (133/317), Northern Brave (434) and the 2024 ACT
  side (353) were being folded into the men's ids. Fixed; the entity watch has a
  mechanical guard (section 1d) that lists every remap with both genders - 17 remaps,
  0 cross-gender. dim_team carries `team_gender`.
- **bridge_entity:** odds names that now resolve to two ids (men + women) are settled
  by the same-date fixture pair (144 links use it). One previously linked priced match
  (odds 550, TKR v Barbados Royals, 2023-09-07) is a men's + women's double-header on
  the same date: genuinely ambiguous, now a Tier-2 review candidate instead of a silent
  link. Priced links: 70 (60 men + 3 women in match_odds_devig; 61 before).
- Payload: prediction training set is same-gender (men's demo payloads unchanged).
- Men's layers unchanged by the widening: 4,748 L3 rows, 28,383 team_form rows,
  3,695 venue snapshots, all 531 men's team ids retained.

Leakage suite: **11/11 PASS** (`pytest tests/test_leakage.py`), after each rebuild.

## Numbers requested

**WBBL present (women, T20):**

| tournament_id | name | matches | completed | dates |
|---|---|---|---|---|
| 309 | Womens Big Bash League, 2023 | 59 | 59 | 2023-10-19 .. 2023-12-02 |
| 765 | Womens Big Bash League, 2024 | 43 | 43 | 2024-10-27 .. 2024-12-01 |
| 1316 | Womens Big Bash League, 2025 | 43 | 43 | 2025-11-09 .. 2025-12-13 |

WBBL 2026 is not in the data yet (no fixtures). league_key `womens big bash league`
groups all three; men's BBL is a separate `big bash league` (4 seasons).

**T20 Spring Challenge 2026 (tournament 1906):** 21 matches, 2026-10-12 .. 2026-10-21,
21 status=completed, 20 decided (10084 has no winner: abandoned), 6 venues. league_key
`spring challenge` groups 2024 (776) + 2025 (1325); 2026 joins once the tournament row
exists.

Player-score coverage: 16 of 21 matches have batting/bowling rows (19-22 each,
i.e. both innings); matches 10078-10081 (the four 12 Oct openers) and 10084
(abandoned) have **0** batting/bowling rows in the dump while their rosters (26-35
cricket__players rows) are present. Worth re-exporting those four if the site has them.
Ball-by-ball: none (0 over_summaries) - expected.

**Ball-by-ball coverage, women overall:** 408 of 1,424 matches (29%; 408 of 1,406
completed) have ball rows (2023: 11, 2024: 155, 2025: 139, 2026: 103) vs 2,218 of
4,748 for men (47%). Phase features are NULL where absent; L3 women rows with home
phase features: 539 of 1,424. Score tables cover 1,248 women's matches.

**New totals (L1 dim_match, after dropping the 956 duplicate):**

| gender | matches | completed | decided (winner) |
|---|---|---|---|
| male | 4,748 | 4,601 | 4,036 |
| female | 1,424 | 1,406 | 1,250 |
| total | 6,172 | 6,007 | 5,286 |

## Entity watch - items for your decision (nothing merged automatically)

1. **ACT identity across editions:** 2024 Spring Challenge ACT side = team 353
   "Australian Capital Territory" (code ACT-W); 2025 and 2026 = team 738 "ACT Meteors
   Women". Different names, so not merged. Alias 353 -> 738 would connect the history
   (bridge-style approved alias). Men's 671 "Australian Capital Territory" (Top End T20)
   stays separate.
2. **Spring Challenge 2026 venues:** Blacktown International Sportspark (6), Bankstown
   Oval (5), Sydney Olympic Park (4), "Cricket Central" (3, city = "Australia"),
   Hurstville Oval (2), "1 Raby Rd" (1, an address, not a ground name). Cricket Central
   and 1 Raby Rd are new keys with no dim_venue counterpart to merge into.
3. **Venue variants (women's grounds, name differs so revise_l1 did not merge):**
   Junction Oval has three keys ("CitiPower Centre Junction Oval" 9, "Cricket Victoria"
   10, "Junction Oval, St Kilda, Melbourne" 9, plus men's "Junction Oval" 1); Albert Park
   Suva has two ("Albert Park" 10, "Albert Park 2, Suva" 10). revise_l1 also flags 7
   name-match/city-conflict pairs (Sydney Cricket Ground, Bellerive Oval, Kensington
   Oval, Zahur Ahmed Chowdhury, Rajiv Gandhi, Queen's Park, The County Ground).
4. **Team duplicates, same gender:** 82 token-subset candidates in entity watch 1b
   (mostly senior vs A / U19 / franchise vs state: distinct). No exact-name same-gender
   duplicate survives the dedupe. The 9 Spring Challenge teams are all canonical
   single ids (190-197, 738).
5. **Bridge review:** odds 550 (TKR v Barbados Royals 2023-09-07, men's/women's
   double-header) and the pre-existing Gujarat Giants -> Gujarat Greats spelling variant
   in `data/lake/l1/bridge/_review_candidates.csv`.
6. 117 new tournaments, 186 new teams, 68 new canonical venues entered L1 (full lists
   in the entity watch).

## Decisions applied (2026-10-23)

1. ACT 353 -> 738: approved cross-season alias in build_l1 (`APPROVED_TEAM_ALIASES`),
   canonical = 738 (8 matches vs 4). Build-time check: same match gender (female/female)
   and canonical has more matches, else abort. Evidence line in the L1 manifest
   (`dim_team_dedupe.approved_cross_season_aliases`). dim_team 717 -> 716.
2. Venues: `MANUAL_MERGES` in revise_l1 - Junction Oval (canonical CitiPower Centre
   Junction Oval key; "Cricket Victoria" and "Junction Oval, St Kilda, Melbourne" fold in,
   cities compatible) and Albert Park Suva ("Albert Park 2, Suva" folds into "Albert
   Park"). dim_venue 342 -> 339. The men's "Junction Oval" key (city=Melbourne, 1 match)
   stays separate and is now in the revise_l1 city-conflict flag list (8 flags).
3. Odds 550: `REJECTED_ODDS_LINKS` in build_bridge - never linked, never re-proposed;
   reconciliation now reads 70 linked + 1 review + 282 out-of-scope + 1 rejected = 354.
4. Training data unchanged: `validation.load_completed(gender="male")` is the default
   (4,036 completed men's matches, as before); the payload calls it with gender=None and
   filters per match. The men+women retrain is the next task.
5. Tournament row 1906: still missing; league_key stays NULL for SC 2026 until the
   cricket__tournaments dump is merged the same staged way (no invented league_key).

## Follow-ups flagged (not changed)

- `check_consistency_and_coverage.py` still describes the men-only scope.
