# Football Intelligence — MVP2-1 Implementation Plan

Version: 1.0
Status: Ready for Implementation
Date: 2026-06-19
Depends on: docs/MVP2_1_DASHBOARD_PLAN.md

---

## 1. Overview

MVP2-1 delivers the Analytics Dashboard through six sequential phases. Phases 0–1
are backend and infrastructure changes; Phases 2–4 build the three frontend pages;
Phase 5 is integration QA. The phases are ordered so that each one produces a
independently testable deliverable.

**Total new files:** ~12 (5 backend, 7 frontend)
**Total files modified:** 3 (main.py, schemas or new file, static serving)
**No changes to:** analytics modules, existing API endpoints, dataset

---

## 2. Architecture Decisions (Fixed Before Any Code)

### 2.1 Frontend tech stack

**Choice: Vanilla HTML + CSS + JavaScript served as FastAPI StaticFiles**

Rationale:
- Zero build tooling (no Node, no npm, no webpack)
- FastAPI already running; add one `app.mount("/", StaticFiles(...))` line
- Chart.js loaded from CDN — no bundling
- All three pages can be implemented in under 600 lines of JS total
- Switching to React later is possible without touching the backend

Consequence: No TypeScript, no component framework, no hot reload. Acceptable
for MVP2-1 scope.

### 2.2 Pre-computed enriched DataFrame

**Choice: Enrich the DataFrame once at startup, store as `app.state.enriched_df`**

Currently `_add_rate_cols(df.copy())` is called inside `generate_comparison()`
and `generate_profile()` on every request — O(n) per request. The leaderboard
endpoint needs the same enriched columns for every player. Running it per
leaderboard request would add O(n) work on every page load.

Fix: call `_add_rate_cols` once in the lifespan context manager at startup, store
the result in `app.state.enriched_df`. All endpoints that need computed columns
read from `app.state.enriched_df`. The raw `app.state.df` is still used for
search (which operates on player_name only).

This change touches `backend/main.py` lifespan and all services that currently
call `_add_rate_cols` internally.

### 2.3 Leaderboard endpoint returns computed columns, not percentiles

**Choice: The leaderboard endpoint returns raw stats + computed rate columns only.
It does NOT return percentile ranks.**

Percentile computation requires a full peer-group scan per player. For 2,800 players
at startup that would be 2,800 × position-filtered scans. This is too expensive to
pre-compute for all players, and too slow to compute per-leaderboard-request.

Percentile ranks stay on the individual profile endpoint (`GET /api/v1/players/{id}`)
where they are computed for one player only.

The leaderboard scatter chart (Goals/90 vs Assists/90) uses rate columns, not
percentiles. This is sufficient.

### 2.4 Client-side filtering on leaderboard

**Choice: Load all leaderboard data once into the browser. Filtering and sorting
are client-side JavaScript operations.**

With ~2,800 players × 12 numeric columns, the initial payload is ~400–600 KB
uncompressed, ~60–80 KB gzip. This is well within browser limits and makes
filter/sort operations instant.

The leaderboard endpoint is therefore called once on page load with no filter
parameters. All subsequent filtering (position chip, competition, min appearances)
happens in the browser without additional API calls.

Exception: the search autocomplete in the nav continues to call
`GET /api/v1/players?query=` on every input event (debounced 250ms).

---

## 3. Phase 0 — Backend: Leaderboard Endpoint and Startup Enrichment

**Goal:** Add the one missing endpoint that the leaderboard page requires.
Optimise startup to pre-compute enriched columns.

**Estimated effort:** 1–2 days

### 3.1 New endpoint: GET /api/v1/leaderboard

#### Request parameters

| Parameter | Type | Required | Default | Constraints | Notes |
|---|---|---|---|---|---|
| `position` | string | No | (all) | One of FW, MF, DF, GK | Applied server-side before return |
| `competition` | string | No | (all) | Exact match | Case-insensitive |
| `nationality` | string | No | (all) | Exact match | Case-insensitive |
| `min_appearances` | integer | No | 5 | 0–100 | Matches sample-size rule |
| `min_minutes` | integer | No | 0 | 0–9000 | Optional second threshold |
| `sort_by` | string | No | `goals_p90` | See sort options | |
| `sort_order` | string | No | `desc` | `asc` or `desc` | |
| `limit` | integer | No | 50 | 1–500 | |
| `offset` | integer | No | 0 | ≥ 0 | |

