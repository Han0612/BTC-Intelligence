# BTC Intelligence

个人使用的 BTC 数据与研究系统。已实现 **M1 真实现货行情**及 **M2 全球新闻、宏观事件与真实社区评论情报**。
M2 的工程与真实接入证据、受限来源、样本偏差见 [M2 验收记录](docs/m2-acceptance.md)。
不连接交易账户，不需要交易 API Key，不自动交易。当前停止在 M2，尚未实现 M2.5、M3、M4。

## 本地启动

需要 Python 3.11+。本机已在项目 `.venv` 内用 Python 3.15.0 验证，未修改全局环境。
所有命令在项目根目录执行；终端关闭、电脑休眠或关机都会中断采集。

```bash
cd /Users/wangzihan/Desktop/btc-intelligence
python3 -m venv .venv                 # 仅首次安装；已有 .venv 可跳过
.venv/bin/python -m pip install -r requirements.lock -e .
cp .env.example .env                 # 可选；已有 .env 时不要覆盖
.venv/bin/btc-intelligence backfill   # 初始化，默认最近 500 根已收盘 1m K 线
.venv/bin/btc-intelligence run        # 持续运行，Ctrl+C 安全停止
```

程序使用默认配置即可工作，无需创建 `.env`。环境变量优先于 `.env`，`.env` 优先于默认值；
支持简单 `KEY=value` 和独占一行的 `#` 注释，不执行 shell、不展开变量。
可在 `.env.example` 查看路径、超时、历史范围、同步间隔与日志级别。
M1 固定 Binance / BTCUSDT / 1m，不开放交易接口配置。

