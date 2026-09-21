# CLAUDE.md

> **跨工具通用指令（系统目标 / 文档导航 / 规范索引 / 架构约束 / 安全红线 / 开发流程）见 `AGENTS.md`**。
> 本文件仅保留 Claude Code 专用内容：常用命令、配置细节、启动流程、自动化守卫、技能触发规则。两文件冲突时以 `AGENTS.md` 为准。

## 项目定位

量化交易平台 — A 股中低频半自动交易系统，**目标：前期资金快速膨胀 · 高收益优先**（见 `docs/01-业务设计/系统目标与投资哲学.md`）。
- 市场：深交所 .SZ + 上交所 .SH，日线/周线级别
- 数据源：Tushare Pro（主）+ Baostock（辅）+ XT P/Mock
- 数据库：PostgreSQL 14+ + TimescaleDB 2.10+

## 常用命令

### 后端（CWD: `quant_server/`，虚拟环境 `.venv/`）

```bash
# 启动（完整初始化：DB 连接池 → FastAPI → EventEngine → MainEngine → 各模块）
python -m quant_server.main --config config.yaml --mode development --port 8080
# 仅启动 API（跳过引擎/模块，适合快速调试路由）
uvicorn quant_server.api.main:create_app --factory --reload --port 8080

# 测试（pyproject.toml 中 testpaths=["tests"]，路径相对于 quant_server/）
pytest                                       # 全量
pytest tests/core/test_engines/test_event_engine.py::test_event_put  # 单条
pytest --cov -q                             # 全量 + 覆盖率

# 代码质量
black . && isort .                           # 格式化（配置见 pyproject.toml，line-length=88）
mypy .                                       # 类型检查（无 mypy.ini，部分规则由 CLI 默认值决定）
```

> ⚠️ **格式化器有两套**：`pyproject.toml` 声明的是 black + isort，但 PostToolUse hook 对新建 `.py` 自动跑的是 `ruff format`（ruff 既不在依赖里也无配置，恰好同为 88 列）。改动格式化相关行为时注意两者差异，不要只改一处。
> ⚠️ `pytest` 的 `addopts = "-v"` 已全局生效（见 `pyproject.toml`），无需再手动加 `-v`。
> ⚠️ `quant_server/scripts/` 下的脚本是**长期资产**，已纳入 git。
> **2026-09-15 按类分目录**（32 个 `.py`、未跟踪 0）：
>
> | 目录 | 数量 | 内容 |
> |:---|---:|:---|
> | `scripts/backtest/` | 6 | 回测与冒烟：`backtest_high_vol_momentum` · `backtest_cross_market_momentum` · `backtest_etf_bottom`⚠️ · `backtest_small_cap`⚠️ · `rolling_start_analysis` · `_rolling_start_cross_market` |
> | `scripts/data/` | 15 | 数据回填与播种：`backfill_*`（11）· `seed_*`（3）· `sync_margin_hsgt` |
> | `scripts/quality/` | 3 | **质量门与巡检**：`audit_strategy`（准入 G1 机检，已接 hook）· `check_all`（收工检查三道门，零 CI 替代）· `sync_strategy_code`（磁盘↔DB 一致性巡检/同步，见 `review/17` §1-8） |
> | `scripts/ops/` | 8 | 运维杂项：`setup_composite` · `add_strategy_to_composite` · `merge_accounts` · `password_utils` · `fix_token` · **`archive_logs`（日志归档，已挂日终）** · `sweep_params`⚠️废弃 · `v2_param_sweep`⚠️废弃 |
>
> ⚠️ 标记含义：**`backtest_etf_bottom`/`backtest_small_cap` 不加载策略类**（独立重实现 —— 改策略后跑它们**验证不了策略代码**，详细对照见「策略开发」节）；**`sweep_params`/`v2_param_sweep` 已标废弃**。
>
> **一次性诊断脚本的两次清理**（先归档后删，可随时取回）：
> | 提交 | 内容 | 取回方式 |
> |:---|:---|:---|
> | `450ccf2` | 33 个（2026-09-12 清理） | `git show 450ccf2:quant_server/scripts/<文件名>` |
> | **`17cc54f`** | **44 个**（2026-09-15 清理，含 `_cm_*` 13 / `_probe_*` 11 / `_phase*` 6 / `_diag_*` 4 / `_verify_*` 等 6 / `_sync_*` 2 / 单件 2） | `git show 17cc54f:quant_server/scripts/<文件名>` |
>
> 新建诊断脚本请沿用 `_` 前缀，**不要提交**（可放 `scripts/_diag/`）。`scripts/_bak/`（同步前自动备份）已在 `.gitignore`。

