"""分平台窗口统计和保守异常候选，不把接入成功等同于完整覆盖。"""
import json

from ..models import now_ms, utc_iso
from .analysis import RULE_VERSION
from .safety import digest

LABELS = ("BULLISH","BEARISH","NEUTRAL","UNKNOWN")


def latest_news(store,hours=24,limit=10):
    rows=[dict(r) for r in store.db.execute("""SELECT a.*,s.name AS source_name FROM news_articles a
     JOIN source_health s ON s.source_id=a.source_id
     WHERE COALESCE(a.verified_published_at_ms,a.published_at_ms,a.first_seen_ms)>=? ORDER BY COALESCE(a.verified_published_at_ms,a.published_at_ms,a.first_seen_ms) DESC LIMIT ?""",
                                            (now_ms()-hours*3600000,limit))]
    for row in rows:
        audit=store.db.execute('SELECT * FROM article_validations WHERE article_id=? ORDER BY checked_at_ms DESC,id DESC LIMIT 1',(row['id'],)).fetchone()
        row['collection_status']='COLLECTED'
        row['effective_published_at_ms']=row['verified_published_at_ms'] or row['published_at_ms']
        row['publication_time_basis']=row['verified_time_basis'] or 'RSS源报告时间，未独立核实初始发布时间'
        row['page_validation']=dict(audit) if audit else {'publisher_status':'NOT_CHECKED','access_status':'NOT_CHECKED'}
    return rows


def latest_comments(store,hours=24,limit=10):
    return [dict(r) for r in store.db.execute("""SELECT c.*,t.title AS thread_title,r.label,r.reason,r.strength FROM social_comments c
     JOIN social_threads t USING(platform,thread_id) LEFT JOIN sentiment_results r
     ON r.platform=c.platform AND r.comment_id=c.comment_id AND r.version=?
     WHERE c.deleted=0 AND c.relevance='RELEVANT' AND c.published_at_ms>=?
     ORDER BY c.published_at_ms DESC LIMIT ?""",(RULE_VERSION,now_ms()-hours*3600000,limit))]


