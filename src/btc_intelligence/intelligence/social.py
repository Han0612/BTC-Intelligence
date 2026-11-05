"""Algolia 仅发现主题 ID；帖子与评论一律回到 HN 官方 Firebase API 核验。"""
import asyncio
import json
import re
from collections import deque

from ..models import now_ms
from .analysis import BTC, Sentiment, classify_comment, comment_relevance,technical_thread
from .safety import clean_text, digest, language
from .transport import FetchError

HN_API = "https://hacker-news.firebaseio.com/v0/item/"
SEARCH = "https://hn.algolia.com/api/v1/search_by_date"


def item_url(item_id):
    if not str(item_id).isdigit():
        raise ValueError("HN ID 必须为纯数字")
    return HN_API+str(item_id)+".json"


def hn_time(value):
    if type(value) is not int or value < 0 or value*1000 > now_ms()+300000:
        return None
    return value*1000


class HackerNewsAdapter:
    def __init__(self, transport, store, config):
        self.http,self.store,self.config = transport,store,config

    async def verify_thread(self,comment,thread_id,cache):
        """独立搜索提供的 story_id 也要沿官方 parent 链核验，不能仅信索引。"""
        seen=set()
        for _ in range(32):
            parent=str(comment.get("parent",""))
            if parent==thread_id:
                return True
            if not parent.isdigit() or parent in seen:
                return False
            seen.add(parent)
            if parent not in cache:
                cache[parent]=await self.http.json(item_url(parent))
            comment=cache[parent]
            if not isinstance(comment,dict) or comment.get("type")!="comment":
                return False
        return False

    async def collect(self):
        cutoff = now_ms()-self.config.hn_lookback_days*86400000
        ids = []
        discovered_comments={}
        ancestor_cache={}
        for query in ("bitcoin","btc"):
            result = await self.http.json(SEARCH,params={"query":query,"tags":"story","numericFilters":"num_comments>0",
                                                       "hitsPerPage":self.config.hn_threads})
            if not isinstance(result,dict) or not isinstance(result.get("hits"),list):
                raise FetchError("HN 独立搜索服务响应结构错误")
            for hit in result["hits"]:
                value = str(hit.get("objectID",""))
                if value.isdigit() and value not in ids:
                    ids.append(value)
        # 评论搜索用于发现讨论嵌在其他主题中的 BTC 金融观点；原文仍由官方 API 获取。
        result=await self.http.json(SEARCH,params={"query":"bitcoin","tags":"comment",
            "numericFilters":"created_at_i>="+str(cutoff//1000),"hitsPerPage":self.config.hn_threads})
        if not isinstance(result,dict) or not isinstance(result.get("hits"),list):
            raise FetchError("HN 独立评论搜索响应结构错误")
        for hit in result["hits"]:
            comment_id,thread_id=str(hit.get("objectID","")),str(hit.get("story_id",""))
            if comment_id.isdigit() and thread_id.isdigit():
                discovered_comments.setdefault(thread_id,[]).append(comment_id)
        # 轮换已知主题，持续检查新回复；不能只发现一次就停止采集。
        known = [r[0] for r in self.store.db.execute("SELECT thread_id FROM social_threads WHERE platform='hn' AND published_at_ms>=? ORDER BY collected_at_ms LIMIT ?",(cutoff,self.config.hn_threads))]
        ids = list(dict.fromkeys(list(discovered_comments)+ids[:self.config.hn_threads]+known))
        titles = {r[0]:r[1] for r in self.store.db.execute("SELECT thread_id,title FROM social_threads WHERE platform='hn'")}
        pending = deque(self.store.state("hn","pending",[]))
        failures, analysis_errors, fetched, inserted, latest = [],0,0,0,None
        filters={'discovered_story_ids':len(ids),'discovered_comment_ids':sum(len(v) for v in discovered_comments.values()),'comments_checked':0,'technical_topics_excluded':0,'deleted_or_dead':0,'empty_or_invalid':0,'irrelevant':0,'market_relevant':0,'new_records':0,'duplicate_records':0,'sampling':'有界搜索发现、选中评论及子回复；并非整棵讨论树或全站'}
        queued = {str(pair[0]) for pair in pending}

        def enqueue(values,thread_id):
            for value in values:
                key = str(value)
                if key.isdigit() and key not in queued and len(pending)<10000:
                    pending.append([key,thread_id]); queued.add(key)

        for thread_id in ids:
            try:
                story = await self.http.json(item_url(thread_id))
                if not isinstance(story,dict) or story.get("type") != "story" or story.get("deleted") or story.get("dead"):
                    continue
                title = clean_text(story.get("title"),500)
                if technical_thread(title) or (not re.search(BTC,title,re.I) and thread_id not in discovered_comments):
                    filters['technical_topics_excluded']+=1
                    continue
                published = hn_time(story.get("time"))
                if published is None or published < cutoff:
                    continue
                stamp = now_ms(); titles[thread_id]=title
                with self.store.db:
                    self.store.save_thread({"platform":"hn","thread_id":thread_id,"title":title,
                        "url":"https://news.ycombinator.com/item?id="+thread_id,"source_url":item_url(thread_id),
                        "discovery_source":"Algolia HN Search（独立索引，非官方关键词 API）",
                        "published_at_ms":published,"first_seen_ms":stamp,"collected_at_ms":stamp,
                        "metrics":json.dumps({"score":story.get("score"),"descendants":story.get("descendants")})})
                enqueue(discovered_comments.get(thread_id,[]) or story.get("kids",[]),thread_id)
            except FetchError as exc:
                failures.append(str(exc))
        # 已知技术悬赏/家电话题不占用投资情绪的扫描预算。
        pending=deque(pair for pair in pending if not technical_thread(titles.get(pair[1],"")))
        recent = self.store.db.execute("SELECT comment_id,thread_id FROM social_comments WHERE platform='hn' AND deleted=0 AND relevance='RELEVANT' ORDER BY collected_at_ms LIMIT 20").fetchall()
        for row in recent:
            enqueue([row[0]],row[1])
        count = 0
        while pending and count < self.config.hn_items:
            batch = [pending.popleft() for _ in range(min(self.config.concurrency,len(pending),self.config.hn_items-count))]
            results = await asyncio.gather(*(self.http.json(item_url(pair[0])) for pair in batch),return_exceptions=True)
            retry_pairs = []
            for (comment_id,thread_id), result in zip(batch,results):
                count += 1
                filters['comments_checked']+=1
                if isinstance(result,Exception):
                    failures.append(type(result).__name__);retry_pairs.append([comment_id,thread_id]);continue
                if not isinstance(result,dict):
                    failures.append("HN 评论响应为空或结构错误");continue
                if str(result.get("id")) != comment_id:
                    failures.append("HN 评论 ID 不匹配");continue
                if comment_id in discovered_comments.get(thread_id,[]) and not result.get("deleted"):
                    try:
                        if not await self.verify_thread(result,thread_id,ancestor_cache):
                            failures.append("HN 独立搜索主题关联未通过官方 parent 链核验");continue
                    except FetchError:
                        failures.append("HN 父链 API 核验失败");retry_pairs.append([comment_id,thread_id]);continue
                with self.store.db:
                    if result.get("deleted") or result.get("dead"):
                        filters['deleted_or_dead']+=1
                        self.store.mark_deleted("hn",comment_id)
                        continue
                    if result.get("type") != "comment":
                        continue
                    enqueue(result.get("kids",[]),thread_id)
                    text = clean_text(result.get("text"))
                    if not text or thread_id not in titles:
                        filters['empty_or_invalid']+=1
                        continue
                    relevance = comment_relevance(text,titles[thread_id])
                    filters['market_relevant' if relevance=='RELEVANT' else 'irrelevant']+=1
                    exists = self.store.db.execute("SELECT 1 FROM social_comments WHERE platform='hn' AND comment_id=?",(comment_id,)).fetchone()
                    if relevance != "RELEVANT" and not exists:
                        continue
                    stamp = now_ms(); published = hn_time(result.get("time"))
                    if published:
                        latest = max(latest or 0,published)
                    try:
                        sentiment = classify_comment(text,titles[thread_id])
                    except Exception:
                        # 分类故障仍保留真实评论，明确 UNKNOWN 并标记来源部分完成。
                        analysis_errors += 1
                        sentiment = Sentiment("UNKNOWN",0,"分析失败，未推断方向")
                    comment={"platform":"hn","comment_id":comment_id,"thread_id":thread_id,
                        "parent_id":str(result.get("parent")) if result.get("parent") else None,
                        "body":text,"author":clean_text(result.get("by"),100) or None,
                        "url":"https://news.ycombinator.com/item?id="+comment_id,"source_url":item_url(comment_id),
                        "published_at_ms":published,"first_seen_ms":stamp,"collected_at_ms":stamp,
                        "language":language(text),"relevance":relevance,
                        "metrics":json.dumps({"score":result.get("score"),"children":len(result.get("kids",[])),"truncated":len(text)>=12000}),
                        "content_hash":digest(text)}
                    inserted += self.store.save_comment(comment,sentiment)
                    fetched += 1
            # 失败 ID 留待下一轮，不在当前轮中反复撞同一接口。
            with self.store.db:
                previous_retry = self.store.state("hn","retry",[])
                self.store.set_state("hn","retry",previous_retry+retry_pairs)
                self.store.set_state("hn","pending",list(pending))
        with self.store.db:
            retries = self.store.state("hn","retry",[])
            merged = list({str(pair[0]):pair for pair in [*pending,*retries]}.values())
            self.store.set_state("hn","pending",merged)
            self.store.set_state("hn","retry",[])
            self.store.set_state("hn","last_discovery_ms",now_ms())
        filters.update(new_records=inserted,duplicate_records=max(0,fetched-inserted),pending=len(merged),failures=len(failures))
        return {"fetched":fetched,"inserted":inserted,"published":latest,"filters":filters,
                "partial":bool(failures or analysis_errors),"errors":len(failures),"analysis_errors":analysis_errors,
                "remaining":len(merged),"scanned_items":count}


class RedditAdapter:
    """预留授权边界：有凭证也不等于已获平台用途批准，不发未授权请求。"""
    async def collect(self):
        raise FetchError("Reddit Data API 待平台批准和 OAuth 授权，未接通", "RESTRICTED")
