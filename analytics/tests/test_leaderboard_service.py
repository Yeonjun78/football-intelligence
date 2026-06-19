"""
Unit tests for backend/services/leaderboard_service.py.

Uses a synthetic 6-player dataset with strictly differentiated stats so
sort/filter outcomes are deterministic without relying on floating-point ties.

_add_rate_cols column formulas (from profile_generator.py):
    goals_p90     = goals  / clip(minutes_played, 1) * 90
    assists_p90   = assists / clip(minutes_played, 1) * 90
    gc_p90        = goals_p90 + assists_p90
    minutes_share = minutes_played / (clip(appearances, 1) * 90)
"""

import pandas as pd
import pytest
from fastapi import HTTPException

from backend.services.leaderboard_service import (
    VALID_SORT_FIELDS,
    get_leaderboard,
)


# ---------------------------------------------------------------------------
# Synthetic dataset
# ---------------------------------------------------------------------------

def _row(name, pos, comp, apps, mins, goals, assists, npg=None):
    return {
        "player_name": name,
        "position": pos,
        "competition": comp,
        "club": "Club",
        "nationality": "EN",
        "age": 25,
        "season": "2025-26",
        "appearances": apps,
        "minutes_played": mins,
        "goals": goals,
        "assists": assists,
        "non_penalty_goals": npg if npg is not None else goals,
    }


_ROWS = [
    # name              pos   comp            apps  mins  goals  assists
    _row("FW_high",    "FW", "Premier League", 30, 2700,    20,     5),
    _row("FW_low",     "FW", "La Liga",        15, 1350,     8,     3),
    _row("FW_micro",   "FW", "Premier League",  3,  270,     2,     1),  # below min-apps threshold
    _row("MF_top",     "MF", "Premier League", 28, 2520,     5,    10),
    _row("DF_solid",   "DF", "Bundesliga",     25, 2250,     1,     2),
    _row("GK_regular", "GK", "Premier League", 32, 2880,     0,     0),
]

_DF = pd.DataFrame(_ROWS).reset_index(drop=True)  # RangeIndex 0-5
# id_map: player_id -> iloc position
_ID_MAP = {1001: 0, 1002: 1, 1003: 2, 1004: 3, 1005: 4, 1006: 5}


# ---------------------------------------------------------------------------
# Position filter
# ---------------------------------------------------------------------------

class TestPositionFilter:
    def test_fw_returns_only_forwards(self):
        r = get_leaderboard(_DF, _ID_MAP, position="FW", limit=10)
        positions = {p["position"] for p in r["players"]}
        assert positions == {"FW"}
        assert r["total"] == 3

    def test_gk_returns_only_keepers(self):
        r = get_leaderboard(_DF, _ID_MAP, position="GK")
        assert r["total"] == 1
        assert r["players"][0]["player_name"] == "GK_regular"

    def test_none_position_returns_all(self):
        r = get_leaderboard(_DF, _ID_MAP, position=None, limit=10)
        assert r["total"] == 6

    def test_position_is_case_insensitive(self):
        upper = get_leaderboard(_DF, _ID_MAP, position="FW")
        lower = get_leaderboard(_DF, _ID_MAP, position="fw")
        assert upper["total"] == lower["total"]

    def test_invalid_position_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            get_leaderboard(_DF, _ID_MAP, position="XX")
        assert exc_info.value.status_code == 422
        assert "Invalid position" in exc_info.value.detail

    def test_invalid_position_message_lists_valid_options(self):
        with pytest.raises(HTTPException) as exc_info:
            get_leaderboard(_DF, _ID_MAP, position="ST")
        detail = exc_info.value.detail
        for pos in ("FW", "MF", "DF", "GK"):
            assert pos in detail


# ---------------------------------------------------------------------------
# Competition filter
# ---------------------------------------------------------------------------

class TestCompetitionFilter:
    def test_filters_to_premier_league(self):
        r = get_leaderboard(_DF, _ID_MAP, competition="Premier League", limit=10)
        comps = {p["competition"] for p in r["players"]}
        assert comps == {"Premier League"}
        # FW_high, FW_micro, MF_top, GK_regular
        assert r["total"] == 4

    def test_competition_case_insensitive(self):
        upper = get_leaderboard(_DF, _ID_MAP, competition="Premier League")
        lower = get_leaderboard(_DF, _ID_MAP, competition="premier league")
        assert upper["total"] == lower["total"]

    def test_nonexistent_competition_returns_empty(self):
        r = get_leaderboard(_DF, _ID_MAP, competition="Serie A")
        assert r["total"] == 0
        assert r["players"] == []

    def test_position_and_competition_combined(self):
        r = get_leaderboard(_DF, _ID_MAP, position="FW", competition="Premier League", limit=10)
        for p in r["players"]:
            assert p["position"] == "FW"
            assert p["competition"] == "Premier League"
        # FW_high, FW_micro both match
        assert r["total"] == 2


