# 01 core 引擎基座审查报告

> 审查基准日期：2026-08-14（代码库 git 当前状态，未做任何修改）
> 审查文件清单：`quant_server/core/` 下 31 个 Python 源文件，共 18,348 行：
> engines/base/engine_base.py(2694)、engines/system/main_engine.py(1166)、engines/system/event_engine.py(851)、engines/system/engine_registry.py(730)、engines/utils/engine_monitor.py(1134)、engines/utils/engine_factory.py(927)、engines/types/enums.py(1596)、engines/types/entities.py(647)、events/system_events.py(574)、events/base.py(215)、events/engine_events.py(132)、events/types.py(229)、exceptions/event_exceptions.py(1229)、exceptions/handlers.py(928)、exceptions/security_exceptions.py(891)、exceptions/business_exceptions.py(860)、exceptions/error_codes.py(842)、exceptions/system_exceptions.py(417)、exceptions/base.py(306)、exceptions/middleware.py(298)、exceptions/types.py(302)、exceptions/auth_exceptions.py(285)、exceptions/validation_exceptions.py(269)、exceptions/__init__.py(296)、core/__init__.py(46) 及各子包 `__init__.py`（engines 192 / types 127 / events 60 / utils 57 / base 24 / system 24）
> 审查方式：只读；全文阅读 core/ 全部源文件 + grep 全库（quant_server/ 全部 .py）验证符号引用；对 main.py、modules/ 关键接线点做闭环核验（仅作引用证据，不在修改范围内）
> 严重度定义：高=功能失效/数据丢失/崩溃；中=部分失效/竞态/隐患；低=清理项/文档不一致

---

## 0. 审查方法说明

1. **静态全量阅读**：core/ 下 31 个文件全部逐行阅读（本报告行号引用均基于该阅读）。
2. **引用验证**：所有"死代码"结论均以 ripgrep 全库检索（`quant_server/**/*.py`）为依据，检索命中仅出现在定义文件与包 `__init__.py` 导出处的符号才判定为死代码；未完全核实的标注"待确认"。
3. **闭环核验**：事件"发布端 → 事件类型 → 订阅端"链路交叉比对（如 `EventType.SYSTEM_STARTED` 在 main_engine.py / main.py / websocket manager 三处的取值），并抽查 modules/ 中 60+ 处 `event_engine.put` 调用点的 await 与返回值处理。
4. **边界核验**：队列满、状态机非法转换、异常路径逐分支走查；对 `asyncio.Lock` 重入、`create_task` 无 loop、协程未 await 等 asyncio 陷阱逐一核对。
5. **未验证项**：运行期行为（如实际吞吐、内存曲线）未做动态测试；涉及 modules/、api/ 的间接引用未全部穷举，均标注"待确认"。

---

## 1. 业界对比分析

### 1.1 EventEngine 事件总线 vs 业界常见实现

**现状**（event_engine.py）：
- 自定义 `heapq` 优先级队列 + 多 worker 协程轮询消费（L175、L305-359），非 `asyncio.Queue`；
- 队列满时"按优先级丢弃/淘汰"（L462-501），`put()` 返回 `bool` 表示是否入队成功；
- 同事件多 handler 用 `asyncio.gather(..., return_exceptions=True)` 并行执行（L394-400）；
- 无批量消费、无 ack/重试、无监听器生命周期管理（订阅者无自动退订绑定）。

**业界做法**：
- 背压：`asyncio.Queue(maxsize=N)` + `task_done()/join()`，生产者在队列满时阻塞或显式选择丢弃并计数告警；Kafka/Redis Stream 类总线用 offset/ack 提供"至少一次/至多一次"语义；
- 批量消费：worker 一次性取多个事件（`get_many`）降低调度开销（高吞吐场景）；
- 异常隔离：handler 异常计入死信/重试队列，而不是与正常事件同队列丢弃；
- 监听器生命周期：订阅对象随组件 `start/stop` 注册/注销，防止悬垂引用与重复回调（vn.py 等量化框架均为此模式）。

**差距结论**：
1. **无背压**：`put()` 返回 False 即静默丢事件，而调用方大量不检查返回值（`modules/data/engines/sync_engine.py:716`、`modules/analysis/managers/analysis_manager.py:118` 等 60+ 处 put 调用均未处理返回值），生产高峰（Tushare 全市场同步）丢事件不可感知。建议：put 失败返回 False + 集中告警计数（dropped_events 已有统计字段），或对业务关键事件（trade/risk）改阻塞式 `put_wait`。
2. **无批量消费**：每 worker 每轮只取 1 个事件（L314-317），10 worker 场景吞吐受限。建议：`_get_event` 支持一次弹出 N 个后逐条处理，或按事件类型分队列。
3. **无 ack/重试**：事件处理失败仅计数（L408-412），无死信队列、无补偿。建议：失败事件进入重试队列（可复用 `RetryExceptionHandler` 思路，handlers.py:341-398），超过阈值进死信并告警。
4. **事件顺序不可靠**：优先级字符串比较（见 3.9），且 10 worker 并发消费天然乱序——对"订单提交→成交回报"类因果事件序列无保障（业界用单消费者/分区键保证顺序）。建议：为 `correlation_id` 相同的事件做顺序路由（同 correlation 固定 worker）。

### 1.2 EngineBase 生命周期 vs 状态机最佳实践

**现状**（engine_base.py）：`EngineStatusValidator` 维护显式状态转换表（L84-108）+ 转换钩子 + 转换历史（L215-274）；`initialize/start/stop/restart/pause/resume` 模板方法（L926-1580）；状态变更集中在 `record.update_status`。

**业界做法**：状态机库（transitions/stateless）或显式 FSM，强调三点：①转换原子性（进入/退出动作 + 失败回滚到原状态）；②幂等（stop 多次调用安全）；③并发防护（状态锁 + 转换中拒绝重入）。

**差距结论**：
1. **stop 失败状态卡死**：`stop()` 内非 `TimeoutError/RuntimeError` 异常（L1394-1401）只 `record_error` 后 `raise`，状态停留在 `STOPPING`，后续无法再 stop/start（状态机不允许 STOPPING→STARTING）；应回滚到 `RUNNING` 或置 `ERROR`。
2. **resume 后监控循环永久终止**：`_monitoring_loop` 以 `while status == RUNNING` 为条件（L1799），`pause()` 将状态改为 `PAUSED` 后循环退出，`resume()` 只改状态（L1551）不重建监控任务 → 恢复后健康检查/指标采集停摆。
3. **start 重试无副作用回滚**：`_on_start()` 成功后若后续步骤（监控任务创建、后台任务启动、事件发布）抛错进入重试（L1096-1231），已启动的子资源不清理——`EventEngine._start_workers`（event_engine.py:250-255）第二次调用会再建 10 个 worker，`_worker_tasks` 累积翻倍。
4. **信号处理器重复注册**：每个 EngineBase 实例构造时都 `signal.signal(SIGINT/SIGTERM)`（L866、L2396-2412），后创建实例覆盖前者，仅最后实例响应；且信号回调里 `asyncio.create_task`（L2404）在事件循环未运行时直接抛 `RuntimeError`。业界做法：由进程级入口统一注册一次，引擎仅提供 shutdown 协程。

### 1.3 异常体系设计

