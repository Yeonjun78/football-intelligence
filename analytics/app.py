"""
Football Intelligence — MVP 1
AI Player Profile Generator — CLI entry point.
"""

import sys

try:
    from analytics.player_search import load_players, search                          # package import
    from analytics.profile_generator import generate_profile, print_profile, PlayerProfile
except ImportError:
    from player_search import load_players, search                                    # direct execution
    from profile_generator import generate_profile, print_profile, PlayerProfile


class PlayerNotFoundError(Exception):
    """Raised when no players match the search query."""

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


def run(query: str | None = None) -> "PlayerProfile":
    """
    Main application flow. Accepts an optional query string for non-interactive use.
    If query is None, prompts the user interactively.

    Raises:
        FileNotFoundError:    cleaned dataset is missing — run prepare_data.py first.
        ValueError:           empty query string provided.
        PlayerNotFoundError:  no players match the query.
    """
    print(BANNER)

    df = load_players()  # raises FileNotFoundError if dataset is missing

    print(f"  Dataset loaded: {len(df):,} players across 5 leagues.\n")

    if query is None:
        query = _prompt_query()

    if not query:
        raise ValueError("No search query provided.")

    results = search(df, query)

    if results.empty:
        raise PlayerNotFoundError(query)

    player_row = _pick_player(results)
    profile = generate_profile(player_row, df)
    print_profile(profile)
    return profile


def main() -> None:
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    try:
        run(query)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except PlayerNotFoundError as e:
        print(f"\n  No players found matching '{e}'.")
        print("  Try a partial name (e.g. 'Kane' instead of 'Harry Kane') or check spelling.\n")
        sys.exit(0)
    except ValueError as e:
        print(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
