"""
MVP 1 Phase 3 — Player Profile Generator
Rule-based profile generation using percentile ranking within position peer groups.
No AI API calls. Analysis is derived entirely from cleaned statistical data.
"""

import sys
from dataclasses import dataclass

import pandas as pd

try:
    from .player_search import load_players, search        # package import (FastAPI)
except ImportError:
    from player_search import load_players, search         # direct execution fallback

# Percentile thresholds for strength / weakness classification
STRENGTH_THRESHOLD = 75   # >= 75th percentile within position group → strength
ELITE_THRESHOLD = 90      # >= 90th percentile → elite label
WEAKNESS_THRESHOLD = 25   # <= 25th percentile → weakness


@dataclass
class PlayerProfile:
    player_name: str
    season: str
    club: str
    competition: str
    nationality: str
    position: str
    age: int
    overview: str
    strengths: list[str]
    weaknesses: list[str]
    stats: dict
    peer_group_size: int


# ── Internal helpers ──────────────────────────────────────────────────────────


def _f(val) -> float:
    """Safely cast any pandas scalar (including Int64 / NA) to float."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _add_rate_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    mins = df["minutes_played"].astype(float).clip(lower=1)
    apps = df["appearances"].astype(float).clip(lower=1)
    nineties = mins / 90

    df["goals_p90"] = df["goals"].astype(float) / nineties
    df["assists_p90"] = df["assists"].astype(float) / nineties
    df["gc_p90"] = (df["goals"].astype(float) + df["assists"].astype(float)) / nineties
    df["minutes_share"] = mins / (apps * 90)
    return df


def _pct_rank(value: float, series: pd.Series) -> float:
    """Percentile rank (0-100) using the midpoint method for tied values.

    Strict less-than assigns the bottom of any tie cluster; midpoint assigns the
    centre, which is the standard scipy.stats.percentileofscore('average') behaviour.
    This matters wherever many players share the same value (e.g. GK minutes_share=1.0,
    players with 0 goals).
    """
    valid = series.dropna()
    if not valid.size:
        return 50.0
    below = (valid < value).sum()
    equal = (valid == value).sum()
    return float((below + equal / 2) / len(valid) * 100)


def _percentiles(player_row: pd.Series, peer_df: pd.DataFrame) -> dict[str, float]:
    metrics = ["goals_p90", "assists_p90", "gc_p90", "minutes_share", "appearances"]
    return {m: _pct_rank(_f(player_row[m]), peer_df[m]) for m in metrics}


# ── Overview ──────────────────────────────────────────────────────────────────


def _overview(row: pd.Series, pct: dict[str, float]) -> str:
    pos = str(row["position"])
    club = str(row["club"])
    comp = str(row["competition"])
    age = int(_f(row["age"]))

    if pos == "FW":
        g = pct["goals_p90"]
        if g >= ELITE_THRESHOLD:
            return "Exceptional striker with elite goal production, among the most clinical finishers in the league."
        if g >= STRENGTH_THRESHOLD:
            return "Elite striker with strong goal production and consistent attacking presence."
        if g >= 50:
            return f"Productive forward contributing goals and building attacking play for {club}."
        return f"Forward with limited scoring output relative to peers in {comp}."

    if pos == "MF":
        gc, g, a = pct["gc_p90"], pct["goals_p90"], pct["assists_p90"]
        if gc >= ELITE_THRESHOLD:
            return "Exceptional midfielder delivering elite goal contributions across goals and assists."
        if gc >= STRENGTH_THRESHOLD:
            if g >= STRENGTH_THRESHOLD and a >= STRENGTH_THRESHOLD:
                return f"Dynamic complete midfielder delivering both goals and assists at a high level for {club}."
            if a >= STRENGTH_THRESHOLD:
                return f"Creative playmaker generating consistent attacking output for {club}."
            if g >= STRENGTH_THRESHOLD:
                return "Goal-scoring midfielder providing a strong offensive threat from midfield."
            return f"Influential midfielder with strong overall attacking contribution for {club}."
        if gc >= 50:
            return f"Reliable midfielder providing steady attacking contribution in {comp}."
        return f"Midfielder with limited attacking output relative to peers in {comp}."

    if pos == "DF":
        a = pct["appearances"]
        if a >= STRENGTH_THRESHOLD:
            if age <= 23:
                return f"Young defender establishing themselves as a trusted regular starter at {club}."
            return f"Experienced, reliable defensive presence consistently selected by the coaching staff at {club}."
        if a >= 50:
            return f"Consistent defensive option providing steady presence in {comp}."
        return f"Rotational defender making contributions when selected at {club}."

    if pos == "GK":
        a = pct["appearances"]
        # GK threshold is 65 (not 75) — appearances is their only available metric
        # in this dataset, so we use a wider band to produce meaningful output.
        if a >= 65:
            return f"Trusted first-choice goalkeeper, consistently selected throughout the 2025-26 season at {club}."
        if a >= 40:
            return f"Reliable goalkeeper competing for the starting position at {club}."
        return f"Backup goalkeeper providing cover at {club}."

    return f"Professional player competing in {comp} during the 2025-26 season."


# ── Strengths ─────────────────────────────────────────────────────────────────


def _strengths(row: pd.Series, pct: dict[str, float]) -> list[str]:
    pos = str(row["position"])
    out: list[str] = []

    if pos in ("FW", "MF"):
        g_p = pct["goals_p90"]
        a_p = pct["assists_p90"]
        gc_p = pct["gc_p90"]
        goals = _f(row["goals"])
        npg = _f(row["non_penalty_goals"])
        pen = goals - npg

        if g_p >= ELITE_THRESHOLD:
            out.append("Elite goal scoring")
        elif g_p >= STRENGTH_THRESHOLD:
            out.append("Goal scoring")

        if a_p >= ELITE_THRESHOLD:
            out.append("Elite chance creation")
        elif a_p >= STRENGTH_THRESHOLD:
            out.append("Chance creation")

        # Overall contribution only if individual metrics didn't already flag it
        covered = any(k in " ".join(out).lower() for k in ("goal", "chance"))
        if gc_p >= STRENGTH_THRESHOLD and not covered:
            out.append("Attacking output")

        # Penalty conversion only if it's a meaningful part of the output
        if goals >= 5 and pen >= 4 and pen / goals >= 0.25:
            out.append("Penalty conversion")

    if pos == "DF":
        if pct["goals_p90"] >= ELITE_THRESHOLD:
            out.append("Elite goal threat from set pieces")
        elif pct["goals_p90"] >= STRENGTH_THRESHOLD:
            out.append("Goal threat from set pieces")

    # Availability: GK/DF use 65th-percentile threshold (not 75th) because
    # appearances is their only available metric in this 12-column dataset.
    avail_threshold = 65 if pos in ("GK", "DF") else STRENGTH_THRESHOLD
    if pct["appearances"] >= avail_threshold:
        out.append("Availability")

    return out


# ── Weaknesses ────────────────────────────────────────────────────────────────


def _weaknesses(row: pd.Series, pct: dict[str, float]) -> list[str]:
    pos = str(row["position"])
    out: list[str] = []

    if pos in ("FW", "MF"):
        if pct["goals_p90"] <= WEAKNESS_THRESHOLD:
            out.append("Below-average goal output")
        if pct["assists_p90"] <= WEAKNESS_THRESHOLD:
            out.append("Limited creative output")
        # Only add overall contribution weakness if neither specific metric flagged it
        if pct["gc_p90"] <= WEAKNESS_THRESHOLD and len(out) == 0:
            out.append("Limited attacking contribution")

        goals = _f(row["goals"])
        npg = _f(row["non_penalty_goals"])
        if goals >= 5 and (goals - npg) / goals >= 0.40:
            out.append("Heavy reliance on penalties")

    # Playing time / selection
    if pct["appearances"] <= WEAKNESS_THRESHOLD:
        out.append("Limited appearances")
    elif pct["minutes_share"] <= WEAKNESS_THRESHOLD:
        out.append("Often used as substitute or rotation player")

    # Structural role observation (FW only — well-established football analytics convention)
    if pos == "FW":
        out.append("Defensive contribution")

    return out


# ── Statistical summary ───────────────────────────────────────────────────────


def _stats_summary(row: pd.Series) -> dict:
    mins = _f(row["minutes_played"])
    nineties = mins / 90 if mins > 0 else 1
    goals = _f(row["goals"])
    assists = _f(row["assists"])
    npg = _f(row["non_penalty_goals"])
    apps = _f(row["appearances"])

    return {
        "appearances": int(apps),
        "minutes_played": int(mins),
        "goals": int(goals),
        "assists": int(assists),
        "non_penalty_goals": int(npg),
        "goal_contributions": int(goals + assists),
        "goals_per_90": round(goals / nineties, 2),
        "assists_per_90": round(assists / nineties, 2),
        "goal_contributions_per_90": round((goals + assists) / nineties, 2),
    }


# ── Public API ────────────────────────────────────────────────────────────────


def generate_profile(player_row: pd.Series, all_df: pd.DataFrame) -> PlayerProfile:
    """
    Generate a rule-based PlayerProfile for a single player.

    Args:
        player_row: A single row from the cleaned players DataFrame.
        all_df: The full cleaned DataFrame — used to compute position peer percentiles.
    """
    pos = str(player_row["position"])

    enriched = _add_rate_cols(all_df)
    player_e = _add_rate_cols(pd.DataFrame([player_row])).iloc[0]
    peer_df = enriched[enriched["position"] == pos]

    pct = _percentiles(player_e, peer_df)

    return PlayerProfile(
        player_name=str(player_row["player_name"]),
        season=str(player_row["season"]),
        club=str(player_row["club"]),
        competition=str(player_row["competition"]),
        nationality=str(player_row["nationality"]),
        position=pos,
        age=int(_f(player_row["age"])),
        overview=_overview(player_e, pct),
        strengths=_strengths(player_e, pct),
        weaknesses=_weaknesses(player_e, pct),
        stats=_stats_summary(player_e),
        peer_group_size=len(peer_df),
    )


def print_profile(profile: PlayerProfile) -> None:
    sep = "=" * 54
    print(f"\n{sep}")
    print(profile.player_name)
    print(f"{profile.club}  |  {profile.competition}")
    print(f"{profile.nationality}  |  {profile.position}  |  Age {profile.age}  |  {profile.season}")
    print(sep)

    print("\nOverview:")
    print(f"  {profile.overview}")

    print("\nStrengths:")
    items = profile.strengths or ["Insufficient data to identify clear strengths"]
    for item in items:
        print(f"  - {item}")

    print("\nWeaknesses:")
    items = profile.weaknesses or ["No notable weaknesses identified"]
    for item in items:
        print(f"  - {item}")

    s = profile.stats
    print("\nStatistical Summary:")
    print(f"  Appearances:             {s['appearances']}")
    print(f"  Minutes Played:          {s['minutes_played']}")
    print(f"  Goals:                   {s['goals']}")
    print(f"  Assists:                 {s['assists']}")
    print(f"  Non-Penalty Goals:       {s['non_penalty_goals']}")
    print(f"  Goal Contributions:      {s['goal_contributions']}")
    print(f"  Goals per 90:            {s['goals_per_90']}")
    print(f"  Assists per 90:          {s['assists_per_90']}")
    print(f"  Contributions per 90:    {s['goal_contributions_per_90']}")
    print(f"\n  Peer group: {profile.peer_group_size} {profile.position} players in dataset")
    print(f"{sep}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> None:
    try:
        df = load_players()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        try:
            query = input("Enter player name: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            sys.exit(0)

    if not query:
        print("No player name provided.")
        sys.exit(1)

    results = search(df, query)

    if results.empty:
        print(f"No players found matching '{query}'.")
        sys.exit(0)

    if len(results) == 1:
        player_row = results.iloc[0]
    else:
        print(f"\n{len(results)} players match '{query}':")
        for i, (_, row) in enumerate(results.iterrows(), 1):
            print(f"  {i}.  {row['player_name']}  ({row['club']}, {row['competition']})")

        if sys.stdin.isatty():
            try:
                choice = input("\nEnter number to select (Enter = 1): ").strip()
                idx = int(choice) - 1 if choice.isdigit() else 0
            except (EOFError, KeyboardInterrupt, ValueError):
                idx = 0
        else:
            idx = 0

        player_row = results.iloc[max(0, min(idx, len(results) - 1))]

    profile = generate_profile(player_row, df)
    print_profile(profile)


if __name__ == "__main__":
    main()
