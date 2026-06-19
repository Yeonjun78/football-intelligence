# Football Intelligence — MVP2 Phase 2: Comparison Engine Plan

Version: 0.1
Status: Design Review
Date: 2026-06-16

---

## 1. Scope

This document designs the Player Comparison Engine: a new analytics module and FastAPI endpoint that takes two player IDs and returns a structured side-by-side comparison with metric-level winners, shared/exclusive strengths and weaknesses, and a rule-based verdict.

No code changes to existing analytics modules. All existing functions are reused as-is.

---

## 2. Dataset Constraints

The current cleaned dataset has 12 columns:

```
player_name, season, nationality, position, club, competition,
age, appearances, minutes_played, goals, assists, non_penalty_goals
```

This determines what can and cannot be compared:

**Comparable (available now):**
- Goals per 90, assists per 90, goal contributions per 90
- Raw goal and assist counts
- Non-penalty goals (penalty independence)
- Appearances (selection/availability)
- Minutes share (fitness and trust — minutes played vs available minutes)

**Not yet comparable (absent from MVP1 dataset, deferred to later phases):**
- xG, xA (expected metrics)
- Passing completion, progressive passes
- Dribbles, ball progression
- Defensive metrics (tackles, interceptions, pressures)
- Market value

The comparison engine is designed to accommodate additional metrics when the dataset expands. Metric definitions are isolated — adding a new metric requires one new entry in the metrics config, not structural changes.

---

## 3. Position-Aware Percentile Strategy

Percentiles are always computed within each player's own position peer group (FW, MF, DF, GK), exactly as in the existing profile generator. This is the only fair basis for comparison: a midfielder ranked 85th among midfielders for assists is more creative than one at the 40th percentile, regardless of how they compare to forwards.

**Same-position comparison** (e.g., FW vs FW): Both percentiles come from the same peer group. Direct comparison is fully meaningful.

**Cross-position comparison** (e.g., FW vs MF): Percentiles come from different peer groups. The comparison is still valid — each player's rank among their peers is a legitimate measure — but the response surfaces `same_position: false` so the frontend can inform the user. The verdict counts metric wins on the basis of relative peer rank.

**GK comparisons**: Goalkeepers have only appearance-based metrics in this dataset. The response is valid but limited. A `data_warning` field surfaces this when either player is a GK.

---

## 4. Metric Draw Threshold

A metric is declared a **draw** when the absolute percentile difference between the two players is less than 5 points. This prevents declaring a winner on statistically negligible differences. A 3-point gap in percentile rank is noise; a 20-point gap is meaningful.

| Advantage | Classification |
|---|---|
| < 5 percentile points | Draw |
| 5–20 points | Clear advantage |
| > 20 points | Dominant advantage |

---

## 5. Analytics Module — `analytics/comparison_engine.py`

This is the only new file in the analytics layer. It imports from `profile_generator.py` and adds no new external dependencies.

### 5.1 Dataclasses

```python
@dataclass
class MetricResult:
    metric: str
    label: str
    player1_value: float
    player1_percentile: float
    player2_value: float
    player2_percentile: float
    winner: str          # "player1" | "player2" | "draw"
    advantage: float     # absolute percentile difference; 0.0 when draw

@dataclass
class StrengthWeaknessBreakdown:
    player1_only: list[str]
    player2_only: list[str]
    shared: list[str]

@dataclass
class ComparisonVerdict:
    winner: str              # "player1" | "player2" | "draw"
    metrics_won: dict        # {"player1": 3, "player2": 1, "draw": 1}
    summary: str             # rule-based plain-English verdict

@dataclass
class PlayerComparison:
    player1_row: pd.Series   # original row (for identity fields)
    player2_row: pd.Series
    same_position: bool
    data_warning: str | None # non-None when comparison is structurally limited
    metrics: list[MetricResult]
    strengths: StrengthWeaknessBreakdown
    weaknesses: StrengthWeaknessBreakdown
    verdict: ComparisonVerdict
```

### 5.2 Metrics Configuration

Metrics are defined as a list of `(metric_key, label, raw_value_key)` tuples. This makes adding new metrics a one-line change:

```python
COMPARISON_METRICS = [
    ("goals_per_90",             "Goals per 90",             "goals"),
    ("assists_per_90",           "Assists per 90",            "assists"),
    ("goal_contributions_per_90","Goal Contributions per 90","goal_contributions"),
    ("appearances",              "Appearances",               "appearances"),
    ("minutes_share",            "Minutes Share",             "minutes_played"),
]
```

`metric_key` maps to the column produced by `_add_rate_cols()`. `raw_value_key` is used to extract the display value from `_stats_summary()`.

### 5.3 `generate_comparison()` — logic flow

