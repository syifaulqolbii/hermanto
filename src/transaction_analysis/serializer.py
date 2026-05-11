from __future__ import annotations
from dataclasses import asdict
from typing import Any

from .models import MarketContext, SectorScore, StockCandidate, StockTransactionAnalysis, NewsItem


def trade_plan_from_candidate(candidate: StockCandidate) -> dict[str, Any]:
    return {
        "symbol": candidate.symbol,
        "sector": candidate.sector,
        "entry_price": candidate.entry_price,
        "entry_zone_low": candidate.entry_zone_low,
        "entry_zone_high": candidate.entry_zone_high,
        "stop_loss": candidate.stop_loss,
        "take_profit_1": candidate.take_profit_1,
        "take_profit_2": candidate.take_profit_2,
        "risk_reward_ratio": candidate.trade_risk_reward_ratio,
        "position_size_lots": candidate.position_size_lots,
        "execution": candidate.trade_plan_summary,
        "final_score": candidate.final_score,
        "candidate_reason": candidate.candidate_reason,
    }


def pipeline_result_to_dict(
    *,
    date: str,
    news_items: list[NewsItem],
    market_context: MarketContext,
    sector_scores: list[SectorScore],
    candidates: list[StockCandidate],
    transaction_analysis: dict[str, StockTransactionAnalysis],
    request_usage: dict[str, int],
    report_path: str | None = None,
) -> dict[str, Any]:
    top = candidates[0] if candidates else None
    return {
        "date": date,
        "report_path": report_path,
        "market_context": asdict(market_context),
        "news_headlines": [asdict(item) for item in news_items[:10]],
        "sector_rotation": [asdict(sector) for sector in sector_scores],
        "top_candidates": [asdict(candidate) for candidate in candidates],
        "top_trade_plan": trade_plan_from_candidate(top) if top else None,
        "transaction_analysis": {
            symbol: asdict(analysis)
            for symbol, analysis in transaction_analysis.items()
        },
        "request_usage": request_usage,
    }


def find_trade_plan(candidates: list[StockCandidate], symbol: str | None = None) -> dict[str, Any] | None:
    if not candidates:
        return None
    if symbol:
        wanted = symbol.upper()
        match = next((candidate for candidate in candidates if candidate.symbol.upper() == wanted), None)
        if not match:
            return None
        return trade_plan_from_candidate(match)
    return trade_plan_from_candidate(candidates[0])
