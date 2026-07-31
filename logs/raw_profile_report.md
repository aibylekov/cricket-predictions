# Raw DB profile — `cricket_raw`

- Server: `12.3.2-MariaDB`
- Tables profiled: **32** (prefixes: `cricket__`, `odd_`, `odds__`)
- Total rows: **2,690,838**
- Read-only profile (Phase 1.1). `cricket_raw` was not modified.

## Summary

| Table | Rows | Date range |
|---|---:|---|
| `cricket__associations` | 49 | 2022-12-21T14:42:20 → 2026-06-04T18:20:04 |
| `cricket__betting_live_tips` | 5,796 | 2024-03-21T14:42:54 → 2026-07-15T16:32:55 |
| `cricket__matches` | 8,902 | 2022-10-03T08:00:00 → 2026-11-02T09:00:00 |
| `cricket__odds` | 1,322 | 2023-02-17T18:50:33 → 2024-03-10T18:20:40 |
| `cricket__over_summaries` | 158,789 | 2023-11-28T18:46:20 → 2026-07-16T11:02:10 |
| `cricket__over_summary_balls` | 971,009 | 1970-01-01T05:01:30 → 2026-07-16T11:02:11 |
| `cricket__over_summary_batsmans` | 352,986 | 2023-11-28T18:46:20 → 2026-07-16T11:02:21 |
| `cricket__over_summary_bowlers` | 159,445 | 2023-11-28T18:46:20 → 2026-07-16T11:02:10 |
| `cricket__over_under_betting_tips` | 3,615 | 2024-02-29T16:07:21 → 2026-07-16T16:27:11 |
| `cricket__players` | 356,884 | 2022-12-21T15:18:18 → 2026-07-16T17:18:09 |
| `cricket__player_batting_scores` | 163,601 | 2022-12-21T16:15:10 → 2026-07-16T17:16:11 |
| `cricket__player_bowling_scores` | 161,081 | 2022-12-21T16:15:10 → 2026-07-16T17:16:11 |
| `cricket__player_fielding_scores` | 158,536 | 2022-12-21T16:15:10 → 2026-07-16T16:58:09 |
| `cricket__predictions` | 8,847 | 2023-07-18T17:13:37 → 2026-07-18 |
| `cricket__prediction_sites` | 6,694 | 2026-01-28T19:03:44 → 2026-01-28T19:03:45 |
| `cricket__teams` | 1,285 | 2022-12-21T15:18:18 → 2026-07-16T16:25:26 |
| `cricket__team_play_stats` | 16,518 | 2022-12-21T15:18:18 → 2026-07-16T17:18:09 |
| `cricket__tournaments` | 1,696 | 2014-05-06T15:15:00 → 2026-11-02T00:00:00 |
| `cricket__tournament_points` | 1,989 | 2022-12-21T15:15:25 → 2026-07-16T11:02:07 |
| `cricket__weather_conditions` | 141,163 | 2023-07-19T18:58:36 → 2026-07-16T17:14:58 |
| `odds__bettilt_matches` | 0 | — |
| `odds__bettilt_odds` | 0 | — |
| `odds__onexbet_matches` | 33 | 2026-07-16T17:15:00 → 2026-07-24T23:00:00 |
| `odds__onexbet_odds` | 66 | 2026-07-16T17:15:00 → 2026-07-16T17:15:00 |
| `odds__parimatch_matches` | 0 | — |
| `odds__parimatch_odds` | 0 | — |
| `odd_markets` | 1 | 2023-05-18T12:08:22 → 2023-05-18T12:08:22 |
| `odd_matches` | 9,504 | 2023-05-21T15:30:00 → 2026-07-20T18:00:00 |
| `odd_match_odds` | 1,020 | 2023-05-28T22:45:25 → 2026-07-16T17:15:01 |
| `odd_outcomes` | 2 | 2023-05-18T12:12:13 → 2023-05-18T12:12:13 |
| `odd_sports` | 1 | 2023-05-18T11:39:04 → 2023-05-18T11:39:04 |
| `odd_vendors` | 4 | 2023-05-18T11:40:26 → 2026-02-24T15:39:40 |

## `cricket__associations`

- Rows: **49**
- Columns: **9**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `key` | varchar(255) | no | 0 | 0.0% |
| `code` | varchar(255) | yes | 0 | 0.0% |
| `name` | varchar(255) | no | 0 | 0.0% |
| `country` | text | no | 0 | 0.0% |
| `parent` | varchar(255) | yes | 39 | 79.6% |
| `active` | tinyint(1) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2022-12-21T14:42:20 | 2026-05-30T23:15:06 |
| `updated_at` | 2022-12-21T14:43:13 | 2026-06-04T18:20:04 |

## `cricket__betting_live_tips`

- Rows: **5,796**
- Columns: **7**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `prediction_id` | bigint(20) | no | 0 | 0.0% |
| `type` | varchar(191) | no | 0 | 0.0% |
| `title` | varchar(191) | no | 0 | 0.0% |
| `description` | text | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2024-03-21T14:42:54 | 2026-07-15T16:32:55 |
| `updated_at` | 2024-03-21T14:42:54 | 2026-07-15T16:32:55 |

## `cricket__matches`

