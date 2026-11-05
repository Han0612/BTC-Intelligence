import json
from urllib.parse import quote

from ..models import now_ms,utc_iso
from .queries import stats,event_rows,latest_news,latest_comments
from .safety import markdown_text

CATEGORIES={"GEOPOLITICS":"地缘政治","MONETARY_POLICY":"货币政策","ECONOMIC_DATA":"经济数据","FINANCIAL_RISK":"金融风险",
            "ENERGY":"能源","TRADE_POLICY":"贸易财政","ETF":"ETF","EXCHANGE":"交易所","CRYPTO_SECURITY":"加密安全",
            "REGULATION":"监管","INSTITUTIONAL":"机构","ONCHAIN":"链上","CRYPTO":"加密市场","OTHER":"其他"}
VERIFY={"OFFICIAL_STATEMENT":"官方源发布（不等于所有影响已证实）","MEDIA_REPORT":"媒体报道（待交叉核实）","UNVERIFIED":"传闻或未核实信息","OPINION":"评论/观点稿，不作为事实确认"}


def excerpt(text,limit=140):
    return text[:limit]+("…" if len(text)>limit else "")


def link(title,url):
    return "["+markdown_text(title)+"]("+quote(url,safe=":/?&=%.-_~")+")"


def brief(store,hours=24,min_samples=20):
    result=stats(store,hours,min_samples)
    events=event_rows(store,hours,10)
    news=latest_news(store,hours,1000)
    lines=["# BTC Intelligence｜全球市场情报简报",f"生成时间：{result['as_of_utc']}；窗口：过去 {hours:g} 小时（UTC）。",
           "事实限于来源报道；传导路径为假设。实际市场反应尚未测量，本期不提供涨跌目标或交易执行指令。",
           "## 一、全球重要事件"]
    if not events:
        lines.append("当前已采集样本中未发现窗口内 High/Critical 事件；这不代表全球没有发生重大事件。")
    for event in events[:6]:
        lines.append(f"- 候选报道组：{markdown_text(event['title'])}｜{CATEGORIES.get(event['category'],event['category'])} / {event['importance']}。文章 {event['article_count']} 篇，数据源 {event['source_count']} 个，发布机构去重 {event['independent_publisher_count']} 家，事件组 {event['event_count']} 个。组级状态：{event['corroboration_status']}。")
        lines.append('  分组口径：'+event['group_scope']+'；独立子事件数量尚未确认。')
        lines.append(f"  发布机构列表：{', '.join(event['publisher_names'])}；最早报道发布 {utc_iso(event['earliest_published_ms']) or '缺失'}；首次发现 {utc_iso(event['first_seen_ms'])}。计数覆盖整组原始文章，以下按机构展示代表报道，完整列表见 events --json。")
        for evidence in event["representative_evidence"][:5]:
            lines.append(f"  - 原始报道：{link(evidence['source_id'],evidence['url'])}；发布 {utc_iso(evidence['effective_published_at_ms']) or '缺失'}；发现 {utc_iso(evidence['first_seen_ms'])}；{VERIFY[evidence['verification']]}。")
        lines.append('  核验依据：'+markdown_text(event['review_rationale']))
        lines.append('  核实范围（不扩展到其他报道细节）：'+markdown_text(event['review_claim']))
        for review in event['claim_reviews']:
            lines.append(f"  - 主张级 {review['status']}：{markdown_text(review['claim'])}；{markdown_text(review['rationale'])}")
            for url in review['evidence_urls']:
                lines.append('    '+link('该主张的核验依据',url))
        unreviewed=[str(item['id']) for item in event['evidence'] if item['detail_verification_status']=='UNVERIFIED']
        lines.append('  尚未逐项核实的报道ID：'+', '.join(unreviewed)+'；已审核主张所在报道的其他细节仍未核实。')
        for url in event['review_evidence_urls']:
            lines.append('  - '+link('独立核验/一手证据',url))
    lines.append("## 二、宏观及地缘风险")
    indirect=[a for a in news if a["relevance"]=="INDIRECT" and a['importance'] in {'High','Critical'} and json.loads(a['paths'])]
    for article in indirect[:6]:
        lines.append(f"- 来源报道：{link(article['title'],article['url'])}（{markdown_text(article['source_name'])}，{utc_iso(article['effective_published_at_ms']) or '发布时间缺失'}）；{VERIFY[article['verification']]}。")
        lines.append("  潜在路径（假设）："+"；".join(json.loads(article["paths"]))+" 实际 BTC 反应：未测量。")
        lines.append('  媒体页面核验：'+article['page_validation']['publisher_status']+'；这与事件事实核实状态分开。')
    if not indirect:
        lines.append("窗口内暂无已入库的间接关联报道，须结合来源覆盖缺口理解。")
    old=store.db.execute("SELECT title,url,published_at_ms FROM news_articles WHERE relevance='INDIRECT' AND published_at_ms<? ORDER BY published_at_ms DESC LIMIT 2",(now_ms()-int(hours*3600000),)).fetchall()
    if old:
        lines.append("历史回填供核实（发布时间早于本窗口，不计为本期突发）：")
        for row in old:
            lines.append(f"- {link(row['title'],row['url'])}，发布 {utc_iso(row['published_at_ms'])}。")
    lines.append("## 三、BTC 与加密直接相关新闻")
    for article in [a for a in news if a["relevance"]=="DIRECT"][:6]:
        lines.append(f"- {link(article['title'],article['url'])}｜{markdown_text(article['source_name'])} / {article['importance']}；发布 {utc_iso(article['effective_published_at_ms']) or '缺失'}，发现 {utc_iso(article['first_seen_ms'])}；{VERIFY[article['verification']]}。")
    lines.append("## 四、社区情绪（分平台，不合并为全球情绪）")
    for row in result["sentiment"]:
        proportions="、".join(f"{label} {row['counts'][label]} 条（{str(row['percent'][label])+'%' if row['percent'][label] is not None else '无样本'}）" for label in row["counts"])
        lines.append(f"- {row['platform']}：有效相关评论 {row['count']}，讨论主题 {row['topics']}；{proportions}。方向计算样本 {row['direction_sample_size']}，最低 {min_samples}；分数 {row['score'] if row['score'] is not None else '不输出'}。{row['sample_status']}；采集覆盖：{row['coverage']}。")
        funnel=row['filter_funnel']
        lines.append(f"  过滤漏斗：累计保存 {funnel['stored_comments']} → 窗口内 {funnel['within_window']} → BTC 市场相关 {funnel['btc_market_relevant']} → 明确多空 {funnel['explicit_directional']} → 可评分 {funnel['score_eligible']}；累计相关 {funnel['relevant_all_time']}，其中窗口外相关 {funnel['relevant_outside_window']}；累计不相关 {funnel['irrelevant_all_time']}，窗口内排除 {funnel['excluded_in_window']}，缺失时间 {funnel['missing_time']}。{row['signal']}。")
    for row in latest_comments(store,hours,3):
        lines.append(f"- 观点摘录（{row['label'] or 'UNKNOWN'}，发布 {utc_iso(row['published_at_ms'])}）：{markdown_text(excerpt(row['body']))} {link('原评论',row['url'])}；主题：{markdown_text(row['thread_title'])}。")
    popular=store.db.execute("""SELECT t.title,t.url,COUNT(*) n FROM social_threads t JOIN social_comments c USING(platform,thread_id)
     WHERE c.deleted=0 AND c.relevance='RELEVANT' AND c.published_at_ms>=? GROUP BY t.platform,t.thread_id ORDER BY n DESC LIMIT 3""",(now_ms()-int(hours*3600000),)).fetchall()
    for row in popular:
        lines.append(f"- 本窗口主题热度：{link(row['title'],row['url'])}，已采集相关评论 {row['n']}；不代表方向强度。")
    lines.append("HN 偏技术人群，当前筛选与有界采样具有偏差，不能代表全体 BTC 投资者；Reddit 待授权。规则支持中英明确方向，否定、讽刺与复杂语境多归 UNKNOWN；强度不是校准概率。")
    lines.append("## 五、异常监控")
    lines.append(f"新闻数量：最近 1 小时 {result['news_1h']['count']}，24 小时 {result['news_24h']['count']}；本窗口直接 {result['news']['direct']}、间接 {result['news']['indirect']}、High/Critical {result['news']['high_critical']}。")
    lines.append(f"本窗口统计口径：文章 {result['news']['article_count']} 篇，数据源 {result['news']['source_count']} 个，去重后的事件候选 {result['news']['event_count']} 个（包括低优先级类别，不等于均已证实）。")
    lines.append(f"与前一等长窗口比较：{result['density_comparison']}；对照起点 {result['baseline_start_utc']}。首次回填数量不能充当新闻或情绪激增证据。")
    for alert in result["alerts"][:10]:
        lines.append(f"- {alert['kind']}：{markdown_text(alert['reason'])}（{alert['status']}）。")
    if not result["alerts"]:
        lines.append("当前未输出异常候选；样本或覆盖不足时不作无异常结论。")
    lines.append("## 六、数据质量")
    lines.append('新闻窗口优先使用同媒体页面标题匹配时的公开原始发布时间，其次为RSS报告时间。原始RSS日期不覆盖；部分RSS可能把更新时刻写为发布时间，差异与负延迟单列。页面对应不等于事实确认。')
    lines.append(f"总体：{result['quality']}。缺失/无效新闻发布时间 {result['missing_news_time']} 条，评论时间缺失 {result['missing_comment_time']} 条；本窗口首次发现 {result['newly_discovered']} 条（含历史回填）。")
    for source in result["health"]:
        lines.append(f"- {source['name']}：{source['quality']} / {source['health_status']}；最近检查 {source['source_checked_at'] or '无新口径记录'}；HTTP {source['last_http_status']}；最后成功 {source['last_success_utc'] or '无'}；最新内容发布 {source['last_published_utc'] or '无'}；请求耗时 {source['last_latency_ms']} ms；队列剩余 {source['pending_items']}；原因：{source['last_error'] or '无'}")
        lines.append(f"  稳态发现延迟样本 {source['monitor_delay_samples']}，分布 {source['monitor_delay_seconds'] or '暂未取得有效的实时延迟样本'}；初始回填、人工发现、恢复回填及异常时间均排除。")
        if source['negative_delay_articles']:
            lines.append(f"  来源发布时间晚于首次发现的时间异常 {source['negative_delay_articles']} 篇：可能为源时间改写或时钟差异，不修饰原始时间，也不计入延迟分布。")
    audited=store.db.execute('SELECT publisher_status,COUNT(*) FROM article_validations GROUP BY publisher_status').fetchall()
    lines.append('原始页面核验（最近质量抽样，历史检查不代表此刻可访问）：'+str({r[0]:r[1] for r in audited})+'。HTTP 可访问与媒体确实发表、事实独立核实及官方确认分别记录。受限页面无法独立核验，不判为虚假。')
    lines.append("发现延迟含历史回填延迟，不能据此宣称实时；RSS 轮询约 5–10 分钟，受源站发布时间、缓存及网络制约。没有访问付费正文、没有调用外部 LLM。")
    return "\n\n".join(lines)+"\n"
