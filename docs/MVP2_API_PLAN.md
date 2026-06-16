# Football Intelligence — MVP2 Phase 1: FastAPI Backend Plan

Version: 0.2
Status: Design Review
Date: 2026-06-16

---

## 1. Scope

This document defines the design for the FastAPI backend that exposes the MVP1 analytics engine (player search + profile generation) as an HTTP API. No code changes to existing analytics modules. The backend becomes the interface that the Next.js frontend (and any future clients) consume.

---

## 2. Design Review: player_id

### 2.1 Why the original plan used DataFrame row index

The initial draft used the pandas row index as `player_id` because it requires no extra work: it is already available on every DataFrame row and maps directly to `df.iloc[id]` for fast lookup. No computation, no state.

### 2.2 Risks of using row index

**Silent wrong-player returns on data updates.**
If `cleaned_players.csv` is updated (new season added, rows reordered, a typo corrected), every index shifts. A client holding `player_id=142` gets back a different player with no error — no 404, no warning, just wrong data.

**CSV row order is fragile.**
The order depends entirely on how `prepare_data.py` writes the file. Any change to sort logic in that script silently renumbers every player across the entire dataset.

**Multi-season data compounds the problem.**
When a new season's rows are prepended or inserted, all downstream indices shift. Every client-stored ID becomes stale simultaneously.

**Duplicate players have no disambiguation.**
The current dataset contains "João Mário Lopes" twice — once for Bologna, once for Juventus. Both are legitimate entries with different row indices. A client storing index 1643 for Bologna cannot verify they haven't silently received the Juventus row after a data reload.

**No validation is possible.**
Index 142 is structurally indistinguishable from index 1642 to the client. There is no way for the client to detect that a stored ID has started pointing to the wrong player.

**No cross-system portability.**
The index has no meaning outside the current process. It cannot be linked to an external data source or a future PostgreSQL table.

### 2.3 Alternatives for MVP2 (no database)

**Option A — Deterministic hash ID (recommended)**

At load time, compute a stable integer from `hash(player_name + "|" + club + "|" + competition + "|" + season)` using a deterministic algorithm (e.g., CRC32 or MD5 truncated to 8 hex chars). Store this as a `_id` column. Build an `id → row` lookup dict at startup.

- Stable across server restarts as long as the source data does not change
- Same player in the same club, competition, and season always gets the same ID
- O(1) lookup via the dict — faster than `df.iloc[n]` for large datasets
- Migrates cleanly to PostgreSQL: the hash becomes a candidate key until replaced by a DB sequence
- One real risk: if source data is corrected (e.g., a name typo is fixed), that player's ID changes. Acceptable at this scale.

**Option B — Composite query params (stateless)**

No ID concept at all. The profile endpoint takes `name`, `club`, and `season` as query parameters. The search result already returns all three fields, so the client has everything needed for a second call.

```
GET /api/v1/players/profile?name=Kylian+Mbapp%C3%A9&club=Real+Madrid&season=2025-26
```

- Fully stateless — no client-side ID storage
- Survives data updates (the composite key is meaningful, not positional)
- Downside: verbose URLs, name must be URL-encoded including accents, harder to link or bookmark
- More friction to wire up on the frontend

**Option C — Name slug**

```
GET /api/v1/players/kylian-mbappe
```

- Human-readable and bookmarkable
- Breaks immediately on duplicate names (`joao-mario-lopes` is ambiguous)
- Requires a suffix to disambiguate: `joao-mario-lopes-bologna-2025-26` — which is just a slugified composite key with worse ergonomics

### 2.4 Decision

**Use Option A: deterministic hash ID.**

It is stable, requires no database, is O(1) to look up, and gives the frontend a single opaque integer to store and pass back. The hash function must be deterministic across Python processes — use `zlib.crc32()` or `hashlib.md5()`, not Python's built-in `hash()` (which is randomised per process since Python 3.3).

---

## 3. Folder Structure

```
backend/
├── main.py                  # FastAPI app instance, lifespan, router mounting
├── dependencies.py          # Shared FastAPI dependencies (get_df, get_id_map)
├── routers/
│   └── players.py           # All /players endpoints
├── models/
│   └── schemas.py           # Pydantic request/response models
└── services/
    └── player_service.py    # Business logic: bridges routers to analytics layer
```

