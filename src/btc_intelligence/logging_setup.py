import logging
import time
from logging.handlers import RotatingFileHandler

from .config import Settings


def setup_logging(settings: Settings) -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s %(message)s", "%Y-%m-%dT%H:%M:%S")
    formatter.converter = time.gmtime
    console = logging.StreamHandler()
    file = RotatingFileHandler(settings.log_dir / "collector.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    for handler in (console, file):
        handler.setFormatter(formatter)
    logging.basicConfig(level=settings.log_level, handlers=[console, file], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
