"""最终复验的合成回归：主张级确认不得扩散到整组及其他进展。"""
import json
from dataclasses import replace

import pytest

from btc_intelligence.intelligence.analysis import Sentiment
from btc_intelligence.intelligence.config import Source
from btc_intelligence.intelligence.queries import event_rows, source_health, sentiment_stats
from btc_intelligence.intelligence.report import brief
from btc_intelligence.intelligence.rss import parse_feed
from btc_intelligence.intelligence.storage import IntelStore
from btc_intelligence.models import now_ms
from test_m2_news import SOURCE,XML


def test_official_claim_does_not_confirm_entire_incident_group_or_other_details(tmp_path):
    store=IntelStore(tmp_path/'synthetic.sqlite3')
    sources=[replace(SOURCE,id='synthetic_'+str(i),kind='crypto') for i in range(3)]
    try:
        store.register(sources)
        base=parse_feed(XML,sources[0],now_ms())[0][0]
        titles=['FBI blames North Korea for Binance $6.3B hack',
                'Binance withdrawals resume after $6.3B hack',
                'THORChain RUNE jumps 13% after Binance $6.3B hack']
        for i,(source,title) in enumerate(zip(sources,titles)):
            store.save_articles(source,[dict(base,title=title,url=f'https://example.org/synthetic/{i}',external_id=str(i),published_at_ms=now_ms()-10000)])
        store.reanalyze()
        group=event_rows(store,24)[0]
        anchor=group['evidence'][0]['id']
        with store.db:
            store.db.execute('''INSERT INTO event_reviews(event_id,status,claim,evidence_urls,rationale,reviewed_at_ms,anchor_article_id)
             VALUES(?,?,?,?,?,?,?)''',(group['id'],'OFFICIALLY_CONFIRMED','合成测试：仅确认被盗及归因，不确认其他细节',json.dumps(['https://www.fbi.gov/synthetic']), '合成核验依据',now_ms(),anchor))
        group=event_rows(store,24)[0]
        assert (group['article_count'],group['source_count'],group['independent_publisher_count'])==(3,3,3)
        assert group['corroboration_status']=='REPORTED'
        assert group['claim_reviews'][0]['status']=='OFFICIALLY_CONFIRMED'
        assert group['independent_subevent_count'] is None
        assert any(e['development_kind']=='REPORTED_MARKET_REACTION' and e['detail_verification_status']=='UNVERIFIED' for e in group['evidence'])
        assert all(e['unreviewed_details_remain'] for e in group['evidence'])
        report=brief(store)
        assert '组级状态：REPORTED' in report and '主张级 OFFICIALLY_CONFIRMED' in report
        assert '组级状态：OFFICIALLY_CONFIRMED' not in report
        # 一条后续未核实主张不能覆盖、丢失另一条已确认主张。
        with store.db:
            store.db.execute('''INSERT INTO event_reviews(event_id,status,claim,evidence_urls,rationale,reviewed_at_ms,anchor_article_id)
             VALUES(?,?,?,?,?,?,?)''',(group['id'],'UNVERIFIED','合成测试：提现比例尚未核实','[]','没有对应一手确认',now_ms(),group['evidence'][1]['id']))
        statuses={r['status'] for r in event_rows(store,24)[0]['claim_reviews']}
        assert statuses=={'OFFICIALLY_CONFIRMED','UNVERIFIED'}
    finally:
        store.close()


@pytest.mark.parametrize('source_id', ['cnbc', 'wsj', 'decrypt'])
def test_health_uses_success_age_separately_from_article_age(tmp_path, monkeypatch, source_id):
    """合成时间边界：旧文章不等于网络故障；停采超过阈值也不能继续健康。"""
    stamp = 1_800_000_000_000
    monkeypatch.setattr('btc_intelligence.intelligence.storage.now_ms', lambda: stamp)
    source = replace(SOURCE, id=source_id, interval=300, stale_hours=48)
    store = IntelStore(tmp_path / 'synthetic-health.sqlite3')
    try:
        store.register([source])
        store.finish_run(source, stamp - 1000, 'OK', published=stamp - 15 * 3600000, http_status=200)
        fresh = source_health(store, at=stamp)[0]
        assert fresh['health_status'] == 'HEALTHY'
        assert not fresh['network_stale'] and not fresh['content_stale']
        assert source_health(store, at=stamp + 900000)[0]['health_status'] == 'HEALTHY'
        stopped = source_health(store, at=stamp + 900001)[0]
        assert stopped['health_status'] == 'STALE'
        assert stopped['network_stale'] and not stopped['content_stale']
        assert stopped['connection_status'] == 'HEALTHY'  # 最近一次检查结果，非当前连通承诺。
        assert stopped['last_success_ms'] == stamp
    finally:
        store.close()


def test_automatic_poll_can_discover_item_published_just_before_previous_check(tmp_path):
    """合成回归复现轮询边界，不将 RSS 单条观测称为延迟分布。"""
    published = 1_800_000_000_000
    discovered = published + 307648
    previous_check = published + 6718
    request_start = published + 306802
    store = IntelStore(tmp_path / 'synthetic-monitor.sqlite3')
    try:
        store.register([SOURCE])
        base = parse_feed(XML, SOURCE, discovered)[0][0]
        store.save_articles(
            SOURCE, [dict(base, published_at_ms=published)],
            run_mode='continuous', checked_at=request_start,
            bootstrap=False, previous_check=previous_check,
        )
        row = store.db.execute('SELECT * FROM news_articles').fetchone()
        assert row['discovery_kind'] == 'MONITOR_NEW'
        assert row['delay_quality'] == 'VALID_MONITOR'
        assert row['discovery_delay_ms'] == 307648
        health = source_health(store, at=discovered)[0]
        assert health['monitor_delay_samples'] == 1
        assert health['monitor_delay_seconds']['min'] == 307.648
    finally:
        store.close()


def test_seven_unknown_comments_produce_no_direction_or_score(tmp_path):
    """合成评论只写临时库；Unknown 不转为 Neutral 或方向性信号。"""
    store = IntelStore(tmp_path / 'synthetic-comments.sqlite3')
    stamp = now_ms()
    try:
        store.register([Source('hn', 'Synthetic HN', 'social', 'https://hacker-news.firebaseio.com/v0/')])
        store.save_thread(dict(
            platform='hn', thread_id='synthetic', title='Bitcoin market discussion',
            url='https://news.ycombinator.com/item?id=1',
            source_url='https://hacker-news.firebaseio.com/v0/item/1.json',
            discovery_source='合成测试', published_at_ms=stamp - 1000,
            first_seen_ms=stamp, collected_at_ms=stamp, metrics='{}',
        ))
        for index in range(7):
            store.save_comment(dict(
                platform='hn', comment_id=str(index), thread_id='synthetic', parent_id=None,
                body='合成歧义样本', author=None, url='https://news.ycombinator.com/item?id=1',
                source_url='https://hacker-news.firebaseio.com/v0/item/1.json',
                published_at_ms=stamp - 1000, first_seen_ms=stamp, collected_at_ms=stamp,
                language='zh', relevance='RELEVANT', metrics='{}', content_hash=str(index),
            ), Sentiment('UNKNOWN', 0, '合成标签，测试统计边界'))
        result = sentiment_stats(store, stamp - 86400000, stamp, min_samples=20)[0]
        assert result['count'] == 7 and result['counts']['UNKNOWN'] == 7
        assert result['counts']['NEUTRAL'] == 0
        assert result['direction_sample_size'] == result['score_sample_size'] == 0
        assert result['score'] is None and result['signal'] == '暂无可信情绪信号'
    finally:
        store.close()