**现状**：`QuantBaseException` 分层（base.py:71）+ `ErrorCode` 枚举（error_codes.py:20）+ 全量异常类约 100 个（business/security/event/validation/system/auth 六个文件）+ `ExceptionMiddleware`（middleware.py:24）+ handler 链（handlers.py:31-795）。但 **EventEngine 实际只抛 `RuntimeError`**（event_engine.py:455），队列满返回 False 而非异常。

**业界做法**：异常层次 2-3 层即可（基类 → 分类 → 具体），错误码全局唯一且集中映射 HTTP 状态码；框架层（事件总线）抛统一基础设施异常，由集中 handler 转 HTTP/告警；不使用的异常类不应长期保留（会腐化为维护负担）。

**差距结论**：
1. **异常体系与实现脱节**：`event_exceptions.py`（1229 行，28 个类 + 6 个函数）业务代码零引用（仅自身与 `__init__.py` 引用），事件引擎真实失败路径用的是 `RuntimeError`/`bool` 返回值——要么引擎接入该体系，要么删除。
2. **错误码不唯一**：`AUTHORIZATION_ERROR_OLD="5001"` 与 `SECURITY_CONFIG_ERROR="5001"` 撞值（error_codes.py:105、157），`ErrorCode("5001")` 反解歧义；`RESOURCE_NOT_FOUND` 与 `NOT_FOUND` 同值 "1006"（L49-50）；`base.py` 的 `to_api_exception` 状态码映射硬编码字符串（L158-166）与枚举定义漂移（"5000" 实为 `SECURITY_ERROR` 却被注释为 AUTHENTICATION_ERROR→401）。
3. **中间件未接线**：`setup_exception_middleware`/`ExceptionMiddleware` 无调用者（grep 仅定义与导出），FastAPI 层异常响应是否复用此体系待确认（api 层可能有自己的 exception handler）——两套体系并存则响应格式不一致。

### 1.5 事件模型与序列化

**现状**（events/base.py）：`BaseEvent` 为 ABC + `EventMetadata` dataclass（L22-68），事件数据放 `self.data` 字典（L125），提供 `to_dict/to_json/from_dict/from_json`（L161-206）与 `mark_processing/mark_processed` 状态标记（L150-159）；`EventMetadata.priority` 类型注解为 `int`（L30）但实际存放 `EventPriority`（IntEnum）成员。

**业界做法**：事件模型多用 pydantic（校验 + 序列化 + 版本化）或冻结 dataclass + typed `data` 字段；事件 schema 随版本演进有兼容策略；追踪字段（trace_id/span_id/correlation_id）由框架自动注入而非调用方手传。

**差距结论**：
1. `data` 为无类型 `Dict[str, Any]`，订阅方靠约定取值，无 schema 校验（`EventValidationError` 已定义但未接入）；建议关键事件（trade/risk）引入 pydantic 或 `__post_init__` 校验；
2. `from_dict` 对 `EventPriority` 反序列化：`metadata.priority` 存 int 值，`EventMetadata.from_dict`（L60）直接 `data.get("priority")` 返回 int，与注解 `int` 一致但与 IntEnum 成员混用——正是 3.9/3.10 优先级混乱的源头之一；
3. `trace_id/correlation_id` 无自动注入点（发布方需手传），分布式追踪链路实际未启用（grep 无 span 注入代码）；
4. `TypedEvent`（base.py:217-227）与 `T/E` 类型变量（L231-232）为占位，无任何子类使用——死代码。

### 1.4 主引擎加载与拓扑排序

**现状**：模块拓扑排序在 `main.py:_sort_modules_by_dependency`（DFS，main.py:721-760）串行加载模块 `initialize`；`MainEngine._start_registered_engines` 对注册引擎 **并行 `asyncio.gather` 启动**（main_engine.py:627-635），无拓扑序；`EngineFactory._sort_engines_by_dependency`（engine_factory.py:811-870）仅用于 shutdown 逆序。

**业界做法**：引擎按依赖图分层串行/并行启动（依赖先就绪），启动失败则中止或降级并回滚已启动组件；启动顺序应显式可观测（日志输出排序结果）。

**差距结论**：
1. 引擎启动顺序无显式拓扑——依赖引擎靠 `_resolve_dependencies`（engine_factory.py:781-809）在创建时"按需顺带创建启动"，顺序隐式且难以预测；与 CLAUDE.md 文档"MainEngine 按拓扑排序加载"表述不符（实际排序在 main.py 模块层，引擎层是并行 gather）。
2. 子引擎启动失败仅记日志（main_engine.py:677-679 返回 False），主引擎照常 RUNNING → 半启动状态无告警升级。
3. 引擎实例存在双注册路径：`MainEngine._start_child_engine` 用 factory 创建占位引擎（PlaceholderEngine，engine_factory.py:354-387），随后模块 `initialize()` 又把真实引擎塞进 `_module_engines`（main_engine.py:872-879）→ 同一模块可能同时存在占位引擎与真实引擎，`get_engine` 查询路径分裂（L849-870 依次查三处）。

---

## 2. 死代码清单

> 以下均经 grep 全库验证（quant_server/ 全部 .py；列"仅自身/__init__"表示除定义文件和包导出外无任何引用）。