# ---------------------------------------------------------------------------
# Min appearances filter
# ---------------------------------------------------------------------------

class TestMinAppearances:
    def test_min_5_excludes_micro_player(self):
        r = get_leaderboard(_DF, _ID_MAP, min_appearances=5, limit=10)
        names = {p["player_name"] for p in r["players"]}
        assert "FW_micro" not in names

    def test_min_0_includes_all(self):
        r = get_leaderboard(_DF, _ID_MAP, min_appearances=0, limit=10)
        assert r["total"] == 6

    def test_high_threshold_returns_empty(self):
        r = get_leaderboard(_DF, _ID_MAP, min_appearances=50)
        assert r["total"] == 0
        assert r["players"] == []

    def test_exact_threshold_is_inclusive(self):
        # FW_low has 15 appearances
        r = get_leaderboard(_DF, _ID_MAP, min_appearances=15, limit=10)
        names = {p["player_name"] for p in r["players"]}
        assert "FW_low" in names

    def test_one_above_threshold_is_excluded(self):
        r = get_leaderboard(_DF, _ID_MAP, min_appearances=16, limit=10)
        names = {p["player_name"] for p in r["players"]}
        assert "FW_low" not in names


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------

class TestSortBy:
    def test_goals_p90_desc_order(self):
        r = get_leaderboard(_DF, _ID_MAP, sort_by="goals_p90", sort_order="desc", limit=10)
        values = [p["goals_p90"] for p in r["players"]]
        assert values == sorted(values, reverse=True)

    def test_goals_p90_asc_order(self):
        r = get_leaderboard(_DF, _ID_MAP, sort_by="goals_p90", sort_order="asc", limit=10)
        values = [p["goals_p90"] for p in r["players"]]
        assert values == sorted(values)

    def test_appearances_desc_order(self):
        r = get_leaderboard(_DF, _ID_MAP, sort_by="appearances", sort_order="desc", limit=10)
        values = [p["appearances"] for p in r["players"]]
        assert values == sorted(values, reverse=True)

    def test_assists_p90_desc_top_player(self):
        # MF_top: 10 assists / 2520 mins → 10/28 * 90 ≈ 0.357
        # FW_high: 5 assists / 2700 mins → 5/30 * 90 ≈ 0.167
        r = get_leaderboard(_DF, _ID_MAP, sort_by="assists_p90", sort_order="desc", limit=1)
        assert r["players"][0]["player_name"] == "MF_top"

    def test_invalid_sort_by_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            get_leaderboard(_DF, _ID_MAP, sort_by="market_value")
        assert exc_info.value.status_code == 422
        assert "Invalid sort_by" in exc_info.value.detail

    def test_invalid_sort_order_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            get_leaderboard(_DF, _ID_MAP, sort_order="random")
        assert exc_info.value.status_code == 422

    def test_all_valid_sort_fields_accepted(self):
        for field in VALID_SORT_FIELDS:
            r = get_leaderboard(_DF, _ID_MAP, sort_by=field, limit=1)
            assert "players" in r, f"sort_by={field} should succeed"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class TestPagination:
    def test_limit_controls_page_size(self):
        r = get_leaderboard(_DF, _ID_MAP, limit=2)
        assert len(r["players"]) == 2

    def test_total_is_unaffected_by_limit(self):
        r1 = get_leaderboard(_DF, _ID_MAP, limit=1)
        r2 = get_leaderboard(_DF, _ID_MAP, limit=100)
        assert r1["total"] == r2["total"] == 6

    def test_offset_skips_leading_rows(self):
        r_all = get_leaderboard(_DF, _ID_MAP, limit=6)
        r_offset = get_leaderboard(_DF, _ID_MAP, limit=4, offset=2)
        ids_all = [p["id"] for p in r_all["players"]]
        ids_offset = [p["id"] for p in r_offset["players"]]
        assert ids_offset == ids_all[2:6]

    def test_offset_beyond_total_returns_empty_players(self):
        r = get_leaderboard(_DF, _ID_MAP, offset=100)
        assert r["players"] == []
        assert r["total"] == 6  # total reflects pre-pagination count

    def test_limit_zero_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            get_leaderboard(_DF, _ID_MAP, limit=0)
        assert exc_info.value.status_code == 422

    def test_limit_501_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            get_leaderboard(_DF, _ID_MAP, limit=501)
        assert exc_info.value.status_code == 422

    def test_negative_offset_raises_422(self):
        with pytest.raises(HTTPException) as exc_info:
            get_leaderboard(_DF, _ID_MAP, offset=-1)
        assert exc_info.value.status_code == 422

    def test_response_echoes_limit_and_offset(self):
        r = get_leaderboard(_DF, _ID_MAP, limit=3, offset=1)
        assert r["limit"] == 3
        assert r["offset"] == 1


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

