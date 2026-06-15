"""
MVP 1 Phase 2 — Player Search
Loads the cleaned player dataset and provides exact and partial name search.
"""

import logging
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_FILE = ROOT / "data" / "processed" / "cleaned_players.csv"

DISPLAY_COLUMNS = [
    "player_name",
    "season",
    "club",
    "competition",
    "nationality",
    "position",
    "age",
    "appearances",
    "minutes_played",
    "goals",
    "assists",
    "non_penalty_goals",
]


def load_players(path: Path = PROCESSED_FILE) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found: {path}\n"
            "Run analytics/prepare_data.py first."
        )
    df = pd.read_csv(path, dtype=str)
    int_cols = ["age", "appearances", "minutes_played", "goals", "assists", "non_penalty_goals"]
    for col in int_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
    return df


def search_exact(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Return rows where player_name matches exactly (case-insensitive)."""
    mask = df["player_name"].str.lower() == name.strip().lower()
    return df[mask][DISPLAY_COLUMNS].reset_index(drop=True)


def search_partial(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Return rows where player_name contains the query string (case-insensitive)."""
    mask = df["player_name"].str.contains(query.strip(), case=False, na=False, regex=False)
    return df[mask][DISPLAY_COLUMNS].reset_index(drop=True)


def search(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Try exact match first; fall back to partial match if no results."""
    results = search_exact(df, query)
    if results.empty:
        results = search_partial(df, query)
    return results


def format_result(row: pd.Series) -> str:
    lines = [
        row["player_name"],
        f"  Club:           {row['club']}",
        f"  League:         {row['competition']}",
        f"  Nationality:    {row['nationality']}",
        f"  Position:       {row['position']}",
        f"  Age:            {row['age']}",
        f"  Appearances:    {row['appearances']}",
        f"  Minutes:        {row['minutes_played']}",
        f"  Goals:          {row['goals']}",
        f"  Assists:        {row['assists']}",
        f"  Non-PK Goals:   {row['non_penalty_goals']}",
    ]
    return "\n".join(str(x) for x in lines)


def print_results(results: pd.DataFrame, query: str) -> None:
    if results.empty:
        print(f"No players found matching '{query}'.")
        return
    print(f"\n{len(results)} player(s) found for '{query}':\n")
    print("-" * 40)
    for _, row in results.iterrows():
        print(format_result(row))
        print("-" * 40)


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    try:
        df = load_players()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # CLI argument takes priority; interactive fallback otherwise
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        try:
            query = input("Enter player name: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

    if not query:
        print("No search query provided.")
        sys.exit(1)

    results = search(df, query)
    print_results(results, query)


if __name__ == "__main__":
    main()