#### Sort options for `sort_by`

| Value | Column sorted | Notes |
|---|---|---|
| `goals_p90` | goals_p90 | Default |
| `assists_p90` | assists_p90 | |
| `gc_p90` | gc_p90 | |
| `goals` | goals | Raw count |
| `assists` | assists | Raw count |
| `appearances` | appearances | |
| `minutes_played` | minutes_played | |
| `minutes_share` | minutes_share | |

Invalid `sort_by` values → 422 with detail listing valid options.
Invalid `sort_order` values → 422.

#### Pagination strategy

Offset-based pagination. Simple to implement, sufficient for 2,800 rows.
Cursor-based pagination is not needed at this dataset scale.

The `total` field in the response always reflects the count after filtering
but before pagination, allowing the frontend to show "Showing 50 of 847".

The leaderboard page's initial load uses `limit=500&offset=0` — enough
to fill the scatter chart with the full filtered dataset in one call. The
table "Load more" button increments offset by 50.

#### Response schema

```
GET /api/v1/leaderboard?position=FW&min_appearances=5&sort_by=goals_p90&limit=2

200 OK
{
  "total": 847,
  "limit": 2,
  "offset": 0,
  "sort_by": "goals_p90",
  "sort_order": "desc",
  "filters_applied": {
    "position": "FW",
    "competition": null,
    "nationality": null,
    "min_appearances": 5,
    "min_minutes": 0
  },
  "players": [
    {
      "id": 1439301664,
      "player_name": "Kylian Mbappé",
      "club": "Real Madrid",
      "competition": "La Liga",
      "nationality": "France",
      "position": "FW",
      "age": 26,
      "season": "2025-26",
      "appearances": 31,
      "minutes_played": 2790,
      "goals": 32,
      "assists": 6,
      "non_penalty_goals": 28,
      "goals_p90": 0.87,
      "assists_p90": 0.17,
      "gc_p90": 1.04,
      "minutes_share": 0.93
    },
    { ... }
  ]
}
```

#### Error responses

```
GET /api/v1/leaderboard?position=XX
422 { "detail": "Invalid position 'XX'. Must be one of: FW, MF, DF, GK." }

GET /api/v1/leaderboard?sort_by=market_value
422 { "detail": "Invalid sort_by 'market_value'. Must be one of: goals_p90, assists_p90, ..." }

GET /api/v1/leaderboard?limit=999
422 { "detail": "limit must be between 1 and 500." }
```

#### Filter metadata endpoint (optional, Nice to Have)

```
GET /api/v1/leaderboard/filters

200 OK
{
  "positions": ["FW", "MF", "DF", "GK"],
  "competitions": ["La Liga", "Premier League", "Bundesliga", ...],
  "nationalities": ["France", "England", "Brazil", ...],
  "seasons": ["2025-26"]
}
```

This allows the frontend to populate filter dropdowns dynamically from the
dataset rather than hardcoding values. Not required for MVP2-1 if values
are included in the initial leaderboard response.

Alternative: include `available_filters` in the main leaderboard response
on the first request (no filters applied). The frontend caches this for the
session. This saves an extra endpoint.

### 3.2 Startup enrichment change

**In `backend/main.py` lifespan:**

Currently: `app.state.df = load_players()`
Change to: also store `app.state.enriched_df = _add_rate_cols(app.state.df.copy())`

**Services that currently call `_add_rate_cols` internally:**
- `analytics/profile_generator.py` → `generate_profile()` — passes df, enriches it
- `analytics/comparison_engine.py` → `generate_comparison()` — passes df, enriches it

Both should be updated to accept an already-enriched DataFrame rather than
enriching it themselves. The service layer passes `app.state.enriched_df`
instead of `app.state.df` to these functions.

This is a minor signature change: `generate_profile(row, df)` →
`generate_profile(row, enriched_df)` and same for `generate_comparison`.
The analytics functions themselves are simplified (remove the `_add_rate_cols`
call from their bodies).

This optimisation is not strictly required for MVP2-1 (the existing behaviour
works), but it eliminates a repeated O(n) computation on every comparison and
profile request. Recommended to do it in Phase 0 while touching main.py.

### 3.3 Files to create or modify