| 位置(文件:行) | 类型 | 说明 | 清理建议 |
|---|---|---|---|
| exceptions/auth_exceptions.py 整文件(1-285) | 整模块死代码 | 6 个类（AuthenticationException/AuthorizationException/TokenException/PermissionException/RateLimitException/SessionException）仅文件内出现；且 AuthenticationException 等与 security_exceptions.py 同名重复 | 删除整个文件，或并入 security_exceptions.py 后删 |
| exceptions/event_exceptions.py 整文件(1-1229) | 整模块死代码 | 28 个异常类 + 6 个工厂/判定函数仅被自身与 exceptions/__init__.py 引用；EventEngine 实现未使用其中任何一类（实际抛 RuntimeError） | 保留公共基类 EventException，其余删除或留待事件引擎接入时再引入 |
| business_exceptions.py:691-733 ValidationException | 重复定义 | 与 base.py:186 同名重复，且未导出（__init__.py 从 base 导入） | 删除此类，统一用 base.ValidationException |
| business_exceptions.py:181,265,307,349,391,479,563,605,647,97,139,223,521,437 等细分异常（RiskException/PortfolioException/OrderException/PositionNotFoundException/InsufficientBalanceException/MarketException/ExecutionException/SettlementException/AnalysisException/BacktestException/AccountException/TradeException/DataException…） | 低引用 | 全库仅 BusinessException（handlers.py 等 20+ 处）与 OrderException（trade_instruction_repo.py:22,697）被使用，其余 12 个细分异常零引用 | 保留高频使用的 BusinessException/OrderException，其余待确认模块层引入后再保留，否则删除 |
| events/system_events.py:179,226,314,356,393,437,488（SystemHeartbeatEvent/SystemAlertEvent/SystemConfigChangedEvent/ModuleStartedEvent/ModuleStoppedEvent/ServiceHealthChangedEvent/ResourceLimitWarningEvent） | 类死代码 | 仅定义与 events/__init__.py 导出；无发布者亦无订阅者（SystemStartedEvent/SystemStoppedEvent 被 main.py:791,822 使用，ReportGeneratedEvent 被 report_tasks.py 使用） | 删除或接入心跳/告警发布链路（与 5.2 事件命名统一后） |
| events/system_events.py:151-176, 304-311, 426-434, 477-485（_generate_sequence/_calculate_health/_determine_change_type/_is_improvement/_generate_recommendation） | 私有辅助函数死代码 | 随宿主死事件类一并死亡 | 随宿主类删除 |
| events/types.py:188-217 CommonEventTypes、220 EventFilterFunc | 类/占位符死代码 | 全库无引用（各模块自建 DataEventType/StrategyEventType 等枚举） | 删除；EventFilterFunc 为 `Any` 占位无价值 |
| events/types.py:123-184 EventType.parse/get_module/get_domain/is_system_event/is_business_event | 方法死代码 | 全库无引用（仅类内互相调用） | 删除或待接入日志/追踪时使用 |
| engines/types/entities.py:186-558（Order/Trade/Position/Account/StrategyConfig/StrategyStatusEntity/Signal/MarketData/TickData/BarData/DepthData/RiskRule/RiskAlert/Metric/Alert/SystemConfig/ConfigItem/EngineHealthInfo/SystemStatus/MonitorStatus/EngineMonitorRecord） | 实体类死代码 | 项目数据层用 SQLAlchemy models + 模块自有 schema，全库无引用；仅 EngineConfigEntity(123)/EngineMetricsEntity(153) 被 engine_base 使用 | 保留 EngineConfigEntity/EngineMetricsEntity，其余删除（含 EntityFactory 561-647） |
| engines/types/entities.py:561-647 EntityFactory | 工厂类死代码 | 全库无调用 | 删除 |
| engines/types/enums.py:791-802 EventPriority、805-855 EventType | 枚举死代码（与 events/types.py 同名双轨） | 全库无引用（模块事件枚举用 events/types.py 的 EventPriority）；main_engine.py:175 引用的 EventType 仅取 SYSTEM_STARTED/SYSTEM_STOPPED 两个值 | 删除或与 events/types.py 合并，杜绝双轨（见 5.2） |
| engines/types/enums.py:940-1370（MarketType/OrderType/TimeInForce/StrategyType/SignalType/DataFrequency/DataSource/DataQuality/RiskLevel/RiskAction/RiskType/AccountType/PositionDirection/SettlementStatus/AlertLevel/MetricType/CheckType/DatabaseType） | 枚举死代码（待确认） | 未在 quant_server 检索到引用（部分可能在 modules/ 待确认） | 按模块实际使用清理，未用删除 |
| engines/types/enums.py:1394-1512 EnumHelper/get_enum_values/get_enum_from_value | 辅助类/函数死代码 | 全库无引用 | 删除 |
| engines/utils/engine_factory.py:130-137 _do_pause/_do_resume | 空桩函数 | 无任何调用 | 删除 |
| engines/utils/engine_monitor.py:1093-1134 get_engine_monitor/start_monitoring/stop_monitoring | 便捷函数死代码 | 无调用者（main_engine 直接用 EngineMonitor 实例） | 删除或改为工厂注入模式 |
| engines/utils/engine_monitor.py:993-1086 generate_report | 方法死代码（待确认） | 未检索到 API/模块调用 | 待确认；未用则删除 |
| engines/system/engine_registry.py:485-522 search_engines、437-483 get_engines_by_tag/status/health/type | 查询方法死代码 | 全库无调用；update_engine_indexes(342-384) 亦无调用者（索引永不过期，见 5.9） | 删除或接入状态变化订阅 |
| engines/system/event_engine.py:648-711 register_general/unregister_general、828-897 reset_statistics/get_event_history/get_handler_info | 方法死代码 | 全库无外部调用（仅 event_engine 内部定义） | 删除，或由监控/API 消费统计时接入 |
| engines/system/event_engine.py:113-137 EventStatistics.reset | 方法半死代码 | 仅 reset_statistics 调用，而 reset_statistics 无外部调用者 | 随 reset_statistics 一并处理 |
| engines/base/engine_base.py:1969-2037 _handle_event/_handle_engine_command/_handle_config_update | 死代码路径 | 无人订阅/发布 "engine_command"、"config_update" 事件类型 → 永不触发 | 删除或接命令通道 |
| engines/base/engine_base.py:747-768 EngineMetricsUpdater.update_metrics | 通用方法死代码 | 其余 8 个 update_* 被 engine_base 使用，update_metrics 无调用 | 删除 |
| engines/base/engine_base.py:140-213 EngineStatusValidator.register_transition_hook/execute_transition_hooks(hook 注册侧) | 半死代码 | 钩子执行被生命周期调用，但 register_transition_hook 无外部注册者 → hooks 恒为空 | 保留框架或删除钩子机制 |
| engines/base/engine_base.py:2565-2644 with_retry、2519-2563 safe_context | 方法死代码（待确认） | 全库无外部调用 | 待确认模块层使用；未用删除 |
| engines/system/main_engine.py:1121-1159 get_main_engine/initialize_system、1162-1166 shutdown_system | 模块级函数死代码 | initialize_system/shutdown_system 无调用者；get_main_engine 与 api/dependencies/main_engine.py 同名实现遮蔽，core 版无引用 | 删除或统一为 api 依赖层实现 |
| security_exceptions.py:805 create_security_exception | 工厂函数（待确认） | 仅 __init__.py 导出 | 待确认；未用删除 |
| engines/__init__.py / exceptions/__init__.py 大而全的导出面 | 导出面膨胀 | 导出大量未使用符号（如 auth_exceptions 类、事件异常类），import 成本与误用风险高 | 导出面与存活符号对齐 |

---

## 3. 边界情况清单

