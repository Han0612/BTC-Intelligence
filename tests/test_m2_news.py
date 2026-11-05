"""M2 合成样本/Mock 网络测试，全部使用临时数据库，绝不写生产数据。"""
import asyncio
from dataclasses import replace

import httpx
import pytest

from btc_intelligence.intelligence.config import Source,IntelConfig,load_sources
from btc_intelligence.intelligence.rss import parse_feed,timestamp
from btc_intelligence.intelligence.safety import clean_text,public_url,fetch_url,markdown_text
from btc_intelligence.intelligence.storage import IntelStore
from btc_intelligence.intelligence.service import IntelService
from btc_intelligence.intelligence.transport import Transport,FetchError
from btc_intelligence.models import now_ms

SOURCE=Source("fed","Federal Reserve","official","https://www.federalreserve.gov/feeds/press_all.xml")
XML=b'''<rss version="2.0"><channel><item><guid>synthetic-1</guid><title>Federal Reserve issues FOMC statement</title>
<link>https://www.federalreserve.gov/newsevents/pressreleases/synthetic.htm</link><description>&lt;p&gt;Interest rates decision&lt;/p&gt;</description>
<pubDate>Wed, 28 Oct 2026 18:00:00 GMT</pubDate></item></channel></rss>'''


def test_rss_normalization_and_missing_time():
    articles,rejected=parse_feed(XML,SOURCE,now_ms())
    assert rejected==0 and len(articles)==1
    assert articles[0]["summary"]=="Interest rates decision"
    assert articles[0]["body"] is None
    missing=XML.replace(b'<pubDate>Wed, 28 Oct 2026 18:00:00 GMT</pubDate>',b'')
    article=parse_feed(missing,SOURCE,now_ms())[0][0]
    assert article["published_at_ms"] is None and article["time_quality"]=="MISSING"


@pytest.mark.parametrize("raw,quality",[("not a date","INVALID"),("2026-01-01T00:00:00","MISSING_TIMEZONE"),("2099-01-01T00:00:00Z","INVALID_RANGE"),(None,"MISSING")])
def test_invalid_publication_times_are_never_replaced_with_collection_time(raw,quality):
    assert timestamp(raw,now_ms())==(None,quality)


@pytest.mark.parametrize("body",[b'<rss><broken>',b'<html>blocked</html>',b'<!DOCTYPE rss [<!ENTITY x "exploit">]><rss><channel>&x;</channel></rss>'])
def test_malformed_or_entity_xml_rejected(body):
    with pytest.raises(FetchError):
        parse_feed(body,SOURCE,now_ms())


def test_atom_and_no_date_are_supported():
    atom=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>test</id><title>Bitcoin ETF</title><link href="https://example.org/news"/><summary>Test</summary><published>2026-10-01T00:00:00Z</published></entry></feed>'''
    result,_=parse_feed(atom,Source("test","test","crypto","https://decrypt.co/feed"),now_ms())
    assert result[0]["url"]=="https://example.org/news"


@pytest.mark.parametrize("url",["file:///etc/passwd","http://127.0.0.1/","http://169.254.169.254/","https://user:secret@example.org/","http://localhost/","https://host.local/","https://example.org:8080/"])
def test_external_url_and_fetch_boundaries(url):
    with pytest.raises(ValueError):
        public_url(url)
    with pytest.raises(ValueError):
        fetch_url(url)


def test_html_is_plain_text_and_feed_never_downloads_links():
    assert clean_text('<script>bad()</script><p>BTC <b>market</b></p><img src="http://127.0.0.1/">')=='BTC market'
    assert public_url("https://example.org/a?utm_source=x&id=1#frag")=="https://example.org/a?id=1"
    with pytest.raises(ValueError):
        fetch_url("https://example.org/article")
    assert markdown_text('![private](http://127.0.0.1)')==r'\!\[private\]\(http://127\.0\.0\.1\)'
    with pytest.raises(ValueError):
        public_url("https://example.org/\x1b[2J")


def test_transport_timeout_retry_api_error_redirect_and_rate_limit(monkeypatch):
    async def no_wait(seconds):
        pass
    monkeypatch.setattr("btc_intelligence.intelligence.transport.asyncio.sleep",no_wait)
    async def scenario():
        count=0
        def timeout(request):
            nonlocal count
            count+=1
            raise httpx.ReadTimeout("合成超时",request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
            with pytest.raises(FetchError,match="ReadTimeout"):
                await Transport(client,IntelConfig()).get(SOURCE.url)
        assert count==2
        for status in (403,429,302,500):
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(status,headers={"Retry-After":"10","Location":"http://127.0.0.1"}))) as client:
                with pytest.raises(FetchError) as error:
                    await Transport(client,IntelConfig()).get(SOURCE.url)
                if status==429:
                    assert error.value.retry_at>=now_ms()+9000
    asyncio.run(scenario())


def test_source_failure_isolated_conditional_sync_and_empty_results(tmp_path):
    async def scenario():
        sources=[SOURCE,Source("decrypt","Decrypt","crypto","https://decrypt.co/feed")]
        store=IntelStore(tmp_path/"synthetic.sqlite3")
        seen=[]
        def handle(request):
            seen.append(request)
            if request.url.host=="decrypt.co":
                return httpx.Response(200,content=b'<html>bad feed</html>')
            if request.headers.get("If-None-Match")=="synthetic-etag":
                return httpx.Response(304)
            return httpx.Response(200,content=XML,headers={"ETag":"synthetic-etag"})
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                service=IntelService(store,sources,IntelConfig(),client)
                rows=await service.once("news")
                assert {r["status"] for r in rows}=={"OK","ERROR"}
                first=store.db.execute("SELECT first_seen_ms FROM news_articles").fetchone()[0]
                again=await service.collect_source(SOURCE)
                assert again["http_status"]==304 and again["inserted"]==0
                assert store.db.execute("SELECT first_seen_ms FROM news_articles").fetchone()[0]==first
                assert store.health("decrypt")["last_success_ms"] is None
                # 合法空 feed 为连接成功，不代表没有发生新闻。
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,content=b'<rss><channel/></rss>'))) as empty:
                    result=await IntelService(store,sources,IntelConfig(),empty).collect_source(sources[1])
                    assert result["status"]=="OK" and result["fetched"]==0
                assert store.db.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]==1
        finally:
            store.close()
    asyncio.run(scenario())


def test_source_configuration_loads_official_whitelist_and_conservative_intervals():
    sources=load_sources()
    assert {"wsj","bloomberg","reuters","wallstreetcn","fed","hn"}<=set(s.id for s in sources)
    assert all(s.interval>=120 for s in sources)