| File | Change |
|---|---|
| `backend/routers/leaderboard.py` | NEW — router with GET /leaderboard |
| `backend/services/leaderboard_service.py` | NEW — filter, sort, paginate logic |
| `backend/models/leaderboard_schemas.py` | NEW — LeaderboardPlayer, LeaderboardResponse |
| `backend/main.py` | MODIFY — add enriched_df to lifespan, mount leaderboard router |
| `backend/dependencies.py` | MODIFY — add get_enriched_df dependency |

No changes to analytics modules in Phase 0.

### 3.4 Phase 0 test strategy

- Unit tests for `leaderboard_service.py`:
  - Filter by position (FW only returns FW)
  - Filter by min_appearances (players below threshold excluded)
  - Sort by goals_p90 descending (first player has highest goals_p90)
  - Sort by appearances ascending
  - Pagination: offset=0 limit=2 returns first 2; offset=2 limit=2 returns next 2
  - `total` reflects post-filter count, not paginated count
  - Invalid position → ValueError (caught by router → 422)
  - Invalid sort_by → ValueError (caught by router → 422)
  - Empty result set (filter excludes all players) → `total=0, players=[]`
- Curl tests: confirm response shape, confirm `filters_applied` matches params
- Confirm `/health` still returns 200 after startup change (enriched_df adds to lifespan)

### 3.5 Phase 0 risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `_add_rate_cols` signature changes break existing profile/comparison | Low | High | Run existing test suite after change |
| enriched_df memory doubles dataset size at startup | Low | Low | ~2,800 rows × 16 cols ≈ negligible |
| minutes_share outliers (> 1.0) appear in leaderboard | Certain | Low | Frontend caps bar display; raw value shown in tooltip |

---

## 4. Phase 1 — Frontend Shell

**Goal:** Establish the HTML/CSS/JS skeleton. Navigation bar, search
autocomplete, health indicator, and routing all work before any page
content is built.

**Estimated effort:** 1 day

### 4.1 Files to create

```
frontend/
├── index.html          Leaderboard page shell (table placeholder)
├── player.html         Profile page shell (card placeholder)
├── compare.html        Comparison page shell (layout placeholder)
├── css/
│   └── app.css         Base styles, nav bar, typography, colour tokens
└── js/
    ├── api.js          API client: all fetch() calls, error handling
    └── nav.js          Nav bar init, search autocomplete, health poll
```

`frontend/` sits at the project root alongside `analytics/` and `backend/`.

### 4.2 Serving the frontend

Add to `backend/main.py` (one line, after all routers are mounted):

```
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
```

This serves `index.html` at `/`, `player.html` at `/player.html`, etc.
The existing API routes (`/api/v1/...`) take priority because they are
registered before the static mount.

### 4.3 api.js responsibilities

All network calls go through `api.js`. No page script calls `fetch()` directly.

Functions:
```
searchPlayers(query)          → GET /api/v1/players?query={query}
getPlayer(id)                 → GET /api/v1/players/{id}
getLeaderboard(params)        → GET /api/v1/leaderboard?{params}
comparePlayer(p1Id, p2Id)     → GET /api/v1/compare?player1={p1}&player2={p2}
getHealth()                   → GET /health
```

Each function:
- Returns a Promise that resolves to the parsed JSON body
- On non-2xx: rejects with `{ status, detail }` extracted from the error body
- The caller handles the error (show banner, not crash)

### 4.4 nav.js responsibilities

- Renders nav bar with logo and search input
- Debounces search input at 250ms
- On input (≥ 2 chars): calls `searchPlayers(query)`, renders dropdown of top 5
- On player select: navigates to `/player.html?id={id}`
- On Enter with no selection: navigates to `/player.html?id={first result id}`
- Polls `getHealth()` every 60 seconds; shows green/red dot in nav
- Exported function `initNav()` called by each page on load

### 4.5 URL and state strategy

All page-to-page navigation uses standard HTML anchor `href` attributes and
`URLSearchParams` to pass IDs. No client-side router. No `history.pushState`.

| Page | URL pattern | State from |
|---|---|---|
| Leaderboard | `/` or `/index.html` | No params (loads all) |
| Profile | `/player.html?id={player_id}` | `URLSearchParams` |
| Comparison | `/compare.html?p1={id}&p2={id}` | `URLSearchParams` |

