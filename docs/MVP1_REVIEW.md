# Football Intelligence — MVP 1 Code Review

Date: 2026-06-15
Scope: analytics/prepare_data.py, analytics/player_search.py, analytics/profile_generator.py, analytics/app.py
Status: P1 items resolved 2026-06-15. P2/P3 items open.

---

## Summary

Four files reviewed. No crash-level bugs in the happy path. The implementation runs end-to-end
correctly for the tested cases. The issues found fall into three categories:

- **Analysis correctness** — profile output that is technically wrong or misleading
- **Architecture** — structural problems that will block FastAPI integration
- **Code quality** — design smells and maintainability debt

Total issues: 16. Priority breakdown: P1 (must fix before MVP 2) — 5, P2 (fix before FastAPI) — 5, P3 (clean-up) — 6.

---

## Priority Matrix

| # | Issue | File | Priority | Type | Status |
|---|---|---|---|---|---|
| 1 | DF/GK goal output never evaluated as strength | profile_generator.py | P1 | Correctness | **RESOLVED** |
| 2 | `_pct_rank` strict `<` distorts tied distributions | profile_generator.py | P1 | Correctness | **RESOLVED** |
| 3 | Overview "Exceptional" inconsistent with non-elite strength labels | profile_generator.py | P1 | Correctness | Open |
| 4 | `sys.exit()` inside `run()` — unusable as library function | app.py | P1 | Architecture | **RESOLVED** |
| 5 | No `__init__.py` — `sys.path.insert` won't compose with FastAPI | all | P1 | Architecture | **RESOLVED** |
| 6 | `generate_profile` recomputes full-dataset rates on every call | profile_generator.py | P2 | Performance | Open |
| 7 | `DISPLAY_COLUMNS` silently drops schema columns | player_search.py | P2 | Architecture | Open |
| 8 | Multi-player selection logic duplicated | app.py / profile_generator.py | P2 | Architecture | Open |
| 9 | Magic numbers in profile logic | profile_generator.py | P2 | Quality | Open |
| 10 | DATA_SCHEMA.md output path is wrong | DATA_SCHEMA.md | P2 | Documentation | **RESOLVED** |
| 11 | `drop` closure over mutable `df` in `validate` | prepare_data.py | P3 | Design smell | Open |
| 12 | `_f` function name too short | profile_generator.py | P3 | Naming | Open |
| 13 | `format_result` / `print_results` are dead code in app flow | player_search.py | P3 | Unused code | Open |
| 14 | FW always has "Defensive contribution" weakness — no threshold | profile_generator.py | P3 | Design | Open |
| 15 | Availability strength/weakness threshold asymmetry for GK/DF | profile_generator.py | P3 | Design | Open |
| 16 | No unit tests | all | P3 | Quality | Open |

---

## File-by-File Findings

---

### 1. prepare_data.py

#### Issue 11 (P3) — `drop` closure over mutable `df`

`validate()` defines a nested `drop()` function that closes over the local variable `df`:

```python
def validate(df: pd.DataFrame) -> pd.DataFrame:
    def drop(mask, reason):
        n = (~mask).sum()
        ...
        return df[mask].copy()   # <-- closes over outer df

    df = drop(df["player_name"].notna() ..., "missing player_name")
    df = drop(df["club"].notna() ...,        "missing club")
    ...
```

Python closures capture variable names, not values. Each call to `drop` sees the *current*
value of `df` at call time, which is the already-filtered result of the previous call.
The code works correctly because the mask is always computed from `df` immediately before
the call, so mask and `df` are always aligned.

However, the pattern is fragile: a reader may reasonably assume `drop` operates on the
original `df`, which is wrong. If the mask were ever computed ahead of time and stored, the
mismatch would produce a silent wrong result.

**Recommendation:** pass `df` as an explicit parameter to `drop` to remove the dependency
on closure state.

#### No other bugs found in prepare_data.py

The normalisation pipeline, Int64 casting, deduplication logic, and error handling are all
correct. The `bad_min` anomaly flag at `appearances * 95` is conservative but reasonable.
The output of `prepare_data.py` (2,476 rows, 12 columns, zero nulls) is verified correct.

---

### 2. player_search.py

