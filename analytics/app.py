"""
Football Intelligence — MVP 1
AI Player Profile Generator — CLI entry point.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from player_search import load_players, search
from profile_generator import generate_profile, print_profile

BANNER = """
╔══════════════════════════════════════════════════════╗
║        Football Intelligence  — MVP 1                ║
║        AI Player Profile Generator                   ║
║        Season 2025-26  |  Big 5 European Leagues     ║
╚══════════════════════════════════════════════════════╝
"""


def _prompt_query() -> str:
    try:
        return input("Search player: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def _pick_player(results):
    """Return a single player row. If multiple matches, prompt for selection."""
    if len(results) == 1:
        return results.iloc[0]

    print(f"\n{len(results)} players match your search:\n")
    for i, (_, row) in enumerate(results.iterrows(), 1):
        print(f"  {i}.  {row['player_name']:<30}  {row['club']}  ({row['competition']})")

    try:
        choice = input("\nEnter number to select (Enter = 1): ").strip()
        idx = int(choice) - 1 if choice.isdigit() else 0
    except (EOFError, KeyboardInterrupt, ValueError):
        idx = 0

    return results.iloc[max(0, min(idx, len(results) - 1))]


def run(query: str | None = None) -> None:
    """
    Main application flow. Accepts an optional query string for non-interactive use.
    If query is None, prompts the user interactively.
    """
    print(BANNER)

    try:
        df = load_players()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"  Dataset loaded: {len(df):,} players across 5 leagues.\n")

    if query is None:
        query = _prompt_query()

    if not query:
        print("No search query entered.")
        sys.exit(1)

    results = search(df, query)

    if results.empty:
        print(f"\n  No players found matching '{query}'.")
        print("  Try a partial name (e.g. 'Kane' instead of 'Harry Kane') or check spelling.\n")
        sys.exit(0)

    player_row = _pick_player(results)
    profile = generate_profile(player_row, df)
    print_profile(profile)


def main() -> None:
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    run(query)


if __name__ == "__main__":
    main()
