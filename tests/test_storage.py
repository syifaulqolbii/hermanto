import os
import tempfile
import pytest
from transaction_analysis.config import Config
from transaction_analysis.storage import Storage


@pytest.fixture
def tmp_storage(tmp_path):
    config = Config()
    config.db_path = str(tmp_path / "test.sqlite3")
    storage = Storage(config)
    storage.init_schema()
    yield storage
    storage.close()


def test_record_and_daily_usage(tmp_storage):
    tmp_storage.record_request("RapidAPI_IDX", "getSectorRotation", "2026-05-10")
    tmp_storage.record_request("RapidAPI_IDX", "getTrendingStocks", "2026-05-10")
    tmp_storage.record_request("RapidAPI_IDX", "getSectorRotation", "2026-05-10")
    assert tmp_storage.daily_usage("RapidAPI_IDX", "2026-05-10") == 3


def test_monthly_usage(tmp_storage):
    tmp_storage.record_request("RapidAPI_IDX", "ep1", "2026-05-10")
    tmp_storage.record_request("RapidAPI_IDX", "ep2", "2026-05-11")
    tmp_storage.record_request("RapidAPI_News", "rss", "2026-05-10")
    assert tmp_storage.monthly_usage("RapidAPI_IDX", "2026-05") == 2
    assert tmp_storage.monthly_usage("RapidAPI_News", "2026-05") == 1


def test_cache_set_and_get(tmp_storage):
    tmp_storage.set_cache(
        provider="RapidAPI_IDX",
        endpoint="getSectorRotation",
        params_hash="abc123",
        symbol=None,
        analysis_date="2026-05-10",
        raw_response={"raw": True},
        normalized={"sectors": []},
        ttl_expires_at="2099-01-01T00:00:00",
    )
    result = tmp_storage.get_cache("RapidAPI_IDX", "getSectorRotation", "abc123", "2026-05-10")
    assert result == {"sectors": []}


def test_cache_miss_returns_none(tmp_storage):
    result = tmp_storage.get_cache("RapidAPI_IDX", "nonexistent", "xyz", "2026-05-10")
    assert result is None


def test_cache_expired_returns_none(tmp_storage):
    tmp_storage.set_cache(
        provider="RapidAPI_IDX",
        endpoint="getSectorRotation",
        params_hash="expired123",
        symbol=None,
        analysis_date="2026-05-10",
        raw_response={},
        normalized={"sectors": []},
        ttl_expires_at="2000-01-01T00:00:00",  # already expired
    )
    result = tmp_storage.get_cache("RapidAPI_IDX", "getSectorRotation", "expired123", "2026-05-10")
    assert result is None


def test_save_report(tmp_storage):
    tmp_storage.save_report(
        analysis_date="2026-05-10",
        report_type="daily",
        summary="Test summary",
        recommendations="HEAL",
        risks="None",
        request_usage_summary='{"RapidAPI_IDX": 5}',
    )
    cur = tmp_storage.conn.execute("SELECT * FROM analysis_reports WHERE analysis_date='2026-05-10'")
    row = cur.fetchone()
    assert row is not None
    assert row["summary"] == "Test summary"
