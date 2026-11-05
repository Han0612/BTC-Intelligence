import asyncio
import json
import signal
from pathlib import Path

import httpx

from .config import load_intel_config,load_sources
from .evaluation import evaluate
from .queries import source_health,event_rows,latest_news,latest_comments,stats
from .report import brief
from .service import IntelService
from .storage import IntelStore

COMMANDS={"news","social","intel-run","sources","events","news-latest","comments","brief","intel-stats","evaluate","analyze"}


def bounded_hours(value):
    number=int(value)
    if number<1 or number>720:
        raise ValueError("窗口须为 1～720 小时（支持 1/24/168 小时）")
    return number


def add_commands(commands,positive_seconds):
    for name,help_text in [("news","单次采集真实 RSS 新闻"),("social","单次采集真实社区评论"),("intel-run","持续采集新闻与评论")]:
        parser=commands.add_parser(name,help=help_text)
        parser.add_argument("--source",action="append",help="仅指定来源 ID，可重复指定")
        if name=="intel-run":
            parser.add_argument("--seconds",type=positive_seconds,help="限时运行；不指定则持续运行")
    for name,help_text in [("sources","数据源健康与覆盖状态"),("events","最近重大事件与证据"),("news-latest","查询最新真实新闻"),
                           ("comments","查询最新真实相关评论"),("intel-stats","分平台情绪与事件热度"),("brief","生成中文情报简报"),("evaluate","规则分类人工样本评测"),("analyze","按当前规则重算本地记录，不请求外部服务")]:
        parser=commands.add_parser(name,help=help_text)
        parser.add_argument("--json",action="store_true",help="输出 JSON")
        if name not in {"sources","evaluate","analyze"}:
            parser.add_argument("--hours",type=bounded_hours,default=24,help="过去小时数，7天使用168")
        if name in {"events","news-latest","comments"}:
            parser.add_argument("--limit",type=int,default=10,help="返回条数，1～1000")
        if name in {"brief","evaluate"}:
            parser.add_argument("--output",type=Path,help="同时保存报告文件")


async def execute(args,settings):
    config=load_intel_config()
    if args.command=="evaluate":
        result=evaluate();output=json.dumps(result,ensure_ascii=False,indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(output+"\n",encoding="utf-8")
        print(output if args.json else f"人工合成自测：评论 {result['comment_correct']}/{result['comment_samples']}，准确率 {result['accuracy']:.1%}；新闻 {result['news_correct']}/{result['news_samples']}。\n"+json.dumps(result['comment_errors'],ensure_ascii=False,indent=2)+"\n不能作为真实社区泛化准确率。")
        return 0
    sources=load_sources()
    store=IntelStore(settings.db_path)
    try:
        store.register(sources)
        if args.command=="analyze":
            print(json.dumps(store.reanalyze(),ensure_ascii=False,indent=2))
            return 0
        if args.command in {"news","social","intel-run"}:
            async with httpx.AsyncClient(trust_env=False,follow_redirects=False,headers={"User-Agent":"BTCIntelligence/0.2 personal-research RSS reader"}) as client:
                service=IntelService(store,sources,config,client)
                if args.command!="intel-run":
                    result=await service.once(args.command,getattr(args,"source",None))
                    print(json.dumps(result,ensure_ascii=False,indent=2))
                    return 0 if result and all(r["status"]=="OK" for r in result) else 2
                stop=asyncio.Event();loop=asyncio.get_running_loop()
                for sig in (signal.SIGINT,signal.SIGTERM):
                    loop.add_signal_handler(sig,stop.set)
                try:
                    await service.run(stop,args.seconds,args.source)
                finally:
                    for sig in (signal.SIGINT,signal.SIGTERM):
                        loop.remove_signal_handler(sig)
                print("情报采集已安全停止；已提交数据保留。来源成功与否请查看 sources。")
                # 退出正常不意味着所有源可用，显式通过健康状态决定批次结果。
                selected=service.select(ids=args.source)
                return 0 if selected and all(store.health(s.id)["status"]=="OK" for s in selected) else 2
        if getattr(args,"limit",10)<1 or getattr(args,"limit",10)>1000:
            raise ValueError("查询条数须为 1～1000")
        if args.command=="sources":
            result=source_health(store)
        elif args.command=="events":
            result=event_rows(store,args.hours,args.limit)
        elif args.command=="news-latest":
            result=latest_news(store,args.hours,args.limit)
        elif args.command=="comments":
            result=latest_comments(store,args.hours,args.limit)
        elif args.command=="intel-stats":
            result=stats(store,args.hours,config.min_samples)
        else:
            result=stats(store,args.hours,config.min_samples) if args.json else brief(store,args.hours,config.min_samples)
            if args.output:
                args.output.parent.mkdir(parents=True,exist_ok=True)
                args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n" if args.json else result,encoding="utf-8")
        if isinstance(result,str):
            print(result)
        elif args.json or args.command=="intel-stats":
            print(json.dumps(result,ensure_ascii=False,indent=2))
        elif args.command=="sources":
            for row in result:
                print(f"{row['source_id']}｜{row['name']}｜{row['quality']} / {row['health_status']}｜HTTP {row['last_http_status']}｜新闻 {row['article_rows']} 评论 {row['comment_rows']}｜最近检查 {row['source_checked_at']}｜最新发布 {row['last_published_utc']}｜最后成功 {row['last_success_utc']}｜{row['last_error'] or ''}")
        else:
            from ..models import utc_iso
            for row in result:
                print(f"[{row.get('source_name') or row.get('platform') or row.get('category')}] {row.get('title') or row.get('thread_title')}\n{row.get('url','')}\n"
                      f"原始发布 UTC：{utc_iso(row.get('published_at_ms')) or '缺失；事件请查看各报道'}\n"
                      f"首次发现 UTC：{utc_iso(row.get('first_seen_ms'))}\n最近采集 UTC：{utc_iso(row.get('collected_at_ms')) or '见原始报道'}\n"
                      f"{row.get('label') or ''} {(row.get('body') or '')[:160]}")
                if args.command=="events":
                    for article in row['evidence']:
                        print(f"  证据：{article['source_id']} {article['url']}")
        return 0
    finally:
        store.close()