| File | Role |
|---|---|
| `main.py` | Creates the `FastAPI` app, registers lifespan, mounts routers |
| `dependencies.py` | `get_df` and `get_id_map` dependencies injected into route handlers |
| `routers/players.py` | HTTP route definitions only — no logic |
| `models/schemas.py` | Pydantic models for all response shapes |
| `services/player_service.py` | Calls `search()`, `generate_profile()` from analytics; raises HTTP exceptions |

---

## 4. Dataset Lifecycle

The dataset is loaded once when the server starts using FastAPI's `lifespan` context manager. Two objects are stored on `app.state`:

- `app.state.df` — the full cleaned DataFrame
- `app.state.id_map` — a `dict[int, int]` mapping hash ID → DataFrame row position

Both are built from `load_players()` at startup. If the dataset file is missing, the server crashes intentionally — the API cannot function without data.

---

## 5. API Endpoints

### Minimum Viable Surface

The frontend's MVP1 user flow has two steps: search → view full profile. The frontend never needs stats or analysis separately — it always renders the complete profile page. Sub-endpoints like `/stats` and `/analysis` are premature decomposition with no current consumer. They are explicitly deferred to a future phase.

**Three endpoints. No more.**

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Server and dataset status |
| GET | `/api/v1/players?query=` | Search players by name |
| GET | `/api/v1/players/{id}` | Full player profile (identity + stats + analysis) |

---

### 5.1 Health Check

```
GET /health
```

Confirms the server is running and the dataset is loaded.

**Response 200:**
```json
{
  "status": "ok",
  "dataset_loaded": true,
  "player_count": 2476
}
```

---

### 5.2 Player Search

```
GET /api/v1/players?query={name}
```

Accent-insensitive, case-insensitive partial name search. Returns a list of matching players with their hash IDs. The client uses these IDs to request a profile.

**Query parameters:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `query` | string | Yes | Minimum 2 characters |

---

**Response 200 — results found:**

`query=mbappe`

```json
[
  {
    "id": 2847163924,
    "player_name": "Kylian Mbappé",
    "club": "Real Madrid",
    "competition": "La Liga",
    "nationality": "France",
    "position": "FW",
    "season": "2025-26"
  },
  {
    "id": 1093847265,
    "player_name": "Ethan Mbappé",
    "club": "Lille",
    "competition": "Ligue 1",
    "nationality": "France",
    "position": "FW",
    "season": "2025-26"
  }
]
```

---

**Response 200 — no results found:**

`query=zzznomatch`

```json
[]
```

A 200 with an empty array — not a 404. "No results" is a valid search outcome, not an error.

---

**Response 422 — query too short:**

`query=m`

```json
{
  "detail": "Query must be at least 2 characters."
}
```

---

**Response 422 — query param missing:**

`GET /api/v1/players` (no query param)

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["query", "query"],
      "msg": "Field required"
    }
  ]
}
```

FastAPI generates this automatically from the route signature.

---

### 5.3 Player Profile

```
GET /api/v1/players/{id}
```

Returns the complete player profile: identity fields, season statistics, and rule-based AI analysis. This is everything the frontend profile page needs in a single call.

**Path parameters:**

| Name | Type | Description |
|---|---|---|
| `id` | integer | Hash ID returned by the search endpoint |

---

**Response 200:**

`GET /api/v1/players/2847163924`

```json
{
  "id": 2847163924,
  "player_name": "Kylian Mbappé",
  "season": "2025-26",
  "club": "Real Madrid",
  "competition": "La Liga",
  "nationality": "France",
  "position": "FW",
  "age": 26,
  "overview": "Exceptional striker with elite goal production, among the most clinical finishers in the league.",
  "strengths": [
    "Elite goal scoring",
    "Penalty conversion",
    "Availability"
  ],
  "weaknesses": [
    "Defensive contribution"
  ],
  "stats": {
    "appearances": 31,
    "minutes_played": 2599,
    "goals": 25,
    "assists": 5,
    "non_penalty_goals": 17,
    "goal_contributions": 30,
    "goals_per_90": 0.87,
    "assists_per_90": 0.17,
    "goal_contributions_per_90": 1.04
  },
  "peer_group_size": 415
}
```

---

**Response 404 — ID not found:**

`GET /api/v1/players/9999999999`

```json
{
  "detail": "Player not found."
}
```

---

## 6. Pydantic Schemas

```python
# backend/models/schemas.py (sketch)