- Rows: **8,902**
- Columns: **33**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `key` | varchar(255) | no | 0 | 0.0% |
| `tournament_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `name` | varchar(255) | no | 0 | 0.0% |
| `short_name` | varchar(255) | no | 0 | 0.0% |
| `sub_title` | varchar(255) | no | 0 | 0.0% |
| `team_a` | bigint(20) unsigned | no | 0 | 0.0% |
| `team_a_winning_probability` | tinyint(4) | yes | 3,244 | 36.4% |
| `team_b` | bigint(20) unsigned | no | 0 | 0.0% |
| `team_b_winning_probability` | tinyint(4) | yes | 3,244 | 36.4% |
| `start_at` | datetime | yes | 0 | 0.0% |
| `venue` | text | no | 0 | 0.0% |
| `metric_group` | varchar(255) | no | 0 | 0.0% |
| `status` | varchar(255) | no | 0 | 0.0% |
| `winner` | varchar(255) | yes | 1,490 | 16.7% |
| `messages` | text | yes | 0 | 0.0% |
| `gender` | varchar(255) | no | 0 | 0.0% |
| `sport` | varchar(255) | no | 0 | 0.0% |
| `format` | varchar(255) | no | 0 | 0.0% |
| `title` | varchar(255) | no | 0 | 0.0% |
| `play_status` | varchar(255) | no | 0 | 0.0% |
| `start_at_local` | datetime | yes | 0 | 0.0% |
| `toss` | text | yes | 590 | 6.6% |
| `notes` | text | yes | 0 | 0.0% |
| `player_of_match` | varchar(255) | yes | 0 | 0.0% |
| `result` | varchar(255) | yes | 0 | 0.0% |
| `result_type` | varchar(255) | yes | 0 | 0.0% |
| `target_balls` | int(10) unsigned | yes | 1,079 | 12.1% |
| `target_runs` | int(10) unsigned | yes | 8,902 | 100.0% |
| `target_dl_applied` | tinyint(1) | yes | 1,239 | 13.9% |
| `weather` | varchar(191) | yes | 1,372 | 15.4% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `start_at` | 2022-10-03T08:00:00 | 2026-11-01T20:00:00 |
| `gender` | female | male |
| `start_at_local` | 2022-10-03T16:00:00 | 2026-11-02T09:00:00 |
| `created_at` | 2022-12-21T15:18:18 | 2026-07-16T16:25:43 |
| `updated_at` | 2022-12-21T15:19:24 | 2026-07-16T17:18:09 |

## `cricket__odds`

- Rows: **1,322**
- Columns: **7**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `match_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `team_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `odds` | varchar(255) | no | 0 | 0.0% |
| `result_prediction` | varchar(255) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2023-02-17T18:50:33 | 2024-03-05T21:13:47 |
| `updated_at` | 2023-02-17T18:50:33 | 2024-03-10T18:20:40 |

## `cricket__over_summaries`

- Rows: **158,789**
- Columns: **15**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `match_id` | bigint(20) | no | 0 | 0.0% |
| `inning_key` | varchar(255) | no | 0 | 0.0% |
| `team` | varchar(255) | no | 0 | 0.0% |
| `over` | int(11) | no | 0 | 0.0% |
| `runs` | int(11) | no | 0 | 0.0% |
| `wickets` | int(11) | no | 0 | 0.0% |
| `match_score` | varchar(255) | no | 0 | 0.0% |
| `match_current_run_rate` | varchar(255) | no | 0 | 0.0% |
| `match_runs` | int(11) | no | 0 | 0.0% |
| `match_wickets` | int(11) | no | 0 | 0.0% |
| `req_run_rate` | varchar(255) | no | 0 | 0.0% |
| `req_runs_balls` | int(11) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2023-11-28T18:46:20 | 2026-07-16T10:58:10 |
| `updated_at` | 2023-11-28T18:46:20 | 2026-07-16T11:02:10 |

## `cricket__over_summary_balls`

- Rows: **971,009**
- Columns: **13**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `over_summary_id` | bigint(20) | no | 0 | 0.0% |
| `key` | varchar(255) | no | 0 | 0.0% |
| `comment` | varchar(255) | yes | 3 | 0.0% |
| `ball_type` | varchar(255) | no | 0 | 0.0% |
| `innings` | varchar(255) | no | 0 | 0.0% |
| `wicket` | varchar(255) | yes | 0 | 0.0% |
| `ball` | varchar(255) | no | 0 | 0.0% |
| `runs` | int(11) | no | 0 | 0.0% |
| `entry_time` | datetime | no | 0 | 0.0% |
| `updated` | datetime | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `entry_time` | 2023-11-28T15:11:57 | 2026-07-16T10:07:58 |
| `updated` | 1970-01-01T05:01:30 | 2026-07-16T10:07:58 |
| `created_at` | 2023-11-28T18:46:24 | 2026-07-16T11:02:11 |
| `updated_at` | 2023-11-28T18:46:24 | 2026-07-16T11:02:11 |

## `cricket__over_summary_batsmans`

- Rows: **352,986**
- Columns: **13**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `over_summary_id` | bigint(20) | no | 0 | 0.0% |
| `player_key` | varchar(255) | no | 0 | 0.0% |
| `player_name` | varchar(255) | yes | 0 | 0.0% |
| `dots` | int(11) | no | 0 | 0.0% |
| `sixes` | int(11) | no | 0 | 0.0% |
| `runs` | int(11) | no | 0 | 0.0% |
| `balls` | int(11) | no | 0 | 0.0% |
| `fours` | int(11) | no | 0 | 0.0% |
| `strike_rate` | varchar(255) | no | 0 | 0.0% |
| `is_dismissed` | tinyint(1) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2023-11-28T18:46:20 | 2026-07-16T10:58:10 |
| `updated_at` | 2023-11-28T19:52:10 | 2026-07-16T11:02:21 |

## `cricket__over_summary_bowlers`

- Rows: **159,445**
- Columns: **18**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `over_summary_id` | bigint(20) | no | 0 | 0.0% |
| `player_key` | varchar(255) | no | 0 | 0.0% |
| `player_name` | varchar(255) | yes | 0 | 0.0% |
| `dots` | int(11) | no | 0 | 0.0% |
| `sixes` | int(11) | no | 0 | 0.0% |
| `runs` | int(11) | no | 0 | 0.0% |
| `balls` | int(11) | no | 0 | 0.0% |
| `maiden_overs` | int(11) | no | 0 | 0.0% |
| `fours` | int(11) | no | 0 | 0.0% |
| `extras_wide` | int(11) | no | 0 | 0.0% |
| `wickets` | int(11) | no | 0 | 0.0% |
| `extras` | int(11) | no | 0 | 0.0% |
| `extras_noball` | int(11) | no | 0 | 0.0% |
| `overs` | varchar(255) | no | 0 | 0.0% |
| `economy` | varchar(255) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2023-11-28T18:46:20 | 2026-07-16T10:58:10 |
| `updated_at` | 2023-11-28T18:46:20 | 2026-07-16T11:02:10 |

## `cricket__over_under_betting_tips`

- Rows: **3,615**
- Columns: **10**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `prediction_id` | bigint(20) | no | 0 | 0.0% |
| `bookmaker_id` | bigint(20) | no | 0 | 0.0% |
| `type` | varchar(255) | no | 0 | 0.0% |
| `title` | varchar(255) | yes | 0 | 0.0% |
| `odds` | varchar(255) | no | 0 | 0.0% |
| `winning_tip` | varchar(255) | no | 0 | 0.0% |
| `description` | text | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2024-02-29T16:07:21 | 2026-07-16T16:27:11 |
| `updated_at` | 2024-02-29T16:07:21 | 2026-07-16T16:27:11 |

## `cricket__players`

- Rows: **356,884**
- Columns: **10**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `match_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `team_id` | bigint(20) unsigned | yes | 0 | 0.0% |
| `key` | varchar(255) | no | 0 | 0.0% |
| `name` | varchar(255) | no | 0 | 0.0% |
| `gender` | varchar(255) | no | 0 | 0.0% |
| `seasonal_role` | varchar(255) | no | 0 | 0.0% |
| `playing_xi` | tinyint(1) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `gender` | _new_kind | male |
| `created_at` | 2022-12-21T15:18:18 | 2026-07-16T16:25:40 |
| `updated_at` | 2022-12-21T16:15:10 | 2026-07-16T17:18:09 |

