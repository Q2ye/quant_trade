# 07 api 层审查报告

> 审查基准日期：2026-02-08（以代码现状为准）
> 审查文件清单（24 个 .py，含依赖包共 30 个源文件）：
> - `api/main.py`（1）
> - `api/routers/`（15）：data / strategy / trade / basket / backtest / account / analysis / monitor / system / risk / health / market / template / composite / signal
> - `api/dependencies/`（5）：auth / config / database / event_engine / main_engine
> - `api/middleware/timing.py`（1）
> - `api/handlers/exception_handlers.py`（1）
> - `api/websocket/`（2）：manager.py / routers.py
> - 交叉引用的 `utils/api_utils/response_formatter.py`、`core/exceptions/`（base/security/error_codes）、`quant_server/main.py`、`config.yaml`
> 审查方式：全量只读（未修改任何业务代码），grep 交叉验证死代码。

---

## 1. 业界对比分析

### 1.1 做得好的方面
- **依赖注入分层清晰**：`dependencies/` 采用"薄接线层"模式（event_engine.py / main_engine.py），由 `quant_server/main.py`（L528-529、L589-590）注入单例，避免 API 层自建基础设施；`get_db_session` 通过 FastAPI 同函数缓存（同一请求内认证与业务共享同一会话，无重复建连）。
- **参数校验意识**：多数分页参数带 `ge=1 / le=100` 约束（basket_router L44-45、data_router L903-904），交易/账户/回测等模块普遍使用 Pydantic request schema；`Query` 带 pattern 的正则校验已出现（market_router L50）。
- **SQL 安全整体良好**：signal_router / data_router / trade_router 的原生 SQL 均使用绑定参数（`:sid`、`:uid`、`:codes`、`:cutoff`），未发现用户输入直接拼接进 SQL 的注入点。
- **批量查询优化**：data_router `get_etfs_api` 用一条 `ROW_NUMBER() OVER (PARTITION BY ...)` 批量取最新行情（L447-458），注释明确说明兼容 TimescaleDB 超表跨 chunk 查询，避免了 ETF 列表 N+1。
- **异常处理器齐全**：`exception_handlers.py` 注册了 422 校验错误 / HTTPException / QuantBaseException / 认证 / 授权 / 数据不存在 六类处理器（L78-102），覆盖 FastAPI 常见错误出口。
- **WebSocket 双向索引**：manager 维护 `channel→ws` 与 `ws→channel` 两个索引（L91-93），断线清理 O(1) 定位；`_EVENT_CHANNEL_MAP` 显式声明事件→频道映射，桥接逻辑集中（L18-77）。
- **日志安全细节**：strategy_router 创建/更新策略时用 `create_summary` 剔除 `code` 字段再打日志（L318、L359），避免把策略代码刷进日志。

### 1.2 与 FastAPI 最佳实践的差距
| 最佳实践 | 现状 | 差距 |
|:--|:--|:--|
| 统一响应模型 | `utils/api_utils/response_formatter.py` 定义 `{code,message,data,detail,timestamp}`（L37-98），但仅部分端点使用 | 存在 **4 套响应格式** 并存（详见 §5.1） |
| 错误码一致性 | ErrorCode 为数字字符串（`SUCCESS="0000"`、`INTERNAL_ERROR="1000"`，error_codes.py L36/43）；exception_handlers 的 `_get_error_code_for_status` 返回 `"INTERNAL_ERROR"` 等英文单词（L105-121）；risk_router 甚至把 `code=500` 当业务码传 | 同一错误在不同出口返回不同 code，前端无法稳定判断 |
| 认证覆盖 | 仅部分路由加 `Depends(get_current_user)` | signal_router 全部端点、data_router 因子定义 PUT/DELETE、WebSocket 端点均无认证（详见 §5.2） |
| 路由分组与注册 | 15 个 router 按模块分文件，main.py 统一注册（L157-180），`enabled_modules` 控制开关 | `template` 模块不在 config.yaml 模块列表（config.yaml L28-117），`template_router` 默认不注册；OpenAPI 把 BearerAuth 安全声明加给全部路径（含公开端点，main.py L92-95），与实际不符 |
| 分页规范 | 部分端点用 response_model 分页；`paginated_response` 快捷函数存在（response_formatter L522-557） | **`paginated_response` 无任何调用方**；多个列表端点无分页（trade /statistics、strategy /feature-sets、data /factors/metadata 内存分页） |
| RESTful 语义 | 动词/资源命名基本规范（basket 嵌套资源 `/basket/{id}/items`、POST /cancel 语义化动作） | DELETE 声明 204 却带 JSON body（template/account/strategy）；`GET /stocks/{code}/full` 未找到返回 200 + `data:null`（market_router L40-42）；删除不存在账户抛 400（account_router L307-312） |
| 请求日志/追踪 | timing_middleware 记录方法/路径/状态码/耗时（timing.py L42-51），含跳过高频路径名单 | 无 request-id / trace-id 关联；日志为 f-string 拼接（L48-50），缺少结构化字段，排查链路困难 |
| WebSocket 管理 | 频道订阅/广播/事件桥接齐全，manager 单例由 main_engine 注入 event_engine（main_engine.py L492-496） | 无鉴权、无心跳、无背压、异常捕获不完整（详见 §1.3） |
| 依赖方向约束 | 架构规定 `modules/ → shared/ → core/`，`api/ → shared/`，禁止反向 | `modules/data/handlers.py:3340-3341` 反向 import `api.dependencies.config`（详见 §5 末行） |

### 1.3 WebSocket 连接管理专项评析
- **连接生命周期**：`websocket_endpoint`（routers.py L17-77）接受连接→按 query 参数初始订阅→循环 receive→finally disconnect。`disconnect` 有 `client_state != DISCONNECTED` 守卫（manager L116-117），避免重复 close。
- **缺失鉴权**：端点未校验任何 token，且频道是自由字符串——任何人可订阅 `order:status`/`events:positions`/`events:account`，实时接收全系统订单/持仓/资金事件（manager `_EVENT_CHANNEL_MAP` L18-77 即推送这些频道）。这是比"无认证 REST 端点"更严重的实时数据泄露面。
- **缺失心跳**：循环内 `await websocket.receive_text()` 无 `asyncio.wait_for` 超时，服务端不发 ping/pong；客户端静默断网（无 FIN）时连接永久滞留，`active_connections` 计数失真。
- **广播健壮性**：`broadcast` 只捕获 `BusinessException`（manager L151），而 starlette 对已断开的 send 抛 `RuntimeError`/`WebSocketDisconnect`——一次异常会中断整个频道循环，后续订阅者收不到消息，死连接也清理不掉。
- **无背压**：顺序 `await send_text`（L147-151），单慢客户端拖慢全频道；无每连接发送队列。
- **与 HTTP 认证体系割裂**：HTTP 侧 `AUTH_ENABLED` 开关（auth.py L35-38）对 WS 完全无效。

