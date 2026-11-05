import asyncio
from dataclasses import replace
from types import SimpleNamespace

from btc_intelligence.config import Settings
from btc_intelligence.intelligence import cli
from btc_intelligence.intelligence.rss import parse_feed
from btc_intelligence.intelligence.storage import IntelStore
from btc_intelligence.models import now_ms
from test_m2_news import SOURCE,XML


def test_news_cli_handles_rss_null_body_and_separates_all_three_times(tmp_path,capsys,monkeypatch):
    path=tmp_path/'synthetic.sqlite3'
    store=IntelStore(path)
    store.register([SOURCE]);store.save_articles(SOURCE,parse_feed(XML,SOURCE,now_ms())[0])
    assert store.db.execute('SELECT body FROM news_articles').fetchone()[0] is None
    store.close()
    monkeypatch.setattr(cli,'load_sources',lambda:[SOURCE])
    args=SimpleNamespace(command='news-latest',hours=720,limit=1,json=False)
    assert asyncio.run(cli.execute(args,replace(Settings(),db_path=path)))==0
    output=capsys.readouterr().out
    assert 'FOMC' in output and all(label in output for label in ('原始发布 UTC','首次发现 UTC','最近采集 UTC'))
