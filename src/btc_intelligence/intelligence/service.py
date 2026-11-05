import asyncio
import logging

from ..models import now_ms
from .rss import parse_feed
from .social import HackerNewsAdapter
from .transport import FetchError, Transport

log = logging.getLogger(__name__)


class IntelService:
    def __init__(self, store, sources, config, client):
        self.store,self.sources,self.config = store,sources,config
        self.http = Transport(client,config)
        self.store.register(sources)

    async def collect_source(self, source, *, run_mode=None):
        run_mode=run_mode or getattr(self,"run_mode","manual")
        started = now_ms()
        health = self.store.health(source.id)
        if not source.enabled:
            return {"source":source.id,"status":"RESTRICTED","reason":source.restriction}
        if health["next_allowed_ms"] > started:
            return {"source":source.id,"status":"COOLDOWN","retry_at_ms":health["next_allowed_ms"]}
        fetched,inserted = 0,0
        try:
            async with asyncio.timeout(180 if source.kind=="social" else self.config.timeout*self.config.retries+10):
                if source.id == "hn":
                    stats = await HackerNewsAdapter(self.http,self.store,self.config).collect()
                    fetched,inserted = stats["fetched"],stats["inserted"]
                    status = "PARTIAL" if stats["partial"] else "OK"
                    error = f"部分采集或分析失败：API {stats['errors']}，分类 {stats['analysis_errors']}" if stats["partial"] else None
                    self.store.finish_run(source,started,status,fetched,inserted,error,stats["published"],run_mode=run_mode,filters=stats.get('filters'),check_result='HEALTHY' if status=='OK' else 'PARTIAL')
                    log.info("评论来源 %s：%s，相关评论 %s，新增 %s，待扫描 %s",source.id,status,fetched,inserted,stats["remaining"])
                    return {"source":source.id,"status":status,**stats}
                headers = {}
                if health["etag"]:
                    headers["If-None-Match"] = health["etag"]
                if health["last_modified"]:
                    headers["If-Modified-Since"] = health["last_modified"]
                code,body,response_headers = await self.http.get(source.url,headers=headers)
                articles,rejected = ([],0) if code == 304 else parse_feed(body,source,now_ms())
                fetched = len(articles)
                before_backfill=self.store.db.execute("SELECT COUNT(*) FROM news_articles WHERE source_id=? AND discovery_kind!='MONITOR_NEW'",(source.id,)).fetchone()[0]
                before_monitor=self.store.db.execute("SELECT COUNT(*) FROM news_articles WHERE source_id=? AND discovery_kind='MONITOR_NEW'",(source.id,)).fetchone()[0]
                initialized=self.store.state(source.id,'quality_initialized',False)
                inserted = self.store.save_articles(source,articles,run_mode=run_mode,checked_at=started,bootstrap=not initialized,previous_check=health.get('last_check_ms'))
                with self.store.db:
                    self.store.set_state(source.id,'quality_initialized',True)
                backfill=self.store.db.execute("SELECT COUNT(*) FROM news_articles WHERE source_id=? AND discovery_kind!='MONITOR_NEW'",(source.id,)).fetchone()[0]-before_backfill
                monitor=self.store.db.execute("SELECT COUNT(*) FROM news_articles WHERE source_id=? AND discovery_kind='MONITOR_NEW'",(source.id,)).fetchone()[0]-before_monitor
                latest = max((a["published_at_ms"] for a in articles if a["published_at_ms"]),default=None)
                status = "PARTIAL" if rejected else "OK"
                error = f"无效条目 {rejected}，合法条目已保留" if rejected else None
                self.store.finish_run(source,started,status,fetched,inserted,error,latest,response_headers,http_status=code,run_mode=run_mode,backfill=backfill,monitor=monitor)
                log.info("新闻来源 %s：HTTP %s，%s，获取 %s，新增 %s",source.id,code,status,fetched,inserted)
                return {"source":source.id,"status":status,"http_status":code,"fetched":fetched,"inserted":inserted,"rejected":rejected}
        except asyncio.CancelledError:
            self.store.finish_run(source,started,"CANCELLED",fetched,inserted,"任务安全停止；已提交数据保留")
            raise
        except Exception as exc:
            # 隔离单来源错误；仅记录异常类型/已清理的自有错误，不输出外部响应或凭据。
            error = str(exc) if isinstance(exc,FetchError) else type(exc).__name__+"：采集失败"
            status = exc.status if isinstance(exc,FetchError) else "ERROR"
            retry_at = exc.retry_at if isinstance(exc,FetchError) else 0
            self.store.finish_run(source,started,"ERROR" if status in {"HTTP_ERROR","NETWORK_ERROR"} else status,fetched,inserted,error,next_allowed=retry_at,http_status=getattr(exc,'http_status',None),run_mode=run_mode,check_result=status)
            log.warning("来源 %s 失败：%s",source.id,error)
            return {"source":source.id,"status":status,"error":error}

    def select(self, mode="all", ids=None):
        sources = [s for s in self.sources if s.enabled and (mode=="all" or (s.kind=="social")==(mode=="social"))]
        if ids:
            unknown = set(ids)-{s.id for s in self.sources}
            if unknown:
                raise ValueError("未知来源："+",".join(sorted(unknown)))
            sources = [s for s in self.sources if s.id in ids]
            if mode!="all" and any((s.kind=="social")!=(mode=="social") for s in sources):
                raise ValueError("指定来源类型与新闻/评论采集命令不匹配")
        return sources

    async def once(self, mode="all", ids=None):
        return await asyncio.gather(*(self.collect_source(s) for s in self.select(mode,ids)))

    async def run(self, stop, seconds=None, ids=None):
        self.run_mode='continuous'
        async def poll(source):
            while not stop.is_set():
                await self.collect_source(source)
                health=self.store.health(source.id)
                delay=max(source.interval,(health["next_allowed_ms"]-now_ms())/1000)
                try:
                    await asyncio.wait_for(stop.wait(),max(1,delay))
                except TimeoutError:
                    pass
        tasks = [asyncio.create_task(poll(s)) for s in self.select(ids=ids)]
        if not tasks:
            raise ValueError("没有可调度的数据源")
        waiter=asyncio.create_task(stop.wait())
        try:
            done,_=await asyncio.wait([waiter,*tasks],timeout=seconds,return_when=asyncio.FIRST_COMPLETED)
            for task in tasks:
                if task in done:
                    task.result()  # 不把数据库/调度层的意外故障静默报告为成功。
        finally:
            for task in [*tasks,waiter]:
                task.cancel()
            await asyncio.gather(*tasks,waiter,return_exceptions=True)
