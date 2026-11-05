import asyncio
import json
from dataclasses import replace

import httpx
import pytest

from btc_intelligence.database import Store
from btc_intelligence.models import now_ms,rest_candle
from btc_intelligence.intelligence.analysis import RULE_VERSION
from btc_intelligence.intelligence.config import Source,IntelConfig
from btc_intelligence.intelligence.rss import parse_feed
from btc_intelligence.intelligence.storage import IntelStore
from btc_intelligence.intelligence.service import IntelService
from btc_intelligence.intelligence.queries import source_health,stats,event_rows,coverage
from btc_intelligence.intelligence.report import brief
from conftest import synthetic_row,BASE_MS
from test_m2_news import XML,SOURCE


def test_repeatable_additive_migration_preserves_m1_and_schema_version(tmp_path):
    path=tmp_path/"synthetic.sqlite3"
    original=Store(path)
    original.save([rest_candle(synthetic_row(),BASE_MS+90000,BASE_MS+90000,"https://test.invalid")])
    before=tuple(original.connection.execute("SELECT * FROM candles").fetchone());original.close()
    for _ in range(2):
        store=IntelStore(path)
        assert tuple(store.db.execute("SELECT * FROM candles").fetchone())==before
        assert store.db.execute("PRAGMA user_version").fetchone()[0]==3
        store.close()
    original=Store(path)
    assert original.connection.execute("PRAGMA user_version").fetchone()[0]==3
    original.close()


def test_news_identity_revisions_and_cross_publisher_evidence_kept(tmp_path):
    store=IntelStore(tmp_path/"synthetic.sqlite3")
    try:
        s1=Source("test1","test1","macro","https://decrypt.co/feed")
        s2=replace(s1,id="test2")
        store.register([s1,s2])
        articles,_=parse_feed(XML,s1,now_ms())
        assert store.save_articles(s1,articles)==1
        first=store.db.execute("SELECT first_seen_ms FROM news_articles").fetchone()[0]
        assert store.save_articles(s1,articles)==0
        articles[0]["collected_at_ms"]+=1000
        articles[0]["summary"]+=" Updated synthetic statement"
        articles[0]["content_hash"]="synthetic-updated-hash"
        assert store.save_articles(s1,articles)==0
        assert store.db.execute("SELECT COUNT(*) FROM article_revisions").fetchone()[0]==2
        assert store.db.execute("SELECT first_seen_ms FROM news_articles").fetchone()[0]==first
        articles[0]["origin"]="test2"
        assert store.save_articles(s2,articles)==1
        assert store.db.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]==2
        assert store.db.execute("SELECT COUNT(*) FROM news_events").fetchone()[0]==1
        assert store.db.execute("SELECT COUNT(*) FROM news_event_links").fetchone()[0]==2
        event=event_rows(store,hours=720)[0]
        assert event["publisher_count"]==2
        assert event["independent_candidates"]==1  # 相同标题/正文转载不能视为两个证据。
        before=[tuple(r) for r in store.db.execute("SELECT id,title,first_seen_ms,collected_at_ms,published_at_ms FROM news_articles ORDER BY id")]
        store.reanalyze();store.reanalyze()
        assert before==[tuple(r) for r in store.db.execute("SELECT id,title,first_seen_ms,collected_at_ms,published_at_ms FROM news_articles ORDER BY id")]
    finally:
        store.close()


HN=Source("hn","Hacker News","social","https://hacker-news.firebaseio.com/v0/")


def hn_mock(deleted=False):
    timestamp=now_ms()//1000-60
    data={
        "1":{"id":1,"type":"story","title":"Bitcoin price outlook","time":timestamp,"kids":[2,3],"score":5,"descendants":3},
        "2":{"id":2,"type":"comment","parent":1,"time":timestamp,"by":"synthetic-user","text":"I am buying BTC.","kids":[4]},
        "3":{"id":3,"type":"comment","parent":1,"time":timestamp,"text":"Signatures and cryptography are clever."},
        "4":{"id":4,"type":"comment","parent":2,"time":timestamp,"text":"I am shorting BTC."},
    }
    if deleted:
        data["2"]={"id":2,"type":"comment","deleted":True}
    def handle(request):
        if request.url.host=="hn.algolia.com":
            return httpx.Response(200,json={"hits":[{"objectID":"1"}]})
        key=request.url.path.rsplit("/",1)[-1].split(".")[0]
        return httpx.Response(200,json=data.get(key))
    return handle


