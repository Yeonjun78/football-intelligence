# Football Intelligence — MVP2 Phase 2: Comparison Engine Plan

Version: 0.3
Status: Ready for Implementation
Date: 2026-06-18
Supersedes: v0.1 (2026-06-16)

Changes from v0.1: full redesign following design review (MVP2_COMPARISON_REVIEW.md).
Fixed two critical runtime bugs, replaced win-count verdict with weighted scoring,
added minimum sample size rules, corrected metric key names, removed dependent metric
from scoring, added structural label filtering, expanded data_warning logic.

---

## 1. Scope

This document designs the Player Comparison Engine: a new analytics module and
FastAPI endpoint that takes two player IDs and returns a structured side-by-side
comparison with metric-level results, shared/exclusive strengths and weaknesses,
and a verdict based on weighted percentile advantage.

No code changes to existing analytics modules (player_search.py,
profile_generator.py, app.py). All existing internal functions are reused.

---

## 2. Dataset Constraints

The current cleaned dataset has 12 columns:

    player_name, season, nationality, position, club, competition,
    age, appearances, minutes_played, goals, assists, non_penalty_goals

Comparable now:
- Goals per 90, assists per 90, goal contributions per 90 (display only -- see section 5)
- Appearances (raw count, used as availability proxy)
- Minutes share (minutes played / appearances x 90)

Deferred -- not in dataset:
- xG, xA, passing metrics, dribbling, defensive metrics, market value

The comparison engine is designed to accommodate new metrics: adding one requires
a single new entry in COMPARISON_METRICS, not structural changes.

---

## 3. Minimum Sample Size

Rule: A player must have appearances >= 5 AND minutes_played >= 270
(equivalent to 3 full games) to be compared without a warning.

Rationale: _add_rate_cols() clips minutes to a minimum of 1, so a player
with 1 appearance and 1 goal produces goals_p90 = 90.0 -- higher than any
legitimate striker in the dataset. Without this guard, small-sample outliers
dominate every comparison.

Behaviour when either player fails the threshold:
- The comparison still runs and returns a full response.
- data_warning is set to flag which player is below threshold, how many
  appearances and minutes they have, and that per-90 statistics may be unreliable.
- The verdict is not blocked. The caller decides how to surface the warning.

Example data_warning text:
  "Ethan Mbappe has limited data (3 appearances, 198 minutes). Per-90 statistics
   may not be reliable."

---

## 4. Position-Aware Percentile Strategy

Percentiles are always computed within each player's own position peer group
(FW, MF, DF, GK). This is the only internally consistent basis: a midfielder
at the 85th percentile for assists is more creative than one at 40th, regardless
of how they compare to forwards.

Same-position comparison (FW vs FW): Both percentiles from the same peer group.
Direct comparison is fully meaningful.

Cross-position comparison (FW vs MF): Percentiles from different peer groups.
same_position: false is surfaced in the response. data_warning notes the
different peer groups with their sizes (e.g., "FW: 415 players, MF: 1119 players").

DF or GK in a cross-position comparison: The available metrics are all
attacking. data_warning explicitly names the structurally disadvantaged player
and states that their defensive contributions are not captured. The verdict
summary leads with this limitation, not with the conclusion.

GK comparison (either player): Goalkeepers have no meaningful attacking
metrics in this dataset. Only appearances and minutes_share are informative.
data_warning flags this regardless of the second player's position.

data_warning composition: All applicable conditions are concatenated into
a single string. null when no warnings apply.

---

## 5. Metric Configuration

### 5.1 Correction from v0.1

v0.1 used the keys goals_per_90, assists_per_90, goal_contributions_per_90
in COMPARISON_METRICS. These do not match the column names produced by
_add_rate_cols(), which are goals_p90, assists_p90, gc_p90. This
mismatch would cause a KeyError at runtime. All metric keys below use the
correct column names.

v0.1 also used a raw_value_key to source the display value from _stats_summary().
This was incorrect: for goals_p90 the raw_value_key was "goals" (integer count),
but the display value should be the per-90 rate (float). For minutes_share the
mapped key did not exist in _stats_summary() at all. The raw_value_key concept
is removed. MetricPlayerValue.value is now always sourced from the enriched row
using metric_key directly.

### 5.2 COMPARISON_METRICS