#### Issue 7 (P2) — `DISPLAY_COLUMNS` silently drops schema columns

`search_exact` and `search_partial` both apply `DISPLAY_COLUMNS` before returning:

```python
return df[mask][DISPLAY_COLUMNS].reset_index(drop=True)
```

This means every caller (including `profile_generator.generate_profile`) receives a filtered
view of the DataFrame. If a new column is added to `prepare_data.py` and `cleaned_players.csv`
but not to `DISPLAY_COLUMNS`, it silently disappears from every downstream consumer.

This was already encountered: `season` was absent from the original `DISPLAY_COLUMNS` and
caused a `KeyError` in `generate_profile`. The fix required editing `player_search.py` to add
the column. As the schema grows toward MVP 2 (new statistics columns), this will need to be
repeated for every new field.

**Recommendation:** remove the `DISPLAY_COLUMNS` filter from `search_exact` and
`search_partial`. Apply it only in `format_result` and `print_results` (the display path),
not in the data-retrieval path. The retrieval functions should return the full row.

#### Issue 13 (P3) — `format_result` and `print_results` are dead code in the app flow

`app.py` calls `generate_profile` + `print_profile` from `profile_generator.py`.
It never calls `format_result` or `print_results` from `player_search.py`. These functions
are only reachable when `player_search.py` is run directly as a standalone CLI.

The functions are not wrong — they serve the standalone use case correctly. But they add
surface area that can drift from the app's actual output format. If the schema changes,
`format_result` may show stale field names while `print_profile` is updated.

**Recommendation:** annotate these as the standalone-CLI display path, or consolidate display
logic into a single module.

---

### 3. profile_generator.py

#### ~~Issue 1 (P1)~~ — DF and GK goal output never evaluated as a strength — **RESOLVED**

`_strengths` only evaluates `goals_p90`, `assists_p90`, and `gc_p90` for
`pos in ("FW", "MF")`. Defenders and goalkeepers are excluded entirely:

```python
if pos in ("FW", "MF"):
    if g_p >= ELITE_THRESHOLD:
        out.append("Elite goal scoring")
    ...
```

**Impact — verified with data:**

189 out of 755 DF players (25%) are above the 75th-percentile threshold for `goals_p90`
among defenders. These players get no strength label for their goal output.

The five highest-scoring defenders in the dataset:

| Player | Goals | Appearances | goals_p90 pct (DF group) |
|---|---|---|---|
| Virgil van Dijk | 6 | 38 | 94.2th |
| Carlos Romero | 6 | 36 | 94.2th |
| Luka Vušković | 6 | 28 | 94.2th |
| Maximilian Mittelstädt | 6 | 32 | 94.2th |
| Danilho Doekhi | 5 | 34 | ~88th |

Van Dijk scoring 6 goals in 38 league appearances is genuinely exceptional for a centre-back.
The profile for Van Dijk currently lists only "Availability" as a strength with no mention
of his goal output.

**Recommendation:** extend `_strengths` to evaluate `goals_p90` for DF (not GK) when it
exceeds STRENGTH_THRESHOLD. Use a position-contextual label such as
"Goal threat from set pieces / dead balls" rather than the generic "Goal scoring".

#### ~~Issue 2 (P1)~~ — `_pct_rank` strict `<` distorts tied distributions — **RESOLVED**

```python
def _pct_rank(value: float, series: pd.Series) -> float:
    valid = series.dropna()
    return float((valid < value).sum() / len(valid) * 100)
```

Strict less-than assigns a low rank to any player at the median of a tie cluster.

**Verified with data — GK minutes_share:**

- 129 of 187 GKs (69%) have `minutes_share == 1.0` (always played the full 90 minutes).
- `_pct_rank(1.0, gk.minutes_share)` returns **31.0** because only 58 GKs have
  `minutes_share < 1.0`.
- The midpoint rank (standard scipy convention) would be **65.5**.

A goalkeeper who always completes 90 minutes is ranked at the 31st percentile by the current
implementation — below the median — despite being statistically among the more reliable keepers.
This is why Thibaut Courtois (32 appearances, 2880 minutes, minutes_share = 1.0) received
only 31st-percentile minutes_share and was initially showing "Insufficient data" for strengths.

