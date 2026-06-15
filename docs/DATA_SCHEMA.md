# Football Intelligence — Data Schema

Version: v0.1
Status: Active
Scope: MVP 1 — AI Player Profile Generator

---

# 1. Dataset Overview

## Source

FBref Big 5 European Leagues

## Season

2024-25

## Leagues Covered

- Premier League (England)
- La Liga (Spain)
- Bundesliga (Germany)
- Serie A (Italy)
- Ligue 1 (France)

## File Location

```
data/players.csv
```

## Structure

- One row per player
- Estimated row count: 2,500 — 3,000 players
- Total columns: 19
- Encoding: UTF-8
- Delimiter: comma

## Source Tables

Player data is sourced and merged from four FBref stat category tables:

| FBref Table | Columns Contributed |
|---|---|
| Standard Stats | player_id, player_name, nationality, position, club, competition, age, appearances, minutes_played, goals, assists, non_penalty_goals |
| Shooting | xg, non_penalty_xg |
| Passing | xa, pass_completion_pct, progressive_passes |
| Possession | progressive_carries |

Merge key: `player_id`

---

# 2. Field Definitions

## player_id

Unique player identifier extracted from the FBref player URL.

Example: `e342ad68`

Used as the primary key for all lookups, merges, and cross-references.

---

## player_name

Full display name of the player as listed on FBref.

Example: `Son Heung-min`

---

## season

The football season the statistics belong to.

Fixed value for MVP 1: `2024-25`

---

## nationality

The player's country of nationality.

Stored as full country name in English.

Example: `South Korea`

FBref provides a 3-letter country code (e.g. `KOR`). This is expanded to the full country name during cleaning.

---

## position

The player's primary position.

Normalised to one of four values: `GK`, `DF`, `MF`, `FW`

FBref may return compound positions (e.g. `MF,FW`). The first listed position is used as the primary position.

---

## club

The player's current club as of the 2024-25 season.

Example: `Tottenham Hotspur`

---

## competition

The top-flight league the player's club competes in.

Example: `Premier League`

---

## age

The player's age as of the 2024-25 season.

Stored as an integer. FBref may provide age in `YY-DDD` format. This is converted to integer years during cleaning.

---

## appearances

Total number of matches the player appeared in during the 2024-25 season.

Sourced from the `MP` column in FBref Standard Stats.

---

## minutes_played

Total minutes played across all appearances in the 2024-25 season.

---

## goals

Total goals scored during the 2024-25 season.

Includes penalty goals.

---

## assists

Total assists registered during the 2024-25 season.

---

## non_penalty_goals

Total goals scored excluding penalties.

Used for percentile calculations and AI analysis to separate open-play goal threat from penalty conversion.

---

## xg

Expected Goals. The sum of shot quality values for all shots taken in the 2024-25 season.

Represents the probability-weighted number of goals a player was expected to score based on shot location and type.

---

## non_penalty_xg

Expected Goals excluding penalties.

Used in analytics and AI analysis to evaluate open-play goal threat independently of penalty situations.

---

## xa

Expected Assisted Goals (xAG). Sourced from the `xAG` column in FBref Passing.

Represents the expected goals value of passes that led directly to a shot. A chance-creation quality metric.

---

## pass_completion_pct

Percentage of attempted passes that were successfully completed.

Stored as a float. Example: `84.3`

---

## progressive_passes

Number of passes that moved the ball at least 10 yards closer to the opponent's goal, or any completed pass into the penalty area.

---

## progressive_carries

Number of carries that moved the ball at least 5 yards closer to the opponent's goal, or any carry into the penalty area.

---

# 3. Data Types

| Column | Type | Format |
|---|---|---|
| player_id | string | Alphanumeric, 8 characters |
| player_name | string | UTF-8 text |
| season | string | `YYYY-YY` |
| nationality | string | Full country name in English |
| position | string | Enum: `GK`, `DF`, `MF`, `FW` |
| club | string | UTF-8 text |
| competition | string | UTF-8 text |
| age | integer | Whole number |
| appearances | integer | Whole number |
| minutes_played | integer | Whole number |
| goals | integer | Whole number |
| assists | integer | Whole number |
| non_penalty_goals | integer | Whole number |
| xg | float | 2 decimal places |
| non_penalty_xg | float | 2 decimal places |
| xa | float | 2 decimal places |
| pass_completion_pct | float | 1 decimal place |
| progressive_passes | integer | Whole number |
| progressive_carries | integer | Whole number |

---

# 4. Validation Rules

## Identity

- `player_id` must be unique across the entire dataset. No duplicates permitted.
- `player_name` must not be null or empty.
- `player_id` must not be null or empty.

## Season

- `season` must equal `2024-25` for all rows in the MVP 1 dataset.

## Position

- `position` must be one of: `GK`, `DF`, `MF`, `FW`.
- No null values permitted.

## Age

- `age` must be a positive integer.
- Valid range: 15 – 45.
- Values outside this range are flagged for manual review.

## Appearances and Minutes

- `appearances` must be >= 0.
- `minutes_played` must be >= 0.
- `minutes_played` must be <= `appearances` × 95. (A player cannot play more than approximately 95 minutes per match.)
- Players with `minutes_played` = 0 are excluded from the dataset.

## Goal and Assist Metrics

