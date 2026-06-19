# Football Intelligence — MVP2 Phase 2: Comparison Plan Design Review

Version: 0.1
Status: Pre-Implementation Review
Date: 2026-06-16
Reviewed: docs/MVP2_COMPARISON_PLAN.md

---

## Summary

The plan is structurally sound: the endpoint design is clean, the analytics reuse strategy is appropriate, and the dataclass hierarchy is well-shaped. However there are four concrete implementation bugs, three logic flaws that produce misleading verdicts in common cases, and several edge cases that would reach users without guard clauses. All issues are fixable before implementation begins.

Findings are grouped by severity.

---

## 1. Implementation Bugs (will break at runtime)

### 1.1 Column name mismatch between COMPARISON_METRICS and `_add_rate_cols()`

**Severity: Critical. The comparison engine will fail on first call.**

`_add_rate_cols()` produces these column names:
```
goals_p90, assists_p90, gc_p90, minutes_share
```

`COMPARISON_METRICS` in the plan references:
```
goals_per_90, assists_per_90, goal_contributions_per_90
```

And `_percentiles()` also uses:
```python
metrics = ["goals_p90", "assists_p90", "gc_p90", "minutes_share", "appearances"]
```

The plan promises reuse of `_percentiles()` as-is, but `COMPARISON_METRICS` uses different key names for the same columns. Any lookup on the enriched row using the COMPARISON_METRICS keys would raise `KeyError`. The comparison engine either needs to translate between naming conventions or adopt the existing column names consistently.