## 验证和查看

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
.venv/bin/btc-intelligence run --seconds 135
.venv/bin/btc-intelligence status
.venv/bin/btc-intelligence status --json
tail -f logs/collector.log
sqlite3 data/btc.sqlite3 'SELECT COUNT(*) FROM candles;'
sqlite3 -header -column data/btc.sqlite3 "SELECT symbol, interval, datetime(open_time_ms/1000,'unixepoch') AS open_utc, close, source_type FROM candles ORDER BY open_time_ms DESC LIMIT 5;"
```

限时运行建议至少 75 秒以跨越一次分钟收盘；135 秒可观察两个收盘。
`run` 输出本次 REST、WebSocket 消息及实际新增行统计；若未同时完成 REST 同步与接收合法 WebSocket 消息，返回非零。
限时运行收到推送并不必然收到收盘消息，应同时检查 `ws_closed_messages`、`ws_rows_inserted` 与数据库。
`status` 是只读操作，显示条数、缺失分钟数、来源和距最新收盘的秒数；读取成功不代表行情仍在更新。
数据文件默认在 `data/btc.sqlite3`，日志按 UTC 输出，单文件 5 MB、保留 3 份备份。

## 数据正确性与恢复

- 使用 Binance 官方公开行情专用 REST / WebSocket（见[数据来源](docs/data-sources.md)），免认证。
  默认不读取系统代理、不自动切换入口；TLS 验证保持开启。
- REST 先查询交易所服务器时间，以服务器当前分钟之前的已收盘 K 线为边界，分页初始化（每页最多 1000 条）。
  REST 不提供单独的事件推送时间，因此 `event_time_ms` 记录收盘时间，`event_time_kind=candle_close`。
- WebSocket 仅在 `k.x=true` 时落库；`event_time_ms` 取交易所 `E`，`event_time_kind=exchange_event`。
  未收盘推送仅用于确认连接状态，不写入行情表。
- 每条记录保留 `source_type`、`source_url`、原始响应 `raw_payload`、事件时间、开收盘时间及 `collected_at_ms`。
  所有时间均为 UTC Unix 毫秒；命令行时间为 ISO 8601 UTC（`Z`）。价格和成交量存十进制文本，避免浮点舍入。
  采集时间来自本机时钟，可能与交易所事件时间有轻微偏差；不人为修改时间戳，REST 收盘判断使用交易所时间。
- 主键为 `(exchange, symbol, interval, open_time_ms)`，重复记录忽略，保留首次成功入库的来源。
  因此 REST 与 WebSocket 同时返回一根 K 线时不会重复计数。
- REST 与 WebSocket 并行；启动即补数，此后默认每 60 秒从库内首个缺失分钟向前补齐。
  重启后会补齐停机期间缺口。REST 返回空数据、乱序或缺口时记错误，不把缺失当成功。
- WebSocket 自动处理 ping/pong；握手超时、30 秒无行情推送、连接关闭（包括交易所 24 小时连接到期）均触发指数退避重连。
  重连间隔含少量抖动，上限默认 60 秒。REST 每次最多重试 3 次，长期运行的同步任务会继续退避重试。
- HTTP 429 遵守 `Retry-After`；401/403/418/451 视为拒绝访问，停止采集并报告，不自动改域名或绕过限制。
- SQLite 使用 WAL、每批事务提交，支持独立终端只读查看。Ctrl+C / SIGTERM 会取消任务、关闭连接并保留已提交数据。

真实数据与测试隔离：测试文件均标注为合成样本，只写入 pytest 临时目录；本地协议测试使用回环地址。
测试不会向实际行情数据库写入样本；真实验收通过公开生产接口另行完成。

## 项目结构

```text
btc-intelligence/
├── .env.example / .gitignore
├── pyproject.toml / requirements.lock
├── README.md
├── src/btc_intelligence/
│   ├── __init__.py / __main__.py
│   ├── cli.py / config.py / logging_setup.py
│   ├── models.py / database.py / service.py
│   ├── collectors/__init__.py / collectors/binance.py
│   └── intelligence/（M2 适配器、存储、分类、统计、简报与 CLI）
├── config/sources.toml（M2 来源及独立轮询间隔）
├── tests/
│   ├── conftest.py
│   ├── test_models_database.py
│   ├── test_rest_service.py
│   └── test_m2_*.py（新闻、分析、迁移、评论、统计与调度）
├── docs/data-sources.md / docs/m1-acceptance.md
├── docs/m2-acceptance.md
├── data/.gitkeep / data/btc.sqlite3（本机数据，Git 忽略）
└── logs/.gitkeep / logs/collector.log（Git 忽略）
```

`.venv`、数据库（含 WAL/SHM）、日志、缓存、`.env` 均被 Git 忽略。
`requirements.lock` 固定本次验收的运行和测试依赖；`pyproject.toml` 声明兼容范围。
采集器、模型、存储和服务分离，为后续 FastAPI、Dashboard 和 Docker 保留边界，本阶段不引入它们。

## 里程碑与当前边界

实际验收证据见 [M1 验收记录](docs/m1-acceptance.md)。本次验证是短时真实采集与重启验证，尚未完成连续 24 小时稳定性验收。
电脑需要保持联网和唤醒；M1 提供前台常驻命令，未安装开机服务或云端部署。

后续路线（须逐次验收）：

1. **M2 核心工程已验收**（`m2-accepted-2026-11-05`）。已交付新闻 RSS、社区评论采集、去重和规则情绪分析。全球新闻覆盖、社区情绪有效样本及长期稳定性仍有限，详见 [M2 质量复验](docs/m2-quality-review.md)。
2. M3：OI、资金费率、多空比例、技术指标及市场结构。
3. M4：多因子研判、证据与风险边界、历史记录和模拟验证；仍不自动交易。

## M2 运行与查询

更新依赖仍只在当前虚拟环境执行：`.venv/bin/python -m pip install -r requirements.lock -e .`。
M1 的 `run` 继续仅负责行情；M2 的 `intel-run` 单独负责情报，可在不同终端运行。

```bash
# 全部已启用新闻来源单次采集；部分来源失败时返回 2，其他来源仍继续入库。
.venv/bin/btc-intelligence news
# 只采集已验证可用的来源（--source 可重复）。
.venv/bin/btc-intelligence news --source wsj --source cnbc --source decrypt --source cointelegraph --source fed --source sec
.venv/bin/btc-intelligence social
# 持续运行，Ctrl+C / SIGTERM 安全停止；验收也可加 --seconds 100。
.venv/bin/btc-intelligence intel-run
.venv/bin/btc-intelligence sources
.venv/bin/btc-intelligence events --hours 24 --json
.venv/bin/btc-intelligence news-latest --hours 24 --limit 10
.venv/bin/btc-intelligence comments --hours 168 --limit 5
.venv/bin/btc-intelligence intel-stats --hours 24 --json
.venv/bin/btc-intelligence brief --hours 24 --output data/brief-24h.md
.venv/bin/btc-intelligence brief --hours 168 --output data/brief-7d.md
.venv/bin/btc-intelligence evaluate --json --output data/evaluation.json
.venv/bin/btc-intelligence analyze  # 可选：本地规则重算，不改原文和采集时间
.venv/bin/python -m pytest -q
```

`sources/events/news-latest/comments/brief/evaluate` 支持 `--json`；窗口支持 1、24、168 小时，范围 1～720 小时。
真实采集命令无 Mock 模式；合成样本仅用于测试与 `evaluate`。返回码 0 表示所选来源本轮完成，2 表示来源受限、失败或部分采集；
正常停止不代表覆盖完整，须结合来源健康、队列和报告理解。查询类命令读取成功返回 0。
不要用 `--source reddit` 或编辑配置启用受限平台来代替平台授权。

## M2 结构与配置

`config/sources.toml` 管理来源、官方 feed、是否启用、轮询秒数与内容陈旧阈值；生产间隔不低于 120 秒，新闻默认 300 秒，Fed/SEC 600 秒。
`.env.example` 提供请求超时、有限重试、并发（默认 4）、HN 每批主题/条目上限、30 天回看与情绪最低样本量（默认 20）。
系统不执行 `.env` 内容，未使用付费模型服务；Reddit 凭证名称仅预留，当前适配器始终标记待授权，不会读取或发送这些凭证。

新增轻量纯 Python 依赖仅 `defusedxml`，已在 Python 3.15 中实际验证。
M2 模块位于 `src/btc_intelligence/intelligence/`：

- `config.py`、`safety.py`、`transport.py`：来源配置、HTML 清理、URL 白名单、响应上限、超时与有限重试。
- `rss.py`、`social.py`：RSS/Atom、HN 官方 API；Algolia 独立索引仅辅助发现 ID。Reddit 为禁用的授权边界占位适配器。
- `storage.py`：SQLite 追加迁移、报道修订、事件关联、帖子与评论、规则结果、健康状态和持久化扫描队列。
- `analysis.py`、`evaluation.py`：新闻与评论分离的规则分析、版本号、人工自测及误判披露。
- `service.py`、`queries.py`、`report.py`、`cli.py`：来源独立调度、窗口统计、告警候选、中文简报和命令行。

迁移版本为 3，可重复执行；M1 的 `candles` 表保持原样，M1 打开数据库不会把版本 3 降回 1。
表包括 `news_articles`、`article_revisions`、`news_events`、`news_event_links`、`social_threads`、`social_comments`、
`sentiment_results`、`source_health`、`collection_runs`、`source_state`、`schema_migrations`。关键时间与来源窗口建有索引。
`data/m1-before-m2-*.sqlite3` 为本次在线备份；`data/m1-baseline.json` 为 M1 基线记录摘要，均被 Git 忽略。

## M2 的数据与分析含义

- 新闻保存来源 ID、原始 ID、标题、RSS 摘要、链接、语言、原始发布时间及原始日期字符串、首次发现与最近采集时间、内容哈希和分析版本。
  `body` 当前均为空：只获取 RSS 合法公开层级，不访问订阅正文。未提供可靠时区或日期异常时将发布时间标为空并标注原因。
- 同来源通过原始 ID 或规范化 URL 去重，首次发现时间保持不变；更新保存内容修订。ETag/Last-Modified 支持增量请求。
- 跨媒体保守聚合共同实词/相似标题，或具有同交易所、同事故及同明确金额的安全事件；保留每家原始报道。
  公开署名、相同标题和相同内容用于转载去重；“独立来源候选”不是独立核实。跨语言改写及无署名转载仍可能漏判。
- 新闻的 DIRECT/INDIRECT/IRRELEVANT/UNKNOWN、事件类别和 Critical/High/Medium/Low 表示监控优先级，不是 BTC 涨跌预测。
  媒体报道、未核实信息与官方源公告分别记录；官方源身份也不等于所有潜在影响已经证实。
- HN 通过独立 Algolia 搜索发现帖子/评论 ID，再从官方 API 获取主题与真实评论。支持嵌套回复、持久化队列、增量扫描和评论去重。
  仅将 BTC 投资/市场语境评论纳入统计；排除技术悬赏、家电与密码学等已识别的非投资主题。正文作为不可信纯文本保存，不执行其中的命令。
  已知评论被删除/隐藏后，下一次有界复查会清除正文及作者并移除情绪结果；不承诺全量即时同步。
- 评论规则版本 `m2-quality-2.0` 支持中英明确多空/中性表述，技术赞美不算看多，否定、反讽、历史立场、条件或复杂语义优先 UNKNOWN。
  强度为规则强度，不是经校准的概率。语言字段为简易识别，混合语种及其他语言不保证正确。
- 各平台按原始评论时间分别统计。分数为 `(Bullish-Bearish)/(Bullish+Bearish+Neutral)`，Unknown 不参与；参与样本不足 20 时不输出分数。
  HN 不能代表整体 BTC 投资者；不会平均为“全球市场情绪”。
- 新闻热度与社交热度分开。历史比较要求覆盖两个连续窗口并有真实轮询记录；首轮历史回填不能当成骤增。
  新闻类别密度至少前期 5 条/当前 10 条且翻倍；讨论量两窗口至少各 20 条且翻倍；情绪占比变化至少 25 个百分点且满足方向样本阈值。
  多源短时报道也仅是待核实候选。无基线显示“样本不足”，来源故障显示“不完整”，未抓到新闻不等于没有事件。
- HTTP 429 持久化冷却时间；401/403/418/451 仅暂停该来源至少一天，不绕过限制。单来源异常不会阻止其他源，已提交数据保留。
  RSS 故障、请求耗时、发布至首次发现延迟、队列剩余量和最后成功时间可查询。历史回填延迟不能当作稳定实时延迟。
- 报告区分事实报道、假设路径和“市场反应未测量”。预留事件发现时间和 `market_reaction_status=NOT_MEASURED`，供后续与 M1 行情对齐；M2 未做因果判断或跨市场行情分析。
- 实际 HTTP 请求只允许审查过的 HTTPS 来源域名，不跟随重定向，不下载文章中 URL/图片；拒绝本地 URL、凭据 URL、实体 XML，清理控制字符并转义报告 Markdown。

完整访问条件、P0 调查、授权缺口与 M2.5 候选见 [数据来源](docs/data-sources.md)。


## 2026-11-02 M2 质量复核

本轮结论与真实21分钟观察结果见 [质量复核报告](docs/m2-quality-review.md)。
旧 M2 验收文档中的数量与延迟属于历史快照，不代表当前来源健康。

- 新闻采用六类内容层级（加密直接、重大宏观、重大地缘、普通财经政治、不相关、信息不足），再判定 BTC 关联与重要性。只有存在明确市场传导条件才生成 INDIRECT 路径，普通福利/选举/企业 AI 新闻不生成泛化解释。优先级不是价格预测。
- 事件分别提供 `article_count`、`source_count`、`independent_publisher_count`、`event_count` 与 `corroboration_status`。`publisher_id` 按发布机构配置，同机构频道应复用；通讯社署名归并。发布机构数不等于独立事实证据，转载/重复文本还另存候选证据组计数。
- 简报按发布机构选择代表报道，同时列出全部机构标签与总文章数，不再只截取同一家前三篇。`events --json` 保留全部原始证据。
- 核实状态包括 REPORTED/CORROBORATED/OFFICIALLY_CONFIRMED/DISPUTED/UNVERIFIED。后四种需要有明确主张和证据的审核记录；媒体数量不会自动升级。官方确认仅限报告列出的已核实主张，不扩展到后续净流出或价格反应。
- 新闻查询 JSON 的 `collection_status` 和 `page_validation` 分开标记“采到 RSS”“原文可访问”“媒体页面标题对应”；事件事实核实另计。抽样核验只读取公开页面元数据，同媒体正常重定向允许，付费/403/验证码不绕过。
- 来源健康另给 `health_status`，区分 HEALTHY、NOT_MODIFIED、STALE、NETWORK_ERROR、HTTP_ERROR、RESTRICTED、NOT_CONFIGURED、DISABLED；旧 `status` 字段为兼容保留。HTTP 304 是成功检查，内容仍可能陈旧。最近检查、最近成功、最新发布时间、历史错误和授权状态分别展示。
- 每次检查的 HTTP 状态、运行模式、重复数、回填数和新增监控数写入 `collection_runs`。新增文章存 `source_checked_at_ms`、`discovery_kind`、`discovery_delay_ms`、`delay_quality`。初始回填、人工发现、恢复回填、源站迟到及旧记录未知模式不混入稳态延迟；负延迟标异常。源站自身延迟不能只凭 RSS 分离。
- 评论漏斗区分累计保存、时间窗内、BTC 市场相关、明确多空与可评分，另列窗口外相关和不相关数；查询发现与子树扫描是有界采样，不代表整棵讨论树。新批次保存扫描/过滤/去重计数。
- 中性仍可参与分数分母，但只有明确 BULLISH+BEARISH 数达到最低门槛才输出分数；Unknown 不转 Neutral。方向不足时明确“暂无可信情绪信号”。技术、行业、交易所风险和转述他人观点不移作 BTC 价格方向。
- 原始新闻/评论不清空，修订保留。派生事件重分组前保存 `event_link_history`，旧事件标不活跃；相同成员集合重算复用 ID。`article_validations` 保存页面检查，`event_reviews` 保存有范围的一手证据审核。

命令保持兼容：

```bash
.venv/bin/btc-intelligence analyze
.venv/bin/btc-intelligence intel-run --seconds 1260
.venv/bin/btc-intelligence sources --json
.venv/bin/btc-intelligence events --hours 24 --json
.venv/bin/btc-intelligence intel-stats --hours 24 --json
.venv/bin/btc-intelligence brief --hours 24 --output data/brief-24h.md
```

`analyze` 重算派生分类与事件关联，保留原文和首次发现时间；它不做网络核验。21分钟观察不能代表7×24稳定性。