from pydantic import BaseModel

class PlayerSearchResult(BaseModel):
    id: int
    player_name: str
    club: str
    competition: str
    nationality: str
    position: str
    season: str

class StatsResponse(BaseModel):
    appearances: int
    minutes_played: int
    goals: int
    assists: int
    non_penalty_goals: int
    goal_contributions: int
    goals_per_90: float
    assists_per_90: float
    goal_contributions_per_90: float

class PlayerProfileResponse(BaseModel):
    id: int
    player_name: str
    season: str
    club: str
    competition: str
    nationality: str
    position: str
    age: int
    overview: str
    strengths: list[str]
    weaknesses: list[str]
    stats: StatsResponse
    peer_group_size: int

class HealthResponse(BaseModel):
    status: str
    dataset_loaded: bool
    player_count: int
```

`AnalysisResponse` and the `/stats`, `/analysis` sub-endpoint schemas are removed. They were unused abstractions.

---

## 7. Service Layer

`player_service.py` is the only file that imports from `analytics/`. Route handlers never import analytics modules directly.

```python
# backend/services/player_service.py (sketch)

from fastapi import HTTPException
import pandas as pd
from analytics.player_search import search
from analytics.profile_generator import generate_profile

def search_players(df: pd.DataFrame, id_map: dict, query: str) -> list[dict]:
    results = search(df, query)
    return [
        {"id": id_map[int(idx)], **row[SEARCH_FIELDS].to_dict()}
        for idx, row in results.iterrows()
    ]

def get_profile(df: pd.DataFrame, id_map: dict, player_id: int):
    row_pos = id_map.get(player_id)
    if row_pos is None:
        raise HTTPException(status_code=404, detail="Player not found.")
    row = df.iloc[row_pos]
    return generate_profile(row, df)
```

---

## 8. Error Handling Strategy

| Scenario | HTTP Status | Source |
|---|---|---|
| Player ID not in `id_map` | 404 | `player_service.py` raises `HTTPException` |
| Query shorter than 2 chars | 422 | Route handler raises `HTTPException` |
| Missing required query param | 422 | FastAPI automatic validation |
| Dataset missing at startup | Server crash | `load_players()` raises `FileNotFoundError` — intentional |
| Unhandled exception | 500 | Global handler in `main.py` |

A global `500` handler is registered in `main.py` to prevent raw tracebacks from reaching clients. All other error shapes follow the `{"detail": "..."}` convention that FastAPI uses natively.

---

## 9. How app.py Is Exposed Through FastAPI

`analytics/app.py` is the CLI entry point. It is not called by FastAPI and must not be modified.

| CLI concern (app.py) | FastAPI treatment |
|---|---|
| `load_players()` | Called once in `lifespan`; stored as `app.state.df` |
| `search(df, query)` | Called by `player_service.search_players()` |
| `generate_profile(row, df)` | Called by `player_service.get_profile()` |
| `print_profile(profile)` | Not used — profile is serialised from the `PlayerProfile` dataclass |
| `_pick_player()` | Not used — search returns all matches; the client selects |
| `run(query)` | Not used — has print statements and interactive prompts |

The `PlayerProfile` dataclass fields map 1:1 to `PlayerProfileResponse`. Conversion is a direct field assignment with no transformation.

---

## 10. Dependencies

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `pydantic` | Included with FastAPI; response schema validation |

No changes to existing analytics dependencies.

---

## 11. Out of Scope for Phase 1

- Database (PostgreSQL) — players served from in-memory CSV with hash IDs
- Authentication / API keys
- CORS configuration — added when the Next.js frontend is wired up
- Rate limiting
- `/stats` and `/analysis` sub-endpoints — deferred until a use case requires them separately
- External AI API calls — profile generation remains rule-based

---

## 12. Reserved Endpoints (future phases)

These paths are reserved and must not be used for other purposes:

```
GET  /api/v1/compare?player1={id}&player2={id}   — MVP2: Player Comparison Engine
POST /api/v1/scout                                — MVP3: AI Scout
GET  /api/v1/prospects                            — MVP3: Prospect List
POST /api/v1/recruitment                          — MVP4: Recruitment Engine
```

---

END OF DOCUMENT