**Fix options:**
- Use the existing `_add_rate_cols()` column names throughout: `goals_p90`, `assists_p90`, `gc_p90`.
- Or rename columns in `_add_rate_cols()` — but that modifies an existing module (disallowed by the plan's own scope).

---

### 1.2 `raw_value_key` in COMPARISON_METRICS maps to wrong sources

**Severity: Critical. Display values will be wrong or cause KeyError.**

The plan describes `raw_value_key` as "used to extract the display value from `_stats_summary()`", but the mappings are incorrect for two metrics:

| Metric | raw_value_key in plan | What `_stats_summary()` returns for that key | What the response example shows |
|---|---|---|---|
| `goals_per_90` | `"goals"` | `25` (integer count) | `0.87` (rate) |
| `minutes_share` | `"minutes_played"` | `2599` (integer minutes) | `0.93` (ratio) |

For `goals_per_90`, the displayed value should be the per-90 rate (0.87), not the raw goal count (25). `_stats_summary()` does return `"goals_per_90": 0.87` — the correct key is `"goals_per_90"`, not `"goals"`.

For `minutes_share`, `_stats_summary()` does not return `minutes_share` at all. The value 0.93 comes from `_add_rate_cols()`, not from `_stats_summary()`. The raw_value_key concept breaks down entirely for this metric.

**Fix:** The `MetricPlayerValue.value` field should be sourced from the enriched row (from `_add_rate_cols()`) using the metric key directly, not from `_stats_summary()`. The `raw_value_key` concept should be removed. Each metric's display value is the same rate/ratio used for the percentile calculation.

---

### 1.3 `appearances` column not produced by `_add_rate_cols()`

**Severity: Moderate. Inconsistency in the metrics pipeline.**

`_add_rate_cols()` adds four new columns: `goals_p90`, `assists_p90`, `gc_p90`, `minutes_share`. It does not touch `appearances`. `_percentiles()` accesses `appearances` directly from the original DataFrame column, which happens to work because `_add_rate_cols()` preserves all original columns.

The plan treats `appearances` as a metric produced by `_add_rate_cols()` (step 1 of `generate_comparison()` is "enrich with rate columns"). This is misleading — `appearances` is a raw count column that already exists. This needs to be clarified in the implementation to avoid confusion about where each metric value comes from.

---

### 1.4 `data_warning` is not set for cross-position comparisons

**Severity: Minor — the field exists but is underused.**

The plan states `data_warning` is `non-None when comparison is structurally limited` and describes it firing when "either player is a GK". But the cross-position FW vs MF response in example 8.2 shows `"data_warning": null` even though `same_position: false`. A FW vs DF comparison is also structurally limited: the metrics available (all attacking) systematically disadvantage the defender. Users reading a confident "player1 holds a clear advantage" verdict for Mbappé vs a centre-back deserve a warning that the comparison is measuring the wrong things for one player.

`data_warning` should fire for two conditions, not one:
1. Either player is a GK (currently described)
2. Positions are different and one is DF or GK (attacking metrics disadvantage them structurally)

---

## 2. Logic Flaws (produce wrong or misleading outputs)

### 2.1 `goal_contributions_per_90` is a linear combination — not an independent metric

**Severity: High. Systematically inflates `metrics_won` and verdict confidence.**

`goal_contributions_per_90 = goals_per_90 + assists_per_90`

This is a mathematical identity. When player1 wins `goals_per_90` and `assists_per_90`, they will always win `goal_contributions_per_90` as well (barring edge cases at exactly the draw threshold). Including all three metrics means the winner of the first two is guaranteed to also win the third.

Concrete effect: A player who leads on goals and assists gets `metrics_won: 3`, triggering the "dominant winner — leads 4+ metrics" template if they also lead on one more metric. But the independent information content is from only 2 dimensions, not 3. The verdict overstates the evidence.

**Fix:** Remove `goal_contributions_per_90` from `COMPARISON_METRICS`. It should appear in the response as a displayed statistic but not as a scored metric contributing to the verdict. Alternatively, include it but explicitly exclude it from `metrics_won` counting.

---

### 2.2 `metrics_won` count ignores magnitude — produces perverse verdicts

**Severity: High. Equal-wins "draw" verdict in cases of lopsided comparison.**

`metrics_won` is a simple count. A player winning a metric by 1 percentile point (just over the draw threshold) counts identically to winning by 60 points. The verdict is determined by win count alone.

Concrete perverse case:
- Player1 wins `goals_per_90` by 60 percentile points
- Player2 wins `appearances` by 5.1 percentile points (just over threshold)
- `metrics_won: {player1: 1, player2: 1}` → verdict winner = "draw"

The summary would say "These players are evenly matched" when player1 has an enormous advantage in the metric that matters most for forwards.

This is not a theoretical edge case — it will happen whenever an elite scorer faces a more available player who is only slightly better on appearances.

**Fix options:**
- Weight metrics by advantage magnitude, not just win/loss binary
- Use a weighted sum of percentile advantages as the verdict signal rather than a win count
- Or: keep the win count but add a secondary tiebreaker using total percentile advantage sum

---

### 2.3 Structural weakness labels pollute the strengths/weaknesses breakdown

**Severity: Moderate. Produces misleading "shared" and "unique" labels.**

`_weaknesses()` unconditionally appends `"Defensive contribution"` for every FW, regardless of performance. This is a structural role observation, not a statistical weakness. In the comparison it behaves as follows:

**FW vs FW comparison:** Both players have `"Defensive contribution"` in weaknesses. It lands in `shared`. The frontend shows "Shared weakness: Defensive contribution" — correct but uninformative. Every FW vs FW comparison will always show this as a shared weakness.

**FW vs MF/DF comparison:** Only the FW has this label. It lands in `player1_only`. The frontend shows "Mbappé has a unique weakness: Defensive contribution" that the midfielder does not have — suggesting the forward is weaker than the midfielder in this area, when the label was never a measurement to begin with.

The plan reuses `_strengths()` and `_weaknesses()` directly, inheriting this design choice without acknowledging it.

**Fix:** Filter structural observations (those not derived from percentile thresholds) from the comparison breakdown. In the current code, "Defensive contribution" for FW is always appended at the end of `_weaknesses()` without a percentile check. These should be excluded from `player1_only`, `player2_only`, and `shared`, or flagged separately as `structural_notes`.

---

## 3. Missing Edge Cases

### 3.1 Minimum sample size — small-sample players produce extreme per-90 rates

A player with 1 appearance and 1 goal has `goals_p90 = 1/90 * 90 = 1.0` goals per 90 — higher than any established striker. `_add_rate_cols()` clips minutes to 1, so a player with 1 minute who scored has `goals_p90 = 90.0`. These players will win every goal-scoring metric comparison against legitimate contenders with no error.

The plan has no minimum sample threshold. Suggested guard: require `appearances >= 5` or `minutes_played >= 270` (3 full games) before including a player in metric percentile ranking. Both players failing this threshold could be flagged in `data_warning`.

---

### 3.2 GK vs GK comparison produces five draws and an uninformative verdict

When both players are GKs, `_pct_rank` returns approximately 50.0 for `goals_p90`, `assists_p90`, and `gc_p90` — because the majority of GKs have 0 in all three, and the midpoint method assigns everyone in the tied cluster the middle rank. The result is:

- Five metrics, each at ~50th percentile for both players
- All five declared draws (advantage = 0)
- `metrics_won: {player1: 0, player2: 0, draw: 5}`
- Verdict: "These players are evenly matched"

This is technically correct and not a crash, but it tells the user nothing. The `data_warning` fires but the comparison still runs to completion and produces a confident-sounding response. The plan should specify that GK vs GK comparisons return a truncated response that only reports the `appearances` and `minutes_share` metrics (where meaningful GK data exists), with all other metrics suppressed.

---

### 3.3 Unknown or null position value

If `player_row["position"]` is null, empty, or a non-standard value (e.g., "AM", "WB", "LWB"), the peer group `enriched[enriched["position"] == pos]` returns an empty DataFrame. `_pct_rank(value, empty_series)` returns 50.0 by design (the `if not valid.size` guard). Every metric becomes a draw.

No error is raised. The response looks normal. This is a silent data quality failure. The plan should specify that an unknown position triggers a 422 or results in a `data_warning`.

---

### 3.4 `minutes_share` can exceed 1.0

`_add_rate_cols()` computes `minutes_share = mins / (apps * 90)`. A player who regularly plays extra time (91–120 minutes per game) will have a `minutes_share` above 1.0. This player appears as having more than 100% availability, which is not meaningful and could rank them above players with perfect 90-minute availability.

The plan does not clip `minutes_share` to `[0, 1]`. Neither does `_add_rate_cols()`. The comparison engine inherits this unconstrained value.

---

### 3.5 `advantage` is set to 0.0 for all draws — loses information

The plan specifies: `advantage: 0.0 when draw`. This means a metric where the gap is exactly 0 (identical players) and a metric where the gap is 4.9 (just under the draw threshold) both report `advantage: 0.0`. The frontend cannot distinguish "these players are identical here" from "these players nearly had a winner here".

**Fix:** Set `advantage` to the actual absolute percentile difference in all cases. Let the `winner` field indicate whether it crossed the draw threshold. The frontend can then render "draw (4.9 pts)" differently from "draw (0.0 pts)".

---

### 3.6 Response is order-dependent with no canonical form

`compare?player1=A&player2=B` and `compare?player1=B&player2=A` return structurally mirrored responses. This has two consequences:

1. A client that receives both calls will store what appears to be two different comparisons, when they are the same comparison from two perspectives.
2. Future HTTP caching (at the CDN or application level) cannot deduplicate these without canonicalisation.

**Fix:** At the service level, sort the two player IDs so the lower ID is always `player1`. Return the response in this canonical order regardless of how the parameters were passed. If the client passed them in a different order, the `player1` and `player2` fields in the response still show the correct identities.

---

## 4. Situations Where the Verdict Becomes Misleading

### 4.1 The "dominant winner" template fires on correlated metrics

The plan triggers the "dominant winner — leads 4+ metrics" template when a player leads on 4 or more metrics. Due to finding 2.1, a player who wins goals_per_90 and assists_per_90 automatically also wins goal_contributions_per_90. Win those three plus appearances or minutes_share and the template fires: "Player X holds a clear advantage."

But the actual independent wins are two (goals and assists). "Dominant winner" on 2 independent metrics is an overclaim.

---

### 4.2 Mbappé vs a defensive midfielder — structurally unfair comparison

The plan's example 8.2 compares Mbappé (FW) with João Gomes (defensive MF). Mbappé wins all attacking metrics convincingly. The verdict: "Kylian Mbappé dominates on all attacking metrics."

This is technically correct within the comparison engine's logic but misleading in football terms. João Gomes's value is defensive — pressing, ball recovery, positioning — none of which are in the dataset. The comparison is not wrong; it is incomplete. The verdict presents itself as an overall quality judgement when it can only measure one dimension of one player's role.

The `same_position: false` flag surfaces this, but the verdict summary does not mention it prominently enough. A user who reads only the `summary` field receives a misleading impression.

**Fix:** When `same_position` is false, the verdict summary should lead with the limitation, not the conclusion. E.g.: "This cross-position comparison measures only attacking output. On those metrics, Mbappé leads. João Gomes's defensive contributions are not captured."

---

### 4.3 Below-average player "beats" another below-average player

Player A at 30th percentile in goals_per_90 "wins" the metric against Player B at 24th percentile (6-point gap, above the draw threshold). The summary template would say "Player A leads on goal scoring rate." In practice, both players are poor scorers. The verdict creates a false impression of quality.

**Fix:** Qualify the verdict summary with absolute performance level when both players are below 50th percentile. "Player A leads on goal scoring rate, though both players score below the position average" is more honest than an unqualified "Player A leads."

---

### 4.4 "Shared strengths" implies equivalence when magnitudes differ

If player1 has "Goal scoring" as a strength (76th percentile, just over the 75th threshold) and player2 has "Elite goal scoring" (91st percentile), the comparison currently categorises "Goal scoring" and "Elite goal scoring" as separate strings via set difference. This is correct — they are different labels.

But if player1 has "Availability" (75th percentile exactly) and player2 has "Availability" (95th percentile), both are the same string and land in `shared`. The frontend cannot distinguish a close shared strength from a dominated one. "Shared: Availability" implies both players are equally strong on this dimension when one is significantly better.

**Fix:** Availability in `shared` is accurate at the string level. This limitation should be noted in the plan with a recommendation: for any metric in `shared`, the `metrics` array already contains the percentile breakdown, so the frontend should be directed to cross-reference rather than treating `shared` as "equal".

---

### 4.5 All-draws verdict when players are genuinely close

If all five metrics produce draws (advantages all < 5 points), `metrics_won` is `{player1: 0, player2: 0, draw: 5}` and winner = "draw". The summary says "evenly matched."

This is the one case where the system is most accurate — these players genuinely are close across all measured dimensions. But the summary template for draws is the same regardless of whether it was 5 draws at 0.0-point gaps (identical players) or 5 draws at 4.9-point gaps (very close but consistently leaning one direction). There is no way to distinguish "literally the same player" from "extremely close over every single metric".

A secondary signal — total percentile advantage sum — would distinguish these cases and produce a more informative summary.

---

## 5. Findings Summary

| # | Area | Severity | Description |
|---|---|---|---|
| 1.1 | Implementation bug | **Critical** | Column names in COMPARISON_METRICS (`goals_per_90`) don't match `_add_rate_cols()` output (`goals_p90`) |
| 1.2 | Implementation bug | **Critical** | `raw_value_key` maps to wrong sources; `minutes_share` value not in `_stats_summary()` at all |
| 1.3 | Implementation bug | Moderate | `appearances` not produced by `_add_rate_cols()` — plan description is misleading |
| 1.4 | Implementation bug | Minor | `data_warning` not set for cross-position DF/GK comparisons |
| 2.1 | Logic flaw | **High** | `goal_contributions_per_90` is linearly dependent on the other two — inflates `metrics_won` |
| 2.2 | Logic flaw | **High** | `metrics_won` count ignores magnitude — 60-point vs 5-point win count the same |
| 2.3 | Logic flaw | Moderate | Structural weakness labels ("Defensive contribution") pollute shared/unique breakdown |
| 3.1 | Edge case | High | No minimum sample size — 1-game players produce extreme per-90 rates |
| 3.2 | Edge case | Moderate | GK vs GK: five draws, uninformative verdict |
| 3.3 | Edge case | Moderate | Unknown position → silent all-50th-percentile result |
| 3.4 | Edge case | Minor | `minutes_share` can exceed 1.0 for extra-time players |
| 3.5 | Edge case | Minor | `advantage: 0.0` for all draws loses information about how close the draw was |
| 3.6 | Edge case | Minor | No canonical parameter order — same comparison is cacheable as two different requests |
| 4.1 | Misleading verdict | High | "Dominant winner" fires on correlated metrics (not independent evidence) |
| 4.2 | Misleading verdict | High | FW vs DF verdict sounds like overall quality judgement; limitation buried |
| 4.3 | Misleading verdict | Moderate | Both-below-average "winner" declared without qualifying absolute level |
| 4.4 | Misleading verdict | Minor | "Shared" strength implies equal magnitude; not surfaced |
| 4.5 | Misleading verdict | Minor | All-draws verdict indistinguishable from "identical players" vs "consistently close" |

---

## 6. Recommended Changes to the Plan Before Implementation

**Must fix before writing any code:**

1. Align `COMPARISON_METRICS` key names with `_add_rate_cols()` output: `goals_p90`, `assists_p90`, `gc_p90`.
2. Remove `raw_value_key` from metric config. Source `MetricPlayerValue.value` from the enriched row directly using `metric_key`.
3. Remove `goal_contributions_per_90` from scored metrics. Retain it as a displayed statistic but exclude it from `metrics_won` counting.
4. Replace simple `metrics_won` win count with a weighted verdict: sum the percentile advantages per player as a tiebreaker. Declare winner by total advantage when win counts are equal.

**Should fix before implementation:**

5. Add minimum sample size guard (≥ 5 appearances or ≥ 270 minutes) with `data_warning` when either player is below it.
6. Filter structural `_weaknesses()` labels (those appended unconditionally, not from percentile checks) from the shared/exclusive breakdown.
7. Expand `data_warning` to fire for cross-position comparisons involving DF or GK.
8. Canonicalise parameter order at the service level (lower ID = player1).
9. Set `advantage` to the actual difference in all cases, not 0.0 for draws.

**Can address post-implementation:**

10. GK vs GK: suppress non-availability metrics from the response.
11. Cross-position verdict summary: lead with the limitation, not the conclusion.
12. Both-below-average qualifier in summary text.
13. Clip `minutes_share` to [0, 1] in `_add_rate_cols()` — but this modifies an existing module; coordinate with profile generator.

---

END OF DOCUMENT
