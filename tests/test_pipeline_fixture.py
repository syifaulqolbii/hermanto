import json
import os
import pytest
from transaction_analysis.config import Config
from transaction_analysis.storage import Storage
from transaction_analysis.data_client import DataClient
from transaction_analysis.pipeline import Pipeline
from transaction_analysis.report import render_report


FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_data.json")


@pytest.fixture
def fixture_data():
    with open(FIXTURE_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def pipeline_result(tmp_path, fixture_data):
    config = Config()
    config.db_path = str(tmp_path / "test.sqlite3")
    config.budget_mode = "conservative"
    storage = Storage(config)
    storage.init_schema()
    client = DataClient(config, storage, fixture_data=fixture_data)
    pipeline = Pipeline(config, storage, client, analysis_date="2026-05-10")
    result = pipeline.run()
    yield result, config, storage
    storage.close()


def test_pipeline_returns_candidates(pipeline_result):
    result, config, storage = pipeline_result
    assert "candidates" in result
    assert len(result["candidates"]) > 0


def test_pipeline_market_context(pipeline_result):
    result, config, storage = pipeline_result
    ctx = result["market_context"]
    assert ctx.analysis_date == "2026-05-10"
    assert ctx.global_sentiment in ("risk-on", "neutral", "risk-off")


def test_pipeline_sector_scores(pipeline_result):
    result, config, storage = pipeline_result
    sectors = result["sector_scores"]
    assert len(sectors) > 0
    assert all(0.0 <= s.final_score <= 1.0 for s in sectors)


def test_pipeline_candidates_scored(pipeline_result):
    result, config, storage = pipeline_result
    for c in result["candidates"]:
        assert 0.0 <= c.final_score <= 1.0


def test_pipeline_transaction_analysis_populated(pipeline_result):
    result, config, storage = pipeline_result
    ta_map = result["transaction_analysis"]
    assert len(ta_map) > 0
    for sym, ta in ta_map.items():
        assert ta.symbol == sym


def test_report_renders_without_error(pipeline_result):
    result, config, storage = pipeline_result
    content = render_report(
        date="2026-05-10",
        news_items=result["news_items"],
        market_ctx=result["market_context"],
        sector_scores=result["sector_scores"],
        candidates=result["candidates"],
        ta_map=result["transaction_analysis"],
        request_usage={"RapidAPI_IDX": 12, "RapidAPI_News": 1},
        config=config,
    )
    assert "# Daily Transaction Analysis Report" in content
    assert "Market Context" in content
    assert "Top Candidates" in content
    assert "Request Usage Summary" in content


def test_report_contains_top_candidate(pipeline_result):
    result, config, storage = pipeline_result
    content = render_report(
        date="2026-05-10",
        news_items=result["news_items"],
        market_ctx=result["market_context"],
        sector_scores=result["sector_scores"],
        candidates=result["candidates"],
        ta_map=result["transaction_analysis"],
        request_usage={"RapidAPI_IDX": 12, "RapidAPI_News": 1},
        config=config,
    )
    top_symbol = result["candidates"][0].symbol
    assert top_symbol in content