```
generate_comparison(row_a, row_b, all_df) → PlayerComparison

1. Enrich the full df with rate columns using _add_rate_cols() — once
2. Enrich row_a and row_b individually
3. Build peer groups: peer_a = enriched[position == row_a.position]
                       peer_b = enriched[position == row_b.position]
4. Compute percentiles for each player against their own peer group
   using the existing _pct_rank() function
5. For each metric in COMPARISON_METRICS:
   a. Get value and percentile for each player
   b. Compute advantage = abs(pct_a - pct_b)
   c. If advantage < DRAW_THRESHOLD → winner = "draw"
      else winner = "player1" if pct_a > pct_b else "player2"
   d. Build MetricResult
6. Compute strengths and weaknesses for each player using existing
   _strengths() and _weaknesses() functions from profile_generator
7. Categorise into shared / player1_only / player2_only via set operations
8. Compute verdict: count metric wins, build summary string
9. Return PlayerComparison
```

### 5.4 Reuse from existing modules

| Existing function | Reused how |
|---|---|
| `_add_rate_cols(df)` | Enriches full df and both player rows |
| `_pct_rank(value, series)` | Computes each player's percentile per metric |
| `_percentiles(row, peer_df)` | Returns all metric percentiles for one player |
| `_strengths(row, pct)` | Generates strength list for each player |
| `_weaknesses(row, pct)` | Generates weakness list for each player |
| `_f(val)` | Safe float cast throughout |
| `_stats_summary(row)` | Extracts raw display values |
| `generate_profile(row, df)` | Not called directly — internals reused individually |

`generate_comparison` is a peer of `generate_profile`, not a wrapper around it. Both call the same internal helpers.

---

## 6. Verdict Generation (Rule-Based)

The verdict summary is generated from which metrics each player leads in. No AI API call.

**Winner determination:**
- Count metrics won (draw counts for neither)
- If player1 wins more → winner = "player1"
- If player2 wins more → winner = "player2"
- If equal wins → winner = "draw"

**Metric label map for summary sentences:**

| Metric key | Summary phrase |
|---|---|
| `goals_per_90` | "goal scoring rate" |
| `assists_per_90` | "creativity" |
| `goal_contributions_per_90` | "overall attacking output" |
| `appearances` | "availability" |
| `minutes_share` | "minutes share" |

**Summary template (dominant winner — leads 4+ metrics):**
> "{Player A} holds a clear advantage, leading on {metric list}. {Player B} edges ahead only on {metric list}."

**Summary template (narrow winner):**
> "{Player A} narrowly leads, winning on {metric list}. {Player B} counters with stronger {metric list}."

**Summary template (draw):**
> "{Player A} and {Player B} are evenly matched. {A} leads on {metric list} while {B} leads on {metric list}."

**Cross-position note appended when `same_position` is false:**
> " Note: percentiles are computed within each player's own position peer group."

**GK warning appended when either player is a GK:**
> " Comparison is limited — goalkeeping metrics are not available in the current dataset."

---

## 7. API Endpoint

```
GET /api/v1/compare?player1={id}&player2={id}
```

Single endpoint. Both parameters are required integers. The IDs are the same hash IDs returned by the search endpoint.

### Parameters

| Name | Type | Required | Notes |
|---|---|---|---|
| `player1` | integer | Yes | Hash ID from search results |
| `player2` | integer | Yes | Hash ID from search results |

---

## 8. Response Examples

### 8.1 Successful comparison — same position (FW vs FW)

```
GET /api/v1/compare?player1=1439301664&player2=2177216342
```
Kylian Mbappé (Real Madrid, FW) vs João Pedro (Chelsea, FW)

