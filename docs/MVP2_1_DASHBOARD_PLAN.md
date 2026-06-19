# Football Intelligence — MVP2-1 Analytics Dashboard Plan

Version: 1.0
Status: Design Review
Date: 2026-06-19

---

## 1. Scope and Objectives

MVP2-1 adds a browser-based Analytics Dashboard that exposes the Football
Intelligence platform to non-technical users. The dashboard is a pure frontend
layer — it consumes the existing FastAPI backend and introduces no new backend
endpoints, no new data, and no new analytics logic.

**Objectives:**
- Allow scouts and analysts to browse players without using curl or the CLI
- Surface percentile rankings and comparison verdicts visually
- Enable position-based and competition-based filtering with no code
- Deliver immediate value from the current dataset without waiting for richer data

**Explicit non-objectives for MVP2-1:**
- No new backend endpoints
- No user accounts, authentication, or saved sessions
- No xG, xA, defensive, or event-level data (not in current dataset)
- No real-time data or live match integration
- No mobile-native layout (responsive web only, desktop-first)

---

## 2. Available Data — What the Dashboard Can Show

Every chart, table, and filter in this document is derived exclusively from
the 12 raw columns and 4 computed columns already served by the API.

**Raw columns (from dataset):**
| Column | Type | Notes |
|---|---|---|
| player_name | string | Display name |
| season | string | Single season currently |
| nationality | string | Country of player |
| position | string | FW, MF, DF, GK |
| club | string | Current club |
| competition | string | League name |
| age | integer | Age at time of dataset |
| appearances | integer | Total appearances |
| minutes_played | integer | Total minutes |
| goals | integer | Total goals |
| assists | integer | Total assists |
| non_penalty_goals | integer | Goals excl. penalties |

**Computed columns (from _add_rate_cols):**
| Column | Formula | Notes |
|---|---|---|
| goals_p90 | goals / (minutes_played / 90) | Clipped at 1 min |
| assists_p90 | assists / (minutes_played / 90) | |
| gc_p90 | goals_p90 + assists_p90 | Display only; not scored |
| minutes_share | minutes_played / (appearances × 90) | Availability ratio |

**Percentile ranks** (from profile_generator, position peer group):
Available for goals_p90, assists_p90, gc_p90, appearances, minutes_share.

**What cannot be shown:**
- Dribbles, tackles, interceptions, key passes, xG, xA
- Match-by-match form, injury history, contract data
- Transfer fees or market value
- Head-to-head match results

---

## 3. API Surface Available to the Dashboard

All data comes from three existing endpoints. No new endpoints needed for MVP2-1.

| Endpoint | Used for |
|---|---|
| GET /api/v1/players?query= | Search autocomplete, player lookup |
| GET /api/v1/players/{id} | Player profile card, percentile bars |
| GET /api/v1/compare?player1=&player2= | Comparison page full response |
| GET /health | Server status indicator |

---

## 4. Dashboard Pages

### 4.1 Page Map

```
/ (Home / Search)
├── /players/{id}           Player Profile
└── /compare?p1=&p2=        Head-to-Head Comparison

Persistent: top navigation bar, search input
```

Three pages total. No routing library complexity needed for MVP2-1.

---

### 4.2 Page 1 — Home / Leaderboard

