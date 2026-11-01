import json
import sqlite3

import pytest

from btc_intelligence.database import Store, database_status
from btc_intelligence.models import rest_candle, utc_iso, websocket_candle
from conftest import BASE_MS, synthetic_row


def test_only_closed_candles_and_event_time_semantics(row, event):
    assert rest_candle(row, row[6], row[6], "https://test.invalid") is None
    event["k"]["x"] = False
    assert websocket_candle(event, BASE_MS + 90000, "wss://test.invalid") is None
    event["k"]["x"] = True
    ws = websocket_candle(event, BASE_MS + 90000, "wss://test.invalid")
    rest = rest_candle(row, BASE_MS + 90000, BASE_MS + 90001, "https://test.invalid")
    assert ws.event_time_ms == event["E"]
    assert ws.event_time_kind == "exchange_event"
    assert rest.event_time_ms == row[6]
    assert rest.event_time_kind == "candle_close"
    assert json.loads(ws.raw_payload) == event
    assert utc_iso(BASE_MS) == "2024-01-01T00:00:00.000Z"


@pytest.mark.parametrize("field,value", [(1, "NaN"), (1, 100.0), (2, "99"), (3, "106"), (5, "-1"), (0, BASE_MS + 1), (8, -1), (9, "11")])
def test_reject_invalid_rest(row, field, value):
    row[field] = value
    with pytest.raises(ValueError):
        rest_candle(row, BASE_MS + 90000, BASE_MS + 90000, "https://test.invalid")


@pytest.mark.parametrize("mutation", ["symbol", "interval", "closed_type", "missing_price", "event_time"])
def test_reject_invalid_websocket(event, mutation):
    if mutation == "symbol":
        event["s"] = "ETHUSDT"
    elif mutation == "interval":
        event["k"]["i"] = "5m"
    elif mutation == "closed_type":
        event["k"]["x"] = "true"
    elif mutation == "missing_price":
        del event["k"]["c"]
    else:
        event["E"] = BASE_MS
    with pytest.raises(ValueError):
        websocket_candle(event, BASE_MS + 90000, "wss://test.invalid")


def test_dedup_persistence_provenance_and_gap_detection(tmp_path):
    path = tmp_path / "synthetic.sqlite3"
    store = Store(path)
    candles = [rest_candle(synthetic_row(BASE_MS + i * 60000), BASE_MS + 300000, BASE_MS + 300001, "https://test.invalid") for i in (0, 2)]
    assert store.save(candles) == 2
    assert store.save(candles) == 0
    assert store.first_missing(BASE_MS, BASE_MS + 179999) == BASE_MS + 60000
    store.close()
    status = database_status(path)
    assert status["rows"] == 2
    assert status["missing_minutes_between_first_and_last"] == 1
    assert status["integrity"] == "ok"
    assert status["source_rows"] == {"rest": 2}
    store = Store(path)
    assert store.save(candles) == 0
    record = dict(store.connection.execute("SELECT * FROM candles LIMIT 1").fetchone())
    assert record["close"] == "105"
    assert record["collected_at_ms"] == BASE_MS + 300001
    assert json.loads(record["raw_payload"])[0] == BASE_MS
    store.close()


def test_status_missing_database_does_not_create_file(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        database_status(path)
    assert not path.exists()
