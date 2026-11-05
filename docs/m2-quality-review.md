# M2 最终独立复验（2026-11-03）

**最终结论：CONDITIONAL PASS。** 全部自动化测试与M1回归通过；事件计数及主张级核验边界成立。真实分类仍有误报、漏报和评论相关性误筛，不能宣称整体分析准确性完全通过。
本节优先于后附2026-11-02历史复核结论：稳态发现延迟已找到 **1条合格样本，307.648秒**，旧“样本为0”的结论不再适用于05:43–06:03 UTC这次后续运行。
本轮未启动新的持续观察，未引入Scrapling/GDELT/新平台/付费服务；未修改业务代码。现有工作区已经包含主张级核验展示，本轮实际检查并增加5项边界回归。
审计证据目录：`data/independent-audit-20261103T042744Z`。修改前SQLite online backup为 `before.sqlite3`，源码快照为 `code-before.zip`。原Git未提交工作保留，没有提交/推送。

## A. 分项验收

| 项目 | 结论 | 实际依据 / 限制 |
|---|---|---|
| 全部pytest | PASS | 140通过、0失败、0跳过，退出0；新增5项复验回归 |
| M1回归 | PASS | 原27项全部通过，退出0；行情原进程继续运行 |
| Binance事故报道族计数 | PASS | 14文章 / 3来源 / 3机构 / 1报道组，非“全部独立事实仅1件” |
| 事件核验边界 | PASS | 组级REPORTED；官方确认仅在具体claim_reviews；其余细节UNVERIFIED |
| 新闻分类质量 | CONDITIONAL PASS | 已修原福利/AI误报，但独立真实抽样仍有分类错误、漏报 |
| 来源健康时间口径 | PASS | 按历史观察时点健康；停采后检查过期正确；今日副本重查三源200 |
| Bloomberg/CoinDesk覆盖 | CONDITIONAL PASS | 今日仍ConnectTimeout，保留错误，不改代理/证书或绕行 |
| 新闻时效 | CONDITIONAL PASS | 1条稳态RSS发现样本；未验证分布、SLA或7×24 |
| 社区观点与最低样本保护 | CONDITIONAL PASS | 7条历史样本UNKNOWN合理；其中3条相关性误筛；不输出分数 |
| 生产数据库保护 | PASS | 新闻、评论、事件、核验、健康、任务等与备份逐行一致；原K线未改 |

## B. 测试与数据保护

实际运行输出（合成/Mock测试仅写pytest临时库，不能代替真实网络接入）：

```text
........................................................................ [ 51%]
....................................................................     [100%]
140 passed in 1.86s
pytest exit_code = 0

...........................                                              [100%]
27 passed in 0.30s
M1 pytest exit_code = 0
```

命令分别为 `.venv/bin/python -m pytest -q` 与 `.venv/bin/python -m pytest -q tests/test_models_database.py tests/test_rest_service.py`。
新增回归位于 `tests/test_m2_final_audit.py`：CNBC/WSJ/Decrypt健康时间边界3项、自动轮询边界1项、7条UNKNOWN无分数1项；原主张级确认隔离测试保留。没有删除、跳过或更改失败案例预期来取得通过。
`pip check` 与 `git diff --check` 均退出0。审计开始135项、结束140项；测试增加不等于真实分类的误判消失。一次M1分组调用误写不存在的 `tests/test_config.py`，退出4且未运行测试，已立即用实际两个M1文件重新运行；完整输出留档。

生产快照为245新闻、54评论；本轮原有3103条K线逐字段不变，检查时已由原M1进程增加至3121条。M2十张被审计表逐行双向EXCEPT均为0变化。SQLite integrity_check=ok，foreign_key_check无异常。
今日网络复查在 `network-recheck.sqlite3` 副本中执行：三源合法RSS手动采集新增57条真实记录仅留在副本；不写回生产库，也不纳入稳态延迟。
实际终端 `sources`、`events --hours 168`、`intel-stats --hours 24`、`brief --hours 168` 与M1 `status` 均退出0；生成的7天简报存在主张级确认，未出现“组级状态：OFFICIALLY_CONFIRMED”。查询后再次逐行比较，生产M2数据仍无变化，详情见 `cli-checks.json`。

## C. Binance安全事件：计数、后续进展与确认范围

当前活动事件组#213：去重文章ID14个、source_id 3个、publisher_id 3个（Cointelegraph 10篇、CNBC 3篇、Decrypt 1篇）。所有14条原始报道保留，3个发布机构并不等于3份独立事实核实。
`event_count=1` 的计量单位为 `INCIDENT_REPORTING_GROUP`：同一次事故的报道族。组内明确保留提现、归因、调查、政治反应、风险评论和媒体所报市场反应；`independent_subevent_count=null`，没有声称归因、提现恢复、RUNE波动等是同一个事实主张。

