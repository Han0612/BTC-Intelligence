"""REST 初始化及补洞 + 实时 WebSocket；所有写入串行经过同一 SQLite 连接。"""

import asyncio
import json
import logging
import random
from dataclasses import asdict, dataclass

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus, WebSocketException

from .collectors.binance import AccessDenied, BinanceREST, SourceError
from .config import Settings
from .database import Store
from .models import MINUTE_MS, now_ms, rest_candle, utc_iso, websocket_candle

log = logging.getLogger(__name__)


@dataclass
class Metrics:
    rest_syncs: int = 0
    rest_rows_inserted: int = 0
    ws_connections: int = 0
    ws_messages: int = 0
    ws_closed_messages: int = 0
    ws_rows_inserted: int = 0
    ws_reconnects: int = 0
    rejected_messages: int = 0


class Collector:
    def __init__(self, settings: Settings, store: Store, rest: BinanceREST):
        self.settings = settings
        self.store = store
        self.rest = rest
        self.metrics = Metrics()

    def backoff(self, failures: int) -> float:
        return min(2 ** min(failures, 10) + random.random(), self.settings.max_reconnect_delay)

    async def backfill(self) -> int:
        server_time = await self.rest.server_time()
        end_ms = (server_time // MINUTE_MS) * MINUTE_MS - 1
        first, _ = self.store.bounds()
        window_start = end_ms + 1 - self.settings.history_minutes * MINUTE_MS
        # 已有库从最早记录检查，重启后补齐停机期间及内部缺口。
        start_ms = self.store.first_missing(min(first, window_start) if first is not None else window_start, end_ms)
        inserted = 0
        source_url = self.settings.rest_url + "/api/v3/klines"
        while start_ms <= end_ms:
            rows = await self.rest.klines(start_ms, end_ms)
            collected = now_ms()
            candles = []
            cursor = start_ms
            for row in rows:
                try:
                    candle = rest_candle(row, server_time, collected, source_url)
                except (TypeError, ValueError) as exc:
                    raise SourceError(f"REST K 线校验失败：{exc}") from exc
                if candle is None or candle.open_time_ms != cursor or candle.close_time_ms > end_ms:
                    raise SourceError(f"REST 分钟数据缺失、未收盘或乱序，期望开盘时间 {utc_iso(cursor)}")
                candles.append(candle)
                cursor += MINUTE_MS
            if not candles:
                raise SourceError(f"REST 返回空数据，缺口开始于 {utc_iso(start_ms)}")
            inserted += self.store.save(candles)
            start_ms = cursor
            if start_ms <= end_ms:
                await asyncio.sleep(0.1)  # 保守限制补数请求速度。
        self.metrics.rest_syncs += 1
        self.metrics.rest_rows_inserted += inserted
        log.info("REST 同步完成：新增 %s 条已收盘 K 线，截至 %s", inserted, utc_iso(end_ms))
        return inserted

    async def rest_loop(self):
        failures = 0
        while True:
            try:
                await self.backfill()
                failures = 0
                await asyncio.sleep(self.settings.reconcile_seconds)
            except AccessDenied:
                raise
            except (SourceError, OSError) as exc:
                delay = self.backoff(failures)
                failures += 1
                log.error("REST 同步失败：%s；%.1f 秒后重试", exc, delay)
                await asyncio.sleep(delay)

    async def websocket_loop(self):
        url = self.settings.ws_url + "/ws/btcusdt@kline_1m"
        failures = 0
        while True:
            try:
                async with connect(
                    url, open_timeout=self.settings.ws_timeout,
                    close_timeout=5, ping_interval=20, ping_timeout=20,
                    max_queue=256, proxy=None,
                ) as ws:
                    self.metrics.ws_connections += 1
                    log.info("WebSocket 已连接：%s", url)
                    while True:
                        message = await asyncio.wait_for(ws.recv(), self.settings.ws_idle_timeout)
                        collected = now_ms()
                        try:
                            event = json.loads(message)
                            if isinstance(event, dict) and event.get("e") == "serverShutdown":
                                raise SourceError("交易所通知即将维护，重新连接")
                            candle = websocket_candle(event, collected, url)
                        except (ValueError, TypeError) as exc:
                            self.metrics.rejected_messages += 1
                            log.warning("拒绝异常 WebSocket 消息：%s", exc)
                            continue
                        failures = 0
                        self.metrics.ws_messages += 1
                        if candle:
                            self.metrics.ws_closed_messages += 1
                            inserted = self.store.save([candle])
                            self.metrics.ws_rows_inserted += inserted
                            log.info("WebSocket 收盘：%s，收盘价 %s，新增 %s 条", utc_iso(candle.open_time_ms), candle.close, inserted)
            except InvalidStatus as exc:
                if exc.response.status_code in {401, 403, 418, 451}:
                    raise AccessDenied(f"WebSocket 拒绝访问：HTTP {exc.response.status_code}；停止，不切换入口") from exc
                if exc.response.status_code == 429:
                    from .collectors.binance import retry_after_seconds
                    await asyncio.sleep(retry_after_seconds(exc.response.headers.get("Retry-After")))
                log.warning("WebSocket 握手失败：HTTP %s", exc.response.status_code)
            except (OSError, TimeoutError, ConnectionClosed, WebSocketException, SourceError) as exc:
                log.warning("WebSocket 连接中断或不可用：%s: %s", type(exc).__name__, exc)
            delay = self.backoff(failures)
            failures += 1
            self.metrics.ws_reconnects += 1
            log.info("WebSocket %.1f 秒后重连；REST 定时补齐缺口", delay)
            await asyncio.sleep(delay)

    async def run(self, stop: asyncio.Event, seconds: float | None = None) -> dict:
        tasks = [asyncio.create_task(self.rest_loop()), asyncio.create_task(self.websocket_loop())]
        waiter = asyncio.create_task(stop.wait())
        try:
            done, _ = await asyncio.wait([*tasks, waiter], timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
            for task in tasks:
                if task in done:
                    task.result()
        finally:
            for task in [*tasks, waiter]:
                task.cancel()
            await asyncio.gather(*tasks, waiter, return_exceptions=True)
        return asdict(self.metrics)
