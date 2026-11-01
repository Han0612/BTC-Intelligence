import asyncio
import json
from dataclasses import replace

import httpx
import pytest
from websockets.asyncio.client import connect as real_connect
from websockets.asyncio.server import serve

from btc_intelligence.collectors.binance import AccessDenied, BinanceREST, SourceError
from btc_intelligence.config import Settings, load_settings
from btc_intelligence.database import Store, database_status
from btc_intelligence.service import Collector
from conftest import BASE_MS, synthetic_event, synthetic_row


def test_pagination_idempotence_internal_gap_and_restart_backfill(tmp_path):
    async def scenario():
        settings = replace(Settings(), db_path=tmp_path / "synthetic.sqlite3", history_minutes=1005)
        server_ms = BASE_MS + 1005 * 60000 + 30000
        pages = []

        def handle(request):
            if request.url.path.endswith("/time"):
                return httpx.Response(200, json={"serverTime": server_ms})
            start, end = int(request.url.params["startTime"]), int(request.url.params["endTime"])
            rows = [synthetic_row(t) for t in range(start, min(end + 1, start + 1000 * 60000), 60000)]
            pages.append(len(rows))
            return httpx.Response(200, json=rows)

        store = Store(settings.db_path)
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                collector = Collector(settings, store, BinanceREST(settings, client))
                assert await collector.backfill() == 1005
                assert pages == [1000, 5]
                assert await collector.backfill() == 0
                with store.connection:
                    store.connection.execute("DELETE FROM candles WHERE open_time_ms=?", (BASE_MS + 300000,))
                assert await collector.backfill() == 1
                # 模拟停机 10 分钟，重启后补齐新增分钟。
                server_ms += 10 * 60000
                assert await collector.backfill() == 10
                status = database_status(settings.db_path)
                assert status["rows"] == 1015
                assert status["missing_minutes_between_first_and_last"] == 0
        finally:
            store.close()
    asyncio.run(scenario())


@pytest.mark.parametrize("status", [401, 403, 418, 451])
def test_access_restriction_stops_without_retry(status):
    async def scenario():
        calls = []
        def handle(request):
            calls.append(request)
            return httpx.Response(status, json={"msg": "synthetic access restriction"})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(AccessDenied):
                await BinanceREST(Settings(), client).server_time()
        assert len(calls) == 1
    asyncio.run(scenario())


def test_timeout_retry_and_rate_limit_respects_retry_after(monkeypatch):
    sleeps = []
    async def fake_sleep(delay):
        sleeps.append(delay)
    monkeypatch.setattr("btc_intelligence.collectors.binance.asyncio.sleep", fake_sleep)
    async def scenario():
        calls = 0
        def handle(request):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ReadTimeout("合成超时", request=request)
            if calls == 2:
                return httpx.Response(429, headers={"Retry-After": "7"})
            return httpx.Response(200, json={"serverTime": BASE_MS})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            assert await BinanceREST(Settings(), client).server_time() == BASE_MS
        assert calls == 3
        assert 7 in sleeps
    asyncio.run(scenario())