| 位置 | 触发场景 | 现状行为 | 风险等级 | 修复建议 |
|---|---|---|---|---|
| event_engine.py:462-501 | 队列满时 put CRITICAL 事件 | `put()` 用 `getattr(event, 'priority', ...)` 取优先级，而 BaseEvent 只有 `metadata.priority` 无 `.priority` 属性 → 恒得 NORMAL → `priority<=2` 不成立 → **CRITICAL 事件也被直接丢弃**，与注释宣称的"高优先级强制插入"相反 | 高 | 统一从 `event.metadata.priority`（events/types.EventPriority）取值并映射到淘汰判定；或为 BaseEvent 增加 `priority` property |
| event_engine.py:38-64, 503-507 | 事件入队排序 | `QueuedEvent.priority` 取 `metadata.priority.name.lower()` 字符串，heapq 按字母序比较："background" < "critical" < "high" < "low" < "normal" → **BACKGROUND 事件最先被处理**，与 PriorityLevel"数值越小越紧急"语义相反（events/types.EventPriority 与 enums.PriorityLevel 两套语义并存且相反） | 高 | 排序字段改为数值（PriorityLevel.get_priority_value 或 EventPriority int），时间戳做次键；并收敛两套优先级枚举 |
| event_engine.py:57, 477-481 | dict 事件携带 int 型 metadata.priority（EventPriority IntEnum 值 10-100） | 堆中 int 与 str 混插 → `heapq` 比较抛 `TypeError` → worker 进异常循环 sleep(0.1)（L322-324），该事件及后续事件卡死 | 中高 | 入队前统一将 priority 归一化为同一类型数值 |
| event_engine.py:607-616, 629-646 | 注册/注销与 put 并发 | register/unregister 用 `asyncio.create_task` 异步执行（fire-and-forget）：①先 put 后注册任务执行 → 事件被"无处理器"丢弃；②无运行 loop 的同步上下文调用直接 RuntimeError；③unregister 返回 True 但实际可能未执行 | 中高 | 注册改为同步写（单线程事件循环内加锁操作即可，无需 create_task）；unregister 返回实际结果 |
| event_engine.py:569-616 | 同一 handler 重复订阅同一事件 | register 无去重：重复订阅 → 同事件执行多次；无订阅上限 | 中 | 以 (event_type, handler/handler_id) 去重或幂等返回既有 id |
| event_engine.py:442-455 | 引擎停止/停止中调用 put | 非 RUNNING 状态直接抛 RuntimeError；停止窗口内生产者（后台线程 bridge）异常刷屏 | 中 | 停止期 put 返回 False + 告警，或提供 is_running 前置检查 |
| event_engine.py:742 | `_create_timer` 同步回调 | `run_in_executor(None, callback, ())` 把空元组当参数传给回调 → 无参同步回调抛 TypeError（当前仅 `_update_statistics` async 回调未暴露） | 中 | 改为 `run_in_executor(None, callback)` |
| engine_base.py:1394-1401 | stop() 中 `_on_stop` 抛非 Timeout/RuntimeError 异常 | 只 record_error 后 raise，**状态停留在 STOPPING**，后续 stop/start 均被状态机拒绝 | 高 | except 分支统一置 ERROR（或回滚 RUNNING）后再 raise |
| engine_base.py:1096-1231 | start() 重试（EventEngine._on_start 二次执行） | 无副作用回滚：`_start_workers` 再次创建 10 个 worker，`_worker_tasks` 翻倍（event_engine.py:250-255 只 append 不清理） | 高 | 重试前调用清理钩子（先 stop 已启动部分）；或 _start_workers 幂等 |
| engine_base.py:1253-1257 | stop() 幂等 | STOPPED 状态直接返回 True，幂等 OK；但 stop 后 `shutdown_event` 不 clear，restart 才 clear（L1427）——直接 start() 会命中 `_monitoring_loop` 的 `shutdown_event.is_set()` 提前退出（L1805） | 中 | start() 时统一 clear shutdown_event/pause_event |
| engine_base.py:2396-2412 | 多引擎实例创建 | 每个实例重复 `signal.signal(SIGINT/SIGTERM)`，后注册覆盖先注册 → 仅最后引擎响应；信号回调中 `asyncio.create_task` 在 loop 未运行时抛 RuntimeError | 中 | 进程级统一注册一次信号，分发到各引擎 shutdown |
| engine_base.py:1491-1495, 1799 | pause→resume 后 | `_monitoring_loop` 随状态 PAUSED 退出，resume 不重建 → 监控循环永久停止 | 中 | resume() 中重建 monitoring_task；或循环条件改为 pause_event 驱动 |
| engine_base.py:105-106, 100-105 | 同步 handler 在 run_in_executor 中执行 | 每次事件调度进默认线程池，handler 内 `call_count += 1`（L97）跨线程无锁；高并发下计数失真 | 低 | 统计改为事件循环内更新，或接受近似值 |
| engine_factory.py:445-545, 781-809 | 引擎循环依赖（A 依赖 B，B 依赖 A） | `create_engine` 持 `self._lock` 期间递归 `_resolve_dependencies → create_engine` 再取同一把 asyncio.Lock（不可重入）→ **死锁**；`_creating_engines` 集合仅保护 event_engine | 中高 | 依赖解析在锁外执行，或 create_engine 内释放锁后再解析依赖；依赖图先做环检测 |
| engine_factory.py:537-542 | create_engine 启动失败 | 仅从 `_engine_instances` 删除实例，不停止已启动部分、不从 registry 注销 | 中 | 失败时反向清理（stop + unregister） |
| engine_factory.py:59 | EngineDescriptor.category 默认值 | `category: EngineCategory = EngineCategory`（默认值是类而非枚举成员），未显式传 category 的描述符 `to_dict()` 会 AttributeError | 中 | 默认值改为 EngineCategory.CUSTOM |
| main_engine.py:921 | get_all_engines 遍历 factory | `self._engine_factory.get_engine(name)` 是 async 方法却**未 await** → 列表里是 coroutine 而非引擎 | 中 | 补 await |
| main_engine.py:62-92, 133-138 | 单例重建/并发构造 | `MainEngine.__new__` 单例 + `_initialized` 防重入，但 `_lock` 是类属性 asyncio.Lock（绑定首个 loop），测试/热重启场景实例不重置 | 低 | 提供 reset 或按 loop 重建机制 |
| event_engine.py:458-459, 515 | `dropped_events` 统计字段 | 未在 EventStatistics 定义，运行时动态挂载；`reset()` 不重置该字段 | 低 | 在 dataclass 中显式声明并加入 reset |
| event_engine.py:76, 93 | `EventHandler.enabled` 字段 | 字段存在且 `call()` 检查（L93）但全库无禁用/启用入口（无 set_enabled 方法） | 低 | 增加 toggle 方法或删除字段 |
| event_engine.py:53-61 | dict 事件 priority 取值 | dict 事件 `metadata.priority` 若为 EventPriority IntEnum（int 值），`self.priority` 存原始 int，与字符串混入堆 → TypeError（同 3.10）；且队列满淘汰逻辑对 dict 事件同样失效（getattr 取不到） | 中高 | 统一 priority 归一化函数，dict/BaseEvent 共用 |

---

## 4. 性能问题清单

| 位置 | 问题 | 影响 | 优化建议 |
|---|---|---|---|
| event_engine.py:342-359 | **忙碌轮询**：`_get_event` 每 10ms `sleep(0.01)` 轮询队列；10 个 worker → 约 1000 次唤醒/秒空转 | CPU 空转、事件延迟 0-10ms 抖动 | 改用 `asyncio.Condition`/`asyncio.Queue` 阻塞获取，或 `loop.create_future` + put 时唤醒 |
| event_engine.py:184, 377 | `_event_history` 保存全部事件对象（maxlen=10000），每事件一次 append | 内存峰值 ~1 万事件对象引用；大 data 事件放大内存 | 仅保存轻量摘要（type/ts/id）或按类型采样 |
| event_engine.py:380-391 | 每事件：复制 handlers 列表 + `sort(key=priority)` | 高吞吐时每事件 O(n log n) | 订阅时维护有序列表，消费时直接遍历 |
| event_engine.py:100-105, 742 | 同步 handler 每次 `run_in_executor`（默认线程池） | 线程调度开销 + 默认池无界 | 预建固定线程池并复用 |
| event_engine.py:457-515 | `put`/`_get_event` 每事件获取 `asyncio.Lock`，且 put 内队列满时 O(n) 扫描找最低优先级（L474-486） | 锁与 O(n) 扫描叠加，满队列时退化 | 用 `asyncio.Queue` 或维护最低优先级索引；减少临界区内扫描 |
| event_engine.py:442-545 | `put` 内两处 logger（L524-525/539-540）在加锁后执行 | 锁内做字符串拼接与日志 I/O，拖长临界区 | 日志移到锁外 |
| engine_monitor.py:759-772 | `_active_alerts` 只清理已解决且超 7 天的警报；未解决警报永不清理 | 引擎持续不健康时每冷却周期（60-300s）新增一条警报，字典无界增长 | 按时间上限清理未解决警报（或合并去重同规则警报） |
| engine_monitor.py:555-580 | 每 5s 对所有引擎 `get_status_info()` 全量序列化（含 record.to_dict、metrics） | 引擎多时监控开销线性放大 | 增量采集/缓存状态 |
| engine_base.py:1873-1918 | `_collect_system_metrics` 每周期 `process.cpu_percent(interval=0.1)` 阻塞 0.1s + psutil 调用 | 监控循环内阻塞事件循环 0.1s/引擎/周期 | 异步化或降低频率 |
| engine_registry.py:634-670 | 引擎状态/健康变化不触发索引更新（update_engine_indexes 无调用者）→ `_status_index` 长期 stale | 查询 API 返回过期状态 | 在 record.update_status 后回调刷新，或查询时实时计算 |
| main_engine.py:627-635 | 引擎并行 gather 启动，无依赖分层 | 依赖引擎未就绪时 `_check_dependencies`（engine_base.py:1649-1676）抛 RuntimeError 触发重试退避（重试 3 次×指数退避）→ 启动时间被拉长 | 按拓扑分层启动 |
| engine_base.py:1132-1138 | 每引擎一个 `_monitoring_loop` 任务，所有引擎各自轮询 psutil/健康检查 | 引擎数量×周期 的任务数，事件循环任务膨胀 | 合并为统一监控器（EngineMonitor 已存在，双轨） |

