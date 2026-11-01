"""Binance 公开现货 REST 与 WebSocket；不使用账户或交易接口。"""

import asyncio
import logging
from email.utils import parsedate_to_datetime
from datetime import UTC, datetime

import httpx

from ..config import Settings

log = logging.getLogger(__name__)


class SourceError(RuntimeError):
    """接口暂时不可用或响应不符合协议。"""


class AccessDenied(SourceError):
    """访问限制；停止采集，禁止自动换地址绕行。"""


def retry_after_seconds(value: str | None) -> float:
    if not value:
        return 1
    try:
        return max(1, float(value))
    except ValueError:
        try:
            return max(1, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 1


class BinanceREST:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    async def request(self, path: str, params: dict | None = None):
        url = self.settings.rest_url + path
        for attempt in range(3):
            delay = min(2 ** attempt, self.settings.max_reconnect_delay)
            try:
                response = await self.client.get(url, params=params)
                if response.status_code in {401, 403, 418, 451}:
                    raise AccessDenied(f"官方接口拒绝访问：HTTP {response.status_code}，地址 {url}；停止，不切换入口")
                if response.status_code == 429:
                    delay = retry_after_seconds(response.headers.get("Retry-After"))
                    # 最后一次仍要遵守冷却时间，防止外层循环过早重试。
                    await asyncio.sleep(delay)
                    raise SourceError("官方接口限流：HTTP 429，已遵守 Retry-After")
                response.raise_for_status()
                result = response.json()
                if isinstance(result, dict) and "code" in result:
                    raise SourceError(f"Binance 接口错误：{result.get('code')} {result.get('msg')}")
                return result
            except AccessDenied:
                raise
            except (httpx.HTTPError, ValueError, SourceError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                    raise SourceError(f"请求参数或接口错误：HTTP {exc.response.status_code}") from exc
                if attempt == 2:
                    raise SourceError(f"REST 请求连续失败：{url}；{type(exc).__name__}: {exc}") from exc
                log.warning("REST 请求失败，第 %s/3 次：%s；等待 %.1f 秒", attempt + 1, exc, delay)
                await asyncio.sleep(delay)

    async def server_time(self) -> int:
        result = await self.request("/api/v3/time")
        if not isinstance(result, dict) or type(result.get("serverTime")) is not int or result["serverTime"] <= 0:
            raise SourceError("服务器时间响应无效")
        return result["serverTime"]

    async def klines(self, start_ms: int, end_ms: int) -> list:
        result = await self.request("/api/v3/klines", {
            "symbol": "BTCUSDT", "interval": "1m", "startTime": start_ms,
            "endTime": end_ms, "limit": 1000,
        })
        if not isinstance(result, list):
            raise SourceError("K 线响应不是列表")
        return result
