# M2 最终质量验收更新（2026-11-02）

最终建议：**CONDITIONAL PASS**。本轮134项测试通过，完成28条原始链接抽查与21分钟真实连续观察。
现有243篇RSS新闻记录、54条原始评论（17条相关；24小时7条均UNKNOWN），没有可信方向性情绪信号。
统计/展示、宏观误报、核实边界、健康状态、回填与监控延迟已修复；来源限制、样本和时效证据仍不完整。
完整最新证据、逐源状态、原始备份与验收依据见 [质量复核报告](m2-quality-review.md)。

以下保留2026-11-01的初次M2验收历史快照，不代表当前条数、健康状态或最新规则版本。

---

# M2 本地验收记录

验收快照：**2026-11-01T10:29:57.330Z**（北京时间 2026-11-01 18:29:57）。
工作目录：`/Users/wangzihan/Desktop/btc-intelligence`。

## 1. 结论与完成范围

**M2-A～M2-F 的本地功能与最低真实数据链路已通过；整体情报产品覆盖按“部分达成”报告。**
已满足至少一个加密媒体、一个独立全球/宏观媒体、一个官方机构以及真实社区评论的最低接入要求。
Bloomberg、Reuters、华尔街见闻及 Reddit 等仍未接通；持续历史基线和方向性评论样本不足，不能宣称全球实时覆盖或形成可靠市场情绪结论。

| 阶段 | 结果 |
|---|---|
| M2-A 新闻底座 | 完成：RSS/Atom、标准化、三类时间、来源级去重、修订记录、健康状态、独立频率与增量请求。 |
| M2-B 重大事件 | 完成初始规则：宏观/央行/地缘/能源/贸易/金融风险及加密事件，DIRECT/INDIRECT/IRRELEVANT/UNKNOWN，解释路径及核实状态。 |
| M2-C 大型媒体 | P0 均逐一调查与本机验证；WSJ 公开官方托管 RSS 实际接通，其余缺口如实记录。未访问付费正文。 |
| M2-D 真实评论 | HN 官方 API 实际接通；Algolia 只辅助发现，官方正文和 parent 链验证；持久化队列、去重、相关性排除及删除复查。Reddit 仅待授权占位。 |
| M2-E 情绪与热度 | 四分类、分平台/分时间窗口、样本阈值、版本、新闻热度、社区热度、历史覆盖判断与候选异常。现有方向样本及历史不足。 |
| M2-F 简报与验收 | CLI 中文六部分简报、真实网络核验、75 项测试、M1 回归、依赖检查和数据保护检查完成。 |

未集成 Scrapling，未部署云端，未做前端、自动交易或完整 M3/M4。

## 2. 环境、Git 与数据保护

- macOS 26.6.2 / arm64；继续使用项目 `.venv` / Python 3.15.0，未修改全局 Python。
- 新增唯一运行依赖为纯 Python `defusedxml 0.7.1`；项目版本 0.2.0。`pip check` 及编译检查通过，实际依赖固定在 `requirements.lock`。
- 开始时 Git 尚无提交，文件均为现有 M1 内容；核对后创建 M1 基线 **`a431a15`**。M2 更改保留在工作区供审阅，未推送远端。
- 通过 SQLite backup API 创建 `data/m1-before-m2-20261101T095905Z.sqlite3`，当时已有 **555 条** M1 记录；先前 505 条是 M1 初次验收快照，不能当作当前数据量。
- 迁移采用追加表/索引，版本 2，可重复执行；不重建或清空 `candles`。基线 555 条完整记录 SHA-256 复核一致，未变更任何字段。
- 当前 M1 状态快照：**585 条**，记录区间缺失 **0** 分钟，最新收盘 `2026-11-01T10:28:59.999Z`。
- SQLite `integrity_check=ok`，`foreign_key_check` 无错误。用户原先启动的 M1 进程继续运行，未被停止。
- `.gitignore` 已排除虚拟环境、SQLite/WAL/SHM、日志、缓存、`.env`、私钥及 `.secrets`；无真实密钥写入代码。

## 3. 逐源实际结果