---

## 5. 业务闭环与 bug 清单

| 位置 | 问题描述 | 严重度(高/中/低) | 修复建议 |
|---|---|---|---|
| main.py:791-799 + main_engine.py:174-182 + enums.py:814 | **SystemStartedEvent 时序/类型分裂**：同一"系统启动"产生两种事件——main.py lifespan 发 `SystemStartedEvent`（"system.started"），MainEngine._on_start 发 EngineLifecycleEvent（"engine.system_started"）；websocket manager 只映射点式 "system.started"（api/websocket/manager.py:61-64） | 高 | 统一事件类型常量表，MainEngine 停止自发布 system 事件，改由 main.py 单点发布 |
| main_engine.py:511-522, 762-771 | **main_engine 注册的三个事件类型无发布者**："system_health_check"/"engine_status_changed"/"system_alert"（下划线式）全库无人 put；且 `_handle_system_health_check(self)` 无 event 参数（L762），EventHandler.call 会传 event → 即使触发也 TypeError；该 handler 还把 `_system_status` 用 SYSTEM_STARTED 类型发布（L771，语义错误） | 高 | 删除这三个注册与 handler，或统一为模块实际使用的事件类型（monitor.system.health.changed 等） |
| engine_base.py:1922-1940 + sync_engine.py:705-722 | **EngineBase._publish_event 事件类型前缀污染**：`lifecycle_stage=event_type.replace("engine_","")` 把业务事件类型当 stage 用 → 事件类型变成 "engine.data.sync.started"；订阅方订阅 "data.sync.started" 永远匹配不上（sync_engine 已发现并"双发"补丁 L712-722） | 高 | EngineLifecycleEvent 构造改为独立 stage 参数；或业务引擎不用 _publish_event 而直接 put 规范事件 |
| integration_service.py:127, 205, 293 | **调用不存在的 API**：`self.event_engine.publish(...)` —— EventEngine 只有 `put`，无 `publish` → AttributeError（分析完成/风险分析/归因分析事件路径必崩） | 高 | 改为 `await self.event_engine.put(...)` |
| risk_engine.py:358, 374 + risk_manager.py:150 | **async put 未 await**：同步方法中 `self.event_engine.put(...)` 不 await → 返回 coroutine 被丢弃，**风险事件永不入队** | 高 | 补 await（方法改 async）或提供同步 put 入口 |
| main.py:524-529 + sync_tasks.py:73-83, 148-167 | **get_event_engine() 与工厂脱节**：main.py 直接 `EventEngine(event_config)` 创建，未注册进 EngineFactory 单例 → `get_event_engine()`（event_engine.py:921-931 经 factory.get_engine）返回 None；且 sync_tasks.py:73 等同步函数调用 async `get_event_engine()` 未 await（拿到 coroutine 再 `.put` → AttributeError） | 高 | 事件引擎创建后注册进 factory（或 factory.set_event_engine）；task 侧 await 并判空 |
| engine_factory.py:761-779 | `_get_shared_event_engine` 依赖实例名 "event_engine" 在 factory 缓存中，否则返回 None → 子引擎 event_engine=None，_publish_event 静默跳过（engine_base.py:1930） | 高 | MainEngine._initialize_core_components 显式 `initialize_factory(event_engine=..., engine_registry=...)` |
| main_engine.py:849-870 | get_engine 三处查询（_module_engines → factory → registry）状态分裂：同一引擎可能同时存在占位实例与真实实例 | 中 | 收敛为单一注册来源（registry），其余为只读缓存 |
| engine_registry.py:342-384 | update_engine_indexes 无调用者 → 状态/健康索引永不刷新，`get_engines_by_status/health` 返回过期集合 | 中 | 在 EngineRecord 状态变更时同步索引，或查询实时计算 |
| engine_monitor.py:425-458, 1103-1116 | `_init_dependencies`/`get_engine_monitor` 用 `hasattr(factory, 'engine_registry')` 探测——EngineFactory 只有私有 `_engine_registry`/`_event_engine`，无公有属性/方法 → 探测恒 False，monitor 拿不到注册表与事件引擎 | 中 | 增加工厂公有访问器，或在 MainEngine 注入 |
| main_engine.py:206-371 | **依赖方向违规**：core 层 MainEngine 直接 import modules（DataSyncService、settlement_tasks、composite_service、ScheduleManager），违反 AGENTS.md"modules/ → shared/ → core/ 单向依赖" | 中 | 日终调度下沉到 system 模块/独立 scheduler 模块 |
| error_codes.py:105,157, 49-50 | 错误码撞值："5001" 双义（SECURITY_CONFIG_ERROR vs AUTHORIZATION_ERROR_OLD）、"1006" 双义（NOT_FOUND vs RESOURCE_NOT_FOUND）→ 反解/HTTP 映射错乱 | 中 | 错误码全局唯一校验（启动时断言），移除 _OLD 别名或改独立段 |
| main_engine.py:734-760, 980-987 | `_publish_system_event` 用 enums.EventType 值（"system_started"）拼 "engine.system_started"；`broadcast_message` 枚举外消息类型被静默降级为 SYSTEM_STARTED 事件（L984） | 中 | 统一事件类型命名（点式），移除降级分支 |
| main_engine.py:762-771 | `_handle_system_health_check` 发布 SYSTEM_STARTED（语义错误：健康检查响应 ≠ 系统启动） | 中 | 改发布 health 事件类型 |
| modules/monitor/engines/alert_engine.py:74-85 | alert_engine 订阅 "monitor.risk.alert.triggered" 等点式事件，与 core 层下划线命名（"system_alert"）不互通 | 中 | 事件命名统一规范（{module}.{domain}.{action}.{status}）并全库校对 |
| main.py:871-878 | `_shutdown_modules` 对 async `module.shutdown()` 未 await（inspect 分支只调用不 await）→ 模块异步关闭逻辑不执行 | 中 | `await module.shutdown()` |
| data/engines/sync_engine.py:337-339, 394-406 | 订阅 "system.heartbeat"，但全库无心跳发布者（main_engine/monitor 均未发 system.heartbeat）→ 死订阅 | 低 | 接心跳发布链路或删除订阅 |
| main_engine.py:584-586 + engine_factory.py:460 | MainEngine 直接构造 `EngineFactory()` 不调 `initialize_factory`，依赖 singleton 先前状态，初始化顺序脆弱 | 中 | 显式初始化并注入依赖 |
| engine_base.py:371-408, 458-484 | record 的 health/error/性能历史写入 metadata 字典无锁（多协程并发 update 时字典追加非原子） | 低 | 状态类更新集中在状态锁内 |
| event_engine.py:442-455 | 引擎停止期间 put 抛 RuntimeError，调用方未捕获（如模块线程 bridge）→ 线程异常日志刷屏 | 中 | put 停止期返回 False + 告警，或提供 is_running 前置检查 |
| strategy/events/management_events.py:98-129 StrategySignalEvent | 与 signal_events.py:13 同名重复定义（事件类型不同：StrategyEventType.SIGNAL_GENERATED vs SignalEventType.ENTRY），全库无引用 | 低 | 删除重复类 |

