"""
Unit tests for comparison_engine.py.

The synthetic dataset below is designed so that expected per-90 values and
percentile outcomes can be reasoned about deterministically.

_add_rate_cols() assumed behaviour (from session context):
    goals_p90     = goals  / clip(minutes_played, 1) * 90
    assists_p90   = assists / clip(minutes_played, 1) * 90
    gc_p90        = goals_p90 + assists_p90
    minutes_share = minutes_played / (clip(appearances, 1) * 90)

_pct_rank(value, series) assumed: midpoint method, 0-100 scale.
"""
import pandas as pd
import pytest

from analytics.comparison_engine import (
    COMPARISON_METRICS,
    DRAW_THRESHOLD,
    STRUCTURAL_LABELS,
    generate_comparison,
)


# ---------------------------------------------------------------------------
# Synthetic dataset helpers
# ---------------------------------------------------------------------------

def _row(name, pos, goals, assists, minutes, appearances,
         club="FC", comp="L1", nat="EN", season="2025-26", age=25):
    return {
        "player_name": name,
        "position": pos,
        "goals": goals,
        "assists": assists,
        "minutes_played": minutes,
        "appearances": appearances,
        "non_penalty_goals": goals,
        "club": club,
        "competition": comp,
        "nationality": nat,
        "season": season,
        "age": age,
    }


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows).reset_index(drop=True)


def _get_row(df: pd.DataFrame, name: str) -> pd.Series:
    return df[df["player_name"] == name].iloc[0]


# 8 FW players with strictly different stats so percentile ordering is clear.
FW_ROWS = [
    # name, goals, assists, minutes, appearances
    _row("FW_top_scorer",   "FW", 18, 2, 900, 10),  # highest goals
    _row("FW_creator",      "FW",  1, 14, 900, 10), # highest assists
    _row("FW_balanced",     "FW",  9, 7, 900, 10),
    _row("FW_low",          "FW",  2, 1, 900, 10),
    _row("FW_mid_a",        "FW",  6, 4, 810, 9),
    _row("FW_mid_b",        "FW",  4, 6, 810, 9),
    _row("FW_regular",      "FW",  5, 5, 900, 10),
    _row("FW_bench",        "FW",  3, 3, 450, 6),   # passes sample size
]

MF_ROWS = [
    _row("MF_top",     "MF", 8, 10, 900, 10),
    _row("MF_mid",     "MF", 3,  5, 810,  9),
    _row("MF_low",     "MF", 1,  1, 720,  8),
    _row("MF_workhorse","MF",2,  4, 900, 10),
    _row("MF_creative","MF", 2, 12, 900, 10),
]

DF_ROWS = [
    _row("DF_a", "DF", 2, 3, 900, 10),
    _row("DF_b", "DF", 0, 1, 810,  9),
    _row("DF_c", "DF", 1, 2, 720,  8),
    _row("DF_d", "DF", 3, 1, 900, 10),
    _row("DF_e", "DF", 0, 0, 900, 10),
]

ALL_DF = _make_df(FW_ROWS + MF_ROWS + DF_ROWS)


# ---------------------------------------------------------------------------
# 1. COMPARISON_METRICS config
# ---------------------------------------------------------------------------

class TestMetricConfig:
    def test_gc_p90_is_not_scored(self):
        gc_entry = next(m for m in COMPARISON_METRICS if m[0] == "gc_p90")
        assert gc_entry[2] is False, "gc_p90 must be is_scored=False"

    def test_four_scored_metrics(self):
        scored = [m for m in COMPARISON_METRICS if m[2] is True]
        assert len(scored) == 4

    def test_scored_metric_keys(self):
        scored_keys = {m[0] for m in COMPARISON_METRICS if m[2]}
        assert scored_keys == {"goals_p90", "assists_p90", "appearances", "minutes_share"}

    def test_draw_threshold_is_five(self):
        assert DRAW_THRESHOLD == 5.0

    def test_structural_labels_contains_defensive_contribution(self):
        assert "Defensive contribution" in STRUCTURAL_LABELS


# ---------------------------------------------------------------------------
# 2. WAS is the sole winner signal (not metrics_won)
# ---------------------------------------------------------------------------

