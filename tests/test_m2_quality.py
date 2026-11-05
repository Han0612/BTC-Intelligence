"""明确的合成质量回归；所有存储均为临时文件，不混入真实采集。"""
import asyncio
import json
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from btc_intelligence.intelligence.analysis import classify_news
from btc_intelligence.intelligence.config import Source,IntelConfig
from btc_intelligence.intelligence.events import evidence_counts
from btc_intelligence.intelligence.queries import event_rows,source_health,stats
from btc_intelligence.intelligence.rss import parse_feed
from btc_intelligence.intelligence.service import IntelService
from btc_intelligence.intelligence.storage import IntelStore
from btc_intelligence.intelligence.validation import audit_article
from btc_intelligence.models import now_ms
from test_m2_news import SOURCE,XML
from btc_intelligence.intelligence.analysis import classify_comment
from btc_intelligence.intelligence.evaluation import CASES as SENTIMENT_CASES

CASES=json.loads((Path(__file__).parent/'fixtures/news-quality-cases.json').read_text())


@pytest.mark.parametrize('text,label',SENTIMENT_CASES[-12:])
def test_stance_subject_negation_quote_and_position_quality(text,label):
    assert classify_comment(text,'Bitcoin price outlook').label==label


@pytest.mark.parametrize('case',CASES,ids=[r['title'] for r in CASES])
def test_layered_news_quality(case):
    result=classify_news(case['title']).record()
    for key in ('relevance','importance','category'):
        assert result[key]==case[key]
    assert bool(result['paths'])==(result['relevance'] in {'DIRECT','INDIRECT'} and result['category']!='CRYPTO')
    if result['relevance']=='INDIRECT':
        assert result['content_type'].startswith('MAJOR_') and result['paths']


def evidence(source,origin=None,publisher=None,index=0,title=None):
    return {'id':index,'source_id':source,'origin':origin or source,'publisher_id':publisher or source,
            'title':title or f'独立原始标题 {index}','content_hash':str(index),'published_at_ms':now_ms()+index,'first_seen_ms':now_ms()}


def test_article_source_publisher_counts_are_distinct_and_representatives_match():
    one=[evidence('a',index=i) for i in range(3)]
    result=evidence_counts(one)
    assert (result['article_count'],result['source_count'],result['independent_publisher_count'])==(3,1,1)
    three=[evidence(source,index=i) for i,source in enumerate(['a','b','c'])]
    result=evidence_counts(three)
    assert (result['article_count'],result['source_count'],result['independent_publisher_count'])==(3,3,3)
    assert len({r['source_id'] for r in result['representative_evidence']})==3
    wire=[evidence(source,origin='wire:Reuters',index=i) for i,source in enumerate(['a','b','c'])]
    assert evidence_counts(wire)['independent_publisher_count']==1
    same_parent=[evidence('channel'+str(i),publisher='same_parent',index=i) for i in range(3)]
    assert evidence_counts(same_parent)['source_count']==3
    assert evidence_counts(same_parent)['independent_publisher_count']==1


def test_two_day_followup_same_event_different_incident_not_merged_and_evidence_kept(tmp_path):
    store=IntelStore(tmp_path/'synthetic.sqlite3')
    sources=[replace(SOURCE,id='a',kind='crypto'),replace(SOURCE,id='b',kind='crypto'),replace(SOURCE,id='c',kind='crypto')]
    try:
        store.register(sources);article=parse_feed(XML,sources[0],now_ms())[0][0]
        titles=['Binance confirms a $6.3B hack','Binance withdrawals resume after $6.3B hack','Binance confirms a separate $2B hack']
        for i,(source,title) in enumerate(zip(sources,titles)):
            store.save_articles(source,[dict(article,title=title,url=f'https://example.org/{i}',external_id=str(i),published_at_ms=now_ms()-(2-i)*86400000)])
        store.reanalyze()
        memberships=[r[0] for r in store.db.execute('SELECT event_id FROM news_event_links ORDER BY article_id')]
        assert memberships[0]==memberships[1] and memberships[2]!=memberships[0]
        assert store.db.execute('SELECT COUNT(*) FROM news_articles').fetchone()[0]==3
        assert store.db.execute('SELECT COUNT(*) FROM news_event_links').fetchone()[0]==3
        assert store.db.execute('SELECT COUNT(*) FROM event_link_history').fetchone()[0]>=3
        ids=[tuple(r) for r in store.db.execute('SELECT event_id,article_id FROM news_event_links ORDER BY article_id')]
        store.reanalyze()
        assert ids==[tuple(r) for r in store.db.execute('SELECT event_id,article_id FROM news_event_links ORDER BY article_id')]
        for row in event_rows(store,168):
            assert row['corroboration_status']=='REPORTED'  # 多家媒体绝不自动官方确认。
    finally:store.close()


