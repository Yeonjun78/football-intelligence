from __future__ import annotations
from pydantic import BaseModel


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
    advantage: float # always actual abs percentile diff; not zeroed for draws


class StrengthWeaknessBreakdown(BaseModel):
    player1_only: list[str]
    player2_only: list[str]
    shared: list[str]


class ComparisonVerdict(BaseModel):
    winner: str
    metrics_won: dict[str, int]        # scored metrics only; informational
    advantage_score: dict[str, float]  # WAS — sole winner-determination signal
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
