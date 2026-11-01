# BTC Intelligence

个人使用的 BTC 数据与研究系统。当前仅完成 **M1：真实现货分钟行情采集与 SQLite 落库**。
不连接交易账户，不需要交易 API Key，不自动交易。新闻、社交情绪、合约与信号仍属后续里程碑。

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
│   └── collectors/__init__.py / collectors/binance.py
├── tests/
│   ├── conftest.py
│   ├── test_models_database.py
│   └── test_rest_service.py
├── docs/data-sources.md / docs/m1-acceptance.md
├── data/.gitkeep / data/btc.sqlite3（本机数据，Git 忽略）
└── logs/.gitkeep / logs/collector.log（Git 忽略）
```

`.venv`、数据库（含 WAL/SHM）、日志、缓存、`.env` 均被 Git 忽略。
`requirements.lock` 固定本次验收的运行和测试依赖；`pyproject.toml` 声明兼容范围。
采集器、模型、存储和服务分离，为后续 FastAPI、Dashboard 和 Docker 保留边界，本阶段不引入它们。

## 里程碑与当前边界

实际验收证据见 [M1 验收记录](docs/m1-acceptance.md)。本次验证是短时真实采集与重启验证，尚未完成连续 24 小时稳定性验收。
电脑需要保持联网和唤醒；M1 提供前台常驻命令，未安装开机服务或云端部署。

后续路线（须逐次验收，本次停在 M1）：

1. **M2 必须包含**新闻 RSS、真实社交评论、去重与情绪分析。
2. M3：OI、资金费率、多空比例、技术指标及市场结构。
3. M4：多因子研判、证据与风险边界、历史记录和模拟验证；仍不自动交易。