def source_health(store,at=None):
    at = now_ms() if at is None else at
    output=[]
    for r in store.db.execute("SELECT * FROM source_health ORDER BY kind,source_id"):
        row=dict(r)
        row["network_stale"] = row["last_success_ms"] is None or at-row["last_success_ms"] > max(row["interval_seconds"]*3,900)*1000
        row["content_stale"] = row["last_published_ms"] is None or at-row["last_published_ms"] > row["stale_hours"]*3600000
        row["published_age_hours"] = round((at-row["last_published_ms"])/3600000,2) if row["last_published_ms"] else None
        row["collection_lag_seconds"] = round((row["last_attempt_ms"]-row["last_published_ms"])/1000,1) if row["last_published_ms"] and row["last_attempt_ms"] else None
        # 请求延迟和发布至发现延迟是不同指标。
        delay=store.db.execute("SELECT MIN(first_seen_ms-published_at_ms),MAX(first_seen_ms-published_at_ms) FROM news_articles WHERE source_id=? AND published_at_ms IS NOT NULL",(row["source_id"],)).fetchone()
        row["discovery_delay_min_seconds"]=round(delay[0]/1000,1) if delay[0] is not None else None
        row["discovery_delay_max_seconds"]=round(delay[1]/1000,1) if delay[1] is not None else None
        row["article_rows"]=store.db.execute("SELECT COUNT(*) FROM news_articles WHERE source_id=?",(row["source_id"],)).fetchone()[0]
        row["comment_rows"]=store.db.execute("SELECT COUNT(*) FROM social_comments WHERE platform=? AND deleted=0 AND relevance='RELEVANT'",(row["source_id"],)).fetchone()[0]
        row["pending_items"]=len(store.state(row["source_id"],"pending",[]))
        row["quality"] = "受限/待授权" if not row["enabled"] else ("不完整" if row["status"]!="OK" or row["network_stale"] else ("内容陈旧/暂无新发布" if row["content_stale"] else "可用"))
        check=row.get('last_check_result','NEVER')
        if not row['enabled']:
            effective='RESTRICTED' if row.get('access_status')=='RESTRICTED' else ('NOT_CONFIGURED' if row.get('access_status')=='NOT_CONFIGURED' else 'DISABLED')
        elif check in {'NETWORK_ERROR','HTTP_ERROR','RESTRICTED','PARTIAL'}:
            effective=check
        elif row['status'] not in {'OK','NEVER'}:
            effective='NETWORK_ERROR' if 'Timeout' in (row['last_error'] or '') else 'HTTP_ERROR'
        elif row['network_stale'] or row['content_stale']:
            effective='STALE' if row['last_success_ms'] else 'NOT_CONFIGURED'
        else:
            effective='NOT_MODIFIED' if row.get('last_http_status')==304 else 'HEALTHY'
        row['health_status']=effective
        row['connection_status']=check
        row['quality']='可用' if effective in {'HEALTHY','NOT_MODIFIED'} else ('受限/待授权' if effective=='RESTRICTED' else ('内容陈旧/暂无新发布' if effective=='STALE' and not row['network_stale'] else '不完整'))
        row['source_checked_at']=utc_iso(row.get('last_check_ms'))
        delays=[r[0]/1000 for r in store.db.execute("SELECT discovery_delay_ms FROM news_articles WHERE source_id=? AND delay_quality='VALID_MONITOR' AND discovery_kind='MONITOR_NEW'",(row['source_id'],))]
        row['monitor_delay_samples']=len(delays)
        row['monitor_delay_seconds']={'min':min(delays),'max':max(delays),'median':sorted(delays)[len(delays)//2]} if delays else None
        row['delay_note']='稳态监控样本单独统计；回填/人工/故障恢复/负延迟及源时间缺失排除，源站自身延迟无法从 RSS 单独分离'
        row['negative_delay_articles']=store.db.execute("SELECT COUNT(*) FROM news_articles WHERE source_id=? AND published_at_ms>first_seen_ms",(row['source_id'],)).fetchone()[0]
        row['all_record_lag_range_seconds']={'min':row['discovery_delay_min_seconds'],'max':row['discovery_delay_max_seconds'],'scope':'含历史回填，不作为稳态延迟'}
        row['discovery_delay_min_seconds']=min(delays) if delays else None
        row['discovery_delay_max_seconds']=max(delays) if delays else None
        last_failure=store.db.execute('SELECT error,finished_at_ms FROM collection_runs WHERE source_id=? AND error IS NOT NULL ORDER BY finished_at_ms DESC LIMIT 1',(row['source_id'],)).fetchone()
        row['last_failure']={'message':last_failure[0],'at_utc':utc_iso(last_failure[1])} if last_failure else None
        for field in ("last_attempt_ms","last_success_ms","last_published_ms"):
            row[field.replace("_ms","_utc")]=utc_iso(row[field])
        output.append(row)
    return output


def event_rows(store,hours=24,limit=20,at=None):
    at=now_ms() if at is None else at
    events=store.db.execute("""SELECT e.* FROM news_events e JOIN news_event_links l ON e.id=l.event_id
     JOIN news_articles a ON a.id=l.article_id WHERE e.active=1 AND COALESCE(a.verified_published_at_ms,a.published_at_ms,a.first_seen_ms)>=?
     AND a.importance IN ('High','Critical') GROUP BY e.id ORDER BY CASE WHEN e.importance='Critical' THEN 0 ELSE 1 END,
     MAX(COALESCE(a.verified_published_at_ms,a.published_at_ms,a.first_seen_ms)) DESC LIMIT ?""",(at-hours*3600000,limit)).fetchall()
    results=[]
    for event in events:
        row=dict(event)
        evidence=[dict(r) for r in store.db.execute("""SELECT a.id,a.source_id,a.origin,a.title,a.url,a.published_at_ms,a.first_seen_ms,a.verification,
         a.content_hash,a.summary,a.verified_published_at_ms FROM news_articles a JOIN news_event_links l ON l.article_id=a.id WHERE l.event_id=?""",(row["id"],))]
        from .events import evidence_counts,review_status,claim_reviews,development_kind
        for item in evidence:
            item['effective_published_at_ms']=item['verified_published_at_ms'] or item['published_at_ms']
            health=store.health(item['source_id'])
            item['publisher_id']=health.get('publisher_id') or item['source_id']
        row.update(evidence_counts(evidence))
        row['event_count']=1
        row['publisher_count']=row['source_count']  # 保留旧 JSON 字段，新增字段为明确统计口径。
        row['independent_candidates']=row['independent_report_groups']
        row['corroboration_status'],row['review_evidence_urls'],row['review_rationale'],row['review_claim']=review_status(store,row['id'],evidence)
        row['claim_reviews']=claim_reviews(store,row['id'],evidence)
        row['counting_unit']='INCIDENT_REPORTING_GROUP'
        row['independent_subevent_count']=None
        row['group_scope']='同一事故的报道族，含归因、恢复、调查、评论及被报道的市场反应；不是独立事实事件总数'
        for item in evidence:
            item['development_kind']=development_kind(item['title'])
            item['claim_reviews']=[review for review in row['claim_reviews'] if review['anchor_article_id']==item['id']]
            item['detail_verification_status']='PARTIALLY_ASSESSED' if item['claim_reviews'] else 'UNVERIFIED'
            item['unreviewed_details_remain']=True
        row['independence_status']='发布机构与转载去重数，不等同于独立核实；母机构按配置归并'
        row['evidence']=evidence
        row['earliest_published_ms']=min((e['effective_published_at_ms'] for e in evidence if e['effective_published_at_ms'] is not None),default=None)
        results.append(row)
    return results


def coverage(store,source_id,start,end):
    """只有实际持续轮询足够久才能比较历史；回填文章不能充当采集基线。"""
    health=store.health(source_id)
    if health["status"]!="OK" or not health["enabled"] or health["last_success_ms"] is None:
        return "不完整"
    if now_ms()-health["last_success_ms"] > max(health["interval_seconds"]*3,900)*1000:
        return "不完整"
    if not health["first_success_ms"] or health["first_success_ms"]>start:
        return "样本不足"
    runs=store.db.execute("SELECT finished_at_ms,status FROM collection_runs WHERE source_id=? AND finished_at_ms BETWEEN ? AND ? ORDER BY finished_at_ms",(source_id,start-health["interval_seconds"]*3000,end)).fetchall()
    points=[r[0] for r in runs if r[1]=="OK"]
    if not points or points[0]>start or points[-1]<end-max(health["interval_seconds"]*3,900)*1000:
        return "不完整"
    if any(r[1]!="OK" and r[0]>=start for r in runs) or any(b-a>max(health["interval_seconds"]*3,900)*1000 for a,b in zip(points,points[1:])):
        return "不完整"
    return "可比较（仅当前订阅源的采集覆盖）"


def sentiment_stats(store,start,end,min_samples=20):
    platforms=[r[0] for r in store.db.execute("SELECT DISTINCT source_id FROM source_health WHERE kind='social'")]
    output=[]
    for platform in platforms:
        rows=store.db.execute("""SELECT c.comment_id,c.thread_id,r.label FROM social_comments c LEFT JOIN sentiment_results r
         ON r.platform=c.platform AND r.comment_id=c.comment_id AND r.version=?
         WHERE c.platform=? AND c.deleted=0 AND c.relevance='RELEVANT' AND c.published_at_ms>=? AND c.published_at_ms<?""",(RULE_VERSION,platform,start,end)).fetchall()
        counts={label:0 for label in LABELS}
        for row in rows:
            counts[row["label"] or "UNKNOWN"]+=1
        total=len(rows); direction_n=total-counts["UNKNOWN"]
        raw=store.db.execute("SELECT COUNT(*),SUM(CASE WHEN published_at_ms>=? AND published_at_ms<? THEN 1 ELSE 0 END),SUM(CASE WHEN published_at_ms IS NULL THEN 1 ELSE 0 END) FROM social_comments WHERE platform=? AND deleted=0",(start,end,platform)).fetchone()
        directional=counts['BULLISH']+counts['BEARISH']
        relevant_all=store.db.execute("SELECT COUNT(*) FROM social_comments WHERE platform=? AND deleted=0 AND relevance='RELEVANT'",(platform,)).fetchone()[0]
        output.append({"platform":platform,"count":total,"counts":counts,
                       "filter_funnel":{"stored_comments":raw[0],"within_window":raw[1] or 0,"outside_window":raw[0]-(raw[1] or 0)-(raw[2] or 0),"missing_time":raw[2] or 0,"btc_market_relevant":total,"relevant_all_time":relevant_all,"relevant_outside_window":relevant_all-total,"irrelevant_all_time":raw[0]-relevant_all,"excluded_in_window":(raw[1] or 0)-total,"explicit_directional":directional,"score_eligible":direction_n,"unknown":counts['UNKNOWN']},
                       "signal":"暂无可信情绪信号" if directional<min_samples else "仅描述该社区采样观点，不代表全球市场",

                       "percent":{key:round(value/total*100,1) if total else None for key,value in counts.items()},
                       "direction_sample_size":directional,"score_sample_size":direction_n,"score":round((counts["BULLISH"]-counts["BEARISH"])/direction_n,3) if directional>=min_samples else None,
                       "score_formula":"(Bullish-Bearish)/(Bullish+Bearish+Neutral)，Unknown 排除",
                       "topics":len({r["thread_id"] for r in rows}),"sample_status":"足够用于描述该平台样本" if directional>=min_samples else "样本不足",
                       "coverage":coverage(store,platform,start,end),"min_samples":min_samples})
    return output


def stats(store,hours=24,min_samples=20,at=None):
    at=now_ms() if at is None else at
    start=at-int(hours*3600000);previous=start-int(hours*3600000)
    def news_counts(begin,end):
        rows=store.db.execute("SELECT relevance,importance,category FROM news_articles WHERE COALESCE(verified_published_at_ms,published_at_ms)>=? AND COALESCE(verified_published_at_ms,published_at_ms)<?",(begin,end)).fetchall()
        event_count=store.db.execute('SELECT COUNT(DISTINCT l.event_id) FROM news_event_links l JOIN news_articles a ON a.id=l.article_id JOIN news_events e ON e.id=l.event_id WHERE e.active=1 AND COALESCE(a.verified_published_at_ms,a.published_at_ms)>=? AND COALESCE(a.verified_published_at_ms,a.published_at_ms)<?',(begin,end)).fetchone()[0]
        source_count=store.db.execute('SELECT COUNT(DISTINCT source_id) FROM news_articles WHERE COALESCE(verified_published_at_ms,published_at_ms)>=? AND COALESCE(verified_published_at_ms,published_at_ms)<?',(begin,end)).fetchone()[0]
        return {"count":len(rows),"article_count":len(rows),"event_count":event_count,"source_count":source_count,"direct":sum(r[0]=="DIRECT" for r in rows),"indirect":sum(r[0]=="INDIRECT" for r in rows),
                "high_critical":sum(r[1] in {"High","Critical"} for r in rows),
                "categories":{category:sum(r[2]==category for r in rows) for category in sorted({r[2] for r in rows})}}
    current=news_counts(start,at);baseline=news_counts(previous,start)
    health=source_health(store,at)
    social=sentiment_stats(store,start,at,min_samples)
    old_social={r["platform"]:r for r in sentiment_stats(store,previous,start,min_samples)}
    alerts=[]
    for event in event_rows(store,hours,50,at):
        if event["importance"]=="Critical":
            alerts.append({"kind":"重大事件候选","event_id":event["id"],"status":"待核实","reason":event["title"]})
        if event["independent_candidates"]>=2:
            times=[r["published_at_ms"] for r in event["evidence"] if r["published_at_ms"] is not None]
            if len(times)>=2 and max(times)-min(times)<=3600000:
                alerts.append({"kind":"多源密集报道候选","event_id":event["id"],"status":"待核实，含首次回填可能",
                               "reason":f"{event['publisher_count']} 家媒体、转载去重后 {event['independent_candidates']} 组候选；不等同于独立证实"})
    news_sources=[s for s in health if s["enabled"] and s["kind"]!="social"]
    news_coverage=[coverage(store,s["source_id"],previous,at) for s in news_sources]
    comparable=bool(news_coverage) and all(s.startswith("可比较") for s in news_coverage)
    density_status="可比较" if comparable else ("不完整" if "不完整" in news_coverage else "样本不足")
    for category,value in current["categories"].items():
        old=baseline["categories"].get(category,0)
        if comparable and old>=5 and value>=10 and value>=old*2:
            alerts.append({"kind":"新闻类别密度上升候选","status":"候选","reason":f"{category} 当前 {value}、前一等长窗口 {old}"})
    for row in social:
        old=old_social[row["platform"]]
        if row["coverage"].startswith("可比较") and old["coverage"].startswith("可比较") and old["count"]>=min_samples and row["count"]>=min_samples:
            if row["count"]>=2*old["count"]:
                alerts.append({"kind":"讨论量上升候选","status":"候选","reason":f"{row['platform']} {old['count']} → {row['count']}"})
            for label in ("BULLISH","BEARISH"):
                if row["direction_sample_size"]>=min_samples and old["direction_sample_size"]>=min_samples and abs(row["percent"][label]-old["percent"][label])>=25:
                    alerts.append({"kind":"情绪占比变化候选","status":"候选","reason":f"{row['platform']} {label} {old['percent'][label]}% → {row['percent'][label]}%"})
    return {"as_of_utc":utc_iso(at),"window_hours":hours,"window_start_utc":utc_iso(start),"baseline_start_utc":utc_iso(previous),
            "time_basis":"优先同媒体页面已核对的原始发布时间，其次RSS报告时间；缺失单列，不用发现时间冒充",
            "news":current,"news_1h":news_counts(at-3600000,at),"news_24h":news_counts(at-86400000,at),"news_previous_window":baseline,
            "newly_discovered":store.db.execute("SELECT COUNT(*) FROM news_articles WHERE first_seen_ms>=?",(start,)).fetchone()[0],
            "missing_news_time":store.db.execute("SELECT COUNT(*) FROM news_articles WHERE published_at_ms IS NULL").fetchone()[0],
            "missing_comment_time":store.db.execute("SELECT COUNT(*) FROM social_comments WHERE published_at_ms IS NULL AND deleted=0").fetchone()[0],
            "sentiment":social,"density_comparison":density_status,"alerts":alerts,
            "health":health,"quality":"不完整" if any(s['enabled'] and s['quality']=='不完整' for s in health) else "当前订阅源可用，仍有未授权覆盖缺口"}
