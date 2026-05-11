from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone

import click
from dotenv import load_dotenv

load_dotenv()

from .config import Config
from .storage import Storage
from .data_client import DataClient, PROVIDER_IDX, PROVIDER_NEWS
from .pipeline import Pipeline
from .report import render_report, save_report
from .serializer import pipeline_result_to_dict, find_trade_plan


@click.group()
def cli():
    """Transaction Analysis CLI — IDX daily report."""


@cli.command("init-db")
def init_db():
    """Create SQLite tables."""
    config = Config()
    storage = Storage(config)
    storage.init_schema()
    storage.close()
    click.echo(f"Database initialized at {config.db_path}")


@cli.command("daily-report")
@click.option("--date", default=None, help="Analysis date YYYY-MM-DD (default: today)")
@click.option("--mode", default=None, type=click.Choice(["conservative", "default", "expanded"]),
              help="Budget mode (overrides TA_BUDGET_MODE env var)")
@click.option("--fixture", is_flag=True, default=False,
              help="Use fixture data instead of live API calls")
@click.option("--json-output", is_flag=True, default=False,
              help="Print structured JSON for Hermes integration")
def daily_report(date: str, mode: str, fixture: bool, json_output: bool):
    """Run the daily analysis pipeline and write a markdown report."""
    config = Config()
    if mode:
        config.budget_mode = mode

    analysis_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    storage = Storage(config)
    storage.init_schema()

    fixture_data = None
    registry = None

    if fixture:
        fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "sample_data.json")
        fixture_path = os.path.normpath(fixture_path)
        with open(fixture_path, encoding="utf-8") as f:
            fixture_data = json.load(f)
        if not json_output:
            click.echo("Running in fixture mode (no API quota used)")
    else:
        from .registry import build_live_registry
        registry = build_live_registry()
        if not json_output:
            click.echo("Running in live mode (using RapidAPI)")

    client = DataClient(config, storage, fixture_data=fixture_data, registry=registry)
    pipeline = Pipeline(config, storage, client, analysis_date=analysis_date)

    if not json_output:
        click.echo(f"Running pipeline for {analysis_date} [{config.budget_mode} mode]...")
    result = pipeline.run()

    request_usage = {
        PROVIDER_IDX: storage.daily_usage(PROVIDER_IDX, analysis_date),
        PROVIDER_NEWS: storage.daily_usage(PROVIDER_NEWS, analysis_date),
    }

    content = render_report(
        date=analysis_date,
        news_items=result["news_items"],
        market_ctx=result["market_context"],
        sector_scores=result["sector_scores"],
        candidates=result["candidates"],
        ta_map=result["transaction_analysis"],
        request_usage=request_usage,
        config=config,
    )

    path = save_report(content, analysis_date, config)
    storage.save_report(
        analysis_date=analysis_date,
        report_type="daily",
        summary=result["market_context"].summary,
        recommendations="\n".join(c.symbol for c in result["candidates"][:5]),
        risks="",
        request_usage_summary=json.dumps(request_usage),
    )
    if json_output:
        payload = pipeline_result_to_dict(
            date=analysis_date,
            news_items=result["news_items"],
            market_context=result["market_context"],
            sector_scores=result["sector_scores"],
            candidates=result["candidates"],
            transaction_analysis=result["transaction_analysis"],
            request_usage=request_usage,
            report_path=path,
        )
        click.echo(json.dumps(payload, ensure_ascii=False))
    else:
        click.echo(f"Report saved: {path}")
        click.echo(f"API usage today — IDX: {request_usage[PROVIDER_IDX]}, News: {request_usage[PROVIDER_NEWS]}")

    storage.close()


@cli.command("latest-report")
@click.option("--date", default=None, help="Analysis date YYYY-MM-DD (default: today)")
@click.option("--json-output", is_flag=True, default=False,
              help="Print JSON with report metadata and content")