## `cricket__player_batting_scores`

- Rows: **163,601**
- Columns: **15**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `player_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `runs` | int(10) unsigned | yes | 0 | 0.0% |
| `balls` | int(10) unsigned | yes | 0 | 0.0% |
| `fours` | tinyint(3) unsigned | yes | 0 | 0.0% |
| `sixes` | tinyint(3) unsigned | yes | 0 | 0.0% |
| `dot_balls` | int(10) unsigned | yes | 2,865 | 1.8% |
| `strike_rate` | varchar(255) | yes | 0 | 0.0% |
| `overs` | varchar(255) | yes | 60,432 | 36.9% |
| `team_runs` | int(10) unsigned | yes | 60,432 | 36.9% |
| `wicket_number` | tinyint(3) | yes | 60,432 | 36.9% |
| `msg` | varchar(255) | yes | 60,432 | 36.9% |
| `ball_key` | varchar(255) | yes | 112,819 | 69.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2022-12-21T16:15:10 | 2026-07-16T16:42:09 |
| `updated_at` | 2022-12-21T16:15:10 | 2026-07-16T17:16:11 |

## `cricket__player_bowling_scores`

- Rows: **161,081**
- Columns: **12**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `player_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `balls` | int(10) unsigned | yes | 0 | 0.0% |
| `runs` | int(10) unsigned | yes | 0 | 0.0% |
| `economy` | varchar(255) | yes | 0 | 0.0% |
| `extras` | tinyint(3) unsigned | yes | 0 | 0.0% |
| `wickets` | tinyint(3) unsigned | yes | 0 | 0.0% |
| `maiden_overs` | tinyint(3) unsigned | yes | 0 | 0.0% |
| `overs` | varchar(255) | yes | 0 | 0.0% |
| `balls_breakup` | text | yes | 2,052 | 1.3% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2022-12-21T16:15:10 | 2026-07-16T16:42:09 |
| `updated_at` | 2022-12-21T16:15:10 | 2026-07-16T17:16:11 |

## `cricket__player_fielding_scores`