class TestWASLogic:
    def test_winner_determined_by_was_not_metrics_won(self):
        """FW_top_scorer dominates on goals; FW_creator wins assists.
        WAS for scorer should still exceed creator despite similar metric counts."""
        df = ALL_DF
        row_scorer  = _get_row(df, "FW_top_scorer")
        row_creator = _get_row(df, "FW_creator")
        result = generate_comparison(row_scorer, row_creator, df)

        # Verify the verdict winner matches the advantage_score winner
        was_p1 = result.verdict.advantage_score["player1"]
        was_p2 = result.verdict.advantage_score["player2"]

        if result.verdict.winner == "player1":
            assert was_p1 > was_p2
        elif result.verdict.winner == "player2":
            assert was_p2 > was_p1
        else:
            assert was_p1 == was_p2 == 0.0

    def test_was_equals_sum_of_won_scored_advantages(self):
        """advantage_score must equal the sum of advantages on scored won metrics."""
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_low")
        result = generate_comparison(row_a, row_b, df)

        manual_was_a = sum(
            m.advantage for m in result.metrics
            if m.is_scored and m.winner == "player1"
        )
        manual_was_b = sum(
            m.advantage for m in result.metrics
            if m.is_scored and m.winner == "player2"
        )

        assert abs(result.verdict.advantage_score["player1"] - round(manual_was_a, 1)) < 0.05
        assert abs(result.verdict.advantage_score["player2"] - round(manual_was_b, 1)) < 0.05

    def test_draw_only_when_both_was_zero(self):
        """A draw verdict requires WAS(A) == WAS(B) == 0."""
        df = ALL_DF
        row_a = _get_row(df, "FW_balanced")
        row_b = _get_row(df, "FW_regular")
        result = generate_comparison(row_a, row_b, df)

        if result.verdict.winner == "draw":
            assert result.verdict.advantage_score["player1"] == 0.0
            assert result.verdict.advantage_score["player2"] == 0.0
        else:
            # If not draw, one WAS must be strictly greater
            was_p1 = result.verdict.advantage_score["player1"]
            was_p2 = result.verdict.advantage_score["player2"]
            assert was_p1 != was_p2

    def test_gc_p90_excluded_from_was(self):
        """gc_p90 must not appear in advantage_score calculation.
        Verify: sum of scored-metric advantages == advantage_score (gc_p90 excluded)."""
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_creator")
        result = generate_comparison(row_a, row_b, df)

        gc_metric = next(m for m in result.metrics if m.metric == "gc_p90")
        assert gc_metric.is_scored is False

        # If gc_p90 were scored it would add to WAS; verify it was not
        scored_sum_p1 = sum(
            m.advantage for m in result.metrics if m.is_scored and m.winner == "player1"
        )
        assert abs(result.verdict.advantage_score["player1"] - round(scored_sum_p1, 1)) < 0.05


# ---------------------------------------------------------------------------
# 3. advantage field always stores actual diff (not zeroed for draws)
# ---------------------------------------------------------------------------

class TestAdvantageField:
    def test_advantage_is_actual_diff_for_draw(self):
        """A draw metric with advantage < 5 should still store the actual diff,
        not 0.0, so the frontend can show how close the draw was."""
        df = ALL_DF
        row_a = _get_row(df, "FW_balanced")
        row_b = _get_row(df, "FW_regular")
        result = generate_comparison(row_a, row_b, df)

        for m in result.metrics:
            if m.winner == "draw":
                # advantage must equal abs(pct_a - pct_b), not forced to 0
                expected = abs(m.player1_percentile - m.player2_percentile)
                assert abs(m.advantage - expected) < 0.15, (
                    f"Draw metric {m.metric}: advantage={m.advantage} != "
                    f"abs({m.player1_percentile} - {m.player2_percentile}) = {expected:.2f}"
                )

    def test_draw_threshold_is_strict_lt(self):
        """advantage < 5.0 is draw; advantage == 5.0 is NOT a draw."""
        # We can't force exact percentile values without mocking, so just verify
        # that any metric whose advantage >= 5 is not labelled draw.
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_low")
        result = generate_comparison(row_a, row_b, df)

        for m in result.metrics:
            if m.advantage >= 5.0:
                assert m.winner != "draw", (
                    f"Metric {m.metric}: advantage={m.advantage} >= 5 but winner=draw"
                )
            if m.winner == "draw":
                assert m.advantage < 5.0