### 日志（`quant_server/logs/`，**两路分离**，2026-09-15 起）

| 文件 | 内容 | 保留 |
|:---|:---|:---|
| `quant_server.log` | **全量**（DEBUG 起），排查时的"全量视图" | 天轮转；**满 10 天的 → 按月打成 `archive/system/YYYY-MM.zip`**（永久，非删除） |
| `strategy_decision.log` | **实盘决策记录，仅此一路**：策略每日运行 / `[策略诊断]` / `[卖出]止损` / `[VETO]` / F9 守卫 / 走弱期 | **月轮转**（`strategy_decision.log.YYYY-MM`）→ gzip 归档，**永久** |

> ⚠️ **`main.py` 的 `backup_count` 必须是 `0`**（= 本 handler 不删任何轮转文件）。
> 若设成非 0，handler 会在超限时**直接删除**最老文件 → **抢在归档之前毁掉它们**。
> 保留策略（10 天 + 按月压缩）由 `scripts/ops/archive_logs.py` 统一执行，已挂日终任务
> （`archive_logs`，`pre_gate order=1` —— 放 pre_gate 是因为 post_gate 在数据完整性门失败时会被整体跳过）。
>
> 归档实测（2026-09-17）：`156M → 109M`，42.2M → `2026-08.zip`（**2.5M，17×压缩**），
> 10.7M → `2026-09.zip`（0.7M）；幂等复跑 0 待归档 ✓

> ⚠️ **为什么决策日志必须独立且长期保留**：**实盘决策过程不落库** ——
> `strategy_manager._run_live_strategies` 的「策略每日运行」「[策略诊断]」只走 `logger.info`，
> 各策略内部的止损/否决/守卫同样只打日志。**DB 只记「决策结果」（`signals`/`positions`/`orders`），
> 不记「决策过程」**。→ 要回答「某天为什么没买 / 为什么选它 / 哪道门拒的」，**只能查这个日志**。
>
> ⚠️ 分流靠 `LiveDecisionFilter`（`utils/core_utils/logging_utils/decision_log.py`）：
> **实盘驱动期间 + 策略层命名空间 + INFO 以上**。不加过滤器会被**回测日志淹没**
> —— 实测 2026-09-13 单日策略层 136,786 行中 **135,501 行来自回测/对照实验**，实盘仅 1,285 行。
>
> 归档/清理：`cd quant_server && .venv/Scripts/python.exe scripts/ops/archive_logs.py [--apply]`
> （默认 dry-run；`--system-days N` 可调保留期，默认 **10**）

### 前端（CWD: `quant_web/`）

```bash
pnpm serve          # 开发服务器 (8081, proxy /api → localhost:8080)
pnpm build          # 生产构建
pnpm preview        # 预览生产构建
pnpm test:unit      # 单元测试 (vitest + jsdom)
pnpm format         # Prettier 格式化
npx vue-tsc --noEmit  # TypeScript 类型检查
```