```python
COMPARISON_METRICS = [
    # (metric_key, label, is_scored)
    # metric_key = column in the enriched DataFrame (_add_rate_cols output,
    #              or original df column for 'appearances')
    # is_scored  = True  -> counts toward WAS and metrics_won
    #              False -> displayed in response but excluded from verdict
    ("goals_p90",    "Goals per 90",             True),
    ("assists_p90",  "Assists per 90",            True),
    ("gc_p90",       "Goal Contributions per 90", False),
    ("appearances",  "Appearances",               True),
    ("minutes_share","Minutes Share",             True),
]
```

gc_p90 (goal contributions per 90) is the sum of goals_p90 and assists_p90.
It is mathematically dependent on the other two: a player who wins both will always
also win gc_p90. Including it as a scored metric inflates metrics_won and the
verdict without adding independent information. It is retained in the response as
a display metric (is_scored: False) because it is useful context for the frontend,
but it contributes nothing to winner determination.

Four metrics are scored: goals_p90, assists_p90, appearances, minutes_share.

### 5.3 Value sourcing

The value field in MetricPlayerValue is taken directly from the enriched row
using metric_key. For goals_p90 this is the computed float (e.g., 0.87).
For appearances this is the raw integer from the original DataFrame column
(e.g., 31). For minutes_share this is the computed ratio (e.g., 0.93).
No secondary key mapping is needed.

Note on appearances: This column is not produced by _add_rate_cols() --
it exists in the original DataFrame and is preserved through the enrichment step.

Note on minutes_share bounds: _add_rate_cols() clips minutes to a minimum of 1
but does not cap them. A player who regularly plays extra time may have
minutes_share > 1.0. Do not modify _add_rate_cols() to fix it here; note it in
data_warning if either player's minutes_share exceeds 1.05.

---

## 6. Metric Draw Threshold

A metric result is a draw when the absolute percentile difference is less
than 5 points. This prevents declaring a winner on statistically negligible gaps.

| Advantage           | Classification    |
|---------------------|-------------------|
| < 5 pct points      | Draw              |
| 5-19 points         | Clear advantage   |
| >= 20 points        | Dominant advantage|

advantage field behaviour (corrected from v0.1):
The advantage field always stores the actual absolute percentile difference,
regardless of whether the result is a draw or a win. v0.1 set advantage: 0.0
for all draws, which lost information about how close the draw actually was.
The winner: "draw" field already indicates the result fell below the threshold.

---

## 7. Verdict Scoring -- Weighted Advantage Score

### 7.1 Why win count alone is insufficient

A simple win count treats a 60-point percentile advantage and a 5.1-point
advantage identically. This produces perverse verdicts: a player who dominates
on goal scoring (60-point lead) can tie or lose the verdict against a player
who barely wins on appearances (5.1-point lead).

### 7.2 Weighted Advantage Score (WAS)

For each scored metric where the result is not a draw, the winning player
accumulates the advantage (percentile difference) into their WAS.

    WAS(player) = sum of advantage for all scored metrics where player won

Draw metrics contribute 0 to both players' WAS. Display-only metrics
(is_scored: False) are excluded entirely.

The player with the higher WAS wins the comparison.

A draw verdict is only declared when both players' WAS is 0 -- meaning
every scored metric fell within the draw threshold. If any scored metric
has a non-draw winner, the overall verdict cannot be a draw.

### 7.3 Example

| Metric        | Player1 pct | Player2 pct | Diff | Winner  | Contributes to WAS  |
|---------------|-------------|-------------|------|---------|---------------------|
| goals_p90     | 92.3        | 74.2        | 18.1 | player1 | player1 += 18.1     |
| assists_p90   | 62.1        | 62.1        | 0.0  | draw    | --                  |
| appearances   | 72.4        | 72.4        | 0.0  | draw    | --                  |
| minutes_share | 68.2        | 58.0        | 10.2 | player1 | player1 += 10.2     |

WAS: player1 = 28.3, player2 = 0.0 -> player1 wins

Under the old win-count system this would be {player1: 2, player2: 0} --
the magnitude of the 18.1-point goal-scoring lead was invisible. With WAS it
directly determines the winner and the strength of the conclusion.

### 7.4 metrics_won is retained for transparency

