import zlib

import pandas as pd
from fastapi import HTTPException

from analytics.player_search import search
from analytics.profile_generator import generate_profile

def make_player_id(player_name: str, club: str, competition: str, season: str) -> int:
    key = f"{player_name}|{club}|{competition}|{season}"
    return zlib.crc32(key.encode()) & 0xFFFFFFFF


def search_players(df: pd.DataFrame, query: str) -> list[dict]:
    results = search(df, query)
    out = []
    for _, row in results.iterrows():
        out.append({
            "id": make_player_id(
                str(row["player_name"]),
                str(row["club"]),
                str(row["competition"]),
                str(row["season"]),
            ),
            "player_name": str(row["player_name"]),
            "club": str(row["club"]),
            "competition": str(row["competition"]),
            "nationality": str(row["nationality"]),
            "position": str(row["position"]),
            "season": str(row["season"]),
        })
    return out


def get_player_profile(df: pd.DataFrame, id_map: dict, player_id: int) -> dict:
    row_pos = id_map.get(player_id)
    if row_pos is None:
        raise HTTPException(status_code=404, detail="Player not found.")
    row = df.iloc[row_pos]
    profile = generate_profile(row, df)
    return {
        "id": player_id,
        "player_name": profile.player_name,
        "season": profile.season,
        "club": profile.club,
        "competition": profile.competition,
        "nationality": profile.nationality,
        "position": profile.position,
        "age": profile.age,
        "overview": profile.overview,
        "strengths": profile.strengths,
        "weaknesses": profile.weaknesses,
        "stats": profile.stats,
        "peer_group_size": profile.peer_group_size,
    }