### 1.4 健康检查真实性专项（维度 5）
- `GET /health/`（health_router L35-51）：仅返回静态字符串，**不检查任何依赖**——可作为存活探针，但被前端当"系统健康"展示有误导性。
- `GET /health/live`（L54-77）：try 内只有固定返回，**永远 healthy**（"应用存活"检查本身无故障路径），`except` 分支不可达。
- `GET /health/ready`（L80-159）：真实检查——DB `SELECT 1`、MainEngine 状态、EventEngine 存在性，是**唯一真实就绪探针**；但依赖 `get_main_engine`/`get_event_engine`（L82-84），API-only 启动（`uvicorn quant_server.api.main:create_app`，未起 MainEngine）时这两个依赖抛 RuntimeError → /ready 直接 500 而非结构化 503。
- `GET /health/detailed`（L162-289）：检查关键表存在性 + `SELECT COUNT(*)` 表统计，注意 L194 的 `required_tables`（`stock_basic/stock_daily/sys_users/strategies/orders`）与数据表设计文档的 93 表命名是否一致待确认（表名若不同会误报 degraded）。
- 各模块 `/health`（data/strategy/trade/analysis/monitor/account/backtest/system/risk）均为 handler 内真实检查，但**全部要求登录**（`Depends(get_current_user)`），K8s/探针无法直接使用——若用于编排探针需加白名单或独立探针端口。

### 1.5 timing 中间件专项（维度 5）
- `timing_middleware`（timing.py L42-51）**不读取/不缓冲 request body**，仅 `call_next` 前后计时，对请求体与流式响应均无副作用，符合零侵入设计。
- 问题在维护性：`_SKIP_PATHS`（L12-26）与 `_SKIP_PREFIXES`（L28-31）为手工名单，与各模块健康端点硬编码对应；新增轮询端点（如 `/quantTrade/data/factors/research/status` 已列，但 `/quantTrade/backtest/tasks/` 前缀已覆盖）需同步维护，漏配即刷屏日志。
- 无采样/慢请求阈值告警（如 >5s 单独 WARN），耗时异常只能靠日志人工翻找。

### 1.6 各 Router 审查快览（风格与主要风险）
| Router | 风格 | 主要风险（详见 §3/§5） |
|:--|:--|:--|
| data_router（1806 行） | response_model 为主 + 少量手工 dict | 因子定义 PUT/DELETE 无认证；日期 strptime 500；statistics 大表 COUNT 无缓存；假 WS 订阅端点 |
| strategy_router（1054 行） | response_model + success_response 混用 | /feature-sets 被遮蔽；/templates 无认证；start 默认 live；portfolio 无 user_id |
| trade_router（759 行） | response_model 为主 | /statistics 跨用户无过滤；/round-trips IDOR；_has_trade_permission 依赖不存在的 can_trade 键 |
| basket_router（382 行） | success_response 包装 | DELETE /batch 被遮蔽；realtime 估值用占位价 100.0 兜底（业务失真）；批量删除无事务 |
| backtest_router（763 行） | response_model + success_response 混用 | 258 行取消逻辑被注释（死代码）；quick/optimize 同步阻塞；batch 结果循环查询 |
| account_router（675 行） | response_model 为主 | 日终结算同步阻塞；DELETE 204 带 body；删除不存在账户 400 |
| analysis_router（655 行） | response_model 统一 | 异常 detail 泄露 str(e)；其余较规范 |
| monitor_router（406 行） | success_response + error_response | can_manage_alerts 字段缺失导致告警管理 403 坏死；301 重定向带 body |
| system_router（953 行） | response_model 统一 | logout token="unknown"；login 无限流；users limit 无上限；clear_cache 返回裸 dict |
| risk_router（316 行） | success_response + error_response | error_response 的 code= 参数用错（HTTP 恒 500）；alert_level 无校验；访问 _module_engines 私有属性 |
| health_router（326 行） | success_response / error_response | / 与 /live 为伪检查（静态返回）；f-string 拼表名；模块 /health 全部要求登录 |
| market_router（358 行） | 手工 `{"success":true,"data":...}` | 自选股 user_id 键错误；未找到返回 200；30+ 处异常泄露；无统一包装 |
| template_router（166 行） | response_model | 整文件默认不注册（config 无 template 模块）；DELETE 204 带 body |
| composite_router（268 行） | success_response | 直接 new MainEngine() 绕过 DI；异常 detail 泄露 str(e) |
| signal_router（265 行） | 手工 dict + 原生 SQL | **全部端点无认证**（资金级操作）；响应格式与全局不一致 |

---

## 2. 死代码清单

> 均经 grep 全仓验证：以下符号在 API 层（及全仓）无引用方。