metrics_won remains in the response as {"player1": N, "player2": M, "draw": K}
across scored metrics only. It is a display aid for the frontend (e.g., "leads
on 2 of 4 metrics") and is not used for winner determination.

### 7.5 Both-below-average qualifier

When the winner's best percentile across all scored metrics is below 50, the
verdict summary notes that both players are performing below the position average
on the compared metrics. The WAS winner is still declared, but the summary avoids
implying either player is strong in absolute terms.

---

## 8. Structural Label Filtering

_weaknesses() in profile_generator.py unconditionally appends
"Defensive contribution" for every FW, regardless of any statistical measurement.
This is a role observation, not a weakness derived from percentile thresholds.

In comparison, this label behaves badly:
- FW vs FW: Both players have it -> shared: ["Defensive contribution"].
  Correct, but uninformative noise in every FW vs FW comparison.
- FW vs MF: Only the FW has it -> player1_only: ["Defensive contribution"].
  Misleading: implies the forward has a unique weakness relative to the
  midfielder, when the label was never a measurement to begin with.

Fix: Before computing player1_only, player2_only, and shared, filter
out any labels in STRUCTURAL_LABELS:

```python
STRUCTURAL_LABELS = frozenset({"Defensive contribution"})
```

Filtered labels are silently excluded from the comparison breakdown.
Not shown anywhere in the response. No new response field is added.

---

## 9. Analytics Module -- analytics/comparison_engine.py

Only new file in the analytics layer. Imports _add_rate_cols, _pct_rank,
_percentiles, _strengths, _weaknesses, _f from profile_generator.py.

### 9.1 Dataclasses

```python
@dataclass
class MetricResult:
    metric: str
    label: str
    is_scored: bool
    player1_value: float
    player1_percentile: float
    player2_value: float
    player2_percentile: float
    winner: str       # "player1" | "player2" | "draw"
    advantage: float  # actual absolute percentile diff; not zeroed out for draws

@dataclass
class StrengthWeaknessBreakdown:
    player1_only: list[str]
    player2_only: list[str]
    shared: list[str]

@dataclass
class ComparisonVerdict:
    winner: str             # "player1" | "player2" | "draw"
    metrics_won: dict       # {"player1": 2, "player2": 0, "draw": 2} -- scored only
    advantage_score: dict   # {"player1": 28.3, "player2": 0.0} -- WAS, scored only
    summary: str

@dataclass
class PlayerComparison:
    player1_row: pd.Series
    player2_row: pd.Series
    same_position: bool
    data_warning: str | None
    metrics: list[MetricResult]
    strengths: StrengthWeaknessBreakdown
    weaknesses: StrengthWeaknessBreakdown
    verdict: ComparisonVerdict
```

### 9.2 generate_comparison() -- logic flow

```
generate_comparison(row_a, row_b, all_df) -> PlayerComparison

1.  Validate minimum sample size for both players.
    Build data_warning string. (Continues regardless.)

2.  Enrich all_df once with _add_rate_cols().

3.  Enrich row_a and row_b individually.

4.  Build peer groups:
      peer_a = enriched_df[position == row_a.position]
      peer_b = enriched_df[position == row_b.position]

5.  Determine same_position and cross-position data_warning additions.

6.  For each (metric_key, label, is_scored) in COMPARISON_METRICS:
      a. value_a = enriched_row_a[metric_key]
         value_b = enriched_row_b[metric_key]
      b. pct_a = _pct_rank(value_a, peer_a[metric_key])
         pct_b = _pct_rank(value_b, peer_b[metric_key])
      c. advantage = abs(pct_a - pct_b)   <- always actual diff
      d. if advantage < DRAW_THRESHOLD:
             winner = "draw"
         else:
             winner = "player1" if pct_a > pct_b else "player2"
      e. Append MetricResult(is_scored=is_scored, advantage=advantage, ...)

7.  Compute WAS and metrics_won across scored metrics only.

8.  winner = "player1" if WAS_a > WAS_b
             "player2" if WAS_b > WAS_a
             "draw"    if WAS_a == WAS_b == 0

9.  Compute strengths and weaknesses for each player using _strengths()
    and _weaknesses().
    Filter STRUCTURAL_LABELS from both lists before set operations.

10. Compute shared / player1_only / player2_only via set difference.

11. Build summary string (see section 10).

12. Return PlayerComparison.
```

### 9.3 Reuse from existing modules

| Function              | Source               | Used for                               |
|-----------------------|----------------------|----------------------------------------|
| _add_rate_cols(df)    | profile_generator.py | Enriches full df and individual rows   |
| _pct_rank(value, s)   | profile_generator.py | Per-metric percentile computation      |
| _percentiles(row, df) | profile_generator.py | Bulk percentile fetch per player       |
| _strengths(row, pct)  | profile_generator.py | Strength list; output filtered         |
| _weaknesses(row, pct) | profile_generator.py | Weakness list; output filtered         |
| _f(val)               | profile_generator.py | Safe float cast                        |

_stats_summary() is not called by the comparison engine. Display values come
from the enriched row directly via metric_key.

---

## 10. Verdict Summary Generation (Rule-Based)

Templates select based on same_position, winner, and position types.
All templates are rule-based string construction. No AI API call.

Metric phrase map:
  goals_p90     -> "goal scoring rate"
  assists_p90   -> "creativity"
  appearances   -> "availability"
  minutes_share -> "minutes share"

Template A -- same position, clear winner (WAS gap > 20):
  "{Winner} holds a clear advantage with a weighted score of {WAS_winner:.1f}
   vs {WAS_loser:.1f}, leading on {metric list}. {Loser} holds an advantage
   only on {metric list}."

Template B -- same position, narrow winner (WAS gap <= 20):
  "{Winner} narrowly leads (weighted score {WAS_winner:.1f} vs {WAS_loser:.1f}),
   winning on {metric list}. {Loser} counters with stronger {metric list}."

Template C -- same position, draw:
  "{Player A} and {Player B} are evenly matched across all scored metrics."

Template D -- cross-position, any result:
  Lead with the limitation: "This is a cross-position comparison
  ({PlayerA position} vs {PlayerB position}). On available attacking metrics,
  {winner} leads with a weighted score of {WAS:.1f} vs {WAS:.1f}, driven by
  {metric list}. {Other player}'s {position role} contributions are not
  captured in this dataset."

Both-below-average qualifier:
  When the winner's highest scored percentile is below 50, append:
  " Note: both players score below the position average on the available metrics."

---

## 11. API Endpoint

    GET /api/v1/compare?player1={id}&player2={id}

Both parameters are required integers -- the same hash IDs returned by the
search endpoint.

Parameters:
  player1  integer  required  Hash ID from search results
  player2  integer  required  Hash ID from search results

Known limitation -- response is order-dependent:
compare?player1=A&player2=B and compare?player1=B&player2=A return
mirror-image responses. There is no canonical form. HTTP caching of comparison
responses is not implemented in Phase 2. Acceptable at MVP scale.

---

## 12. Response Examples

### 12.1 Same position -- FW vs FW

    GET /api/v1/compare?player1=1439301664&player2=2177216342
    Kylian Mbappe (Real Madrid, FW) vs Joao Pedro (Chelsea, FW)

```json
{
  "player1": {
    "id": 1439301664,
    "player_name": "Kylian Mbappe",
    "club": "Real Madrid",
    "competition": "La Liga",
    "nationality": "France",
    "position": "FW",
    "age": 26,
    "season": "2025-26"
  },
  "player2": {
    "id": 2177216342,
    "player_name": "Joao Pedro",
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
      "metric": "goals_p90",
      "label": "Goals per 90",
      "is_scored": true,
      "player1": { "value": 0.87, "percentile": 92.3 },
      "player2": { "value": 0.51, "percentile": 74.2 },
      "winner": "player1",
      "advantage": 18.1
    },
    {
      "metric": "assists_p90",
      "label": "Assists per 90",
      "is_scored": true,
      "player1": { "value": 0.17, "percentile": 62.1 },
      "player2": { "value": 0.17, "percentile": 62.1 },
      "winner": "draw",
      "advantage": 0.0
    },
    {
      "metric": "gc_p90",
      "label": "Goal Contributions per 90",
      "is_scored": false,
      "player1": { "value": 1.04, "percentile": 91.8 },
      "player2": { "value": 0.68, "percentile": 78.4 },
      "winner": "player1",
      "advantage": 13.4
    },
    {
      "metric": "appearances",
      "label": "Appearances",
      "is_scored": true,
      "player1": { "value": 31.0, "percentile": 72.4 },
      "player2": { "value": 31.0, "percentile": 72.4 },
      "winner": "draw",
      "advantage": 0.0
    },
    {
      "metric": "minutes_share",
      "label": "Minutes Share",
      "is_scored": true,
      "player1": { "value": 0.93, "percentile": 68.2 },
      "player2": { "value": 0.87, "percentile": 58.0 },
      "winner": "player1",
      "advantage": 10.2
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
    "shared": []
  },
  "verdict": {
    "winner": "player1",
    "metrics_won": { "player1": 2, "player2": 0, "draw": 2 },
    "advantage_score": { "player1": 28.3, "player2": 0.0 },
    "summary": "Kylian Mbappe holds a clear advantage with a weighted score of 28.3 vs 0.0, leading on goal scoring rate and minutes share. Joao Pedro matches him on creativity and appearances."
  }
}
```

Notes:
- gc_p90 is included with is_scored: false. Its winner and advantage are shown
  but excluded from metrics_won and advantage_score.
- weaknesses.shared is empty -- "Defensive contribution" filtered by
  STRUCTURAL_LABELS. In v0.1 it appeared as a shared weakness for all FW vs FW.
- metrics_won counts only scored metrics: 2 wins + 2 draws = 4 total (correct;
  gc_p90 excluded).
- advantage_score.player1 = 18.1 + 10.2 = 28.3 (goals_p90 + minutes_share;
  gc_p90 excluded).

---

### 12.2 Cross-position with structural disadvantage -- FW vs MF

    GET /api/v1/compare?player1=1439301664&player2=1614395966
    Kylian Mbappe (FW) vs Joao Gomes (MF)

```json
{
  "player1": {
    "id": 1439301664,
    "player_name": "Kylian Mbappe",
    "club": "Real Madrid",
    "competition": "La Liga",
    "nationality": "France",
    "position": "FW",
    "age": 26,
    "season": "2025-26"
  },
  "player2": {
    "id": 1614395966,
    "player_name": "Joao Gomes",
    "club": "Wolves",
    "competition": "Premier League",
    "nationality": "Brazil",
    "position": "MF",
    "age": 24,
    "season": "2025-26"
  },
  "same_position": false,
  "data_warning": "This comparison crosses positions. Attacking metrics structurally favour Kylian Mbappe (FW). Joao Gomes's defensive contributions are not captured in this dataset. Percentiles computed within each player's own position peer group (FW: 415 players, MF: 1119 players).",
  "metrics": [
    {
      "metric": "goals_p90",
      "label": "Goals per 90",
      "is_scored": true,
      "player1": { "value": 0.87, "percentile": 92.3 },
      "player2": { "value": 0.03, "percentile": 31.4 },
      "winner": "player1",
      "advantage": 60.9
    },
    {
      "metric": "assists_p90",
      "label": "Assists per 90",
      "is_scored": true,
      "player1": { "value": 0.17, "percentile": 62.1 },
      "player2": { "value": 0.03, "percentile": 28.8 },
      "winner": "player1",
      "advantage": 33.3
    },
    {
      "metric": "gc_p90",
      "label": "Goal Contributions per 90",
      "is_scored": false,
      "player1": { "value": 1.04, "percentile": 91.8 },
      "player2": { "value": 0.06, "percentile": 24.1 },
      "winner": "player1",
      "advantage": 67.7
    },
    {
      "metric": "appearances",
      "label": "Appearances",
      "is_scored": true,
      "player1": { "value": 31.0, "percentile": 72.4 },
      "player2": { "value": 35.0, "percentile": 81.6 },
      "winner": "player2",
      "advantage": 9.2
    },
    {
      "metric": "minutes_share",
      "label": "Minutes Share",
      "is_scored": true,
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
    "player1_only": [],
    "player2_only": ["Below-average goal output", "Limited creative output"],
    "shared": []
  },
  "verdict": {
    "winner": "player1",
    "metrics_won": { "player1": 2, "player2": 1, "draw": 1 },
    "advantage_score": { "player1": 94.2, "player2": 9.2 },
    "summary": "This is a cross-position comparison (FW vs MF). On available attacking metrics, Kylian Mbappe leads with a weighted score of 94.2 vs 9.2, driven by goal scoring rate and creativity. Joao Gomes's defensive contributions are not captured in this dataset."
  }
}
```

Notes:
- data_warning is non-null. The verdict summary leads with the cross-position
  caveat, not with the conclusion.
- weaknesses.player1_only is empty -- "Defensive contribution" filtered by
  STRUCTURAL_LABELS, avoiding the misleading implication that Mbappe has a
  unique weakness relative to a midfielder.
- advantage_score.player1 = 60.9 + 33.3 = 94.2 (goals_p90 + assists_p90;
  gc_p90 excluded despite its 67.7-point advantage being the largest).

---

### 12.3 Error -- same player both sides

    GET /api/v1/compare?player1=1439301664&player2=1439301664

```json
HTTP 422
{ "detail": "Cannot compare a player with themselves." }
```

---

### 12.4 Error -- player ID not found

    GET /api/v1/compare?player1=1439301664&player2=9999999999

```json
HTTP 404
{ "detail": "Player not found: player2." }
```

The error names the failing parameter so the client knows which lookup to retry.

---

### 12.5 Error -- missing parameter

    GET /api/v1/compare?player1=1439301664

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

## 13. Pydantic Schemas

Added to backend/models/schemas.py. Do not change PlayerSearchResult as part
of this work -- schema unification is a versioned API change deferred to Phase 3.

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
    is_scored: bool
    player1: MetricPlayerValue
    player2: MetricPlayerValue
    winner: str      # "player1" | "player2" | "draw"
    advantage: float # always actual percentile diff; not zeroed for draws

class StrengthWeaknessBreakdown(BaseModel):
    player1_only: list[str]
    player2_only: list[str]
    shared: list[str]

class ComparisonVerdict(BaseModel):
    winner: str
    metrics_won: dict[str, int]       # scored metrics only
    advantage_score: dict[str, float] # WAS per player; scored metrics only
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

---

## 14. Files to Create or Modify

```
analytics/
+-- comparison_engine.py         NEW

backend/
+-- main.py                      MODIFY -- mount compare router (1 line)
+-- routers/
|   +-- compare.py               NEW
+-- services/
|   +-- comparison_service.py    NEW
+-- models/
    +-- schemas.py               MODIFY -- add comparison schemas only
```

No changes to analytics/player_search.py, analytics/profile_generator.py,
analytics/app.py, or backend/services/player_service.py.

---

## 15. Service Layer

backend/services/comparison_service.py is the only backend file that imports
from analytics.comparison_engine. The router imports nothing from analytics.

The service function:
1. Guards player1 == player2 -> 422
2. Looks up both rows from id_map -> 404 with named parameter if either missing
3. Calls generate_comparison(row1, row2, df)
4. Converts PlayerComparison dataclass to response dict

---

## 16. Error Handling

| Scenario              | Status | Response                                        |
|-----------------------|--------|-------------------------------------------------|
| player1 == player2    | 422    | "Cannot compare a player with themselves."      |
| Either ID not found   | 404    | "Player not found: player1." or "player2."      |
| Either param missing  | 422    | FastAPI auto (array format)                     |
| Non-integer param     | 422    | FastAPI auto                                    |
| Unhandled exception   | 500    | Generic handler in main.py (already registered)|

---

## 17. Reuse Summary

| What                  | Source               | Status                          |
|-----------------------|----------------------|---------------------------------|
| _add_rate_cols(df)    | profile_generator.py | Reused as-is                    |
| _pct_rank(value, s)   | profile_generator.py | Reused as-is                    |
| _percentiles(row, df) | profile_generator.py | Reused as-is                    |
| _strengths(row, pct)  | profile_generator.py | Reused; output filtered         |
| _weaknesses(row, pct) | profile_generator.py | Reused; output filtered         |
| _f(val)               | profile_generator.py | Reused as-is                    |
| load_players()        | player_search.py     | Already in app.state.df         |
| make_player_id()      | player_service.py    | Reused as-is for ID lookup      |
| get_df, get_id_map    | dependencies.py      | Injected into compare route     |
| Global 500 handler    | main.py              | Already registered              |

New analytics code is limited to comparison_engine.py: COMPARISON_METRICS,
STRUCTURAL_LABELS, generate_comparison(), dataclasses, WAS computation,
and verdict summary template logic.

---

## 18. Out of Scope for Phase 2

- AI-generated narrative comparison
- xG, xA, dribbling, defensive metrics
- More-than-two-player comparison
- Historical season-over-season comparison
- Tactical fit scoring
- Canonical parameter ordering / HTTP caching
- GK-specific metric suppression (GK vs GK shows all metrics; data_warning explains)
- Unification of PlayerSearchResult and PlayerIdentity schemas

---

END OF DOCUMENT
