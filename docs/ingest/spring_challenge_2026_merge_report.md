# Merge report — spring_challenge_2026

- generated: 2026-10-23T11:26:53
- dump dir: `C:\Users\Corsair\cricket-predictions\data\raw\spring_challenge_2026`
- staging db: `cricket_sc`
- mode: **APPLIED (new rows inserted into cricket_raw)**

## 1. Dump inspection

| file | alias | CREATE | ALTER | INSERT stmts | row tuples | forbidden statements |
|---|---|---|---|---|---|---|
| cricket__matches.sql | `m` | 1 | 2 | 1 | 21 | none |
| cricket__player_batting_scores.sql | `bat` | 1 | 2 | 1 | 341 | none |
| cricket__player_bowling_scores.sql | `bowl` | 1 | 2 | 2 | 341 | none |
| cricket__player_fielding_scores.sql | `fld` | 1 | 2 | 1 | 341 | none |
| cricket__players.sql | `p` | 1 | 2 | 2 | 639 | none |
| cricket__team_play_stats.sql | `tps` | 1 | 2 | 1 | 40 | none |
| cricket__teams.sql | `team` | 1 | 2 | 1 | 9 | none |
| cricket__tournament_points.sql | `tp` | 1 | 2 | 1 | 9 | none |

Dumps are CREATE TABLE (alias name) + ALTER TABLE (PK/indexes/AUTO_INCREMENT) + INSERT. No DROP/TRUNCATE. Sourcing them into cricket_raw directly would have created junk alias tables; they were loaded into the staging db instead.

## 2. Merge per table

| table | staged | raw rows before | raw max id before | staged id range | already present (identical) | present but CHANGED (kept existing) | inserted | raw rows after |
|---|---|---|---|---|---|---|---|---|
| cricket__matches | 21 | 8,902 | 8920 | 10078–10098 | 0 | 0 | 21 | 8923 |
| cricket__player_batting_scores | 341 | 163,601 | 163768 | 183667–185568 | 0 | 0 | 341 | 163942 |
| cricket__player_bowling_scores | 341 | 161,081 | 161219 | 181118–183019 | 0 | 0 | 341 | 161422 |
| cricket__player_fielding_scores | 341 | 158,536 | 158614 | 178513–180414 | 0 | 0 | 341 | 158877 |
| cricket__players | 639 | 356,884 | 357510 | 400494–403811 | 0 | 0 | 639 | 357523 |
| cricket__team_play_stats | 40 | 16,518 | 16540 | 18449–18636 | 0 | 0 | 40 | 16558 |
| cricket__teams | 9 | 1,285 | 1296 | 190–738 | 9 | 0 | 0 | 1285 |
| cricket__tournament_points | 9 | 1,989 | 2005 | 2288–2296 | 0 | 0 | 9 | 1998 |

## 3. Column drift (dump vs cricket_raw)

None — every dump column exists in cricket_raw and vice versa.

## 4. Changed rows (same id, different content — NOT overwritten)

None — every overlapping id is a byte-identical duplicate.