The same effect applies wherever values cluster at round numbers (0.0 for gc_p90 — 220 MF
players, i.e. 19.7% of the peer group, have exactly 0.0).

**Recommendation:** replace strict `<` with the midpoint method:

```python
def _pct_rank(value: float, series: pd.Series) -> float:
    valid = series.dropna()
    if not valid.size:
        return 50.0
    below = (valid < value).sum()
    equal = (valid == value).sum()
    return float((below + equal / 2) / len(valid) * 100)
```

This is the standard "percentile of score" method and produces fair results for tied groups.

#### Issue 3 (P1) — Overview "Exceptional" is inconsistent with non-elite strength labels

`_overview` and `_strengths` use the same thresholds but evaluate different metrics:

- `_overview` for MF fires `ELITE_THRESHOLD` when `gc_p90 >= 90`
- `_strengths` fires `ELITE_THRESHOLD` for goals and assists separately

**Verified with Mohamed Salah:**

| Metric | Value | Percentile |
|---|---|---|
| goals_p90 | 0.294 | **87.6th** |
| assists_p90 | 0.294 | **91.2th** |
| gc_p90 | 0.587 | **92.8th** |

Because `gc_p90 >= 90`, the overview says **"Exceptional midfielder delivering elite goal
contributions"**. But because `goals_p90 = 87.6 < 90`, the strength label is plain
**"Goal scoring"** (not "Elite goal scoring").

A user reads: "Exceptional midfielder" in the headline, then "Goal scoring" (non-elite) in the
body. The two code paths use the same threshold on different metrics, producing contradictory
output.

**Recommendation:** align the overview tier with the strength labels it produces. Two options:
- Make the overview use the same per-metric breakdown as strengths (not aggregate gc_p90).
- Or make strengths also check gc_p90 for the "elite" label, not just individual metrics.

#### Issue 6 (P2) — `generate_profile` recomputes `_add_rate_cols(all_df)` on every call

```python
def generate_profile(player_row, all_df):
    enriched = _add_rate_cols(all_df)       # full 2476-row computation
    player_e = _add_rate_cols(pd.DataFrame([player_row])).iloc[0]
    peer_df = enriched[enriched["position"] == pos]
```

`_add_rate_cols` on 2,476 rows takes approximately **1.37ms** per call. For a single CLI query
this is negligible. But when FastAPI serves concurrent requests — or when a batch endpoint
generates profiles for a squad (25+ players) — this will scale linearly: 25 calls × 1.37ms
for the same data = 34ms of unnecessary recomputation per request.

The enriched DataFrame is derived entirely from `all_df`, which does not change between calls.

**Recommendation:** cache the enriched DataFrame. The simplest approach for MVP 2:

```python
_enriched_cache: pd.DataFrame | None = None

def _get_enriched(df: pd.DataFrame) -> pd.DataFrame:
    global _enriched_cache
    if _enriched_cache is None:
        _enriched_cache = _add_rate_cols(df)
    return _enriched_cache
```

A production approach would pass the pre-enriched DataFrame in at application startup.

#### Issue 9 (P2) — Magic numbers in profile logic

The following literal values appear inline with no named constant:

| Value | Location | Meaning |
|---|---|---|
| `65` | `_strengths`, `_overview` | GK/DF availability threshold (not 75) |
| `0.25` | `_strengths` line 164 | Minimum penalty fraction for "Penalty conversion" strength |
| `4` | `_strengths` line 164 | Minimum raw penalty goal count |
| `0.40` | `_weaknesses` line 194 | Penalty fraction for "Heavy reliance" weakness |
| `23` | `_overview` line 113 | Age cutoff for "Young defender" label |

If the penalty thresholds need adjustment after review, a developer must find all four magic
values scattered across two functions. There is also no explicit constant documenting why GK/DF
use 65 vs the standard 75.

**Recommendation:** group all tunable constants at the top of the file alongside `STRENGTH_THRESHOLD`:

```python
GK_DF_AVAIL_THRESHOLD = 65     # lower band: appearances is the only GK/DF metric available
YOUNG_PLAYER_AGE = 23
PENALTY_MIN_GOALS = 5
PENALTY_MIN_RAW = 4
PENALTY_STRENGTH_RATIO = 0.25
PENALTY_RELIANCE_RATIO = 0.40
```