> ⚠️ **2026-09-15 实测订正两处（原表述与实际不符）**：
>
> | 原表述 | 实测 |
> |:---|:---|
> | `pnpm test:e2e  # E2E（cypress open）` | ❌ **cypress 未安装**、无 `cypress/` 目录、`package.json` 无该依赖（仅在 `scripts` 里）→ 跑必然失败。**E2E 实际不存在**（现有前端测试只有 `tests/unit/` 下 3 个 vitest 文件） |
> | 「husky + lint-staged **已配置**：提交时自动跑 prettier」 | ⚠️ **只有一半**：`lint-staged` 的配置与依赖在 `package.json` 里，但**无 `.husky/` 目录、无 `prepare` 脚本** → **git hook 未安装**，提交时不会真的触发 |
>
> 二者待办：要么补齐（安装 cypress / `npx husky init`），要么删掉对应表述。

## 配置系统

项目使用**双层配置**：

| 文件 | 用途 | 加载方式 |
|:---|:---|:---|
| `quant_server/config.yaml` | 非敏感参数（模块开关、引擎参数、端口、日志等） | `StartupConfig.__init__()` 主动加载 |
| `quant_server/.env` | 敏感凭证 + 环境变量（DB 密码、Tushare Token、`SIMULATED_TRADING`） | pydantic-settings 自动解析 |

关键环境变量（`.env`）：
- `ENVIRONMENT` — `development` / `production` / `testing`，决定加载 `DEV_*` 还是 `PROD_*` 前缀配置
- `SIMULATED_TRADING` — ⚠️ **只影响日志与 API 返回值的展示，不是执行开关**。真正的执行开关是 `config.yaml` 的 `modules.trade.simulated_trading`（详见「安全红线」）
- `DEV_DATABASE__HOST/PORT/USER/PASSWORD/NAME` — 开发库（默认 `quant_signals_dev`，与生产库隔离）
- `DEV_TUSHARE_TOKEN` — Tushare Pro 数据源凭证
- `AUTH_ENABLED=false` — JWT 校验开关（`config.yaml` 中控制，非 `.env`）

## 数据库

- DDL 入口：`docs/sql/create_table.sql`（**表结构以该文件为准**，21 张超表，无迁移框架，直接执行）
  > ⚠️ 2026-09-15 订正：原写「131 张表」，实测 `CREATE TABLE` 为 **133**（同处 AGENTS.md 已同步改为不写数字）。
  > **计数类表述一律以文件为准**，避免随 DDL 演进反复漂移。
- 开发库与生产库分离：开发 `quant_signals_dev`，生产 `quant_signals`

## 分支策略

- `dev` — 开发分支（当前工作分支）
- `master` — 生产/稳定分支
- **严禁在 `master` 上直接提交**，所有变更经 `dev` 验证后合并

## 安全红线

- ⚠️ **`.env` 的 `SIMULATED_TRADING` 不是执行开关**，它只被 `main.py` 用于日志与 API 返回值展示。**真正的执行开关是 `config.yaml` → `modules.trade.simulated_trading`**（`modules/trade/__init__.py:77-79`）。两者可背离，改一个不会影响另一个。
- ⚠️ **本系统不具备自动下单能力，这一点不要误解**：`config.yaml` 的开关确实会改变执行路径（`execution_engine.py:170` 模拟内存直接成交 ←→ `:203` 「真实交易路径」调 `broker_adapter.send_order`），**但两条路径的 broker 都是 `SimBrokerAdapter`**（`modules/trade/__init__.py:96-106`，`BrokerAdapter` 基类的 7 个方法全为 `pass`，全仓无真实券商适配器实现）。因此**把 `SIMULATED_TRADING` 或 `simulated_trading` 设为 false，都不会产生真实交易**。
  > 误解来源：`execution_engine.py:163,165,202` 的注释与日志（「安全红线 — 模拟模式下绝不向券商发送真实订单」「[LIVE] 真实交易模式：发送订单至券商」）是按「能真实下单」写的，但该能力从未实现。
  > 另注：`TradeManager.simulated_trading` 可被 `update_trading_config` **运行时修改**（`trade_manager.py:45-46`），无审计。
