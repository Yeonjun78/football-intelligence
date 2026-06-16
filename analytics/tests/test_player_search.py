"""Unit tests for accent-insensitive player search."""

import pandas as pd
import pytest

from analytics.player_search import _normalize, search, search_exact, search_partial

# Minimal DataFrame that mirrors the real schema expected by DISPLAY_COLUMNS.
_PLAYERS = [
    ("Kylian Mbappé", "2024-25", "Real Madrid", "Champions League", "France", "FW", 26, 30, 2700, 25, 5, 24),
    ("João Cancelo", "2024-25", "Barcelona", "La Liga", "Portugal", "DF", 31, 28, 2520, 2, 7, 2),
    ("João Félix", "2024-25", "Atletico Madrid", "La Liga", "Portugal", "FW", 25, 25, 2200, 10, 4, 10),
    ("Erling Haaland", "2024-25", "Man City", "Premier League", "Norway", "FW", 24, 32, 2880, 27, 5, 27),
    ("Ionuț Radu", "2024-25", "Celta Vigo", "La Liga", "Romania", "GK", 28, 38, 3420, 0, 0, 0),
    ("Luka Modrić", "2024-25", "Real Madrid", "La Liga", "Croatia", "MF", 39, 25, 2000, 3, 8, 3),
]
_COLS = [
    "player_name", "season", "club", "competition", "nationality",
    "position", "age", "appearances", "minutes_played",
    "goals", "assists", "non_penalty_goals",
]


def _make_df() -> pd.DataFrame:
    df = pd.DataFrame(_PLAYERS, columns=_COLS)
    # Mirror what load_players() does: add the _name_key column.
    from analytics.player_search import _normalize
    df["_name_key"] = df["player_name"].fillna("").apply(_normalize)
    return df


# ── _normalize ──────────────────────────────────────────────────────────────

def test_normalize_strips_acute_accent():
    assert _normalize("Mbappé") == "mbappe"


def test_normalize_strips_tilde():
    assert _normalize("João") == "joao"


def test_normalize_strips_cedilla():
    assert _normalize("Modrić") == "modric"


def test_normalize_is_case_insensitive():
    assert _normalize("MBAPPE") == "mbappe"
    assert _normalize("Mbappé") == "mbappe"


def test_normalize_plain_ascii_unchanged():
    assert _normalize("Haaland") == "haaland"


# ── search_exact ─────────────────────────────────────────────────────────────

def test_exact_accent_query_finds_accented_name():
    df = _make_df()
    result = search_exact(df, "Kylian Mbappé")
    assert len(result) == 1
    assert result.iloc[0]["player_name"] == "Kylian Mbappé"


def test_exact_unaccented_query_finds_accented_name():
    df = _make_df()
    result = search_exact(df, "Kylian Mbappe")
    assert len(result) == 1
    assert result.iloc[0]["player_name"] == "Kylian Mbappé"


def test_exact_joao_query_finds_joao():
    df = _make_df()
    result = search_exact(df, "Joao Cancelo")
    assert len(result) == 1
    assert result.iloc[0]["player_name"] == "João Cancelo"


def test_exact_case_insensitive():
    df = _make_df()
    result = search_exact(df, "erling haaland")
    assert len(result) == 1


def test_exact_no_match_returns_empty():
    df = _make_df()
    result = search_exact(df, "Cristiano Ronaldo")
    assert result.empty


# ── search_partial ────────────────────────────────────────────────────────────

def test_partial_unaccented_finds_accented():
    df = _make_df()
    result = search_partial(df, "Mbappe")
    assert len(result) == 1
    assert result.iloc[0]["player_name"] == "Kylian Mbappé"


def test_partial_joao_finds_joao():
    df = _make_df()
    result = search_partial(df, "Joao")
    assert len(result) == 2
    assert "João Cancelo" in result["player_name"].values
    assert "João Félix" in result["player_name"].values


def test_partial_modric_finds_modric():
    df = _make_df()
    result = search_partial(df, "Modric")
    assert len(result) == 1
    assert result.iloc[0]["player_name"] == "Luka Modrić"


def test_partial_case_insensitive():
    df = _make_df()
    result = search_partial(df, "haaland")
    assert len(result) == 1


def test_partial_multiple_results():
    """Partial 'joao' should match both João Cancelo and João Félix (accent-insensitive)."""
    df = _make_df()
    result = search_partial(df, "joao")
    assert len(result) == 2
    assert set(result["player_name"]) == {"João Cancelo", "João Félix"}


def test_partial_no_match_returns_empty():
    df = _make_df()
    result = search_partial(df, "zzznomatch")
    assert result.empty


# ── search (combined) ─────────────────────────────────────────────────────────

def test_search_falls_back_to_partial():
    """'Mbappe' won't exact-match; should fall back to partial and find Mbappé."""
    df = _make_df()
    result = search(df, "Mbappe")
    assert len(result) == 1
    assert result.iloc[0]["player_name"] == "Kylian Mbappé"


def test_search_exact_match_preferred():
    df = _make_df()
    result = search(df, "Erling Haaland")
    assert len(result) == 1
    assert result.iloc[0]["player_name"] == "Erling Haaland"


# ── display names are never mutated ──────────────────────────────────────────

def test_displayed_name_is_original():
    df = _make_df()
    for func in (search_exact, search_partial):
        result = func(df, "Ionut Radu")
        if not result.empty:
            assert result.iloc[0]["player_name"] == "Ionuț Radu"


def test_name_key_not_in_results():
    df = _make_df()
    result = search_partial(df, "Mbappe")
    assert "_name_key" not in result.columns
