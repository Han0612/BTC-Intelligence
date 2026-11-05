"""合成的连续两窗口数据，用于检验异常阈值及故障时不输出误导结论。"""
import json
from dataclasses import replace

from btc_intelligence.models import now_ms
from btc_intelligence.intelligence.analysis import Sentiment
from btc_intelligence.intelligence.config import Source
from btc_intelligence.intelligence.queries import stats
from btc_intelligence.intelligence.storage import IntelStore
from btc_intelligence.intelligence.rss import parse_feed
from test_m2_news import SOURCE,XML


def test_heat_and_sentiment_candidates_require_continuous_coverage_and_minimum_samples(tmp_path):
    store=IntelStore(tmp_path/"synthetic.sqlite3")
    hn=Source('hn','Hacker News','social','https://hacker-news.firebaseio.com/v0/')
    end=now_ms();current=end-3600000;previous=current-3600000
    try:
        store.register([SOURCE,hn])
        with store.db:
            for source in (SOURCE,hn):
                store.db.execute("UPDATE source_health SET status='OK',first_success_ms=?,last_success_ms=? WHERE source_id=?",(previous-300000,end,source.id))
                for stamp in range(previous-300000,end+1,300000):
                    store.db.execute("INSERT INTO collection_runs(source_id,started_at_ms,finished_at_ms,status,fetched,inserted,latency_ms) VALUES(?,?,?,'OK',1,0,1)",(source.id,stamp,stamp))
            store.save_thread({'platform':'hn','thread_id':'synthetic','title':'Bitcoin market discussion','url':'https://news.ycombinator.com/item?id=1','source_url':'https://hacker-news.firebaseio.com/v0/item/1.json','discovery_source':'合成测试','published_at_ms':previous,'first_seen_ms':previous,'collected_at_ms':end,'metrics':'{}'})
            for prefix,start,count,label in [('old',previous,20,'BULLISH'),('new',current,40,'BEARISH')]:
                for index in range(count):
                    stamp=start+1000+index*1000
                    comment={'platform':'hn','comment_id':prefix+str(index),'thread_id':'synthetic','parent_id':None,'body':'合成市场观点','author':None,'url':'https://news.ycombinator.com/item?id=1','source_url':'https://hacker-news.firebaseio.com/v0/item/1.json','published_at_ms':stamp,'first_seen_ms':stamp,'collected_at_ms':stamp,'language':'zh','relevance':'RELEVANT','metrics':'{}','content_hash':prefix+str(index)}
                    store.save_comment(comment,Sentiment(label,0.8,'合成标签，专门测试统计'))
        original=parse_feed(XML,SOURCE,end)[0][0]
        articles=[]
        for prefix,start,count in [('old',previous,5),('new',current,10)]:
            for index in range(count):
                articles.append(dict(original,external_id=prefix+str(index),url=f'https://www.federalreserve.gov/synthetic/{prefix}/{index}',published_at_ms=start+1000+index*1000))
        store.save_articles(SOURCE,articles)
        output=stats(store,hours=1,min_samples=20,at=end)
        kinds={row['kind'] for row in output['alerts']}
        assert {'新闻类别密度上升候选','讨论量上升候选','情绪占比变化候选'}<=kinds
        with store.db:
            store.db.execute("UPDATE source_health SET status='ERROR'")
        degraded=stats(store,hours=1,min_samples=20,at=end)
        assert degraded['density_comparison']=='不完整'
        assert not any(row['kind'] in kinds for row in degraded['alerts'])
    finally:
        store.close()