This makes every page directly linkable and bookmarkable with no router complexity.

### 4.6 Phase 1 test strategy

- Open `http://127.0.0.1:8001` in browser → index.html loads
- Open `http://127.0.0.1:8001/player.html?id=1439301664` → no 404
- Open `http://127.0.0.1:8001/compare.html?p1=A&p2=B` → no 404
- Type 2+ chars in search → dropdown appears with player names
- Select player from dropdown → navigates to player.html
- Health dot → green when server is up, red when server is stopped
- DevTools Network: confirm all fetch calls go to `/api/v1/...`
- DevTools Console: no uncaught errors on page load

### 4.7 Phase 1 risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| StaticFiles mount catches API routes | Low | High | Register all API routers before mounting static |
| CORS errors if frontend served from different port | Low | Medium | Frontend served by same FastAPI server; no CORS issue |
| Search autocomplete fires before Phase 0 leaderboard endpoint is ready | N/A | N/A | Autocomplete uses existing `/api/v1/players` endpoint |

---

## 5. Phase 2 — Leaderboard Page

**Goal:** Complete the Leaderboard page: table with sorting and filters,
scatter chart, and the two-player compare selection flow.

**Estimated effort:** 2–3 days

### 5.1 Files to create or modify

| File | Change |
|---|---|
| `frontend/index.html` | MODIFY — add table, filter bar, chart container markup |
| `frontend/js/leaderboard.js` | NEW — all leaderboard page logic |

External dependency loaded from CDN:
- Chart.js v4 (`<script src="https://cdn.jsdelivr.net/npm/chart.js">`)
  Added to `index.html` only. No other pages need it.

### 5.2 leaderboard.js responsibilities

On page load:
1. Call `getLeaderboard({ limit: 500, offset: 0 })` — fetches the full unfiltered dataset
2. Store result in a module-level `state.allPlayers` array
3. Extract distinct competitions and nationalities from the result; populate
   the filter dropdowns
4. Render the table with default sort (goals_p90 desc) and default filter
   (min_appearances = 5, position = All)
5. Render the scatter chart with the same filtered set

On filter/sort change:
1. Re-filter `state.allPlayers` client-side
2. Re-render table (first 50 rows) and scatter chart
3. No API call

Table interactions:
- Column header click → sort by that column (toggle asc/desc)
- Player name click → navigate to `/player.html?id={id}`
- Checkbox select (max 2) → "Compare selected" button appears
- "Compare selected" → navigate to `/compare.html?p1={id1}&p2={id2}`
- "Load more" → append next 50 rows from `state.filteredPlayers`

Filter bar:
- Position chips: click to toggle (multi-select; All deselects others)
- Competition dropdown: multi-select; default All
- Min Appearances slider: integer 0–38; default 5
- "Reset filters" link restores defaults

### 5.3 Scatter chart spec

Library: Chart.js Scatter type

Data: one point per player in the current filtered set (not paginated).

```
{
  x: player.goals_p90,
  y: player.assists_p90,
  label: player.player_name,    // for tooltip
  club: player.club,
  position: player.position,
  id: player.id
}
```

Colours by position:
- FW → #3B82F6 (blue)
- MF → #10B981 (green)
- DF → #F59E0B (amber)
- GK → #EF4444 (red)

Axes:
- X: Goals/90 (min 0, max determined by data, soft cap at 1.5 with note)
- Y: Assists/90 (min 0, max determined by data)

Tooltip on hover: "Player Name\nClub · Position\nG/90: 0.87 · A/90: 0.17"

Click on point: navigate to `/player.html?id={player.id}`

Points > 500: show a notice "Chart shows top 500 players by {sort_by}.
Use filters to narrow the view." Do not plot all 2,800 at once.

### 5.4 Phase 2 test strategy

- Leaderboard loads: table shows 50 rows, scatter shows up to 500 points
- Default sort is Goals/90 desc: first row has highest goals_p90 in unfiltered set
- Click Goals/90 header: re-sorts asc; click again → desc
- Position chip "FW": table and scatter show only FW players
- Min Appearances = 0: more players appear (including small-sample ones)
- Competition filter: only players from that competition shown
- Checkbox two players → "Compare selected" appears → click → compare.html loads
- Player name click → player.html loads with correct id
- DevTools Network: confirm only one API call made on load; no calls on filter change

