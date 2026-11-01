"""SQLite 单写入连接；每批事务提交，WAL 允许独立状态查询。"""

import sqlite3
from pathlib import Path

from .models import Candle, MINUTE_MS, now_ms, utc_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, interval TEXT NOT NULL,
    open_time_ms INTEGER NOT NULL, close_time_ms INTEGER NOT NULL,
    open TEXT NOT NULL, high TEXT NOT NULL, low TEXT NOT NULL, close TEXT NOT NULL,
    volume TEXT NOT NULL, quote_volume TEXT NOT NULL, trades INTEGER NOT NULL,
    taker_buy_volume TEXT NOT NULL, taker_buy_quote_volume TEXT NOT NULL,
    event_time_ms INTEGER NOT NULL, event_time_kind TEXT NOT NULL,
    collected_at_ms INTEGER NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('rest', 'websocket')),
    source_url TEXT NOT NULL, raw_payload TEXT NOT NULL,
    PRIMARY KEY (exchange, symbol, interval, open_time_ms),
    CHECK(exchange='binance' AND symbol='BTCUSDT' AND interval='1m'),
    CHECK(open_time_ms % 60000 = 0 AND close_time_ms = open_time_ms + 59999),
    CHECK(event_time_ms >= close_time_ms AND collected_at_ms >= 0)
);
PRAGMA user_version=1;
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=5)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def save(self, candles: list[Candle]) -> int:
        if not candles:
            return 0
        keys = list(candles[0].record())
        sql = f"INSERT INTO candles ({','.join(keys)}) VALUES ({','.join(':'+k for k in keys)}) ON CONFLICT DO NOTHING"
        before = self.connection.total_changes
        with self.connection:
            self.connection.executemany(sql, [c.record() for c in candles])
        return self.connection.total_changes - before

    def bounds(self) -> tuple[int | None, int | None]:
        row = self.connection.execute("SELECT MIN(open_time_ms), MAX(open_time_ms) FROM candles").fetchone()
        return row[0], row[1]

    def first_missing(self, start_ms: int, end_ms: int) -> int:
        cursor = start_ms
        for row in self.connection.execute(
            "SELECT open_time_ms FROM candles WHERE open_time_ms BETWEEN ? AND ? ORDER BY open_time_ms",
            (start_ms, end_ms),
        ):
            if row[0] != cursor:
                break
            cursor += MINUTE_MS
        return cursor


def database_status(path: Path) -> dict:
    # 只读查询，路径错误时不创建空库。
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        row = connection.execute(
            "SELECT COUNT(*) AS count, MIN(open_time_ms) AS first, MAX(open_time_ms) AS last, "
            "MAX(collected_at_ms) AS collected FROM candles"
        ).fetchone()
        latest = connection.execute("SELECT * FROM candles ORDER BY open_time_ms DESC LIMIT 1").fetchone()
        missing = 0 if not row["count"] else (row["last"] - row["first"]) // MINUTE_MS + 1 - row["count"]
        sources = {r[0]: r[1] for r in connection.execute("SELECT source_type, COUNT(*) FROM candles GROUP BY source_type")}
        return {
            "database": str(path.resolve()), "checked_at_utc": utc_iso(now_ms()),
            "integrity": connection.execute("PRAGMA quick_check").fetchone()[0],
            "rows": row["count"], "missing_minutes_between_first_and_last": missing,
            "first_open_utc": utc_iso(row["first"]), "latest_open_utc": utc_iso(row["last"]),
            "latest_close_utc": utc_iso(latest["close_time_ms"]) if latest else None,
            "latest_event_utc": utc_iso(latest["event_time_ms"]) if latest else None,
            "latest_collected_utc": utc_iso(row["collected"]),
            "latest_close_price": latest["close"] if latest else None,
            "latest_source_url": latest["source_url"] if latest else None,
            "latest_event_time_kind": latest["event_time_kind"] if latest else None,
            "seconds_since_latest_close": round((now_ms() - latest["close_time_ms"]) / 1000, 3) if latest else None,
            "source_rows": sources,
        }
    finally:
        connection.close()