**Purpose:** Entry point. Shows the dataset at a glance. Lets users discover
players by position, competition, or raw output rather than by name.

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  Football Intelligence                       [Search...] │
├─────────────────────────────────────────────────────────┤
│  LEADERBOARD                                            │
│                                                         │
│  Filters: [Position ▾] [Competition ▾] [Min Apps ▾]   │
│                                                         │
│  Sort by: [Goals/90 ▾]                                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │ # Player         Club      Pos  G/90  A/90  Gls │   │
│  │ 1 K. Mbappé      Real      FW   0.87  0.17  32  │   │
│  │ 2 H. Kane        Bayern    FW   0.81  0.24  28  │   │
│  │ ...                                              │   │
│  └─────────────────────────────────────────────────┘   │
│  Showing 25 of 2,847 players    [Load more]            │
└─────────────────────────────────────────────────────────┘
```

**Components:**

**Filter bar (all client-side after initial load):**
- Position: All / FW / MF / DF / GK (radio chips)
- Competition: multi-select dropdown, populated from dataset
- Min Appearances: slider 0–38, default 5 (matches sample-size rule)
- Min Minutes: hidden by default; shown with an "Advanced" toggle

**Sortable leaderboard table:**

| Column | Visible by default | Sortable |
|---|---|---|
| Rank | Yes | No |
| Player name (link → profile) | Yes | No |
| Club | Yes | No |
| Position | Yes | Yes |
| Goals/90 | Yes | Yes |
| Assists/90 | Yes | Yes |
| Goals (raw) | Yes | Yes |
| Appearances | Yes | Yes |
| Minutes played | No | Yes |
| Minutes share | No | Yes |
| GC/90 | No | Yes |

Clicking a player name navigates to /players/{id}.

**Scatter chart — Goals/90 vs Assists/90 (position-coloured):**

```
Assists/90
   │              ● (FW)
   │         ●       ●
   │    ■ (MF)  ●
   │  ■    ■
   │ ▲ (DF)
   └──────────────────── Goals/90