### 5.5 Phase 2 risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| 500-player scatter is too dense to read | High | Medium | Default to FW filter; label: "Showing Forwards" |
| Competition dropdown has 20+ competitions | Certain | Low | Multi-select with search/filter within the dropdown |
| Client-side sort of 2,800 rows is slow in old browsers | Low | Low | JS sort of 2,800 objects is sub-millisecond in any modern browser |
| "Load more" confuses users who expect infinite scroll | Low | Low | Label button "Show next 50 players" |
| Chart.js CDN unavailable | Very Low | Medium | Scatter chart degrades gracefully to table-only; catch script error |

---

## 6. Phase 3 — Player Profile Page

**Goal:** Complete the profile page with the stat overview, percentile bars,
strengths/weaknesses, and "Compare with..." flow.

**Estimated effort:** 1–2 days

### 6.1 Files to create or modify

| File | Change |
|---|---|
| `frontend/player.html` | MODIFY — add card, stats, bars, chips markup |
| `frontend/js/player.js` | NEW — profile page logic |

### 6.2 player.js responsibilities

On page load:
1. Read `id` from `URLSearchParams`
2. If no id → redirect to `/` (no silent fail)
3. Call `getPlayer(id)` → render profile
4. If 404 → show "Player not found" with a link back to leaderboard

Rendering:
- Header card: name, club, competition, position, age, season
- data_warning banner: yellow, shown only if profile response contains a warning
  (for low-minutes players) — note: the existing profile endpoint does not return
  a data_warning field, only the comparison endpoint does. For MVP2-1, compute the
  warning client-side: if `appearances < 5 || minutes_played < 270`, show the
  same text as the comparison engine would.
- Stats overview: display all 7 raw/computed stats in a two-column grid
- Percentile bars: one bar per metric (goals_p90, assists_p90, appearances,
  minutes_share, gc_p90); bar width = percentile value; colour by threshold
- Peer group footnote: "Percentiles ranked among {peer_group_size} {position} players"
- Strengths chips: green pill badges from `profile.strengths`
- Weaknesses chips: amber pill badges from `profile.weaknesses`
- DF/GK disclaimer: if position is DF or GK, show a static note below percentile
  bars: "Defensive metrics are not available in the current dataset. These
  percentiles reflect attacking output only."

"Compare with another player" flow:
- Renders a search input inline on the profile page (not the nav bar)
- On selection: navigates to `/compare.html?p1={current_id}&p2={selected_id}`
- If current player is a GK: show "Cross-position comparisons will include a
  data warning" below the compare input

### 6.3 Percentile bar component spec

Each bar:
```
[Label]      [Value]   [Bar ████████░░░] [Percentile]
Goals/90     0.87      ████████████░░░   92nd
```

Bar fill colour:
- ≥ 70: #10B981 (green)
- 40–69: #F59E0B (amber)
- < 40: #EF4444 (red)

Bar container is always 100% width. Filled portion = `percentile / 100 * 100%`.
Tooltip: "Better than {percentile}% of {position} players in the dataset."

`gc_p90` bar has a ⓘ label: "Display only — not used in comparison scoring."
This prevents users from thinking gc_p90 is an independent metric.

### 6.4 Phase 3 test strategy

- Navigate to `/player.html?id={valid_id}` → profile renders correctly
- Navigate to `/player.html?id=0` (invalid) → "Player not found" message
- Navigate to `/player.html` (no id) → redirects to `/`
- GK player → DF/GK disclaimer is visible
- Player with < 5 appearances → data_warning banner appears
- All percentile bars render with correct colours
- "Compare with..." search → type a name → select player → navigates to compare.html
- DF player: percentile bars render (low values expected); disclaimer shown

### 6.5 Phase 3 risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Profile API does not return data_warning | Certain | Low | Compute client-side using same thresholds (apps < 5 OR mins < 270) |
| Percentile bars look alarming for DF (red bars) | Certain | Medium | DF/GK disclaimer + note on peer group |
| "Compare with..." search conflicts with nav search | Low | Low | Give inline search a distinct placeholder text and container |

---

## 7. Phase 4 — Comparison Page

**Goal:** Complete the head-to-head comparison page with dual metric bars,
WAS verdict card, and strengths/weaknesses breakdown.

