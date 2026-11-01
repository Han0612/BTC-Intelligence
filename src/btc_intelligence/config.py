"""仅从项目 .env 和进程环境读取非敏感配置。"""

import math
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path("data/btc.sqlite3")
    log_dir: Path = Path("logs")
    log_level: str = "INFO"
    rest_url: str = "https://data-api.binance.vision"
    ws_url: str = "wss://data-stream.binance.vision:443"
    history_minutes: int = 500
    http_timeout: float = 10
    ws_timeout: float = 15
    ws_idle_timeout: float = 30
    reconcile_seconds: float = 60
    max_reconnect_delay: float = 60

    def __post_init__(self):
        # 固定官方地址，拒绝误配为测试网、非加密地址或携带凭据的 URL。
        if self.rest_url not in {"https://api.binance.com", "https://data-api.binance.vision"}:
            raise ValueError("REST 地址必须是已支持的 Binance 官方公开行情入口")
        if self.ws_url not in {
            "wss://data-stream.binance.vision:443",
            "wss://stream.binance.com:443",
            "wss://stream.binance.com:9443",
        }:
            raise ValueError("WebSocket 地址必须是已支持的 Binance 官方公开行情入口")
        if not 1 <= self.history_minutes <= 10080:
            raise ValueError("历史初始化范围须为 1～10080 分钟")
        for name in ("http_timeout", "ws_timeout", "ws_idle_timeout", "reconcile_seconds", "max_reconnect_delay"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} 必须是有限正数")
        if self.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("日志级别无效")


def load_settings(env_file: Path = Path(".env")) -> Settings:
    values = {}
    if env_file.exists():
        for number, line in enumerate(env_file.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if not sep:
                raise ValueError(f".env 第 {number} 行缺少等号")
            values[key.strip()] = value.strip().strip("\"'")
    values.update(os.environ)
    defaults = Settings()
    fields = {
        "db_path": Path, "log_dir": Path, "log_level": str,
        "rest_url": str, "ws_url": str, "history_minutes": int,
        "http_timeout": float, "ws_timeout": float, "ws_idle_timeout": float,
        "reconcile_seconds": float, "max_reconnect_delay": float,
    }
    return Settings(**{
        field: convert(values.get("BTC_" + field.upper(), str(getattr(defaults, field))))
        for field, convert in fields.items()
    })