- Rows: **158,536**
- Columns: **7**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `player_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `catches` | tinyint(3) unsigned | yes | 0 | 0.0% |
| `stumpings` | tinyint(3) unsigned | yes | 0 | 0.0% |
| `runouts` | tinyint(3) unsigned | yes | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2022-12-21T16:15:10 | 2026-07-16T16:42:09 |
| `updated_at` | 2022-12-21T16:15:10 | 2026-07-16T16:58:09 |

## `cricket__predictions`

- Rows: **8,847**
- Columns: **47**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `site_id` | bigint(20) unsigned | yes | 0 | 0.0% |
| `bookmaker_id` | bigint(20) unsigned | yes | 0 | 0.0% |
| `match_key` | varchar(255) | yes | 1,961 | 22.2% |
| `team_a` | bigint(20) | yes | 6,886 | 77.8% |
| `team_b` | bigint(20) | yes | 6,886 | 77.8% |
| `tournament_id` | bigint(20) | yes | 6,886 | 77.8% |
| `time_start` | time | yes | 0 | 0.0% |
| `date_start` | date | yes | 0 | 0.0% |
| `our_prediction_title` | text | no | 0 | 0.0% |
| `title` | varchar(255) | yes | 0 | 0.0% |
| `slug` | varchar(255) | yes | 0 | 0.0% |
| `format` | varchar(191) | yes | 0 | 0.0% |
| `venue` | varchar(191) | yes | 22 | 0.2% |
| `city` | varchar(255) | yes | 1,984 | 22.4% |
| `match_number` | varchar(191) | yes | 0 | 0.0% |
| `match_preview` | text | yes | 0 | 0.0% |
| `weather_conditions` | text | yes | 0 | 0.0% |
| `venue_details` | text | yes | 0 | 0.0% |
| `winning_prediction` | text | no | 0 | 0.0% |
| `winning_prediction_is` | varchar(255) | no | 0 | 0.0% |
| `prediction_result` | varchar(255) | yes | 8,847 | 100.0% |
| `winner` | varchar(255) | yes | 163 | 1.8% |
| `toss` | text | yes | 0 | 0.0% |
| `toss_info` | text | yes | 0 | 0.0% |
| `host_score_and_rr` | varchar(255) | yes | 8,847 | 100.0% |
| `guest_score_and_rr` | varchar(255) | yes | 8,847 | 100.0% |
| `host_preview` | text | yes | 0 | 0.0% |
| `host_predicted_starting_xi` | text | yes | 0 | 0.0% |
| `guest_preview` | text | yes | 0 | 0.0% |
| `guest_predicted_starting_xi` | text | yes | 0 | 0.0% |
| `host_classifier` | varchar(255) | yes | 8,847 | 100.0% |
| `host_before_start_classifier` | varchar(255) | yes | 8,847 | 100.0% |
| `guest_classifier` | varchar(255) | yes | 8,847 | 100.0% |
| `guest_before_start_classifier` | varchar(255) | yes | 8,847 | 100.0% |
| `key_points` | text | yes | 0 | 0.0% |
| `meta_title` | varchar(255) | yes | 0 | 0.0% |
| `meta_description` | text | yes | 0 | 0.0% |
| `table_id` | int(10) unsigned | yes | 8,847 | 100.0% |
| `banner` | varchar(255) | yes | 8,839 | 99.9% |
| `schema` | text | yes | 8,846 | 100.0% |
| `status` | varchar(255) | no | 0 | 0.0% |
| `source` | varchar(20) | no | 0 | 0.0% |
| `created_by` | int(10) unsigned | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |
| `deleted_at` | timestamp | yes | 8,652 | 97.8% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `time_start` | 0:00:00 | 23:45:00 |
| `date_start` | 2023-07-21 | 2026-07-18 |
| `host_predicted_starting_xi` | (Batting XI, Fielding XI): Aasif Sheikh(w), Kushal Bhurtel, Rohit Paudel(c), Sundeep Jora, Lokesh Bam, Dipendra Singh Airee, Sompal Kami, Karan KC, Aarif Sheikh, Nandan Yadav, Gulsan Jha, Sandeep Lamichhane, Lalit Rajbanshi, Sher Malla, Basir Ahamad | Zulamry Mohdin, Ahmad Zubaidi Zulkifle, Muhamad Syahadat, Mohamad Fairuz Sharom, Shamsul Ikmal, Samiullah Khan, Hassan Masood, Muhammad Amir Azim, Syazrul Ezat, Fitri Sham, Muhammad Gulraiz |
| `guest_predicted_starting_xi` | ,David Warner (c),Salman Agha, Jason Roy, Reeza Hendricks,Azam Khan (wk),Moeen Ali,Khushdil Shah,Hasan Ali,Zahid Mehmood, Rizwanullah/Abbas Afridi, Mohammad Hamza/ Mir Hamza. | Zubayr Hamza, Reeza Hendricks, Rassie van der Dussen, Temba Bavuma, Mitchell Van Buuren, Delano Potgieter, Wandile Makwetu (wk), Beyers Swanepoel, Bjorn Fortuin (c), Codi Yusuf, Nqabayomzi Peter |
| `host_before_start_classifier` | — | — |
| `guest_before_start_classifier` | — | — |
| `created_at` | 2023-07-18T17:13:37 | 2026-07-16T16:41:43 |
| `updated_at` | 2023-09-16T17:16:05 | 2026-07-16T16:41:43 |
| `deleted_at` | 2023-09-16T17:16:05 | 2026-07-07T13:02:23 |

## `cricket__prediction_sites`

- Rows: **6,694**
- Columns: **6**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `prediction_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `site_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `bookmaker_id` | bigint(20) unsigned | yes | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2026-01-28T19:03:44 | 2026-01-28T19:03:45 |
| `updated_at` | 2026-01-28T19:03:44 | 2026-01-28T19:03:45 |

## `cricket__teams`

- Rows: **1,285**
- Columns: **10**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `key` | varchar(255) | no | 0 | 0.0% |
| `code` | varchar(255) | no | 0 | 0.0% |
| `name` | varchar(255) | no | 0 | 0.0% |
| `short_name` | varchar(191) | yes | 1 | 0.1% |
| `country_code` | varchar(255) | yes | 439 | 34.2% |
| `logo` | varchar(255) | yes | 80 | 6.2% |
| `is_national` | tinyint(1) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2022-12-21T15:18:18 | 2026-07-16T16:25:26 |
| `updated_at` | 2023-01-24T14:18:26 | 2026-07-16T16:25:26 |

## `cricket__team_play_stats`

- Rows: **16,518**
- Columns: **25**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `team_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `match_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `overs` | text | no | 0 | 0.0% |
| `is_completed` | tinyint(1) | no | 0 | 0.0% |
| `score_str` | varchar(255) | yes | 0 | 0.0% |
| `score_runs` | int(11) | yes | 0 | 0.0% |
| `score_balls` | int(11) | yes | 0 | 0.0% |
| `score_fours` | int(11) | yes | 0 | 0.0% |
| `score_sixes` | int(11) | yes | 0 | 0.0% |
| `score_dot_balls` | int(11) | yes | 0 | 0.0% |
| `score_run_rate` | varchar(255) | yes | 0 | 0.0% |
| `wickets` | int(11) | yes | 0 | 0.0% |
| `extra_runs` | int(11) | yes | 0 | 0.0% |
| `extra_bye` | int(11) | yes | 0 | 0.0% |
| `extra_leg_bye` | int(11) | yes | 0 | 0.0% |
| `extra_wide` | int(11) | yes | 0 | 0.0% |
| `extra_no_ball` | int(11) | yes | 0 | 0.0% |
| `extra_penalty` | varchar(255) | yes | 1,478 | 8.9% |
| `balls_breakup` | int(11) | yes | 0 | 0.0% |
| `dot_balls` | int(11) | yes | 0 | 0.0% |
| `wides` | int(11) | yes | 0 | 0.0% |
| `no_balls` | int(11) | yes | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2022-12-21T15:18:18 | 2026-07-16T16:12:45 |
| `updated_at` | 2022-12-21T16:15:10 | 2026-07-16T17:18:09 |

## `cricket__tournaments`

- Rows: **1,696**
- Columns: **23**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `key` | varchar(255) | yes | 71 | 4.2% |
| `name` | varchar(255) | no | 0 | 0.0% |
| `slug` | varchar(191) | yes | 0 | 0.0% |
| `short_name` | varchar(255) | no | 0 | 0.0% |
| `countries` | text | yes | 156 | 9.2% |
| `start_date` | datetime | yes | 0 | 0.0% |
| `gender` | varchar(255) | no | 0 | 0.0% |
| `point_system` | varchar(255) | yes | 156 | 9.2% |
| `rounds` | text | yes | 431 | 25.4% |
| `competition` | text | yes | 156 | 9.2% |
| `association_key` | varchar(255) | yes | 156 | 9.2% |
| `metric_group` | varchar(255) | yes | 156 | 9.2% |
| `sport` | varchar(255) | no | 0 | 0.0% |
| `is_date_confirmed` | tinyint(1) | no | 0 | 0.0% |
| `is_venue_confirmed` | tinyint(1) | no | 0 | 0.0% |
| `last_scheduled_match_date` | datetime | yes | 156 | 9.2% |
| `formats` | text | yes | 1,623 | 95.7% |
| `logo` | varchar(255) | yes | 1,684 | 99.3% |
| `rich_text` | text | yes | 1,233 | 72.7% |
| `active` | tinyint(1) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `start_date` | 2014-05-06T15:15:00 | 2026-08-19T15:30:00 |
| `gender` | female | male |
| `is_date_confirmed` | 1 | 1 |
| `last_scheduled_match_date` | 2022-11-10T05:30:00 | 2026-11-02T00:00:00 |
| `created_at` | 2022-12-21T15:14:07 | 2026-07-16T16:30:23 |
| `updated_at` | 2023-08-08T20:06:51 | 2026-07-16T16:30:23 |

## `cricket__tournament_points`

- Rows: **1,989**
- Columns: **15**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `tournament_id` | bigint(20) unsigned | no | 0 | 0.0% |
| `group_name` | varchar(255) | yes | 0 | 0.0% |
| `team_code` | varchar(255) | yes | 0 | 0.0% |
| `position_in_table` | int(10) unsigned | yes | 0 | 0.0% |
| `played` | int(10) unsigned | yes | 0 | 0.0% |
| `won` | int(10) unsigned | yes | 0 | 0.0% |
| `lost` | int(10) unsigned | yes | 0 | 0.0% |
| `tied` | int(10) unsigned | yes | 0 | 0.0% |
| `draw` | int(10) unsigned | yes | 0 | 0.0% |
| `no_result` | int(10) unsigned | yes | 0 | 0.0% |
| `points` | varchar(255) | yes | 0 | 0.0% |
| `net_run_rate` | varchar(255) | yes | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2022-12-21T15:15:25 | 2026-07-08T17:36:12 |
| `updated_at` | 2023-01-22T23:20:33 | 2026-07-16T11:02:07 |

## `cricket__weather_conditions`

- Rows: **141,163**
- Columns: **10**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `temperature` | varchar(255) | yes | 0 | 0.0% |
| `clouds` | varchar(255) | yes | 0 | 0.0% |
| `wind_speed` | varchar(255) | yes | 0 | 0.0% |
| `wind_direction` | varchar(255) | yes | 0 | 0.0% |
| `city` | varchar(255) | yes | 0 | 0.0% |
| `date` | varchar(255) | yes | 0 | 0.0% |
| `precipitation_milimeter` | varchar(255) | yes | 111,304 | 78.8% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `date` | 2023-07-19 15:00:00 | 2026-07-21 09:00:00 |
| `created_at` | 2023-07-19T18:58:36 | 2026-07-16T17:14:58 |
| `updated_at` | 2023-07-19T20:02:30 | 2026-07-16T17:14:58 |

## `odds__bettilt_matches`

- Rows: **0**
- Columns: **15**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `external_id` | bigint(20) | no | 0 | 0.0% |
| `scheduled` | datetime | no | 0 | 0.0% |
| `type` | varchar(191) | no | 0 | 0.0% |
| `virtual` | tinyint(1) | no | 0 | 0.0% |
| `sport` | varchar(191) | no | 0 | 0.0% |
| `category` | varchar(191) | no | 0 | 0.0% |
| `tournament` | varchar(191) | no | 0 | 0.0% |
| `team_a_name` | varchar(191) | no | 0 | 0.0% |
| `team_a_short_name` | varchar(191) | yes | 0 | 0.0% |
| `team_a_country_code` | varchar(191) | yes | 0 | 0.0% |
| `team_b_name` | varchar(191) | no | 0 | 0.0% |
| `team_b_short_name` | varchar(191) | yes | 0 | 0.0% |
| `team_b_country_code` | varchar(191) | yes | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `scheduled` | — | — |
| `created_at` | — | — |
| `updated_at` | — | — |

## `odds__bettilt_odds`

- Rows: **0**
- Columns: **12**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `match_external_id` | bigint(20) | no | 0 | 0.0% |
| `internal_market` | varchar(191) | yes | 0 | 0.0% |
| `market_id` | int(10) unsigned | no | 0 | 0.0% |
| `market` | varchar(191) | no | 0 | 0.0% |
| `specifier` | varchar(191) | yes | 0 | 0.0% |
| `internal_outcome` | varchar(191) | yes | 0 | 0.0% |
| `outcome_id` | int(10) unsigned | no | 0 | 0.0% |
| `outcome` | varchar(191) | no | 0 | 0.0% |
| `type` | varchar(191) | no | 0 | 0.0% |
| `value` | varchar(191) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | — | — |
| `updated_at` | — | — |

## `odds__onexbet_matches`

- Rows: **33**
- Columns: **8**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `external_id` | bigint(20) | no | 0 | 0.0% |
| `start_time` | datetime | no | 0 | 0.0% |
| `sport_id` | int(10) unsigned | no | 0 | 0.0% |
| `tournament_id` | varchar(191) | no | 0 | 0.0% |
| `team_a_name` | varchar(191) | no | 0 | 0.0% |
| `team_b_name` | varchar(191) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `start_time` | 2026-07-16T18:00:00 | 2026-07-24T23:00:00 |
| `created_at` | 2026-07-16T17:15:00 | 2026-07-16T17:15:00 |
| `updated_at` | 2026-07-16T17:15:00 | 2026-07-16T17:15:00 |

## `odds__onexbet_odds`

- Rows: **66**
- Columns: **8**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `match_external_id` | bigint(20) | no | 0 | 0.0% |
| `internal_market` | varchar(191) | yes | 0 | 0.0% |
| `internal_outcome` | varchar(191) | yes | 0 | 0.0% |
| `outcome` | varchar(191) | yes | 0 | 0.0% |
| `type` | varchar(191) | no | 0 | 0.0% |
| `value` | varchar(191) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2026-07-16T17:15:00 | 2026-07-16T17:15:00 |
| `updated_at` | 2026-07-16T17:15:00 | 2026-07-16T17:15:00 |

## `odds__parimatch_matches`

- Rows: **0**
- Columns: **13**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `external_id` | bigint(20) | no | 0 | 0.0% |
| `start_time` | datetime | no | 0 | 0.0% |
| `stage` | varchar(191) | no | 0 | 0.0% |
| `sport` | varchar(191) | no | 0 | 0.0% |
| `sport_id` | int(10) unsigned | no | 0 | 0.0% |
| `category` | varchar(191) | no | 0 | 0.0% |
| `category_id` | varchar(191) | no | 0 | 0.0% |
| `tournament` | varchar(191) | no | 0 | 0.0% |
| `tournament_id` | varchar(191) | no | 0 | 0.0% |
| `team_a_name` | varchar(191) | no | 0 | 0.0% |
| `team_b_name` | varchar(191) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `start_time` | — | — |
| `created_at` | — | — |
| `updated_at` | — | — |

## `odds__parimatch_odds`

- Rows: **0**
- Columns: **10**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `match_external_id` | bigint(20) | no | 0 | 0.0% |
| `internal_market` | varchar(191) | yes | 0 | 0.0% |
| `market_id` | varchar(191) | no | 0 | 0.0% |
| `market` | varchar(191) | no | 0 | 0.0% |
| `internal_outcome` | varchar(191) | yes | 0 | 0.0% |
| `outcome_id` | varchar(191) | no | 0 | 0.0% |
| `outcome` | varchar(191) | no | 0 | 0.0% |
| `value` | varchar(191) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | — | — |
| `updated_at` | — | — |

## `odd_markets`

- Rows: **1**
- Columns: **7**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `similar_names` | text | yes | 0 | 0.0% |
| `sport_id` | int(10) unsigned | no | 0 | 0.0% |
| `name` | varchar(191) | no | 0 | 0.0% |
| `generic_name` | varchar(191) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2023-05-18T12:08:22 | 2023-05-18T12:08:22 |
| `updated_at` | 2023-05-18T12:08:22 | 2023-05-18T12:08:22 |

## `odd_matches`

- Rows: **9,504**
- Columns: **7**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `sport_id` | int(10) unsigned | no | 0 | 0.0% |
| `start_time` | datetime | no | 0 | 0.0% |
| `team_home_name` | varchar(191) | no | 0 | 0.0% |
| `team_away_name` | varchar(191) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `start_time` | 2023-05-21T15:30:00 | 2026-07-20T18:00:00 |
| `created_at` | 2023-05-22T21:15:28 | 2026-07-16T12:14:37 |
| `updated_at` | 2023-05-22T21:15:28 | 2026-07-16T12:14:37 |

## `odd_match_odds`

- Rows: **1,020**
- Columns: **8**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `match_id` | int(10) unsigned | no | 0 | 0.0% |
| `vendor` | varchar(191) | no | 0 | 0.0% |
| `market` | varchar(191) | no | 0 | 0.0% |
| `name` | varchar(191) | no | 0 | 0.0% |
| `generic_name` | varchar(191) | yes | 0 | 0.0% |
| `value` | varchar(191) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `vendor` | 1xBet | Puntit |
| `created_at` | 2023-05-28T22:45:25 | 2026-07-16T17:15:01 |
| `updated_at` | 2023-05-28T22:45:25 | 2026-07-16T17:15:01 |

## `odd_outcomes`

- Rows: **2**
- Columns: **7**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `market_id` | int(10) unsigned | no | 0 | 0.0% |
| `name` | varchar(191) | no | 0 | 0.0% |
| `generic_name` | varchar(191) | no | 0 | 0.0% |
| `similar_names` | text | yes | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2023-05-18T12:12:13 | 2023-05-18T12:12:13 |
| `updated_at` | 2023-05-18T12:12:13 | 2023-05-18T12:12:13 |

## `odd_sports`

- Rows: **1**
- Columns: **6**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `name` | varchar(191) | no | 0 | 0.0% |
| `generic_name` | varchar(191) | no | 0 | 0.0% |
| `active` | tinyint(1) | no | 0 | 0.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `created_at` | 2023-05-18T11:39:04 | 2023-05-18T11:39:04 |
| `updated_at` | 2023-05-18T11:39:04 | 2023-05-18T11:39:04 |

## `odd_vendors`

- Rows: **4**
- Columns: **8**

| Column | Type | Nullable | Nulls | Null % |
|---|---|:--:|---:|---:|
| `id` | bigint(20) unsigned | no | 0 | 0.0% |
| `name` | varchar(191) | no | 0 | 0.0% |
| `generic_name` | varchar(191) | no | 0 | 0.0% |
| `modelName` | varchar(191) | no | 0 | 0.0% |
| `source_vendor_id` | bigint(20) unsigned | yes | 3 | 75.0% |
| `odds_offset` | decimal(10,2) | yes | 3 | 75.0% |
| `created_at` | timestamp | yes | 0 | 0.0% |
| `updated_at` | timestamp | yes | 0 | 0.0% |

**Date / datetime ranges**

| Column | Min | Max |
|---|---|---|
| `source_vendor_id` | 1 | 1 |
| `created_at` | 2023-05-18T11:40:26 | 2026-02-24T15:39:40 |
| `updated_at` | 2023-05-18T11:40:26 | 2026-02-24T15:39:40 |

## Source investigation

_Phase 1.1 targeted investigations (read-only). Re-running `src/data/inspect_sources.py` replaces this section._

### A) Odds lineage

#### `odd_matches`

```sql
CREATE TABLE `odd_matches` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `sport_id` int(10) unsigned NOT NULL,
  `start_time` datetime NOT NULL,
  `team_home_name` varchar(191) NOT NULL,
  `team_away_name` varchar(191) NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=9511 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