#### Issue 14 (P3) — FW always gets "Defensive contribution" as a weakness

```python
if pos == "FW":
    out.append("Defensive contribution")
```

This is unconditional. Every FW in the dataset — including players with zero other weaknesses —
receives this entry. The structural observation is defensible in football analytics terms, but
the implementation means:

- GK, DF, and MF can return "No notable weaknesses identified"
- FW always returns at least one weakness regardless of performance

If the product evolution moves toward AI text generation, the AI will see "Defensive
contribution" as a weakness for every striker and will likely produce repetitive analysis.

**Recommendation:** either apply a data condition (e.g. flag only when defensive stats are
requested and confirmed absent), or document it explicitly as a position-structural constant
rather than a data-derived weakness.

#### Issue 15 (P3) — Availability strength/weakness threshold asymmetry for GK/DF

Strengths: GK/DF use 65th-percentile threshold for "Availability".
Weaknesses: `pct["appearances"] <= WEAKNESS_THRESHOLD` (25th) applies to all positions.

A GK with 66th-percentile appearances gets "Availability" as a strength.
A GK with 26th-percentile appearances does not get "Limited appearances" as a weakness.
A GK between 25th and 65th percentile gets neither — an informational void.

The asymmetry was introduced when the GK strength threshold was lowered as a workaround for
the `_pct_rank` tied-value issue. Fixing Issue 2 (midpoint percentile) may resolve the
original threshold problem and allow GK/DF to use the standard 75/25 split.

---

### 4. app.py

#### ~~Issue 4 (P1)~~ — `sys.exit()` inside `run()` makes it unusable as a library function — **RESOLVED**

`run()` is designed to be callable by FastAPI (it accepts an optional `query` string).
But it calls `sys.exit()` in four places:

```python
def run(query: str | None = None) -> None:
    ...
    except FileNotFoundError:
        sys.exit(1)          # terminates the whole process
    ...
    if not query:
        sys.exit(1)          # same
    if results.empty:
        sys.exit(0)          # same
```

A FastAPI route handler that calls `run("Kane")` would terminate the entire server process
when the player is not found. `sys.exit()` raises `SystemExit`, which propagates through
all except clauses unless explicitly caught.

**Recommendation:** raise typed exceptions from `run()` and let `main()` handle the exit:

```python
class PlayerNotFoundError(Exception): ...
class DatasetNotFoundError(Exception): ...

def run(query: str) -> PlayerProfile:     # returns profile, raises on error
    df = load_players()                   # raises FileNotFoundError
    results = search(df, query)
    if results.empty:
        raise PlayerNotFoundError(query)
    player_row = _pick_player(results)
    return generate_profile(player_row, df)

def main() -> None:
    try:
        profile = run(query)
        print_profile(profile)
    except PlayerNotFoundError as e:
        print(f"Not found: {e}")
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
```

---

### 5. Cross-cutting (all files)

#### ~~Issue 5 (P1)~~ — No `__init__.py` — `sys.path.insert` workarounds won't compose with FastAPI — **RESOLVED**

