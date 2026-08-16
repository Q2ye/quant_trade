# 05 trade + risk 模块审查报告

> 审查基准日期：2026-02-12（以代码库现状为准，纯只读审查，未修改任何业务代码）
> 审查文件清单：`quant_server/modules/trade/` 39 个 .py 文件（engines 5 / services 9 / managers 3 / adapters 4 / events 6 / tasks 3 / utils 3 / 顶层 6）+ `quant_server/modules/risk/` 20 个 .py 文件（engines 2 / rules 6 / services 2 / managers 2 / events 2 / tasks 2 / 顶层 4），合计 **59 个文件**，全部逐行阅读；交叉验证 `main.py`、`config.yaml`、`shared/database/models/business_models.py`、`docs/sql/create_table.sql`、`core/engines/system/event_engine.py`、`modules/strategy/`（signal_events、strategy_manager、signal_router）、`modules/backtest/engines/backtest_broker.py` 等关联文件。
>
> 审查方法：逐文件通读 → 对疑似死代码/跨模块引用做 grep 全库验证 → 对阈值、状态词汇、事件签名做三方（常量/规则类/DB CHECK）比对 → 对"三层资金防护"声明做实现溯源。所有结论附文件:行号实证；无法定论的标注"待确认"。

**主要结论速览（详细证据见对应章节）：**

- **最严重（高）×10**：①实盘/模拟链路资金校验实际 0 层（§1.5/§6#1）；②引擎成交不落库且订单 dict 键与表列不匹配导致 insert 必失败（§5#2）；③半自动确认双链路分裂、`approved` 死状态（§1.2/§6#3）；④并发确认无锁可双倍同步持仓（§3#2）；⑤风控阈值实际生效 0.5/0.15/0.25 与声明 0.30/0.05/0.10 不符（§5.4）；⑥涨跌停规则在信号链路永不触发（§3#7）；⑦SIMULATED_TRADING 可运行时关闭（§3#12）；⑧重复信号无去重（§3#1）；⑨execute_signal API 假执行（§5#9）；⑩pnl_outcome 盈亏回填机制不存在（§5#3）。
- **结构性**：RiskEngine 双实例化导致检查/巡检/事件全部双份（§4#6/§6#15）；`trade/events/risk_events.py` 与 `risk/events/risk_events.py` 确认重复建设（§2#1）；4 个任务类/管理器类从未启动、2 个文件整文件死代码（§2）。
- **防御性**：模拟路径买入可扣成负资金、卖空负持仓被静默删除、两处未定义 logger 的 NameError（§3/§5）。
- **正面确认**：SIMULATED_TRADING 环境变量已正确注入 TradeManager（`main.py:684` → `trade/__init__.py:80`），执行引擎默认安全回退模拟（`execution_engine.py:166-168`）；`signal_type` 的 buy/sell/hold 映射与 DB CHECK 一致（`signal_engine.py:129-136` vs `create_table.sql:3296`）；超期信号有 expired 兜底（`data/tasks/daily_strategy_runner.py:135`）。

## 1. 业界对比分析

### 1.1 订单状态机 vs FIX/OMS 标准

**现状**：系统没有显式订单状态机。状态是在内存 dict 上直接赋值，且无合法转移校验：
- 模拟路径一步到位 `order_data["status"] = "filled"`（`execution_engine.py:174`）；
- 撤单直接置 `"cancelled"`（`execution_engine.py:281`）；
- 恢复在途订单时提到 `partial_filled`/`accepted`（`execution_engine.py:90-91`），但全链路**没有任何代码处理部分成交的增量回报**——成交只认 `status == "filled"` 一个分支（`execution_engine.py:209-211`），部分成交后订单与持仓量即脱节。

**对比**：FIX/OMS 标准状态为 `New → PartiallyFilled ⇄ Filled | Cancelled | Rejected | Expired`，转移必须由券商回报驱动，且每笔成交（Trade）挂在订单下累计。本系统 XTP 适配器是硬编码 mock（`xtp_adapter.py:134-140` 的 `get_order_status` 恒返回 filled），无真实回报通道，状态机无从建立。

**状态词汇三处分裂**（同义词不同写法）：
| 出处 | 词汇 |
|:--|:--|
| `trade/constants.py:14-20` | pending / filled / cancelled / rejected / failed |
| `docs/sql/create_table.sql:854`（orders.status CHECK） | submitted / partial_filled / filled / cancelled / rejected |
| `execution_tasks.py:77,103` 轮询判断 | pending / submitted |

**建议**：以 DB CHECK 为唯一事实源，删除 `ORDER_STATUS` 常量或与 DB 对齐；引入状态转移表（`{from, to, event, guard}`）并用单元测试锁定；部分成交按 `filled_volume` 增量更新持仓与资金，最终成交才触发结算。

### 1.2 半自动确认流程 vs 人工审批最佳实践

**现状**：存在**两条并行、词汇与副作用不一致**的确认链路：
1. `api/routers/signal_router.py:37-86` — `POST /signals/{id}/confirm`：写 `signal_status='confirmed'`，发布 `SignalConfirmedEvent`（`strategy_manager.py:1027-1029` 订阅并同步策略侧持仓）；
2. `modules/trade/handlers.py:610-652` — `review_signal`：写 `approved/rejected`，**不发事件、不生成订单**，`approved` 成为无消费者死状态。

**对比**：人工审批最佳实践要求"审批即动作"（approved → 自动落单或进入待执行队列）、幂等（同一信号不可重复审批）、状态词汇单一、审计留痕（`reviewed_by/reviewed_at` 已有，`business_models.py:257-258`）。

**状态词汇三方不一致**：
| 出处 | 词汇 |
|:--|:--|
| `docs/sql/create_table.sql:3307`（signals.signal_status CHECK） | pending_manual / confirmed / executed / partial / cancelled / rejected / expired / approved |
| `business_models.py:247-248`（模型注释） | pending_manual / confirmed / partial / cancelled / rejected / expired（缺 executed/approved） |
| 代码实际写入 | pending_manual（`signal_engine.py:160,219`）、approved/rejected（`handlers.py:633-634`）、confirmed/cancelled（`signal_repo_v2.py` 经 signal_router）、executed/failed/error（`signal_engine.py:259,278,282,287`）、expired（`data/tasks/daily_strategy_runner.py:135`） |