**Estimated effort:** 2 days

### 7.1 Files to create or modify

| File | Change |
|---|---|
| `frontend/compare.html` | MODIFY — add dual-column layout markup |
| `frontend/js/compare.js` | NEW — comparison page logic |

### 7.2 compare.js responsibilities

On page load:
1. Read `p1` and `p2` from `URLSearchParams`
2. If either missing → show "Please select two players to compare" with link to `/`
3. If `p1 === p2` → show "Select two different players" (the API would 422 anyway)
4. Call `comparePlayer(p1, p2)` → render full comparison
5. If 404 → show which player was not found (from API `detail` field)
6. If 422 (same player) → show appropriate message

Rendering:

**Player headers:** Two columns side by side. Each shows name, club, competition,
position, age. Name links to `/player.html?id={id}`.

**data_warning banner:** Full-width yellow banner above verdict if
`response.data_warning` is not null. Text = exact string from API. Cross-position
comparisons show this in amber, not yellow, to reinforce the limitation.

**Verdict card:**
- Background: green if winner is clear + same_position; amber if cross-position
  or if WAS gap < 10; grey if draw
- Winner name (large, bold), or "Even Match" for draws
- "Weighted Advantage Score: {was_p1} vs {was_p2}"
- Summary text from `response.verdict.summary`
- Metrics won line: "{Name} leads on {N} of 4 scored metrics · {Name2} leads on {M} · {K} draws"

**Metric breakdown rows:**

One row per metric. Layout:

```
[Label]  [P1 value (pct)]  [Left bar ████░░] [░░████ Right bar]  [P2 value (pct)]
                              [← P1 wins +18.1 →]
```

- Left bar fills from centre-left outward based on player1 percentile / 100
- Right bar fills from centre-right outward based on player2 percentile / 100
- Centre label shows: "← {Winner} wins +{advantage}" or "Draw ({advantage})"
- `advantage` is always shown (even for draws), so "Draw (0.0)" vs "Draw (4.2)"
  lets users see closeness
- Bars use the same colour rules as profile: green ≥ 70, amber 40–69, red < 40
- `gc_p90` row has muted styling + "(display only)" label + ⓘ tooltip

**Strengths/weaknesses panel:**
Three sections: "{P1} only", "{P2} only", "Shared".
Chip badges with player-coloured borders.

**Swap button:** "↔ Swap players" → navigates to
`/compare.html?p1={current_p2}&p2={current_p1}`.

### 7.3 Phase 4 test strategy

- `/compare.html?p1={id1}&p2={id2}` with two valid same-position FW IDs:
  - Renders without data_warning
  - Verdict card is green or grey
  - All 5 metric rows render
  - gc_p90 row has "(display only)" label
  - Swap button reverses the order (reload page, both players visible)
- `/compare.html?p1={fw_id}&p2={mf_id}` (cross-position):
  - data_warning banner is visible
  - Verdict card is amber
  - Summary text starts with "This is a cross-position comparison"
- `/compare.html?p1={id}&p2={id}` (same player):
  - Shows error message; no API call needed (caught client-side)
- `/compare.html?p1=0&p2={id}` (invalid player):
  - Shows "Player not found: player1."
- Advantage field for draw metrics: shows actual value, not 0.0
- metrics_won display does not include gc_p90 in the count

### 7.4 Phase 4 risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Dual-bar layout is confusing when both bars are small | Medium | Medium | Add axis labels "0" at centre, "100" at edges |
| Verdict card colour (amber) for all cross-position comparisons feels alarming | Medium | Low | Add a label: "Cross-position · interpret with caution" |
| Shareable URL is order-dependent | Certain | Low | Swap button + always label bars by player name, not "player1"/"player2" |

---

## 8. Phase 5 — Integration QA

**Goal:** End-to-end testing of all three pages, all navigation flows,
all error states, and cross-browser validation.

**Estimated effort:** 1–2 days

### 8.1 Test checklist

**Navigation flows:**
- Leaderboard → click player name → Profile page loads
- Profile page → "Compare with..." → select player → Comparison page loads
- Comparison page → player header link → Profile page loads
- Comparison page → Swap → reversed comparison loads
- Any page → nav search → select player → Profile page loads
- Any page → nav search → no results → no crash, empty dropdown