_Sample rows (odd_matches):_
```text
id=7 | sport_id=1 | start_time=2023-05-21T15:30:00 | team_home_name=Mumbai Indians | team_away_name=Sunrisers Hyderabad | created_at=2023-05-22T21:15:28 | updated_at=2023-05-22T21:15:28
id=8 | sport_id=1 | start_time=2023-05-21T20:25:00 | team_home_name=Royal Challengers Bangalore | team_away_name=Gujarat Titans | created_at=2023-05-22T21:15:28 | updated_at=2023-05-22T21:15:28
id=9 | sport_id=1 | start_time=2023-05-23T19:30:00 | team_home_name=Gujarat Titans | team_away_name=Chennai Super Kings | created_at=2023-05-22T21:15:28 | updated_at=2023-05-22T21:15:28
id=10 | sport_id=1 | start_time=2023-05-24T19:30:00 | team_home_name=Lucknow Super Giants | team_away_name=Mumbai Indians | created_at=2023-05-22T21:15:28 | updated_at=2023-05-22T21:15:28
id=11 | sport_id=1 | start_time=2023-05-26T19:30:00 | team_home_name=TBC | team_away_name=TBC | created_at=2023-05-22T21:15:28 | updated_at=2023-05-22T21:15:28
```

#### `odd_match_odds`

