import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.dependencies import get_df, get_id_map
from backend.models.schemas import PlayerProfileResponse, PlayerSearchResult
from backend.services.player_service import get_player_profile, search_players

router = APIRouter()


@router.get("/players", response_model=list[PlayerSearchResult])
def search(
    query: str = Query(..., description="Player name (min 2 chars)"),
    df: pd.DataFrame = Depends(get_df),
):
    if len(query.strip()) < 2:
        raise HTTPException(status_code=422, detail="Query must be at least 2 characters.")
    return search_players(df, query)


@router.get("/players/{player_id}", response_model=PlayerProfileResponse)
def profile(
    player_id: int,
    df: pd.DataFrame = Depends(get_df),
    id_map: dict = Depends(get_id_map),
):
    return get_player_profile(df, id_map, player_id)