`app.py` and `profile_generator.py` both use:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
```

This works when the files are run directly. It breaks when imported from outside the
`analytics/` directory (e.g., from a FastAPI `main.py` at the repo root) because:
- The `sys.path.insert` runs on import, but it inserts the path of the *importer's* resolved
  file, not the analytics directory's path.
- If `from analytics.app import run` is used, the relative imports inside `app.py` fail
  because `analytics/` is not a package.

**Recommendation:** add `analytics/__init__.py` (empty file) and convert all intra-package
imports to relative:

```python
# In profile_generator.py
from .player_search import load_players, search
```

This is the correct pattern for any module that will be imported by FastAPI.

#### Issue 8 (P2) — Multi-player selection logic is duplicated

`profile_generator.main()` (lines 334–350) and `app.py._pick_player()` (lines 30–45) contain
independent implementations of the same multi-player selection UI. They differ in one way:
`profile_generator.main()` checks `sys.stdin.isatty()` before prompting; `_pick_player()`
does not.

Both exist because `profile_generator.py` has its own `main()` for standalone use. The
standalone `main()` was not removed when `app.py` was introduced as the canonical entry point.

**Recommendation:** remove the multi-player selection logic from `profile_generator.main()`.
Have `profile_generator.main()` call `app.run()` instead, or delegate selection to a shared
utility function in `player_search.py` (which already handles search).

#### Issue 16 (P3) — No unit tests

None of the four modules has a corresponding test file. The validation currently relies on
manual end-to-end CLI runs. Before FastAPI integration, the following functions should have
unit tests as a minimum:

| Function | Test cases needed |
|---|---|
| `normalise_nationality` | `"us USA"` → `"United States"`, missing, unknown code |
| `normalise_position` | `"MF,FW"` → `"MF"`, invalid → `None` |
| `normalise_competition` | `"eng Premier League"` → `"Premier League"`, unknown prefix |
| `search_exact` | match, no match, case-insensitive |
| `search_partial` | substring, no match, accent character |
| `_pct_rank` | normal, all-tied, empty series |
| `generate_profile` | FW, MF, DF, GK — verify overview/strengths/weaknesses types |

---

## Findings Not in the Issue List

The following were checked and found correct:

- **`validate` drop chain** — each filter sees the progressively reduced `df`. Confirmed
  correct despite the closure pattern.
- **Division-by-zero in `_stats_summary`** — guarded by `if mins > 0 else 1`. Since all
  players have `minutes_played >= 90` after filtering, the fallback never fires.
- **Penalty arithmetic** — `goals - npg` with the `goals >= 5` guard prevents division by
  zero. Verified no rows have `non_penalty_goals > goals` in the cleaned dataset (0 rows).
- **`Int64` arithmetic in `_add_rate_cols`** — `.astype(float)` correctly converts nullable
  Int64 to float64, with NA becoming NaN. The `.clip(lower=1)` guards against zero-division.
- **`search_partial` with `regex=False`** — correctly prevents regex injection from user input.
- **Accented player names** — partial search finds `Mbappé` via `"Mbapp"`. No accent
  normalisation needed for the search use case.
- **`DISPLAY_COLUMNS` vs CSV columns** — currently fully aligned. Zero columns missing in
  either direction.

---

## Recommended Fix Order

Fixing in this order minimises rework:

1. **Issue 5** — Add `__init__.py`, convert to relative imports. All other issues reference
   module paths; do this first so subsequent changes don't need to re-handle imports.
2. **Issue 4** — Remove `sys.exit()` from `run()`. Required before any FastAPI work.
3. **Issue 7** — Remove `DISPLAY_COLUMNS` filter from search retrieval path. Required before
   adding MVP 2 schema columns, otherwise each new column needs a manual addition.
4. **Issue 2** — Fix `_pct_rank` to use midpoint method. This may resolve the GK/DF
   threshold workaround (Issue 15), so fix before revisiting that.
5. **Issue 1** — Add DF goal output to strength evaluation. Verify Van Dijk gets "Goal
   threat from set pieces" after Issue 2 is fixed (his percentile may change).
6. **Issue 3** — Align overview and strength tiers. Trivial once Issue 1 and 2 are resolved.
7. **Issues 8, 9, 11, 12, 13, 14, 15, 16** — quality and design cleanup, no strict ordering.

---

## What Is Working Well

- **Pipeline correctness** — `prepare_data.py` produces a clean, validated dataset with
  correct transformations for all five normalization rules (nationality, position, competition,
  age, deduplication).
- **Search reliability** — exact-then-partial fallback is the right design. Case-insensitive.
  No regex injection risk. Handles accented names via substring.
- **Profile architecture** — the `PlayerProfile` dataclass with only JSON-serializable types
  is well-designed for future FastAPI serialization.
- **Percentile approach** — comparing against position peers (FW vs FW, not all players)
  is analytically sound and produces meaningful relative rankings.
- **Error handling** — all I/O operations (file load, user input, `EOFError`) are handled.
  No unguarded exceptions in the happy path.
- **Modularity** — each module has a single clear responsibility. `generate_profile` takes
  a row and returns a dataclass, making it trivially testable once tests are added.

---

END OF DOCUMENT