**建议**：合并为单一确认接口；确认动作统一发布事件并触发订单生成；`signal_status` 词汇收敛到 DB CHECK 集合并同步模型注释；废弃 `review_signal` 或让其复用 confirm 链路。

### 1.3 仓位管理（目标仓位/再平衡）

**现状**：`PositionEngine` 仅是 broker 持仓的读缓存（`position_engine.py:96-127`），无目标仓位、无再平衡、无 T+1 可用量、无冻结/解冻语义。回测侧有 `allocator.rebalance()`（`backtest_engine.py:711`）与 Sizer 权重分配，但实盘/模拟链路完全没有对应物。

**影响**：`single_position_limit`、`position_concentration` 等规则依赖 `positions` 数据（`risk/engines/risk_engine.py:281-282`），而引擎链路的模拟 broker 持仓恒为空（见 §5.1），这些规则在实盘/模拟下拿不到真实输入。

**建议**：半自动定位下仓位管理可后置（人工盯盘），但若启用全自动必须引入目标权重/再平衡模块（复用 backtest allocator 设计）；至少让 `PositionEngine` 支持从 DB `positions` 表（`business_models.py` Position 模型）加载持仓，而非只依赖 broker 内存态。

### 1.4 风控规则引擎 vs 规则表驱动

**现状**：每规则独立类（19 个 `RiskRule` 子类），阈值硬编码在类默认值里；`_load_default_rules` **无参实例化**（`risk/engines/risk_engine.py:219-239`），即 config/常量中的阈值完全不生效（见 §5.4）。`update_rule_params`（`risk_engine.py:333-363`）可热改内存参数但不持久化（重启即失），且事件构造有 bug（见 §5.11）。规则启停状态有 DB 持久化（`_schedule_rule_db_sync`，`risk_engine.py:385-423`），但参数没有。

**对比**：成熟规则引擎（Drools/Easy Rules）以规则表/DSL 驱动，参数与规则体分离、可热加载、可版本化。本系统"每类一文件"可读性尚可，但**参数来源单一且不一致**是硬伤；且 19 条规则全部"默认启用"（`risk_engine.py:244`），缺少分级默认策略（如高频预警类默认开、强阻断类默认关）。

**建议**：阈值统一从 DB `risk_rules.condition`（`business_models.py:813`，JSON 条件字段，目前空置）或 config 注入规则构造；参数变更走 DB 持久化 + 事件广播；补参数范围校验与白名单。

### 1.5 资金校验"三层防护"评估（已发现三层——逐层核实）

**结论：声明与事实不符，实盘/模拟链路实际为 0 层。**

- `risk/rules/account_rules.py:33-39` 注释声称"资金不足检查已由 Broker 三层防护处理（_validate_order + submit_order 自动缩减 + match_orders 二次校验）"。grep 全库验证：`submit_order`/`match_orders` **只存在于回测 broker**（`modules/backtest/engines/backtest_broker.py:334,579`，含 `:499-530` 资金缩减、`:750-777` 二次校验）。
- 实盘/模拟链路：`ExecutionEngine.execute_order`（`execution_engine.py:162-240`）模拟路径直接成交，无任何资金校验；`SimBrokerAdapter._process_trade`（`sim_adapter.py:98-115`）买入 `self.capital -= cost`，**不检查余额，可扣成负数**。
- 实际存在的校验仅 1 层且不完整：`handlers.py:143-146, 321-327` 的 `available_balance < order_amount`——**不含费用**、只查 buy、且只覆盖 API 直连下单，与引擎链路无关。
- `AccountBalanceRule.check` 恒返回 `(True, …)`（`account_rules.py:33-39`），风控层对资金问题完全放行。

**建议**：在 `ExecutionEngine.execute_order` 入口做统一校验（buy：金额+预估费用 ≤ 可用资金；sell：持仓 ≥ 卖出量），模拟路径同样执行；删除 `account_rules.py` 误导性注释或让规则真正实现校验；API 层校验补费用项。

### 1.6 五维度总体判断汇总

| 维度 | 对比基准 | 本系统差距 | 总体评级 |
|:--|:--|:--|:--|
| 订单状态机 | FIX/OMS 回报驱动状态机 | 无显式状态机、无部分成交增量、无券商回报通道（XTP 为 mock） | 不合格 |
| 半自动确认 | 审批即动作 + 幂等 + 单一词汇 | 双链路词汇分裂、approved 无下游、并发无锁 | 不合格 |
| 仓位管理 | 目标仓位/再平衡 | 仅读缓存，无目标/再平衡/T+1 可用量 | 欠缺（半自动可接受） |
| 规则引擎 | 规则表驱动 + 参数外部化 | 每类一文件可读，但阈值硬编码且多处不一致、参数不持久化 | 部分合格 |
| 资金校验 | 多层防御 | 回测 3 层、实盘/模拟 0 层、API 1 层不完整 | 不合格（高风险） |

## 2. 死代码清单