| 文章ID | 来源 | 报道进展与原文 |
|---|---|---|
| 1 | cointelegraph | [阶段一提现](https://cointelegraph.com/news/binance-says-phase-one-of-withdrawals-opens-after-63b-hack)；WITHDRAWAL_UPDATE |
| 2 | cointelegraph | [FBI归因](https://cointelegraph.com/news/fbi-blames-north-korea-for-record-63b-binance-hack)；ATTRIBUTION_OR_LAW_ENFORCEMENT |
| 9 | cointelegraph | [政治反应](https://cointelegraph.com/news/binance-63b-record-hack-sparks-pre-election-political-chatter)；POLITICAL_REACTION |
| 12 | cointelegraph | [加密股票下跌报道](https://cointelegraph.com/markets/coinbase-leads-crypto-stock-selloff-shares-tumble)；REPORTED_MARKET_REACTION |
| 14 | cointelegraph | [事故回顾](https://cointelegraph.com/news/recap-binances-record-63b-hack-unfolded)；INCIDENT_REPORT_OR_RECAP |
| 15 | cointelegraph | [事故时间线](https://cointelegraph.com/news/live-updates-binance-63b-hack-linked-to-north-koreas-tradertraitor)；INCIDENT_REPORT_OR_RECAP |
| 18 | cointelegraph | [执法响应](https://cointelegraph.com/news/binance-fbi-recover-assets-hack)；ATTRIBUTION_OR_LAW_ENFORCEMENT |
| 24 | cointelegraph | [RUNE价格变化报道](https://cointelegraph.com/markets/rune-token-surges-binance-hack)；REPORTED_MARKET_REACTION |
| 27 | cointelegraph | [链上调查归因](https://cointelegraph.com/news/north-korea-linked-to-63b-binance-hack-by-crypto-investigators)；ATTRIBUTION_OR_LAW_ENFORCEMENT |
| 29 | cointelegraph | [工程师笔记本线索](https://cointelegraph.com/news/binance-hack-may-involve-private-key-misuse-not-theft-blockaid-ceo)；INVESTIGATION_UPDATE |
| 115 | decrypt | [额外入侵点线索](https://decrypt.co/382203/binance-finds-additional-points-of-breach-in-6-3b-hack)；INVESTIGATION_UPDATE |
| 158 | cnbc | [提现及覆盖率声明](https://www.cnbc.com/2026/10/31/binance-hack-asset-coverage-withdrawals.html)；WITHDRAWAL_UPDATE |
| 186 | cnbc | [客户资产风险解读](https://www.cnbc.com/make-it/2026/10/30/binance-crypto-hack-customer-funds.html)；RISK_COMMENTARY |
| 230 | cnbc | [钱包安全评论](https://www.cnbc.com/2026/10/31/binance-hack-crypto-wallet-safety.html)；RISK_COMMENTARY |

另核对：文章#218（**36.4亿美元 / $3.64B**净流出）属于事件组#415；#234（$5.8B净流出）属于#430；#213（ETF资金报道）属于#410，均未并入#213安全事故报道组（注意文章ID和事件ID是不同命名空间）。
没有在这14条标题/摘要中发现明确的另一宗事故被强行合并；但当前属于“事故报道族”而非完整事件图谱，后续进展的独立性尚未逐条事实核验，不能称已证明没有其他独立子事件。基于同品牌/金额的规则仍可能误合并，需保守人工复核。

**本轮重新读取[FBI一手公告](https://www.fbi.gov/investigate/cyber/alerts/2026/north-korea-responsible-for-6-billion-binance-attack)。** 它明确给出：2026-10-29前后Binance有超过60亿美元虚拟资产被盗；FBI将责任归于朝鲜并使用TraderTraitor标签；FBI及合作机构观察到资产主要被换成ETH，并呼吁相关机构阻断所列地址。后续进一步洗钱是其预期，不能写成已经完成。
公告**没有确认**精确$6.3B/$6.4B、工程师笔记本的完整攻击链、20分钟完成、90%资产覆盖、$3B冻结、提现全部恢复、$3.64B/$5.8B净流出、RUNE涨13%、ETF流出或BTC价格因果。不能用FBI公告支持这些其他主张。
实际输出：`corroboration_status=REPORTED`；仅锚定文章#2的有范围主张为 `OFFICIALLY_CONFIRMED`。#2为 `PARTIALLY_ASSESSED` 且 `unreviewed_details_remain=true`；其余13篇 `detail_verification_status=UNVERIFIED`。当前简报写“组级状态REPORTED”和“主张级OFFICIALLY_CONFIRMED”，不会把官方确认扩散到整组；测试还验证一条UNVERIFIED后续主张可与确认主张同时保留。

## D. 真实新闻独立抽样：不以合成样本满分替代质量

人工检查20条已入库RSS记录，覆盖重大宏观、地缘、普通社会政治及加密安全。10条符合预期、1条误报、1条分类错误、6条漏报、2条不确定。样本有目的选择、不是随机盲测，不能据此计算总体准确率；“漏报”指已入库但未被规则选为监控候选，不代表原文被删除。

| ID / 原文 | 当前分类 | 人工复验 |
|---|---|---|
| [#139](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm) | MONETARY_POLICY / High / INDIRECT | 符合预期：不含BTC的FOMC声明正确进入货币政策High/INDIRECT。 |
| [#215](https://www.cnbc.com/2026/11/02/us-iran-war-trump-hormuz-rubio.html) | GEOPOLITICS / High / INDIRECT | 符合预期：不含BTC的美伊战争报道正确进入地缘High/INDIRECT，事实仍待独立核实。 |
| [#188](https://www.sec.gov/newsroom/press-releases/2026-111-sec-issues-exemptive-relief-treasury-clearing-requirements-certain-inter-affiliate-non-us-repo) | FINANCIAL_RISK / High / INDIRECT | 符合预期：美债清算豁免具有合理融资/流动性路径，不是BTC方向预测。 |
| [#38](https://www.wsj.com/world/middle-east/oil-prices-rise-after-hormuz-tanker-attack-houthi-claims-stoke-supply-fears-de48df37?mod=rss_worldnews) | GEOPOLITICS / High / INDIRECT | 符合预期：冲突及能源供应忧虑进入重大事件候选。 |
| [#41](https://www.wsj.com/business/energy-oil/oil-prices-fall-as-traders-weigh-u-s-iran-diplomacy-afe80fa9?mod=rss_worldnews) | ENERGY / High / INDIRECT | 符合预期：油价与外交谈判进入能源候选。 |
| [#222](https://www.cnbc.com/2026/11/01/social-security-senate-races.html) | OTHER / Low / IRRELEVANT | 符合预期：参议院与福利前景保持Low/IRRELEVANT，无泛化路径。 |
| [#223](https://www.cnbc.com/2026/11/01/social-security-benefit-cuts-2032.html) | OTHER / Low / IRRELEVANT | 符合预期：个人退休福利削减保持Low/IRRELEVANT。 |
| [#225](https://www.cnbc.com/2026/11/01/jpmorgan-amazon-ai-agents-meta-muse.html) | OTHER / Low / IRRELEVANT | 符合预期：企业AI策略未误判为机构BTC事件。 |
| [#214](https://decrypt.co/382295/how-to-run-ai-model-locally-why-you-might-want) | OTHER / Low / IRRELEVANT | 符合预期：本地AI教程保持Low/IRRELEVANT。 |
| [#159](https://www.cnbc.com/2026/10/31/trump-murdoch-wsj-epstein-defamation-lawsuit-dismissed.html) | OTHER / Low / IRRELEVANT | 符合预期：个人诽谤诉讼保持Low/IRRELEVANT。 |
| [#78](https://www.wsj.com/world/africa/trumps-deportation-deal-with-cameroon-will-equip-unit-accused-of-war-crimes-a94d3faa?mod=rss_worldnews) | GEOPOLITICS / High / INDIRECT | 误报：战争罪指控相关遣返/装备协议被war词升级；现有摘要没有明确全市场传导证据，应普通政治或待评估。 |
| [#142](https://www.federalreserve.gov/newsevents/pressreleases/other20261009a.htm) | MONETARY_POLICY / High / INDIRECT | 分类错误：家庭财务调查不是利率决策；policymakers内的policy子串误触发货币政策，应经济调查/常规信息并另评重要性。 |
| [#65](https://www.wsj.com/world/europe/ukraine-hits-russian-oil-refinery-ending-a-pause-and-defying-trump-be68eeff?mod=rss_worldnews) | OTHER / Low / IRRELEVANT | 漏报：Hits/refinery词形未覆盖，真实俄炼油厂遭袭被Low/IRRELEVANT；应地缘或能源候选。 |
| [#238](https://www.wsj.com/world/europe/u-s-pushes-to-restore-russian-gas-sales-to-europe-via-ukraine-0ca62dc7?mod=rss_worldnews) | OTHER / Low / IRRELEVANT | 漏报：Russian Gas/restore未覆盖，能源停火与恢复供气被Low/IRRELEVANT；应能源/地缘候选。 |
| [#144](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261007a.htm) | OTHER / Low / IRRELEVANT | 漏报：Federal Open Market Committee全称/Minutes未覆盖，官方FOMC会议纪要被Low/IRRELEVANT；应货币政策候选。 |
| [#25](https://cointelegraph.com/news/trezor-cryptobilis-wallet-implant-funds-warning) | OTHER / Low / IRRELEVANT | 漏报：Trezor/CryptoBilis实体未覆盖，硬件钱包安全警告被忽略；应加密安全候选，suspected不能确认为真。 |
| [#114](https://decrypt.co/382216/trezor-warns-cryptobilis-buyers-after-report-of-hardware-implant-in-safe-5) | OTHER / Low / IRRELEVANT | 漏报：同一Trezor安全报道在Decrypt仍被忽略；候选报道应保留未核实状态。 |
| [#244](https://cointelegraph.com/news/btcpay-server-hot-wallet-thefts-older-versions) | OTHER / Low / IRRELEVANT | 漏报：BTCPay与钱包盗币实体未覆盖，报告盗窃被忽略；应加密安全候选。 |
| [#170](https://www.cnbc.com/2026/10/31/trump-big-oil-refining-profits.html) | ENERGY / High / INDIRECT | 不确定：利润稿与能源供应紧张并存，High是否过度需结合事件规模，不凭标题判定。 |
| [#245](https://www.wsj.com/economy/china-private-manufacturing-gauge-shows-steady-expansion-in-october-9e3be2ca?mod=rss_worldnews) | OTHER / Low / IRRELEVANT | 不确定：RSS仅有制造业及AI需求摘要；公开页表明含PMI，但未给异常程度，不能肯定High；也不能自动视为普通AI。 |

FOMC声明#139、美债清算#188、美伊#215、能源#38/#41均不需要BTC关键词即可进入候选；原#222/#223福利及#225 AI误报确已修好。
真实新发现的P1缺口包括：FOMC全称会议纪要、Hits/refinery、Russian Gas、Trezor/BTCPay实体覆盖不足；war词与policy子串仍可能误报。已重新读取[官方会议纪要发布页](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261007a.htm)及[WSJ炼油厂报道公开摘要](https://www.wsj.com/world/europe/ukraine-hits-russian-oil-refinery-ending-a-pause-and-defying-trump-be68eeff)确认对应内容存在；BTCPay原文本轮网络核验超时，仅以已存RSS报告作为分类审查输入，不冒充事实已确认。
按本轮边界将这些非阻塞规则问题登记，不继续扩大修复范围；因此不能把上一轮42条合成自测全对解释成真实新闻没有漏报。

## E. 数据源健康与时钟基准

生产库最后成功时间均来自11月2日持续轮询；按 **2026-11-02T06:03:10Z** 计算如下（没有拿今天的墙钟回推当时状态）：

| 来源 | 最后成功检查UTC | 最新RSS报告时间UTC | 当时状态 / network_stale / content_stale |
|---|---|---|
| decrypt | 2026-11-02T06:03:06.899Z | 2026-11-01T16:01:02.000Z | HEALTHY / False / False |
| wsj | 2026-11-02T06:03:07.694Z | 2026-11-02T05:58:00.000Z | HEALTHY / False / False |
| cnbc | 2026-11-02T06:03:08.821Z | 2026-11-02T05:09:45.000Z | HEALTHY / False / False |

- `network_stale` 使用查询时刻减 `last_success_ms`，阈值为 `max(3×interval,900秒)`；三源interval=300秒，超过15分钟没有成功检查即为true。它表示检查结果过期，不是已经证明网站断网。
- `content_stale` 使用查询时刻减源报告的 `last_published_ms`；三源阈值48小时。不是用首次发现或程序启动时间判断。官方低频源另有较长阈值。
- `connection_status` 保留最近一次检查结果，`health_status` 是查询时综合状态。停采后 `connection_status=HEALTHY` 与 `health_status=STALE/network_stale=true` 可以同时出现，含义分别是“上次成功”和“目前未刷新”。不能只取前者声称正在运行。
- 审计当日生产M2未重启，所以三源network_stale=true而content_stale仍false是正确结果；不是错误将旧文章当网络失败。HTTP304也刷新成功检查，不能据此宣称有新内容。
- `last_published_ms` 为RSS源报告时间，CNBC部分日期会后改；页面核对的初始发布时间另存 `verified_published_at_ms`，不覆盖原RSS。负延迟异常不参与稳态样本。当前未发现影响这三源48小时阈值判断的时间矛盾。

今日本机使用相同正式适配器、TLS校验和有限重试对副本复查；不使用系统代理、不跟随未审查重定向：

| 来源 | 本轮检查完成UTC | 真实结果 | 最新源发布时间UTC |
|---|---|---|
| coindesk | 2026-11-03T04:32:05.827Z | 未收到HTTP响应 / NETWORK_ERROR；ConnectTimeout：请求失败（已有限重试） | 未取得 |
| decrypt | 2026-11-03T04:31:41.922Z | HTTP 200 / HEALTHY | 2026-11-02T23:10:25.000Z |
| wsj | 2026-11-03T04:31:42.053Z | HTTP 200 / HEALTHY | 2026-11-03T03:00:00.000Z |
| bloomberg | 2026-11-03T04:32:06.933Z | 未收到HTTP响应 / NETWORK_ERROR；ConnectTimeout：请求失败（已有限重试） | 未取得 |
| cnbc | 2026-11-03T04:31:42.596Z | HTTP 200 / HEALTHY | 2026-11-03T04:27:41.000Z |

生产库原有Bloomberg/CoinDesk ConnectTimeout记录与失败时间保留；今日副本再次重现，均没有成功新闻，不能声称接通。三源今日200仅证明本次RSS可达，不自动将生产库旧健康记录改为今日成功，也不是持续运行证据。

## F. WSJ 06:03新增记录与稳态时效

定位到真实文章 **#245 / WP-WSJ-0004025748**：[亚洲制造业活动与AI需求报道](https://www.wsj.com/economy/china-private-manufacturing-gauge-shows-steady-expansion-in-october-9e3be2ca?mod=rss_worldnews)。原始日期字符串：`Mon, 02 Nov 2026 05:58:00 GMT`。

| 时间 / 字段 | 实际值 |
|---|---|
| RSS报告发布时间 | 2026-11-02T05:58:00.000Z |
| 上一轮请求开始 / 成功完成 | 05:58:05.530Z / 05:58:06.718Z |
| 本轮请求开始 / 文章首次发现 | 06:03:06.802Z / 06:03:07.648Z |
| 本轮采集完成 | 06:03:07.694Z |
| collection_runs.id / run_mode | 110 / continuous |
| 本轮结果 | HTTP200、71篇、1新增、monitor_inserted=1、backfill_inserted=0 |
| discovery_kind / delay_quality | MONITOR_NEW / VALID_MONITOR |
| published→first_seen | **307648毫秒 = 307.648秒 ≈5分7.648秒** |

WSJ前五轮均HTTP200成功：05:43:03.524、05:48:04.495、05:53:05.535、05:58:06.718、06:03:07.694。该源此前已初始化，本轮距上次成功检查300.084秒，未超900秒恢复阈值；发布时间距上一成功检查仅早6.718秒，未落入“早于previous_check减300秒”的源站迟到排除区；无中间故障、日期缺失、改写或负延迟。article_time_history只有同一源日期观察，故此条符合当前筛选规则。
**结论：不是首次回填、人工采集或故障恢复；稳态样本总数为1。** 分类为IRRELEVANT不会改变它作为“RSS发现链路”样本的有效性；它不单独证明重大BTC新闻的时延。
发布时间比上一轮抓取略早仍未发现，可能与RSS/CDN分发延迟或源报告时间有关；仅凭两轮响应无法分离源站发布、缓存和轮询各自耗时。不将307.648秒说成纯网络请求延迟、SLA、p95或统计分布，也不宣称已验证全天近实时。今日副本手动新增57条全部排除。
后续如需延迟评估：保持现有合法300秒轮询，在已完成初始化且持续成功的连续窗口中等待更多新发表文章，保留每轮成功时间和源时间修订；逐条排除初始化/人工/恢复/迟到/异常，再按源报告样本数和分位数。若窗口没有合格新文章，应如实报0，不缩短间隔或制造样本。本轮不再自动启动长跑。

## G. 历史7条UNKNOWN与当前样本

历史窗口固定为2026-11-01T06:03:10Z至2026-11-02T06:03:10Z：规则筛出7条、5主题，四分类0/0/0/7；明确方向与评分分母都为0，score=null，提示“暂无可信情绪信号”。累计仍54条原始评论、17条规则相关；这17条不是人工确认有效的投资观点。

| 评论原文 | 人工检查 | UNKNOWN是否合理 |
|---|---|---|
| [50323075](https://news.ycombinator.com/item?id=50323075) | 市场语境/歧义：价格操纵/赔偿机制的假设与否定，不是作者当前明确多空。 | 合理；未强制转中性或多空 |
| [50325698](https://news.ycombinator.com/item?id=50325698) | 相关性误筛：挖矿取暖及耗能技术；行业怀疑不等于BTC价格看空。 | 合理；未强制转中性或多空 |
| [50326369](https://news.ycombinator.com/item?id=50326369) | 相关性误筛：AI数据中心/GPU与矿机类比；sold/holding等泛词误触发。 | 合理；未强制转中性或多空 |
| [50326967](https://news.ycombinator.com/item?id=50326967) | 相关性误筛：硬件加密密钥案例与历史币值，并非当前BTC投资观点。 | 合理；未强制转中性或多空 |
| [50328100](https://news.ycombinator.com/item?id=50328100) | 市场语境/歧义：价值存储与基本面正面论述，可能隐含多头，但混合否定和用途辩论，没有明确持仓/价格方向。 | 合理；未强制转中性或多空 |
| [50330251](https://news.ycombinator.com/item?id=50330251) | 市场语境/歧义：假设dump-and-pump机制；不是作者当前实际持仓声明。 | 合理；未强制转中性或多空 |
| [50332711](https://news.ycombinator.com/item?id=50332711) | 市场语境/歧义：引文/历史用途/价值存储论述，不能可靠推断当前价格方向。 | 合理；未强制转中性或多空 |

其中50325698、50326369、50326967偏取暖挖矿、GPU和硬件安全类比，不应作为BTC投资者观点样本。保守UNKNOWN避免了方向性误导，但不能代替修正相关性筛选；该问题列为P1，不为提高样本数修改分类。50328100、50332711可能有隐含积极态度，规则不承诺可靠解析，允许UNKNOWN。
到11月3日本轮审计时，生产库过去24小时相关评论已为0；历史“7条”不能冒充当前新鲜评论。HN采样单一、有界且偏技术人群，不能代表全球BTC投资者。

## H. 未解决问题与M2.5建议

1. P1新闻规则：上表真实误报/分类错误与六条漏报（含同一Trezor事件两家报道），应优先补实体、词形和政策全称，并防止policy/war泛化。合成评测覆盖不足仍存在。
2. P1评论相关性：技术类比和历史价值描述会命中泛化金融词；历史7条中3条误筛。保守无分数正确，但有效市场样本仍不足。
3. 事件组是事故报道族；独立子事件识别、复杂金额角色和无署名转载判定仍需人工，不能视为完善事件图谱。官方确认只限具体主张。
4. 只有1条稳态样本，无法验证延迟分布和7×24稳定性；M2停止后健康会正确过期。下一阶段不要把“采集命令退出正常”当覆盖完整。
5. Bloomberg/CoinDesk真实网络未通，Reuters/Reddit授权等原覆盖限制仍在；未接入来源不能依靠适配器存在获得通过。

**不建议立即扩平台掩盖现有质量缺口。建议先验收本轮CONDITIONAL PASS并安排上述P1质量任务，再决定进入M2.5。** 未发现需本轮修改生产业务代码/数据库的新增P0，未宣称无缺陷；本轮仅新增回归与审计记录，停止等待产品指令。

## I. 可复现命令

```bash
cd /Users/wangzihan/Desktop/btc-intelligence
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest -q tests/test_models_database.py tests/test_rest_service.py
.venv/bin/btc-intelligence sources --json
.venv/bin/btc-intelligence events --hours 168 --limit 1000 --json
.venv/bin/btc-intelligence intel-stats --hours 24 --json
.venv/bin/btc-intelligence brief --hours 168 --output data/brief-audit-7d.md
sqlite3 -header -column data/btc.sqlite3 "SELECT id,source_id,published_raw,datetime(published_at_ms/1000,'unixepoch') AS published_utc,datetime(first_seen_ms/1000.0,'unixepoch') AS first_seen_utc,discovery_kind,delay_quality,discovery_delay_ms FROM news_articles WHERE id=245;"
```

查询时窗口随当前时刻移动；固定历史窗口证据见 `health-historical.json`、`social-audit.json`、`wsj-discovery-trace.json`。`network-recheck.json`为今日副本真实网络测试，`all_tests-final.txt`/`m1_regression-final.txt`为Mock/合成自动化回归，两者分开。

---

# 2026-11-02历史质量修复记录（保留追溯）

以下为当时快照。其“134项测试”“稳态样本0”等历史结论由上面2026-11-03复验更新，不能当作最新结论。

# M2 数据质量复核与最终验收

复核日期：2026-11-02；最终数据快照 `2026-11-02T05:35:37.974Z`，时间均 UTC。结论：**CONDITIONAL PASS**。
本轮仅修复 M2，未增加 Scrapling、GDELT、商业 API、云部署、Dashboard、衍生品分析、自动交易或主动推送。

## 1. 修复前的问题与保护措施

- P0 事件展示：旧简报的整组统计确有三家媒体，但只截取前三篇 Cointelegraph 文章，统计口径与展示证据不一致；旧字段也混淆文章、数据源和独立机构。
- P0 宏观相关性：`sec` 前缀会误命中 security，`strategy` 会误触发机构事件；普通福利、选举和企业 AI 新闻被归入 INDIRECT，且生成不匹配路径。
- P0 真实性：采到 RSS、页面可访问、媒体发表、事实交叉核实及官方确认没有充分分层；重大主张缺少明确审核范围。
- P0 情绪：缺少“累计→窗口→相关→明确多空→可评分”的解释，容易将 UNKNOWN=100%误读为中性。
- P1 健康：旧 OK 及历史条数容易被误当当前健康，HTTP304没有独立展示口径。
- P1 时效：手动采集不能证明持续监控；旧延迟范围混入回填，部分 RSS 日期后续改写造成负延迟。

开始时原有75项测试全部通过。工作区已有未提交 M2 内容，未重建、未重置 Git，也未提交或推送。
修改前使用 SQLite online backup 保存 **1693 根 K线、231篇原始新闻、54条评论记录**。
备份目录：`/Users/wangzihan/Desktop/btc-intelligence/data/quality-review-20261102T045724Z`，含 `before.sqlite3`、`workspace-before.zip`、`state-before.json`。
未备份或展示真实 `.env` 凭证，实际数据和日志仍被 Git 忽略。

## 2. 模块修复与统计定义

- `analysis.py`：六层内容类型识别后再判断 DIRECT/INDIRECT/IRRELEVANT/UNKNOWN，最后判重要性。普通财经/政治/科技没有具体金融冲击条件时不生成影响路径。规则版本 **m2-quality-2.0**。
- `events.py` / `storage.py`：文章数 `article_count`、不同来源数 `source_count`、按 `publisher_id`/通讯社归并的 `independent_publisher_count`、事件数 `event_count` 分开。重复文本的候选证据组再另计，不自动认定独立事实核实。
- 机构计数依赖明确的机构目录，不按不同频道/域名自动独立。同母机构复用 publisher_id；有明确 Reuters 等通讯社归属时归并原始机构。
- 事件以具体主题、实体、动作、金额及72小时内进展保守关联；同实体不同事故/金额/明确日期不强行合并。同一事件跨两天的后续报道可关联。
- 派生关联重算前写 `event_link_history`，旧候选标不活跃。相同成员集合复用事件 ID，不清空新闻或评论。
- `validation.py`：检查已审查媒体域名、HTTP结果和公开页面标题/发布时间；不抓订阅正文，不绕403或验证码，不跟随跨机构重定向。
- `event_reviews`：记录 REPORTED/CORROBORATED/OFFICIALLY_CONFIRMED/DISPUTED/UNVERIFIED，明确已核实主张与证据。确认随原始证据文章绑定，不能从媒体数量升级。
- `queries.py` / `report.py`：按机构展示代表文章、列明总口径和审核范围。普通新闻不再出现在重大宏观段。报道、假设路径、实际市场反应分开；市场反应仍为 NOT_MEASURED。
- `service.py` / `transport.py`：复用独立轮询，记录 HTTP200/304/网络错误、运行模式、重复/回填/监控新增及检查时间，故障隔离与有限重试保持。
- `source_health` 新 health_status 与旧 status 分开，兼容原 CLI；连接、内容陈旧、授权状态和历史错误分别提供。
- `social.py`：新增实际批次过滤计数；评论对象（BTC价格、技术、行业、交易所风险）及转述/否定/条件/反讽分开。模糊语义仍 UNKNOWN。

迁移版本3，可重复执行；原迁移测试仅将版本断言2更新为3，所有数据保留断言保留，未删除或跳过失败测试。
原文、URL、首次发现时间保持；正文修订与来源日期变动分别留在 article_revisions / article_time_history。
新增已核对页面发布时间为独立派生字段 verified_published_at_ms，不覆盖原始 RSS 日期。
窗口查询优先该媒体页面标题对应时的公开原始发布时间，否则使用 RSS 报告时间并披露边界。

## 3. 修复前后效果

真实数据库中的三个误报例子：

| 原始记录 | 修复前 | 修复后 | 路径处理 |
|---|---|---|---|
| [These Senate races may help determine the fate of Social Security](https://www.cnbc.com/2026/11/01/social-security-senate-races.html) | REGULATION / INDIRECT / Medium | OTHER / IRRELEVANT / Low | 已清空不匹配路径 |
| [Social Security may have to cut retirement benefits in six years. Here's how much money is at stake for beneficiaries](https://www.cnbc.com/2026/11/01/social-security-benefit-cuts-2032.html) | REGULATION / INDIRECT / Medium | OTHER / IRRELEVANT / Low | 已清空不匹配路径 |
| [For JPMorgan, Amazon, fighting AI bots like Meta Muse may not be a winning long-term strategy](https://www.cnbc.com/2026/11/01/jpmorgan-amazon-ai-agents-meta-muse.html) | INSTITUTIONAL / INDIRECT / Medium | OTHER / IRRELEVANT / Low | 已清空不匹配路径 |

42个人工标注质量样本（合成测试，非真实新闻）：修复前精确分类 **32/42**，修复后 **42/42**；相关性误报 **7→0**，重大事件相关性漏报 **0→0**。
其余旧错误属于类别/等级不匹配。正例战争、央行、CPI/PCE/非农/GDP、美债/美元、ETF及安全事件保留 High/Critical/Medium 的明确依据，并非统一降级。
这些样本参与开发，不是独立盲测，不能作为真实世界准确率保证。对含糊、隐含和跨语言信息仍可能漏报。
完整逐例前后输出见备份目录 `classification-comparison.json`，标注见 `tests/fixtures/news-quality-cases.json`。

事件实际修复结果：当前同一 Binance 安全事件候选 **14 篇文章 / 3 个来源 / 3 家机构 / 1 个事件**。
机构列表：cnbc, cointelegraph, decrypt。简报分别展示这三家代表链接，`events --json` 保留全部14篇，不再截成同一家三篇。
这只修复来源口径与展示，不将14篇等同于14家，或把三家等同于三份独立事实证明。
已用合成测试覆盖同源3篇、独立媒体3篇、同一通讯社被3站转载、同母机构多频道、跨两天跟进和同实体不同事故。

## 4. 至少20条原始新闻核验

实际抽查 **28 条**，覆盖 Fed、SEC、CNBC、WSJ、Decrypt、Cointelegraph 六类源。
结果：**16条媒体页面标题对应，4条页面标题未能对应，4条SEC页面403，4条WSJ页面网络超时**。
HTTP200只证明可访问；标题对应只支持媒体确实发表了对应标题，**不独立证明正文主张为真**。
受限/超时/标题不对应均标为无法独立核验，未判为假新闻，也未声称完成独立事实核实。

| 文章/源 | 原始链接与标题 | HTTP | 媒体发表核验 | 页面访问 | 页面公开原始时间 UTC（若有） |
|---|---|---:|---|---|---|
| 138 / fed | [Federal Reserve Board announces approval of application by The Bank of Nova Scotia ](https://www.federalreserve.gov/newsevents/pressreleases/orders20261029a.htm) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 缺失 |
| 139 / fed | [Federal Reserve issues FOMC statement ](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 缺失 |
| 140 / fed | [Federal Reserve Board announces termination of enforcement actions with Gardner Bancshares, Inc. and Small Business Bank ](https://www.federalreserve.gov/newsevents/pressreleases/enforcement20261016a.htm) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 缺失 |
| 141 / fed | [Minutes of the Board's discount rate meetings on August 17, September 9, and September 16, 2026 ](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261013a.htm) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 缺失 |
| 188 / sec | [SEC Issues Exemptive Relief from Treasury Clearing Requirements for Certain Inter-Affiliate and Non-U.S. Repo Transactions ](https://www.sec.gov/newsroom/press-releases/2026-111-sec-issues-exemptive-relief-treasury-clearing-requirements-certain-inter-affiliate-non-us-repo) | 403 | UNVERIFIED | RESTRICTED | 缺失 |
| 189 / sec | [Two Entities Charged in $130 Million Fraud Scheme That Used False SEC Filings to Boost Investor Confidence ](https://www.sec.gov/newsroom/press-releases/2026-110-two-entities-charged-130-million-fraud-scheme-used-false-sec-filings-boost-investor-confidence) | 403 | UNVERIFIED | RESTRICTED | 缺失 |
| 190 / sec | [SEC Announces Fiscal Year 2027 Examination Priorities ](https://www.sec.gov/newsroom/press-releases/2026-109-sec-announces-fiscal-year-2027-examination-priorities) | 403 | UNVERIFIED | RESTRICTED | 缺失 |
| 191 / sec | [SEC and AMF Announce Supervisory MOU To Enhance Cooperation for Investment Advisers and Investment Service Providers ](https://www.sec.gov/newsroom/press-releases/2026-108-sec-amf-announce-supervisory-mou-enhance-cooperation-investment-advisers-investment-service) | 403 | UNVERIFIED | RESTRICTED | 缺失 |
| 217 / cnbc | [Canada-India $5.5 billion bank takeover attracts opposition from workers, politicians ](https://www.cnbc.com/2026/11/02/canada-india-bank-takeover-protest-workers.html) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 2026-11-02T04:09:34.000Z |
| 216 / cnbc | [Sam Altman makes surprise South Korea visit as OpenAI builds on chip partnerships ](https://www.cnbc.com/2026/11/02/openai-sam-altman-samsung-sk-south-korea.html) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 2026-11-02T02:58:53.000Z |
| 215 / cnbc | [Rubio says Trump wants to end Iran war 'peacefully' even as both sides prepare for strikes ](https://www.cnbc.com/2026/11/02/us-iran-war-trump-hormuz-rubio.html) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 2026-11-02T02:38:07.000Z |
| 218 / cnbc | [Binance sees $3.64 billion in net outflows as withdrawals resume after massive hack ](https://www.cnbc.com/2026/11/02/binance-outflow-hack-bitcoin.html) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 2026-11-02T00:11:37.000Z |
| 237 / wsj | [The U.S. Once Dominated the World’s Oceans. China’s Xi is Changing That. ](https://www.wsj.com/world/china/china-xi-maritime-dominance-ef5f5c5a?mod=rss_worldnews) | 超时 | UNVERIFIED | NETWORK_ERROR | 缺失 |
| 238 / wsj | [U.S. Pushes to Restore Russian Gas Sales to Europe Via Ukraine ](https://www.wsj.com/world/europe/u-s-pushes-to-restore-russian-gas-sales-to-europe-via-ukraine-0ca62dc7?mod=rss_worldnews) | 超时 | UNVERIFIED | NETWORK_ERROR | 缺失 |
| 239 / wsj | [Serbia’s Gen Z Students Toppled a Strongman. Now Comes the Hard Part. ](https://www.wsj.com/world/europe/serbias-gen-z-students-toppled-a-strongman-now-comes-the-hard-part-0f40dd7a?mod=rss_worldnews) | 超时 | UNVERIFIED | NETWORK_ERROR | 缺失 |
| 241 / wsj | [Opinion / Brazil’s Order Against Bolsonaro Was Appropriate ](https://www.wsj.com/opinion/brazils-order-against-bolsonaro-was-appropriate-1ebec324?mod=rss_worldnews) | 超时 | UNVERIFIED | NETWORK_ERROR | 缺失 |
| 213 / decrypt | [Bitcoin ETF Investors Head for the Exits After Record Binance Hack ](https://decrypt.co/382309/bitcoin-etf-investors-exits-record-binance-hack) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 缺失 |
| 214 / decrypt | [How to Run an AI Model Locally—And Why You Might Want To ](https://decrypt.co/382295/how-to-run-ai-model-locally-why-you-might-want) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 缺失 |
| 99 / decrypt | [Binance Hack: Everything You Need to Know About the Biggest Crypto Heist in History ](https://decrypt.co/382306/binance-hack-everything-you-need-to-know) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 缺失 |
| 100 / decrypt | [Why AI Models Cheat: Reward Hacking, Explained ](https://decrypt.co/382274/why-ai-models-cheat-reward-hacking-explained) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 缺失 |
| 232 / cointelegraph | [Bank of Korea probes financial firms’ exposure to crypto risks ](https://cointelegraph.com/news/bank-of-korea-probes-financial-firms-exposure-to-crypto-risks) | 200 | TITLE_NOT_VERIFIED | PUBLIC_METADATA | 2026-11-02T03:55:50.905Z |
| 233 / cointelegraph | [THORChain halts swaps after block reorg bug, slowing Binance hackers ](https://cointelegraph.com/news/thorchain-halts-swaps-after-block-reorg-bug-slowing-binance-hackers) | 200 | TITLE_NOT_VERIFIED | PUBLIC_METADATA | 2026-11-02T01:51:48.436Z |
| 234 / cointelegraph | [Binance net outflows surge to $5.8B as withdrawals resume after record hack ](https://cointelegraph.com/news/binance-net-outflows-surge-to-58b-as-withdrawals-resume-after-record-hack) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 2026-11-01T23:59:27.071Z |
| 235 / cointelegraph | [THORChain founder rejects freeze request, CZ thanks Secret Service: Hodler’s Digest ](https://cointelegraph.com/magazine/36b-flees-binance-on-reopen-thorchain-co-founder-opposes-coin-freeze-hodlers-digest) | 200 | TITLE_NOT_VERIFIED | PUBLIC_METADATA | 2026-11-01T23:09:13.135Z |
| 1 / cointelegraph | [Binance says phase one of withdrawals opens after $6.3B hack ](https://cointelegraph.com/news/binance-says-phase-one-of-withdrawals-opens-after-63b-hack) | 200 | TITLE_NOT_VERIFIED | PUBLIC_METADATA | 2026-11-01T09:38:18.486Z |
| 158 / cnbc | [Binance resumes withdrawals following $6.3 billion hack, says 90% of stolen user assets are covered ](https://www.cnbc.com/2026/10/31/binance-hack-asset-coverage-withdrawals.html) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 2026-10-31T16:03:24.000Z |
| 2 / cointelegraph | [FBI blames North Korea for record $6.3B Binance hack ](https://cointelegraph.com/news/fbi-blames-north-korea-for-record-63b-binance-hack) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 2026-11-01T07:44:38.196Z |
| 169 / cnbc | [Qatari mediators held talks in Tehran aimed at restarting direct U.S.-Iran negotiations, source says ](https://www.cnbc.com/2026/10/31/qatar-iran-us-talks-mediation.html) | 200 | PUBLISHER_PAGE_MATCH | PUBLIC_METADATA | 2026-10-31T12:11:12.000Z |

样本域名归属检查均匹配；同站合法重定向可追踪。RSS内容哈希/来源ID/URL去重与事件原始链接保留。
部分 CNBC 页面 `article:published_time` 与 RSS 日期有差异：这说明 RSS 时间不一定是初次发表时间，而非自动证明内容虚假。
页面时间只在同媒体 HTTP200 且标题对应后单独提供，原始 RSS 值完整保留。

重大事件核验：

1. **Binance 安全事件：OFFICIALLY_CONFIRMED，仅限以下主张。**
   [FBI 2026-10-31 一手公告](https://www.fbi.gov/investigate/cyber/alerts/2026/north-korea-responsible-for-6-billion-binance-attack)称10月29日前后发生超过60亿美元的资产盗窃，并作出 TraderTraitor 归因。
   该公告不确认每篇文章的精确6.3B数字、受损笔记本机制、提现恢复比例、后续净流出金额或 BTC 价格影响。简报明确显示核实范围，不将整组标题所有细节标为已证实。
2. **Fed 发布FOMC声明：OFFICIALLY_CONFIRMED，仅确认公告存在。**
   [官方2026-10-28声明](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm)实际HTTP200且标题对应；并非确认其已经影响 BTC。
3. **美伊局势及Rubio表述：UNVERIFIED。**
   [CNBC原始报道](https://www.cnbc.com/2026/11/02/us-iran-war-trump-hormuz-rubio.html)HTTP200、标题对应，但本轮没有找到完全对应的权威原始确认，不凭多家报道升级官方确认。

## 5. 社区评论与情绪

当前累计原始评论 **54条**：BTC市场相关 **17条**，不相关/非投资语境 **37条**；没有删除这些原始记录来美化样本数。
24小时漏斗：累计54 → 时间窗内7 → BTC市场相关7 → 明确多空0 → 可评分0。
累计相关17中 **10条在24小时窗口外**，因此“17累计、7在窗口”并非重复丢失。当前7条来自5个主题，全部 UNKNOWN。

最新有效评论 `2026-11-02T03:10:20.000Z`；示例：[真实评论50332711](https://news.ycombinator.com/item?id=50332711)、[真实评论50330251](https://news.ycombinator.com/item?id=50330251)。
它们讨论技术/货币用途/事件经济机制，没有足够明确的自身 BTC 价格方向；Unknown 不转 Neutral。
批次真实诊断还记录发现主题31个、评论候选20个、检查64条、技术主题排除9个、删除/隐藏3个、无关44条、相关17条、重复17/新增0。
这些是一个批次的不同阶段计数，不能相加当作全站评论总量；官方parent链回溯与子树扫描有界，搜索索引和部分树遍历仍可能漏样本。

方向分数只有明确 BULLISH+BEARISH 达20条才输出；中性可参与分母但不能单靠中性数量满足方向门槛。
当前明确输出 **暂无可信情绪信号**。HN偏技术社区，不能称全球BTC情绪；Reddit没有审批/OAuth，覆盖缺口仍在。

人工标注情绪自测 **46/48，95.83%**，不是独立盲测或真实泛化准确率。
支持中英明确观点；否定、条件、引用、反讽、多资产及隐含语义保守处理。两个未覆盖的同义涨跌表述仍漏判为 UNKNOWN，未强行提高方向样本。

| 期望/输出 | BULLISH | BEARISH | NEUTRAL | UNKNOWN |
|---|---:|---:|---:|---:|
| BULLISH | 9 | 0 | 0 | 1 |
| BEARISH | 0 | 8 | 0 | 1 |
| NEUTRAL | 0 | 0 | 8 | 0 |
| UNKNOWN | 0 | 0 | 0 | 21 |

各类 precision/recall/support：`{"BULLISH": {"precision": 1.0, "recall": 0.9, "support": 10}, "BEARISH": {"precision": 1.0, "recall": 0.8889, "support": 9}, "NEUTRAL": {"precision": 1.0, "recall": 1.0, "support": 8}, "UNKNOWN": {"precision": 0.913, "recall": 1.0, "support": 21}}`。

## 6. 实际持续采集与发现时效

观察从 **2026-11-02T05:02:59.412384+00:00** 到 **2026-11-02T05:23:59.755340+00:00**，共 **1260.343秒，约21分钟**（北京时间13:02:59～13:23:59）。
全部现有已启用来源，生产轮询间隔未缩短；低频官方源600秒，其余通常300秒。网络恢复与重启保留 ETag/队列/冷却状态。

| 来源 | 轮询/批次 | HTTP200 / 304 | 检查成功率 | 失败批次 | 新增记录 | 重复条目 | 回填 / 合格监控新增 |
|---|---:|---|---|---:|---:|---:|---|
| bloomberg | 4 | 0 / 0 | 0.0% | 4 | 0 | 0 | 0 / 0 |
| cnbc | 5 | 5 / 0 | 100.0% | 0 | 0 | 150 | 0 / 0 |
| coindesk | 4 | 0 / 0 | 0.0% | 4 | 0 | 0 | 0 / 0 |
| cointelegraph | 5 | 5 / 0 | 100.0% | 0 | 5 | 145 | 5 / 0 |
| decrypt | 5 | 5 / 0 | 100.0% | 0 | 0 | 195 | 0 / 0 |
| fed | 3 | 0 / 3 | 100.0% | 0 | 0 | 0 | 0 / 0 |
| hn | 4 | 0 / 0 | API批次 4/4 | 0 | 0 | 68 | 0 / 0 |
| sec | 3 | 2 / 1 | 100.0% | 0 | 0 | 50 | 0 / 0 |
| wsj | 5 | 5 / 0 | 100.0% | 0 | 7 | 348 | 7 / 0 |

RSS成功率口径为每次来源检查最终HTTP结果（含304），不是逐次底层重试成功率。HN按API批次计，未伪造每个HTTP请求的成功率；单请求重试分布尚未细化。
21分钟内新增12篇文章全部为启动回填，新增评论0。可用六个RSS源均100%完成检查，HN4/4批次完成；两个网络异常源各4次失败，没有中断其他来源。
进程安全停止，**退出码2**如实表示部分来源失败，不是崩溃；M1原有进程保留。原始日志 `continuous.log` 与起止清单 `observation.json` 可复现审计。

**合格稳态发现延迟样本量0，暂未取得有效的实时延迟样本，故没有均值/分位数分布。**
不能声称期间没有任何新闻发表，只能说未观察到合格 MONITOR_NEW 样本。首次导入/人工/恢复回填/源站迟到、旧记录未知模式和时间异常均排除。
历史检查另外发现3篇 RSS 时间晚于首次发现，其中某条 RSS 由00:11:37改写为05:09:45，而公开页面仍给出00:11:37。
已保留RSS时间变动和独立页面时间，标 NEGATIVE_TIME_ANOMALY，未移动首次发现时间、未取绝对值制造正常延迟。
来源自身发布延迟与系统轮询延迟无法只凭RSS完全分离；本次也不是7×24小时稳定性验收。

## 7. 最新来源健康与覆盖

以下是当前快照，不以历史条数代替健康；页面访问核验与feed健康各自独立。

| 来源 | 当前health_status | 最近HTTP | 新闻/相关评论条数 | 最近检查UTC | 最新源报告时间UTC |
|---|---|---|---|---|---|
| CoinDesk | NETWORK_ERROR | — | 0 / 0 | 2026-11-02T05:19:35.868Z | — |
| Cointelegraph | NOT_MODIFIED | 304 | 35 / 0 | 2026-11-02T05:24:55.292Z | 2026-11-02T03:55:50.000Z |
| Decrypt | HEALTHY | 200 | 41 / 0 | 2026-11-02T05:24:54.708Z | 2026-11-01T16:01:02.000Z |
| AP News | RESTRICTED | 403 | 0 / 0 | 2026-11-02T05:17:54.347Z | — |
| Reuters | RESTRICTED | — | 0 / 0 | 2026-11-02T05:17:45.856Z | — |
| The Wall Street Journal | HEALTHY | 200 | 75 / 0 | 2026-11-02T05:24:57.241Z | 2026-11-02T02:00:00.000Z |
| Bloomberg | NETWORK_ERROR | — | 0 / 0 | 2026-11-02T05:19:40.808Z | — |
| CNBC | HEALTHY | 200 | 47 / 0 | 2026-11-02T05:24:55.565Z | 2026-11-02T05:09:45.000Z |
| 华尔街见闻 | RESTRICTED | 200 | 0 / 0 | 2026-11-02T05:17:53.889Z | — |
| Bureau of Labor Statistics | RESTRICTED | 403 | 0 / 0 | 2026-11-02T05:17:56.231Z | — |
| Federal Reserve | NOT_MODIFIED | 304 | 20 / 0 | 2026-11-02T05:24:55.287Z | 2026-10-29T20:30:00.000Z |
| SEC | NOT_MODIFIED | 304 | 25 / 0 | 2026-11-02T05:24:57.184Z | 2026-10-30T19:30:00.000Z |
| U.S. Treasury | NOT_CONFIGURED | — | 0 / 0 | 2026-11-02T05:17:59.663Z | — |
| Hacker News | HEALTHY | — | 0 / 17 | 2026-11-02T05:22:17.348Z | 2026-11-02T03:10:20.000Z |
| Reddit | RESTRICTED | 403 | 0 / 0 | 2026-11-02T05:18:10.230Z | — |

- CoinDesk：官方说明仍使用现有RSS。DNS有解析结果，普通TLS连接未完成，连续观察仍ConnectTimeout/ConnectError。不能确定是解析、路由或源站原因，也不能据此判RSS废弃。
- Bloomberg：markets/economics同域频道及www公开候选均超时，DNS有结果、TLS未完成；未改DNS、代理、证书或使用镜像。
- Reuters旧入口当前仍超时，授权未满足；华尔街见闻公开页200但自动采集许可仍未核实。
- AP/BLS本轮仍403；Reddit说明页本机403且API本来就待审批/OAuth，未尝试未授权API。
- Treasury旧候选本轮ReadTimeout，历史404不能冒作当前结果；保持NOT_CONFIGURED。
- HTTP304被记录为NOT_MODIFIED成功检查，内容可同时STALE；已通过合成回归验证。近期最后成功、最新文章、当前连接、历史错误和授权状态分别显示。

## 8. 自动化测试、M1回归与原始数据保护

**134项测试全部通过、失败0，pytest退出码0**，含原有M1的27项和全部原M2回归。
新增质量回归含42新闻样本、12观点对象/引用/否定等样本及机构计数、同事故进展、异事故分离、核实边界、304/STALE、负延迟与回填隔离。
旧测试未删除或跳过；仅迁移版本断言按真实版本3更新。Mock均写临时库，真实网络数据另列，不能用测试通过代表来源接通。
`pip check`、编译与空白检查通过；M1真实终端再次成功连接REST/WS，短时验收未跨收盘不冒称写入收盘线。
当前行情库约 **1731条**；质量修复前 **1693条完整记录逐字段比对一致**。
原231篇新闻的来源/URL/首次发现及全部初始内容修订保留，54个评论ID及首次发现保留。
SQLite integrity_check=ok、foreign_key_check无错误。时间证据来自修复前备份或实际采集，不生成模拟新闻混入库。

## 9. 尚未解决与最终建议

- 工程与观测限制：尚无已知阻断核心流程的复现Bug；HN单HTTP请求级的重试/延迟明细尚未细化，当前为批次口径。尚未取得真实稳态延迟样本，也未做7×24验证。
- 来源限制：Bloomberg/CoinDesk网络、Reuters/Reddit授权、华尔街见闻许可、AP/BLS403、Treasury入口未配置；本轮不能突破。
- 样本不足：HN方向性0、单社区且有界树，不能给市场情绪分数或全球方向结论。
- 算法限制：规则对隐含、跨语言、复杂实体/金额角色与无署名转载仍可能漏判；同一事故的新金额指标可能需要人工关联，机构归属目录需维护。
- 核验限制：28条抽样只有16条标题对应，受限/标题不对应的12条仍无法独立核验；其他未抽查记录不被宣称已核实。权威公告也只确认明确主张，不能推断BTC价格反应。

**建议 CONDITIONAL PASS**：核心统计、误报案例、追溯与保守边界已修复，真实采集和21分钟多源运行成立；受限覆盖、情绪样本及实时延迟证据不足使其不适合无条件PASS。
测试数量增加不是通过依据，真实证据与正确限制才是依据。原始逐项文件均保存在备份目录，实际数据/日志不进入Git。

## 10. 本地复现

```bash
cd /Users/wangzihan/Desktop/btc-intelligence
.venv/bin/python -m pytest -q
.venv/bin/btc-intelligence news --source cnbc --source decrypt --source cointelegraph --source wsj --source fed --source sec
.venv/bin/btc-intelligence social
.venv/bin/btc-intelligence analyze
.venv/bin/btc-intelligence intel-run --seconds 1260
.venv/bin/btc-intelligence sources --json
.venv/bin/btc-intelligence events --hours 24 --json
.venv/bin/btc-intelligence intel-stats --hours 24 --json
.venv/bin/btc-intelligence brief --hours 24 --output data/brief-24h.md
.venv/bin/btc-intelligence status
```

`intel-run`部分来源失败返回2；Ctrl+C或SIGTERM安全停止。重算仅改派生分类/关联，不会替代网络事实核验。
本轮已停止M2验收进程，保留原M1进程，等待产品验收，不推进M2.5。