def test_websocket_disconnect_reconnect_invalid_and_duplicate_messages(tmp_path, monkeypatch):
    """真实本地 WebSocket 协议测试；消息为合成数据，不访问交易所。"""
    async def scenario():
        path = tmp_path / "synthetic.sqlite3"
        store = Store(path)
        connections = 0
        stop = asyncio.Event()
        async def handler(ws):
            nonlocal connections
            connections += 1
            await ws.send("{bad-json")
            await ws.send(json.dumps(synthetic_event(BASE_MS, closed=False)))
            await ws.send(json.dumps(synthetic_event(BASE_MS + (connections - 1) * 60000)))
            await ws.send(json.dumps(synthetic_event(BASE_MS + (connections - 1) * 60000)))
            if connections >= 2:
                # 等客户端处理第二次连接的数据。
                for _ in range(100):
                    if database_status(path)["rows"] == 2:
                        stop.set()
                        break
                    await asyncio.sleep(0.01)
            await ws.close()

        settings = replace(Settings(), db_path=path)
        # 本例单独验证 WebSocket，REST 任务替换为等待任务，不调用外部接口。
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            monkeypatch.setattr("btc_intelligence.service.connect", lambda url, **kw: real_connect(f"ws://127.0.0.1:{port}", **kw))
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as client:
                collector = Collector(replace(settings, history_minutes=1), store, BinanceREST(settings, client))
                monkeypatch.setattr(collector, "backoff", lambda failures: 0.01)
                async def synthetic_rest_loop():
                    collector.metrics.rest_syncs = 1
                    await asyncio.Event().wait()
                monkeypatch.setattr(collector, "rest_loop", synthetic_rest_loop)
                try:
                    metrics = await collector.run(stop, seconds=5)
                    assert stop.is_set()
                    assert metrics["ws_connections"] >= 2
                    assert metrics["ws_reconnects"] >= 1
                    assert metrics["ws_rows_inserted"] == 2
                    assert metrics["rejected_messages"] >= 2
                    assert database_status(path)["source_rows"] == {"websocket": 2}
                finally:
                    store.close()
    asyncio.run(scenario())


def test_rest_gap_is_reported_instead_of_claiming_success(tmp_path):
    async def scenario():
        settings = replace(Settings(), history_minutes=2)
        def handle(request):
            if request.url.path.endswith("/time"):
                return httpx.Response(200, json={"serverTime": BASE_MS + 120000})
            return httpx.Response(200, json=[synthetic_row(BASE_MS + 60000)])
        store = Store(tmp_path / "synthetic.sqlite3")
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                with pytest.raises(SourceError, match="缺失"):
                    await Collector(settings, store, BinanceREST(settings, client)).backfill()
            assert database_status(tmp_path / "synthetic.sqlite3")["rows"] == 0
        finally:
            store.close()
    asyncio.run(scenario())


def test_exhausted_timeouts_fail_explicitly(monkeypatch):
    async def no_wait(delay):
        pass
    monkeypatch.setattr("btc_intelligence.collectors.binance.asyncio.sleep", no_wait)
    async def scenario():
        calls = 0
        def handle(request):
            nonlocal calls
            calls += 1
            raise httpx.ConnectTimeout("合成连接超时", request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(SourceError, match="连续失败"):
                await BinanceREST(Settings(), client).server_time()
        assert calls == 3
    asyncio.run(scenario())


def test_fatal_restriction_cancels_other_task_and_propagates(tmp_path, monkeypatch):
    async def scenario():
        store = Store(tmp_path / "synthetic.sqlite3")
        cancelled = asyncio.Event()
        async with httpx.AsyncClient() as client:
            collector = Collector(Settings(), store, BinanceREST(Settings(), client))
            async def restricted_rest():
                await asyncio.sleep(0.01)
                raise AccessDenied("合成地域限制：451")
            async def waiting_ws():
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            monkeypatch.setattr(collector, "rest_loop", restricted_rest)
            monkeypatch.setattr(collector, "websocket_loop", waiting_ws)
            try:
                with pytest.raises(AccessDenied, match="451"):
                    await collector.run(asyncio.Event(), seconds=1)
                assert cancelled.is_set()
            finally:
                store.close()
    asyncio.run(scenario())


def test_configuration_is_local_and_validated(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("BTC_HISTORY_MINUTES=10\nBTC_LOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setenv("BTC_HISTORY_MINUTES", "20")
    assert load_settings(env).history_minutes == 20
    assert load_settings(env).log_level == "WARNING"
    for kwargs in ({"rest_url": "http://example.org"}, {"ws_url": "wss://testnet.binance.vision"}, {"http_timeout": float("nan")}, {"history_minutes": 0}):
        with pytest.raises(ValueError):
            Settings(**kwargs)