| 位置(文件:行) | 类型 | 说明 | 清理建议 |
|:--|:--|:--|:--|
| `trade/events/risk_events.py`（全文件 8 个类） | 重复建设 | 与 `risk/events/risk_events.py` 功能重复；仅 `RiskAlertEvent` 被 `trade/tasks/risk_tasks.py:10,103,123` 引用，其余 7 类仅被 `trade/events/__init__.py:17-20` 与 `trade/__init__.py:219-220` 再导出，无业务引用 | **确认重复建设**。统一用 `risk/events/risk_events.py`；迁移 `risk_tasks.py` 引用后整文件删除 |
| `trade/tasks/risk_tasks.py`（RiskTasks 全类） | 未启动任务 | 定义并导出（`tasks/__init__.py:3`），全库无 `.start()` 调用；其 3 个周期循环（:50-84）与 `risk_engine._check_loop` 重复 | 删除（功能已被 RiskEngine 巡检覆盖） |
| `trade/tasks/execution_tasks.py`（ExecutionTasks 全类） | 未启动任务 | 无调用；且 `OrderUpdateEvent(order_id=…, order_status=…, order_data=…)`（:84-89）与构造签名 `(order_id, status, **kwargs)`（`order_events.py:18-23`）不匹配，一旦启用即 TypeError | 删除；订单回报应走事件订阅而非轮询任务 |
| `trade/managers/risk_manager.py:55-120` | 从未调用 | `bind_risk_engine` 全库零调用 → `_risk_engine` 恒 None；回退路径 `from modules.trade.rules.* import` 指向**不存在的目录**（`trade/rules/` 不存在），必然 ImportError 被吞（:119-120） | 删除该类，规则管理由 RiskEngine 承担 |
| `risk/managers/rule_manager.py`（RuleManager 全类） | 从未实例化 | 仅 `managers/__init__.py:1` 导出；且 `get_risk_rules` 读 `r.enabled`（:30），ORM 实际字段为 `is_active`（`business_models.py:815`）→ 一旦使用即 AttributeError | 删除 |
| `risk/tasks/daily_check.py`（run_daily_risk_check） | 从未调用 | 仅 `tasks/__init__.py:1` 导出；且引用不存在的 `risk_engine._risk_manager`（:48-51），检查永远跳过 | 删除或接入定时任务并修正属性 |
| `trade/models.py`（全文件 6 个模型） | 遗留重复模型 | 从未被 import（grep 验证）；`Order/Trade/Position/Account/Signal/RiskEvent` 表名与 `business_models.py` 完全冲突，一旦误引入即 "Table already defined" | 整文件删除 |
| `trade/utils/order_validator.py`（OrderValidator） | 定义未使用 | 仅 `utils/__init__.py:4` 导出；引擎/适配器/handler 零调用 | 若启用则接入 `execute_signal`/`execute_order` 入口，否则删除 |
| `trade/adapters/xtp_adapter.py`（XTPBrokerAdapter） | 从未实例化 | `trade/__init__.py:104-111` 非模拟分支也回退 `SimBrokerAdapter`，`broker` 配置被忽略；且 `xtp_adapter.py:25 super().__init__(config)` 对无 `__init__` 的 ABC（`broker_adapter.py:7-48`）调用 → TypeError | 未接真实 XTP 前删除，或修正构造并让 `broker` 配置生效 |
| `trade/events/execution_events.py`（8 个 dataclass 事件） | 定义未使用 | 仅 `events/__init__.py:4-12` 再导出；全库无 `OrderCreateEvent/OrderSubmitEvent/OrderFillEvent/…` 的 put/subscribe | 删除或接入真实执行回报链路 |
| `trade/constants.py:42-49`（SIGNAL_STATUS） | 部分死值 | `RECEIVED/PROCESSING` 从未写入 DB（persist 直接写 pending_manual，`signal_engine.py:160`）；`ERROR` 只写 DB 不写内存状态 | 收敛为实际使用的状态集合 |
| `trade/constants.py:52-61`（DEFAULT_CONFIG）、`:64-69`（TRADING_FEES） | 未接入 | 实际费率走 `cost_calculator.py:18-24`（万一免五/印花 0.05%/过户万 0.1）；`TRADING_FEES` 印花税 0.001 为 2023-08 前旧值，若被误用将多收税 | 删除或改为引用 `cost_calculator` 统一费率 |
| `trade/events/position_events.py:41-49`（PositionRiskEvent） | 重复定义 | 与 `trade/events/risk_events.py:118` 同名类，本文件版本未导出未使用 | 删除本文件重复类 |
| `risk/constants.py:14-36`（RiskRuleName 枚举） | 不完整枚举 | 缺 `sector_concentration / stock_stop_loss / trade_count / limit_up_down / suspension` 5 条实际注册规则（`risk_engine.py:219-239`） | 补全或删除（当前无引用方） |
| `risk/events/__init__.py:3-9` | 导出不全 | `RiskCheckRequestedEvent` 被 `signal_engine.py:232` 实际使用，但未从包级导出 | 补导出或统一从模块路径引用 |

## 3. 边界情况清单

