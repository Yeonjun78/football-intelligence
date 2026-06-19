import pandas as pd
from fastapi import APIRouter, Depends, Query

from backend.dependencies import get_df, get_id_map
from backend.models.comparison_schemas import ComparisonResponse
from backend.services.comparison_service import compare_players

router = APIRouter()


@router.get("/compare", response_model=ComparisonResponse)
def compare(
    player1: int = Query(..., description="Player 1 hash ID from search results"),
    player2: int = Query(..., description="Player 2 hash ID from search results"),
    df: pd.DataFrame = Depends(get_df),
    id_map: dict = Depends(get_id_map),
):
    return compare_players(df, id_map, player1, player2)
