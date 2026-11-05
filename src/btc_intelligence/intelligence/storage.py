"""兼容 M1 的追加迁移；原始报道、事件关联和评论分析分表保存。"""
import json
import sqlite3
from pathlib import Path

from ..database import Store
from ..models import now_ms
from .analysis import classify_news, classify_comment, comment_relevance, same_event, RULE_VERSION
from .safety import digest
from .quality_migration import migrate

MIGRATION = """
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at_ms INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS news_articles(
 id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, external_id TEXT NOT NULL,
 title TEXT NOT NULL, summary TEXT NOT NULL, body TEXT,
 url TEXT NOT NULL, language TEXT NOT NULL, published_at_ms INTEGER,
 published_raw TEXT, time_quality TEXT NOT NULL,
 first_seen_ms INTEGER NOT NULL, collected_at_ms INTEGER NOT NULL,
 content_hash TEXT NOT NULL, origin TEXT NOT NULL,
 category TEXT NOT NULL, assets TEXT NOT NULL, relevance TEXT NOT NULL,
 importance TEXT NOT NULL, verification TEXT NOT NULL, paths TEXT NOT NULL,
 evidence TEXT NOT NULL, analysis_version TEXT NOT NULL,
 UNIQUE(source_id,external_id), UNIQUE(source_id,url)
);
CREATE INDEX IF NOT EXISTS news_published ON news_articles(published_at_ms);
CREATE INDEX IF NOT EXISTS news_seen ON news_articles(first_seen_ms);
CREATE INDEX IF NOT EXISTS news_category_time ON news_articles(category,published_at_ms);
CREATE TABLE IF NOT EXISTS article_revisions(
 article_id INTEGER NOT NULL REFERENCES news_articles(id), content_hash TEXT NOT NULL,
 observed_at_ms INTEGER NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
 PRIMARY KEY(article_id,content_hash)
);
CREATE TABLE IF NOT EXISTS news_events(
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
 importance TEXT NOT NULL, relevance TEXT NOT NULL, first_seen_ms INTEGER NOT NULL,
 last_seen_ms INTEGER NOT NULL, paths TEXT NOT NULL,
 aggregation_version TEXT NOT NULL, market_reaction_status TEXT NOT NULL DEFAULT 'NOT_MEASURED'
);
CREATE INDEX IF NOT EXISTS events_seen ON news_events(last_seen_ms);
CREATE TABLE IF NOT EXISTS news_event_links(
 event_id INTEGER NOT NULL REFERENCES news_events(id),
 article_id INTEGER NOT NULL REFERENCES news_articles(id),
 reason TEXT NOT NULL, PRIMARY KEY(event_id,article_id)
);
CREATE TABLE IF NOT EXISTS social_threads(
 platform TEXT NOT NULL, thread_id TEXT NOT NULL, title TEXT NOT NULL,
 url TEXT NOT NULL, source_url TEXT NOT NULL, discovery_source TEXT NOT NULL,
 published_at_ms INTEGER, first_seen_ms INTEGER NOT NULL, collected_at_ms INTEGER NOT NULL,
 metrics TEXT NOT NULL, PRIMARY KEY(platform,thread_id)
);
CREATE TABLE IF NOT EXISTS social_comments(
 platform TEXT NOT NULL, comment_id TEXT NOT NULL, thread_id TEXT NOT NULL,
 parent_id TEXT, body TEXT NOT NULL, author TEXT, url TEXT NOT NULL,
 source_url TEXT NOT NULL, published_at_ms INTEGER, first_seen_ms INTEGER NOT NULL,
 collected_at_ms INTEGER NOT NULL, language TEXT NOT NULL, relevance TEXT NOT NULL,
 metrics TEXT NOT NULL, content_hash TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(platform,comment_id), FOREIGN KEY(platform,thread_id) REFERENCES social_threads(platform,thread_id)
);
CREATE INDEX IF NOT EXISTS comments_published ON social_comments(platform,published_at_ms);
CREATE INDEX IF NOT EXISTS comments_seen ON social_comments(first_seen_ms);
CREATE TABLE IF NOT EXISTS sentiment_results(
 platform TEXT NOT NULL, comment_id TEXT NOT NULL, version TEXT NOT NULL,
 label TEXT NOT NULL CHECK(label IN ('BULLISH','BEARISH','NEUTRAL','UNKNOWN')),
 strength REAL NOT NULL, reason TEXT NOT NULL, analyzed_at_ms INTEGER NOT NULL,
 PRIMARY KEY(platform,comment_id,version), FOREIGN KEY(platform,comment_id) REFERENCES social_comments(platform,comment_id)
);
CREATE TABLE IF NOT EXISTS source_health(
 source_id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, url TEXT NOT NULL,
 enabled INTEGER NOT NULL, interval_seconds INTEGER NOT NULL, stale_hours INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'NEVER', last_attempt_ms INTEGER, last_success_ms INTEGER,
 first_success_ms INTEGER, last_published_ms INTEGER, last_error TEXT,
 consecutive_failures INTEGER NOT NULL DEFAULT 0, last_items INTEGER NOT NULL DEFAULT 0,
 last_inserted INTEGER NOT NULL DEFAULT 0, last_latency_ms INTEGER,
 etag TEXT, last_modified TEXT, next_allowed_ms INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS collection_runs(
 id INTEGER PRIMARY KEY, source_id TEXT NOT NULL, started_at_ms INTEGER NOT NULL,
 finished_at_ms INTEGER NOT NULL, status TEXT NOT NULL, fetched INTEGER NOT NULL,
 inserted INTEGER NOT NULL, error TEXT, latency_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_source_time ON collection_runs(source_id,started_at_ms);
CREATE TABLE IF NOT EXISTS source_state(
 source_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
 updated_at_ms INTEGER NOT NULL, PRIMARY KEY(source_id,key)
);
"""