| 位置 | 触发场景 | 现状行为 | 风险等级 | 修复建议 |
|:--|:--|:--|:--|:--|
| `signal_engine.py:171-297` | 同一策略同一股票同日重复出信号 | 无去重/幂等键，每个信号独立持久化+执行，重复建仓；`batch_process_signals`（:368-374）串行处理不查重 | 高 | 以 (strategy_id, ts_code, signal_type, 交易日) 建立幂等键，重复信号置 `cancelled` 或拒收 |
| `signal_repo_v2.py:55-63` + `signal_router.py:37-86` | 两人同时确认同一信号 | `update_signal_status` 无条件 UPDATE（无状态前置/乐观锁），两次 confirm 都成功、发两次 `SignalConfirmedEvent`（:82），策略持仓双倍同步 | 高 | UPDATE 加 `WHERE signal_status='pending_manual'`，rowcount==0 返回 409；或加 version 乐观锁 |
| `handlers.py:625-637` | 并发 review_signal | 先查状态再更新（TOCTOU），无锁，两请求均可写 | 高 | 条件更新 + 校验 rowcount |
| `execution_engine.py:209-211` | 订单部分成交 | 仅 `status=="filled"` 分支更新持仓；无 partial_filled 增量处理，部分成交后订单与持仓量脱节；XTP mock 恒返回 filled（`xtp_adapter.py:134-140`） | 高 | 增加 partial_filled 分支：按 filled_volume 增量更新持仓/资金 |
| `handlers.py:196-201` | 撤单 | 直接改 DB `status='cancelled'`，**不调券商撤单**（实盘券商端订单仍活）；撤单与成交无互斥 | 高 | 撤单走 `execution_engine.cancel_order` → broker；DB 条件更新防竞态 |
| `execution_engine.py:170-199` | 模拟路径卖空 | 无持仓校验直接成交；`sim_adapter.py:132-135` 持仓减到 ≤0 直接 `del`（负仓位凭空消失、资金虚增） | 高 | 模拟路径同样校验 `持仓 ≥ 卖出量`，不足拒绝 |
| `market_rules.py:174-195` | 涨停买/跌停卖 | `LimitUpDownRule` 在信号链路恒不触发：`signal_engine.py:181-199` 信号 dict 无 `pre_close`，规则内 `pre_close = close`（:177）→ 永不到限价；模拟成交不校验涨跌停 | 高 | 信号链路注入 `pre_close`/`is_st`；模拟撮合前校验涨跌停 |
| `signal_engine.py:263-269` | warning 缩减 | `max(int(qty*0.5), 100)`：qty<200 时数量**反而放大**（50→100）；且结果非 100 整数倍（A 股手数要求）；缩减后不重跑风控、不更新 DB quantity | 中 | `qty = max((qty//2)//100*100, 100)` 且 ≤ 原量；缩减结果回写 DB |
| `execution_engine.py:320-330` | 滑点/价格区间 | `price_limit_low/high`、`max_slippage_pct` 仅透传存储，模拟按信号价直接成交，无任何应用 | 中 | 模拟撮合在 `[price_limit_low, price_limit_high]` 内成交并记录滑点 |
| `sim_adapter.py:106-115` | 未知 direction（如 `short`） | 走 else 按卖出处理（:113-115）；且 `logger` **未定义**（文件无 `import logging`/`logger`）→ NameError 崩溃 | 中 | 定义 logger；未知方向拒绝订单而非按卖出 |
| `risk_engine.py:333-363` | `update_rule_params` 参数边界 | 无范围校验（可把 max_loss_percent 设为负/0）；类型转换失败仅 warning 仍 setattr | 中 | 加 (min,max) 约束与属性白名单 |
| `trade_manager.py:40-52` | 运行时切换 SIMULATED_TRADING | `update_trading_config` 运行中可把 `simulated_trading` 改为 false，无二次确认/审计 | 高 | 禁止运行时切换，改配置需重启+强审计 |
| `handlers.py:140-145, 321-327` | 买单资金校验 | `available_balance < order_amount` 不含佣金/印花税，边界单被接受 | 中 | 校验 `金额+预估费用 ≤ 可用` |
| `handlers.py:1027` | `get_round_trips` 异常路径 | 引用**未定义**的 `logger`（handlers.py 顶部无 logging）→ NameError 掩盖原始异常 | 中 | 顶部补 `logger = logging.getLogger(__name__)` |
| `xtp_adapter.py:25,90` | XTP 实例化/下单 | `super().__init__(config)` TypeError；`send_order` 用 `symbol` 键而引擎传 `ts_code`（`execution_engine.py:321`） | 中 | 修正构造；统一键名 |
| `signal_engine.py:208-211` | 通知发送条件 | 仅 `run_mode == "live"` 发微信/钉钉通知；semi_auto 用户收不到"需人工确认"提醒（依赖前端轮询） | 中（待确认前端轮询） | 通知条件改为 `live or semi_auto`，通知内容带确认链接 |
| `signal_engine.py:151` | quantity 类型 | 未校验 `quantity` 为 int；若策略传字符串，`int(original_qty * 0.5)`（:265）或成交逻辑直接异常 | 低 | 入参 schema 校验 int > 0 |

## 4. 性能问题清单

| 位置 | 问题 | 影响 | 优化建议 |
|:--|:--|:--|:--|
| `signal_engine.py:205, 219, 278, 333-347` | 每信号**同步 await 2 次独立 DB 会话**（persist + 回写），直接阻塞事件循环；`batch_process_signals`（:368-374）串行 N 次 DB 往返 | 信号吞吐受 DB RTT 限制，批量信号时事件循环长时间占用 | persist 与回写合并为一次事务；或改为事件/后台任务异步落库 |
| `risk/engines/risk_engine.py:592-625` | 每个违规 `_persist_risk_event` 独立开一个 DB 会话；`check_signal` 内 19 规则串行（:515-558） | 多违规信号每信号 N 次 DB 连接 | 违规事件批量累积后一次写入；规则检查为纯内存计算可保留串行 |
| `risk/engines/risk_engine.py:548` | `self._risk_events` 无限 append，无上限/无淘汰 | 内存随信号量线性增长（泄漏） | 定长 `collections.deque(maxlen=500)` 或定期清理 |
| `risk/engines/risk_engine.py:578-590` | `get_last_check_action_hint` 取 `_risk_events[-3:]`，**跨信号共享** | 并发信号下 A 信号的缩减/阻断 hint 可能来自 B 信号（错误缩减或错误放行） | hint 随 `check_signal` 返回值返回，不读全局列表 |
| `risk/engines/risk_engine.py:641-669` | `_cleanup_loop` 结构错误：`break`（:662）退出内层循环后外层立即 `sleep(300)` 重跑 → **每约 5 分钟清一次**而非注释声称的"每天" | 高频无谓 DB DELETE | 重写为单循环 `while: sleep(86400); cleanup()` |
| `trade/__init__.py:131-137,161` + `risk/__init__.py:81-117` | **双 RiskEngine 实例**：trade 模块建一个（注入 position_engine），risk 模块再建一个并覆盖 `_module_engines["risk_engine"]`（`risk/__init__.py:99-100`）；两者都订阅 `risk.check.requested`（`risk_engine.py:100-104`）、都跑 `_check_loop` | 全自动链路每个信号风控检查×2、巡检×2、违规事件×2 | 单实例化：trade 不再自建，从 `main_engine._module_engines["risk_engine"]` 取用 |
| `round_trip_service.py:84-97` | 账户全部成交无分页全量加载到内存 | 大账户内存/响应时间劣化 | 加分页或按 ts_code 过滤下推 SQL |
| `core/engines/system/event_engine.py:462-487` | 队列满时**丢弃最低优先级事件** | 低优先级风险事件/通知可能静默丢失（高优先级保留） | 监控队列水位；风险类事件改直连告警通道 |
| `mark_to_market.py:83-138` | 逐持仓更新 + 末尾 flush；无分页 | 持仓多时单事务内存累积 | 分批 commit |

## 5. 业务闭环与 bug 清单

