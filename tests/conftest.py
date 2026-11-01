"""所有测试样本均为合成数据，只允许写入 pytest 临时目录。"""

import pytest

BASE_MS = 1_704_067_200_000  # 2024-01-01T00:00:00Z；合成样本，与真实采集隔离。


def synthetic_row(open_ms=BASE_MS):
    return [open_ms, "100", "110", "90", "105", "10", open_ms + 59999, "1000", 3, "4", "400", "0"]


def synthetic_event(open_ms=BASE_MS, closed=True):
    return {
        "e": "kline", "E": open_ms + 60001, "s": "BTCUSDT",
        "k": {"t": open_ms, "T": open_ms + 59999, "s": "BTCUSDT", "i": "1m",
              "o": "100", "h": "110", "l": "90", "c": "105", "v": "10", "q": "1000",
              "n": 3, "V": "4", "Q": "400", "x": closed},
    }


@pytest.fixture
def row():
    return synthetic_row()


@pytest.fixture
def event():
    return synthetic_event()