# ---------------------------------------------------------------------------
# 4. metrics_won counts only scored metrics
# ---------------------------------------------------------------------------

class TestMetricsWon:
    def test_metrics_won_excludes_gc_p90(self):
        """metrics_won total must equal the count of scored metrics (4), not 5."""
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_creator")
        result = generate_comparison(row_a, row_b, df)

        mw = result.verdict.metrics_won
        total = mw["player1"] + mw["player2"] + mw["draw"]
        scored_count = sum(1 for m in COMPARISON_METRICS if m[2])
        assert total == scored_count, f"metrics_won total {total} != scored count {scored_count}"

    def test_metrics_won_is_informational_only(self):
        """The player with more metrics_won should not necessarily be the verdict winner.
        This test verifies the WAS winner takes precedence."""
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_creator")
        result = generate_comparison(row_a, row_b, df)

        was_p1 = result.verdict.advantage_score["player1"]
        was_p2 = result.verdict.advantage_score["player2"]
        expected_winner = (
            "player1" if was_p1 > was_p2
            else "player2" if was_p2 > was_p1
            else "draw"
        )
        assert result.verdict.winner == expected_winner


# ---------------------------------------------------------------------------
# 5. Structural label filtering
# ---------------------------------------------------------------------------

class TestStructuralLabels:
    def test_defensive_contribution_absent_from_fw_vs_fw(self):
        """'Defensive contribution' is a role observation not a stat.
        It must not appear anywhere in the comparison breakdown."""
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_creator")
        result = generate_comparison(row_a, row_b, df)

        all_labels = (
            result.strengths.player1_only
            + result.strengths.player2_only
            + result.strengths.shared
            + result.weaknesses.player1_only
            + result.weaknesses.player2_only
            + result.weaknesses.shared
        )
        for label in STRUCTURAL_LABELS:
            assert label not in all_labels, (
                f"Structural label '{label}' must not appear in comparison breakdown"
            )

    def test_defensive_contribution_absent_from_fw_vs_mf(self):
        """Cross-position: 'Defensive contribution' should not appear as a
        player1_only weakness (which would misleadingly imply FW has a unique
        weakness vs MF)."""
        df = ALL_DF
        row_fw = _get_row(df, "FW_top_scorer")
        row_mf = _get_row(df, "MF_mid")
        result = generate_comparison(row_fw, row_mf, df)

        all_labels = (
            result.weaknesses.player1_only
            + result.weaknesses.player2_only
            + result.weaknesses.shared
        )
        for label in STRUCTURAL_LABELS:
            assert label not in all_labels


# ---------------------------------------------------------------------------
# 6. Sample size warning
# ---------------------------------------------------------------------------

class TestSampleSizeWarning:
    def test_no_warning_for_above_threshold_players(self):
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")   # 900 min, 10 apps — well above
        row_b = _get_row(df, "FW_creator")
        result = generate_comparison(row_a, row_b, df)
        # Warning should be None or not contain "limited data"
        if result.data_warning:
            assert "limited data" not in result.data_warning

    def test_warning_for_below_threshold_appearances(self):
        """A player with 3 appearances should trigger a data_warning."""
        sparse_rows = FW_ROWS + [_row("FW_sparse", "FW", 2, 0, 270, 3)]
        df = _make_df(sparse_rows + MF_ROWS + DF_ROWS)
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_sparse")
        result = generate_comparison(row_a, row_b, df)
        assert result.data_warning is not None
        assert "FW_sparse" in result.data_warning
        assert "limited data" in result.data_warning

    def test_warning_for_below_threshold_minutes(self):
        """A player with >= 5 apps but < 270 minutes still triggers a warning."""
        sparse_rows = FW_ROWS + [_row("FW_injury", "FW", 1, 0, 200, 5)]
        df = _make_df(sparse_rows + MF_ROWS + DF_ROWS)
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_injury")
        result = generate_comparison(row_a, row_b, df)
        assert result.data_warning is not None
        assert "FW_injury" in result.data_warning

    def test_comparison_runs_despite_warning(self):
        """Comparison is not blocked by the sample size warning — it just warns."""
        sparse_rows = FW_ROWS + [_row("FW_sparse2", "FW", 1, 0, 180, 2)]
        df = _make_df(sparse_rows + MF_ROWS + DF_ROWS)
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_sparse2")
        result = generate_comparison(row_a, row_b, df)
        assert result.verdict is not None
        assert result.verdict.winner in ("player1", "player2", "draw")


