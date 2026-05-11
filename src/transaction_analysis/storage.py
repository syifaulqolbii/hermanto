from __future__ import annotations
import sqlite3
import json
import os
from datetime import datetime, date, timezone
from typing import Any, Optional

from .config import Config


DDL = """
CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_date TEXT NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1,
    monthly_quota INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    params_hash TEXT NOT NULL,
    symbol TEXT,
    analysis_date TEXT NOT NULL,
    raw_response TEXT,
    normalized_json TEXT,
    ttl_expires_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    UNIQUE(provider, endpoint, params_hash, analysis_date)
);

CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    published_at TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    url TEXT,
    sentiment_score REAL DEFAULT 0.0,
    themes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS market_context (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL UNIQUE,
    global_sentiment TEXT,
    commodity_bias TEXT,
    forex_bias TEXT,
    indices_bias TEXT,
    summary TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sector_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    sector TEXT NOT NULL,
    sector_id TEXT,
    momentum_score REAL DEFAULT 0.0,
    status TEXT,
    foreign_flow REAL DEFAULT 0.0,
    avg_return_today REAL DEFAULT 0.0,
    recommendation TEXT,
    final_score REAL DEFAULT 0.0,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS market_movers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    mover_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT,
    price REAL DEFAULT 0.0,
    change_percent REAL DEFAULT 0.0,
    value REAL DEFAULT 0.0,
    rank INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stock_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    sector TEXT,
    theme TEXT,
    candidate_reason TEXT,
    pre_score REAL DEFAULT 0.0,
    technical_score REAL DEFAULT 0.0,
    smart_money_score REAL DEFAULT 0.0,
    bandar_score REAL DEFAULT 0.0,
    risk_reward_score REAL DEFAULT 0.0,
    final_score REAL DEFAULT 0.0,
    status TEXT DEFAULT 'candidate'
);

CREATE TABLE IF NOT EXISTS stock_transaction_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    smart_money_summary TEXT,
    bandar_accumulation_summary TEXT,
    bandar_distribution_summary TEXT,
    retail_bandar_sentiment TEXT,
    whale_summary TEXT,
    broker_summary TEXT,
    pump_dump_risk TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_date TEXT NOT NULL,
    report_type TEXT NOT NULL DEFAULT 'daily',
    summary TEXT,
    recommendations TEXT,
    risks TEXT,
    request_usage_summary TEXT,
    created_at TEXT NOT NULL
);
"""


class Storage:
    def __init__(self, config: Config):
        os.makedirs(os.path.dirname(config.db_path), exist_ok=True)
        self.conn = sqlite3.connect(config.db_path)
        self.conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        self.conn.executescript(DDL)
        self.conn.commit()

    # --- api_usage ---

    def record_request(self, provider: str, endpoint: str, request_date: str, monthly_quota: int = 0) -> None:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            "SELECT id, request_count FROM api_usage WHERE provider=? AND endpoint=? AND request_date=?",
            (provider, endpoint, request_date),
        )
        row = cur.fetchone()
        if row:
            self.conn.execute(
                "UPDATE api_usage SET request_count=? WHERE id=?",
                (row["request_count"] + 1, row["id"]),
            )
        else:
            self.conn.execute(
                "INSERT INTO api_usage (provider, endpoint, request_date, request_count, monthly_quota, created_at) VALUES (?,?,?,1,?,?)",
                (provider, endpoint, request_date, monthly_quota, now),
            )
        self.conn.commit()

    def daily_usage(self, provider: str, request_date: str) -> int:
        cur = self.conn.execute(
            "SELECT COALESCE(SUM(request_count),0) as total FROM api_usage WHERE provider=? AND request_date=?",
            (provider, request_date),
        )
        return cur.fetchone()["total"]

    def monthly_usage(self, provider: str, year_month: str) -> int:
        cur = self.conn.execute(
            "SELECT COALESCE(SUM(request_count),0) as total FROM api_usage WHERE provider=? AND request_date LIKE ?",
            (provider, f"{year_month}%"),
        )
        return cur.fetchone()["total"]

    # --- api_cache ---

    def get_cache(self, provider: str, endpoint: str, params_hash: str, analysis_date: str) -> Optional[Any]:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            "SELECT normalized_json FROM api_cache WHERE provider=? AND endpoint=? AND params_hash=? AND analysis_date=? AND ttl_expires_at > ?",
            (provider, endpoint, params_hash, analysis_date, now),
        )
        row = cur.fetchone()
        if row and row["normalized_json"]:
            return json.loads(row["normalized_json"])
        return None

    def set_cache(self, provider: str, endpoint: str, params_hash: str, symbol: Optional[str],
                  analysis_date: str, raw_response: Any, normalized: Any, ttl_expires_at: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO api_cache (provider, endpoint, params_hash, symbol, analysis_date, raw_response, normalized_json, ttl_expires_at, fetched_at)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(provider, endpoint, params_hash, analysis_date) DO UPDATE SET
                 raw_response=excluded.raw_response,
                 normalized_json=excluded.normalized_json,
                 ttl_expires_at=excluded.ttl_expires_at,
                 fetched_at=excluded.fetched_at""",
            (provider, endpoint, params_hash, symbol, analysis_date,
             json.dumps(raw_response), json.dumps(normalized), ttl_expires_at, now),
        )
        self.conn.commit()

    # --- analysis_reports ---

    def save_report(self, analysis_date: str, report_type: str, summary: str,
                    recommendations: str, risks: str, request_usage_summary: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO analysis_reports (analysis_date, report_type, summary, recommendations, risks, request_usage_summary, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (analysis_date, report_type, summary, recommendations, risks, request_usage_summary, now),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
