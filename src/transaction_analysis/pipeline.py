from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Optional

from .config import Config
from .data_client import DataClient, PROVIDER_IDX, PROVIDER_NEWS
from .models import (
    MarketContext, SectorScore, MarketMover, StockCandidate,
    StockTransactionAnalysis, NewsItem,
)
from .scoring import (
    normalize_score, preliminary_candidate_score, final_candidate_score,
    score_from_signal,
)
from .storage import Storage


class Pipeline:
    def __init__(self, config: Config, storage: Storage, client: DataClient,
                 analysis_date: Optional[str] = None):
        self.config = config
        self.storage = storage
        self.client = client
        self.date = analysis_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # ------------------------------------------------------------------ #
    # Step 2 — News Sentiment
    # ------------------------------------------------------------------ #

    def fetch_news(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        sources = self.config.news_sources[: self.config.daily_news_budget]
        for source in sources:
            raw = self.client.fetch(
                PROVIDER_NEWS, "rss",
                params={"source": source, "limit": 25},
                analysis_date=self.date,
            )
            if not raw:
                continue
            articles = raw if isinstance(raw, list) else raw.get("articles", raw.get("items", []))
            for a in articles[:10]:
                items.append(NewsItem(
                    source=source,
                    title=a.get("title", ""),
                    published_at=a.get("pubDate", a.get("published_at", "")),
                    url=a.get("link", a.get("url", "")),
                    summary=a.get("description", a.get("summary", "")),
                ))
        return items

    def _news_sentiment(self, items: list[NewsItem]) -> str:
        """Very simple keyword-based sentiment from headlines."""
        risk_off_kw = ["recession", "crash", "selloff", "tariff", "war", "inflation spike",
                       "rate hike", "default", "crisis", "downturn"]
        risk_on_kw = ["rally", "surge", "record high", "rate cut", "stimulus", "growth",
                      "beat expectations", "strong jobs", "recovery"]
        text = " ".join(i.title.lower() for i in items)
        off = sum(1 for k in risk_off_kw if k in text)
        on = sum(1 for k in risk_on_kw if k in text)
        if off > on + 1:
            return "risk-off"
        if on > off + 1:
            return "risk-on"
        return "neutral"

    # ------------------------------------------------------------------ #
    # Step 3 — Global & Macro Context
    # ------------------------------------------------------------------ #

    def fetch_market_context(self, news_items: list[NewsItem]) -> MarketContext:
        ctx = MarketContext(analysis_date=self.date)

        overview = self.client.fetch(PROVIDER_IDX, "getGlobalMarketOverview", {}, analysis_date=self.date)
        commodities = self.client.fetch(PROVIDER_IDX, "getCommoditiesImpact", {}, analysis_date=self.date)
        forex = self.client.fetch(PROVIDER_IDX, "getForexIdrImpact", {}, analysis_date=self.date)
        indices = self.client.fetch(PROVIDER_IDX, "getIndicesImpact", {}, analysis_date=self.date)

        ctx.global_sentiment = self._news_sentiment(news_items)

        if commodities:
            ctx.commodity_bias = str(commodities.get("summary", commodities.get("bias", "")))
        if forex:
            ctx.forex_bias = str(forex.get("summary", forex.get("bias", "")))
        if indices:
            ctx.indices_bias = str(indices.get("summary", indices.get("ihsg_prediction", "")))

        parts = [f"Global sentiment: {ctx.global_sentiment}"]
        if ctx.commodity_bias:
            parts.append(f"Commodity: {ctx.commodity_bias}")
        if ctx.forex_bias:
            parts.append(f"Forex: {ctx.forex_bias}")
        if ctx.indices_bias:
            parts.append(f"Indices: {ctx.indices_bias}")
        ctx.summary = " | ".join(parts)
        return ctx

    # ------------------------------------------------------------------ #
    # Step 4 — Sector Rotation
    # ------------------------------------------------------------------ #

    def fetch_sector_scores(self) -> tuple[list[SectorScore], dict[str, list]]:
        raw = self.client.fetch(PROVIDER_IDX, "getSectorRotation", {}, analysis_date=self.date)
        if not raw:
            return [], {}
        scores: list[SectorScore] = []
        sector_top_stocks: dict[str, list] = {}

        # real API: hot_sectors + cold_sectors + all_sectors
        all_sectors = raw.get("all_sectors", [])
        hot = raw.get("hot_sectors", [])
        cold = raw.get("cold_sectors", [])

        # fallback: old fixture format with "sectors" key
        if not all_sectors and not hot:
            all_sectors = raw.get("sectors", raw.get("data", []))

        for s in (all_sectors or hot + cold):
            sector_name = s.get("sector_name", s.get("sector", s.get("name", "")))
            sc = SectorScore(
                analysis_date=self.date,
                sector=sector_name,
                sector_id=str(s.get("sector_id", s.get("sectorId", ""))),
                momentum_score=float(s.get("momentum_score", s.get("momentumScore", 0)) or 0),
                status=s.get("status", ""),
                foreign_flow=0.0,
                avg_return_today=float(s.get("avg_return_today", s.get("avgReturnToday", 0)) or 0),
                recommendation=s.get("recommendation", ""),
            )
            ff = s.get("foreign_flow", s.get("foreignFlow", ""))
            if isinstance(ff, (int, float)):
                sc.foreign_flow = float(ff)
            sc.final_score = normalize_score(sc.momentum_score, 0, 10)
            scores.append(sc)
            top = s.get("top_stocks", [])
            if top:
                sector_top_stocks[sector_name] = top

        # mark hot/cold status if coming from hot_sectors/cold_sectors lists
        hot_names = {s.get("sector_name", "") for s in hot}
        cold_names = {s.get("sector_name", "") for s in cold}
        for sc in scores:
            if not sc.status:
                if sc.sector in hot_names:
                    sc.status = "LEADING"
                elif sc.sector in cold_names:
                    sc.status = "LAGGING"

        return sorted(scores, key=lambda x: x.final_score, reverse=True), sector_top_stocks

    # ------------------------------------------------------------------ #
    # Step 5 — Market Movers & Attention
    # ------------------------------------------------------------------ #

    def fetch_market_movers(self) -> list[MarketMover]:
        movers: list[MarketMover] = []
        for mover_type in ["top-value", "net-foreign-buy"]:
            raw = self.client.fetch(
                PROVIDER_IDX, f"getMarketMover/{mover_type}",
                {"moverType": mover_type},
                analysis_date=self.date,
            )
            if not raw:
                continue
            items = raw.get("data", raw.get("stocks", raw if isinstance(raw, list) else []))
            if not isinstance(items, list):
                continue
            for i, item in enumerate(items[:10]):
                movers.append(MarketMover(
                    analysis_date=self.date,
                    mover_type=mover_type,
                    symbol=item.get("symbol", item.get("stockCode", "")),
                    name=item.get("name", item.get("stockName", "")),
                    price=float(item.get("price", item.get("lastPrice", 0)) or 0),
                    change_percent=float(item.get("changePercent", item.get("change_percent", 0)) or 0),
                    value=float(item.get("value", item.get("totalValue", 0)) or 0),
                    rank=i + 1,
                ))

        trending = self.client.fetch(PROVIDER_IDX, "getTrendingStocks", {}, analysis_date=self.date)
        if trending:
            # after unwrap: either a list directly or {"data": [...]}
            if isinstance(trending, list):
                items = trending
            else:
                items = trending.get("data", trending.get("stocks", []))
            if isinstance(items, list):
                for i, item in enumerate(items[:10]):
                    movers.append(MarketMover(
                        analysis_date=self.date,
                        mover_type="trending",
                        symbol=item.get("symbol", item.get("stockCode", "")),
                        name=item.get("name", item.get("stockName", "")),
                        price=float(item.get("last", item.get("price", item.get("lastPrice", 0))) or 0),
                        change_percent=float(item.get("percent", item.get("changePercent", item.get("change_percent", 0))) or 0),
                        rank=i + 1,
                    ))
        return movers

    # ------------------------------------------------------------------ #
    # Step 6 — Candidate Merge & Pre-Ranking
    # ------------------------------------------------------------------ #

    def build_candidates(
        self,
        sector_scores: list[SectorScore],
        sector_top_stocks: dict[str, list],
        movers: list[MarketMover],
        market_ctx: MarketContext,
    ) -> list[StockCandidate]:
        symbol_scores: dict[str, dict] = {}

        def _ensure(sym: str, sector: str = "") -> dict:
            if sym not in symbol_scores:
                symbol_scores[sym] = {
                    "sector": sector,
                    "reasons": [],
                    "market_attention": 0.0,
                    "foreign_flow": 0.0,
                    "liquidity": 0.0,
                }
            if sector and not symbol_scores[sym]["sector"]:
                symbol_scores[sym]["sector"] = sector
            return symbol_scores[sym]

        # sector top stocks (primary source when market movers unavailable)
        for sc in sector_scores[:5]:
            for i, stock in enumerate(sector_top_stocks.get(sc.sector, [])[:5]):
                sym = stock.get("symbol", "")
                if not sym:
                    continue
                entry = _ensure(sym, sc.sector)
                score = max(0.0, 1.0 - i * 0.15)
                entry["market_attention"] = max(entry["market_attention"], score * sc.final_score)
                entry["reasons"].append(f"sector-top:{sc.sector}")

        # market movers
        for m in movers:
            sym = m.symbol
            if not sym:
                continue
            entry = _ensure(sym)
            if m.mover_type == "net-foreign-buy":
                entry["foreign_flow"] = max(entry["foreign_flow"], 1.0 - (m.rank - 1) * 0.1)
                entry["reasons"].append("net-foreign-buy")
            elif m.mover_type == "top-value":
                entry["liquidity"] = max(entry["liquidity"], 1.0 - (m.rank - 1) * 0.1)
                entry["reasons"].append("top-value")
            elif m.mover_type == "trending":
                entry["market_attention"] = max(entry["market_attention"], 1.0 - (m.rank - 1) * 0.1)
                entry["reasons"].append("trending")

        news_alignment = 0.5 if market_ctx.global_sentiment == "neutral" else (
            0.8 if market_ctx.global_sentiment == "risk-on" else 0.2
        )

        candidates: list[StockCandidate] = []
        for sym, entry in symbol_scores.items():
            sector_mom = max((s.final_score for s in sector_scores if s.sector == entry["sector"]), default=0.5)
            pre = preliminary_candidate_score(
                sector_momentum=sector_mom,
                market_attention=entry["market_attention"],
                foreign_flow=entry["foreign_flow"],
                news_theme_alignment=news_alignment,
                liquidity=entry["liquidity"],
            )
            reasons = list(dict.fromkeys(entry["reasons"]))  # deduplicate preserving order
            candidates.append(StockCandidate(
                analysis_date=self.date,
                symbol=sym,
                sector=entry["sector"],
                candidate_reason=", ".join(reasons),
                pre_score=round(pre, 4),
            ))

        return sorted(candidates, key=lambda c: c.pre_score, reverse=True)

    # ------------------------------------------------------------------ #
    # Step 7 — Stock-Specific Analysis
    # ------------------------------------------------------------------ #

    def run_pass1_technical(self, candidates: list[StockCandidate]) -> list[StockCandidate]:
        top = candidates[: self.config.candidates_lightweight]
        for c in top:
            tech = self.client.fetch(
                PROVIDER_IDX, "getTechnicalAnalysis",
                {"symbol": c.symbol}, symbol=c.symbol, analysis_date=self.date,
            )
            rr = self.client.fetch(
                PROVIDER_IDX, "calculateRiskReward",
                {"symbol": c.symbol}, symbol=c.symbol, analysis_date=self.date,
            )
            if tech:
                raw_signal = tech.get("signal", {})
                if isinstance(raw_signal, dict):
                    signal = raw_signal.get("action", tech.get("trend", {}).get("overallTrend", "NEUTRAL"))
                else:
                    signal = raw_signal
                c.technical_score = score_from_signal(signal)
                if not c.entry_price:
                    resistance = float(tech.get("resistance", tech.get("nearest_resistance", tech.get("nearestResistance", 0))) or 0)
                    support = float(tech.get("support", tech.get("nearest_support", tech.get("nearestSupport", 0))) or 0)
                    if support and resistance:
                        c.entry_price = resistance
                        c.entry_zone_low = support
                        c.entry_zone_high = resistance
            if rr:
                rr_val = rr.get("riskRewardRatio", rr.get("risk_reward_ratio", rr.get("risk_reward_ratio_value", 1.0))) or 1.0
                c.risk_reward_score = normalize_score(float(rr_val), 0, 5)
                c.trade_risk_reward_ratio = float(rr_val)

                entry = rr.get("entry_price", rr.get("entryPrice", rr.get("current_price", rr.get("currentPrice", rr.get("price", 0))))) or 0
                stop = rr.get("stop_loss", rr.get("stopLoss", rr.get("recommended_stop_loss", rr.get("recommendedStopLoss", 0)))) or 0
                targets = rr.get("targets", rr.get("target_prices", rr.get("targetPrices", [])))
                if isinstance(targets, list) and targets:
                    first = targets[0]
                    second = targets[1] if len(targets) > 1 else targets[0]
                    c.take_profit_1 = float(first.get("price", first.get("target", first)) if isinstance(first, dict) else first or 0)
                    c.take_profit_2 = float(second.get("price", second.get("target", second)) if isinstance(second, dict) else second or 0)
                else:
                    c.take_profit_1 = float(rr.get("take_profit_1", rr.get("takeProfit1", rr.get("target_price_1", rr.get("targetPrice1", rr.get("target1", 0))))) or 0)
                    c.take_profit_2 = float(rr.get("take_profit_2", rr.get("takeProfit2", rr.get("target_price_2", rr.get("targetPrice2", rr.get("target2", c.take_profit_1))))) or 0)

                c.entry_price = float(entry)
                c.stop_loss = float(stop)
                if c.entry_price:
                    c.entry_zone_low = float(rr.get("entry_zone_low", rr.get("entryZoneLow", c.entry_price * 0.98)) or 0)
                    c.entry_zone_high = float(rr.get("entry_zone_high", rr.get("entryZoneHigh", c.entry_price * 1.01)) or 0)
                c.position_size_lots = float(rr.get("position_size_lots", rr.get("positionSizeLots", rr.get("recommended_lots", 0))) or 0)
                if c.entry_price and c.stop_loss and c.take_profit_1:
                    c.trade_plan_summary = "Buy on pullback/breakout confirmation within entry zone; invalidate below stop loss."
        return sorted(top, key=lambda c: c.technical_score + c.risk_reward_score, reverse=True)

    def run_pass2_bandar(self, candidates: list[StockCandidate]) -> list[tuple[StockCandidate, StockTransactionAnalysis]]:
        top = candidates[: self.config.candidates_bandar]
        results = []
        for c in top:
            ta = StockTransactionAnalysis(analysis_date=self.date, symbol=c.symbol)

            sm = self.client.fetch(PROVIDER_IDX, "getSmartMoneyFlow", {"symbol": c.symbol}, symbol=c.symbol, analysis_date=self.date)
            ba = self.client.fetch(PROVIDER_IDX, "getBandarAccumulation", {"symbol": c.symbol}, symbol=c.symbol, analysis_date=self.date)
            bd = self.client.fetch(PROVIDER_IDX, "getBandarDistribution", {"symbol": c.symbol}, symbol=c.symbol, analysis_date=self.date)
            rbs = self.client.fetch(PROVIDER_IDX, "getRetailBandarSentiment", {"symbol": c.symbol}, symbol=c.symbol, analysis_date=self.date)

            if sm:
                flow = sm.get("flow_direction", sm.get("signal", sm.get("trend", "NEUTRAL")))
                score_val = float(sm.get("smart_money_score", 5) or 5)
                ta.smart_money_summary = f"Flow: {flow} | Score: {score_val}/10"
                c.smart_money_score = normalize_score(score_val, 0, 10)
            if ba:
                status = ba.get("status", ba.get("signal", ""))
                acc_score = float(ba.get("accumulation_score", ba.get("accumulationScore", ba.get("score", 50))) or 50)
                ta.bandar_accumulation_summary = f"Status: {status} | Score: {acc_score}"
                c.bandar_score = max(c.bandar_score, normalize_score(acc_score, 0, 10))
            if bd:
                status = bd.get("status", bd.get("signal", ""))
                dist_score = float(bd.get("distribution_score", bd.get("distributionScore", bd.get("score", 50))) or 50)
                ta.bandar_distribution_summary = f"Status: {status} | Score: {dist_score}"
                c.bandar_score = min(c.bandar_score, 1.0 - normalize_score(dist_score, 0, 10))
            if rbs:
                divergence = rbs.get("divergence", {})
                if isinstance(divergence, dict):
                    div_type = divergence.get("type", "NEUTRAL")
                    warning = divergence.get("warning", "")
                    ta.retail_bandar_sentiment = f"{div_type}: {warning}" if warning else div_type
                else:
                    ta.retail_bandar_sentiment = str(divergence)

            results.append((c, ta))
        return results

    def run_pass3_deep(self, candidates: list[StockCandidate], ta_map: dict[str, StockTransactionAnalysis]) -> None:
        top = candidates[: self.config.candidates_deep]
        for c in top:
            ta = ta_map.get(c.symbol, StockTransactionAnalysis(analysis_date=self.date, symbol=c.symbol))

            whale = self.client.fetch(PROVIDER_IDX, "getWhaleTransactions", {"symbol": c.symbol}, symbol=c.symbol, analysis_date=self.date)
            broker = self.client.fetch(PROVIDER_IDX, "getBrokerSummary",
                {"symbol": c.symbol, "from": self.date, "to": self.date,
                 "transactionType": "TRANSACTION_TYPE_NET",
                 "marketBoard": "MARKET_BOARD_ALL",
                 "investorType": "INVESTOR_TYPE_ALL"},
                symbol=c.symbol, analysis_date=self.date,
            )
            pnd = self.client.fetch(PROVIDER_IDX, "getPumpDumpDetection", {"symbol": c.symbol}, symbol=c.symbol, analysis_date=self.date)

            if whale:
                pred = whale.get("prediction", {})
                if isinstance(pred, dict):
                    direction = pred.get("short_term_direction", "")
                    confidence = pred.get("confidence", "")
                    reasoning = pred.get("reasoning", [])
                    ta.whale_summary = f"{direction} (confidence: {confidence}%) — {reasoning[0] if reasoning else ''}"
                else:
                    ta.whale_summary = str(pred)
            if broker:
                brokers = broker.get("brokers", broker.get("topBrokers", []))
                if isinstance(brokers, list) and brokers:
                    top_b = brokers[:3]
                    ta.broker_summary = " | ".join(
                        f"{b.get('broker_code', b.get('broker','?'))} net:{b.get('net_value', b.get('net','?'))}"
                        for b in top_b
                    )
                else:
                    ta.broker_summary = str(broker.get("summary", ""))
            if pnd:
                ta.pump_dump_risk = pnd.get("risk_level", pnd.get("riskLevel", pnd.get("risk", "LOW")))

    # ------------------------------------------------------------------ #
    # Step 8 — Final Score
    # ------------------------------------------------------------------ #

    def compute_final_scores(
        self,
        candidates: list[StockCandidate],
        sector_scores: list[SectorScore],
        market_ctx: MarketContext,
    ) -> list[StockCandidate]:
        sector_map = {s.sector: s.final_score for s in sector_scores}
        news_macro = 0.5 if market_ctx.global_sentiment == "neutral" else (
            0.8 if market_ctx.global_sentiment == "risk-on" else 0.2
        )
        for c in candidates:
            c.final_score = final_candidate_score(
                sector_rotation=sector_map.get(c.sector, 0.5),
                news_macro_alignment=news_macro,
                market_mover=c.pre_score,
                smart_money=c.smart_money_score,
                bandar_accumulation=c.bandar_score,
                technical_confirmation=c.technical_score,
                risk_reward=c.risk_reward_score,
            )
        return sorted(candidates, key=lambda c: c.final_score, reverse=True)

    # ------------------------------------------------------------------ #
    # Orchestrate
    # ------------------------------------------------------------------ #

    def run(self) -> dict:
        news_items = self.fetch_news()
        market_ctx = self.fetch_market_context(news_items)
        sector_scores, sector_top_stocks = self.fetch_sector_scores()
        movers = self.fetch_market_movers()

        candidates = self.build_candidates(sector_scores, sector_top_stocks, movers, market_ctx)

        pass1 = self.run_pass1_technical(candidates)
        pass2_results = self.run_pass2_bandar(pass1)

        ta_map: dict[str, StockTransactionAnalysis] = {}
        pass2_candidates = []
        for c, ta in pass2_results:
            ta_map[c.symbol] = ta
            pass2_candidates.append(c)

        self.run_pass3_deep(pass2_candidates, ta_map)
        final = self.compute_final_scores(pass2_candidates, sector_scores, market_ctx)

        return {
            "date": self.date,
            "news_items": news_items,
            "market_context": market_ctx,
            "sector_scores": sector_scores,
            "movers": movers,
            "candidates": final,
            "transaction_analysis": ta_map,
        }