---

## 6. 严重度汇总表（Top 20，跨 5 维度按严重度排序）

| # | 严重度 | 维度 | 位置 | 问题摘要 | 修复方案摘要 |
|---|---|---|---|---|---|
| 1 | 高 | 边界 | event_engine.py:462-501 | 队列满时 BaseEvent 无 `.priority` 属性，CRITICAL 事件按 NORMAL 处理被丢弃 | put 从 `metadata.priority` 取优先级统一映射 |
| 2 | 高 | 性能/正确 | event_engine.py:38-64 | QueuedEvent 字符串优先级字母序排序，BACKGROUND 最先处理（优先级反转） | 排序键改数值（get_priority_value） |
| 3 | 高 | 业务闭环 | integration_service.py:127,205,293 | 调用不存在的 `event_engine.publish` → AttributeError | 改 `await put` |
| 4 | 高 | 业务闭环 | risk_engine.py:358,374; risk_manager.py:150 | async `put` 未 await，风险事件永不发布 | 补 await 或提供同步 put |
| 5 | 高 | 业务闭环 | engine_base.py:1922-1940 | `_publish_event` 把业务类型拼成 "engine.data.sync.started"，订阅匹配断裂（sync_engine 双发补丁） | 独立 stage 参数，业务事件直发 put |
| 6 | 高 | 业务闭环 | main_engine.py:511-522,762 | 三个下划线事件类型无发布者 + handler 签名缺 event 参数 | 删除或统一为模块实际事件类型 |
| 7 | 高 | 边界 | engine_base.py:1394-1401 | stop 非标准异常卡 STOPPING，无法再启停 | except 分支置 ERROR/回滚 RUNNING |
| 8 | 高 | 边界 | engine_base.py:1096-1231 | start 重试无回滚，EventEngine 重复启动 worker | 重试前清理副作用，_start_workers 幂等 |
| 9 | 高 | 业务闭环 | main.py:524 + sync_tasks.py:73 | EventEngine 未入 factory，get_event_engine() 返回 None/未 await coroutine | 注入 factory + 调用方 await/判空 |
| 10 | 高 | 边界 | engine_factory.py:445,512,781 | 循环依赖时 create_engine 持锁递归 → 死锁 | 依赖解析移出锁，先做环检测 |
| 11 | 中高 | 边界 | event_engine.py:607-646 | register/unregister fire-and-forget 竞态，先 put 后注册丢事件 | 注册同步化，unregister 返回真实结果 |
| 12 | 中高 | 边界 | event_engine.py:57,477-481 | 堆内 int/str 混合优先级比较 TypeError，worker 卡异常循环 | 入队统一归一化 priority |
| 13 | 中 | 业界对比 | engine_base.py:1799,1551 | resume 后监控循环永久停止 | resume 重建 monitoring_task |
| 14 | 中 | 边界 | engine_base.py:2396-2412 | 每引擎重复注册 SIGINT/SIGTERM 互相覆盖 | 进程级统一注册一次 |
| 15 | 中 | 业务闭环 | main_engine.py:921 | get_all_engines 未 await factory.get_engine，装入 coroutine | 补 await |
| 16 | 中 | 业务闭环 | engine_registry.py:342 | 状态/健康索引无刷新入口 | 状态变更时同步索引 |
| 17 | 中 | 业界对比 | error_codes.py:105,157,49 | 错误码 "5001"/"1006" 撞值，反解歧义 | 错误码唯一性启动校验 |
| 18 | 中 | 业务闭环 | main_engine.py:174 + enums.py:814 + system_events.py:21 | 事件类型三轨命名（点式/下划线/engine.前缀），闭环断裂 | 统一点式命名 + 全库校对 |
| 19 | 中 | 业务闭环 | engine_monitor.py:438-456 | hasattr 探测工厂公有属性恒 False，monitor 依赖缺失 | 工厂加公有访问器并注入 |
| 20 | 中 | 死代码 | exceptions/auth_exceptions.py、event_exceptions.py 等 | 约 3000+ 行异常体系死代码 + entities.py 实体死代码 | 按引用清单删除/合并（见第 2 章） |

---

## 7. 修复优先级建议与执行顺序

1. **第一优先（阻断性，功能失效/数据丢失）**：第 6 章 #1-#10。
   - #1/#2 事件优先级双轨（一个 PR 一并修复：统一 priority 归一化函数，put/QueuedEvent/淘汰逻辑共用）；
   - #3/#4 补 publish→put、补 await（涉及 modules/，需跨模块改动，先小步灰度）；
   - #5/#6 事件类型闭环（engine_base 的 _publish_event 签名改造 + main_engine 死注册清理）；
   - #7/#8 状态机异常回滚与 start 幂等；
   - #9/#10 事件引擎注入 factory、依赖解析锁外化。
2. **第二优先（正确性隐患）**：#11-#19。其中 #13/#14/#16 改动小、收益直接（resume 重启监控、信号注册收敛、索引刷新）。
3. **第三优先（清理，低风险可分批）**：#20 及第 2 章死代码清单。建议按模块分批：exceptions 体系（auth/event/重复类）→ entities/enums 死枚举 → engine 方法级死代码。
4. **配套治理**：①事件类型注册表（类型字符串→定义处）单点维护，杜绝三轨命名；②put 调用点统一 review（60+ 处返回值/await 检查）；③错误码唯一性 CI 校验。

---

### 附 A：关键证据链（grep 汇总）

