import pytest
from transaction_analysis.scoring import (
    normalize_score,
    preliminary_candidate_score,
    final_candidate_score,
    score_from_signal,
)


def test_normalize_score_clamps():
    assert normalize_score(150, 0, 100) == 1.0
    assert normalize_score(-10, 0, 100) == 0.0
    assert normalize_score(50, 0, 100) == pytest.approx(0.5)


def test_normalize_score_none():
    assert normalize_score(None) == 0.0


def test_normalize_score_zero_span():
    assert normalize_score(5, 5, 5) == 0.0


def test_preliminary_candidate_score_weights():
    score = preliminary_candidate_score(
        sector_momentum=1.0,
        market_attention=1.0,
        foreign_flow=1.0,
        news_theme_alignment=1.0,
        liquidity=1.0,
        corporate_action=1.0,
    )
    assert score == pytest.approx(0.25 + 0.20 + 0.20 + 0.15 + 0.10 + 0.10)


def test_preliminary_candidate_score_zeros():
    assert preliminary_candidate_score() == pytest.approx(0.0)


def test_final_candidate_score_weights():
    score = final_candidate_score(
        sector_rotation=1.0,
        news_macro_alignment=1.0,
        market_mover=1.0,
        smart_money=1.0,
        bandar_accumulation=1.0,
        technical_confirmation=1.0,
        risk_reward=1.0,
    )
    assert score == pytest.approx(0.20 + 0.15 + 0.15 + 0.20 + 0.15 + 0.10 + 0.05)


def test_score_from_signal_known():
    assert score_from_signal("STRONG_BUY") == 1.0
    assert score_from_signal("STRONG_SELL") == 0.0
    assert score_from_signal("BUY") == 0.75
    assert score_from_signal("ACCUMULATING") == 0.85


def test_score_from_signal_unknown_defaults_neutral():
    assert score_from_signal("UNKNOWN_SIGNAL") == 0.5


def test_score_from_signal_none():
    assert score_from_signal(None) == 0.5
