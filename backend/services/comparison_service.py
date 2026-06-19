from __future__ import annotations

import pandas as pd
from fastapi import HTTPException

from analytics.comparison_engine import generate_comparison, PlayerComparison
from backend.services.player_service import make_player_id


def compare_players(
    df: pd.DataFrame,
    id_map: dict,
    player1_id: int,
    player2_id: int,
) -> dict:
    if player1_id == player2_id:
        raise HTTPException(
            status_code=422,
            detail="Cannot compare a player with themselves.",
        )

    pos1 = id_map.get(player1_id)
    if pos1 is None:
        raise HTTPException(status_code=404, detail="Player not found: player1.")

    pos2 = id_map.get(player2_id)
    if pos2 is None:
        raise HTTPException(status_code=404, detail="Player not found: player2.")

    row1 = df.iloc[pos1]
    row2 = df.iloc[pos2]

    result = generate_comparison(row1, row2, df)
    return _to_dict(result, player1_id, player2_id, row1, row2)


def _player_identity(row: pd.Series, player_id: int) -> dict:
    return {
        "id": player_id,
        "player_name": str(row["player_name"]),
        "club": str(row["club"]),
        "competition": str(row["competition"]),
        "nationality": str(row["nationality"]),
        "position": str(row["position"]),
        "age": int(row.get("age", 0)),
        "season": str(row["season"]),
    }


def _to_dict(
    result: PlayerComparison,
    p1_id: int,
    p2_id: int,
    row1: pd.Series,
    row2: pd.Series,
) -> dict:
    return {
        "player1": _player_identity(row1, p1_id),
        "player2": _player_identity(row2, p2_id),
        "same_position": result.same_position,
        "data_warning": result.data_warning,
        "metrics": [
            {
                "metric": m.metric,
                "label": m.label,
                "is_scored": m.is_scored,
                "player1": {
                    "value": m.player1_value,
                    "percentile": m.player1_percentile,
                },
                "player2": {
                    "value": m.player2_value,
                    "percentile": m.player2_percentile,
                },
                "winner": m.winner,
                "advantage": m.advantage,
            }
            for m in result.metrics
        ],
        "strengths": {
            "player1_only": result.strengths.player1_only,
            "player2_only": result.strengths.player2_only,
            "shared": result.strengths.shared,
        },
        "weaknesses": {
            "player1_only": result.weaknesses.player1_only,
            "player2_only": result.weaknesses.player2_only,
            "shared": result.weaknesses.shared,
        },
        "verdict": {
            "winner": result.verdict.winner,
            "metrics_won": result.verdict.metrics_won,
            "advantage_score": result.verdict.advantage_score,
            "summary": result.verdict.summary,
        },
    }