**Error states:**
- Server down: all pages show a "Server unavailable" banner (health dot red)
- 404 on profile: "Player not found" shown, not blank page
- 404 on comparison: "Player not found: player1/2" shown
- 422 from comparison (same player caught client-side before API call)
- Leaderboard fetch failure: show "Could not load player data. Refresh to retry."
- Network timeout: retry button, not blank page

**Edge cases:**
- Player with accent in name (Mbappé) — renders correctly in all fields
- Player with `minutes_share > 1.0` — percentile bar capped at 100% visually
- GK vs GK comparison — data_warning shown, metric bars all render
- Player with 0 goals (all bars red for FW) — renders without JavaScript error
- Very long player name — truncated with ellipsis in table; full in profile

**Cross-browser (minimum):**
- Chrome (latest)
- Firefox (latest)
- Safari (latest, macOS)

**Responsive check (not full mobile redesign):**
- At 1024px width: all three pages readable
- At 768px width: acceptable (table may require horizontal scroll)
- At < 768px: not a requirement for MVP2-1

---

## 9. Files Summary

### New files

| File | Phase | Purpose |
|---|---|---|
| `backend/routers/leaderboard.py` | 0 | Leaderboard route |
| `backend/services/leaderboard_service.py` | 0 | Filter/sort/paginate logic |
| `backend/models/leaderboard_schemas.py` | 0 | Pydantic schemas |
| `frontend/index.html` | 1 | Leaderboard page |
| `frontend/player.html` | 1 | Profile page |
| `frontend/compare.html` | 1 | Comparison page |
| `frontend/css/app.css` | 1 | All styles |
| `frontend/js/api.js` | 1 | API client |
| `frontend/js/nav.js` | 1 | Navigation + search |
| `frontend/js/leaderboard.js` | 2 | Leaderboard logic |
| `frontend/js/player.js` | 3 | Profile logic |
| `frontend/js/compare.js` | 4 | Comparison logic |

### Modified files

| File | Phase | Change |
|---|---|---|
| `backend/main.py` | 0 | Add enriched_df to lifespan; mount leaderboard router; mount StaticFiles |
| `backend/dependencies.py` | 0 | Add `get_enriched_df` dependency |

### Unchanged

All analytics modules, existing routers, existing services, existing schemas,
dataset files.

### New tests

| File | Phase | Tests |
|---|---|---|
| `analytics/tests/test_leaderboard_service.py` | 0 | Filter, sort, pagination |

No automated frontend tests in MVP2-1. Manual testing per Phase 5 checklist.

---

## 10. Critical Review of This Implementation Plan

### 10.1 Architectural risks

**Risk: `app.state.enriched_df` doubles startup memory**
`_add_rate_cols` creates a copy of the DataFrame with 4 extra columns. At 2,800
rows this is negligible (< 1 MB). At 50,000 rows (future dataset) it would
still be ~15 MB — acceptable. Not a real risk at current scale.

**Risk: StaticFiles mount must come last**
`app.mount("/", StaticFiles(...))` must be the final line after all API routers.
If it is placed before any router, the static handler will intercept `/api/v1/...`
requests. This is a silent bug — the API returns 404 but no error is raised.
Must be enforced by code review: StaticFiles mount is always the last statement
in main.py.

**Risk: The leaderboard endpoint returns 500 players in one JSON response**
500 players × 16 fields each is ~120 KB of JSON uncompressed. With gzip
(FastAPI serves gzip if the client accepts it) this is ~15–20 KB. Not a concern.

**Risk: Client-side filter state lost on page navigation**
When a user filters to "FW only", clicks a player, then presses Back, the
leaderboard reloads with default filters (no state is preserved). This is a
UX friction point, not a data correctness issue. Acceptable for MVP2-1.

**Risk: The leaderboard endpoint is new but no pre-computed percentiles are
served — profile percentiles still require an individual API call.**
A user who wants to see top scorers can use the leaderboard. A user who wants
to see top scorers by percentile cannot, because the leaderboard doesn't include
percentiles. This is intentional (see §2.3 above) but means the leaderboard
table and the profile percentile bars are not directly comparable. Document
this explicitly in the UI: "Sort by Goals/90 rate — see individual player
profiles for percentile rankings."

### 10.2 Dataset limitations affecting this plan