class IntelStore:
    def __init__(self, path: Path):
        self.base = Store(path)
        self.db = self.base.connection
        self.db.execute("PRAGMA foreign_keys=ON")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version > 3:
            self.close()
            raise ValueError("数据库版本高于当前程序，拒绝迁移")
        try:
            self.db.executescript("BEGIN IMMEDIATE;" + MIGRATION)
            self.db.execute("INSERT OR IGNORE INTO schema_migrations VALUES (2,?)", (now_ms(),))
            migrate(self.db)
            self.db.execute("INSERT OR IGNORE INTO schema_migrations VALUES (3,?)",(now_ms(),))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            self.close()
            raise

    def close(self):
        self.base.close()

    def register(self, sources):
        with self.db:
            for s in sources:
                self.db.execute("""INSERT INTO source_health(source_id,name,kind,url,enabled,interval_seconds,stale_hours,status,last_error)
                 VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET
                 name=excluded.name,kind=excluded.kind,url=excluded.url,enabled=excluded.enabled,
                 interval_seconds=excluded.interval_seconds,stale_hours=excluded.stale_hours,
                 status=CASE WHEN excluded.enabled=0 THEN 'RESTRICTED' WHEN source_health.enabled=0 AND excluded.enabled=1 THEN 'NEVER' ELSE source_health.status END,
                 last_error=CASE WHEN excluded.enabled=0 THEN excluded.last_error ELSE source_health.last_error END""",
                 (s.id,s.name,s.kind,s.url,s.enabled,s.interval,s.stale_hours,"NEVER" if s.enabled else "RESTRICTED",s.restriction or None))
                self.db.execute("UPDATE source_health SET publisher_id=?,access_status=? WHERE source_id=?",(s.publisher_id or s.id,s.access_status if s.enabled or s.access_status=="NOT_CONFIGURED" else ("RESTRICTED" if s.restriction else "DISABLED"),s.id))

    def health(self, source_id):
        return dict(self.db.execute("SELECT * FROM source_health WHERE source_id=?", (source_id,)).fetchone())

    def state(self, source_id, key, default=None):
        row = self.db.execute("SELECT value FROM source_state WHERE source_id=? AND key=?", (source_id,key)).fetchone()
        return json.loads(row[0]) if row else default

    def set_state(self, source_id, key, value):
        self.db.execute("INSERT INTO source_state VALUES(?,?,?,?) ON CONFLICT(source_id,key) DO UPDATE SET value=excluded.value,updated_at_ms=excluded.updated_at_ms",
                        (source_id,key,json.dumps(value),now_ms()))

    def finish_run(self, source, started, status, fetched=0, inserted=0, error=None, published=None, headers=None, next_allowed=0, *, http_status=None, run_mode="manual", backfill=0, monitor=0, filters=None, check_result=None):
        end = now_ms()
        with self.db:
            self.db.execute("INSERT INTO collection_runs(source_id,started_at_ms,finished_at_ms,status,fetched,inserted,error,latency_ms) VALUES(?,?,?,?,?,?,?,?)",
                            (source.id,started,end,status,fetched,inserted,error,end-started))
            self.db.execute("""UPDATE source_health SET status=?,last_attempt_ms=?,last_items=?,last_inserted=?,last_latency_ms=?,
             last_error=?,consecutive_failures=CASE WHEN ?='OK' THEN 0 ELSE consecutive_failures+1 END,
             last_success_ms=CASE WHEN ?='OK' THEN ? ELSE last_success_ms END,
             first_success_ms=CASE WHEN ?='OK' THEN COALESCE(first_success_ms,?) ELSE first_success_ms END,
             last_published_ms=CASE WHEN ? IS NULL THEN last_published_ms ELSE MAX(COALESCE(last_published_ms,0),?) END,
             next_allowed_ms=? WHERE source_id=?""",
             (status,started,fetched,inserted,end-started,error,status,status,end,status,end,published,published,next_allowed,source.id))
            result=check_result or ("NOT_MODIFIED" if http_status==304 else ("HEALTHY" if status=="OK" else status))
            self.db.execute("UPDATE collection_runs SET http_status=?,check_result=?,run_mode=?,duplicates=?,backfill_inserted=?,monitor_inserted=?,filter_stats=? WHERE id=last_insert_rowid()",
                            (http_status,result,run_mode,max(0,fetched-inserted),backfill,monitor,json.dumps(filters or {})))
            self.db.execute("UPDATE source_health SET last_http_status=?,last_check_ms=?,last_check_result=?,last_error_at_ms=CASE WHEN ? IS NOT NULL THEN ? ELSE last_error_at_ms END WHERE source_id=?",
                            (http_status,end,result,error,end,source.id))
            if headers and status == "OK":
                self.db.execute("UPDATE source_health SET etag=COALESCE(?,etag),last_modified=COALESCE(?,last_modified) WHERE source_id=?",
                                (headers.get("etag"),headers.get("last-modified"),source.id))

    def save_articles(self, source, articles, *, run_mode="manual", checked_at=None, bootstrap=False, previous_check=None):
        inserted = 0
        with self.db:
            for article in articles:
                analysis = classify_news(article["title"],article["summary"],source.kind == "official")
                a = analysis.record()
                old = self.db.execute("SELECT * FROM news_articles WHERE source_id=? AND (external_id=? OR url=?)",
                                      (source.id,article["external_id"],article["url"])).fetchone()
                fields = dict(article,source_id=source.id,first_seen_ms=old["first_seen_ms"] if old else article["collected_at_ms"],
                              category=a["category"],content_type=a["content_type"],assets=json.dumps(a["assets"]),relevance=a["relevance"],importance=a["importance"],
                              verification=a["verification"],paths=json.dumps(a["paths"],ensure_ascii=False),
                              evidence=json.dumps(a["evidence"],ensure_ascii=False),analysis_version=RULE_VERSION)
                fields['source_checked_at_ms']=checked_at or article['collected_at_ms']
                if old:
                    delay=old['first_seen_ms']-article['published_at_ms'] if article['published_at_ms'] is not None else None
                    quality=old['delay_quality']
                    if delay is None:quality='MISSING_TIME'
                    elif delay<0:quality='NEGATIVE_TIME_ANOMALY'
                    elif old['published_at_ms']!=article['published_at_ms']:quality='SOURCE_TIME_CHANGED'
                    fields.update(discovery_delay_ms=delay,delay_quality=quality)
                if not old:
                    published=article["published_at_ms"]
                    if bootstrap:
                        discovery_kind="INITIAL_BACKFILL"
                    elif run_mode!="continuous":
                        discovery_kind="MANUAL_DISCOVERY"
                    elif not previous_check or (checked_at or article["collected_at_ms"])-previous_check>source.interval*3000:
                        discovery_kind="RECOVERY_BACKFILL"
                    elif published is not None and published<previous_check-source.interval*1000:
                        discovery_kind="LATE_SOURCE_ARRIVAL"
                    else:
                        discovery_kind="MONITOR_NEW"
                    delay=article["collected_at_ms"]-published if published is not None else None
                    delay_quality="MISSING_TIME" if delay is None else ("NEGATIVE_TIME_ANOMALY" if delay<0 else ("VALID_MONITOR" if discovery_kind=="MONITOR_NEW" else "EXCLUDED_"+discovery_kind))
                    fields.update(discovery_kind=discovery_kind,source_checked_at_ms=checked_at or article["collected_at_ms"],discovery_delay_ms=delay,delay_quality=delay_quality)
                if old:
                    # 来源 ID 改变时保持既有身份；更新时间和内容，首次发现时间不变。
                    fields["external_id"] = old["external_id"]
                    cols = [k for k in fields if k not in {"source_id","external_id","first_seen_ms"}]
                    self.db.execute("UPDATE news_articles SET " + ",".join(k+"=?" for k in cols) + " WHERE id=?",
                                    [fields[k] for k in cols] + [old["id"]])
                    article_id = old["id"]
                else:
                    cols = list(fields)
                    cursor = self.db.execute("INSERT INTO news_articles("+",".join(cols)+") VALUES("+",".join("?" for _ in cols)+")",[fields[k] for k in cols])
                    article_id = cursor.lastrowid
                    inserted += 1
                self.db.execute("INSERT OR IGNORE INTO article_revisions VALUES(?,?,?,?,?)",
                                (article_id,fields["content_hash"],fields["collected_at_ms"],fields["title"],fields["summary"]))
                for observation in ([dict(old)] if old else [])+[fields]:
                    key=digest(str(observation['published_at_ms'])+'|'+str(observation['published_raw'])+'|'+observation['time_quality'])
                    self.db.execute('INSERT OR IGNORE INTO article_time_history VALUES(?,?,?,?,?,?)',(article_id,key,observation['collected_at_ms'],observation['published_at_ms'],observation['published_raw'],observation['time_quality']))
                self._link_event(article_id,fields)
        return inserted

    def _link_event(self, article_id, article):
        existing = self.db.execute("SELECT event_id FROM news_event_links WHERE article_id=?", (article_id,)).fetchone()
        if existing:
            # 规则重算时更新单报道事件标签，保留原报道和修订记录。
            if self.db.execute("SELECT COUNT(*) FROM news_event_links WHERE event_id=?",(existing[0],)).fetchone()[0]==1:
                self.db.execute("UPDATE news_events SET category=?,importance=?,relevance=?,paths=?,aggregation_version=? WHERE id=?",
                                (article["category"],article["importance"],article["relevance"],article["paths"],RULE_VERSION,existing[0]))
            return
        stamp = article["published_at_ms"] or article["first_seen_ms"]
        candidates = self.db.execute("""SELECT DISTINCT e.* FROM news_events e JOIN news_event_links l ON l.event_id=e.id
         JOIN news_articles a ON a.id=l.article_id WHERE e.category=? AND ABS(COALESCE(a.published_at_ms,a.first_seen_ms)-?)<=129600000""",
                                    (article["category"],stamp)).fetchall()
        event = next((e for e in candidates if same_event(article["title"],e["title"],article["category"])),None)
        if event:
            event_id = event["id"]
            self.db.execute("UPDATE news_events SET last_seen_ms=MAX(last_seen_ms,?) WHERE id=?",(article["first_seen_ms"],event_id))
            reason = "同类事件、36小时内，标题共同实词和相似度满足保守阈值；仍需核实"
        else:
            event_id = self.db.execute("""INSERT INTO news_events(title,category,importance,relevance,first_seen_ms,last_seen_ms,paths,aggregation_version)
             VALUES(?,?,?,?,?,?,?,?)""",(article["title"],article["category"],article["importance"],article["relevance"],article["first_seen_ms"],article["first_seen_ms"],article["paths"],RULE_VERSION)).lastrowid
            reason = "首次报道建立候选事件；未推断因果或实际行情反应"
        self.db.execute("INSERT INTO news_event_links VALUES(?,?,?)", (event_id,article_id,reason))

    def save_thread(self, thread):
        cols = list(thread)
        updates = [k+"=excluded."+k for k in cols if k not in {"platform","thread_id","first_seen_ms"}]
        self.db.execute("INSERT INTO social_threads("+",".join(cols)+") VALUES("+",".join("?" for _ in cols)+") ON CONFLICT(platform,thread_id) DO UPDATE SET "+",".join(updates),[thread[k] for k in cols])

    def reanalyze(self):
        """仅重算本地分析字段，不改变原文、来源和三个外部数据时间。"""
        news_count,comment_count=0,0
        with self.db:
            for row in self.db.execute("SELECT a.*,s.kind FROM news_articles a JOIN source_health s ON s.source_id=a.source_id").fetchall():
                a=classify_news(row["title"],row["summary"],row["kind"]=="official").record()
                values={"category":a["category"],"content_type":a["content_type"],"relevance":a["relevance"],"importance":a["importance"],"verification":a["verification"],
                        "assets":json.dumps(a["assets"]),"paths":json.dumps(a["paths"],ensure_ascii=False),
                        "evidence":json.dumps(a["evidence"],ensure_ascii=False),"analysis_version":a["version"]}
                self.db.execute("UPDATE news_articles SET "+",".join(k+"=?" for k in values)+" WHERE id=?",[*values.values(),row["id"]])
                if row['published_at_ms'] is not None and row['published_at_ms']>row['first_seen_ms']:
                    self.db.execute("UPDATE news_articles SET discovery_delay_ms=first_seen_ms-published_at_ms,delay_quality='NEGATIVE_TIME_ANOMALY' WHERE id=?",(row['id'],))
                self._link_event(row["id"],dict(row,**values));news_count+=1
            for row in self.db.execute("SELECT c.*,t.title FROM social_comments c JOIN social_threads t USING(platform,thread_id) WHERE c.deleted=0").fetchall():
                result=classify_comment(row["body"],row["title"])
                self.db.execute("UPDATE social_comments SET relevance=? WHERE platform=? AND comment_id=?",
                                (comment_relevance(row["body"],row["title"]),row["platform"],row["comment_id"]))
                self.db.execute("INSERT OR REPLACE INTO sentiment_results VALUES(?,?,?,?,?,?,?)",
                                (row["platform"],row["comment_id"],result.version,result.label,result.strength,result.reason,now_ms()))
                comment_count+=1
        from .events import rebuild
        event_count=rebuild(self)
        return {"news_reanalyzed":news_count,"comments_reanalyzed":comment_count,"events":event_count,"version":RULE_VERSION,"external_requests":0}

    def save_comment(self, comment, sentiment):
        old = self.db.execute("SELECT 1 FROM social_comments WHERE platform=? AND comment_id=?", (comment["platform"],comment["comment_id"])).fetchone()
        cols = list(comment)
        updates = [k+"=excluded."+k for k in cols if k not in {"platform","comment_id","first_seen_ms"}]
        self.db.execute("INSERT INTO social_comments("+",".join(cols)+") VALUES("+",".join("?" for _ in cols)+") ON CONFLICT(platform,comment_id) DO UPDATE SET "+",".join(updates),[comment[k] for k in cols])
        self.db.execute("""INSERT INTO sentiment_results VALUES(?,?,?,?,?,?,?) ON CONFLICT(platform,comment_id,version)
         DO UPDATE SET label=excluded.label,strength=excluded.strength,reason=excluded.reason,analyzed_at_ms=excluded.analyzed_at_ms""",
                        (comment["platform"],comment["comment_id"],sentiment.version,sentiment.label,sentiment.strength,sentiment.reason,now_ms()))
        return int(not old)

    def mark_deleted(self, platform, comment_id):
        self.db.execute("UPDATE social_comments SET body='',author=NULL,deleted=1,collected_at_ms=? WHERE platform=? AND comment_id=?",(now_ms(),platform,comment_id))
        self.db.execute("DELETE FROM sentiment_results WHERE platform=? AND comment_id=?",(platform,comment_id))
