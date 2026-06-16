from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    dataset_loaded: bool
    player_count: int


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