def test_real_comment_structure_incremental_queue_filter_dedup_and_deletion(tmp_path):
    async def scenario():
        store=IntelStore(tmp_path/"synthetic.sqlite3")
        try:
            config=replace(IntelConfig(),hn_items=1,hn_threads=1)
            async with httpx.AsyncClient(transport=httpx.MockTransport(hn_mock())) as client:
                service=IntelService(store,[HN],config,client)
                for _ in range(4):
                    assert (await service.once("social"))[0]["status"]=="OK"
            rows=store.db.execute("SELECT * FROM social_comments ORDER BY comment_id").fetchall()
            assert [r["comment_id"] for r in rows]==["2","4"]
            assert rows[0]["body"]=="I am buying BTC." and rows[0]["parent_id"]=="1"
            assert rows[1]["parent_id"]=="2" and rows[1]["thread_id"]=="1"
            assert rows[0]["url"]=="https://news.ycombinator.com/item?id=2"
            assert "firebaseio.com" in rows[0]["source_url"]
            first=rows[0]["first_seen_ms"]
            async with httpx.AsyncClient(transport=httpx.MockTransport(hn_mock(deleted=True))) as client:
                await IntelService(store,[HN],replace(config,hn_items=20),client).once("social")
            row=store.db.execute("SELECT * FROM social_comments WHERE comment_id='2'").fetchone()
            assert row["deleted"]==1 and row["body"]=="" and row["author"] is None and row["first_seen_ms"]==first
            assert not store.db.execute("SELECT 1 FROM sentiment_results WHERE comment_id='2'").fetchone()
        finally:
            store.close()
    asyncio.run(scenario())


def test_sentiment_failure_preserves_comment_as_unknown_and_marks_partial(tmp_path,monkeypatch):
    def broken(*args):
        raise RuntimeError("合成分类故障")
    monkeypatch.setattr("btc_intelligence.intelligence.social.classify_comment",broken)
    async def scenario():
        store=IntelStore(tmp_path/"synthetic.sqlite3")
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(hn_mock())) as client:
                result=await IntelService(store,[HN],IntelConfig(),client).once("social")
            assert result[0]["status"]=="PARTIAL"
            assert store.db.execute("SELECT COUNT(*) FROM social_comments").fetchone()[0]==2
            assert {r[0] for r in store.db.execute("SELECT label FROM sentiment_results")}=={"UNKNOWN"}
        finally:
            store.close()
    asyncio.run(scenario())


def test_comment_search_only_discovers_ids_official_text_and_parent_chain_are_authoritative(tmp_path):
    async def scenario():
        store=IntelStore(tmp_path/"synthetic.sqlite3")
        stamp=now_ms()//1000-60
        def handle(request):
            if request.url.host=="hn.algolia.com":
                hits=[{"objectID":"2","story_id":1,"comment_text":"不可信索引文本，不能入库"}] if request.url.params.get('tags')=='comment' else []
                return httpx.Response(200,json={"hits":hits})
            key=request.url.path.rsplit('/',1)[-1]
            items={'1.json':{'id':1,'type':'story','title':'Central bank policy discussion','time':stamp,'kids':[8]},
                   '2.json':{'id':2,'type':'comment','parent':3,'time':stamp,'text':'I am buying Bitcoin.'},
                   '3.json':{'id':3,'type':'comment','parent':1,'time':stamp,'text':'Parent context'}}
            return httpx.Response(200,json=items.get(key))
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                result=await IntelService(store,[HN],IntelConfig(),client).once('social')
            assert result[0]['status']=='OK'
            row=store.db.execute('SELECT * FROM social_comments').fetchone()
            assert row['body']=='I am buying Bitcoin.' and row['thread_id']=='1' and row['parent_id']=='3'
        finally:
            store.close()
    asyncio.run(scenario())