def latest_report(date: str, json_output: bool):
    """Print the latest saved markdown report for Hermes."""
    config = Config()
    analysis_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join(config.reports_dir, f"{analysis_date}-daily-report.md")
    if not os.path.exists(path):
        raise click.ClickException(f"Report not found: {path}")
    with open(path, encoding="utf-8") as f:
        content = f.read()
    if json_output:
        click.echo(json.dumps({"date": analysis_date, "report_path": path, "content": content}, ensure_ascii=False))
    else:
        click.echo(content)


@cli.command("stock-plan")
@click.argument("symbol", required=False)
@click.option("--date", default=None, help="Analysis date YYYY-MM-DD (default: today)")
@click.option("--mode", default=None, type=click.Choice(["conservative", "default", "expanded"]),
              help="Budget mode (overrides TA_BUDGET_MODE env var)")
@click.option("--fixture", is_flag=True, default=False,
              help="Use fixture data instead of live API calls")
@click.option("--json-output", is_flag=True, default=False,
              help="Print structured JSON for Hermes integration")
def stock_plan(symbol: str | None, date: str, mode: str, fixture: bool, json_output: bool):
    """Generate the latest top trade plan, or a plan for SYMBOL if present in candidates."""
    config = Config()
    if mode:
        config.budget_mode = mode
    analysis_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    storage = Storage(config)
    storage.init_schema()

    fixture_data = None
    registry = None
    if fixture:
        fixture_path = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "sample_data.json")
        fixture_path = os.path.normpath(fixture_path)
        with open(fixture_path, encoding="utf-8") as f:
            fixture_data = json.load(f)
    else:
        from .registry import build_live_registry
        registry = build_live_registry()

    client = DataClient(config, storage, fixture_data=fixture_data, registry=registry)
    pipeline = Pipeline(config, storage, client, analysis_date=analysis_date)
    result = pipeline.run()
    plan = find_trade_plan(result["candidates"], symbol)
    storage.close()

    if plan is None:
        label = symbol.upper() if symbol else "top candidate"
        raise click.ClickException(f"Trade plan not found for {label}")

    if json_output:
        click.echo(json.dumps({"date": analysis_date, "trade_plan": plan}, ensure_ascii=False))
        return

    click.echo(f"Trade Plan — {plan['symbol']} ({analysis_date})")
    if plan.get("entry_zone_low") and plan.get("entry_zone_high"):
        click.echo(f"Entry Zone : {plan['entry_zone_low']:,.0f} - {plan['entry_zone_high']:,.0f}")
    elif plan.get("entry_price"):
        click.echo(f"Entry Ref  : {plan['entry_price']:,.0f}")
    if plan.get("stop_loss"):
        click.echo(f"Stop Loss  : {plan['stop_loss']:,.0f}")
    if plan.get("take_profit_1"):
        click.echo(f"TP1        : {plan['take_profit_1']:,.0f}")
    if plan.get("take_profit_2"):
        click.echo(f"TP2        : {plan['take_profit_2']:,.0f}")
    if plan.get("risk_reward_ratio"):
        click.echo(f"RR         : {plan['risk_reward_ratio']:.2f}R")
    click.echo(f"Score      : {plan['final_score']:.2f}")


@cli.command("usage")
@click.option("--month", default=None, help="Month YYYY-MM (default: current month)")
def usage(month: str):
    """Show API request usage for the month."""
    config = Config()
    storage = Storage(config)
    storage.init_schema()

    ym = month or datetime.now(timezone.utc).strftime("%Y-%m")
    idx = storage.monthly_usage(PROVIDER_IDX, ym)
    news = storage.monthly_usage(PROVIDER_NEWS, ym)
    storage.close()

    click.echo(f"Usage for {ym}:")
    click.echo(f"  RapidAPI_IDX  : {idx:>4} / 1000")
    click.echo(f"  RapidAPI_News : {news:>4} / 100")


if __name__ == "__main__":
    cli()
