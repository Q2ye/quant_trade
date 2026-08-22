# AGENTS.md — 量化交易平台 (QuantTrade) 跨工具统一指令源

> 本文档为**跨 AI 编码工具的统一指令源**（Claude Code / Cursor / Codex CLI / Aider 等均支持）。
> Claude Code 专用扩展见 `CLAUDE.md`；所有规范文件的职责边界见下文「规范文件索引」。

## 系统目标（唯一真相源）

> **前期资金快速膨胀 · 高收益优先**。目标（2026-08 用户确认，三档制）：**5 年 30 万起步 —— 底线 ≥3x / 基准 5-8x（150-240 万）/ 冲刺 10x+（500 万）**；主策略实证年化 **36.67%**（7.1 实盘组合，`backtest_tasks` 权威口径）；卫星策略**不追求年化，只追求单次进攻收益**；**实盘资金 ≥50 万触发 IV 接入 → 期权转可实施**（冲刺唯一大增量）。完整目标函数、可行性拆解与权威回测口径见：
> **`docs/01-业务设计/系统目标与投资哲学.md`**（系统级目标唯一真相源，任何文档涉及目标表述一律引用此文，不重复维护）

## 技术栈

| 层 | 技术 |
|:---|:---|
| 后端 | Python / FastAPI / SQLAlchemy 2.0 / PostgreSQL 14+ + TimescaleDB 2.10+ |
| 前端 | Vue 3 + TypeScript / Naive UI / ECharts / Vite / Vuex 4 |
| 数据源 | Tushare Pro (主) + Baostock (辅) + XT P/Mock |
| 包管理 | pip (后端) / pnpm (前端) |

## 文档导航（docs 目录唯一入口：`docs/README.md`）

| 文档 | 用途 |
|:---|:---|
| `docs/README.md` | **docs 唯一入口**：核心策略体系 → 业务设计 → 功能设计 → 调研分析 → 归档 |
| `docs/01-业务设计/系统目标与投资哲学.md` | **系统目标唯一真相源**（前期资金快速膨胀期/投资哲学/红线） |
| `docs/01-业务设计/系统建设现状白皮书.md` | **代码现状基线**：模块/引擎(22)/表(131)/策略(5)/前端(55页)/API(15路由) 代码实证；冲突裁决以此为准 |
| `docs/01-业务设计/量化交易系统详细设计.md` | **系统设计真相源**：架构约束/启动流程/数据体系/策略体系/回测/实盘/开发规范 |
| `docs/01-业务设计/技术实现设计.md` | 引擎体系(22)/事件体系/API 契约(15 router)/Repository(126)/数据管道 |
| `docs/00-核心策略体系/`（4 份） | 策略体系入口：规划（多策略整体架构规划）/ 策略设计 / 基建设计 / 实施计划 |
| `docs/02-功能设计/` | 功能级依据：策略体系/数据模块/市场模块/交易模块/风控/账户/绩效/监控/系统 |
| `docs/sql/create_table.sql` | DDL 入口（131 张表，21 张超表），无迁移框架，直接执行 |
| `docs/04-归档/` | 历史只读，不删（含已整合的设计源文档、已退役策略报告） |

## 规范文件索引（职责边界一览）

> 以下规范文件由 Claude Code 实现（`.claude/` 目录）。**其它工具（Cursor/Aider/Codex 等）按「职责」列对照执行**，路径为 Claude Code 专用。

### 规则（Rules，按文件变更自动加载）

| 文件 | 适用路径 | 职责 |
|:---|:---|:---|
| `.claude/rules/audit.md` | `**` | 通用代码审计：不等式方向三步检查、边界条件、禁止项 |
| `.claude/rules/audit-backend.md` | `quant_server/**/*.py` | 后端深度审计：数据流追踪（单源原则）、查询模式、算法复杂度、运行时、金融精度 |
| `.claude/rules/audit-strategy.md` | `quant_server/modules/strategy/**/*.py` | 策略专属深度审计：未来函数零容忍、四大模块拆分、边界全覆盖、交付六步 |
| `.claude/rules/strategy-gates.md` | 同上 | 策略快速质量门：每次变更必查清单（DB 同步/参数声明/冒烟回测） |
| `.claude/rules/frontend.md` | `quant_web/**` | 前端三阶段流程（页面方案→开发路径→实施）与编码/验证规范 |

### 技能（Skills，按任务关键词调用）

| 技能 | 职责 | 触发关键词 |
|:---|:---|:---|
| `.claude/skills/quantsys-architect/` | 架构层开发 SOP（依赖方向/引擎/事件/Repository/配置） | 模块架构、引擎开发、事件通信、建表 |
| `.claude/skills/strategy-dev/` | 策略开发 SOP（类型定位/数据依赖/代码规范/DB 同步/回测） | 策略代码、因子接入、回测参数 |
| `.claude/skills/strategy-auditor/` | 策略质量门：机检清单（未来函数/凭证/除零/参数越界） | 上线前检查、回测前验证 |
| `.claude/skills/strategy-review/` | 策略系统盘查（A1-C3 九检查块） | 回测远低于目标、实盘漂移排查 |
| `.claude/skills/frontend-craft/` | 前端质感与规范（页面设计/组件开发/SKILL） | 新页面、新组件、UI 质感 |

### 其它

| 文件 | 职责 |
|:---|:---|
| `.claude/agents/strategy-reviewer.md` | 独立策略审查 Agent（只读，作者不自审） |
| `.claude/agents/backtest-analyzer.md` | 回测结果深度分析 Agent（只读） |
| `.claude/settings.json` | 自动化守卫 hooks：`.env`/`.git/` 写入拦截、master 推送拦截、py 文件自动 ruff format、凭证扫描 |

## 关键架构约束

- **依赖方向**: `modules/ → shared/ → core/`（严格单向，不可反向）；`api/ → shared/`
- **模块间通信**: 仅通过 EventEngine 异步事件，**禁止直接 import 其他模块**
- **事件命名**: `{module}.{domain}.{action}.{status}` 格式
- **Engine vs Service**: Engine 有状态（继承 `EngineBase`），Service 无状态纯计算
- **Repository**: 一表一仓库，继承 `BaseRepository`，纯数据访问不含业务逻辑

## 安全红线（不可违反）

- **`SIMULATED_TRADING=true`** 是开发环境安全总开关，**开发/测试环境不得设为 false**
- 禁止向 `.env`、`.git/`、凭证文件写入
- 禁止在主分支 (master/main) 上直接提交（当前工作分支 `dev`）

## 开发流程

1. 编码前先读 `docs/` 核心文档（系统目标 → 白皮书 → 详细设计 → 相关功能设计）
2. 先输出《开发路径说明》（涉及文件 + 跨模块影响 + 验证方案），等用户确认后再编码
3. 仅修改规划内文件，不顺手重构无关代码
4. 禁止未经确认私自回退任何代码（git revert/reset/手动撤销）
5. 排查问题必须完整追踪逻辑链路、定位根因后再修改；**严禁依据猜测私自修改代码**
6. 遇到信息缺失、计划偏差、需求变更 → 暂停并提交结构化报告，等待用户确认

## 市场与交易模式

- **市场**: A 股（深交所 .SZ + 上交所 .SH）
- **频率**: 中低频，日线/周线级别（非高频/Tick 级）
- **交易模式**: 半自动（策略生成信号 → 人工确认 → 执行）
- **目标导向**: 前期资金快速膨胀 · 高收益优先（赔率优先于胜率、集中持仓、非对称止盈）
