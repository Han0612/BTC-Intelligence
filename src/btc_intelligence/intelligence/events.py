"""派生事件、发布机构去重与交叉核实；计数绝不提升为事实确认。"""
import json

from ..models import now_ms
from .analysis import RULE_VERSION,same_event


def publisher(row):
    origin=row.get('origin','')
    if origin.startswith('wire:'):
        return origin[5:].strip().lower().replace('associated press','ap')
    return row.get('publisher_id') or row['source_id']


def evidence_counts(evidence):
    parents=list(range(len(evidence)))
    def root(index):
        while parents[index]!=index:
            parents[index]=parents[parents[index]];index=parents[index]
        return index
    for i,left in enumerate(evidence):
        for j,right in enumerate(evidence[:i]):
            if publisher(left)==publisher(right) or left['content_hash']==right['content_hash'] or left['title'].casefold()==right['title'].casefold():
                parents[root(i)]=root(j)
    reps=[];seen=set()
    for row in sorted(evidence,key=lambda x:x['published_at_ms'] or x['first_seen_ms'],reverse=True):
        key=publisher(row)
        if key not in seen:reps.append(row);seen.add(key)
    return {'article_count':len(evidence),'source_count':len({e['source_id'] for e in evidence}),
            'independent_publisher_count':len({publisher(e) for e in evidence}),
            'independent_report_groups':len({root(i) for i in range(len(evidence))}),
            'publisher_names':sorted({publisher(e) for e in evidence}),'representative_evidence':reps}


def rebuild(store):
    """仅重算派生关联；旧关联留档，完全相同的成员集合复用事件 ID。"""
    db=store.db
    articles=[dict(r) for r in db.execute('SELECT * FROM news_articles ORDER BY COALESCE(published_at_ms,first_seen_ms),id')]
    old={}
    for row in db.execute('SELECT event_id,article_id FROM news_event_links ORDER BY event_id,article_id'):
        old.setdefault(row[0],set()).add(row[1])
    memberships={frozenset(ids):event_id for event_id,ids in old.items()}
    groups=[]
    for article in articles:
        timestamp=article['published_at_ms'] or article['first_seen_ms']
        match=None
        for group in reversed(groups):
            anchor=group[0]
            if article['category']==anchor['category'] and timestamp-(anchor['published_at_ms'] or anchor['first_seen_ms'])<=72*3600000 and same_event(article['title'],anchor['title'],article['category']):
                match=group;break
        if match is None:groups.append([article])
        else:match.append(article)
    with db:
        for row in db.execute('SELECT * FROM news_event_links').fetchall():
            db.execute('INSERT OR IGNORE INTO event_link_history VALUES(?,?,?,?,?)',(row['event_id'],row['article_id'],row['reason'],RULE_VERSION,now_ms()))
        db.execute('DELETE FROM news_event_links')
        db.execute('UPDATE news_events SET active=0')
        for group in groups:
            event_id=memberships.get(frozenset(a['id'] for a in group))
            anchor=group[0];first=min(a['first_seen_ms'] for a in group);last=max(a['first_seen_ms'] for a in group)
            level=max((a['importance'] for a in group),key=lambda value:{'Low':0,'Medium':1,'High':2,'Critical':3}[value])
            if event_id is None:
                event_id=db.execute('''INSERT INTO news_events(title,category,importance,relevance,first_seen_ms,last_seen_ms,paths,aggregation_version,active)
                 VALUES(?,?,?,?,?,?,?,?,1)''',(anchor['title'],anchor['category'],level,anchor['relevance'],first,last,anchor['paths'],RULE_VERSION)).lastrowid
            else:
                db.execute('UPDATE news_events SET active=1,title=?,category=?,importance=?,relevance=?,paths=?,aggregation_version=? WHERE id=?',
                           (anchor['title'],anchor['category'],level,anchor['relevance'],anchor['paths'],RULE_VERSION,event_id))
            for article in group:
                db.execute('INSERT INTO news_event_links VALUES(?,?,?)',(event_id,article['id'],'同一主张/事故的72小时内进展；不表示事实已证实'))
    return len(groups)


def claim_reviews(store,event_id,evidence):
    """审核结论只属于所写出的主张，不能继承为整组或整篇文章的确认。"""
    ids=[e['id'] for e in evidence]
    rows=store.db.execute('SELECT * FROM event_reviews WHERE event_id=? OR anchor_article_id IN ('+','.join('?' for _ in ids)+') ORDER BY reviewed_at_ms DESC,id DESC',[event_id,*ids]).fetchall()
    return [dict(r,status=r['status'],evidence_urls=json.loads(r['evidence_urls']),scope='仅该主张，不代表整篇报道或整个事件组') for r in rows]


def development_kind(title):
    """报道族内的主题关系，不声称已证明后续事件或因果。"""
    text=title.lower()
    if 'selloff' in text or 'jumps' in text or 'stock' in text:return 'REPORTED_MARKET_REACTION'
    if 'political' in text or 'election' in text:return 'POLITICAL_REACTION'
    if 'withdraw' in text:return 'WITHDRAWAL_UPDATE'
    if 'fbi' in text or 'north korea' in text or 'tradertraitor' in text:return 'ATTRIBUTION_OR_LAW_ENFORCEMENT'
    if 'laptop' in text or 'breach' in text:return 'INVESTIGATION_UPDATE'
    if 'safety' in text or 'what happens' in text:return 'RISK_COMMENTARY'
    return 'INCIDENT_REPORT_OR_RECAP'


def review_status(store,event_id,evidence):
    if any(e['verification'] not in {'UNVERIFIED','OPINION'} for e in evidence):
        return 'REPORTED',[], '组级只表示有可追溯报道；官方确认等结论仅列在 claim_reviews 的具体主张中','本组包含多个事实主张与后续进展，不作整组官方确认'
    return 'UNVERIFIED',[],'仅传闻/观点或信息不足，未独立核实','本组具体事实主张尚未经独立人工核验'