| 位置 | 问题描述 | 严重度(高/中/低) | 修复建议 |
|:--|:--|:--|:--|
| `trade/__init__.py:140-147` + `execution_engine.py:227-238,170-199` | **引擎成交不落库**：trade init 未给 ExecutionEngine 传 `session_factory`（:146 缺参）；模拟路径（:170-199）根本不写 DB；实盘路径（:227-238）传入的 order dict 键为 `quantity/filled_price/filled_quantity`（XTP mock `xtp_adapter.py:88-96` 用 `volume/price`），而 orders 表列为 `volume/filled_volume/avg_price`（`create_table.sql:840-859`）且 `user_id/account_id` NOT NULL（:842-843）→ **insert 必失败并被 except 静默吞掉**。→ 引擎下单后订单/成交/持仓/资金全无记录，`signal.order_id` 指向不存在的订单 | 高 | 引擎注入 session_factory；落库前将 order dict 键映射到表列（quantity→volume 等）并补齐 user_id/account_id；成交链复用 `trade_record_service.py:89-237` 的事务编排 |
| `handlers.py:610-652` | 半自动确认闭环断裂：review_signal 仅改 `signal_status='approved'`，不生成订单、不发事件；`approved` 无消费者。另一路 `signal_router.py:37-86` 只同步策略持仓，不写 order/trade/account | 高 | 统一确认链路：approve → 生成订单（走执行引擎或半自动下单队列）→ 成交 → 回写 signal；或文档化"确认后必须手动 record_trade"并做状态机防呆 |
| Signal 模型 `business_models.py:247` | **pnl_outcome/盈亏回填机制不存在**：Signal 无 pnl 字段，全库 grep `pnl_outcome` 零匹配；`round_trip_service.py:116-203` 实时计算已实现盈亏但不落库，信号链路无盈亏闭环 | 高 | 增加 signal 盈亏回填字段（round_trip 结算后 UPDATE）或明确由 analysis 模块承担 |
| `position_rules.py:67`（0.5）、`account_rules.py:45`（0.15）、`account_rules.py:102`（0.25） vs `risk/constants.py:57,62-63`（0.30/0.05/0.10） vs `trade/constants.py:59-60`（0.3/0.05/0.1） | **阈值不一致**：规则按类默认无参实例化（`risk_engine.py:219-239`），**实际生效为 0.5/0.15/0.25**；constants 三处 0.30/0.05/0.10 全是死值。单股 50% 上限、亏损 15% 才停、回撤 25% 才停，均比声明值宽松 | 高 | 阈值单一事实源（DB `risk_rules.condition` 或 config），规则构造时注入，删除常量死值 |
| `handlers.py:303-363` | `execute_signal` API 假执行：直接写 `status='submitted'` 订单即返回"信号执行成功/executed"（:353），无撮合、无持仓、无资金变动；还把 `signal_id` 硬塞成 order_id（:348） | 高 | 删除或改走 `SignalEngine.process_signal`/`ExecutionEngine.execute_signal` 真实链路 |
| `handlers.py:129-177` | `create_order` 创建的订单永远卡在 `submitted`，无任何后续处理 | 中 | 接入执行引擎或标记"仅落单不撮合"并加超时取消 |
| `execution_engine.py:76-120` | 恢复的在途订单无驱动：`_recover_pending_orders` 把订单载入内存后，无任何轮询/回报消费（ExecutionTasks 未启动），重启后恢复的 `submitted` 订单成为僵尸 | 中 | 恢复后挂订单回报监听或启动状态刷新任务 |
| `risk_engine.py:354-361` | `update_rule_params` 构造 `RiskRuleStatusChangedEvent(rule_name=…, message=…)`，而类签名要求 `enabled`（`risk/events/risk_events.py:159-173`）→ **TypeError 必现** | 中 | 补 `enabled` 参数或改事件签名 |
| `risk_engine.py:123-134` + `trade/__init__.py:131-137` | 双 RiskEngine 订阅同一事件 → 全自动链路重复检查/重复违规事件（见 §4） | 中 | 单实例化 |
| `handlers.py:66-91` | `get_order_list` 的 `total` 用分页后的 `filtered_orders` 长度（:67），总数恒等于当页条数 | 低 | 用 count 查询 |
| `execution_engine.py:260-274` | 结算事件 `account_ids` 取 `order.get("account_id")`；模拟路径 order dict 未确保携带 account_id（`execute_signal` 有传 :326，但模拟路径未回填），可能空列表导致结算无账户 | 中（待确认 account 侧空列表行为） | 确保 order_data 全程携带 account_id；空列表时跳过并告警 |
| `sim_adapter.py:98-115` | `close_short` 按买入扣钱（:106）但持仓逻辑只认 `buy`（:127），方向语义混乱；未知方向 NameError（见 §3） | 中 | 精简方向集合（A 股仅 buy/sell） |
| `strategy/events/signal_events.py:48` | 所有 `StrategySignalEvent.event_type` 恒为 ENTRY（含 EXIT/STOP_LOSS 信号），下游按事件类型分发的消费者无法区分 | 低 | 按 signal_type 映射事件类型 |
| `daily_check.py:48-51` | 引用不存在的 `risk_engine._risk_manager`，待处理事件检查永远跳过（死代码叠加） | 低 | 改查 `_risk_events` 或删该检查 |
| `mark_to_market.py:33-45` | 盯市用**前复权价**（qfq）与持仓成本（原始成交价）混算 pnl，除权日口径偏差 | 中（待确认复权基准） | 明确复权口径：成本/市值统一用未复权或统一 qfq |
| `handlers.py:457-480` | 账户概览 `daily_pnl` 用裸 SQL `DISTINCT ON` 直查 `account_daily_performance`，绕开 Repository 分层且无索引校验 | 低 | 迁移到 Repository + 确认索引 |

## 6. 严重度汇总表（Top 20）