计数为当前新闻条数或相关评论条数，0 明确表示没有成功采集。时间均为 UTC。
HTTP 可访问的探测页不等于采集成功；详细入口与可获取层级见 [data-sources.md](data-sources.md)。

| 媒体/机构/社区 | 最近一次采集状态 | 实际条数 | 最后内容发布时间 UTC | 最后成功采集 UTC | 文章发布至首次发现延迟 |
|---|---|---:|---|---|---|
| CoinDesk | ERROR | 0 | — | — | — |
| Cointelegraph | OK | 30 | 2026-11-01T09:38:18.000Z | 2026-11-01T10:13:30.610Z | 1837.3～211474.3 秒（含历史回填） |
| Decrypt | OK | 39 | 2026-10-31T15:01:02.000Z | 2026-11-01T10:13:30.116Z | 68873.7～315817.7 秒（含历史回填） |
| AP News | RESTRICTED | 0 | — | — | — |
| Reuters | RESTRICTED | 0 | — | — | — |
| The Wall Street Journal | OK | 68 | 2026-11-01T02:00:00.000Z | 2026-11-01T10:17:01.899Z | 29335.6～27125875.6 秒（含历史回填） |
| Bloomberg | ERROR | 0 | — | — | — |
| CNBC | OK | 30 | 2026-11-01T09:03:47.000Z | 2026-11-01T10:13:30.172Z | 3909.5～148395.5 秒（含历史回填） |
| 华尔街见闻 | RESTRICTED | 0 | — | — | — |
| Bureau of Labor Statistics | RESTRICTED | 0 | — | — | — |
| Federal Reserve | OK | 20 | 2026-10-29T20:30:00.000Z | 2026-11-01T10:17:00.678Z | 221936.2～3946136.2 秒（含历史回填） |
| SEC | OK | 25 | 2026-10-30T19:30:00.000Z | 2026-11-01T10:13:31.621Z | 139137.8～4388937.8 秒（含历史回填） |
| U.S. Treasury | RESTRICTED | 0 | — | — | — |
| Hacker News | OK | 11 | 2026-11-01T06:03:40.000Z | 2026-11-01T10:28:12.052Z | — |
| Reddit | RESTRICTED | 0 | — | — | — |

- **Bloomberg**：自有域名候选 feed 连接超时，未得到 XML；0 条，未宣称成功。
- **WSJ**：自有 Dow Jones 托管公开 RSS，HTTP 200/304；70 个 feed 条目对应 68 篇唯一文章，重复项未增加记录。只获取标题、摘要、时间和链接，不是全站或付费独家新闻线。
- **Reuters**：旧免费入口本机超时；已核实官方 Reuters Connect 授权路径，未获得权限，不将第三方镜像冒充官方。
- **华尔街见闻**：公开页面探测 HTTP 200，但未核实自动获取许可及官方开放接口，因此未导入快讯正文，保持待许可。
- **CNBC**：官方 RSS HTTP 200，真实入库；仅该 feed 选题，不保证全球所有突发。
- **CoinDesk**：官方 RSS 有说明但本机超时；适配器支持不等于已经接通。
- **Decrypt / Cointelegraph**：独立加密专业来源，真实标题/摘要/时间/链接已入库；正文 `body` 保持 NULL。
- **Fed / SEC**：官方一手公告，真实 RSS 与条件请求成功；未将官方来源身份直接等同于 BTC 影响证实。
- **AP / BLS**：本机 HTTP 403；未绕过。财政部候选旧 RSS HTTP 404，未用其他频道冒充其政策新闻。
- **Reddit**：官方外部 API 需用途审批与 OAuth，未申请、未连接；凭证名字仅预留。具体费用取决于批准范围，未产生费用。

首轮为历史回填：延迟较大不能当作稳态实时延迟。来源健康另存请求耗时、失败次数、最后尝试、最近成功、内容年龄及冷却时间；`sources --json` 可复查。
本次成功来源请求/批次耗时通常约 0.5～2.5 秒，HN 批次约几十秒，超时源约 25～26 秒；这不是新闻发现延迟。

