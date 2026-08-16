# AGENTS.md — 量化交易平台 (QuantTrade)

> 本文件为跨 AI 编码工具的统一指令源（Claude Code / Cursor / Codex CLI / Aider 等均支持）。
> Claude Code 专用扩展见 `CLAUDE.md`。

## 技术栈

| 层 | 技术 |
|:---|:---|
| 后端 | Python 3.8+ / FastAPI / SQLAlchemy 2.0 / PostgreSQL 14+ + TimescaleDB 2.10+ |
| 前端 | Vue 3 + TypeScript / Naive UI / ECharts 5 / Vite |
| 数据源 | Tushare Pro (主) + Baostock (辅) |
| 包管理 | pip (后端) / pnpm (前端) |

## 关键架构约束

- **依赖方向**: `modules/ → shared/ → core/`（严格单向，不可反向）
- **模块间通信**: 仅通过 EventEngine 异步事件，**禁止直接 import 其他模块**
- **事件命名**: `{module}.{domain}.{action}.{status}` 格式
- **Engine vs Service**: Engine 有状态（继承 EngineBase），Service 无状态纯计算
- **Repository**: 一表一仓库，继承 `BaseRepository`，纯数据访问不含业务逻辑

## 安全红线（不可违反）

- **`SIMULATED_TRADING=true`** 是开发环境安全总开关，**开发/测试环境不得设为 false**
- 禁止向 `.env`、`.git/`、凭证文件写入
- 禁止在主分支 (master/main) 上直接提交

## 开发流程

1. 编码前先输出《开发路径说明》（涉及文件 + 跨模块影响 + 验证方案），等用户确认
2. 仅修改规划内文件，不顺手重构无关代码
3. 禁止未经确认私自回退任何代码（git revert/reset/手动撤销）
4. 遇到信息缺失、计划偏差、需求变更 → 暂停并提交结构化报告，等待用户确认

## 文档索引

| 文档 | 用途 |
|:---|:---|
| `docs/量化交易平台方案设计.md` | 业务架构、流程链路、模块交互 |
| `docs/量化交易系统-混合架构设计.md` | 分层架构、目录结构、引擎/事件规范 |
| `docs/量化交易平台数据表设计.md` | 表结构、时序超表、Repository 编写 |
| `docs/sql/create_table.sql` | 建表 SQL（93 张表） |
| `docs/策略回测业务流程说明.md` | 回测流程、API 速查、信号链路 |

## 市场与交易模式

- **市场**: A 股（深交所 .SZ + 上交所 .SH）
- **频率**: 中低频，日线/周线级别（非高频/Tick 级）
- **交易模式**: 半自动（策略生成信号 → 人工确认 → 执行）