| 位置(文件:行) | 类型 | 说明 | 清理建议 |
|:--|:--|:--|:--|
| api/dependencies/auth.py:366-372 | 未使用导出 | `PermissionRequired` / `SuperuserRequired` / `OptionalAuth` / `CurrentUser` 定义后无任何 router 引用 | 删除或改为文档注释；权限校验统一走 `require_permission` 风格函数 |
| api/dependencies/auth.py:285-322 / 324-350 / 257-282 | 未使用导出 | `require_permission` / `require_superuser` / `optional_auth` 仅在 `dependencies/__init__.py` 再导出，全仓无调用（grep 验证） | 删除，或后续把 `require_permission` 接入敏感端点 |
| api/dependencies/event_engine.py:44-67, 71 | 未使用导出 | API 层 `EventPriority` / `publish_system_event` / `EventEngineDep` 无调用方（router 均用 `Depends(get_event_engine)`） | 删除；如需发布系统事件直接用 core 层 EventPriority |
| api/dependencies/database.py:128-140, 142-182, 220-232, 255-269, 284-290, 294-328, 332-333 | 未使用导出 | `get_readonly_session` / `get_transaction_session` / `TransactionSessionDep` / `ReadonlySessionDep` / `get_transaction_decorator` / `with_transaction` / `close_api_database` / `APITransactionScope` / `create_session` / `initialize_database` / `close_database` 均无 API 层调用（main.py L419 用的是 shared 层同名函数） | 收敛到 shared 层，API 层只保留 `get_db_session` / `initialize_api_database` |
| api/dependencies/database.py:185-218, 251, 266 | 未使用导出 | `get_database_health` / `SharedDBSessionDep` 无调用方（health_router 自写检查，未使用该依赖） | 删除 |
| api/dependencies/config.py:22-31 | 未使用函数 | `get_config_by_path` 全仓无引用（grep 仅命中定义处） | 删除 |
| utils/api_utils/response_formatter.py:560-618 | 未注册中间件 | `ResponseMiddleware` 在 api/main.py 无 `add_middleware`，全仓无注册点 | 若想统一响应格式应注册它（见 §5.1），否则删除 |
| api/routers/__init__.py:42-57 | 未使用常量 | `ROUTERS` 列表无 import 方 | 删除 |
| api/routers/template_router.py（整文件） | 默认未注册路由 | config.yaml L28-117 无 `template` 模块，main.py 默认 `enabled_modules`（L53-56）也不含，`include_router` 永不执行 | 与 strategy_router 的 `/templates` 端点（L164-207）功能重复，合并去重后删除其一 |
| api/routers/basket_router.py:261-286 | 被遮蔽的死路由 | `DELETE /batch` 声明在 `DELETE /{basket_id}`（L141）之后，`/batch` 永远被当作 basket_id 匹配 | 将 `/batch` 声明移到 `/{basket_id}` 之前 |
| api/routers/strategy_router.py:987-1013 | 被遮蔽的死路由 | `GET /feature-sets` 声明在 `GET /{strategy_id}`（L253）之后，永远匹配不到（会 404 落到策略详情） | 移到 L253 之前 |
| api/routers/system_router.py:518 | 未使用导入 | `get_token_from_header` 导入后未调用（logout 用 `token="unknown"`，见 §5.3） | 修复 logout 或删除导入 |
| api/websocket/manager.py:18-77 `_EVENT_CHANNEL_MAP` | 部分死映射 | `order_created`/`order_create`/`order_submit`/`execution_success` 等 8 个事件名与现有事件命名规范 `{module}.{domain}.{action}.{status}`（如 `trade.order.submitted`）不一致，实际可能永不触发 | 与 modules 各 events 文件中的 event_type 逐一核对后收敛 |

---

## 3. 边界情况清单

