---
name: quantsys-architect
description: 量化交易系统架构师。当涉及模块架构设计、引擎开发、事件通信、数据库表设计、Repository规范、系统配置、启动流程时使用。策略开发请用strategy-dev skill。
---

# QuantSys Architect

> 策略开发 → 用 `strategy-dev` skill。本技能专注**架构层面**的决策与开发。

## 核心知识库

| 文档 | 回答什么 |
|:---|:---|
| `docs/量化交易平台方案设计.md` | 业务流程、模块职责、数据同步方案、功能优先级 |
| `docs/量化交易系统-混合架构设计.md` | 代码架构、目录规划、事件定义、模块边界 |
| `docs/量化交易平台数据表设计.md` | 表结构、时序超表、Repository 编写 |
| `docs/sql/create_table.sql` | 完整 DDL（93 张表） |
| `docs/策略回测业务流程说明.md` | 回测流程、API 速查、信号链路 |

## 开发流程

1. **知识准备**：对照上表确定信息归属文档，浏览 `api/` `core/` `shared/` `modules/` 目录
2. **架构预检**：检查 `shared/` `core/` 是否已有实现；确认依赖方向不反向；确认事件通信需求
3. **输出《开发路径说明》**：涉及文件 + 跨模块影响 + 验证方案 + 风险点 → 等用户确认
4. **实施**：仅修改规划内文件，不顺手重构无关代码

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
