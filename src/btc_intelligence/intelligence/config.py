import math
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .safety import fetch_url


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    kind: str
    url: str
    interval: int = 300
    stale_hours: int = 48
    enabled: bool = True
    restriction: str = ""
    publisher_id: str = ""
    access_status: str = "PUBLIC_RSS"


@dataclass(frozen=True)
class IntelConfig:
    timeout: float = 12
    retries: int = 2
    concurrency: int = 4
    hn_threads: int = 20
    hn_items: int = 120
    hn_lookback_days: int = 30
    min_samples: int = 20


def load_intel_config() -> IntelConfig:
    # .env 仅为简单键值，不执行文本；进程环境优先。
    env = {}
    if Path(".env").exists():
        for line in Path(".env").read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                env[key.strip()] = value.strip().strip("\"'")
    env.update(os.environ)
    converters = {"timeout": float, "retries": int, "concurrency": int, "hn_threads": int,
                  "hn_items": int, "hn_lookback_days": int, "min_samples": int}
    default = IntelConfig()
    values = {k: t(env.get("BTC_INTEL_" + k.upper(), str(getattr(default, k)))) for k, t in converters.items()}
    for key, value in values.items():
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"BTC_INTEL_{key.upper()} 必须为有限正数")
    if values["retries"] > 3 or values["concurrency"] > 8 or values["hn_items"] > 500 or values["hn_threads"] > 100:
        raise ValueError("采集并发或批次超出保守限制")
    return IntelConfig(**values)


def load_sources(path: Path = Path("config/sources.toml")) -> list[Source]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    sources = [Source(**row) for row in data["sources"]]
    ids = [s.id for s in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("来源 ID 重复")
    for source in sources:
        if source.interval < 120 or source.stale_hours < 1:
            raise ValueError("来源间隔不得低于 120 秒，新鲜度阈值至少 1 小时")
        if source.enabled:
            fetch_url(source.url)
    return sources
