from __future__ import annotations

import pandas as pd
from fastapi import HTTPException

from analytics.profile_generator import _add_rate_cols

VALID_POSITIONS: frozenset[str] = frozenset({"FW", "MF", "DF", "GK"})

VALID_SORT_FIELDS: frozenset[str] = frozenset({
    "goals_p90",
    "assists_p90",
    "gc_p90",
    "goals",
    "assists",
    "appearances",
    "minutes_played",
    "minutes_share",
})


def _validate(
    position: str | None,
    sort_by: str,
    sort_order: str,
    limit: int,
    offset: int,
) -> None:
    if position is not None and position.upper() not in VALID_POSITIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid position '{position}'. Must be one of: FW, MF, DF, GK.",
        )
    if sort_by not in VALID_SORT_FIELDS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid sort_by '{sort_by}'. "
                f"Must be one of: {', '.join(sorted(VALID_SORT_FIELDS))}."
            ),
        )
    if sort_order not in ("asc", "desc"):
        raise HTTPException(
            status_code=422,
            detail="sort_order must be 'asc' or 'desc'.",
        )
    if not (1 <= limit <= 500):
        raise HTTPException(
            status_code=422,
            detail="limit must be between 1 and 500.",
        )
    if offset < 0:
        raise HTTPException(
            status_code=422,
            detail="offset must be >= 0.",
        )


def get_leaderboard(
    df: pd.DataFrame,
    id_map: dict,
    *,
    position: str | None = None,
    competition: str | None = None,
    min_appearances: int = 0,
    sort_by: str = "goals_p90",
    sort_order: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Filter, sort, and paginate the player dataset.

    id_map: player_id -> iloc position (RangeIndex assumption).
    Returns a plain dict that matches LeaderboardResponse schema.
    """
    _validate(position, sort_by, sort_order, limit, offset)

    # Inverse map: original iloc position -> player_id
    inv_id_map: dict[int, int] = {iloc: pid for pid, iloc in id_map.items()}

    # Enrich with computed rate columns.
    # Preserves RangeIndex so idx labels equal original iloc positions.
    enriched = _add_rate_cols(df.copy())

    # --- filter ---
    mask = pd.Series(True, index=enriched.index)
    if position is not None:
        mask &= enriched["position"].str.upper() == position.upper()
    if competition is not None:
        mask &= enriched["competition"].str.lower() == competition.lower()
    if min_appearances > 0:
        mask &= enriched["appearances"] >= min_appearances

    filtered = enriched.loc[mask]
    total = len(filtered)

    # --- sort ---
    filtered = filtered.sort_values(sort_by, ascending=(sort_order == "asc"))

    # --- paginate ---
    page = filtered.iloc[offset: offset + limit]

    # --- serialise ---
    players = []
    for idx, row in page.iterrows():
        original_pos = int(idx)  # RangeIndex: label == original iloc position
        player_id = inv_id_map.get(original_pos, 0)
        players.append({
            "id": player_id,
            "player_name": str(row["player_name"]),
            "club": str(row["club"]),
            "competition": str(row["competition"]),
            "nationality": str(row["nationality"]),
            "position": str(row["position"]),
            "age": int(row.get("age", 0)),
            "season": str(row["season"]),
            "appearances": int(row["appearances"]),
            "minutes_played": int(row["minutes_played"]),
            "goals": int(row["goals"]),
            "assists": int(row["assists"]),
            "non_penalty_goals": int(row.get("non_penalty_goals", 0)),
            "goals_p90": round(float(row["goals_p90"]), 3),
            "assists_p90": round(float(row["assists_p90"]), 3),
            "gc_p90": round(float(row["gc_p90"]), 3),
            "minutes_share": round(float(row["minutes_share"]), 4),
        })

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "sort_by": sort_by,
        "sort_order": sort_order,
        "filters_applied": {
            "position": position,
            "competition": competition,
            "min_appearances": min_appearances,
        },
        "players": players,
    }
