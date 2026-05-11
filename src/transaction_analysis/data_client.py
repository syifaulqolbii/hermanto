from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from .config import Config
from .storage import Storage


PROVIDER_IDX = "RapidAPI_IDX"
PROVIDER_NEWS = "RapidAPI_News"

TTL_HOURS: dict[str, int] = {
    "default": 24,
    "orderbook": 0,
    "running_trade": 0,
    "tradebook_chart": 0,
}


def _params_hash(params: dict) -> str:
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()


def _ttl_expires(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


class DataClient:
    """Cache-first wrapper around provider callables.

    In fixture mode, responses come from the fixture registry.
    In live mode, provider_fn (or registry lookup) is called on cache miss.
    """

    def __init__(self, config: Config, storage: Storage,
                 fixture_data: Optional[dict] = None,
                 registry=None):
        self.config = config
        self.storage = storage
        self.fixture_data = fixture_data
        self.registry = registry  # ProviderRegistry | None
        self._disabled: set[str] = set()

    def fetch(
        self,
        provider: str,
        endpoint: str,
        params: dict,
        symbol: Optional[str] = None,
        provider_fn: Optional[Callable[..., Any]] = None,
        analysis_date: Optional[str] = None,
        ttl_hours: int = 24,
    ) -> Optional[Any]:
        today = analysis_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        phash = _params_hash(params)
        ep_key = f"{provider}/{endpoint}"

        if ep_key in self._disabled:
            return None

        # cache hit
        cached = self.storage.get_cache(provider, endpoint, phash, today)
        if cached is not None:
            return cached

        # fixture mode
        if self.fixture_data is not None:
            raw = self.fixture_data.get(ep_key)
            if raw is None:
                return None
            self.storage.set_cache(provider, endpoint, phash, symbol, today, raw, raw, _ttl_expires(ttl_hours))
            return raw

        # resolve provider_fn from registry if not explicitly passed
        if provider_fn is None and self.registry is not None:
            provider_fn = self.registry.get(provider, endpoint)

        if provider_fn is None:
            return None

        try:
            raw = provider_fn(**params)
        except Exception as exc:
            msg = str(exc)
            if "401" in msg or "403" in msg:
                self._disabled.add(ep_key)
            import sys
            print(f"[DataClient] ERROR {ep_key}: {exc}", file=sys.stderr)
            return None

        self.storage.record_request(provider, endpoint, today)
        self.storage.set_cache(provider, endpoint, phash, symbol, today, raw, raw, _ttl_expires(ttl_hours))
        return raw

    def budget_ok(self, provider: str, analysis_date: str) -> bool:
        used = self.storage.daily_usage(provider, analysis_date)
        if provider == PROVIDER_IDX:
            return used < self.config.daily_idx_budget
        if provider == PROVIDER_NEWS:
            return used < self.config.daily_news_budget
        return True

