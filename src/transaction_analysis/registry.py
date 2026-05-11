from __future__ import annotations
from typing import Any, Callable, Optional
from . import providers


class ProviderRegistry:
    """Maps (provider, endpoint) to a callable for live API calls."""

    def __init__(self):
        self._registry: dict[str, Callable[..., Any]] = {}

    def register(self, provider: str, endpoint: str, fn: Callable[..., Any]) -> None:
        self._registry[f"{provider}/{endpoint}"] = fn

    def get(self, provider: str, endpoint: str) -> Optional[Callable[..., Any]]:
        return self._registry.get(f"{provider}/{endpoint}")


def build_live_registry() -> ProviderRegistry:
    """Wire all live RapidAPI provider functions."""
    from .data_client import PROVIDER_IDX, PROVIDER_NEWS
    r = ProviderRegistry()

    # News
    r.register(PROVIDER_NEWS, "rss", providers.rss)

    # IDX — Global / Macro
    r.register(PROVIDER_IDX, "getGlobalMarketOverview", lambda **_: providers.getGlobalMarketOverview())
    r.register(PROVIDER_IDX, "getCommoditiesImpact", lambda **_: providers.getCommoditiesImpact())
    r.register(PROVIDER_IDX, "getForexIdrImpact", lambda **_: providers.getForexIdrImpact())
    r.register(PROVIDER_IDX, "getIndicesImpact", lambda **_: providers.getIndicesImpact())
    r.register(PROVIDER_IDX, "getEconomicCalendar", lambda **_: providers.getEconomicCalendar())
    r.register(PROVIDER_IDX, "getTodayCorporateActions", lambda **_: providers.getTodayCorporateActions())

    # IDX — Sector & Market
    r.register(PROVIDER_IDX, "getSectorRotation", lambda **_: providers.getSectorRotation())
    r.register(PROVIDER_IDX, "getTrendingStocks", lambda **_: providers.getTrendingStocks())
    r.register(PROVIDER_IDX, "getMarketMover/top-value",
               lambda **_: providers.getMarketMover("top-value"))
    r.register(PROVIDER_IDX, "getMarketMover/net-foreign-buy",
               lambda **_: providers.getMarketMover("net-foreign-buy"))
    r.register(PROVIDER_IDX, "getBreakoutAlerts", lambda **_: providers.getBreakoutAlerts())

    # IDX — Technical & Risk
    r.register(PROVIDER_IDX, "getTechnicalAnalysis",
               lambda symbol, **_: providers.getTechnicalAnalysis(symbol))
    r.register(PROVIDER_IDX, "calculateRiskReward",
               lambda symbol, **_: providers.calculateRiskReward(symbol))

    # IDX — Transaction Analysis
    r.register(PROVIDER_IDX, "getSmartMoneyFlow",
               lambda symbol, **_: providers.getSmartMoneyFlow(symbol))
    r.register(PROVIDER_IDX, "getBandarAccumulation",
               lambda symbol, **_: providers.getBandarAccumulation(symbol))
    r.register(PROVIDER_IDX, "getBandarDistribution",
               lambda symbol, **_: providers.getBandarDistribution(symbol))
    r.register(PROVIDER_IDX, "getRetailBandarSentiment",
               lambda symbol, **_: providers.getRetailBandarSentiment(symbol))
    r.register(PROVIDER_IDX, "getWhaleTransactions",
               lambda symbol, **_: providers.getWhaleTransactions(symbol))
    r.register(PROVIDER_IDX, "getBrokerSummary",
               lambda symbol, **_: providers.getBrokerSummary(symbol))
    r.register(PROVIDER_IDX, "getPumpDumpDetection",
               lambda symbol, **_: providers.getPumpDumpDetection(symbol))

    return r