| 位置 | 触发场景 | 现状行为 | 风险等级 | 修复建议 |
|:--|:--|:--|:--|:--|
| api/routers/data_router.py:582-584, 645-647, 686 | `start_date/end_date` 传非法格式（如 `2026-13-99`） | `dt.strptime` 抛 ValueError → 500 | 高 | 用 `Query(pattern=...)` 或自定义校验器，返回 422 |
| api/routers/market_router.py:100 | `windows="1d,abc"` | `int()` 抛 ValueError → 500 | 中 | 逐项 try 或正则校验 `^\d+d$`，非法项跳过 |
| api/routers/system_router.py:720-721 | `list_users_api` 的 `limit` 无上限 | 可传 `limit=10^9` 拉全表 | 中 | `Query(100, ge=1, le=500)` |
| api/routers/backtest_router.py:486 | `get_batch_task_results_api` 的 `task_ids` 列表无长度上限 | 传千级 task_id 造成循环查询风暴 | 中 | schema 加 `max_length=50` 或分块 |
| api/routers/basket_router.py:236-237 | `get_performance` 的 `start_date/end_date` 任意字符串 | 无格式校验，透传 handler（待确认 handler 是否校验） | 中 | 加日期 pattern 校验 |
| api/routers/risk_router.py:163, 264 | `alert_level` 任意值；黑名单 `body: Dict` 无 schema | 无校验，错误值透传 handler | 中 | 用 Literal/枚举；黑名单定义 Pydantic schema |
| api/routers/strategy_router.py:168-183 | `list_templates_api` 先取整页再内存过滤 `is_builtin` | 过滤发生在分页后，page 语义错乱（第 2 页可能为空） | 低 | 过滤条件下沉到查询层 |
| api/dependencies/auth.py:78-145 | AUTH_ENABLED=false 且 DB 不可用时 | 走 L131-145 兜底，**返回硬编码超级管理员**（fail-open 设计，含固定 UUID） | 高 | 兜底分支明确注释为"仅本地调试"；生产配置启动时强校验禁止 AUTH_ENABLED=false |
| api/dependencies/auth.py:102-116 | 多请求并发首次访问（无种子用户） | 两请求同时 INSERT 种子用户 → username 唯一约束冲突 → 落入 L131 兜底 | 中 | 用 `INSERT ... ON CONFLICT DO NOTHING` 或启动时预置 |
| api/websocket/routers.py:38-77 | 客户端断网（无 FIN） | `receive_text` 无限阻塞，无 ping/pong 心跳，死连接长期滞留 | 高 | 服务端定时 ping，用 `asyncio.wait_for` 包裹 receive |
| api/websocket/manager.py:147-160 | 发送时连接已断 | 只捕获 `BusinessException`；starlette 实际抛 `RuntimeError`/`WebSocketDisconnect`，① 死连接清不掉 ② 异常中断广播循环，后续订阅者收不到 | 高 | 捕获 `(RuntimeError, WebSocketDisconnect, BusinessException)`；逐连接 send 用 try 隔离 |
| api/websocket/manager.py:204-208 | EngineLifecycleEvent 带 `details` | 原地向 `event_data["details"]` 注入 `_event` 字段，**修改了共享事件对象**（同事件被多 handler 消费会串数据） | 中 | 构造新 dict，不修改原事件 |
| api/dependencies/event_engine.py:37-38 / main_engine.py:35-36 | API-only 启动且端点依赖引擎 | 抛 RuntimeError → 500，无友好 503 | 中 | 捕获后转 503 并给出明确提示 |
| api/routers/composite_router.py:30-44 | 并发首次请求 | `_main_engine_cache` 模块级全局直接 `MainEngine()` 实例化（绕过注入的单例），与 main.py 注入的引擎可能并存两个实例 | 高 | 改用 `api.dependencies.main_engine.get_main_engine` 依赖 |
| api/routers/strategy_router.py:478-480 | `start_strategy` 请求未带 `run_mode` | 默认 `'live'` 实盘模式启动策略，未联动 `SIMULATED_TRADING` 开关（待确认 handler 是否拦截） | 高 | 默认值改为 `sim`/`backtest`，或强制校验安全开关 |
| api/routers/backtest_router.py:664-728 | `run-scenario` 提交任意 `code` | 设计上允许任意 Python 代码执行（后台线程池），无沙箱 | 高 | 单用户并发数限制 + 资源限额；长期应沙箱化（待确认现有约束） |
| api/routers/data_router.py:1761-1797 | `GET /events/subscribe` | 返回的 `ws_endpoint=/ws/events/{id}` **在 websocket/routers.py 中不存在**，订阅 ID 也未注册到任何地方——假功能 | 中 | 删除或接入真实 WS 订阅 |
| api/routers/signal_router.py:83-84 | EventEngine 未初始化 | `except ImportError: pass` 静默吞掉事件发布失败，成交确认后持仓不同步但接口返回成功 | 中 | 失败时记录日志并返回部分成功语义 |
| api/routers/market_router.py:40-42 | `GET /stocks/{ts_code}/full` 股票不存在 | 返回 200 + `{"data": null, "message": "Not found"}`，语义错误 | 中 | 返回 404 |
| api/routers/market_router.py:36-63 | `ts_code` 未经格式校验直接 `.upper()` 透传 | 非法代码落入 handler 查询（待确认 handler 处理） | 低 | 加 `pattern=r"^\d{6}\.(SH|SZ|BJ)$"` 校验 |
| api/routers/composite_router.py:213-220 | `trigger_composite` 成功后访问 `result['strategies_triggered']` | 若 handler 异常结构缺键 → KeyError → 500 | 中 | 用 `result.get(...)` 并容错 |
| api/routers/basket_router.py:236-255 | `get_performance` 未校验 start_date ≤ end_date | 倒置区间返回空或异常（待确认 handler） | 低 | 参数层校验日期顺序 |
| api/routers/data_router.py:1137-1186 | `delete_sync_tasks_batch` / `delete_sync_task` 返回 `JSONResponse(content=result)` 裸结果 | 不走统一 envelope，前端解析不一致 | 中 | 用 `success_response(data=result)` |
| api/routers/data_router.py:1472-1490, 1534-1552 | `cancel_factor_research` / `delete_factor_research` 同样裸 `JSONResponse(content=result)` | 同上 | 中 | 统一包装 |
| api/routers/health_router.py:114-119 | `/health/ready` 把 `engine_status` 整个塞进响应 | 暴露内部引擎状态细节（内存/队列等，待确认字段） | 低 | 只返回 status 摘要 |
| api/routers/signal_router.py:22-25 | `fill_time: Optional[str]` 无 ISO 格式校验 | 非法时间字符串透传到事件（后续解析失败待确认） | 低 | 用 `datetime` 类型或 pattern |
| api/routers/strategy_router.py:130-137 | `create_instance_from_template` 的 `capital` 来自 `body.get("capital", 1000000.0)`，body 为未校验 Dict | 可传负数/超长金额；其余字段全无 schema | 中 | 定义 Pydantic schema |
| api/routers/basket_router.py:300 | `duplicate_basket` 的 `new_name` 无长度上限 | 超长名称入库报错或截断（待确认 DB 列宽） | 低 | schema 加 max_length |
| api/routers/data_router.py:901-902 | `get_sync_tasks_api` 的 `group` 参数任意字符串（注释称 1-7） | 无枚举校验，透传 handler | 低 | `Literal["1","2","3","4","5","6","7"]` |
| api/routers/backtest_router.py:898 | `trigger_strategy_api` 的 `request: StrategyTriggerRequest = Body(StrategyTriggerRequest())` | 以模型实例作 Body 默认值，空 body 时语义依赖 Pydantic 默认实例，行为隐晦 | 低 | 显式 `Body(default=None)` + 手动校验 |

---

## 4. 性能问题清单

| 位置 | 问题 | 影响 | 优化建议 |
|:--|:--|:--|:--|
| api/routers/backtest_router.py:531-550 | `quick_backtest` 在 async 端点内**同步等待**整个回测完成 | 长回测阻塞事件循环，全部请求排队 | 改为后台任务 + 轮询任务状态 |
| api/routers/account_router.py:632-675 | `trigger_daily_settlement_api` 同步执行日终结算 | 多账户结算耗时分钟级，阻塞事件循环 | 提交线程池/后台任务，返回 task_id |
| api/routers/backtest_router.py:586-620 | `optimize_parameters_api` 参数优化同步执行 | 网格搜索可能长时间阻塞 | 改为异步任务队列 |
| api/routers/backtest_router.py:484-526 | 批量获取回测结果循环逐条查询（N+1） | task_ids 多时产生 N 次完整查询 | 单条 `WHERE task_id IN (...)` 批量查询 |
| api/routers/trade_router.py:668-718 | `get_trade_statistics_api` 无分页、无用户过滤 | 全库聚合；COUNT/SUM 全表扫描；跨用户数据（见 §5） | 加 user_id 条件 + 日期范围强制 |
| api/routers/data_router.py:1662-1707 | `get_data_statistics` 连续 6 个大表聚合，含 `COUNT(*)`（stock_daily 千万行级） | 每次请求全表扫描，无缓存 | 结果缓存 60s，或改为预计算统计表 |
| api/routers/data_router.py:424-435 | `get_etfs_api` type 筛选路径**全量拉取** ETF 再内存过滤分页 | ETF 上千只时每页请求全量 | 分类推断结果落库或按 name 前缀 SQL 过滤 |
| api/routers/data_router.py:1340-1368 | `get_factor_metadata_api` 全量取回后内存分页 | 元数据量大时响应体超大 | LIMIT/OFFSET 下沉到 SQL |
| api/websocket/manager.py:143-151 | 广播为**顺序 await send_text**，无每客户端发送队列/背压 | 慢客户端拖慢整个频道广播（队头阻塞）；高并发订阅下延迟放大 | 每连接独立发送队列 + `asyncio.wait_for` 超时丢包 |
| api/websocket/manager.py:225 | 每次事件转发打 INFO 日志（含订阅者数） | `data.sync.progress` 类高频事件刷屏日志 | 降为 DEBUG 或采样统计 |
| api/websocket/manager.py:248-251 | 事件桥接订阅约 40 个 event_type | 高频事件（sync progress）无节流/合并 | 对 progress 类事件做合并窗口（如 500ms 合并） |
| api/routers/data_router.py:1230-1253 | `DELETE /quality` 循环 `db_session.delete` 最多 1000 条 | 大记录数下长事务 + 慢删除 | 批量 `DELETE ... WHERE` |
| api/routers/health_router.py:199-204 | `/health/detailed` 对 `stock_daily` 等表 `SELECT COUNT(*)` | 与 /statistics 重复的全表扫描 | 复用统计缓存 |
| api/dependencies/auth.py:78-145 | 每次请求在认证关闭时执行一次 `select SysUser`（+可能 INSERT 种子用户） | 无认证模式下每请求多一次 DB 往返 | 进程内缓存 seed user 查询结果 |