```

- One dot per player (filtered to current filter selection)
- Coloured by position (FW=blue, MF=green, DF=amber, GK=red)
- Hover: tooltip showing player name, club, values
- Click: navigate to that player's profile page
- X axis: Goals/90 (capped display at 1.5 for visual clarity; outliers noted)
- Y axis: Assists/90

This chart immediately shows the position separation and helps scouts identify
creative forwards vs. goal-only forwards vs. creative midfielders.

**Data source:** Initial load fetches all players via repeated search calls OR
a single GET /api/v1/players?query= with a broad query. See §8 (Architecture
Risks) for limitations of this approach.

---

### 4.3 Page 2 — Player Profile

**URL:** /players/{player_id}

**Purpose:** Deep-dive on one player. Shows computed percentile rankings
alongside raw stats. Enables one-click comparison initiation.

**Layout:**

```
┌────────────────────────────────────────────────────────┐
│  ← Back to Leaderboard                                 │
├────────────────────────────────────────────────────────┤
│  Kylian Mbappé                                         │
│  Real Madrid · La Liga · FW · Age 26 · 2025-26         │
│                                                        │
│  [Compare with another player ▾]                       │
├────────────────────────────────────────────────────────┤
│  STATS OVERVIEW          │  PERCENTILE RANKS (vs FWs)  │
│                          │                              │
│  Goals         32        │  Goals/90      ████████░ 92 │
│  Assists        6        │  Assists/90    █████░░░░ 62  │
│  Appearances   31        │  Appearances   ███████░░ 72  │
│  Minutes     2,790       │  Minutes share ███████░░ 68  │
│  Goals/90    0.87        │  GC/90         ████████░ 91  │
│  Assists/90  0.17        │                              │
│  GC/90       1.04        │                              │
├────────────────────────────────────────────────────────┤
│  STRENGTHS                    WEAKNESSES               │
│  ● Elite goal scoring         ● Limited creativity     │
│  ● Penalty conversion                                  │
├────────────────────────────────────────────────────────┤
│  PEER GROUP: 415 forwards in dataset                   │
└────────────────────────────────────────────────────────┘
```

**Components:**

**Header card:**
- Player name, club, competition, position, age, season
- "Compare with another player" — opens a search dropdown; selecting a second
  player navigates to /compare?p1={id}&p2={chosen_id}

**Stats overview (left column):**
Raw numbers from the profile response:
goals, assists, appearances, minutes_played, goals_p90, assists_p90, gc_p90

**Percentile bars (right column):**
One horizontal bar per metric. Bar width = percentile value (0–100).
Colour: green ≥ 70, amber 40–69, red < 40.
Label shows the numeric percentile ("92nd").

Metrics shown: goals_p90, assists_p90, appearances, minutes_share, gc_p90
(note: gc_p90 displayed as informational; labelled "Goal Contributions/90")

**Strengths / Weaknesses chips:**
Lists from profile response. Displayed as pill badges. Strengths = green,
weaknesses = amber/red. No labels explaining why — the percentile bars
already communicate the reasoning.

**Peer group footnote:**
"Percentiles ranked among {N} {position} players in the dataset."
Prevents users from thinking 92nd percentile means 92nd in the world.

**data_warning banner (if present):**
Yellow banner below header if the player has < 5 appearances or < 270 minutes.
Text: the data_warning string from the API response.

---

### 4.4 Page 3 — Head-to-Head Comparison

**URL:** /compare?p1={id}&p2={id}

**Purpose:** Side-by-side comparison of two players. Directly renders the
/api/v1/compare response.

**Entry points:**
- From Profile page: "Compare with..." dropdown
- From Leaderboard: checkbox select two players → "Compare" button
- Direct URL (shareable link)

**Layout:**

```
┌────────────────────────────────────────────────────────────┐
│  HEAD-TO-HEAD COMPARISON                                   │
├──────────────────────┬─────────────────────────────────────┤
│  Kylian Mbappé       │  Mohamed Salah                      │
│  Real Madrid · FW    │  Liverpool · FW                     │
├──────────────────────┼─────────────────────────────────────┤
│  [data_warning banner — full width, if present]            │
├────────────────────────────────────────────────────────────┤
│  VERDICT                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Winner: Kylian Mbappé                                │  │
│  │ Weighted Advantage Score: 28.3 vs 12.1               │  │
│  │ "Mbappé holds a clear advantage..."                  │  │
│  │ Metrics won: Mbappé 2 · Salah 1 · Draw 1            │  │
│  └──────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────┤
│  METRIC BREAKDOWN                                          │
│                                                            │
│  Goals/90        Mbappé 0.87 (92) ████████░ ░██████ 0.54  │
│                                    ◄ Mbappé wins +18.1 ►   │
│                                                            │
│  Assists/90      Mbappé 0.17 (62) █████░░░░ ░█████░ 0.19  │
│                                    ◄ Draw (0.0) ►          │
│                                                            │
│  GC/90 ⓘ        Mbappé 1.04 (92) ████████░ ░██████ 0.73  │
│  [display only]                   ◄ Mbappé wins +14.2 ►   │
│                                                            │
│  Appearances     Mbappé 31 (72)   ███████░░ ░█████░ 28    │
│                                    ◄ Draw (2.8) ►          │
│                                                            │
│  Minutes Share   Mbappé 0.93 (68) ███████░░ ░███░░░ 0.82  │
│                                    ◄ Salah wins +8.3 ►     │
├────────────────────────────────────────────────────────────┤
│  STRENGTHS & WEAKNESSES                                    │
│  Mbappé only:  Elite goal scoring · Penalty conversion     │
│  Salah only:   Consistency                                 │
│  Shared:       Availability                                │
└────────────────────────────────────────────────────────────┘
```

**Components:**

**Player headers:**
Each side shows: name, club, competition, position, age.
Links back to individual profile pages.

**data_warning banner:**
Full-width yellow banner above the verdict if `data_warning` is non-null.
This covers: small sample, cross-position, GK warnings.
Text is the exact string from the API. Not summarised.

**Verdict card:**
- Winner name (or "Draw") in large type
- Advantage score: "Weighted Advantage Score: {p1} vs {p2}"
- Summary text (from API verdict.summary)
- Metrics won display: "X leads on N of 4 scored metrics"
- For draws: "Evenly matched on all 4 scored metrics"

For cross-position comparisons, the verdict card colour is amber (not green)
to visually reinforce the limitation surfaced in data_warning.

**Metric breakdown rows:**

Each metric row shows:
- Metric label
- Player 1 value + percentile on the left
- Dual opposing bars (player1 fills left, player2 fills right)
- Player 2 value + percentile on the right
- Win/draw label centred below the bars: "← Player1 wins +{advantage}" or "Draw ({advantage})"

`gc_p90` row includes a ⓘ tooltip: "Goal contributions per 90 is not scored in
the verdict — it equals Goals/90 + Assists/90 and would count those metrics twice."

The `advantage` field from the API is shown even for draws, so users can see
"Draw (0.0)" vs "Draw (4.2)" and understand how close the draw was.

**Strengths and weaknesses:**
Three groups as returned by the API: player1_only, player2_only, shared.
Displayed as labelled chip lists. Structural labels ("Defensive contribution")
are already filtered server-side and do not appear here.

**Swap button:**
"↔ Swap players" — reloads with p1 and p2 reversed. Useful because the
comparison response is order-dependent (noted as known limitation in the plan).

---

## 5. Navigation Structure

```
Top nav (persistent across all pages):
┌────────────────────────────────────────────────────────┐
│ ⚽ Football Intelligence    [Search player name...]  ●  │
└────────────────────────────────────────────────────────┘

