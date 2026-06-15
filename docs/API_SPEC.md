# Football Intelligence — API Specification
# Football Intelligence API Specification

Version: v0.1

Status: MVP 1

---

# 1. Purpose

This document defines the API endpoints for Football Intelligence.

Current Scope:

MVP 1 — AI Player Profile Generator

---

# 2. Base URL

Future:

/api/v1

---

# 3. Health Check

Endpoint

GET /health

Purpose

Verify API availability.

Response

```json
{
  "status": "ok"
}
```

---

# 4. Player Search

Endpoint

GET /players

Purpose

Search players by name.

Example

GET /players?query=messi

Response

```json
[
  {
    "id": 1,
    "name": "Lionel Messi"
  }
]
```

---

# 5. Player Profile

Endpoint

GET /players/{player_id}

Purpose

Retrieve player profile.

Response

```json
{
  "id": 1,
  "name": "Lionel Messi",
  "age": 38,
  "nationality": "Argentina",
  "club": "Inter Miami",
  "position": "RW",
  "preferred_foot": "Left"
}
```

---

# 6. Season Statistics

Endpoint

GET /players/{player_id}/stats

Purpose

Retrieve season statistics.

Response

```json
{
  "appearances": 32,
  "goals": 21,
  "assists": 14,
  "xg": 18.5,
  "xa": 11.3,
  "pass_completion": 87.2
}
```

---

# 7. AI Analysis

Endpoint

GET /players/{player_id}/analysis

Purpose

Generate AI player analysis.

Response

```json
{
  "strengths": [
    "Chance creation",
    "Ball progression"
  ],
  "weaknesses": [
    "Defensive intensity"
  ],
  "playing_style": "Creative playmaker",
  "similar_players": [
    "Kevin De Bruyne",
    "Bruno Fernandes"
  ]
}
```

---

# 8. MVP 2 Future APIs

Reserved

GET /compare

GET /compare/{player1}/{player2}

---

# 9. MVP 3 Future APIs

Reserved

POST /scout

GET /prospects

---

# 10. MVP 4 Future APIs

Reserved

POST /recruitment

GET /recruitment/recommendations

---

# 11. API Design Principles

Principle 1

RESTful Design

Principle 2

Predictable Naming

Principle 3

Versioned APIs

Principle 4

JSON Responses

Principle 5

Scalable Endpoint Structure

---

END OF DOCUMENT