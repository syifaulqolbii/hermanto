import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

BUDGET_LIMITS = {
    "conservative": {"idx": 20, "news": 1},
    "default":      {"idx": 37, "news": 3},
    "expanded":     {"idx": 50, "news": 5},
}

@dataclass
class Config:
    budget_mode: str = field(default_factory=lambda: os.getenv("TA_BUDGET_MODE", "default"))
    news_sources: list[str] = field(default_factory=lambda: os.getenv(
        "TA_NEWS_SOURCES", "Bloomberg,MarketWatch,FinancialTimes"
    ).split(","))
    candidates_lightweight: int = field(default_factory=lambda: int(os.getenv("TA_CANDIDATES_LIGHTWEIGHT", "5")))
    candidates_bandar: int = field(default_factory=lambda: int(os.getenv("TA_CANDIDATES_BANDAR", "3")))
    candidates_deep: int = field(default_factory=lambda: int(os.getenv("TA_CANDIDATES_DEEP", "2")))
    db_path: str = field(default_factory=lambda: os.getenv("TA_DB_PATH", "data/transaction_analysis.sqlite3"))
    reports_dir: str = field(default_factory=lambda: os.getenv("TA_REPORTS_DIR", "reports"))

    @property
    def daily_idx_budget(self) -> int:
        return BUDGET_LIMITS.get(self.budget_mode, BUDGET_LIMITS["default"])["idx"]

    @property
    def daily_news_budget(self) -> int:
        return BUDGET_LIMITS.get(self.budget_mode, BUDGET_LIMITS["default"])["news"]