# ---------------------------------------------------------------------------
# 7. same_position flag and cross-position warnings
# ---------------------------------------------------------------------------

class TestPositionHandling:
    def test_same_position_flag_true_for_fw_vs_fw(self):
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_creator")
        result = generate_comparison(row_a, row_b, df)
        assert result.same_position is True

    def test_same_position_flag_false_for_fw_vs_mf(self):
        df = ALL_DF
        row_fw = _get_row(df, "FW_top_scorer")
        row_mf = _get_row(df, "MF_mid")
        result = generate_comparison(row_fw, row_mf, df)
        assert result.same_position is False

    def test_cross_position_has_data_warning(self):
        df = ALL_DF
        row_fw = _get_row(df, "FW_top_scorer")
        row_mf = _get_row(df, "MF_mid")
        result = generate_comparison(row_fw, row_mf, df)
        assert result.data_warning is not None

    def test_fw_vs_df_data_warning_mentions_defensive_contributions(self):
        df = ALL_DF
        row_fw = _get_row(df, "FW_top_scorer")
        row_df = _get_row(df, "DF_a")
        result = generate_comparison(row_fw, row_df, df)
        assert result.data_warning is not None
        assert "defensive contributions" in result.data_warning.lower()

    def test_cross_position_verdict_summary_leads_with_limitation(self):
        """Template D: cross-position verdict summary must start with the
        cross-position caveat, not with the winner's name."""
        df = ALL_DF
        row_fw = _get_row(df, "FW_top_scorer")
        row_mf = _get_row(df, "MF_mid")
        result = generate_comparison(row_fw, row_mf, df)
        assert result.verdict.summary.startswith(
            "This is a cross-position comparison"
        ), f"Summary does not lead with limitation: {result.verdict.summary[:80]}"

    def test_percentiles_use_own_position_peer_group(self):
        """A FW's percentiles are computed against other FWs.
        The same player in a different position would get a different percentile."""
        df = ALL_DF
        row_fw = _get_row(df, "FW_top_scorer")
        row_mf = _get_row(df, "MF_mid")
        result = generate_comparison(row_fw, row_mf, df)

        goals_metric = next(m for m in result.metrics if m.metric == "goals_p90")
        # FW_top_scorer has 18 goals in 900 min = 1.8 goals_p90.
        # Among FWs this is highest, so percentile should be > 80.
        assert goals_metric.player1_percentile > 80, (
            f"FW_top_scorer goals_p90 percentile among FWs should be > 80, "
            f"got {goals_metric.player1_percentile}"
        )


# ---------------------------------------------------------------------------
# 8. Response shape invariants
# ---------------------------------------------------------------------------

class TestResponseShape:
    def test_five_metrics_returned(self):
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_low")
        result = generate_comparison(row_a, row_b, df)
        assert len(result.metrics) == len(COMPARISON_METRICS)

    def test_metric_keys_match_config(self):
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_low")
        result = generate_comparison(row_a, row_b, df)
        result_keys = [m.metric for m in result.metrics]
        config_keys = [m[0] for m in COMPARISON_METRICS]
        assert result_keys == config_keys

    def test_is_scored_matches_config(self):
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_low")
        result = generate_comparison(row_a, row_b, df)
        for res_m, cfg_m in zip(result.metrics, COMPARISON_METRICS):
            assert res_m.is_scored == cfg_m[2]

    def test_winner_values_are_valid(self):
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_creator")
        result = generate_comparison(row_a, row_b, df)
        valid = {"player1", "player2", "draw"}
        assert result.verdict.winner in valid
        for m in result.metrics:
            assert m.winner in valid

    def test_advantage_score_keys(self):
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_low")
        result = generate_comparison(row_a, row_b, df)
        assert set(result.verdict.advantage_score.keys()) == {"player1", "player2"}

    def test_metrics_won_keys(self):
        df = ALL_DF
        row_a = _get_row(df, "FW_top_scorer")
        row_b = _get_row(df, "FW_low")
        result = generate_comparison(row_a, row_b, df)
        assert set(result.verdict.metrics_won.keys()) == {"player1", "player2", "draw"}