---

## 5. 业务闭环与 bug 清单

| 位置 | 问题描述 | 严重度(高/中/低) | 修复建议 |
|:--|:--|:--|:--|
| **响应格式不统一（全局）** | 4 套格式并存：① `success_response/error_response` → `{code,message,data,detail,timestamp}`（response_formatter L37-98）；② 手工 `{"success":true,"data":...}`（market_router L32、signal_router L86/110/128、trade_router L703、backtest L515）；③ 异常处理器 → `{success:false,error:{...}}`（exception_handlers L33-45，其 `exc.to_dict()` 格式见 core/exceptions/base.py L127-138）；④ response_model 端点裸返回 Pydantic（account/analysis/backtest/trade/monitor/system/data 大部分端点） | 高 | 全端点统一走 `success_response/error_response` 或注册 `ResponseMiddleware`；异常处理器改为输出同一 envelope |
| **错误码体系混乱** | ErrorCode 数字码（"0000"/"1000"）vs `_get_error_code_for_status` 英文码（"INTERNAL_ERROR"）vs risk_router 传 `code=500`（业务码变 "500"）；前端无法稳定判断成功 | 高 | 统一以 ErrorCode 枚举为唯一业务码源；`error_response` 调用改 `status_code=` 参数 |
| api/routers/risk_router.py:95 | `toggle_rule` 的 ValueError 分支 `error_response(message=str(e), code=404)` → **HTTP 状态仍 500**，业务码 "404" | 高 | 改为 `status_code=404`；同类问题见 L74/98/118/136/155/181/196/216/241/259/279/299 |
| api/routers/signal_router.py:37-38, 89-90, 113-116, 156-157 | **信号确认/取消/待确认/追溯全部无认证**——任何人可确认成交（资金级操作） | 高 | 全部加 `Depends(get_current_user)` + 交易权限校验 |
| api/websocket/routers.py:17-21 | WebSocket 无认证，且可订阅 `order:status`/`events:positions`/`events:account` 频道 → 未授权用户可实时获取全系统订单/持仓/资金数据 | 高 | 连接时校验 JWT（query token 或首次消息鉴权），频道订阅做权限过滤 |
| api/routers/data_router.py:1508-1519, 1522-1531 | 因子定义 **PUT/DELETE 无认证依赖**（仅 session），任何人可改/停用因子 | 高 | 加 `Depends(get_current_user)`（参考 L1497 的 POST） |
| 各 router 异常泄露（market_router L34/44/63…、account_router L101-104、composite_router L77/91/163/182/225/243/268、backtest L550/581、template L68/87/104、system_router L442/465/484/506…） | `HTTPException(detail=str(e))` 把内部异常/DB 错误原文返回客户端 | 高 | 统一 `detail="服务器内部错误"`，`str(e)` 仅进日志 |
| api/routers/system_router.py:518-524 | `logout_api` 从不提取请求 token，固定传 `token="unknown"` 进黑名单 → **登出不生效**（黑名单记录错误 token） | 高 | 从 Authorization 头取 token 后调用 logout |
| api/routers/backtest_router.py:258 | `executor.cancel(task_id)` 整行被 `#` 注释（代码与注释同行），**线程池中运行的回测任务永远无法真正取消** | 高 | 还原为可执行代码并处理异常 |
| api/routers/monitor_router.py:221, 252, 289, 329 | 权限判断读 `current_user.get("can_manage_alerts"/"can_trigger_alerts")`，而 `get_current_user`（auth.py L224-236）**从不返回这两个字段** → 恒为 False → 告警规则管理/手动告警对所有人 403（功能坏死） | 高 | 改用 auth.py 的 `permissions` 列表判断，或补充字段 |
| api/routers/market_router.py:340, 354 | 自选股用 `current_user.get("user_id")`，而用户字典键为 `"id"`（auth.py L225）→ 恒为 `""`，所有用户共享同一自选股记录（串数据 + 功能失效） | 高 | 改 `current_user.get("id")` |
| api/routers/trade_router.py:668-718 | `get_trade_statistics_api` 聚合 SQL **无 user_id 过滤** → 任一登录用户可看全系统交易统计；且无分页 | 高 | 加 `AND user_id = :uid` |
| api/routers/trade_router.py:632-662 | `get_round_trips_api` 调用 `get_round_trips(session, account_id, ts_code)` **未传 user_id**，无归属校验（IDOR） | 高 | 传入 `current_user.id`，handler 校验账户归属（待确认 handler 现状） |
| api/routers/strategy_router.py:674-721 | `get_portfolio_detail/performance/weights` 调用 handler **未传 user_id** | 中 | 传 user_id，handler 校验归属（待确认） |
| api/routers/template_router.py:127-136, account_router.py:277-303, strategy_router.py:411-437 | DELETE 声明 `status_code=204` 却返回带 body 的 `success_response` → 204 响应体被丢弃/前端解析失败，且与其余端点不一致 | 中 | 改 200 或改为空 204（删除 body） |
| api/routers/health_router.py:202-203 | `text(f"SELECT COUNT(*) FROM {table}")` f-string 拼表名（值来自硬编码列表 + DB 元数据，非用户输入，但模式危险） | 低 | 改白名单映射或参数化 |
| api/routers/strategy_router.py:79-91, 164-207 | `/builtin`、`/templates`、`/templates/{id}` 无认证（与 template_router 功能重复，且后者默认未注册） | 中 | 统一加认证并与 template_router 合并 |
| api/routers/data_router.py:971-993, 1120-1134 | `/sync/types`、`/sync/status/all`、`/sync/supported-data-types` 无认证 | 低 | 加 `Depends(get_current_user)`（元数据，风险低） |
| api/main.py:120-131 | CORS `allow_origins` 默认仅 localhost:3000/5173（生产前端 origin 未配置，待确认部署）；`TrustedHostMiddleware allowed_hosts=["*"]`（注释自认生产应限制） | 中 | 生产配置显式 origins + 域名白名单 |
| api/main.py:136 | `from api.handlers.exception_handlers import ...` 绝对导入，与同文件其余相对导入不一致；依赖 cwd 在 sys.path 才可运行 | 低 | 改相对导入 `from .handlers...` |
| api/routers/monitor_router.py:63-75 | `/risk/alerts` 重定向返回 301 + JSON body（无 `Location` 头语义） | 低 | 改 307/308 + `Location` 头 |
| api/routers/account_router.py:307-312 | 删除不存在账户抛 400（应为 404） | 低 | ValueError 分支改 404 |
| api/dependencies/database.py:117 | 用 `"connection" in str(e).lower()` 判断连接错误，误判率高 | 低 | 按异常类型（OperationalError/InterfaceError）判断 |
| api/routers/system_router.py:686 | `clear_cache_api` 失败时返回裸 dict `{"cleared":False,...}`，未走统一格式 | 低 | 用 `error_response` |
| api/main.py:97-113 | `custom_openapi` 隐藏 page/page_size/sort_by/sort_order 文档参数 | 低 | 保留文档参数，或前端对接时补齐说明 |
| api/routers/data_router.py:1230-1253 | `DELETE /quality` 任意登录用户可删质量检查记录（无管理员校验） | 中 | 加 `_require_admin`（参考 system_router L712） |
| api/routers/system_router.py:445-465 | 开放注册无邀请码/审批；`login` 无频率限制（暴力破解面） | 中 | 注册加邀请码或管理员审批；登录加限流（429） |
| api/routers/backtest_router.py:558 | `export_report_api` 的 `report_format` 无枚举校验（任意字符串透传） | 低 | `Literal["json","csv"]` |
| api/dependencies/auth.py:208-213 | 权限码生成逻辑：`can_read` 优先 → `can_write` → 否则 `"execute"`——一个既不可读也不可写的权限被映射成 `execute`，且 `data` 模块判定用 `"data" in perm.lower()` 子串匹配（L220），误匹配 `"data_management"` 之类 | 中 | 显式三字段映射 + 精确权限码匹配 |
| api/routers/system_router.py:574-649 | 密码重置/邮箱验证接口 handler 抛 `NotImplementedError` → 返回 501 | 认证闭环功能未实现却暴露路由，前端误以为可用 | 中 | 未实现前隐藏路由或返回明确"未启用" |
| api/routers/market_router.py:67-73, 133-140, 346-357 | `body: Dict = Body(...)` 无 schema 且无大小限制（screener/财务对比/自选股保存） | 超大/畸形 body 直接进 handler，可能 500 或慢查询 | 中 | 定义 Pydantic schema + body 大小限制 |
| api/routers/strategy_router.py:1035-1054 | `train/lgb` 无 db_session 依赖、无用户资源配额 | 任意登录用户可反复提交训练任务耗资源（并发无限制，待确认 TrainingService 内部限制） | 中 | 单用户并发训练数限制 + 管理员权限 |
| api/routers/backtest_router.py:911-933 | `trigger_strategy` 通过 BackgroundTasks 执行，但 `background_tasks` 在响应返回后才运行且不受进程管理 | 服务重启/worker 退出会丢任务；无任务持久化 | 中 | 走统一任务队列（executor） |
| modules/data/handlers.py:3340-3341（跨层引用） | 模块层反向 import `api.dependencies.config.get_settings`（违反 AGENTS.md 依赖方向 `modules/ → api/` 禁止）；且 `get_settings()` 为 async 函数，此处未见 await（疑为未等待协程） | 依赖方向违规 + 运行时行为错误（待确认 handler 上下文是否 await） | 中 | 模块层直接使用 `shared.config.config_manager.get_config()`，删除该 import |