```json
{
  "player1": {
    "id": 1439301664,
    "player_name": "Kylian Mbappé",
    "club": "Real Madrid",
    "competition": "La Liga",
    "nationality": "France",
    "position": "FW",
    "age": 26,
    "season": "2025-26"
  },
  "player2": {
    "id": 2177216342,
    "player_name": "João Pedro",
    "club": "Chelsea",
    "competition": "Premier League",
    "nationality": "Brazil",
    "position": "FW",
    "age": 23,
    "season": "2025-26"
  },
  "same_position": true,
  "data_warning": null,
  "metrics": [
    {
      "metric": "goals_per_90",
      "label": "Goals per 90",
      "player1": { "value": 0.87, "percentile": 92.3 },
      "player2": { "value": 0.51, "percentile": 74.2 },
      "winner": "player1",
      "advantage": 18.1
    },
    {
      "metric": "assists_per_90",
      "label": "Assists per 90",
      "player1": { "value": 0.17, "percentile": 61.5 },
      "player2": { "value": 0.17, "percentile": 61.5 },
      "winner": "draw",
      "advantage": 0.0
    },
    {
      "metric": "goal_contributions_per_90",
      "label": "Goal Contributions per 90",
      "player1": { "value": 1.04, "percentile": 91.8 },
      "player2": { "value": 0.68, "percentile": 78.4 },
      "winner": "player1",
      "advantage": 13.4
    },
    {
      "metric": "appearances",
      "label": "Appearances",
      "player1": { "value": 31.0, "percentile": 72.4 },
      "player2": { "value": 31.0, "percentile": 72.4 },
      "winner": "draw",
      "advantage": 0.0
    },
    {
      "metric": "minutes_share",
      "label": "Minutes Share",
      "player1": { "value": 0.93, "percentile": 68.2 },
      "player2": { "value": 0.87, "percentile": 57.9 },
      "winner": "player1",
      "advantage": 10.3
    }
  ],
  "strengths": {
    "player1_only": ["Elite goal scoring", "Penalty conversion"],
    "player2_only": ["Goal scoring"],
    "shared": ["Availability"]
  },
  "weaknesses": {
    "player1_only": [],
    "player2_only": [],
    "shared": ["Defensive contribution"]
  },
  "verdict": {
    "winner": "player1",
    "metrics_won": { "player1": 3, "player2": 0, "draw": 2 },
    "summary": "Kylian Mbappé holds a clear advantage, leading on goal scoring rate, overall attacking output, and minutes share. João Pedro matches him on creativity and appearances but cannot close the gap in clinical finishing."
  }
}
```

---

### 8.2 Successful comparison — cross-position (FW vs MF)

```
GET /api/v1/compare?player1=1439301664&player2=1614395966
```
Kylian Mbappé (FW) vs João Gomes (MF)

```json
{
  "player1": {
    "id": 1439301664,
    "player_name": "Kylian Mbappé",
    "club": "Real Madrid",
    "competition": "La Liga",
    "nationality": "France",
    "position": "FW",
    "age": 26,
    "season": "2025-26"
  },
  "player2": {
    "id": 1614395966,
    "player_name": "João Gomes",
    "club": "Wolves",
    "competition": "Premier League",
    "nationality": "Brazil",
    "position": "MF",
    "age": 24,
    "season": "2025-26"
  },
  "same_position": false,
  "data_warning": null,
  "metrics": [
    {
      "metric": "goals_per_90",
      "label": "Goals per 90",
      "player1": { "value": 0.87, "percentile": 92.3 },
      "player2": { "value": 0.03, "percentile": 31.4 },
      "winner": "player1",
      "advantage": 60.9
    },
    {
      "metric": "assists_per_90",
      "label": "Assists per 90",
      "player1": { "value": 0.17, "percentile": 61.5 },
      "player2": { "value": 0.03, "percentile": 28.8 },
      "winner": "player1",
      "advantage": 32.7
    },
    {
      "metric": "goal_contributions_per_90",
      "label": "Goal Contributions per 90",
      "player1": { "value": 1.04, "percentile": 91.8 },
      "player2": { "value": 0.06, "percentile": 24.1 },
      "winner": "player1",
      "advantage": 67.7
    },
    {
      "metric": "appearances",
      "label": "Appearances",
      "player1": { "value": 31.0, "percentile": 72.4 },
      "player2": { "value": 35.0, "percentile": 81.6 },
      "winner": "player2",
      "advantage": 9.2
    },
    {
      "metric": "minutes_share",
      "label": "Minutes Share",
      "player1": { "value": 0.93, "percentile": 68.2 },
      "player2": { "value": 0.90, "percentile": 71.3 },
      "winner": "draw",
      "advantage": 3.1
    }
  ],
  "strengths": {
    "player1_only": ["Elite goal scoring", "Penalty conversion"],
    "player2_only": ["Availability"],
    "shared": []
  },
  "weaknesses": {
    "player1_only": ["Defensive contribution"],
    "player2_only": ["Below-average goal output", "Limited creative output"],
    "shared": []
  },
  "verdict": {
    "winner": "player1",
    "metrics_won": { "player1": 3, "player2": 1, "draw": 1 },
    "summary": "Kylian Mbappé dominates on all attacking metrics, leading on goal scoring rate, creativity, and overall attacking output. João Gomes counters with stronger availability. Note: percentiles are computed within each player's own position peer group."
  }
}
```

---

### 8.3 Error — same player both sides

```
GET /api/v1/compare?player1=1439301664&player2=1439301664
```

```json
HTTP 422
{
  "detail": "Cannot compare a player with themselves."
}
```

---

### 8.4 Error — player ID not found

```
GET /api/v1/compare?player1=1439301664&player2=9999999999
```

```json
HTTP 404
{
  "detail": "Player not found: player2."
}
```

The error names which ID failed so the client knows which lookup to retry.

