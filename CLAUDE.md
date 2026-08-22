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
black . && isort .                           # 格式化
mypy .                                       # 类型检查（无 mypy.ini，部分规则由 CLI 默认值决定）
```

### 前端（CWD: `quant_web/`）

```bash
pnpm serve          # 开发服务器 (8081, proxy /api → localhost:8080)
pnpm build          # 生产构建
pnpm preview        # 预览生产构建
pnpm test:unit      # 单元测试 (vitest + jsdom)
pnpm format         # Prettier 格式化
npx vue-tsc --noEmit  # TypeScript 类型检查
```

## 配置系统

项目使用**双层配置**：

| 文件 | 用途 | 加载方式 |
|:---|:---|:---|
| `quant_server/config.yaml` | 非敏感参数（模块开关、引擎参数、端口、日志等） | `StartupConfig.__init__()` 主动加载 |
| `quant_server/.env` | 敏感凭证 + 环境变量（DB 密码、Tushare Token、`SIMULATED_TRADING`） | pydantic-settings 自动解析 |

关键环境变量（`.env`）：
- `ENVIRONMENT` — `development` / `production` / `testing`，决定加载 `DEV_*` 还是 `PROD_*` 前缀配置
- `SIMULATED_TRADING=true` — **安全总开关**，false 产生真实交易
- `DEV_DATABASE__HOST/PORT/USER/PASSWORD/NAME` — 开发库（默认 `quant_signals_dev`，与生产库隔离）
- `DEV_TUSHARE_TOKEN` — Tushare Pro 数据源凭证
- `AUTH_ENABLED=false` — JWT 校验开关（`config.yaml` 中控制，非 `.env`）

## 数据库

- DDL 入口：`docs/sql/create_table.sql`（**131 张表**，21 张超表，无迁移框架，直接执行）
- 开发库与生产库分离：开发 `quant_signals_dev`，生产 `quant_signals`

## 分支策略

- `dev` — 开发分支（当前工作分支）
- `master` — 生产/稳定分支
- **严禁在 `master` 上直接提交**，所有变更经 `dev` 验证后合并

## 安全红线

- **`SIMULATED_TRADING=true`** 是安全总开关。**开发/测试环境严禁设为 false**，否则产生真实资金交易。
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

策略实现位于 `quant_server/modules/strategy/strategies/`，继承 `base/base_strategy.py`。**实际策略清单（代码实证，见白皮书 §4）**：

| 定位 | 策略 | 文件 |
|:---|:---|:---|
| 主池进攻 | 高波动动量轮动 7.1（实盘确认 2026-08；代码注释 v7.3） | `rotation/high_vol_momentum_strategy.py` |
| 主池防守 | ETF 底部抄底（LightGBM） | `etf/bottom_strategy.py` |
| 参考/历史 | 低吸轮动 | `reference/stock_low_high_strategy.py` |
| 基类 | BaseStrategy 生命周期 | `base/base_strategy.py` + `base/strategy_context.py` |

> ⚠️ 旧文档所列 industry_rotation / dl / ml 等策略**代码中不存在**；`rotation/` 下 `high_vol_momentum_v71_restore.py`、`v90.py` 为版本快照文件，非活动策略。

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
| 策略体系入口 | `docs/00-核心策略体系/`（5 份） | 策略规划/设计/基建/可行性/实施 |
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