def test_public_metadata_match_does_not_confirm_facts_and_restriction_is_not_fake():
    async def scenario():
        article={'id':1,'source_id':'cnbc','url':'https://www.cnbc.com/synthetic','title':'Bitcoin ETF approval'}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,text='<html><head><meta property="og:title" content="Bitcoin ETF approval"></head></html>'))) as client:
            result=await audit_article(client,article)
            assert result['publisher_status']=='PUBLISHER_PAGE_MATCH' and '不证明' in result['details']
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(403))) as client:
            result=await audit_article(client,article)
            assert result['access_status']=='RESTRICTED' and result['publisher_status']=='UNVERIFIED'
        unsafe=dict(article,url='http://127.0.0.1/secret')
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:pytest.fail('不应请求本机'))) as client:
            assert not (await audit_article(client,unsafe))['url_domain_match']
    asyncio.run(scenario())


def test_304_check_and_stale_history_are_different_and_failures_not_masked(tmp_path):
    async def scenario():
        store=IntelStore(tmp_path/'synthetic.sqlite3')
        try:
            source=replace(SOURCE,stale_hours=24)
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(304))) as client:
                service=IntelService(store,[source],IntelConfig(),client)
                with store.db:
                    store.db.execute('UPDATE source_health SET last_published_ms=?',(now_ms()-48*3600000,))
                await service.once('news')
                row=source_health(store)[0]
                assert row['health_status']=='STALE' and row['connection_status']=='NOT_MODIFIED'
                assert row['last_http_status']==304 and store.health(source.id)['last_success_ms']
                with store.db:store.db.execute('UPDATE source_health SET last_published_ms=?',(now_ms(),))
                assert source_health(store)[0]['health_status']=='NOT_MODIFIED'
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(503))) as client:
                await IntelService(store,[source],replace(IntelConfig(),retries=1),client).once('news')
            assert source_health(store)[0]['health_status']=='HTTP_ERROR'
        finally:store.close()
    asyncio.run(scenario())


def test_initial_manual_recovery_negative_and_monitor_delays_are_separate(tmp_path):
    store=IntelStore(tmp_path/'synthetic.sqlite3')
    try:
        store.register([SOURCE]);stamp=now_ms();base=parse_feed(XML,SOURCE,stamp)[0][0]
        examples=[('initial',stamp-1000000,True,'continuous',stamp-300000),('manual',stamp-2000,False,'manual',stamp-300000),('recovery',stamp-2000,False,'continuous',stamp-2000000),('negative',stamp+1000,False,'continuous',stamp-300000),('monitor',stamp-2000,False,'continuous',stamp-300000)]
        for key,published,bootstrap,mode,previous in examples:
            store.save_articles(SOURCE,[dict(base,external_id=key,url=f'https://www.federalreserve.gov/{key}',published_at_ms=published)],run_mode=mode,checked_at=stamp,bootstrap=bootstrap,previous_check=previous)
        assert store.db.execute("SELECT COUNT(*) FROM news_articles WHERE delay_quality='VALID_MONITOR'").fetchone()[0]==1
        assert store.db.execute("SELECT delay_quality FROM news_articles WHERE external_id='negative'").fetchone()[0]=='NEGATIVE_TIME_ANOMALY'
        assert source_health(store)[0]['monitor_delay_samples']==1
        old=store.db.execute("SELECT first_seen_ms,discovery_kind FROM news_articles WHERE external_id='monitor'").fetchone()
        store.save_articles(SOURCE,[dict(base,external_id='monitor',url='https://www.federalreserve.gov/monitor',collected_at_ms=stamp+5000)])
        assert tuple(old)==tuple(store.db.execute("SELECT first_seen_ms,discovery_kind FROM news_articles WHERE external_id='monitor'").fetchone())
    finally:store.close()