---

## 6. 严重度汇总表（Top 20）

| # | 严重度 | 维度 | 位置 | 问题摘要 | 修复方案摘要 |
|:--|:--|:--|:--|:--|:--|
| 1 | 高 | 业务闭环 | signal_router.py:37-156 | 信号确认/取消/待确认/追溯全部无认证，资金级操作可被匿名调用 | 全部端点加 `get_current_user` + 交易权限 |
| 2 | 高 | 业务闭环 | websocket/routers.py:17-21 | WebSocket 无鉴权且可订阅订单/持仓/账户频道，泄露全系统实时敏感数据 | 连接鉴权（JWT）+ 频道权限过滤 |
| 3 | 高 | 业务闭环 | data_router.py:1508-1531 | 因子定义 PUT/DELETE 无认证依赖 | 补 `Depends(get_current_user)` |
| 4 | 高 | 业务闭环 | 各 router（market/account/composite/backtest 等 30+ 处） | 500 错误 `detail=str(e)` 泄露内部异常/DB 细节 | 统一"服务器内部错误"，str(e) 仅入日志 |
| 5 | 高 | 业务闭环 | system_router.py:518-524 | logout 固定传 `token="unknown"`，登出黑名单失效 | 从 Authorization 头取 token |
| 6 | 高 | 业务闭环 | backtest_router.py:258 | `executor.cancel` 被注释成死代码，线程池回测无法取消 | 还原代码并加异常处理 |
| 7 | 高 | 业务闭环 | monitor_router.py:221/252/289/329 | `can_manage_alerts` 字段不存在 → 告警管理全部 403 坏死 | 改用 permissions 列表或补字段 |
| 8 | 高 | 业务闭环 | market_router.py:340/354 | 自选股用错键 `user_id`（应为 `id`）→ 功能失效且全用户共享记录 | 改 `current_user.get("id")` |
| 9 | 高 | 业务闭环 | trade_router.py:668-718 | 交易统计无 user_id 过滤，跨用户数据泄露 | SQL 加 `user_id = :uid` |
| 10 | 高 | 业务闭环 | trade_router.py:632-662 | 买卖配对追溯无账户归属校验（IDOR） | 传 user_id 并在 handler 校验 |
| 11 | 高 | 边界情况 | auth.py:131-145 | 认证关闭且 DB 故障时 fail-open 返回硬编码超级管理员 | 仅限本地调试，生产配置禁止 |
| 12 | 高 | 边界情况 | strategy_router.py:478-480 | 启动策略默认 `run_mode='live'`，未联动 SIMULATED_TRADING | 默认 sim，并校验安全开关 |
| 13 | 高 | 边界情况 | composite_router.py:33-44 | 直接 `MainEngine()` 绕过 DI，可能双实例 | 用注入的 `get_main_engine` |
| 14 | 中高 | 业务闭环 | response_formatter + 全部 router | 4 套响应格式并存，错误码体系混乱（"0000"/"1000"/"INTERNAL_ERROR"/"404"） | 统一 envelope + ErrorCode 单一来源 |
| 15 | 中高 | 业务闭环 | risk_router.py:74-299 | `error_response(code=404/500)` 参数用错 → HTTP 恒 500 | 改 `status_code=` |
| 16 | 中高 | 死代码 | basket_router.py:141 vs 261 | `DELETE /batch` 被 `/{basket_id}` 遮蔽 | 调整声明顺序 |
| 17 | 中高 | 死代码 | strategy_router.py:253 vs 987 | `GET /feature-sets` 被 `/{strategy_id}` 遮蔽 | 调整声明顺序 |
| 18 | 中 | 性能 | backtest_router.py:531-550/632-675/586-620 | async 端点内同步执行回测/结算/优化，阻塞事件循环 | 后台任务化 |
| 19 | 中 | 性能 | websocket/manager.py:143-160 | 广播顺序发送无背压、异常捕获不完整，慢客户端拖垮频道 | 独立发送队列 + 捕获 RuntimeError/WebSocketDisconnect |
| 20 | 中 | 边界情况 | data_router.py:582-584/645-647/686 | 非法日期参数导致 500 | 参数校验返回 422 |

