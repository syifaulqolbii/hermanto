from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NewsItem:
    source: str
    title: str
    published_at: str
    url: str
    summary: str = ""
    sentiment_score: float = 0.0
    themes: list[str] = field(default_factory=list)


@dataclass
class MarketContext:
    analysis_date: str
    global_sentiment: str = "neutral"   # risk-on | neutral | risk-off
    commodity_bias: str = ""
    forex_bias: str = ""
    indices_bias: str = ""
    summary: str = ""


@dataclass
class SectorScore:
    analysis_date: str
    sector: str
    sector_id: str = ""
    momentum_score: float = 0.0
    status: str = ""            # leading | improving | weakening | lagging
    foreign_flow: float = 0.0
    avg_return_today: float = 0.0
    recommendation: str = ""    # overweight | underweight | neutral
    final_score: float = 0.0
    reason: str = ""


@dataclass
class MarketMover:
    analysis_date: str
    mover_type: str
    symbol: str
    name: str = ""
    price: float = 0.0
    change_percent: float = 0.0
    value: float = 0.0
    rank: int = 0


@dataclass
class StockCandidate:
    analysis_date: str
    symbol: str
    sector: str = ""
    theme: str = ""
    candidate_reason: str = ""
    pre_score: float = 0.0
    technical_score: float = 0.0
    smart_money_score: float = 0.0
    bandar_score: float = 0.0
    risk_reward_score: float = 0.0
    entry_price: float = 0.0
    entry_zone_low: float = 0.0
    entry_zone_high: float = 0.0
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    trade_risk_reward_ratio: float = 0.0
    position_size_lots: float = 0.0
    trade_plan_summary: str = ""
    final_score: float = 0.0
    status: str = "candidate"   # candidate | shortlisted | final | rejected


@dataclass
class StockTransactionAnalysis:
    analysis_date: str
    symbol: str
    smart_money_summary: str = ""
    bandar_accumulation_summary: str = ""
    bandar_distribution_summary: str = ""
    retail_bandar_sentiment: str = ""
    whale_summary: str = ""
    broker_summary: str = ""
    pump_dump_risk: str = ""


@dataclass
class AnalysisReport:
    analysis_date: str
    report_type: str = "daily"
    summary: str = ""
    recommendations: str = ""
    risks: str = ""
    request_usage_summary: str = ""
