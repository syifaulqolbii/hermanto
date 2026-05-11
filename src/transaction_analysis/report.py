from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Any

from .models import (
    MarketContext, SectorScore, StockCandidate,
    StockTransactionAnalysis, NewsItem,
)
from .storage import Storage
from .config import Config


def render_report(
    date: str,
    news_items: list[NewsItem],
    market_ctx: MarketContext,
    sector_scores: list[SectorScore],
    candidates: list[StockCandidate],
    ta_map: dict[str, StockTransactionAnalysis],
    request_usage: dict[str, int],
    config: Config,
) -> str:
    lines: list[str] = []

    lines.append(f"# Daily Transaction Analysis Report — {date}")
    lines.append(f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")

    # --- Market Context ---
    lines.append("## Market Context")
    lines.append(f"- **Global Sentiment:** {market_ctx.global_sentiment}")
    if market_ctx.commodity_bias:
        lines.append(f"- **Commodity:** {market_ctx.commodity_bias}")
    if market_ctx.forex_bias:
        lines.append(f"- **Forex (USD/IDR):** {market_ctx.forex_bias}")
    if market_ctx.indices_bias:
        lines.append(f"- **Indices:** {market_ctx.indices_bias}")
    lines.append("")

    # --- News Headlines ---
    if news_items:
        lines.append("## News Headlines")
        for item in news_items[:6]:
            lines.append(f"- [{item.title}]({item.url}) _{item.source}_")
        lines.append("")

    # --- Sector Rotation ---
    lines.append("## Sector Rotation")
    if sector_scores:
        hot = [s for s in sector_scores if s.status.upper() in ("LEADING", "IMPROVING")]
        cold = [s for s in sector_scores if s.status.upper() in ("WEAKENING", "LAGGING")]
        if hot:
            lines.append(f"- **Hot sectors:** {', '.join(s.sector for s in hot[:3])}")
        if cold:
            lines.append(f"- **Cold sectors:** {', '.join(s.sector for s in cold[:3])}")
        lines.append("")
        lines.append("| Sector | Status | Score | Recommendation |")
        lines.append("|--------|--------|-------|----------------|")
        for s in sector_scores[:8]:
            lines.append(f"| {s.sector} | {s.status} | {s.final_score:.2f} | {s.recommendation} |")
    else:
        lines.append("_No sector data available._")
    lines.append("")

    # --- Top Candidates ---
    lines.append("## Top Candidates")
    if candidates:
        lines.append("| # | Symbol | Sector | Pre Score | Final Score | Reason |")
        lines.append("|---|--------|--------|-----------|-------------|--------|")
        for i, c in enumerate(candidates[:5], 1):
            lines.append(
                f"| {i} | **{c.symbol}** | {c.sector} | {c.pre_score:.2f} | {c.final_score:.2f} | {c.candidate_reason} |"
            )
    else:
        lines.append("_No candidates identified today._")
    lines.append("")

    # --- Smart Money / Bandar Summary ---
    if ta_map:
        lines.append("## Smart Money & Bandar Analysis")
        for sym, ta in ta_map.items():
            lines.append(f"### {sym}")
            if ta.smart_money_summary:
                lines.append(f"- **Smart Money:** {ta.smart_money_summary}")
            if ta.bandar_accumulation_summary:
                lines.append(f"- **Bandar Accumulation:** {ta.bandar_accumulation_summary}")
            if ta.bandar_distribution_summary:
                lines.append(f"- **Bandar Distribution:** {ta.bandar_distribution_summary}")
            if ta.retail_bandar_sentiment:
                lines.append(f"- **Retail vs Bandar:** {ta.retail_bandar_sentiment}")
            if ta.whale_summary:
                lines.append(f"- **Whale Activity:** {ta.whale_summary}")
            if ta.pump_dump_risk:
                lines.append(f"- **Pump & Dump Risk:** {ta.pump_dump_risk}")
        lines.append("")

    # --- Trading Thesis for Final Candidate ---
    if candidates:
        top = candidates[0]
        lines.append("## Trading Thesis")
        lines.append(f"**Top Candidate: {top.symbol}**")
        lines.append("")
        lines.append("**Why:**")
        if top.candidate_reason:
            for r in top.candidate_reason.split(","):
                lines.append(f"- {r.strip()}")
        if top.smart_money_score > 0.6:
            lines.append("- Smart money / bandar signal positive")
        if top.technical_score > 0.6:
            lines.append("- Technical structure acceptable")
        if top.risk_reward_score > 0.4:
            lines.append("- Risk-reward acceptable")
        lines.append("")
        if top.entry_price or top.stop_loss or top.take_profit_1:
            lines.append("**Trade Plan:**")
            if top.entry_zone_low and top.entry_zone_high:
                lines.append(f"- **Entry Zone:** {top.entry_zone_low:,.0f} – {top.entry_zone_high:,.0f}")
            elif top.entry_price:
                lines.append(f"- **Entry Reference:** {top.entry_price:,.0f}")
            if top.stop_loss:
                lines.append(f"- **Stop Loss:** {top.stop_loss:,.0f}")
            if top.take_profit_1:
                lines.append(f"- **Take Profit 1:** {top.take_profit_1:,.0f}")
            if top.take_profit_2 and top.take_profit_2 != top.take_profit_1:
                lines.append(f"- **Take Profit 2:** {top.take_profit_2:,.0f}")
            if top.trade_risk_reward_ratio:
                lines.append(f"- **Risk/Reward:** {top.trade_risk_reward_ratio:.2f}R")
            if top.position_size_lots:
                lines.append(f"- **Position Size:** {top.position_size_lots:,.0f} lots")
            if top.trade_plan_summary:
                lines.append(f"- **Execution:** {top.trade_plan_summary}")
            lines.append("")

        lines.append("**Risk:**")
        ta = ta_map.get(top.symbol)
        if ta and ta.pump_dump_risk and ta.pump_dump_risk.upper() not in ("LOW", ""):
            lines.append(f"- Pump & dump risk: {ta.pump_dump_risk}")
        lines.append("- Avoid chasing if already extended")
        if top.stop_loss:
            lines.append(f"- Invalid if price breaks below {top.stop_loss:,.0f} with high volume")
        else:
            lines.append("- Invalid if support breaks with high volume")
        lines.append("")
        lines.append("**Action Style:** Watchlist / wait pullback / breakout confirmation")
        lines.append("")

    # --- Request Usage Summary ---
    lines.append("## Request Usage Summary")
    lines.append(f"| Provider | Used Today | Daily Budget | Mode |")
    lines.append(f"|----------|-----------|--------------|------|")
    idx_used = request_usage.get("RapidAPI_IDX", 0)
    news_used = request_usage.get("RapidAPI_News", 0)
    lines.append(f"| RapidAPI_IDX | {idx_used} | {config.daily_idx_budget} | {config.budget_mode} |")
    lines.append(f"| RapidAPI_News | {news_used} | {config.daily_news_budget} | {config.budget_mode} |")
    lines.append("")

    return "\n".join(lines)


def save_report(content: str, date: str, config: Config) -> str:
    os.makedirs(config.reports_dir, exist_ok=True)
    path = os.path.join(config.reports_dir, f"{date}-daily-report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