---

### 8.5 Error — missing parameter

```
GET /api/v1/compare?player1=1439301664
```

```json
HTTP 422
{
  "detail": [
    {
      "type": "missing",
      "loc": ["query", "player2"],
      "msg": "Field required",
      "input": null
    }
  ]
}
```

FastAPI generates this automatically.

---

## 9. Pydantic Schemas

Added to `backend/models/schemas.py`:

```python
class PlayerIdentity(BaseModel):
    id: int
    player_name: str
    club: str
    competition: str
    nationality: str
    position: str
    age: int
    season: str

class MetricPlayerValue(BaseModel):
    value: float
    percentile: float

class MetricResult(BaseModel):
    metric: str
    label: str
    player1: MetricPlayerValue
    player2: MetricPlayerValue
    winner: str         # "player1" | "player2" | "draw"
    advantage: float

class StrengthWeaknessBreakdown(BaseModel):
    player1_only: list[str]
    player2_only: list[str]
    shared: list[str]

class ComparisonVerdict(BaseModel):
    winner: str                  # "player1" | "player2" | "draw"
    metrics_won: dict[str, int]  # {"player1": 3, "player2": 1, "draw": 1}
    summary: str

class ComparisonResponse(BaseModel):
    player1: PlayerIdentity
    player2: PlayerIdentity
    same_position: bool
    data_warning: str | None
    metrics: list[MetricResult]
    strengths: StrengthWeaknessBreakdown
    weaknesses: StrengthWeaknessBreakdown
    verdict: ComparisonVerdict
```

`PlayerIdentity` is also used in search results — `PlayerSearchResult` will be refactored to inherit from it or be replaced by it, removing the duplicate identity field definitions.

---

## 10. Files to Create or Modify

```
analytics/
└── comparison_engine.py         NEW — generate_comparison(), all dataclasses

backend/
├── main.py                      MODIFY — mount compare router (1 line)
├── routers/
│   └── compare.py               NEW — GET /api/v1/compare endpoint
├── services/
│   └── comparison_service.py    NEW — compare_players() service function
└── models/
    └── schemas.py               MODIFY — add comparison schemas; refactor PlayerIdentity
```

No changes to `analytics/player_search.py`, `analytics/profile_generator.py`, `analytics/app.py`, or `backend/services/player_service.py`.

---

## 11. Service Layer

`backend/services/comparison_service.py`:

The service function:
1. Guards against same-ID comparison → 422
2. Looks up both rows from `id_map` → 404 with named parameter if either missing
3. Calls `generate_comparison(row1, row2, df)` from analytics
4. Converts the `PlayerComparison` dataclass to a dict the router can return

The service is the only backend file that imports from `analytics.comparison_engine`. The router imports nothing from analytics directly.

---

## 12. Error Handling

| Scenario | Status | Response |
|---|---|---|
| `player1 == player2` | 422 | `"Cannot compare a player with themselves."` |
| Either ID not in `id_map` | 404 | `"Player not found: player1."` or `"player2."` |
| Either param missing | 422 | FastAPI auto (array format) |
| Non-integer param value | 422 | FastAPI auto |
| Unhandled exception | 500 | Generic handler in `main.py` (already registered) |

---

## 13. Reuse Summary

| What | Source | Reused as-is |
|---|---|---|
| `load_players()` | `player_search.py` | Yes — dataset already in `app.state.df` |
| `_add_rate_cols()` | `profile_generator.py` | Yes — called inside `generate_comparison()` |
| `_pct_rank()` | `profile_generator.py` | Yes — per-metric percentile computation |
| `_percentiles()` | `profile_generator.py` | Yes — called per player per peer group |
| `_strengths()` | `profile_generator.py` | Yes — called per player |
| `_weaknesses()` | `profile_generator.py` | Yes — called per player |
| `_f()` | `profile_generator.py` | Yes — safe float cast |
| `_stats_summary()` | `profile_generator.py` | Yes — extract raw display values |
| `make_player_id()` | `player_service.py` | Yes — ID lookup unchanged |
| `get_df`, `get_id_map` | `dependencies.py` | Yes — injected into compare route |
| Global 500 handler | `main.py` | Yes — already registered |

New code in the analytics layer is limited to:
- `comparison_engine.py` — comparison logic and dataclasses
- `COMPARISON_METRICS` config list
- Verdict summary generator (rule-based string construction)

---

## 14. Out of Scope for Phase 2

- AI-generated narrative comparison (reserved for a future phase when LLM integration is added)
- xG, xA, dribbling, defensive metrics (not in current dataset)
- More-than-two-player comparison
- Historical season-over-season comparison
- Tactical fit scoring (requires club/formation data not in dataset)

---

END OF DOCUMENT