| # | 严重度 | 维度 | 位置 | 问题摘要 | 修复方案摘要 |
|:--|:--|:--|:--|:--|:--|
| 1 | 高 | 业界对比/资金 | `execution_engine.py:162-240`、`sim_adapter.py:98-115`、`account_rules.py:33-39` | 实盘/模拟链路资金"三层防护"实际 0 层，模拟买入可致负资金 | 引擎入口统一资金/持仓校验（buy 金额+费用≤可用，sell 持仓≥数量）；删除误导注释 |
| 2 | 高 | 业务闭环 | `execution_engine.py:227-238`、`trade/__init__.py:140-147`、`create_table.sql:840-859` | 引擎成交不落库：未注入 session_factory + 订单 dict 键与表列不匹配 + NOT NULL 缺失 → insert 必失败被吞 | 注入 session_factory；键映射（quantity→volume）+ 补 user_id/account_id；成交链事务化 |
| 3 | 高 | 业务闭环 | `handlers.py:610-652`、`signal_router.py:37-86` | 半自动确认双链路词汇分裂；`approved` 死状态无下游，确认后无订单 | 统一确认接口，approve 后生成订单/发事件，收敛 signal_status 词汇 |
| 4 | 高 | 边界 | `signal_repo_v2.py:55-63` | 并发确认无条件覆盖，双重确认双倍同步持仓 | 条件 UPDATE（WHERE pending_manual）+ rowcount 校验 |
| 5 | 高 | 业务闭环 | `position_rules.py:67`、`account_rules.py:45,102` | 阈值实际生效 0.5/0.15/0.25，与 constants 0.30/0.05/0.10 不符，风控大幅放宽 | 阈值单一事实源注入规则，删除死常量 |
| 6 | 高 | 边界 | `market_rules.py:174-195` + `signal_engine.py:181-199` | 涨跌停规则信号链路永不触发（无 pre_close），涨停照买 | 信号携带 pre_close/is_st，模拟撮合前校验 |
| 7 | 高 | 边界 | `trade_manager.py:40-52` | SIMULATED_TRADING 可运行时改为 false 无审计 | 禁止运行时切换，改配置需重启 |
| 8 | 高 | 边界 | `signal_engine.py:171-297` | 重复信号无去重，重复建仓 | 幂等键 (strategy, ts_code, type, 日) 去重 |
| 9 | 高 | 业务闭环 | `handlers.py:303-363` | execute_signal API 假执行（状态 executed 无成交），signal_id 误用 order_id | 走真实引擎链路或删除 |
| 10 | 高 | 业务闭环 | Signal 模型 `business_models.py:247` | pnl_outcome/盈亏回填机制不存在，信号无盈亏闭环 | 增加 signal 盈亏回填字段并接入 round_trip |
| 11 | 中 | 性能 | `risk_engine.py:548,578-590` | `_risk_events` 无限增长 + hint 跨信号污染 | deque 定长 + hint 随返回值传递 |
| 12 | 中 | bug | `risk_engine.py:354-361` | update_rule_params 事件构造缺 enabled 必现 TypeError | 补参数或改事件签名 |
| 13 | 中 | bug | `handlers.py:196-201` | 撤单绕过券商，仅改 DB | 撤单走引擎→broker |
| 14 | 中 | 边界 | `signal_engine.py:265` | warning 缩减 qty<200 放大、非整手 | 修正为向下取整手且≤原量 |
| 15 | 中 | 性能/架构 | `trade/__init__.py:131-137` + `risk/__init__.py:81-117` | 双 RiskEngine 重复检查/巡检/事件 | 单实例化统一取用 |
| 16 | 中 | bug | `xtp_adapter.py:25` | XTP 构造 super().__init__(config) TypeError；且从未使用 | 修正构造或删除 mock |
| 17 | 中 | bug | `sim_adapter.py:113`、`handlers.py:1027` | 两处引用未定义 logger → NameError | 补 logger 定义 |
| 18 | 中 | 边界 | `sim_adapter.py:132-135` | 卖空负持仓直接删除，资金虚增 | 卖出前校验持仓 |
| 19 | 低 | bug | `handlers.py:66-91` | 分页 total 恒为当页数 | count 查询 |
| 20 | 低 | bug | `risk_engine.py:641-669` | 清理任务每 5 分钟而非每天 | 重写循环结构 |

### 6.1 修复优先级建议

- **P0（上线/实盘前必须）**：§6#1 资金校验、#2 成交落库、#5 阈值统一、#7 SIMULATED_TRADING 防切换、#6 涨跌停注入 pre_close。
- **P1（近期）**：#3 确认链路统一、#4 并发确认锁、#8 信号去重、#9 假执行下线、#10 盈亏回填、#13 撤单走券商、#15 双 RiskEngine 去重。
- **P2（清理）**：§2 全部死代码删除、#12/#16/#17 事件签名与 logger bug、#19/#20 分页与清理循环。

### 6.2 附录 A：风控阈值三方对照表（实际生效值以★标注）

| 参数 | 规则类默认（★实际生效） | risk/constants.py | trade/constants.py | DB 配置 | 一致性 |
|:--|:--|:--|:--|:--|:--|
| 总仓位上限 max_position_ratio | 0.8（`position_rules.py:10`） | 0.80（`constants.py:56`） | 0.8（`trade/constants.py:58`） | 空 | ✅ 一致 |
| 单股仓位上限 max_single_position_ratio | ★0.5（`position_rules.py:67`） | 0.30（`constants.py:57`） | 0.3（`trade/constants.py:59`） | 空 | ❌ 不一致 |
| 账户亏损上限 max_loss_percent | ★0.15（`account_rules.py:45`） | 0.05（`constants.py:62`） | 0.05（`trade/constants.py:57`） | 空 | ❌ 不一致 |
| 回撤上限 max_drawdown_percent | ★0.25（`account_rules.py:102`） | 0.10（`constants.py:63`） | 0.1（`trade/constants.py:60`） | 空 | ❌ 不一致 |
| 日资金变化 max_daily_change_percent | 0.15（`account_rules.py:186`） | 0.15（`constants.py:64`） | — | 空 | ✅ 一致 |
| 前 N 集中度 max_top_n_ratio | 0.6（`position_rules.py:183`） | 0.60（`constants.py:58`） | — | 空 | ✅ 一致 |
| 持仓风险阈值 position_risk_threshold | 0.10（`risk_engine.py:788`） | 0.10（`constants.py:74`） | 0.1（`trade/constants.py:60`） | 空 | ✅ 一致 |

> 注：`risk/constants.py` 中 0.30/0.05/0.10 与规则类默认 0.5/0.15/0.25 的差异即用户关注点——**实际生效的是规则类默认值**，即风控比声明的宽松。DB `risk_rules.condition`（`business_models.py:813`）为空，`update_rule_params` 仅改内存不落库，重启还原。

### 6.3 附录 B：信号状态机可达性检查