**Single season:** The leaderboard will show "2025-26" as the only season.
The season filter chip would be useless. Remove it from the leaderboard filter bar.
Add it back only when a second season appears in the data.

**GK metrics absent:** The profile page for GKs shows four out of five percentile
bars in the red zone. This is visually alarming. The DF/GK disclaimer in Phase 3
mitigates this, but the root cause (no keeper stats) persists until the dataset
is extended.

**Non-penalty goals not surfaced:** `non_penalty_goals` is in the dataset and in
the leaderboard response schema, but no current profile endpoint or comparison
endpoint uses it. The leaderboard table does not sort by it. This is a gap in
the platform that the dashboard exposes without resolving. Acceptable for MVP2-1.

### 10.3 UX risks

**Risk: Leaderboard default shows all positions, which is misleading.**
The dashboard plan recommended defaulting to FW. This implementation plan
adopts that recommendation: the position filter defaults to "FW" on first
page load with a visible label "Showing Forwards · change position to see others."

**Risk: The comparison page amber verdict card may confuse users.**
A user comparing Mbappé (FW) vs Gomes (MF) sees an amber card saying Mbappé
wins. They may not understand why the card is amber (cross-position caveat)
rather than green. The data_warning banner above it carries the explanation.
Recommendation: add a small label under the verdict card title: "Cross-position
comparison — see note above." This redundancy is worth the UX clarity.

**Risk: "Load more" on the leaderboard is inconsistent with the scatter chart.**
The scatter chart shows up to 500 players (loaded all at once). The table
initially shows 50 with "Load more". If a user sees a player in the scatter
chart but can't find them in the table without clicking "Load more" several
times, they will be confused.

Mitigation: clicking a scatter chart point navigates directly to that player's
profile page, bypassing the table entirely. This removes the inconsistency
in practice — users who discover players in the scatter chart never need to
find them in the table.

### 10.4 Scalability concerns

**Dataset growth:** At 50,000 players, the "load all 500 into browser" strategy
breaks down. The leaderboard endpoint's pagination exists for this reason — the
frontend should be updated to use server-side pagination before the dataset
exceeds ~5,000 players.

**Concurrent leaderboard requests:** Each leaderboard request runs a pandas
filter + sort on the enriched DataFrame. Pandas is single-threaded and not
thread-safe for concurrent writes. Since the enriched_df is read-only after
startup, concurrent reads are safe. This is acceptable for MVP2-1 usage
(single analyst, not high concurrency).

**FastAPI StaticFiles for production:** FastAPI's built-in StaticFiles is not
optimised for production traffic (no CDN, no cache headers beyond default).
For MVP2-1 (single user / small team) this is fine. For production, serve
the frontend through a CDN or nginx.

---

## 11. Implementation Order — Ranked by ROI

| Rank | Phase | Deliverable | Why this order |
|---|---|---|---|
| 1 | Phase 0 | Leaderboard endpoint + enriched_df | Hard blocker; nothing else can be tested without this |
| 2 | Phase 1 | Frontend shell + nav search | All pages depend on nav and api.js; enables integration testing |
| 3 | Phase 3 | Player Profile page | Simplest page; uses existing profile endpoint with no new logic; confirms the rendering pipeline works before the complex pages |
| 4 | Phase 2 | Leaderboard page + scatter chart | Requires Phase 0 and Phase 1; the chart is the most complex frontend component |
| 5 | Phase 4 | Comparison page | Requires Phase 1; the dual-bar layout is the most complex layout component |
| 6 | Phase 5 | Integration QA | Requires all previous phases |

**Rationale for Profile before Leaderboard:**
The Profile page (Phase 3) uses only the existing `GET /api/v1/players/{id}`
endpoint which already works. Building it first confirms that the HTML/CSS/JS
pipeline (Phase 1 output) is correct before adding the new leaderboard endpoint
dependency. A working Profile page also provides immediate value to a user who
already knows the player IDs — they don't need to wait for the full leaderboard.

**Minimum viable demo after Phase 3:**
After completing Phases 0, 1, and 3 (in 3–4 days), a user can:
- Open the browser
- Type a player name in the nav search
- See a profile with percentile bars

That is already a significant improvement over the current CLI-only experience.
Phases 2 and 4 add discovery and comparison, but Phase 3 alone delivers the
core analytical value.

---

END OF DOCUMENT