def test_statistics_minimum_samples_staleness_windows_and_report(tmp_path):
    async def scenario():
        store=IntelStore(tmp_path/"synthetic.sqlite3")
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(hn_mock())) as client:
                await IntelService(store,[HN],IntelConfig(),client).once("social")
            output=stats(store,hours=24,min_samples=20)
            row=output["sentiment"][0]
            assert row["count"]==2 and row["topics"]==1
            assert row["score"] is None and row["sample_status"]=="样本不足"
            assert row["counts"]["BULLISH"]==1 and row["counts"]["BEARISH"]==1
            # 降低阈值仅为合成统计验证；生产默认仍为 20。
            assert stats(store,hours=24,min_samples=2)["sentiment"][0]["score"]==0
            assert "历史" not in output["time_basis"] or "原始" in output["time_basis"]
            assert "样本不足"==coverage(store,"hn",now_ms()-86400000,now_ms())
            with store.db:
                store.db.execute("UPDATE source_health SET last_success_ms=?,last_published_ms=?",(now_ms()-86400000,now_ms()-100*3600000))
            health=source_health(store)[0]
            assert health["network_stale"] and health["content_stale"] and health["quality"]=="不完整"
            report=brief(store,hours=24)
            for required in ("全球重要事件","宏观及地缘风险","直接相关新闻","社区情绪","异常监控","数据质量","样本不足","不完整"):
                assert required in report
        finally:
            store.close()
    asyncio.run(scenario())


def test_scheduler_single_source_error_does_not_stop_others_and_cancels_cleanly(tmp_path,monkeypatch):
    async def scenario():
        store=IntelStore(tmp_path/"synthetic.sqlite3")
        sources=[SOURCE,Source("decrypt","Decrypt","crypto","https://decrypt.co/feed")]
        calls=[]
        async with httpx.AsyncClient() as client:
            service=IntelService(store,sources,IntelConfig(),client)
            async def fake(source):
                calls.append(source.id)
                store.finish_run(source,now_ms(),"ERROR" if source.id=="decrypt" else "OK")
                return {"status":"ERROR" if source.id=="decrypt" else "OK"}
            monkeypatch.setattr(service,"collect_source",fake)
            try:
                await service.run(asyncio.Event(),seconds=0.03)
                assert set(calls)=={"fed","decrypt"}
            finally:
                store.close()
    asyncio.run(scenario())


def test_scheduler_recovers_after_api_failure_and_cancelled_fetch_is_recorded(tmp_path):
    async def scenario():
        store=IntelStore(tmp_path/"synthetic.sqlite3")
        # 仅测试缩短周期，生产配置读取强制 >=120 秒。
        source=replace(SOURCE,interval=1)
        calls=0
        def handle(request):
            nonlocal calls
            calls+=1
            return httpx.Response(503) if calls==1 else httpx.Response(200,content=XML)
        try:
            async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                await IntelService(store,[source],replace(IntelConfig(),retries=1),client).run(asyncio.Event(),seconds=1.2)
            assert calls>=2 and store.health(source.id)["status"]=="OK"
            assert [r[0] for r in store.db.execute("SELECT status FROM collection_runs ORDER BY id")][:2]==["ERROR","OK"]
            async def slow(request):
                await asyncio.sleep(10)
                return httpx.Response(200,content=XML)
            async with httpx.AsyncClient(transport=httpx.MockTransport(slow)) as client:
                await IntelService(store,[source],IntelConfig(),client).run(asyncio.Event(),seconds=0.02)
            assert store.health(source.id)["status"]=="CANCELLED"
            assert store.db.execute("SELECT COUNT(*) FROM news_articles").fetchone()[0]==1
        finally:
            store.close()
    asyncio.run(scenario())