| 检索目标 | 检索式（简化） | 结论 |
|---|---|---|
| auth_exceptions 引用 | `auth_exceptions|RateLimitException|SessionException` | 仅定义文件内命中 → 整文件死代码 |
| 事件异常使用 | `EventException|EventQueueFullError|HandlerTimeoutError` | 仅自身与 __init__.py → 整模块死代码 |
| 系统事件使用 | `SystemStartedEvent|SystemHeartbeatEvent|ReportGeneratedEvent` | Started/Stopped 被 main.py 用；Heartbeat/Alert/Config/Module/Health/Resource 无引用 |
| 事件类型命名 | `system\.started|"system_started"|engine\.{stage}` | 三轨并存：点式（system_events.py:21）、下划线（enums.py:814）、engine. 前缀（engine_events.py:74） |
| main_engine 订阅 | `system_health_check|engine_status_changed|system_alert` | 仅注册处与 handler 定义，无发布者 |
| put 未 await | `event_engine\.put\(` 在同步方法（risk_engine.py:358,374; risk_manager.py:150） | 3 处确认未 await |
| publish 不存在 | `event_engine\.publish` | integration_service.py:127,205,293 调用不存在的方法 |
| get_event_engine 链路 | `get_event_engine\(|get_engine_factory\(|initialize_factory` | main.py 直建 EventEngine 未入 factory；sync_tasks.py:73 等未 await |
| 引擎索引刷新 | `update_engine_indexes` | 仅定义，无调用者 |
| 监控便捷函数 | `get_engine_monitor\(|start_monitoring\(`（engine_monitor 模块级） | 无调用者 |
| factory 公有属性 | `hasattr\(.*engine_registry|hasattr\(.*event_engine` | engine_monitor.py:438-456 探测恒 False（工厂仅有私有属性） |
| EventEngine 方法 | `register_general|get_event_history|reset_statistics|get_handler_info` | 无外部调用 |
| 拓扑排序 | `_sort_modules_by_dependency|_sort_engines_by_dependency|gather\(.*start` | 模块级 DFS 在 main.py；引擎级为并行 gather 无拓扑 |
| shutdown 未 await | `module\.shutdown\(\)` | main.py:875 异步 shutdown 未 await |

### 附 B：审查边界与免责

1. 本报告基于静态阅读与引用检索，未运行业务代码、未做动态压测；性能结论（第 4 章）为结构性分析，量化数据待基准测试验证。
2. 涉及 modules/、api/ 的问题（如 integration_service、risk_engine、sync_tasks）仅作为 core API 设计缺陷的外部证据引用，其修复需按项目流程单独确认。
3. 所有"待确认"项均因超出 core/ 直接证据范围，建议由后续专项确认。

---

### 附：审查说明

1. 所有"待确认"项均因超出 core/ 直接证据范围（modules/、api/ 引用尚未逐一验证），建议由后续专项确认。
2. 本报告为只读审查，未修改任何业务代码；唯一写入为本文档。
3. 报告共 5 个审查维度全覆盖 + 严重度 Top 20 汇总 + 修复优先级建议；所有问题均带文件:行号实证。

---

## 8. 业界标准对照

> 本章把前文 5 个维度的既有发现映射到业界公认的代码 review 判定标准，作为"为什么这是问题"的依据。标准引用：Google 工程实践 Code Review 规范（Code Health/可读性）、Robert C. Martin《Clean Code》（命名/函数职责/注释）、SOLID 原则、Martin Fowler《重构》坏味道清单、PEP 8 与 Brett Slatkin《Effective Python》、OWASP Top 10 / CWE 安全条目。

### 8.1 判定标准清单

| 标准 | 来源 | 本报告中的判定用途 |
|---|---|---|
| Code Health / 可读性 / 未使用代码即债务 | Google Engineering Practices（Code Review Developer Guide） | 死代码、命名混乱、误导性注释的判定依据 |
| 命名表达意图、函数单一职责、注释解释"为什么" | Clean Code 第 2/3/4 章 | 事件类型命名、函数语义错位、空桩函数的判定依据 |
| SRP / OCP / DIP / ISP / LSP | SOLID 原则 | God Class、core 依赖 modules、异常体系脱节、优先级契约反转的判定依据 |
| Long Method / Duplicated Code / God Class / Dead Code / Speculative Generality / Primitive Obsession / Shotgun Surgery / Feature Envy / Switch Statements / Message Chains | Fowler《重构》第 3 章坏味道清单 | 大函数、重复逻辑、双轨枚举、贫血实体、调用面广的判定依据 |
| 编码风格一致性、import 卫生 | PEP 8；Effective Python 第 4 项（PEP 8） | 函数定义空格、多余 import、标准库复用（asyncio.Queue）的判定依据 |
| 异步正确性（await、任务引用、可取消性） | Effective Python 第 55-58 项 | 未 await 的 put、fire-and-forget create_task 的判定依据 |
| CWE-209（响应信息泄露）/ CWE-532（日志敏感信息）/ CWE-248（未捕获异常）/ CWE-400（资源耗尽） | OWASP Top 10 与 CWE 列表 | 中间件回显 traceback、警报无界增长、任务异常静默的判定依据 |

### 8.2 问题 → 标准映射表

