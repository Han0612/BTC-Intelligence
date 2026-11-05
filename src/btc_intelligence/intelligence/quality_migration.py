"""M2 质量修复追加迁移；原始表不删除，旧关联重算前留档。"""
def migrate(db):
    additions={
        'news_articles':{'content_type':"TEXT NOT NULL DEFAULT 'UNCLASSIFIED'",'discovery_kind':"TEXT NOT NULL DEFAULT 'LEGACY_UNCLASSIFIED'",'source_checked_at_ms':'INTEGER','discovery_delay_ms':'INTEGER','delay_quality':"TEXT NOT NULL DEFAULT 'LEGACY_UNKNOWN'",'verified_published_at_ms':'INTEGER','verified_time_basis':'TEXT'},
        'source_health':{'publisher_id':"TEXT NOT NULL DEFAULT ''",'access_status':"TEXT NOT NULL DEFAULT 'PUBLIC_RSS'",'last_http_status':'INTEGER','last_check_ms':'INTEGER','last_check_result':"TEXT NOT NULL DEFAULT 'NEVER'",'last_error_at_ms':'INTEGER'},
        'collection_runs':{'http_status':'INTEGER','check_result':"TEXT NOT NULL DEFAULT 'LEGACY'",'run_mode':"TEXT NOT NULL DEFAULT 'manual'",'duplicates':"INTEGER NOT NULL DEFAULT 0",'backfill_inserted':"INTEGER NOT NULL DEFAULT 0",'monitor_inserted':"INTEGER NOT NULL DEFAULT 0",'filter_stats':"TEXT NOT NULL DEFAULT '{}'"},
        'news_events':{'active':"INTEGER NOT NULL DEFAULT 1"},
    }
    for table,fields in additions.items():
        present={r[1] for r in db.execute('PRAGMA table_info('+table+')')}
        for name,definition in fields.items():
            if name not in present:db.execute('ALTER TABLE '+table+' ADD COLUMN '+name+' '+definition)
    sql='''
      CREATE TABLE IF NOT EXISTS event_link_history(event_id INTEGER,article_id INTEGER,reason TEXT,version TEXT,replaced_at_ms INTEGER,PRIMARY KEY(event_id,article_id,version));
      CREATE TABLE IF NOT EXISTS article_validations(id INTEGER PRIMARY KEY,article_id INTEGER NOT NULL REFERENCES news_articles(id),checked_at_ms INTEGER NOT NULL,http_status INTEGER,url_domain_match INTEGER NOT NULL,page_title TEXT,title_match INTEGER,page_published_raw TEXT,access_status TEXT NOT NULL,publisher_status TEXT NOT NULL,details TEXT NOT NULL,evidence_url TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS event_reviews(id INTEGER PRIMARY KEY,event_id INTEGER NOT NULL REFERENCES news_events(id),status TEXT NOT NULL CHECK(status IN ('REPORTED','CORROBORATED','OFFICIALLY_CONFIRMED','DISPUTED','UNVERIFIED')),claim TEXT NOT NULL,evidence_urls TEXT NOT NULL,rationale TEXT NOT NULL,reviewed_at_ms INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS validations_article ON article_validations(article_id,checked_at_ms);
      CREATE INDEX IF NOT EXISTS discoveries_kind_time ON news_articles(discovery_kind,first_seen_ms);
      CREATE TABLE IF NOT EXISTS article_time_history(article_id INTEGER NOT NULL REFERENCES news_articles(id),observation_key TEXT NOT NULL,observed_at_ms INTEGER NOT NULL,published_at_ms INTEGER,published_raw TEXT,time_quality TEXT NOT NULL,PRIMARY KEY(article_id,observation_key));
    '''
    for statement in sql.split(';'):
        if statement.strip():db.execute(statement)
    if 'anchor_article_id' not in {r[1] for r in db.execute('PRAGMA table_info(event_reviews)')}:
        db.execute('ALTER TABLE event_reviews ADD COLUMN anchor_article_id INTEGER REFERENCES news_articles(id)')
    db.execute('PRAGMA user_version=3')