● = server health indicator (green/red dot, polls /health every 60s)
Search = live autocomplete using GET /api/v1/players?query=
         shows top 5 results as a dropdown
         Enter or click → navigates to that player's profile
```

Navigation flows:

```
Leaderboard
  │
  ├── Click player name ──────────────→ Profile page
  │
  └── Check two rows → Compare ──────→ Comparison page

Profile page
  │
  └── "Compare with..." dropdown ─────→ Comparison page (this player as p1)

Comparison page
  │
  ├── Player 1 header link ───────────→ Player 1 profile
  ├── Player 2 header link ───────────→ Player 2 profile
  └── ↔ Swap ────────────────────────→ Comparison page (p1/p2 swapped)

Any page
  └── Search autocomplete ────────────→ Profile page
```

---

## 6. Filters Reference

All filters on the Leaderboard are client-side after initial data load.
No filter change triggers a new API call.

| Filter | Type | Values | Default |
|---|---|---|---|
| Position | Multi-chip | All, FW, MF, DF, GK | All |
| Competition | Multi-select dropdown | All distinct values in dataset | All |
| Nationality | Multi-select dropdown | All distinct values | All |
| Min Appearances | Slider | 0–38 | 5 |
| Sort column | Column header click | Any numeric column | Goals/90 |
| Sort direction | Second click on header | Asc / Desc | Desc |

**Min Appearances default = 5** aligns with the comparison engine's sample-size
rule and prevents inflated per-90 statistics from dominating the leaderboard.
A tooltip on the slider explains: "Players with fewer than 5 appearances may
have unreliable per-90 statistics."

---

## 7. Must Have vs Nice to Have

### 7.1 Must Have (MVP2-1)

| Feature | Reason |
|---|---|
| Leaderboard table with sort and position filter | Core discovery flow |
| Scatter chart (Goals/90 vs Assists/90) | Only chart possible without event data |
| Player profile page with percentile bars | Direct value from existing profile API |
| Head-to-head comparison page | Direct value from existing comparison API |
| Comparison metric breakdown with dual bars | Main visual of the comparison engine |
| Verdict card with WAS and summary | Surfaces the core analytical result |
| data_warning banner on comparison page | Required to avoid misleading users |
| Search autocomplete in top nav | Primary navigation mechanism |
| Min Appearances filter (default 5) | Prevents inflated small-sample leaderboard |
| Peer group footnote on percentile bars | Prevents misinterpretation |

### 7.2 Nice to Have (Future MVPs)

| Feature | Blocker | When |
|---|---|---|
| Position-normalized scatter (radar chart) | Only 2 meaningful FW metrics now | After dataset expansion |
| Player form / trend line | No match-by-match data | After event dataset |
| Club leaderboard (avg goals/90 by club) | Possible now but low value | MVP2-2 |
| Season-over-season comparison | Dataset may have one season only | After multi-season data |
| Export to CSV / PDF | Low priority for MVP | MVP3 |
| Saved comparisons / watchlist | Requires user accounts | MVP3+ |
| Mobile-optimised comparison layout | Complex dual-column at small screen | MVP2-2 |
| Nationality flag icons | Asset management overhead | MVP2-2 |
| GK-specific metric display | No GK metrics in dataset | After data expansion |
| Radar/spider chart | Needs ≥ 5 independent metrics | After data expansion |
| Dark mode | Cosmetic | MVP2-2 |

---

## 8. Critical Review — Risks and Mitigations

### 8.1 Architectural Risks

**Risk A — No bulk player endpoint**
The dashboard Leaderboard needs all players to populate the table and scatter
chart. The existing API only offers `GET /api/v1/players?query=` (search) and
`GET /api/v1/players/{id}` (single profile). There is no `GET /api/v1/players`
endpoint that returns the full dataset.

**Impact:** The Leaderboard cannot be built without either:
(a) Adding a new `GET /api/v1/players/all` or `GET /api/v1/leaderboard` endpoint
(b) Making N individual profile calls (N = dataset size, ~2,800+ players)
(c) A client-side dataset bundle (a pre-exported JSON file served as a static asset)

Option (b) is unusable. Option (c) couples the frontend to manual dataset exports.
Option (a) is the right fix but requires a new backend endpoint — a stated non-objective.

**This is the highest-priority architectural risk. The Leaderboard page as designed
cannot be implemented without resolving it.**

Recommended mitigation: Add a single lightweight endpoint before dashboard
implementation begins:
```
GET /api/v1/leaderboard?position=FW&competition=La+Liga&min_appearances=5
```
Returns a flat list of players with pre-computed rate columns (no percentile
computation needed — that only happens per-player in the profile). This is
a read-only, O(n) pandas filter over the already-loaded DataFrame.

**Risk B — No pagination on search**
`GET /api/v1/players?query=` returns all matches for the query. For a broad query
(e.g. "a") this could return thousands of rows. The autocomplete dropdown will
work, but the scatter chart data loading strategy needs to account for this.

Recommended mitigation: Add `limit` and `offset` params to the search endpoint,
or cap the leaderboard endpoint at 500 rows with filter enforcement.

**Risk C — Order-dependent comparison response**
`/compare?player1=A&player2=B` and `?player1=B&player2=A` return mirror-image
responses. Shareable URLs are position-dependent. Two users sharing a "compare"
link may see different verdict labels ("player1 wins" vs "player2 wins").

Recommended mitigation: The "Swap" button on the comparison page plus labelling
both sides clearly by name (not "player1"/"player2") largely defuses this.
A canonical URL (always put lower ID first) could be added but is not required.

**Risk D — `same_position: false` UX handling**
The API returns a verdict for cross-position comparisons with a `data_warning`.
The dashboard must not display a green "winner" card for a cross-position
comparison without prominently showing the limitation. If the data_warning
banner is visually subtle, users will read the verdict and ignore the caveat.

Recommended mitigation: Cross-position comparisons render the verdict card in
amber, with data_warning displayed above the verdict (not below it).

---

### 8.2 Dataset Limitations

**Limitation 1 — No defensive metrics for DF/GK**
The dashboard cannot show any meaningful percentile bars for defenders or
goalkeepers beyond appearances and minutes_share. A DF's profile page will
show all five metric bars but four of them are structurally unfavourable.

**Impact on UX:** A user viewing a top defender's profile will see "22nd
percentile goals/90" and think they are viewing a bad player. The peer group
footnote ("Percentiles among 893 defenders") helps but may not be enough.

Recommended mitigation: On profile pages for DF and GK, add a persistent
note: "Defensive metrics (tackles, interceptions, clearances) are not available
in the current dataset. Percentile bars reflect attacking output only."

**Limitation 2 — Single season**
If the dataset contains only one season, "season" is not a useful filter and
can be removed from the filter bar entirely. Displaying it wastes space.

Verify the number of distinct seasons in the dataset before building the filter.

**Limitation 3 — Non-penalty goals available but not surfaced**
`non_penalty_goals` is in the dataset but not used by any API endpoint. The
profile generator uses `goals` for `goals_p90`, which inflates penalty takers.
The dashboard plan does not expose this gap — it just inherits it from the API.

This is a data quality note, not a dashboard-level fix. Flagged for the next
backend iteration.

**Limitation 4 — minutes_share can exceed 1.0**
Players with extra-time minutes may show `minutes_share > 1.0`. The percentile
bar display should cap the visual bar at 100% even if the underlying value
exceeds it, while showing the raw value in the tooltip.

---

### 8.3 UX Risks

**UX Risk 1 — Percentile bars without context mislead casual users**
A user who doesn't understand percentile ranking will read "92nd percentile
goals/90" and think the player scores 92 goals per 90 minutes. Labels must
say "92nd percentile among FW" not just "92".

Recommended mitigation: Show "vs {N} FW" below the bar chart heading.
Add a one-line tooltip on the bars: "This player scores more than 92% of
forwards in the dataset."

**UX Risk 2 — Leaderboard default shows all positions together**
Goals/90 for FW and DF are not comparable. A leaderboard sorted by Goals/90
with all positions mixed will show all FWs at the top and all DFs at the
bottom — suggesting defenders are bad, not that they play a different role.

Recommended mitigation: Default the position filter to "FW" on first load,
with a visible banner: "Showing Forwards. Change position filter to see others."

**UX Risk 3 — Comparison page with no data_warning feels like a full endorsement**
When `data_warning` is null (same-position, both above sample threshold),
users should understand the comparison is still limited to 4 metrics.
Without a disclaimer, a "clear winner" verdict reads as a comprehensive
scouting assessment.

Recommended mitigation: A persistent small footnote on every comparison page:
"Comparison based on goals, assists, appearances, and minutes share only."
This is not a warning banner — just a scope disclosure.

**UX Risk 4 — Scatter chart with 2,800+ dots is unreadable**
Rendering all players simultaneously as a scatter chart will produce an
overplotted blob. With the default filter (Min Appearances = 5, All positions),
the chart will have too many points to read.

Recommended mitigation:
- Default to position filter = FW (500–600 players, still readable)
- Use opacity 0.5 on dots to show density
- Add a "Max 500 players displayed" notice when the filter returns more

**UX Risk 5 — Search autocomplete latency**
The search endpoint makes a full pandas DataFrame scan on every keystroke.
With 300ms network latency + scan time, the autocomplete will lag on fast
typists or slow connections.

Recommended mitigation: Debounce the autocomplete input at 250ms before
firing the API call. Minimum 2-character query (already enforced server-side).

---

### 8.4 Scalability Concerns

**Concern 1 — Client-side filtering requires full dataset in browser memory**
The Leaderboard filter approach (one load, client-side filtering) requires
loading all players into the browser. At ~2,800 players × 12 columns, this is
roughly 1–2 MB of JSON — acceptable for modern browsers but not for mobile
or slow connections.

**Concern 2 — Comparison page is not cacheable**
The comparison response is order-dependent (player1/player2 asymmetry) and
the API has no ETag or cache headers. Every page load re-runs the full
comparison computation including `_add_rate_cols` on the full DataFrame.
At 2,800 players this is fast, but would scale poorly at 50,000+.

This is a known limitation from the comparison plan. Acceptable at MVP scale.

**Concern 3 — No backend for the leaderboard**
Repeated scatter chart re-renders on every filter change will re-process the
same ~2,800-player JSON client-side. With complex position+competition+appearances
filters this is O(n) in JavaScript — fine now but noted.

---

### 8.5 Recommended Pre-Implementation Actions (Priority Order)

| Priority | Action | Reason |
|---|---|---|
| P0 | Add GET /api/v1/leaderboard endpoint (backend) | Leaderboard page is impossible without it |
| P1 | Verify dataset season count | Determines if season filter is needed |
| P1 | Add limit param to /players search | Prevents autocomplete returning 2,000 results |
| P2 | Add DF/GK disclaimer text to profile page design | Prevents misleading defensive player profiles |
| P2 | Confirm positions available in dataset | Ensures filter chips are accurate |
| P3 | Decide canonical URL strategy for comparison | Affects shareability |

---

## 9. Tech Stack Recommendation (Frontend Only)

No new backend code beyond the leaderboard endpoint. Frontend choices are
outside the scope of the Football Intelligence Python stack, but constraints
for MVP2-1 are:

- Must consume the existing FastAPI JSON API
- No server-side rendering required (purely static frontend served separately)
- Must be deliverable without a build pipeline if needed (i.e., vanilla JS/HTML
  is acceptable for MVP2-1 speed; a React/Vue app is acceptable for quality)

**Recommended for MVP2-1 speed:** Plain HTML + vanilla JS + a charting library
(Chart.js or Plotly.js). Zero build tooling. Served as static files.

**Acceptable alternative:** React + recharts. More maintainable long-term but
adds build pipeline complexity.

The choice does not affect the API design or analytics modules.

---

## 10. Out of Scope for MVP2-1

- User authentication or saved state
- Admin panel or data upload UI
- Email alerts or notifications
- PDF/CSV export
- Embedded iframes or widgets
- Radar/spider chart (insufficient independent metrics)
- Mobile-first layout (desktop-first only)
- i18n / localisation
- A/B testing or analytics instrumentation
- Any new backend analytics logic

---

END OF DOCUMENT