| 状态 | 写入方 | 是否有消费者/出口 | 判定 |
|:--|:--|:--|:--|
| received（内存） | `signal_engine.py:197` | 仅展示，未持久化 | 冗余 |
| processing | 无任何写入方（`constants.py:44` 仅定义） | 无 | 死状态 |
| pending_manual | `signal_engine.py:160,219`（DB） | confirm/review/expire 三入口 | 正常 |
| confirmed | `signal_router.py:63`（DB） | StrategyManager 同步持仓（`strategy_manager.py:1028`） | 有出口但无订单 |
| approved | `handlers.py:634`（DB） | **无任何消费者** | 死状态 |
| rejected | `handlers.py:634`、`signal_engine.py:259` | 展示 | 正常 |
| cancelled | `signal_router.py:102` | 展示 | 正常 |
| executed | `signal_engine.py:278`、`trade_record_service.py:225` | 追溯展示（`signal_router.py:156-265`） | 正常 |
| failed / error | `signal_engine.py:282,287` | 展示 | 正常 |
| expired | `data/tasks/daily_strategy_runner.py:135` | 展示 | 正常 |
| partial | 无任何写入方 | 无 | 死状态（DB 允许但代码不写） |

> 结论：`processing`、`partial` 为死状态；`approved` 为无出口死状态（半自动闭环断点）；状态转移无集中定义、无非法转移拦截。

### 6.4 附录 C：订单状态词汇对照（内存 / DB / 处理方）

| 内存值（`execution_engine.py` / `constants.py:14-20`） | DB CHECK（`create_table.sql:854`） | 处理方 | 备注 |
|:--|:--|:--|:--|
| pending | （无对应值） | `execution_tasks.py:77,103` 轮询判断用 | DB 写入会违反 CHECK |
| submitted | submitted | `handlers.py:158,340`、`_recover_pending_orders`（`execution_engine.py:88`） | 唯一落库入口 |
| partial_filled | partial_filled | 仅恢复时读（`execution_engine.py:90`），无写入方 | 有状态无处理 |
| filled | filled | `execution_engine.py:174`、`trade_record_service.py:167` | 正常 |
| cancelled | cancelled | `execution_engine.py:281`、`handlers.py:199` | 正常 |
| rejected | rejected | 无写入方 | 有状态无写入 |
| failed | （无对应值） | `execution_engine.py:256` 返回 dict | DB 写入会违反 CHECK |

> 结论：`pending`/`failed` 不可落库（违反 CHECK）；`rejected`/`partial_filled` 有状态定义但无写入路径；建议统一由 DB CHECK 集合作唯一事实源。

> 审查声明：本次为纯只读审查，未修改任何业务代码；唯一写入为本报告文件。全部结论均附文件:行号实证；标注"待确认"项（结算空账户行为、盯市复权口径、semi_auto 通知依赖前端轮询）需结合 account/monitor/前端行为进一步核实。

## 7. 业界标准对照（判定依据）

> 本章将前述 §1–§6 各问题映射到业界公认的代码审查与工程规范，作为判定依据。判定标准索引如下，映射表见 §7.2。

### 7.1 判定标准索引

| 缩写 | 标准 | 出处/要点 | 本报告应用场景 |
|:--|:--|:--|:--|
| GCR | Google Code Review 规范（Code Health） | CL 应小、可读、行为清晰、无重复、可维护；**删除死代码与过度设计**（Speculative Generality）；代码审查优先关注正确性与可维护性 | §2 死代码清单；§5 假执行/卡死订单；§6 优先级 |
| CC | Clean Code（Robert C. Martin） | 函数/类单一职责；命名自解释；**注释必须与实现一致**（误导性注释是缺陷）；错误处理清晰；避免上帝对象 | §1.5 误导性注释；§5 handlers 上帝类；§5.11 事件构造 |
| SOLID | 单一职责/开闭/里氏/接口隔离/依赖倒置 | SRP：每个类只有一个变更理由；DIP：依赖抽象；OCP：对扩展开放 | §1.3 PositionEngine 职责；§1.4 规则参数注入；双 RiskEngine 重复实现 |
| REF | Martin Fowler《重构》坏味道清单 | Dead Code、Duplicated Code、Lazy Class、Speculative Generality、Data Clumps、Shotgun Surgery、Primitive Obsession、Long Method/God Object、Message Chains、Divergent Change | §2 死代码；§5 阈值三处重复（Data Clumps/Shotgun Surgery）；dict 传递（Primitive Obsession） |
| OMS | 交易系统业界规范（OMS/订单状态机/FIX） | FIX 订单生命周期：New→PartiallyFilled→Filled/Cancelled/Rejected/Expired；**状态转移由回报驱动、非法转移拦截**；**订单幂等性（client_order_id）**；部分成交增量记账；成交/持仓/资金一致性与审计 | §1.1 状态机；§3 部分成交/撤单竞态/重复信号；§5 成交不落库 |
| RISK | 风控规则引擎模式 | 规则表/DSL 驱动、**阈值参数外部化**（可配置、可热加载、可版本化）、规则与引擎解耦、规则有输入字段声明与动作分级 | §1.4 规则引擎；§5.4 阈值不一致；`update_rule_params` 不持久化 |
| PY | PEP 8 与 Effective Python | 模块级 `logger = logging.getLogger(__name__)` 约定（Effective Python #57）；EAFP/防御式编程；**禁止裸 except**、异常链完整；导入组织（PEP 8）；构造参数默认值与签名一致性 | §3/§5 两处未定义 logger；事件签名 TypeError；`except Exception: pass` 静默吞错 |
| TDD | 测试驱动/正确性保障（Google Code Review 亦要求测试） | 状态机转移、并发幂等、边界条件应有单元测试锁定 | 全报告修复建议均建议补测试 |

### 7.2 问题 → 标准映射表