## 4. 实际新闻与全球重大事件

**真实新闻共 212 篇**；最新发布 `2026-11-01T09:38:18.000Z`，最近文章采集 `2026-11-01T10:17:01.865Z`。
最近 24 小时按发布时间计 **33 篇**，最近 1 小时 **1 篇**；缺失/异常发布时间 **0 条**。
历史 RSS 条目可能早于本窗口；首次发现时间不被用于伪装为新发布。

以下是实际网络返回并入库、**标题没有 BTC/Bitcoin** 的例子，不是合成测试：

- [Qatari mediators held talks in Tehran aimed at restarting direct U.S.-Iran negotiations, source says](https://www.cnbc.com/2026/10/31/qatar-iran-us-talks-mediation.html)：GEOPOLITICS / INDIRECT / UNVERIFIED；原始发布 `2026-10-31T13:47:03.000Z`，首次发现 `2026-11-01T10:08:56.492Z`。
- [Federal Reserve issues FOMC statement](https://www.federalreserve.gov/newsevents/pressreleases/monetary20261028a.htm)：MONETARY_POLICY / INDIRECT / OFFICIAL_STATEMENT；原始发布 `2026-10-28T18:00:00.000Z`，首次发现 `2026-11-01T10:08:56.211Z`。

第一条为匿名来源报道，标记 UNVERIFIED；第二条为官方发布，标记 OFFICIAL_STATEMENT。两者均不是对 BTC 走势的确认。
路径字段分别记录能源/通胀/美元/风险偏好，或利率/流动性预期；**实际市场反应 NOT_MEASURED**，没有给出因果结论。
未出现的“战争爆发/冲突升级”等场景由明确标注的合成测试覆盖，未冒充真实突发。

跨媒体实际聚合示例：同一 Binance 安全事件的报道关联到事件 #213，
保留 Cointelegraph、Decrypt、CNBC 的原始文章与链接；当前媒体数 3，署名/文本去重后的候选组数 3。
这只证明聚合链路工作，**不证明三家独立核实了每项主张**。媒体可能共同引用同一公告，未署名转载仍可能漏判。
按相同主题笼统聚合不被允许；普通标题采用实词与相似度阈值，安全事件须同交易所、同事故词、同明确金额，仍属于候选关联。

## 5. 真实社区评论

实际获取并保留过 **48 条**真实 HN 评论记录，经当前相关性规则纳入统计 **11 条**，
其余 **37 条**因技术悬赏/家电/非投资主题或市场语境不足排除，未用于抬高情绪样本量。
最新有效评论发布 `2026-11-01T06:03:40.000Z`，最后采集 `2026-11-01T10:28:09.002Z`。

帖子与评论正文均来自官方 Firebase API；搜索索引中的正文不会入库，独立服务给出的主题 ID 还沿官方 parent 链核验。
每条均保留主题、评论 ID/父 ID、真实正文、官方 API URL、网页链接及三类时间。必要示例：

- 主题：The $6.3B Binance hack was pulled off in just 20 minutes；必要摘录：“They still need to find buyers at that price. The price is what it is because there are…”；[原评论](https://news.ycombinator.com/item?id=50323075)；发布 `2026-11-01T06:03:40.000Z`，首次发现 `2026-11-01T10:22:56.720Z`，最近采集 `2026-11-01T10:27:36.972Z`；分类 `UNKNOWN`。
- 主题：Binance-hacker-1029 – $5.6B stolen from Binance；必要摘录：“Huh? Bitcoin is only worth anything because you can find some third parties that are willing to give…”；[原评论](https://news.ycombinator.com/item?id=50322157)；发布 `2026-11-01T02:16:52.000Z`，首次发现 `2026-11-01T10:22:57.875Z`，最近采集 `2026-11-01T10:27:50.867Z`；分类 `UNKNOWN`。

真实重复采集最后一轮：获取 **11 条相关评论，新增 0 条，剩余队列 0**。先前遍历批次会发现新评论，不能把新增真实 ID 误作重复。
只遍历有界发现结果和选定主题，不宣称 HN 全量覆盖；HN 偏技术人群且主题集中，无法代表整体投资者。
Reddit 未授权，缺少其核心 BTC 投资/交易社区；没有用新闻文章意见冒充投资者情绪。

## 6. 情绪统计、评测与局限

- 新闻侧只分析事件、重要性、核实状态与潜在路径；新闻负面措辞不产生 BTC 看空标签。观点稿另标 OPINION，不作事实确认。
- 评论版本 `m2-rules-1.0`：中英透明词典/规则，BULLISH / BEARISH / NEUTRAL / UNKNOWN；技术赞美、否定、条件、反讽、历史立场及模糊语义保守处理。
- 实际 HN 24 小时 **7 条 / 2 个主题**，7 天 **11 条 / 3 个主题**；当前全部 UNKNOWN，明确方向样本为 **0**，低于阈值 20，**不输出情绪分数**。
- UNKNOWN=100% 不等于中性，更不等于没有风险。真实样本多为资产价值、事件机制及条件讨论，规则也存在漏识别；不能强行给它们贴多空标签。
- 分数公式 `(Bullish-Bearish)/(Bullish+Bearish+Neutral)`；Unknown 排除，必须同时展示参与样本数。不平均为“全球 BTC 情绪”。

人工合成自测集：评论 **34/36，94.44%**；新闻 **9/9**。
这些案例用于开发和修正规则，**不是独立盲测，不能代表真实样本泛化准确率**。

混淆矩阵（行=人工期望，列=规则输出）：

| 期望 / 输出 | BULLISH | BEARISH | NEUTRAL | UNKNOWN |
|---|---:|---:|---:|---:|
| BULLISH | 8 | 0 | 0 | 1 |
| BEARISH | 0 | 7 | 0 | 1 |
| NEUTRAL | 0 | 0 | 6 | 0 |
| UNKNOWN | 0 | 0 | 0 | 13 |

剩余漏判案例均被保守输出 UNKNOWN：

1. 人工看多样本 “I expect Bitcoin to appreciate substantially.”（未覆盖该同义表达）。
2. 人工看空样本 “Bitcoin is headed for a collapse.”（未覆盖该句式）。

交付命令核验发现的 RSS 正文为空时新闻查询显示异常已修正，并补入 CLI 回归；新闻/评论查询明确分别展示发布时间、首次发现和最近采集时间。

已修正并加入回归的误判：short term 不等于做空；历史 bullish 不等于当前立场；媒体名称 Wall Street Journal 不等于金融危机；普通存款产品推荐不当作央行决策。
相关性排除仍可能有假阳性/假阴性，其他语言、混合资产、引用、复杂讽刺和隐含观点不保证准确。没有调用或计费第三方 LLM。

新闻数量、分类变化与社交热度分别统计。当前历史比较为“不完整”，社交为“样本不足”，不把首次回填当作讨论激增。
监控支持 Critical 候选、多源短时报道候选、类别密度翻倍、讨论翻倍及多空比例变化；必须满足采集覆盖与最低基线样本。
“未发现候选”不表示全球没有发生事件。

## 7. 工程测试与真实网络的区别

**pytest 共 75 项，通过 75，失败 0**；最后功能测试约 1.8 秒。包含原有 M1 **27 项全部回归**，新增 M2 **48 项**。
`pip check` 与 `compileall` 通过。测试均写 pytest 临时目录，不混入实际数据库。

| 类型 | 验证内容 |
|---|---|
| 合成/Mock 网络测试 | HTTP 超时与有限重试、403/429/重定向/503、API 失败及恢复、XML 格式/实体异常、空 feed、重复数据、缺失/未来/无时区时间、恶意 URL/HTML/Markdown、安全取消。 |
| 合成/Mock 评论测试 | 官方正文优先、parent 链核验、嵌套评论、持久化队列、去重、相关性排除、评论删除、分类故障保留 UNKNOWN、四分类、窗口与最低样本、长期未更新。 |
| 合成/Mock 调度与存储 | 来源独立运行、网络恢复继续采集、重复迁移不改 M1、健康记录、窗口基线不足、跨媒体聚合且保留证据、转载去重、本地重算不改三个原始时间。 |
| **真实网络** | WSJ/CNBC/Decrypt/Cointelegraph/Fed/SEC RSS 成功入库，重复采集新增 0；Fed/SEC/WSJ 出现 HTTP 304；失败源真实超时/403/404 单列。 |
| **真实 HN** | 官方主题/评论/父链核验与入库，最后一轮相关评论新增 0；不是 Mock，原始链接可追溯。 |
| **真实持续运行** | `intel-run --seconds 100 --source hn --source wsj --source fed` 正常停止；另起 M2 真实子进程发送 SIGTERM，退出码 0。未完成 24 小时稳定性观察。 |
| **M1 真实回归** | 更新后的 CLI 运行 8 秒，REST 同步 1 次、WS 建连 1 次且收到 3 条合法更新，退出码 0；该短窗口无收盘事件，未声称它写入收盘线。原用户 M1 进程持续落库，基线哈希与连续性保持。 |

原始本地证据：`data/source-probes.json`、`m2-news-repeat.json`、`m2-social-verified-repeat.json`、`m2-sigterm.json`、
`m2-m1-live-regression.txt`、`m2-m1-preservation.json`、`m2-snapshot.json`、`m2-evaluation.json`；均被 Git 忽略，不含凭证。
本次只验证短时运行与规则故障恢复，不能宣称 24 小时运行稳定性或全网完整性。

## 8. 可复现命令与产物

在项目根目录执行：

```bash
.venv/bin/python -m pip install -r requirements.lock -e .
.venv/bin/python -m pytest -q
.venv/bin/btc-intelligence news --source wsj --source cnbc --source decrypt --source cointelegraph --source fed --source sec
.venv/bin/btc-intelligence social
.venv/bin/btc-intelligence intel-run
.venv/bin/btc-intelligence sources
.venv/bin/btc-intelligence news-latest --hours 24 --limit 5
.venv/bin/btc-intelligence comments --hours 168 --limit 5
.venv/bin/btc-intelligence events --hours 24 --json
.venv/bin/btc-intelligence intel-stats --hours 24 --json
.venv/bin/btc-intelligence brief --hours 24 --output data/brief-24h.md
.venv/bin/btc-intelligence evaluate --json --output data/evaluation.json
.venv/bin/btc-intelligence analyze
.venv/bin/btc-intelligence status
```

不指定来源的 `news` 会一并尝试已启用但本机超时的 Bloomberg/CoinDesk，其他来源继续采集；部分失败返回 2，不伪装全成功。
`analyze` 只按本地版本重算分类/相关性，不发外部请求，不修改原文和发布/首次发现/采集时间。
本次产物：`data/m2-brief-24h.md`、`data/m2-brief-7d.md`、`data/m2-evaluation.json`。
M2 验收进程已停止，用户原有 M1 进程保留。重跑后条数和时间可能变化，以命令现场结果为准。

## 9. 产品价值、缺口与 M2.5 建议

当前价值：将加密、全球财经和官方公告统一为可追溯事件候选，能发现不提 BTC 的宏观信息；同时将真实社区评论与新闻意见分开，并暴露采集质量。

当前主要短板：RSS 选题有限且可能延迟；未接通全部 P0 媒体；社区单一、样本少；规则保守且漏掉隐含方向；独立证据判断和跨语言事件聚合不完备；无持续两窗口基线。
没有主动发现完整日历/所有 CPI/PCE/非农发布，也没有完整美元、美债、原油、美股/衍生品联动数据；不能把时间接近当因果。

M2.5 优先候选为华尔街见闻公开中文快讯、财政部公开政策公告、BLS 公开经济数据发布页。
均须先核官方 API/RSS、授权条款、robots 与正常访问条件；Scrapling 不能替代授权，也不能用于绕过本次 403 或付费墙。
详情与独有价值见 [数据来源文档](data-sources.md#m25-候选尚未开发)。

**到此停止，等待产品验收；未推进 M2.5、M3、M4。**
