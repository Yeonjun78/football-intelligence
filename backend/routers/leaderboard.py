from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_df, get_id_map
from backend.models.leaderboard_schemas import LeaderboardResponse
from backend.services.leaderboard_service import get_leaderboard

router = APIRouter()


@router.get("/leaderboard", response_model=LeaderboardResponse)
def leaderboard(
    position: str | None = Query(None, description="Filter by position: FW, MF, DF, GK"),
    competition: str | None = Query(None, description="Filter by competition (case-insensitive)"),
    min_appearances: int = Query(0, ge=0, description="Minimum appearances"),
    sort_by: str = Query("goals_p90", description="Column to sort by"),
    sort_order: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, description="Results to return (1–500)"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    df: pd.DataFrame = Depends(get_df),
    id_map: dict = Depends(get_id_map),
) -> LeaderboardResponse:
    return get_leaderboard(
        df,
        id_map,
        position=position,
        competition=competition,
        min_appearances=min_appearances,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset,
    )