| 问题位置（章节/编号） | 判定标准 | 标准要点与判定依据 |
|:--|:--|:--|
| §1.1 / §6.4 订单状态机与词汇分裂 | OMS + PY | **依据：交易系统规范（OMS/订单状态机/FIX）**——订单生命周期必须为回报驱动的显式状态机，`New→PartiallyFilled→Filled/Cancelled/Rejected`，非法转移应被拦截；内存常量 `pending/failed` 与 DB CHECK 集（`create_table.sql:854`）不一致属"单一事实源"违背，同义词词汇分裂（pending/submitted）违反 PEP 8 命名一致性 |
| §1.2 / §6#3 半自动确认双链路、`approved` 死状态 | OMS + GCR | **依据：交易系统规范——审批留痕与幂等**（一次审批一个动作、同一信号不可重复审批）；`approved` 无消费者属 GCR Code Health 的"行为不一致/未完成功能"，双链路词汇分裂（confirmed vs approved）违背单一事实源 |
| §1.3 PositionEngine 仅缓存、无目标仓位/再平衡 | CC + SOLID | **依据：Clean Code 单一职责**——`position_engine.py:96-127` 职责边界模糊（缓存+查询混用，`get_position` 每次覆写 `self.positions`，:100）；SOLID SRP 要求持仓状态管理独立于 broker 读取 |
| §1.4 规则引擎阈值硬编码、参数不持久化 | RISK + REF | **依据：风控规则引擎模式——阈值参数外部化**（规则表/DB 驱动、可热加载）；19 条规则无参实例化（`risk_engine.py:219-239`）使配置形同虚设；`update_rule_params`（:333-363）只改内存不落库，违背"参数可版本化" |
| §1.5 资金"三层防护"声明不实 | CC + OMS | **依据：Clean Code——注释必须与实现一致**（`account_rules.py:34-36` 注释宣称 broker 三层防护，实盘/模拟链路不存在该实现，属误导性注释）；**交易系统规范——资金/持仓前置校验**（defense in depth，下单前校验、成交时复核） |
| §2 死代码清单（15 项） | REF + GCR | **依据：Fowler《重构》坏味道——Dead Code / Lazy Class / Speculative Generality / Duplicated Code**；Google Code Review：删除无用代码是 Code Health 基本要求。典型：`trade/models.py` 与 `business_models.py` 同表名重复（Duplicated Code + 隐患）；`trade/events/risk_events.py` 与 `risk/events/risk_events.py` 重复建设（Duplicated Code）；4 个任务/管理器类从未启动（Lazy Class）；`XTPBrokerAdapter`/`OrderValidator` 从未使用（Speculative Generality） |
| §3 重复信号无去重 | OMS | **依据：交易系统规范——订单幂等性**（client_order_id/信号幂等键，`signal_engine.py:171-297` 无任何幂等键，重复信号重复建仓） |
| §3 并发确认 TOCTOU | OMS + PY | **依据：交易系统规范——审批幂等与乐观锁**（条件 UPDATE + rowcount 校验）；Effective Python EAFP 原则要求写操作自带前置条件守卫（`signal_repo_v2.py:55-63` 无条件 UPDATE） |
| §3 部分成交/撤单竞态 | OMS | **依据：交易系统规范——部分成交增量记账与撤单-成交互斥**（`execution_engine.py:209-211` 仅处理 filled；`handlers.py:196-201` 撤单绕过券商且与成交无互斥） |
| §3 涨跌停规则永不触发 | OMS + TDD | **依据：交易系统规范——交易前置校验**（涨停禁买/跌停禁卖应强制生效）；`pre_close` 缺失使规则恒不触发（`market_rules.py:177`），缺测试暴露 |
| §3/§5 两处未定义 logger | PY | **依据：Effective Python #57——模块级 logger 约定**（`sim_adapter.py:113`、`handlers.py:1027` 引用未定义 logger，NameError 必现） |
| §3 SIMULATED_TRADING 运行时切换 | OMS + GCR | **依据：交易系统规范——安全开关不可运行时变更**（`trade_manager.py:40-52` 运行中可关模拟开关，违反 AGENTS.md 安全红线精神）；GCR：破坏性行为需审计与二次确认 |
| §4 双 RiskEngine 实例 | SOLID + REF | **依据：SOLID SRP/DIP——同一职责只应有一个实现**；两处各自 `initialize`（`trade/__init__.py:131-137`、`risk/__init__.py:81-117`）导致检查/巡检/事件双份，属 Duplicated Code + Divergent Change 风险 |
| §4 `_risk_events` 无限增长 + hint 跨信号污染 | CC + PY | **依据：Clean Code——状态管理正确性**（全局可变列表被多信号共享，`risk_engine.py:548,578-590`）；Effective Python：共享可变状态需同步/隔离 |
| §4 每信号 2 次 DB 会话阻塞事件循环 | GCR + PY | **依据：Google Code Review——性能意识**；Effective Python：资源复用（连接池复用、批量写），热路径避免逐条建会话 |
| §5 引擎成交不落库、订单键与表列不匹配 | OMS + TDD | **依据：交易系统规范——成交/持仓/资金一致性**（order→trade→position→account 必须原子落库）；dict 键与表列错位（quantity vs volume）属"数据契约不匹配"，缺集成测试未暴露 |
| §5 pnl_outcome 盈亏回填缺失 | OMS | **依据：交易系统规范——信号-成交-盈亏全链路闭环**（信号 → 订单 → 成交 → 持仓 → 结算 → 盈亏回填，`business_models.py:247` 无 pnl 字段，全库无 `pnl_outcome`） |
| §5 handlers.py（1083 行）上帝类 + dict 传参 | REF + CC | **依据：Fowler《重构》坏味道——Long Method / God Object / Primitive Obsession**：`TradeHandler` 承担订单/持仓/信号/篮子/健康检查全部职责，`signal_data`/`order_data` 以裸 dict 跨层传递（`signal_engine.py:181-199` 手工重建 dict 易丢键，:194 注释即证），建议引入类型化 DTO（Pydantic/ dataclass） |
| §5 事件构造缺参 TypeError | PY + CC | **依据：Effective Python——构造参数与签名一致**；`RiskRuleStatusChangedEvent(rule_name=…, message=…)` 缺必填 `enabled`（`risk_engine.py:354-361` vs `risk_events.py:159-173`），属接口契约破坏，应有类型检查/测试兜底 |
| §5 分页 total 恒为当页数 | CC + TDD | **依据：Clean Code——正确性优先**（`handlers.py:66-91` 用过滤后分页结果计 total），属明显逻辑错误，缺测试未拦截 |
| §6 修复优先级（P0/P1/P2） | GCR + RISK | **依据：Google Code Review——按风险与可维护性排序**（资金安全类 P0、正确性/一致性 P1、清理类 P2）；RISK：风控参数与规则的治理优先级最高 |

> 结论：本报告 §1–§6 的全部问题均可在上述业界标准中找到对应判定依据；其中**交易系统规范（OMS/订单状态机/FIX 幂等性）**与**Fowler 坏味道清单（Dead Code/Duplicated Code/Data Clumps）**覆盖问题面最广，建议将"状态机显式化、阈值单一事实源、死代码清理"作为下一迭代的首批整改项，并为状态转移与并发幂等补充单元测试（TDD）。
