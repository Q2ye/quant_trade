---
name: quantsys-architect
description: 量化交易系统架构师。当涉及模块架构设计、引擎开发、事件通信、数据库表设计、Repository规范、系统配置、启动流程时使用。策略开发请用strategy-dev skill。
---

# QuantSys Architect

> 策略开发 → 用 `strategy-dev` skill。本技能专注**架构层面**的决策与开发。

## 核心知识库

| 文档 | 回答什么 |
|:---|:---|
| `docs/01-业务设计/系统目标与投资哲学.md` | **系统目标唯一真相源**：前期资金快速膨胀期、目标区间、投资哲学 |
| `docs/01-业务设计/系统建设现状白皮书.md` | **代码现状基线**：模块/引擎/表/策略/前端/API 全部代码实证 |
| `docs/01-业务设计/量化交易系统详细设计.md` | 架构约束、启动流程、数据体系、策略体系、回测、实盘、开发规范 |
| `docs/01-业务设计/技术实现设计.md` | 引擎体系(22)/事件体系/API 契约(15 router)/Repository（以 `shared/database/repositories/` 目录为准） |
| `docs/00-核心策略体系/多策略整体架构规划.md` | 主+卫星双层资金架构、三条铁律、策略定位 |
| `docs/sql/create_table.sql` | 完整 DDL（表结构以此文件为准，21 张超表） |

## 架构层要回答的问题（S2 设计 / S3 拆分时用）

> 本技能不定义流程阶段：S1–S5、四档、确认点见 `docs/06-标准规范/00_交付流程总纲.md`。

1. **知识准备**：对照上表确定信息归属文档，浏览 `api/` `core/` `shared/` `modules/` 目录
2. **架构预检**：`shared/` `core/` 是否已有实现；依赖方向是否反向；是否需要事件通信
3. **落笔位置**：预检结论写进 `02-设计.md`（契约 / 影响面 / 依赖），不另起文档
4. **实施**：只改 `03-任务.md` 规划内文件，不顺手重构无关代码

## 核心架构速查

### 依赖方向（严禁反向）
```
modules/ → shared/ → core/
modules/ → utils/
api/ → shared/
```

### Engine vs Service
- **Engine**：有状态，继承 `EngineBase`，响应事件，协调 Service
- **Service**：无状态纯计算，不持有事件引擎引用

### 通信机制
- Service → Repository：同步直接调用
- 模块间：**仅通过 EventEngine 异步事件**，禁止直接 import
- 事件命名：`{module}.{domain}.{action}.{status}`

### 模块标准目录
```
modules/<name>/
  engines/  events/  services/  handlers.py
  managers/  schemas.py  models.py  tasks/  utils/  constants.py
```

### Repository 规范
一表一 Repository，继承 `BaseRepository`，纯 CRUD 不含业务逻辑。

### 代码模板
```python
from core.engines.base.engine_base import EngineBase
from core.events.base import BaseEvent

class XxxEngine(EngineBase):
    def __init__(self, event_engine, repository: XxxRepository):
        super().__init__(event_engine)
        self._repo = repository
        self._subscribe_events()

    def _subscribe_events(self):
        self.event_engine.subscribe(XxxEvent, self.handle_xxx)

    async def handle_xxx(self, event: XxxEvent) -> None:
        pass
```

## 优先复用开源库

- 技术指标：`ta-lib`、`pandas-ta`
- 数学计算：`numpy`、`scipy`
- 数据处理：`polars`、`pandas`
- 任务调度：`APScheduler`
- 核心自研：EventEngine、EngineBase、Repository 基类、API 网关

## 异常处理

遇到信息缺失/计划偏差/需求变更 → 立即暂停，提交结构化报告，等用户确认。禁止自行假设。
