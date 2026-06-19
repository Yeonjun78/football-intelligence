from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from analytics.profile_generator import (
    _add_rate_cols,
    _percentiles,
    _pct_rank,
    _strengths,
    _weaknesses,
)

DRAW_THRESHOLD = 5.0

# (metric_key, label, is_scored)
# metric_key must match column names produced by _add_rate_cols() or original df.
# is_scored=False means the metric appears in the response but is excluded from
# WAS and metrics_won — used for gc_p90 which is linearly dependent on the others.
COMPARISON_METRICS: list[tuple[str, str, bool]] = [
    ("goals_p90",    "Goals per 90",             True),
    ("assists_p90",  "Assists per 90",            True),
    ("gc_p90",       "Goal Contributions per 90", False),
    ("appearances",  "Appearances",               True),
    ("minutes_share","Minutes Share",             True),
]

# Role-based weakness labels (not from percentile thresholds) are stripped from
# the comparison breakdown to avoid misleading player1_only / player2_only results.
STRUCTURAL_LABELS: frozenset[str] = frozenset({"Defensive contribution"})

_MIN_APPEARANCES = 5
_MIN_MINUTES = 270

_METRIC_PHRASES: dict[str, str] = {
    "goals_p90":    "goal scoring rate",
    "assists_p90":  "creativity",
    "appearances":  "availability",
    "minutes_share":"minutes share",
}


@dataclass
class MetricResult:
    metric: str
    label: str
    is_scored: bool
    player1_value: float
    player1_percentile: float
    player2_value: float
    player2_percentile: float
    winner: str      # "player1" | "player2" | "draw"
    advantage: float # always actual abs diff; not zeroed out for draws


@dataclass
class StrengthWeaknessBreakdown:
    player1_only: list[str]
    player2_only: list[str]
    shared: list[str]


@dataclass
class ComparisonVerdict:
    winner: str
    metrics_won: dict[str, int]        # scored metrics only
    advantage_score: dict[str, float]  # WAS per player; scored metrics only
    summary: str


@dataclass
class PlayerComparison:
    player1_name: str
    player2_name: str
    same_position: bool
    data_warning: str | None
    metrics: list[MetricResult]
    strengths: StrengthWeaknessBreakdown
    weaknesses: StrengthWeaknessBreakdown
    verdict: ComparisonVerdict


def _sample_warning(row: pd.Series) -> str | None:
    apps = int(row.get("appearances", 0))
    mins = int(row.get("minutes_played", 0))
    if apps < _MIN_APPEARANCES or mins < _MIN_MINUTES:
        return (
            f"{row['player_name']} has limited data "
            f"({apps} appearances, {mins} minutes). "
            "Per-90 statistics may not be reliable."
        )
    return None


def _cross_position_warning(
    row_a: pd.Series,
    row_b: pd.Series,
    peer_a_size: int,
    peer_b_size: int,
) -> str:
    pos_a = str(row_a.get("position", ""))
    pos_b = str(row_b.get("position", ""))
    parts: list[str] = []

    if "GK" in (pos_a, pos_b):
        parts.append(
            "Goalkeeping metrics are not in this dataset. "
            "Only appearances and minutes share are meaningful."
        )

    # Identify structurally disadvantaged player.
    # Any player in a position with lower expected attacking output than their
    # opponent (DF/GK vs anyone, or non-FW vs FW) is flagged.
    for disadv_row, adv_row in [(row_a, row_b), (row_b, row_a)]:
        d_pos = str(disadv_row.get("position", ""))
        a_pos = str(adv_row.get("position", ""))
        if d_pos in ("DF", "GK") or (a_pos == "FW" and d_pos != "FW"):
            parts.append(
                f"This comparison crosses positions. "
                f"Attacking metrics structurally favour {adv_row['player_name']} ({a_pos}). "
                f"{disadv_row['player_name']}'s defensive contributions are not captured "
                f"in this dataset."
            )
            break
    else:
        parts.append(f"This comparison crosses positions ({pos_a} vs {pos_b}).")

    parts.append(
        f"Percentiles computed within each player's own position peer group "
        f"({pos_a}: {peer_a_size} players, {pos_b}: {peer_b_size} players)."
    )

    return " ".join(parts)