- ✅ **真实资金风险的唯一路径是人工环节**：系统出信号 → 人工在券商端下单 → 人工回系统「确认成交」+「录入成交」（`execution_mode=semi_auto`）。保护你的是人工确认这一步，不是上面那两个开关——**别把开关当成兜底**。
- **严禁**向 `.env`、`.git/`、凭证文件写入任何内容。
- **严禁**在 `master` 分支上直接提交。
- 高收益目标不豁免任何安全/风控红线（见 `AGENTS.md`）。

## 行为约束

- **编码前必须先读核心文档**：`docs/01-业务设计/系统目标与投资哲学.md`（目标）→ `系统建设现状白皮书.md`（代码现状基线）→ `量化交易系统详细设计.md`（系统设计），并浏览 `api/` `core/` `shared/` `modules/` 目录。不跳过信息收集直接编码。
- **先输出《开发路径说明》，等用户确认后再编码**。不跳过确认步骤。
- **只修改规划内文件**，不顺手重构无关代码、格式化相邻文件、或"修复"未在计划中的问题。
- **严禁私自回退代码**（git revert/reset/手动撤销）。任何回退操作前必须向用户说明原因并获取确认。
- **排查问题必须完整追踪逻辑链路**：从入口到出口逐环节排查，定位到根因后再修改代码。**严禁依据猜测私自修改代码** — 不确定时必须先验证假设，确认根因后再动手。
- **遇到信息缺失、计划偏差、需求变更 → 立即暂停**，提交结构化报告，等待用户确认。不自行假设解决方案。
- **处理后端任务时**，先加载 `.claude/skills/quantsys-architect/SKILL.md` 执行步骤 0-3。
- **处理前端任务时**，遵循 `.claude/rules/frontend.md`，调用 `.claude/skills/frontend-craft/SKILL.md`。

## 启动流程

1. `QuantServer.__init__()` → `StartupConfig` 加载 `config.yaml`（pydantic-settings 同时解析 `.env`）
2. `initialize()` → DB 连接池 → FastAPI `create_app()` → EventEngine → MainEngine
3. MainEngine 按**拓扑排序**加载各模块 `initialize(main_engine, event_engine, config)`，自动解析模块间依赖
4. `SystemStartedEvent` → 各引擎开始处理事件
5. Uvicorn ASGI 服务，前端 Vite proxy `/api` → `localhost:8080`

默认启用的 10 个模块（`config.yaml` 中可禁用，职责明细见 `docs/01-业务设计/业务功能设计.md`）：

| 模块 | 职责 |
|:---|:---|
| `data` | 数据同步（Tushare→DB）、因子计算、研究服务 |
| `strategy` | 策略管理、信号生成、绩效跟踪 |
| `trade` | 信号→订单执行（模拟/实盘）、仓位管理 |
| `backtest` | 历史回测、绩效分析、参数优化 |
| `account` | 多账户管理、资金流水、日终结算 |
| `risk` | 风控检查（止损、仓位上限，19 条规则） |
| `analysis` | 绩效归因、Sharpe/MDD 等指标 |
| `monitor` | 系统监控、告警推送（微信/钉钉/邮件） |
| `market` | 实时行情、交易日历 |
| `system` | JWT 认证、系统配置 |

## 策略开发

策略实现位于 `quant_server/modules/strategy/strategies/`，继承 `base/base_strategy.py`。

> ⚠️ **策略运行时从 DB `strategies.code` 加载代码（`exec()`），回测引擎同样如此**——改磁盘 `.py` 文件**必须同步 `strategies.code` 才生效**，否则实盘/回测仍跑旧代码。改参数默认值还须同步 DB `strategy_parameters` 覆盖（JSON 列会盖掉 `DEFAULT_PARAMS`）。

**信号级冒烟验证（磁盘加载、不走 DB）**：

