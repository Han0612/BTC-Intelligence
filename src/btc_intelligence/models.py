"""不可变的已收盘 K 线；价格保留十进制原文，避免浮点误差。"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

MINUTE_MS = 60_000


def now_ms() -> int:
    return int(datetime.now(UTC).timestamp() * 1000)


def utc_iso(timestamp_ms: int | None) -> str | None:
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class Candle:
    exchange: str
    symbol: str
    interval: str
    open_time_ms: int
    close_time_ms: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    quote_volume: str
    trades: int
    taker_buy_volume: str
    taker_buy_quote_volume: str
    event_time_ms: int
    event_time_kind: str
    collected_at_ms: int
    source_type: str
    source_url: str
    raw_payload: str

    def __post_init__(self):
        if (self.exchange, self.symbol, self.interval) != ("binance", "BTCUSDT", "1m"):
            raise ValueError("M1 只接收 Binance BTCUSDT 1m")
        if any(type(v) is not int or v < 0 for v in (
            self.open_time_ms, self.close_time_ms, self.event_time_ms, self.collected_at_ms, self.trades
        )):
            raise ValueError("时间戳与成交笔数必须为非负整数")
        if self.open_time_ms % MINUTE_MS or self.close_time_ms != self.open_time_ms + MINUTE_MS - 1:
            raise ValueError("K 线时间边界无效")
        if self.event_time_ms < self.close_time_ms:
            raise ValueError("收盘事件早于 K 线收盘时间")
        expected_kind = {"rest": "candle_close", "websocket": "exchange_event"}
        if expected_kind.get(self.source_type) != self.event_time_kind:
            raise ValueError("数据来源与事件时间语义不匹配")
        decimal_fields = (
            self.open, self.high, self.low, self.close, self.volume,
            self.quote_volume, self.taker_buy_volume, self.taker_buy_quote_volume,
        )
        if any(not isinstance(v, str) for v in decimal_fields):
            raise ValueError("价格与成交量必须保留接口的十进制字符串")
        try:
            values = [Decimal(v) for v in decimal_fields]
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("价格或成交量无效") from exc
        if any(not v.is_finite() or v < 0 for v in values) or any(v <= 0 for v in values[:4]):
            raise ValueError("价格必须为有限正数，成交量必须为有限非负数")
        o, h, low, c = values[:4]
        if not low <= min(o, c) <= max(o, c) <= h:
            raise ValueError("OHLC 价格关系无效")
        if values[6] > values[4] or values[7] > values[5]:
            raise ValueError("主动买入量超过总成交量")

    def record(self) -> dict:
        return asdict(self)


def rest_candle(row: list, server_time_ms: int, collected_at_ms: int, source_url: str) -> Candle | None:
    if not isinstance(row, list) or len(row) < 11:
        raise ValueError("REST K 线结构无效")
    if type(row[6]) is not int:
        raise ValueError("REST 收盘时间无效")
    if row[6] >= server_time_ms:
        return None
    return Candle(
        "binance", "BTCUSDT", "1m", row[0], row[6],
        *row[1:6], row[7], row[8], row[9], row[10],
        row[6], "candle_close", collected_at_ms, "rest", source_url,
        json.dumps(row, separators=(",", ":")),
    )


def websocket_candle(event: dict, collected_at_ms: int, source_url: str) -> Candle | None:
    if not isinstance(event, dict) or event.get("e") != "kline":
        raise ValueError("WebSocket 事件不是 K 线")
    k = event.get("k")
    if not isinstance(k, dict) or type(k.get("x")) is not bool:
        raise ValueError("WebSocket K 线结构无效")
    if event.get("s") != "BTCUSDT" or k.get("s") != "BTCUSDT" or k.get("i") != "1m":
        raise ValueError("WebSocket 交易对或周期不匹配")
    if not k["x"]:
        return None
    try:
        return Candle(
            "binance", "BTCUSDT", "1m", k["t"], k["T"],
            k["o"], k["h"], k["l"], k["c"], k["v"], k["q"], k["n"], k["V"], k["Q"],
            event["E"], "exchange_event", collected_at_ms, "websocket", source_url,
            json.dumps(event, separators=(",", ":")),
        )
    except KeyError as exc:
        raise ValueError(f"WebSocket K 线缺少字段 {exc}") from exc