def _join_phrases(phrases: list[str]) -> str:
    if not phrases:
        return ""
    if len(phrases) == 1:
        return phrases[0]
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


def _verdict_summary(
    row_a: pd.Series,
    row_b: pd.Series,
    same_position: bool,
    metric_results: list[MetricResult],
    winner: str,
    was_a: float,
    was_b: float,
) -> str:
    name_a = str(row_a["player_name"])
    name_b = str(row_b["player_name"])
    pos_a = str(row_a.get("position", ""))
    pos_b = str(row_b.get("position", ""))

    a_won = [_METRIC_PHRASES.get(m.metric, m.label) for m in metric_results
             if m.is_scored and m.winner == "player1"]
    b_won = [_METRIC_PHRASES.get(m.metric, m.label) for m in metric_results
             if m.is_scored and m.winner == "player2"]

    winner_name  = name_a  if winner == "player1" else name_b
    loser_name   = name_b  if winner == "player1" else name_a
    winner_was   = was_a   if winner == "player1" else was_b
    loser_was    = was_b   if winner == "player1" else was_a
    winner_won   = a_won   if winner == "player1" else b_won
    loser_won    = b_won   if winner == "player1" else a_won
    loser_pos    = pos_b   if winner == "player1" else pos_a

    # Both-below-average: winner's best scored percentile is still < 50
    winner_pcts = [
        (m.player1_percentile if winner == "player1" else m.player2_percentile)
        for m in metric_results
        if m.is_scored and m.winner != "draw"
    ]
    below_avg = bool(winner_pcts) and max(winner_pcts) < 50
    below_suffix = (
        " Note: both players score below the position average on the available metrics."
        if below_avg else ""
    )

    if not same_position:
        # Template D — lead with the limitation
        if winner == "draw":
            body = f"{name_a} and {name_b} are evenly matched on available metrics."
        else:
            body = (
                f"On available attacking metrics, {winner_name} leads with a weighted score of "
                f"{winner_was:.1f} vs {loser_was:.1f}, driven by {_join_phrases(winner_won) or 'no scored metric'}. "
                f"{loser_name}'s {loser_pos} contributions are not captured in this dataset."
            )
        return f"This is a cross-position comparison ({pos_a} vs {pos_b}). {body}{below_suffix}"

    if winner == "draw":
        # Template C
        return f"{name_a} and {name_b} are evenly matched across all scored metrics.{below_suffix}"

    was_gap = abs(was_a - was_b)

    if was_gap > 20:
        # Template A — clear winner
        summary = (
            f"{winner_name} holds a clear advantage with a weighted score of "
            f"{winner_was:.1f} vs {loser_was:.1f}, leading on "
            f"{_join_phrases(winner_won) or 'no scored metric'}."
        )
        if loser_won:
            summary += f" {loser_name} holds an advantage only on {_join_phrases(loser_won)}."
    else:
        # Template B — narrow winner
        summary = (
            f"{winner_name} narrowly leads (weighted score {winner_was:.1f} vs {loser_was:.1f}), "
            f"winning on {_join_phrases(winner_won) or 'no scored metric'}."
        )
        if loser_won:
            summary += f" {loser_name} counters with stronger {_join_phrases(loser_won)}."

    return summary + below_suffix