- `goals`, `assists`, `non_penalty_goals` must be >= 0.
- `non_penalty_goals` must be <= `goals`.

## Expected Metrics

- `xg`, `non_penalty_xg`, `xa` must be >= 0.0.
- `non_penalty_xg` must be <= `xg`.

## Pass Completion

- `pass_completion_pct` must be between 0.0 and 100.0 inclusive.

## Progressive Actions

- `progressive_passes`, `progressive_carries` must be >= 0.

---

# 5. Missing Value Policy

## Minimum Playing Time Threshold

Players with fewer than **90 minutes played** are excluded from the dataset entirely.

Rationale: statistical metrics are unreliable and misleading for players with very limited appearances. A player with 1 appearance and 1 goal produces distorted percentile values.

## Field-Level Policy

| Column | Null Permitted | Action if Null |
|---|---|---|
| player_id | No | Exclude row |
| player_name | No | Exclude row |
| season | No | Exclude row |
| nationality | Yes | Store as `Unknown` |
| position | No | Exclude row |
| club | No | Exclude row |
| competition | No | Exclude row |
| age | No | Exclude row |
| appearances | No | Exclude row |
| minutes_played | No | Exclude row |
| goals | No | Default to `0` |
| assists | No | Default to `0` |
| non_penalty_goals | No | Default to `0` |
| xg | Yes | Default to `0.00` |
| non_penalty_xg | Yes | Default to `0.00` |
| xa | Yes | Default to `0.00` |
| pass_completion_pct | Yes | Store as null; exclude from pass-based percentiles |
| progressive_passes | Yes | Default to `0` |
| progressive_carries | Yes | Default to `0` |

## Notes

- xG and xA may be null for some FBref entries (particularly older or lower-profile competitions). Default to `0.00` rather than excluding the player.
- `pass_completion_pct` may be null for players who rarely pass (e.g. some forwards). Null is preserved rather than defaulting to `0`, to avoid distorting completion percentiles.
- Goalkeepers are retained in the dataset but excluded from outfield-player percentile calculations in the analytics layer.

---

# 6. Data Normalization Rules

## Player Names

- Stored in original UTF-8 encoding. Accented characters are preserved (e.g. `Vinícius Júnior`, `Kylian Mbappé`).
- Leading and trailing whitespace is stripped.
- No case conversion applied. Names are stored as they appear on FBref.

## Nationality

FBref provides 3-letter IOC country codes (e.g. `ENG`, `KOR`, `BRA`). These are expanded to full country names in English during cleaning.

Examples:
- `ENG` → `England`
- `KOR` → `South Korea`
- `BRA` → `Brazil`
- `FRA` → `France`

## Position

FBref may provide compound positions (e.g. `MF,FW`, `DF,MF`). Normalisation rule:

- Take the first listed position only.
- Map to the standard four-value enum.

Mapping:
- `GK` → `GK`
- `DF` → `DF`
- `MF` → `MF`
- `FW` → `FW`
- `MF,FW` → `MF`
- `DF,MF` → `DF`
- `FW,MF` → `FW`

## Competition Names

FBref competition identifiers are mapped to full league names:

| FBref Value | Stored As |
|---|---|
| `eng Premier League` | `Premier League` |
| `es La Liga` | `La Liga` |
| `de Bundesliga` | `Bundesliga` |
| `it Serie A` | `Serie A` |
| `fr Ligue 1` | `Ligue 1` |

## Age

FBref may provide age as `YY-DDD` (years and days). This is converted to integer years by taking the year component only.

Example: `28-192` → `28`

## Numeric Rounding

| Column | Rounding |
|---|---|
| xg | 2 decimal places |
| non_penalty_xg | 2 decimal places |
| xa | 2 decimal places |
| pass_completion_pct | 1 decimal place |

All integer fields are stored without decimals.

## Duplicate Handling

If a player appears more than once (e.g. transferred mid-season, listed separately per club), the row with the higher `minutes_played` value is retained. The player's club is set to the club they spent more time at.

---

# 7. Example Record

The following is an illustrative example record demonstrating the expected structure and value formats.

```
player_id:            e342ad68
player_name:          Son Heung-min
season:               2024-25
nationality:          South Korea
position:             FW
club:                 Tottenham Hotspur
competition:          Premier League
age:                  32
appearances:          34
minutes_played:       2847
goals:                14
assists:              9
non_penalty_goals:    13
xg:                   11.40
non_penalty_xg:       10.20
xa:                   7.30
pass_completion_pct:  79.4
progressive_passes:   68
progressive_carries:  112
```

---

# Known Gap

**Preferred Foot** was specified as a player profile field in `PROJECT_MASTER.md` and `ROADMAP.md` but is not available in FBref standard data exports. It is intentionally excluded from the MVP 1 dataset schema.

This field will be revisited in MVP 2 when Transfermarkt is introduced as a supplementary data source. The gap is recorded in `DECISIONS.md`.

---

# Document References

- `docs/PROJECT_MASTER.md` — field requirements (Section 8)
- `docs/ROADMAP.md` — MVP 1 feature specification
- `docs/MVP1_IMPLEMENTATION_PLAN.md` — Phase 1 deliverable definition
- `docs/DATA_SOURCES.md` — FBref source selection and risk register
- `docs/DECISIONS.md` — Decision 011 (static dataset strategy)

---

END OF DOCUMENT