**修复优先级建议（P0 → P3）**：
- **P0（上线前必须）**：#1、#2、#3 认证补齐；#4 异常信息脱敏；#5 logout 修复。
- **P1（本周）**：#6-#13 功能坏死/越权/安全开关联动修复。
- **P2（本月）**：#14、#15 响应与错误码统一；#16、#17 路由遮蔽；#19 WS 广播健壮性。
- **P3（持续）**：死代码清理（§2 全表）、分页补齐、同步阻塞任务化、缓存与节流。

---

### 附：审查范围与局限
- 本次仅审查 API 层文件；handler/service/repository 层内的所有权校验、沙箱、`SIMULATED_TRADING` 联动等仅标注"待确认"，需后续层审查核实。
- `utils/api_utils/response_formatter.py` 不在审查范围文件清单内，但因其定义统一响应规范，作为交叉引用纳入分析。
- 未执行运行时验证（未启动服务实测端点行为），以上"现状行为"均基于静态代码路径推导；标"待确认"项需结合 handler 层代码或实测确认。

**发现统计概览**：本报告共记录问题 **79 项**——§3 边界情况 24 项（高危 8）、§4 性能 13 项、§5 业务闭环/bug 34 项（高危 13）、§2 死代码 13 项、§1 业界对比差距 8 项。其中 **Top 20 中 13 项为"高"**，集中在：认证缺失（信号/WS/因子定义 3 处）、异常信息泄露（30+ 端点）、登出失效、回测取消死代码、两处权限字段错配导致功能坏死、两处越权数据访问、安全开关未联动。建议按 §6 的 P0→P3 顺序推进修复，优先解决"匿名可操作资金/交易数据"类问题（#1/#2/#3）与"功能坏死"类问题（#7/#8/#16/#17），再统一响应与错误码体系（#14/#15）。

> 复核方式：全部行号均来自本次会话对源文件的逐行读取；死代码判断经全仓 grep（含 `__pycache__` 之外的全部 .py）确认无引用方；标注"待确认"的项未深入 handler/service 层，需在后续层审查或运行时验证中核实。

> 本报告为只读审查产出，未修改任何业务代码；唯一写入文件即本报告。

---

## 7. 业界标准对照

> 本章将前文各维度的问题映射到业界公认的代码审查 / 安全 / API 设计标准，作为判定依据的追溯。引用标准：Google Code Review 规范（Code Health）、Clean Code（Robert C. Martin）、SOLID 原则、Martin Fowler《重构》坏味道清单、FastAPI 官方最佳实践、REST API 设计规范（Richardson 成熟度模型）、OWASP API Security Top 10（2023）、PEP 8 与 Effective Python。

### 7.1 引用标准清单

| 标准 | 本报告采用的判定要点 | 对应章节 |
|:--|:--|:--|
| Google Code Review 规范（Code Health） | 代码可读性、无死代码/被注释代码、注释必须与代码一致、命名自解释、小步可维护变更 | §2、§5（#6） |
| Clean Code | 函数单一职责、异常处理不吞错/不靠字符串匹配、日志使用占位符惰性求值、命名一致性 | §3（database.py:117）、§5（#4/#8） |
| SOLID 原则 | DIP：高层不依赖具体实现，依赖注入统一（禁直接 new 引擎）；SRP：一个模块一个职责；OCP：角色/权限判断避免硬编码散落 | §1.2、§5（#13）、§3（composite_router） |
| Martin Fowler《重构》坏味道 | Duplicated Code（重复样板/重复端点）、Dead Code（未被调用的函数/被遮蔽路由）、Shotgun Surgery（同类改动散落多文件）、Comments（注释掉的代码）、Feature Envy（访问他对象私有成员） | §2 全表、§5（#6/#14/#16/#17）、risk_router:309 |
| FastAPI 官方最佳实践 | Depends 依赖注入、response_model 校验、Pydantic/Query 参数约束、async 端点避免同步阻塞、统一异常处理与状态码语义 | §1.2、§3、§4（#18）、§5（#14/#15） |
| REST API 设计规范（Richardson 成熟度模型） | Level 2：动词/状态码语义正确（204 不应带 body、404/400 区分、未找到不返回 200）；统一错误结构（类比 RFC 7807 Problem Details） | §5（#14）、monitor 301、account 400、market 200+null |
| OWASP API Security Top 10（2023） | API1 对象级授权失效（BOLA/IDOR）、API2 认证失效、API3 属性级授权失效、API4 资源消耗无限制、API5 功能级授权失效、API8 安全配置错误、API9 库存管理不当、敏感信息泄露、注入、限流 | §5（#1/#2/#3/#5/#9/#10）、§3、§4（#19） |
| PEP 8 / Effective Python | 导入风格一致、禁止裸 except、日志用 %-占位符惰性求值、消除魔法字符串、行内不留被注释代码 | §1.2（main.py:136）、health_router:306、system_router:518 |

