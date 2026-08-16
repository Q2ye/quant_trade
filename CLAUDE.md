# CLAUDE.md

> 跨工具通用指令见 `AGENTS.md`。本文件为 Claude Code 专用扩展。

## 项目定位

量化交易平台 — A 股中低频半自动交易系统。
- 市场：深交所 .SZ + 上交所 .SH，日线/周线级别
- 数据源：Tushare Pro（主）+ Baostock（辅）
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

- DDL 入口：`docs/sql/create_table.sql`（93 张表，含 TimescaleDB 超表）
- 无迁移框架（Alembic 等），**直接执行 SQL 文件建表**
- 开发库与生产库分离：开发 `quant_signals_dev`，生产 `quant_signals`

## 分支策略

- `dev` — 开发分支（当前工作分支）
- `master` — 生产/稳定分支
- **严禁在 `master` 上直接提交**，所有变更经 `dev` 验证后合并

## 安全红线

- **`SIMULATED_TRADING=true`** 是安全总开关。**开发/测试环境严禁设为 false**，否则产生真实资金交易。
- **严禁**向 `.env`、`.git/`、凭证文件写入任何内容。
- **严禁**在 `master` 分支上直接提交。

## 行为约束

- **编码前必须先读 docs/ 下三份核心设计文档**（方案设计、混合架构设计、数据表设计），浏览 `api/` `core/` `shared/` `modules/` 目录。不跳过信息收集直接编码。
- **先输出《开发路径说明》，等用户确认后再编码**。不跳过确认步骤。
- **只修改规划内文件**，不顺手重构无关代码、格式化相邻文件、或"修复"未在计划中的问题。
- **严禁私自回退代码**（git revert/reset/手动撤销）。任何回退操作前必须向用户说明原因并获取确认。
- **排查问题必须完整追踪逻辑链路**：从入口到出口逐环节排查，定位到根因后再修改代码。**严禁依据猜测私自修改代码** — 不确定时必须先验证假设，确认根因后再动手。
- **遇到信息缺失、计划偏差、需求变更 → 立即暂停**，提交结构化报告，等待用户确认。不自行假设解决方案。
- **处理后端任务时**，先加载 `.claude/skills/quantsys-architect/SKILL.md` 执行步骤 0-3。
- **处理前端任务时**，遵循 `.claude/rules/frontend.md`，调用 `.claude/skills/frontend-craft/SKILL.md`。

## 核心架构约束

### 依赖方向（严禁反向）
```
modules/ → shared/ → core/
modules/ → utils/
api/ → shared/
```

### 通信机制（严禁跨模块直接 import）
| 场景 | 方式 |
|:---|:---|
| Service → Repository | 同步直接调用 |
| 模块间（如 strategy → trade） | **仅通过 EventEngine 异步事件** |
| Engine 之间 | EventEngine 发布/订阅 |

### Engine vs Service（严禁混淆职责）
- **Engine**：有状态，继承 `EngineBase`，响应事件，协调 Service
- **Service**：无状态纯计算，不持有事件引擎引用

### 事件命名
格式 `{module}.{domain}.{action}.{status}`，如 `trade.order.submitted`

### 模块标准目录
```
modules/<name>/
  engines/  events/  services/  handlers.py
  managers/  schemas.py  models.py  tasks/  utils/  constants.py
```

### Repository 规范
一表一 Repository，继承 `BaseRepository`，纯 CRUD 不含业务逻辑。

## 启动流程

1. `QuantServer.__init__()` → `StartupConfig` 加载 `config.yaml`（pydantic-settings 同时解析 `.env`）
2. `initialize()` → DB 连接池 → FastAPI `create_app()` → EventEngine → MainEngine
3. MainEngine 按**拓扑排序**加载各模块 `initialize(main_engine, event_engine, config)`，自动解析模块间依赖
4. `SystemStartedEvent` → 各引擎开始处理事件
5. Uvicorn ASGI 服务，前端 Vite proxy `/api` → `localhost:8080`

默认启用的 10 个模块（`config.yaml` 中可禁用）：

| 模块 | 职责 |
|:---|:---|
| `data` | 数据同步（Tushare→DB）、因子计算、研究服务 |
| `strategy` | 策略管理、信号生成（技术/AI/Alpha 三类策略） |
| `trade` | 信号→订单执行（模拟/实盘）、仓位管理 |
| `backtest` | 历史回测、绩效分析 |
| `account` | 多账户管理、资金流水 |
| `risk` | 风控检查（止损、仓位上限） |
| `analysis` | 绩效归因、Sharpe/MDD 等指标 |
| `monitor` | 系统监控、钉钉/微信通知 |
| `market` | 实时行情、交易日历 |
| `system` | JWT 认证、系统配置 |

## 策略开发

策略实现位于 `quant_server/modules/strategy/strategies/`，继承 `base/base_strategy.py`：

| 分类 | 策略 | 文件 |
|:---|:---|:---|
| 技术指标 | MA 双均线交叉 | `technical/ma_cross_strategy.py` |
| 技术指标 | MACD | `technical/macd_strategy.py` |
| Alpha 因子 | 多因子选股 | `alpha/factor_strategy.py` |
| Alpha 因子 | 均值回归 | `alpha/mean_reversion_strategy.py` |
| 行业轮动 | 行业轮动 | `rotation/industry_rotation_strategy.py` |
| 大类资产 | 多资产轮动 | `rotation/multi_asset_rotation_strategy.py` |
| AI | 深度学习 | `ai/dl_strategy.py` |
| AI | 机器学习 | `ai/ml_strategy.py` |

## 自动化守卫（`.claude/settings.json`）

- **PreToolUse → Write/Edit**：拦截对 `.env`、`.git/`、凭证文件的写入
- **PreToolUse → `git push`**：拦截向 `master` 分支的推送
- **PostToolUse → Write**：自动 `ruff format` 格式化新写入的 `.py` 文件

## 规则与技能索引

| 资源 | 路径 | 触发条件 |
|:---|:---|:---|
| 架构设计文档 | `docs/量化交易系统-混合架构设计.md` | 后端开发 |
| 方案设计文档 | `docs/量化交易平台方案设计.md` | 业务设计 |
| 数据表设计 | `docs/量化交易平台数据表设计.md` + `docs/sql/create_table.sql` | DB 变更 |
| 回测业务流程 | `docs/策略回测业务流程说明.md` | 回测相关 |
| 后端开发 SOP | `.claude/skills/quantsys-architect/SKILL.md` | 后端编码 |
| 策略系统盘查 | `.claude/skills/strategy-review/SKILL.md` | 策略达标性/问题点定位（目标不可达、回测不佳、上线前） |
| 前端质感规范 | `.claude/skills/frontend-craft/SKILL.md` | 前端 UI |
| 前端页面设计 | `.claude/skills/frontend-craft/page-design.md` | 新页面 |
| 组件开发规范 | `.claude/skills/frontend-craft/component-dev.md` | 新组件 |
| 前端开发规则 | `.claude/rules/frontend.md` | `quant_web/**` |
| 通用代码审计 | `.claude/rules/audit.md` | `**` |
| 后端深度审计 | `.claude/rules/audit-backend.md` | `quant_server/**/*.py` |
