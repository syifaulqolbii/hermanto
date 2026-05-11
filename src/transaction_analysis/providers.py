from __future__ import annotations
import os
import urllib.request
import urllib.parse
import json
import time
from typing import Any, Optional


IDX_HOST = "indonesia-stock-exchange-idx.p.rapidapi.com"
IDX_BASE = f"https://{IDX_HOST}"

NEWS_HOST = "economics-news-rss.p.rapidapi.com"
NEWS_BASE = f"https://{NEWS_HOST}"

# Minimum seconds between requests to avoid 429
REQUEST_DELAY = 1.2


def _get_key() -> str:
    key = os.getenv("RAPIDAPI_KEY", "")
    if not key:
        raise RuntimeError("RAPIDAPI_KEY not set in environment")
    return key


_last_request_time: float = 0.0


def _request(url: str, host: str, retries: int = 2) -> Any:
    global _last_request_time
    # rate limit: enforce minimum gap between requests
    elapsed = time.monotonic() - _last_request_time
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)

    req = urllib.request.Request(url)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-rapidapi-host", host)
    req.add_header("x-rapidapi-key", _get_key())
    req.add_header("User-Agent", "curl/8.4.0")

    for attempt in range(retries + 1):
        try:
            _last_request_time = time.monotonic()
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode())
                # unwrap {"success": true, "data": {...}} envelope
                if isinstance(body, dict) and body.get("success") and "data" in body:
                    inner = body["data"]
                    # some endpoints double-wrap: {"data": {"data": [...]}}
                    if isinstance(inner, dict) and "data" in inner and isinstance(inner["data"], list):
                        return inner["data"]
                    return inner
                return body
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(2.0 * (attempt + 1))
                continue
            raise
    return None


def _idx(path: str, params: Optional[dict] = None) -> Any:
    url = f"{IDX_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return _request(url, IDX_HOST)


def _news(params: Optional[dict] = None) -> Any:
    url = NEWS_BASE + "/rss"
    if params:
        url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    return _request(url, NEWS_HOST)


# ------------------------------------------------------------------ #
# News
# ------------------------------------------------------------------ #

def rss(source: str = "Bloomberg", limit: int = 25) -> Any:
    return _news({"source": source, "limit": limit})


# ------------------------------------------------------------------ #
# IDX — Global / Macro
# ------------------------------------------------------------------ #

def getGlobalMarketOverview() -> Any:
    return _idx("/api/global/market-overview")

def getCommoditiesImpact() -> Any:
    return _idx("/api/main/commodities-impact")

def getForexIdrImpact() -> Any:
    return _idx("/api/main/forex-idr-impact")

def getIndicesImpact() -> Any:
    return _idx("/api/global/indices-impact")

def getEconomicCalendar() -> Any:
    return _idx("/api/calendar/economic")

def getTodayCorporateActions() -> Any:
    return _idx("/api/calendar/today")


# ------------------------------------------------------------------ #
# IDX — Sector & Market Screening
# ------------------------------------------------------------------ #

def getSectorRotation() -> Any:
    return _idx("/api/analysis/retail/sector-rotation")

def getTrendingStocks() -> Any:
    return _idx("/api/main/trending")

def getMarketMover(moverType: str = "top-value") -> Any:
    return _idx(f"/api/movers/{moverType}")

def getBreakoutAlerts() -> Any:
    return _idx("/api/analysis/retail/breakout/alerts")


# ------------------------------------------------------------------ #
# IDX — Stock-Specific Transaction Analysis
# ------------------------------------------------------------------ #

def getSmartMoneyFlow(symbol: str, days: int = 30) -> Any:
    return _idx(f"/api/analysis/bandar/smart-money/{symbol}", {"days": days})

def getBandarAccumulation(symbol: str, days: int = 30) -> Any:
    return _idx(f"/api/analysis/bandar/accumulation/{symbol}", {"days": days})

def getBandarDistribution(symbol: str, days: int = 30) -> Any:
    return _idx(f"/api/analysis/bandar/distribution/{symbol}", {"days": days})

def getRetailBandarSentiment(symbol: str, days: int = 7) -> Any:
    return _idx(f"/api/analysis/sentiment/{symbol}", {"days": days})

def getWhaleTransactions(symbol: str, min_lot: int = 500) -> Any:
    return _idx(f"/api/analysis/whale-transactions/{symbol}", {"min_lot": min_lot})

def getBrokerSummary(symbol: str, from_date: str = "", to_date: str = "") -> Any:
    return _idx(f"/api/market-detector/broker-summary/{symbol}", {
        "from": from_date,
        "to": to_date,
        "transactionType": "TRANSACTION_TYPE_NET",
        "marketBoard": "MARKET_BOARD_ALL",
        "investorType": "INVESTOR_TYPE_ALL",
        "limit": 25,
    })

def getPumpDumpDetection(symbol: str, days: int = 14) -> Any:
    return _idx(f"/api/analysis/bandar/pump-dump/{symbol}", {"days": days})

def getForeignOwnership(symbol: str) -> Any:
    return _idx(f"/api/emiten/{symbol}/foreign-ownership")

def getInsiderTradingBySymbol(symbol: str) -> Any:
    return _idx(f"/api/emiten/{symbol}/insider")


# ------------------------------------------------------------------ #
# IDX — Technical & Risk
# ------------------------------------------------------------------ #

def getTechnicalAnalysis(symbol: str, timeframe: str = "daily", period: int = 100) -> Any:
    return _idx(f"/api/analysis/technical/{symbol}", {"timeframe": timeframe, "period": period})

def calculateRiskReward(symbol: str, days: int = 30, risk_percent: float = 2.0) -> Any:
    return _idx(f"/api/analysis/retail/risk-reward/{symbol}", {
        "days": days,
        "risk_percent": risk_percent,
    })

def getLatestOHLCV(symbol: str, timeframe: str = "daily", limit: int = 100) -> Any:
    return _idx(f"/api/chart/{symbol}/{timeframe}/latest", {"limit": limit})

def getOrderbook(symbol: str) -> Any:
    return _idx(f"/api/emiten/{symbol}/orderbook")

def getEmitenInfo(symbol: str) -> Any:
    return _idx(f"/api/emiten/{symbol}/info")