### 7.2 问题类别 → 标准映射（按章节）

| 问题类别 | 代表位置 | 依据标准 | 标准要点 |
|:--|:--|:--|:--|
| 认证缺失（信号确认/WS/因子定义） | signal_router.py:37-156、websocket/routers.py:17-21、data_router.py:1508-1531 | OWASP API2 — 认证失效 | 敏感操作必须验证身份；WS 会话同样受认证控制 |
| 越权访问（跨用户/IDOR） | trade_router.py:668-718、trade_router.py:632-662、strategy_router.py:674-721 | OWASP API1 — 对象级授权失效（BOLA/IDOR） | 每次资源访问必须校验当前用户对目标对象的属主权 |
| 权限字段错配致功能坏死/属性级越权 | monitor_router.py:221/252/289/329、market_router.py:340/354 | OWASP API3 — 属性级授权失效；Clean Code — 命名一致性 | 授权判定必须基于实际返回的权限模型字段 |
| 异常信息泄露内部细节 | 各 router `detail=str(e)` 30+ 处 | OWASP — 敏感信息泄露；Clean Code — 异常处理 | 对外只返回通用错误，堆栈/DB 细节仅入日志 |
| fail-open 认证兜底 | auth.py:131-145 | OWASP API8 — 安全配置错误；Secure by Default | 认证失败应 fail-closed；生产环境禁止关闭认证 |
| 登出失效 | system_router.py:518-524 | OWASP API2 — 会话管理失效 | 注销必须作用于真实 token |
| 资源消耗无限制（无分页/无上限/同步阻塞） | trade_router.py:668-718、system_router.py:720-721、backtest_router.py:531-550、data_router.py:1662-1707 | OWASP API4 — 资源消耗无限制；FastAPI 官方 — async 端点勿做阻塞调用 | 列表必须分页限流；重计算必须异步化 |
| 响应/错误码 4 套格式并存 | response_formatter.py vs exception_handlers.py vs 手工 dict vs response_model | REST — 统一错误结构（RFC 7807 类比）；FastAPI — 统一响应模型 | 全局单一 envelope 与单一错误码来源 |
| 死代码与被注释代码 | §2 全表、backtest_router.py:258 | Google Code Review — Code Health；Fowler — Dead Code / Comments 坏味道 | 删除未调用代码与注释掉的代码，保持仓库可维护 |
| 被遮蔽路由 | basket_router.py:141/261、strategy_router.py:253/987 | Fowler — Dead Code；FastAPI — 路由声明顺序 | 静态路径必须先于动态路径段声明 |
| 绕过 DI 直接实例化引擎 | composite_router.py:33-44、risk_router.py:309 | SOLID — DIP；FastAPI — 依赖注入最佳实践 | 一律经 Depends 获取单例；不访问他人私有成员（Feature Envy） |
| SQL 注入面（低危模式） | health_router.py:202-203（f-string 拼表名） | OWASP — 注入 | 表名/列名一律白名单映射，杜绝任何 f-string 拼 SQL |
| CORS / Host 头白名单 | main.py:120-131 | OWASP API8 — 安全配置错误 | 生产限定 origin 与 allowed_hosts |
| 路由库存与假端点 | template_router（默认不注册）、data_router.py:1761-1797（/ws/events/{id} 不存在） | OWASP API9 — 库存管理不当 | 未实现/未启用的端点不应暴露或应明确 404/501 |

### 7.3 Top 20 问题逐条标准标注

| # | 问题摘要 | 依据标准 |
|:--|:--|:--|
| 1 | 信号确认等资金级操作无认证 | OWASP API2 — 认证失效 |
| 2 | WebSocket 无鉴权泄露实时订单/持仓/资金 | OWASP API2 + 敏感信息泄露 |
| 3 | 因子定义 PUT/DELETE 无认证 | OWASP API2 — 认证失效 |
| 4 | 500 错误 detail=str(e) 泄露内部异常 | OWASP — 敏感信息泄露；Clean Code — 异常处理 |
| 5 | logout 黑名单 token 错误导致登出失效 | OWASP API2 — 会话管理失效 |
| 6 | executor.cancel 被注释成死代码，回测无法取消 | Google Code Review（Code Health）；Fowler — Comments/Dead Code |
| 7 | can_manage_alerts 字段错配致告警管理 403 坏死 | OWASP API3 — 属性级授权失效 |
| 8 | 自选股 user_id 键错误致功能失效+串数据 | OWASP API3；Clean Code — 命名一致性 |
| 9 | 交易统计无 user_id 过滤跨用户泄露 | OWASP API1 — BOLA |
| 10 | 买卖配对无归属校验（IDOR） | OWASP API1 — BOLA/IDOR |
| 11 | 认证关闭+DB 故障 fail-open 返回硬编码超管 | OWASP API8 — 安全配置错误；Secure by Default |
| 12 | 启动策略默认 run_mode='live' 未联动安全开关 | OWASP API8 — 安全配置错误；Secure by Default |
| 13 | 直接 new MainEngine() 绕过 DI | SOLID — DIP；FastAPI — 依赖注入 |
| 14 | 4 套响应格式并存、错误码体系混乱 | REST — 统一错误结构；FastAPI — 统一响应模型；Fowler — Shotgun Surgery |
| 15 | error_response 参数用错致 HTTP 恒 500 | FastAPI — 状态码语义；REST Level 2 |
| 16 | basket DELETE /batch 被路由遮蔽 | Fowler — Dead Code；FastAPI — 路由顺序 |
| 17 | strategy /feature-sets 被路由遮蔽 | Fowler — Dead Code；FastAPI — 路由顺序 |
| 18 | async 端点内同步回测/结算/优化 | FastAPI 官方 — async 端点避免阻塞；OWASP API4 |
| 19 | WS 广播无背压、异常捕获不完整 | OWASP API4 — 资源消耗；系统设计 — 背压 |
| 20 | 非法日期参数导致 500 | FastAPI — Query/Pydantic 校验；OWASP — 输入验证 |

> 结论：本报告全部问题均可溯源至上述 8 类业界标准；修复时建议以 §6 的 P0→P3 顺序执行，并在每个修复 PR 的 review 中按 7.1 清单逐条复核（认证→授权→输入校验→资源限制→统一响应→死代码清理）。
