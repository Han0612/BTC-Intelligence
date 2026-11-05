import argparse
import asyncio
import json
import logging
import math
import signal
import sqlite3
import sys

import httpx

from .collectors.binance import BinanceREST, SourceError
from .config import load_settings
from .database import Store, database_status
from .logging_setup import setup_logging
from .service import Collector
from .intelligence.cli import COMMANDS,add_commands,execute


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("运行秒数必须是有限正数")
    return number


async def collect(settings, command: str, seconds: float | None) -> int:
    store = Store(settings.db_path)
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False, follow_redirects=False) as client:
            collector = Collector(settings, store, BinanceREST(settings, client))
            if command == "backfill":
                inserted = await collector.backfill()
                print(f"历史初始化/补数完成：新增 {inserted} 条真实已收盘 K 线。")
                return 0
            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop.set)
            try:
                metrics = await collector.run(stop, seconds)
            finally:
                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.remove_signal_handler(sig)
            print("本次采集统计（真实接口）：" + json.dumps(metrics, ensure_ascii=False))
            if not metrics["rest_syncs"] or not metrics["ws_messages"]:
                logging.error("本次运行未同时验证成功 REST 和 WebSocket，请检查日志")
                return 1
            return 0
    finally:
        store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="BTC Intelligence：M1 真实行情与 M2 全球新闻、社区情报")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backfill", help="通过官方 REST 初始化历史并补齐缺口")
    run = commands.add_parser("run", help="持续采集；Ctrl+C 或 SIGTERM 安全停止")
    run.add_argument("--seconds", type=positive_seconds, help="限时运行，用于真实接口验收")
    status = commands.add_parser("status", help="只读查看数据库条数、来源、缺口和新鲜度")
    status.add_argument("--json", action="store_true", help="输出 JSON 状态")
    add_commands(commands,positive_seconds)
    args = parser.parse_args()
    try:
        settings = load_settings()
        if args.command in COMMANDS:
            setup_logging(settings)
            return asyncio.run(execute(args,settings))
        if args.command == "status":
            result = database_status(settings.db_path)
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"数据库：{result['database']}\n实际条数：{result['rows']}\n完整性：{result['integrity']}\n"
                      f"最早开盘 UTC：{result['first_open_utc']}\n最新开盘 UTC：{result['latest_open_utc']}\n"
                      f"最新收盘 UTC：{result['latest_close_utc']}\n最新采集 UTC：{result['latest_collected_utc']}\n"
                      f"最新收盘价：{result['latest_close_price']} USDT\n来源统计：{result['source_rows']}\n"
                      f"记录范围内缺失分钟数：{result['missing_minutes_between_first_and_last']}\n"
                      f"距最新收盘：{result['seconds_since_latest_close']} 秒（判断数据是否陈旧）")
            return 0 if result["integrity"] == "ok" else 1
        setup_logging(settings)
        return asyncio.run(collect(settings, args.command, getattr(args, "seconds", None)))
    except (ValueError, OSError, sqlite3.Error, SourceError) as exc:
        print(f"执行失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("已停止，已提交的数据保留。")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
