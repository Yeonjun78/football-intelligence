from __future__ import annotations
from pydantic import BaseModel


class LeaderboardPlayer(BaseModel):
    id: int
    player_name: str
    club: str
    competition: str
    nationality: str
    position: str
    age: int
    season: str
    appearances: int
    minutes_played: int
    goals: int
    assists: int
    non_penalty_goals: int
    goals_p90: float
    assists_p90: float
    gc_p90: float
    minutes_share: float


class FiltersApplied(BaseModel):
    position: str | None
    competition: str | None
    min_appearances: int


class LeaderboardResponse(BaseModel):
    total: int
    limit: int
    offset: int
    sort_by: str
    sort_order: str
    filters_applied: FiltersApplied
    players: list[LeaderboardPlayer]
