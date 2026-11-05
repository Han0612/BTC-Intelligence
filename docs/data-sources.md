# V1 数据来源与访问条件

核对日期：2026-11-02。最新复核与限界见 [质量复核报告](m2-quality-review.md)。原 M2 表中条数为历史记录，不能据此判定当前健康。M1 现货行情和 M2 情报已实际验证，逐源结果见下表与 [M2 验收](m2-acceptance.md)。
所有来源后续均须记录原始来源标识/URL、事件时间与 UTC 采集时间。缺失的发布时间不得用采集时间伪装。

## 行情（M1）

| 来源 | 用途及官方入口 | 访问条件与当前状态 |
|---|---|---|
| Binance 现货公开行情专用接口 | REST `https://data-api.binance.vision/api/v3/time`、`/api/v3/klines?symbol=BTCUSDT&interval=1m`；WS `wss://data-stream.binance.vision:443/ws/btcusdt@kline_1m` | 官方免密钥生产行情入口，本机 REST HTTP 200、WS 推送均已实际验证；不使用账户接口。遵守访问地区和频率限制。 |
| Binance 标准入口 | `https://api.binance.com`、`wss://stream.binance.com:443` | 本次 REST 连接超时（curl 28 / HTTP 000），WS 握手超时；未收到地域拒绝响应，无法仅凭超时判断原因。程序不自动切换入口。 |
| Kraken（备选，未实现） | [REST OHLC 文档](https://docs.kraken.com/api-reference/market-data/get-ohlc-data)、[WS OHLC 文档](https://docs-legacy.kraken.com/api/docs/websocket-v1/ohlc/) | 官方公共行情；REST 最后一根为未完成 K 线，须过滤；通常使用 XBT/USD（WS 标识需按官方版本核对），不能冒充 BTCUSDT。本机 REST 探测超时，不能宣称可用。 |
| Coinbase Exchange（备选，未实现） | [REST candles 文档](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-candles)、[WS 说明](https://help.coinbase.com/en/developer-platform/websocket-feeds/exchange) | 公共行情候选；常用 BTC-USD、REST granularity=60；WS 逐笔行情需自行聚合分钟线。须重新验证本机连通性、权限与限流，不能直接视为可用替代。 |

依据：[Binance 官方 Market Data Only](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md)、
[官方 WebSocket 协议](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md)、
[官方 REST 文档](https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md)。
REST 每页最多 1000 根；WS 使用 UTC 流，仅落库已收盘 K 线。遇访问限制须停止并记录原因，不用代理绕行。

## M2 全球新闻：实际访问与覆盖层级

| 来源 | 获取方式与本机结果 | 访问范围与缺口 |
|---|---|---|
| **Bloomberg P0** | 自有域名候选 `https://feeds.bloomberg.com/markets/news.rss`；本机 ConnectTimeout，两轮有限请求均未得到 XML | **未接通**；没有使用第三方镜像，没有访问订阅正文。需要进一步核验当前官方 feed/授权产品，不能宣称其全部资讯已覆盖。 |
| **WSJ P0** | Dow Jones 自有托管 `https://feeds.content.dowjones.io/public/rss/RSSWorldNews`；HTTP 200，后续 HTTP 304/200，真实入库 | 只读该公开世界新闻 feed 的标题、摘要、链接与日期，**未获取付费正文**；非 WSJ 全站/独家快讯授权。旧 RSS 导航页返回 404，直接以实际官方托管 feed 为准。 |
| **Reuters P0** | 旧公开入口 `https://www.reuters.com/tools/rss` 本机超时；[Reuters Connect 官方说明](https://reutersagency.com/content-delivery-platforms/reuters-connect/)提供授权内容/API 路径 | **未接通**，待商业/用途授权；未找到已核实的现行免费官方全球新闻 RSS，不使用第三方 Reuters 镜像。 |
| **华尔街见闻 P0** | `https://wallstreetcn.com/live` 本机 HTTP 200；仅用于可用性调查，没有采集快讯正文 | **未接通**：未核实自动获取许可与公开官方接口。可见页面不等于 API 授权；禁用适配，列为许可核验后的 M2.5 候选。 |
| **CNBC P1** | `https://www.cnbc.com/id/100003114/device/rss/rss.html`；HTTP 200，真实入库 | 官方公开 RSS 标题/摘要；非完整新闻线，不抓订阅正文。 |
| **AP News P1** | `https://apnews.com/hub/world-news` 本机 HTTP 403 | **未接通**；不绕过拦截。授权服务须另行申请，不用非官方镜像补数。 |
| CoinDesk | `https://www.coindesk.com/arc/outboundfeeds/rss/` 本机超时；[官方 RSS 说明](https://www.coindesk.com/coindesk-news/2021/09/17/coindesk-rss) | **未接通**；RSS 适配器支持该源，但编写了适配器不等于成功采集。 |
| Decrypt | `https://decrypt.co/feed`；HTTP 200，真实入库 | 官方公开 feed；仅标题与 RSS description 摘要，不读正文 content:encoded。 |
| Cointelegraph | `https://cointelegraph.com/rss`；HTTP 200，真实入库 | 官方公开 RSS 标题/摘要/时间/链接；不扩展到站内付费内容。 |
| Federal Reserve | `https://www.federalreserve.gov/feeds/press_all.xml`；HTTP 200/304，真实入库；[官方 feed 目录](https://www.federalreserve.gov/feeds/feeds.htm) | 官方一手公告，包含 FOMC 声明；本阶段仍只读取 feed 摘要。身份为官方不等于已经验证 BTC 影响。 |
| SEC | `https://www.sec.gov/news/pressreleases.rss`；HTTP 200/304，真实入库 | 官方公开监管公告；未访问 EDGAR 批量接口或账户信息。 |
| BLS | 官方 RSS 候选 `https://www.bls.gov/feed/news_release/rss.xml` 本机 HTTP 403；[官方 feed 目录](https://www.bls.gov/feed/) | **未接通**；不绕行 403。当前 CPI/非农依赖已接入媒体的选题，缺少 BLS 直接核实链路。 |
| U.S. Treasury | 候选旧 RSS `https://home.treasury.gov/system/files/136/treasury-rss.xml` HTTP 404；[TreasuryDirect 官方 RSS 目录](https://www.treasurydirect.gov/rss/)另有国债发布渠道 | **未接通**当前财政部新闻；TreasuryDirect 有价证券发布不等于财政部全球政策新闻，本阶段未将它冒作同一来源。 |

来源均为发布方或其自有托管域名，不使用未经核实的第三方 RSS 镜像。RSS 的可访问性不授予全文转发/商业再分发权限；
仅作本地个人 feed 阅读、标题与必要摘要分析，保留原始链接。后续扩大用途须另核条款。
`config/sources.toml` 记录具体入口、受限原因及独立轮询频率（通常 300 秒，官方低频公告 600 秒）。
Bloomberg/CoinDesk 故障只影响本源；受限源保持禁用，手动指定会明确返回待授权状态。

## M2 真实社区评论

| 来源 | 实际状态/方法 | 访问条件与代表性 |
|---|---|---|
| Hacker News | **已接通** [官方 API](https://github.com/HackerNews/API) `https://hacker-news.firebaseio.com/v0/item/{id}.json`；真实帖子及嵌套评论入库 | 不需要凭证；每条评论保留主题、parent、原文链接、官方 API URL、发布时间与发现/采集时间；必要公开作者 ID，不采用户资料。技术悬赏/家电等非投资主题排除。HN 偏技术人群，不代表 BTC 投资者整体。 |
| Algolia HN Search | **已验证的独立发现服务** `https://hn.algolia.com/api/v1/search_by_date`；[服务说明](https://hn.algolia.com/about)、[API 入口](https://hn.algolia.com/api) | 查询帖子和评论，仅用 ID 辅助发现；不能称其为 HN 官方关键词 API。正文和主题关联均回官方 API 核验，评论搜索的 story_id 还沿官方 parent 链验证。索引延迟、分页/批次数量会限制覆盖。 |
| Reddit | **未接通/待授权**，重点社区 r/Bitcoin、r/CryptoCurrency | [官方访问说明](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data)、[官方 FAQ](https://developers.reddit.com/docs/guides/faq)、[Data API 条款](https://redditinc.com/policies/data-api-terms)。外部 API 须平台审批、用途许可及 OAuth；费用视批准范围，不假设免费，不自动申请。 |
| Bluesky | 本阶段未实现、未作成功接入声明 | [官方 API 目录](https://bsky.network/docs/api-directory/)、[限流说明](https://bsky.network/docs/rate-limits/)可供未来核验；不为凑平台数量而导入非投资样本。 |
| X | 本阶段未实现、未获 API 授权 | 须确认官方 API 授权与费用后再讨论接入；不爬网页绕过权限。 |

Reddit 适配器是禁用的授权占位，**没有伪装成成功调用**。`.env.example` 只预留 `BTC_REDDIT_CLIENT_ID` / `BTC_REDDIT_CLIENT_SECRET` 名称；
当前不读取或发送。将来在平台明确批准后再实现 token 流程，凭证只放被 Git 忽略的本地环境，禁止写日志。
仅有凭证不能替代审批；没有 Reddit 样本意味着无法覆盖其投资/交易社群，不能用 HN 或媒体意见补作 Reddit 情绪。

## 增量、时间与限制

新闻无 BTC 关键词也可入库并识别 INDIRECT。新闻存三种时间，源时间缺失/异常标为空，绝不拿采集时间冒充。
RSS ETag/Last-Modified 与唯一键用于增量去重，修订另存；事件聚合保留每篇证据。
HN 每轮有界扫描（默认每次搜索最多 20 个发现结果、120 个评论条目，另有限制的主题复查），保存队列，重复刷新不重建评论 ID。
内容陈旧、采集失败、队列剩余与样本不足分别披露。首轮回填不代表近实时发现；5–10 分钟轮询也不能保证所有事件及时到达。

## M2.5 候选（尚未开发）

M2 **未安装、未集成 Scrapling**。未来仅在公开许可、robots 和正常可访问条件满足后评估：

1. 华尔街见闻公开快讯：独有价值是中文宏观与亚洲交易时段覆盖；须先明确自动获取及本地分析许可，优先官方授权接口。
2. 美国财政部公开政策公告：可补充制裁、财政与国债政策的一手事实；先查当前官方 RSS/API，确无适当结构化入口再考虑允许的公开 HTML。
3. BLS 官方公开发布页：补充 CPI/就业公告的事实和发布时间；仅在网络能正常访问且许可明确时考虑，**不使用 Scrapling 绕过本次 403**。

Bloomberg/WSJ/Reuters 的付费正文和身份验证页面不列为绕行目标。上述候选不意味着已获得自动抓取许可。

## 合约数据（M3）

计划使用 [Binance USDⓈ-M 官方市场数据接口](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)：
OI、历史 OI、资金费率、多空账户/持仓比例。只使用公开市场数据，接入前核验具体 endpoint、历史窗口、统计口径、限流与地区条件。
本机尚未验证合约接口；现货专用域名可用不意味着合约接口可用。禁止用现货量推算结果冒充真实 OI。


## 2026-11-02 重新检查（覆盖旧探测结论）

- 正常 RSS/API 已在本轮连续观察重新请求：CNBC、Decrypt、Cointelegraph、WSJ 官方托管 RSS、美联储、SEC 及 HN；逐源轮询次数和 HTTP 200/304 见质量报告。WSJ RSS 可用与其原文网站可访问是两件事。
- CoinDesk：官方说明仍指向 `https://www.coindesk.com/arc/outboundfeeds/rss/`，没有把超时误判为地址废弃。系统 DNS 能返回结果，但正常 TLS 连接未完成，实际 RSS ConnectTimeout/ConnectError；未修改 DNS、代理或证书校验。
- Bloomberg：`feeds.bloomberg.com/markets/news.rss`、同域 economics 频道及 `www.bloomberg.com/feeds/news.rss` 公开候选均超时，DNS 有结果、TLS 未能建立；不能确定是解析、路由还是源站问题，不能声称成功或已废弃。未用镜像替代。
- Reuters：旧公开 RSS 入口本轮仍连接超时，Reuters Connect 的授权条件仍未满足，没有请求未经授权 API。
- 华尔街见闻：2026-11-02 公开 live 页 HTTP 200，但自动获取许可未核实，继续 RESTRICTED，不导入页面正文。
- AP、BLS：本轮均 HTTP 403，停止于该限制；Reddit 访问说明页本机也返回 403，API 仍因未获用途审批和 OAuth 而未接通。
- Treasury：候选旧 RSS 历史曾返回404，本轮读取超时；没有确定的现行新闻入口，状态 NOT_CONFIGURED，不能继续沿用“当前404”的旧结论。
- 本轮抽样原始新闻页面：Fed/CNBC/Decrypt 多个页面 HTTP 200 且标题对应；SEC 页面403，WSJ 原文网站超时；Cointelegraph 部分标题不能对应。逐条原始链接与结论见质量报告，不据此给受限内容贴虚假标签。

一手证据仅作为本次事实核验，不作为新增采集平台：
[FBI 2026-10-31 Binance 攻击公告](https://www.fbi.gov/investigate/cyber/alerts/2026/north-korea-responsible-for-6-billion-binance-attack)、
[Fed 2026-10-28 FOMC 声明](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm)。
FBI 公告确认范围不能被扩大为对所有后续净流出金额、恢复比例或 BTC 市场影响的确认。
