from __future__ import annotations
from typing import Optional


def normalize_score(value: Optional[float], lo: float = 0.0, hi: float = 100.0) -> float:
    """Clamp and normalize a raw score to [0, 1]."""
    if value is None:
        return 0.0
    span = hi - lo
    if span == 0:
        return 0.0
    return max(0.0, min(1.0, (value - lo) / span))


def preliminary_candidate_score(
    sector_momentum: float = 0.0,
    market_attention: float = 0.0,
    foreign_flow: float = 0.0,
    news_theme_alignment: float = 0.0,
    liquidity: float = 0.0,
    corporate_action: float = 0.0,
) -> float:
    """Weighted preliminary score from plan section Step 6.

    All inputs expected in [0, 1].
    """
    return (
        0.25 * sector_momentum
        + 0.20 * market_attention
        + 0.20 * foreign_flow
        + 0.15 * news_theme_alignment
        + 0.10 * liquidity
        + 0.10 * corporate_action
    )


def final_candidate_score(
    sector_rotation: float = 0.0,
    news_macro_alignment: float = 0.0,
    market_mover: float = 0.0,
    smart_money: float = 0.0,
    bandar_accumulation: float = 0.0,
    technical_confirmation: float = 0.0,
    risk_reward: float = 0.0,
) -> float:
    """Weighted final score from plan section Step 8.

    All inputs expected in [0, 1].
    """
    return (
        0.20 * sector_rotation
        + 0.15 * news_macro_alignment
        + 0.15 * market_mover
        + 0.20 * smart_money
        + 0.15 * bandar_accumulation
        + 0.10 * technical_confirmation
        + 0.05 * risk_reward
    )


def score_from_signal(signal: Optional[str]) -> float:
    """Convert a text signal label to a [0,1] score."""
    mapping = {
        "STRONG_BUY": 1.0,
        "BUY": 0.75,
        "NEUTRAL": 0.5,
        "SELL": 0.25,
        "STRONG_SELL": 0.0,
        "ACCUMULATING": 0.85,
        "DISTRIBUTING": 0.15,
        "LEADING": 1.0,
        "IMPROVING": 0.75,
        "WEAKENING": 0.35,
        "LAGGING": 0.1,
        "OVERWEIGHT": 0.85,
        "UNDERWEIGHT": 0.2,
        "NEUTRAL_SECTOR": 0.5,
    }
    if signal is None:
        return 0.5
    return mapping.get(signal.upper().replace(" ", "_"), 0.5)
