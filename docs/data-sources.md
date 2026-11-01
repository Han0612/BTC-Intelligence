# V1 数据来源与访问条件

核对日期：2026-11-01。**M1 仅实现 Binance 现货行情**，以下 M2/M3 条目是计划，不代表已完成采集或已获访问许可。
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

## 新闻（M2 必须实现）

| 来源 | 获取方式 | 访问条件 |
|---|---|---|
| CoinDesk | 官方 RSS `https://www.coindesk.com/arc/outboundfeeds/rss/`；[官方订阅说明](https://www.coindesk.com/coindesk-news/2021/09/17/coindesk-rss) | 优先采集标题、RSS 摘要、链接、发布时间；M2 验证本机连通性与供稿条款，遵守缓存和轮询限制，不默认抓全文或转发全文。 |
| Cointelegraph（候选） | 官方站点 RSS `https://cointelegraph.com/rss` | M2 核验 feed、域名变化及授权条件；若不可用，报告并换合法来源。 |

M2 需做 BTC 相关性筛选、GUID/链接规范化去重、发布时间解析与来源追溯。Scrapling 仅用于条款和 robots 允许的适合公开网页，
不抓登录内容、不绕付费墙或风控验证；本阶段不安装或调用。

## 社交评论与情绪（M2 必须实现）

| 来源 | 计划获取内容 | 访问条件 |
|---|---|---|
| Bluesky（优先验证） | BTC/Bitcoin 相关真实公开帖子、回复；使用公开 AppView API，例如 `app.bsky.feed.searchPosts` 与 thread 接口 | [官方 API 目录](https://bsky.network/docs/api-directory/)、[限流说明](https://bsky.network/docs/rate-limits/)。优先 `public.api.bsky.app`；具体 endpoint 是否公开、搜索覆盖与回复可用性须 M2 实测；不宣称全量覆盖。 |
| Reddit（条件来源） | r/Bitcoin、r/CryptoCurrency 相关帖子及评论 | [官方访问说明](https://support.reddithelp.com/hc/en-us/articles/14945211791892-Developer-Platform-Accessing-Reddit-Data)、[Data API 条款](https://redditinc.com/policies/data-api-terms)。外部 Data API 须申请批准并满足 OAuth 等要求；未经批准不采集，不把网页可见性当 API 授权。 |
| X（条件候选） | BTC 相关帖子及回复 | 仅在有官方 API 合法授权且确认可用额度/费用时接入，M1 未核验权限、未采集。无权限时不以网页爬取绕过。 |

M2 至少接入一个实际可访问、合法许可的真实社交来源。没有可用源时须明确报告 M2 未完成，不能用新闻情绪或合成评论替代。
保留帖子 URI/ID、原始链接、作者公开标识（最小化存储）、创建时间、采集时间、语言、是否回复及情绪模型版本/置信度，支持去重和删除同步。
情绪分数与真实原文分别保留，不把模型推断当事实。

## 合约数据（M3）

计划使用 [Binance USDⓈ-M 官方市场数据接口](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)：
OI、历史 OI、资金费率、多空账户/持仓比例。只使用公开市场数据，接入前核验具体 endpoint、历史窗口、统计口径、限流与地区条件。
本机尚未验证合约接口；现货专用域名可用不意味着合约接口可用。禁止用现货量推算结果冒充真实 OI。