class TestResponseShape:
    def test_top_level_keys(self):
        r = get_leaderboard(_DF, _ID_MAP)
        assert set(r.keys()) == {
            "total", "limit", "offset", "sort_by", "sort_order",
            "filters_applied", "players",
        }

    def test_player_keys(self):
        r = get_leaderboard(_DF, _ID_MAP, limit=1)
        assert r["players"], "expected at least one player"
        p = r["players"][0]
        expected = {
            "id", "player_name", "club", "competition", "nationality",
            "position", "age", "season", "appearances", "minutes_played",
            "goals", "assists", "non_penalty_goals",
            "goals_p90", "assists_p90", "gc_p90", "minutes_share",
        }
        assert set(p.keys()) == expected

    def test_filters_applied_reflects_params(self):
        r = get_leaderboard(_DF, _ID_MAP, position="FW", competition="La Liga", min_appearances=10)
        fa = r["filters_applied"]
        assert fa["position"] == "FW"
        assert fa["competition"] == "La Liga"
        assert fa["min_appearances"] == 10

    def test_filters_applied_none_for_unset_params(self):
        r = get_leaderboard(_DF, _ID_MAP)
        fa = r["filters_applied"]
        assert fa["position"] is None
        assert fa["competition"] is None

    def test_player_id_matches_id_map(self):
        r = get_leaderboard(_DF, _ID_MAP, limit=10)
        inv = {iloc: pid for pid, iloc in _ID_MAP.items()}
        for player in r["players"]:
            row_idx = _DF[_DF["player_name"] == player["player_name"]].index[0]
            assert player["id"] == inv[row_idx], (
                f"id mismatch for {player['player_name']}"
            )

    def test_gc_p90_equals_goals_plus_assists_p90(self):
        r = get_leaderboard(_DF, _ID_MAP, limit=10)
        for p in r["players"]:
            expected = round(p["goals_p90"] + p["assists_p90"], 2)
            actual = round(p["gc_p90"], 2)
            assert abs(actual - expected) < 0.01, (
                f"{p['player_name']}: gc_p90={actual}, expected≈{expected}"
            )

    def test_sort_by_and_sort_order_echoed_in_response(self):
        r = get_leaderboard(_DF, _ID_MAP, sort_by="assists_p90", sort_order="asc")
        assert r["sort_by"] == "assists_p90"
        assert r["sort_order"] == "asc"

    def test_non_penalty_goals_in_response(self):
        r = get_leaderboard(_DF, _ID_MAP, limit=1)
        assert "non_penalty_goals" in r["players"][0]


# ---------------------------------------------------------------------------
# Computed column correctness
# ---------------------------------------------------------------------------

class TestComputedColumns:
    def test_goals_p90_formula(self):
        # FW_high: 20 goals / 2700 mins * 90 = 0.667
        r = get_leaderboard(_DF, _ID_MAP, position="FW", sort_by="goals_p90", sort_order="desc", limit=1)
        p = r["players"][0]
        assert p["player_name"] == "FW_high"
        expected = round(20 / 2700 * 90, 3)
        assert abs(p["goals_p90"] - expected) < 0.001

    def test_minutes_share_formula(self):
        # GK_regular: 2880 mins / (32 apps * 90) = 1.0
        r = get_leaderboard(_DF, _ID_MAP, position="GK")
        p = r["players"][0]
        expected = round(2880 / (32 * 90), 4)
        assert abs(p["minutes_share"] - expected) < 0.001