```sql
CREATE TABLE `odd_match_odds` (
  `match_id` int(10) unsigned NOT NULL,
  `vendor` varchar(191) NOT NULL,
  `market` varchar(191) NOT NULL,
  `name` varchar(191) NOT NULL,
  `generic_name` varchar(191) DEFAULT NULL,
  `value` varchar(191) NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

_Sample rows (odd_match_odds):_
```text
match_id=15 | vendor=Parimatch | market=Winner 2 Ways | name=Chennai Super Kings | generic_name=team_home_name | value=1.94 | created_at=2023-05-28T22:45:25 | updated_at=2023-05-28T22:45:25
match_id=15 | vendor=Parimatch | market=Winner 2 Ways | name=Gujarat Titans | generic_name=team_away_name | value=1.86 | created_at=2023-05-28T22:45:25 | updated_at=2023-05-28T22:45:25
match_id=89 | vendor=Parimatch | market=Winner 2 Ways | name=Durham | generic_name=team_home_name | value=1.94 | created_at=2023-06-23T22:45:27 | updated_at=2023-06-23T22:45:27
match_id=89 | vendor=Parimatch | market=Winner 2 Ways | name=Yorkshire | generic_name=team_away_name | value=1.8 | created_at=2023-06-23T22:45:27 | updated_at=2023-06-23T22:45:27
match_id=89 | vendor=Bettilt | market=Winner 2 Ways | name=Durham | generic_name=team_home_name | value=1.97 | created_at=2023-06-23T22:45:27 | updated_at=2023-06-23T22:45:27
```

#### `odd_markets`

```sql
CREATE TABLE `odd_markets` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `similar_names` text DEFAULT NULL,
  `sport_id` int(10) unsigned NOT NULL,
  `name` varchar(191) NOT NULL,
  `generic_name` varchar(191) NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `odd_markets_generic_name_unique` (`generic_name`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

_Sample rows (odd_markets):_
```text
id=1 | similar_names=["Winner 2 Ways", "winner (incl.super over)"] | sport_id=1 | name=Winner 2 Ways | generic_name=WINNER 2 WAYS | created_at=2023-05-18T12:08:22 | updated_at=2023-05-18T12:08:22
```

#### `odd_outcomes`

```sql
CREATE TABLE `odd_outcomes` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `market_id` int(10) unsigned NOT NULL,
  `name` varchar(191) NOT NULL,
  `generic_name` varchar(191) NOT NULL,
  `similar_names` text DEFAULT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `odd_outcomes_generic_name_unique` (`generic_name`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

_Sample rows (odd_outcomes):_
```text
id=1 | market_id=1 | name=Team home | generic_name=team_home_name | similar_names=["Win 1", "WINNER_HOME","Team 1 Wins"] | created_at=2023-05-18T12:12:13 | updated_at=2023-05-18T12:12:13
id=2 | market_id=1 | name=Team away | generic_name=team_away_name | similar_names=["Win 2", "WINNER_AWAY","Team 2 Wins"] | created_at=2023-05-18T12:12:13 | updated_at=2023-05-18T12:12:13
```

#### Market types in `odd_match_odds`

| Market | Rows | Distinct matches | Match-winner? |
|---|---:|---:|:--:|
| Winner 2 Ways | 1,020 | 354 | ✓ |

**Match-winner market present:** `Winner 2 Ways` — **354 matches** priced.

_Outcome prices per (match, vendor) for the winner market:_

| # outcomes/side | # (match,vendor) groups |
|---:|---:|
| 2 | 510 |

#### Vendors present in `odd_match_odds`

| Vendor | Rows | Distinct matches |
|---|---:|---:|
| Parimatch | 626 | 313 |
| 1xBet | 248 | 124 |
| Puntit | 132 | 66 |
| Bettilt | 14 | 7 |

#### Coverage over cricket T20 (men)

> `odd_matches` has **no cricket foreign key** — only team names + `start_time`. Coverage below is a heuristic join on `DATE(start)` + exact team-name match (either home/away orientation). This under-counts wherever names differ, which is precisely the gap `bridge_entity` (README §1.4) must close.

- Cricket fixtures in `odd_matches` (sport_id=1): **9,504**
- …that map to a **T20-male** cricket match (name+date): **4,044**
- **T20-male matches with actual winner odds:** **59** cricket matches (via 66 priced `odd_matches`)


### B) Ball-by-ball reality check

#### `cricket__over_summary_balls`

```sql
CREATE TABLE `cricket__over_summary_balls` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `over_summary_id` bigint(20) NOT NULL,
  `key` varchar(255) NOT NULL,
  `comment` varchar(255) DEFAULT NULL,
  `ball_type` varchar(255) NOT NULL,
  `innings` varchar(255) NOT NULL,
  `wicket` varchar(255) DEFAULT NULL,
  `ball` varchar(255) NOT NULL,
  `runs` int(11) NOT NULL,
  `entry_time` datetime NOT NULL,
  `updated` datetime NOT NULL,
  `created_at` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `cricket__over_summary_balls_over_summary_id_key_index` (`over_summary_id`,`key`)
) ENGINE=InnoDB AUTO_INCREMENT=971010 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
```

_Sample rows:_
```text
id=1 | over_summary_id=1 | key=567360 | comment=Ajaz Patel to Taijul Islam: No runs. | ball_type=normal | innings=a_1 | wicket= | ball=1 | runs=0 | entry_time=2023-11-28T16:11:17 | updated=2023-11-28T16:11:17 | created_at=2023-11-28T18:46:24 | updated_at=2023-11-28T18:46:24
id=2 | over_summary_id=1 | key=567424 | comment=Ajaz Patel to Taijul Islam: 1 run. | ball_type=normal | innings=a_1 | wicket= | ball=1 | runs=1 | entry_time=2023-11-28T16:11:17 | updated=2023-11-28T16:11:17 | created_at=2023-11-28T18:46:24 | updated_at=2023-11-28T18:46:24
id=3 | over_summary_id=1 | key=567488 | comment=Ajaz Patel to Shoriful Islam: 1 run. | ball_type=normal | innings=a_1 | wicket= | ball=1 | runs=1 | entry_time=2023-11-28T16:11:18 | updated=2023-11-28T16:11:18 | created_at=2023-11-28T18:46:24 | updated_at=2023-11-28T18:46:24
id=4 | over_summary_id=1 | key=567552 | comment=Ajaz Patel to Taijul Islam: No runs. | ball_type=normal | innings=a_1 | wicket= | ball=1 | runs=0 | entry_time=2023-11-28T16:11:18 | updated=2023-11-28T16:11:18 | created_at=2023-11-28T18:46:24 | updated_at=2023-11-28T18:46:24
id=5 | over_summary_id=1 | key=567616 | comment=Ajaz Patel to Taijul Islam: No runs. | ball_type=normal | innings=a_1 | wicket= | ball=1 | runs=0 | entry_time=2023-11-28T16:11:18 | updated=2023-11-28T16:11:18 | created_at=2023-11-28T18:46:24 | updated_at=2023-11-28T18:46:24
```

#### Grain: is it one row per delivery?

Each `over_summary_id` groups the deliveries of one over. A T20 over is 6 legal balls (more when extras add re-bowls), so a mode of **6 rows per over** proves **per-delivery** grain — not per-over.

| Balls in over | # overs |
|---:|---:|
| 1 | 514 |
| 2 | 633 |
| 3 | 802 |
| 4 | 1,248 |
| 5 | 2,964 |
| 6 | 127,335 |
| 7 | 20,523 |
| 8 | 3,793 |
| 9 | 724 |
| 10 | 179 |
| 11 | 43 |
| 12 | 17 |
| 13 | 1 |

Columns proving per-delivery grain: `over_summary_id` (→ over via `cricket__over_summaries.over`), `ball` (ball # within over), `runs` (runs off that ball), `ball_type`/`wicket` (per-ball events), and `comment` (e.g. _"Ajaz Patel to Taijul Islam: No runs."_). **Batter & bowler are embedded in `comment` text, not separate columns** — L0 parsing will need to extract them (or join Roanuz ball keys).

#### The `1970-01-01` date

| Column | Rows before 2000 | % of table |
|---|---:|---:|
| `entry_time` | 0 | 0.0000% |
| `updated` | 82 | 0.0084% |
| `created_at` | 0 | 0.0000% |
| `updated_at` | 0 | 0.0000% |

- `updated`: **82** bad rows, **82 recoverable** via `over_summary_id → over_summaries.match_id → cricket__matches.start_at`.

The real per-ball timestamp is `entry_time` (clean). The stray epoch dates sit in the secondary `updated` column and are fully recoverable, so this is **not** a blocker for L0.