```bash
cd quant_server && .venv/Scripts/python.exe scripts/backtest/backtest_high_vol_momentum.py      # 2025-01-01~2026-08-07
cd quant_server && .venv/Scripts/python.exe scripts/backtest/backtest_cross_market_momentum.py  # 2021-01-01~2026-08-07
cd quant_server && .venv/Scripts/python.exe scripts/backtest/backtest_etf_bottom.py
cd quant_server && .venv/Scripts/python.exe scripts/backtest/backtest_small_cap.py              # 微盘，2021-01-01~2026-08-07
```

> ⚠️ **2026-09-15 实测订正 —— 这 4 个脚本并非都是"策略冒烟"**：
>
> | 脚本 | 加载策略类 | 支持 `[start] [end]` |
> |:---|:---|:---|
> | `backtest_high_vol_momentum.py` | ✅ | ✅ |
> | `backtest_cross_market_momentum.py` | ✅ | ✅ |
> | `backtest_etf_bottom.py` | ❌ **独立重实现** | ❌ 日期硬编码 |
> | `backtest_small_cap.py` | ❌ **独立重实现** | ✅ |
>
> **后两个不 `import` 任何策略类**（自带撮合/止损逻辑，如 `backtest_small_cap.py` 的 `STOP_LOSS = -0.09`
> 是脚本内常量，与策略 `stop_loss_pct` 参数无关）→ **改 `etf/bottom_strategy.py` 或
> `microcap/microcap_strategy.py` 后跑它们，全绿也验证不了策略代码**。
> 自检命令：`grep -cE "import.*Strategy|from modules.strategy.strategies" scripts/<脚本>.py`（0 = 重实现）。
> 这两个策略的回归验证请用 pytest：`test_bottom_strategy_p1_fixes.py` / `test_microcap_strategy.py`。

**验证口径（全项目统一）**：有交易 / 无 NaN / 收益率 ∈ **[−95%, +500%]**。
（旧的「收益率合理」表述已废弃，见 `.claude/skills/strategy-dev/SKILL.md` 步骤 5。）

> ⚠️ **路径依赖型策略禁止用单一起始日结论**（区间收益随起跑日剧烈漂移）。必须用滚动起始日看**中位数 / 下四分位**分布：
> `cd quant_server && .venv/Scripts/python.exe scripts/backtest/rolling_start_analysis.py [start1,start2,...]`（默认 6 个起始日，固定结束于 2026-09-04）。

**实际策略清单（代码实证，见白皮书 §4）**：

| 定位 | 策略 | 文件 |
|:---|:---|:---|
| 主池进攻 | 高波动动量轮动 v7.1（实盘确认 2026-08） | `rotation/high_vol_momentum_strategy.py` |
| 主池避险 | 跨市场动量避险轮动 v1.0（A股走弱切全球/商品 ETF） | `rotation/cross_market_momentum_strategy.py` |
| 主池防守 | ETF 底部抄底（LightGBM，磁盘 v4） | `etf/bottom_strategy.py` |
| 卫星·事件 | 恐慌抄底（阶段 4b，模拟盘 draft） | `panic/panic_bottom_strategy.py` |
| 卫星·进攻 | 微盘股 + 双指数择时（阶段 4c，模拟盘 draft） | `microcap/microcap_strategy.py` |
| 参考/历史 | 低吸轮动 | `reference/stock_low_high_strategy.py` |
| 参考/历史 | 深跌反包（短线超跌反弹，2026-09 数据挖掘） | `reference/deep_drop_rebound_strategy.py` |
| 基类 | BaseStrategy 生命周期 | `base/base_strategy.py` + `base/strategy_context.py` |

> ⚠️ 旧文档所列 industry_rotation / dl / ml 等策略**代码中不存在**（历史快照文件如 `high_vol_momentum_v90.py` 已删除，对应测试已 `pytest.mark.skip`）。
> ⚠️ 一个策略的代码可能同时存在于**多处 DB 副本**（`strategies.code` 多个实例 + `strategy_templates.code_template`）。磁盘→DB 同步已有带 dry-run 的脚本范式可参考：`scripts/_sync_cross_market_code.py`（不带 `--apply` 只查，带则 UPDATE 全部副本）。