| 位置（前文编号） | 维度 | 依据标准 | 判定说明 |
|---|---|---|---|
| event_engine.py:38-64 优先级字符串排序（Top#2） | 性能/正确 | Clean Code（命名/契约）；Effective Python 第 47 项（类型明确化） | "priority" 字段存字符串却承载数值语义，行为与 PriorityLevel 文档契约相反（LSP/契约违反）；应用数值类型（Primitive Obsession） |
| event_engine.py:462-501 队列满淘汰失效（Top#1） | 边界 | Effective Python（getattr 默认值陷阱）；Google Code Review（可读性） | `getattr(event,'priority',默认)` 在 BaseEvent 上恒取默认值——防御性代码掩盖了真实契约，属可读性与正确性双重问题 |
| event_engine.py:442-545 put() 约 100 行（含 3 个 return 分支、2 处日志、淘汰逻辑） | 边界 | Fowler — Long Method；Clean Code 函数职责 | 入队、淘汰、统计、日志四职责混一函数；应拆分为 _try_evict_lowest() 等 |
| event_engine.py:53-61 vs 464-485 优先级提取逻辑重复且不一致 | 边界 | Fowler — Duplicated Code | 同一"取事件优先级"逻辑在两处重复实现，已产生行为漂移（dict/BaseEvent 结果不同）；应提取唯一 `_event_priority(event)` |
| event_engine.py:607-646 register/unregister fire-and-forget（Top#11） | 边界 | Effective Python 第 55 项（任务须持有引用并 await）；CWE-248 | create_task 未保存引用、未捕获异常 → "Task exception was never retrieved"，且先 put 后注册丢事件 |
| event_engine.py:342-359 10ms 忙轮询（Top 性能#1） | 性能 | Effective Python 第 60 项（复用标准库）；Google Code Review（简单优先） | 自造轮子替代 asyncio.Queue/Condition，属于"标准库已有正确方案却重复实现" |
| event_engine.py:569-616 重复订阅无去重 | 边界 | Clean Code（防御性设计）；Effective Python（输入校验） | register 无幂等/去重，重复订阅产生重复回调 |
| engine_base.py:1922-1940 _publish_event 类型前缀污染（Top#5） | 业务闭环 | Clean Code 命名；Google Code Review（命名表达意图） | 参数名 event_type 实为 lifecycle_stage，命名与语义不符导致事件类型被污染 |
| engine_base.py:1394-1401 stop 卡 STOPPING（Top#7） | 边界 | Google Code Review（错误处理路径完备性）；Effective Python 第 56 项（except 分支穷尽） | 异常分支未处理状态回滚，属"遗漏的异常路径"审查重点 |
| engine_base.py:1096-1231 start 重试无回滚（Top#8） | 边界 | Clean Code（函数前置/后置条件）；Fowler — 重构"以状态对象取代重复条件" | 重试循环内重复启动副作用，无失败清理钩子 |
| engine_base.py 整类 2694 行（生命周期+依赖+监控+错误+信号+上下文） | 业界对比 | SOLID — SRP；Fowler — God Class | 六类职责集中于基类；建议拆 EngineLifecycle/EngineMonitorable/EngineCommandable mixin |
| engine_base.py:2396-2412 信号处理器重复注册（Top#14） | 边界 | Effective Python（全局状态副作用）；Google Code Review（副作用最小化） | 构造时改进程级全局信号 = 隐式全局副作用，后建实例覆盖先建 |
| engine_base.py:852-857 vs 2387-2392 retry_strategy 构建重复 | 业界对比 | Fowler — Duplicated Code | 同一 dict 构建逻辑两处复制，修改一处漏一处 |
| engine_base.py:566-768 EngineMetricsUpdater 8 个近似方法 | 死代码 | Fowler — Feature Envy；贫血领域模型 | 更新逻辑外置于实体，8 个方法 90% 重复（update_* 模式相同）；应合并为通用 update() |
| engine_base.py:2565-2644 with_retry 与 start() 内联重试逻辑重复 | 业界对比 | Fowler — Duplicated Code | 指数退避逻辑在 start()（L1096-1231）与 with_retry 两处重复 |
| main_engine.py:174 + enums.py:814 + system_events.py:21 事件类型三轨（Top#18） | 业务闭环 | Google Code Review（可读性/命名一致性）；Fowler — Divergent Change | 同一概念"系统启动"三处定义三种值，修改需多处同步，属发散式变更 |
| main_engine.py:206-371 _start_daily_scheduler 150 行内联闭包 + import modules | 业务闭环 | Clean Code（函数职责）；SOLID — DIP；Fowler — Long Method | ①大闭包应提取为模块级服务；②core 直接 import modules 违反依赖倒置（AGENTS.md 亦禁止） |
| main_engine.py:771 健康检查响应发布 SYSTEM_STARTED | 业务闭环 | Clean Code 命名（表达真实意图） | 事件类型与语义不符（health 响应 ≠ 启动事件） |
| main_engine.py:849-870 get_engine 三处查询链 | 业务闭环 | Fowler — Message Chains / Middle Man | 查询在 _module_engines/factory/registry 三处游走，调用方难以判断真实来源 |
| main_engine.py:921 get_all_engines 未 await | 业务闭环 | Effective Python 第 52 项（async/await 正确性） | async 函数不 await 装入 coroutine，属异步误用 |
| engine_factory.py:445,512,781 持锁递归死锁（Top#10） | 边界 | Effective Python 第 55 项；Google Code Review（并发正确性） | 不可重入锁内递归调用自身，并发缺陷典型反例 |
| engine_factory.py:59 category 默认值为类本身 | 边界 | Clean Code（默认值意图）；Effective Python（默认参数陷阱） | `EngineCategory = EngineCategory` 用类对象当实例默认值，属默认值反模式 |
| engine_factory.py:130-137 _do_pause/_do_resume 空桩 | 死代码 | Google Code Review — Code Health；Clean Code 注释 | 空桩 + 误导性 docstring 应删除或实装 |
| engine_monitor.py:759-772 未解决警报无界增长（Top 性能） | 性能 | CWE-400（资源耗尽）；Fowler — 重构 | 未解决警报仅按 resolved 时间清理，持续告警场景内存无界 |
| engine_monitor.py:438-456 hasattr 探测私有属性 | 业务闭环 | SOLID — DIP；Clean Code（封装） | 依赖未公开 API（私有 _engine_registry），hasattr 探测恒 False 属脆弱的隐式契约 |
| error_codes.py:105,157 "5001" 撞值（Top#17） | 业界对比 | Google Code Review（数据一致性）；Clean Code（单一事实来源） | 同一错误码两义，反解歧义，属数据定义缺陷 |
| middleware.py:172 include_traceback 回显客户端 | 业界对比 | OWASP — CWE-209（响应信息泄露） | 开启后堆栈含文件路径/内部结构直接返回客户端，建议仅 DEBUG 环境且脱敏 |
| handlers.py:127-136 异常消息原样入日志 | 业界对比 | OWASP — CWE-532（敏感信息日志） | str(exception) 可能含 token/密码（QuantBaseException.message 由调用方传入），脱敏仅覆盖 SecurityException 分支 |
| sync_tasks.py:73 等未 await get_event_engine | 业务闭环 | Effective Python 第 52 项 | 同步函数调用 async 函数拿 coroutine，属于典型异步误用 |
| modules/analysis/services/integration_service.py:127 publish 不存在 | 业务闭环 | Google Code Review（API 契约）；Effective Python（错误尽早暴露） | 调用未定义方法，运行时才暴露；应在类型检查阶段拦截 |
| risk_engine.py:358,374; risk_manager.py:150 未 await put（Top#4） | 业务闭环 | Effective Python 第 52 项 | async put 不 await → coroutine 丢弃，事件静默丢失（最隐蔽的数据丢失类缺陷） |
| entities.py / enums.py 大面死实体与死枚举 | 死代码 | Google Code Review — Code Health；Fowler — Dead Code / Speculative Generality | 未使用代码与"以防万一"的推测性抽象（EventFilterFunc/TypedEvent/28 个事件异常类）应删除 |
| 函数定义 `def foo (` 空格风格、enums.py:22 `from builtins import int` | 业界对比 | PEP 8（E 系列）；Effective Python 第 4 项 | 全库函数定义空格不规范、多余 import，破坏统一风格（建议引入 ruff/black CI 门禁） |

### 8.3 标准命中统计与综述

| 标准 | 命中问题数（映射表） | 主要聚集区 |
|---|---|---|
| Effective Python（异步/默认值/标准库） | 9 | event_engine 异步误用、未 await put、锁递归 |
| Fowler 坏味道（Long Method/Duplicated/God Class/Dead Code 等） | 9 | engine_base 大基类、优先级提取重复、retry 重复、死代码 |
| Clean Code（命名/职责/注释） | 8 | 事件类型语义、_publish_event 参数命名、空桩注释 |
| SOLID（SRP/DIP/LSP/OCP） | 6 | God Class、core→modules 依赖、异常体系脱节、优先级契约 |
| Google Code Review（可读性/Code Health/错误路径） | 7 | 死代码治理、命名一致性、异常分支穷尽 |
| OWASP/CWE（209/532/400/248） | 3 | traceback 回显、日志敏感信息、警报无界增长 |
| PEP 8 | 2 | 风格一致性、import 卫生 |

**综述**：本报告 Top 20 严重问题中，约 60% 可归因于两类根因——①**契约不明确/命名与语义分离**（事件类型三轨、优先级双轨、`_publish_event` 参数误用、`publish` 不存在的方法），对应 Clean Code/命名/Google 可读性标准；②**异步正确性缺失**（未 await 的 put、fire-and-forget 注册、锁内递归），对应 Effective Python 异步条目。死代码体量（约 3000+ 行）对应 Google Code Review 的 Code Health 治理要求，建议纳入后续清理 Sprint；安全标准命中集中在"错误信息暴露"（CWE-209/532），风险中等但修复成本低（日志脱敏 + traceback 开关收紧）。修复时可按第 7 章优先级执行，每个 PR 的 review checklist 可直接引用 8.2 映射表对应条目。