def generate_comparison(
    row_a: pd.Series,
    row_b: pd.Series,
    all_df: pd.DataFrame,
) -> PlayerComparison:
    """Compare two players by position-aware percentile advantage.

    row_a / row_b must be rows from all_df (index labels must be valid iloc positions).
    WAS (Weighted Advantage Score) is the sole winner-determination signal.
    metrics_won is informational only.
    """
    # 1. Sample-size warnings (both players checked; comparison still runs)
    warn_parts: list[str] = []
    for w in (_sample_warning(row_a), _sample_warning(row_b)):
        if w:
            warn_parts.append(w)

    # 2. Enrich full df once; recover rows by their integer index label.
    #    Assumes all_df uses RangeIndex so row.name == iloc position.
    enriched_df = _add_rate_cols(all_df.copy())
    enriched_row_a = enriched_df.iloc[int(row_a.name)]
    enriched_row_b = enriched_df.iloc[int(row_b.name)]

    # 3. Peer groups (position-filtered slices of the enriched df)
    pos_a = str(row_a.get("position", ""))
    pos_b = str(row_b.get("position", ""))
    peer_a = enriched_df[enriched_df["position"] == pos_a]
    peer_b = enriched_df[enriched_df["position"] == pos_b]

    same_position = pos_a == pos_b

    # 4. Position-based data_warning
    if not same_position:
        warn_parts.append(_cross_position_warning(row_a, row_b, len(peer_a), len(peer_b)))
    if "GK" in (pos_a, pos_b) and same_position:
        warn_parts.append(
            "Goalkeeping metrics are not in this dataset. "
            "Only appearances and minutes share are meaningful."
        )

    data_warning = " ".join(warn_parts) if warn_parts else None

    # 5. Per-metric results
    metric_results: list[MetricResult] = []
    for metric_key, label, is_scored in COMPARISON_METRICS:
        val_a = float(enriched_row_a.get(metric_key, 0.0))
        val_b = float(enriched_row_b.get(metric_key, 0.0))
        pct_a = _pct_rank(val_a, peer_a[metric_key])
        pct_b = _pct_rank(val_b, peer_b[metric_key])
        advantage = abs(pct_a - pct_b)
        if advantage < DRAW_THRESHOLD:
            m_winner = "draw"
        elif pct_a > pct_b:
            m_winner = "player1"
        else:
            m_winner = "player2"
        metric_results.append(MetricResult(
            metric=metric_key,
            label=label,
            is_scored=is_scored,
            player1_value=round(val_a, 3),
            player1_percentile=round(pct_a, 1),
            player2_value=round(val_b, 3),
            player2_percentile=round(pct_b, 1),
            winner=m_winner,
            advantage=round(advantage, 1),
        ))

    # 6. WAS — scored metrics only; winner determined solely by WAS
    was_a = was_b = 0.0
    won_a = won_b = draw_count = 0
    for m in metric_results:
        if not m.is_scored:
            continue
        if m.winner == "player1":
            was_a += m.advantage
            won_a += 1
        elif m.winner == "player2":
            was_b += m.advantage
            won_b += 1
        else:
            draw_count += 1

    if was_a > was_b:
        verdict_winner = "player1"
    elif was_b > was_a:
        verdict_winner = "player2"
    else:
        verdict_winner = "draw"

    # 7. Strengths / weaknesses with structural labels filtered
    pct_dict_a = _percentiles(enriched_row_a, peer_a)
    pct_dict_b = _percentiles(enriched_row_b, peer_b)

    set_s_a = set(_strengths(enriched_row_a, pct_dict_a)) - STRUCTURAL_LABELS
    set_s_b = set(_strengths(enriched_row_b, pct_dict_b)) - STRUCTURAL_LABELS
    set_w_a = set(_weaknesses(enriched_row_a, pct_dict_a)) - STRUCTURAL_LABELS
    set_w_b = set(_weaknesses(enriched_row_b, pct_dict_b)) - STRUCTURAL_LABELS

    strengths = StrengthWeaknessBreakdown(
        player1_only=sorted(set_s_a - set_s_b),
        player2_only=sorted(set_s_b - set_s_a),
        shared=sorted(set_s_a & set_s_b),
    )
    weaknesses = StrengthWeaknessBreakdown(
        player1_only=sorted(set_w_a - set_w_b),
        player2_only=sorted(set_w_b - set_w_a),
        shared=sorted(set_w_a & set_w_b),
    )

    # 8. Verdict summary
    summary = _verdict_summary(
        row_a, row_b, same_position, metric_results,
        verdict_winner, was_a, was_b,
    )

    verdict = ComparisonVerdict(
        winner=verdict_winner,
        metrics_won={"player1": won_a, "player2": won_b, "draw": draw_count},
        advantage_score={"player1": round(was_a, 1), "player2": round(was_b, 1)},
        summary=summary,
    )

    return PlayerComparison(
        player1_name=str(row_a["player_name"]),
        player2_name=str(row_b["player_name"]),
        same_position=same_position,
        data_warning=data_warning,
        metrics=metric_results,
        strengths=strengths,
        weaknesses=weaknesses,
        verdict=verdict,
    )