## 自动化守卫（`.claude/settings.json`）

- **PreToolUse → Write/Edit**：拦截对 `.env`、`.git/`、凭证文件的写入
- **PreToolUse → `git push`**：拦截向 `master` 分支的推送
- **PostToolUse → Write**：自动 `ruff format` 格式化新写入的 `.py` 文件；凭证硬编码扫描

## 规则与技能触发索引

> 完整职责边界表见 `AGENTS.md`「规范文件索引」。此处为触发速查：

| 资源 | 路径 | 触发条件 |
|:---|:---|:---|
| 系统目标 | `docs/01-业务设计/系统目标与投资哲学.md` | 涉及目标/定位/收益口径 |
| 代码现状基线 | `docs/01-业务设计/系统建设现状白皮书.md` | 冲突裁决 / 现状核对 |
| 系统设计 | `docs/01-业务设计/量化交易系统详细设计.md` | 架构/数据/策略体系 |
| 技术实现 | `docs/01-业务设计/技术实现设计.md` | 引擎/事件/API 契约/Repository |
| 策略体系入口 | `docs/00-核心策略体系/`（见 `docs/README.md`） | 策略规划/设计/基建/可行性/实施/迭代记录 |
| 后端开发 SOP | `.claude/skills/quantsys-architect/SKILL.md` | 后端编码 |
| 策略开发 SOP | `.claude/skills/strategy-dev/SKILL.md` | 策略开发 |
| 策略质量门 | `.claude/skills/strategy-auditor/SKILL.md` | 上线前/回测前检查 |
| 策略系统盘查 | `.claude/skills/strategy-review/SKILL.md` | 目标不可达、回测不佳、实盘漂移 |
| 前端质感规范 | `.claude/skills/frontend-craft/SKILL.md` | 前端 UI |
| 前端页面设计 | `.claude/skills/frontend-craft/page-design.md` | 新页面 |
| 组件开发规范 | `.claude/skills/frontend-craft/component-dev.md` | 新组件 |
| 前端开发规则 | `.claude/rules/frontend.md` | `quant_web/**` |
| 通用代码审计 | `.claude/rules/audit.md` | `**` |
| 后端深度审计 | `.claude/rules/audit-backend.md` | `quant_server/**/*.py` |
| 策略深度审计 | `.claude/rules/audit-strategy.md` | `quant_server/modules/strategy/**/*.py` |
| 策略快速质量门 | `.claude/rules/strategy-gates.md` | 策略文件变更 |
| 回测分析标准流程 | `docs/06-标准规范/04_回测分析标准流程.md` | 回测结果分析（所有策略通用） |
| 策略运行分析标准流程 | `docs/06-标准规范/07_策略运行分析标准流程.md` | 实盘/日终运行分析（所有策略通用） |
| 策略实盘准入标准 | `docs/06-标准规范/06_策略实盘准入标准.md` | 策略上线/准入判定（六道门 G0–G5 + 三级实盘） |
| 策略过拟合检验标准 | `docs/06-标准规范/05_策略过拟合检验标准.md` | 参数/机制采纳前的过拟合检验（台账/PBO/DSR） |
| 因子研究标准流程 | `docs/06-标准规范/03_因子研究标准流程.md` | 因子研究/注册/落库/消费（含 PIT 红线） |
| 数据质量标准 | `docs/06-标准规范/01_数据质量标准.md` | 数据五道门（完整性/正确性/PIT/停牌/运行期） |
| 交易·风控·账户专项规则 | `.claude/rules/trade-risk-account.md` | `quant_server/modules/{trade,risk,account}/**/*.py` |
| 卫星策略分析 | `docs/00-核心策略体系/卫星策略分析.md` | 微盘/恐慌抄底卫星优化方向 |
