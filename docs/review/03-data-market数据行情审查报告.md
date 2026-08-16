# 03 data + market 模块审查报告

> 审查基准日期：2026-08-14（只读审查，未修改任何业务代码）
> 审查文件清单（46 个 .py + 6 个支撑文件）：
> - data 模块 31 个：`services/sync_service.py`(6127行)、`handlers.py`(3730)、`factor_calculators.py`(2291)、`services/market_service.py`(2338)、`engines/{sync,clean,quality,research}_engine.py`(1095/1513/2034/1206)、`engines/__init__.py`、`events/*`(8个)、`services/{quality_service,clean_service,etf_factor_daily,adjusted_price_generator,market_state_classifier,research_service}.py`、`utils/{factor_calculator,quality_checker,timing}.py`、`managers/*`(4个)、`tasks/*`(5个)、`__init__.py`、`constants.py`
> - market 模块 15 个：`engines/market_engine.py`、`handlers.py`、`services/*`(10个)、`events/market_events.py`、`constants.py`、`schemas.py`
> - 支撑文件 6 个：`docs/sql/create_table.sql`、`quant_server/config.yaml`、`core/engines/system/main_engine.py`、`shared/sources/tushare_source.py`、`shared/database/repositories/base/{repository_base,hyper_repository_base}.py`、`shared/database/repositories/operation/task/data_sync_task_repo.py`
> 审查方法：全量阅读 + 跨模块 grep 实证（死代码/调用链）；所有结论均附 文件:行号；无法确定的标注"待确认"。

## 1. 业界对比分析

### 1.1 数据同步管道（幂等 / 断点续传 / 增量 / 批大小 / 限流）

| 维度 | 现状 | 证据 | 业界差距与建议 |
|---|---|---|---|
| 幂等 upsert | 日/周/月/复权因子/财务等均走 `bulk_upsert`（PG `ON CONFLICT DO UPDATE`），且 `stock_daily` 建表含 `UNIQUE(ts_code,trade_date)`（create_table.sql:2792） | sync_service.py:1820、2127、2784 | ✅ 达标；但**分钟线例外**见下 |
| 分钟线幂等 | `stock_minutes` 表**无任何唯一约束/索引**（create_table.sql:2822-2834），`batch_insert` 的 upsert 分支依赖反射唯一约束（hyper_repository_base.py:146-169），无约束时退化为 `DO NOTHING` 也失效（无冲突目标）→ 重复同步同一时段**必然产生重复行** | sync_service.py:2476、etf_minute 同（3640） | ❌ 需补 `UNIQUE(ts_code, trade_time, freq)` 超表索引（TimescaleDB 需先建 hypertable 约束，改用普通唯一索引） |
| 增量断点续传 | 服务层实现四模式智能日期推断（full/incremental/up_to_date/overlap），按每股 DB 最新日期续传 | sync_service.py:1519-1576 | ✅ 服务层合格 |
| 引擎层断点续传 | 引擎任务队列/状态**纯内存**（`self.tasks`/`task_queue` 无持久化），进程重启丢全部排队/运行中任务 | sync_engine.py:171-174、685-696 | ❌ 业界用 DB 任务表 + 状态机；建议任务落库并启动时恢复 |
| 批大小 | `bulk_upsert`/`batch_insert` 默认 chunk 1000，规避 PG 32767 参数上限 | hyper_repository_base.py:103-173 | ✅ 合理 |
| 限流 | 双层：config `sync_rate_limits` 并发信号量 + `tushare_source._RATE_LIMITS` 令牌桶（80% 余量），失败指数退避重试 `_retry_on_rate_limit` | sync_service.py:486-581、1737-1757；config.yaml:160-179 | ✅ 高于业界常见水平；但**令牌桶在请求完成后才取令牌**（sync_service.py:1753-1755），突发窗口首 N 个请求不受控，建议请求前取 |
| 全市场批量拉取 | 日线/复权/每日指标/ETF 日线/指数日线走"按交易日一次拉全市场"路径，将 5000+ 次逐股 HTTP 降为 M 次 | sync_service.py:1823-1920 | ✅ 好设计；但 90 分位基准（:1859）使**落后于基准的少数停牌股靠逐股路径补齐**，逻辑正确但复杂度高，建议单测覆盖 |
| 串行瓶颈 | main_engine 日终任务对 9 种数据类型**串行** `await svc.sync_market_data(...)`（每种 3-60 分钟） | main_engine.py:230-256 | ❌ 应改 `batch_sync_data`（内部已支持 Semaphore(5) 并发）；见 §4 |

### 1.2 Tushare 限流处理

- 正面：限流错误识别（`_is_rate_limit_error` 匹配"频率超限/每秒请求/访问受限"）、告警 60s 节流、接口级 sleep 0.15s、按接口频率令牌桶，tushare_source.py:46-121、350、426；sync_service.py:534-581。
- 反面：引擎层（sync_engine）**完全无限流与退避**，且重试机制失效（见 §5）；`_cancellable_run_in_executor` 的 `future.cancel()` 无法真正终止 OS 线程（sync_service.py:1461-1467），HTTP 请求仍会跑完，仅结果丢弃——符合 Python 限制，但取消后的 Tushare 配额照常消耗，业界建议用连接级超时（requests timeout）配合。

### 1.3 质量检查策略

- 质量体系有两套实现：`DataQualityService`（**活代码**，handlers.py:1979/3009 调用）+ `clean_service`（**死链路**，仅 clean_engine→data_manager 引用，而 DataManager 无实例化点，见 §2）。
- **致命缺陷**：质量服务在无 ts_code / 股票列表 / 因子覆盖三种场景下**写入硬编码假指标**（quality_service.py:292-306 返回固定 `{"expected_trading_days":30,"missing_count":2,"quality_score":0.96}` 且写入 data_quality_checks 表；:357-359 假设 98% 有效；:402-403 魔法系数 100 估算缺失数且可为负）——质量分数体系当前不可信，需重构为真实采样统计。
- 业界对比：缺失/重复/范围检查应基于真实 SQL 聚合（COUNT/GROUP BY）而非估算；建议参考 §5 修复项逐条落实。

### 1.4 因子计算向量化

- 主体已向量化（groupby/rolling/ewm），但存在**5 处 Python 级循环**：`_calculate_beta` 逐日 `np.cov`（factor_calculators.py:1254-1267）、`_calc_max_dd_duration` rolling apply（:2288-2289，且结果未用）、`_calc_obv_divergence` apply lambda（:2543）、`_calc_vol_decline_corr` groupby.apply（:2355-2358）、market_state_classifier 全部指标纯循环（market_state_classifier.py:89-141）。
- 除零/NaN 防护严重缺失：PE/PB/turnover/sharpe 分母 0 → inf 直入因子序列（factor_calculators.py:334/387/1384/1437/1326）；RSI 强上涨段 `replace(inf,NaN)` 后 `fillna(50)` 把本应 100 的超买填成中性 50（:1687-1690）——**明确的数值错误**；ETF 因子入库只滤 NaN 不过滤 inf（etf_factor_daily.py:138）。
- 重复计算：38 个 ETF 因子各自重算同一中间量（RSI 系 4 次、vol MA20 4 次、TR 3 次），建议抽公共中间量缓存（factor_calculators.py:2005-2752）。

### 1.5 PIT（point-in-time）正确性

- **复权因子 PIT（高）**：前复权基准 = `当前因子 / DB 内最新因子`（adjusted_price_generator.py:62-73、market_service.py:1539-1541），而表按日**增量写入、历史行从不重算** → 每当新除权除息发生，最新因子变化，此前写入的 qfq 历史行全部失真；`stock_adjusted_prices` 表内跨期序列不在同一复权基准。
- **后复权公式错误（高）**：`hfq = raw ÷ (current/latest)`，而 Tushare 官方口径为 `raw × factor`（与同文件 qfq `raw × factor/latest` 自洽）；adjusted_price_generator.py:132-137 与 market_service.py:1554-1564 两处同错 → 后复权价被错误缩放。建议按官方公式修正并在文档标注锚定口径（待确认项目自定义口径）。
- **清洗写回污染（高）**：clean_service 把"缺失交易日"（多为**停牌日**）用前一日 OHLC 前向填充并硬插 vol=0（clean_service.py:1267-1316）；除权除息日价格跳空被误判为异常并以**最新价**覆盖（:889-899、:1403，`closes[0]` 是 DESC 序最新价而非异常日前一价）→ 真实行情被篡改，下游因子/回测被系统性污染。
- **交易日近似（中）**：`_get_trading_days_from_db` 恒返回 []（TODO），回退的近似日历把春节近似为 1/1-3、端午/中秋用中旬近似（clean_service.py:1121-1162）→ 停牌/缺失判定在节假日前后的窗口错误，建议接入 `TradeCalendarRepository`。
- **位置对齐脆弱（中）**：etf_factor_daily 用 `df["ts_code"].values` 与 `result_series` 位置对齐（etf_factor_daily.py:124-126），依赖 pandas 版本的行序稳定性（`include_groups=False` 需 pandas≥2.2），建议按 index merge。

### 1.6 数据新鲜度与调度（与策略安全的闭环）

- **正面（值得保留）**：main_engine 日终任务在驱动策略前校验 `stock_daily` 最新交易日==当日且条数≥4000，否则**跳过策略驱动**（main_engine.py:303-329，注释引用 600833 旧数据事故）——这是本模块最接近业界"数据就绪门禁"的设计。
- **缺口 1（中）**：market_state_daily 由分类器在日终任务内同步执行（main_engine.py:263-266），一旦同步/分类失败，`market_state_service.get_market_state` 无新鲜度标记，前端无法区分"今日无数据"与"数据滞后"（market_state_service.py:36-45）。
- **缺口 2（中）**：`market_state_daily`（分类器产出）与 `stock_daily`（涨跌停统计）两张表日期可能不同步，前端按索引对齐 dates/limit_dates 可能错位（market_state_service.py:45-59）——建议按 trade_date 键值合并。
- **缺口 3（低）**：日终调度 21:20 与注释（20:00）、FIXME（16:30）、日志（22:42）四处不一致（main_engine.py:357/362/369）；且 `date.today()` 用服务器本地时区，部署非 Asia/Shanghai 时区会错一天（main.py:212-255）。
- **缺口 4（中）**：quality_tasks/research_tasks/sync_tasks 的定时配置（如每日质量检查、因子计算）从未注册（见 §2），"定时质量检查"实际不存在；仅同步完成钩子（handlers.py:3004-3020）触发一次质量检查。

### 1.7 ETL 综合评估结论

| 评估项 | 结论 | 一句话建议 |
|---|---|---|
| 幂等 | 部分达标（日线等 bulk_upsert + 唯一约束） | 补 stock_minutes 唯一索引 |
| 断点续传 | 服务层达标，引擎层缺失 | 引擎任务落库 |
| 增量 | 达标（四模式推断） | 保持 |
| 批大小 | 达标（chunk 1000） | 保持 |
| 限流 | 达标且偏优（令牌桶+指数退避） | 令牌改请求前取 |
| 质量检查 | **不达标**（假数据入库） | 重构为真实聚合 |
| 因子向量化 | 主体达标，5 处循环 + 除零/NaN 防护缺失 | 逐项修 |
| PIT | **不达标**（复权锚定漂移、清洗写回污染、hfq 公式错） | 修正公式 + 停牌不填充 + 全量重锚 |
| 数据新鲜度门禁 | 部分达标（main_engine 条数门禁） | 补 market_state 新鲜度标记 |

## 2. 死代码清单

> grep 范围：`quant_server/**/*.py` 全目录；"无引用"= 全库仅定义处/自引用命中。

| 位置(文件:行) | 类型 | 说明 | 清理建议 |
|---|---|---|---|
| managers/data_manager.py:57 `DataManager` | 类（整链死） | 全项目无 `DataManager(` 实例化；唯一引用是 managers/__init__.py:21 导出。`modules.data.managers` 包无人 import | 删除包或接入模块 initialize |
| managers/data_manager.py:816 `execute_data_pipeline` | 方法 | 全库仅定义处 1 命中，无调用方 | 随 DataManager 一并处理 |
| managers/research_manager.py:108 / status_manager.py:44 | 类 | 同属 managers 死包；status_manager 的并发护栏（:61-93）从未生效 | 同上 |
| engines/clean_engine.py:193 `DataCleanEngine`、engines/quality_engine.py:180 `DataQualityEngine`、engines/research_engine.py:56 `FactorResearchEngine` | 引擎 | 仅被死类 DataManager 实例化（data_manager.py:157/169/181）；运行链路（data/__init__.py:198-203）只启动 DataSyncEngine | 若 QualityService 仍要自动检查，改由 handler/task 直调；否则删除三引擎 |
| engines/__init__.py:212/284/353/409 register_all/create_all/create_by_type/get_all_types | 函数 | 零调用 | 删除 |
| tasks/sync_tasks.py、quality_tasks.py、research_tasks.py | 模块 | `modules.data.tasks` 包无任何外部 import；其 Celery beat_schedule（quality_tasks.py:692-723 等）从未注册；且内部 `@celery_app.task` 装饰 async def、`session` 未定义（research_tasks.py:989-992）、查询未按股票过滤（:378-381）等硬伤，一旦启用即坏 | 删除或整体重构为 apscheduler 任务并注册 |
| tasks/daily_strategy_runner.py:22 `DailyStrategyRunner` | 类 | 零引用；其文档声称的 API 端点 `/quantTrade/data/run-daily-strategies` 在路由层不存在；且 `_step_generate_adjusted_prices` 用不存在的 `self.db`（:125）必抛 AttributeError；`_step_sync_data` 是空 stub（:112-118） | 删除（真实日终流程在 main_engine.py:358-368） |
| handlers.py:2718 `_execute_sync_data_sync` / handlers.py:2278 `_execute_sync_factor_research` | 函数 | 无调用方（实际走 :1181 与 :411 的 async 版本） | 删除 |
| sync_service.py:1336 `retry_failed_sync` | 方法 | 无调用方，且路由层无重试端点（grep data_router 无 retry 路由）——"重试失败任务"功能缺失 | 补 API 或删除 |
| services/clean_service.py `DataCleanService` | 类（运行期死） | 唯一引用 clean_engine.py:59/1624/1633，而 clean_engine 属死链 → 运行时不可达 | 见 clean_engine 处置 |
| events/factor_calculation_events.py | 模块 | 文件头自述"v4.0 预留—暂未实例化"，事件类无构造调用 | 删除或实现 |
| events/__init__.py:198-203 `DataSyncRequestEvent` 等 4 类 | 引用 | 引用的类在所有文件中均未定义（grep 无 class 定义）→ 死引用 | 修正或删除 |
| quality_engine.py:1565-1604 通知方法 / research_engine.py:1158-1165 缓存方法 | 方法 | `logger.debug`/`pass` 空实现，无实际功能 | 实现或删除 |
| market/engines/market_engine.py:22 `MarketEngine` | 引擎 | 从未实例化；market/__init__.py 无 initialize()（main.py 日志"没有initialize函数，跳过初始化"），main_engine 的 module→engine 映射无 "market" | 删除或在启用前补 initialize + 引擎注册 |
| market/events/market_events.py:9-72 4 个事件类 | 事件 | 全仓无发布者/订阅者 | 删除或实现闭环 |
| market/services/limit_service.py:142 `_count_consecutive` | 函数 | 已被窗口函数批量版（:97-125）替代，无调用 | 删除 |
| market/services/financial_service.py:15-59 `get_indicators_compare` 的 metrics 参数 | 参数 | 接收但完全未使用，恒返回全部 8 项指标 | 实现过滤或删参 |
| services/quality_service.py:32-51/434-493 | 函数 | `_is_invalid_financial_statement`/`_check_financial_consistency` 仅被注释代码引用；`_check_financial_data_integrity` 方法不存在（整段被注释） | 删除或重写 |
| services/market_state_classifier.py:172 | 语句 | `vol_ratio = _calc_volume_ratio(closes, 20)` 计算后从未使用（真正量比 :180 用 amounts 重算），且参数传错（closes 当成交量） | 删除 |
| market/constants.py:8-40 | 枚举 | MarketStatus/SectorType/MarketIndex/MAJOR_INDICES 全仓无引用 | 删除或接入 |
| quality_engine.py:2370-2410 `register_quality_engine` | 函数 | 内部自建一次性 `EngineFactory()` 注册后丢弃，外部 factory 不生效 | 修正注册逻辑 |
| sync_service.py:3567-3581 等被注释旧方法块 | 注释代码 | 多处 `# [DEAD]` 注释遗留（async_sync_stock_quotes 等） | 清理 |

## 3. 边界情况清单

| 位置 | 触发场景 | 现状行为 | 风险等级 | 修复建议 |
|---|---|---|---|---|
| sync_service.py:1106-1115 + create_table.sql:1396-1415 | batch_sync_data 预创建子任务写 `parent_task_id` | **表缺该列**（模型有 business_models.py:939）→ INSERT UndefinedColumn 报错，批量同步整体失败；cancel_sync 的 `parent_task_id` 级联 SQL（handlers.py:1855）、repo parent_only 查询（data_sync_task_repo.py:143/167）同样报错 | 高 | 补 `ALTER TABLE data_sync_tasks ADD COLUMN parent_task_id VARCHAR(64)` 并同步 create_table.sql |
| sync_service.py:3888 | `_sync_trade_calendar` 中 Tushare 返回 None | `calendar_data` 未赋值即 `len(calendar_data)` → NameError | 中 | 判空后返回 0 条 |
| sync_service.py:2146 / 2791 | `_sync_stock_list`/`_sync_etf_basic` 走非 bulk 分支 | 引用未定义变量 `idx`/`etf` → NameError（bulk 分支存在故平时不触发，潜伏 bug） | 低 | 删除死分支或修正变量 |
| sync_service.py:4870 | `_sync_audit_opinion` 清洗列集合 | 误用 `StockExpress.__table__.columns`（应为 StockAuditOpinion）→ 审计意见专属字段被过滤丢弃 | 高 | 改用本表列集合 |
| sync_service.py:3796-3797 | `_sync_financial_data` 三表任一拉取/写入异常 | `except Exception: pass` 静默吞掉，records_failed 不累计 → 任务显示成功但数据缺失 | 中 | 记录失败并累计计数 |
| sync_service.py:2465-2494 / 3625-3654 | 分钟/ETF分钟同步中断 | 串行循环无断点续传，中断后从头重跑；`batch_insert` 无唯一约束兜底 → 重复行累积 | 中 | 加唯一约束 + 增量起点记录 |
| sync_service.py:1951 | 同一秒两次同类型同步 | `task_id = sync_{type}_{%Y%m%d_%H%M%S}`，task_id 列 UNIQUE → IntegrityError 500 | 中 | task_id 加 uuid 后缀 |
| handlers.py:2857-2863 | 取消请求先于后台任务 token 创建到达 | cancel 置 DB cancelled 后，后台任务 :2863 无条件覆盖为 running → 已取消任务继续执行（DB 回退检查 :2913 读到的已是 running） | 高 | 写 running 前查 DB 状态，或 token 随任务记录提前创建 |
| sync_engine.py:727-770 / 998-1026 | 引擎队列取消/超时 | 取消不剔除队列项、不中断运行中协程，完成后覆盖 CANCELLED/COMPLETED；超时只标记 FAILED 不 cancel 底层任务，完成时状态被回写覆盖 | 高 | 移出队列 + 持有协程引用并真 cancel |
| sync_engine.py:583-584 | 引擎队列执行任务 | `DataType(config.sync_type.value)`：DataSyncType 值 full/incremental… 与 DataType 值 daily_quotes… 完全错配 → 必 ValueError | 高 | 建 sync_type→DataType 映射 |
| clean_engine.py:1560-1567 vs 1328-1410 | 清洗规则执行 | 默认/修复规则 `rule_type` 与 `check_methods` 键零匹配 → 全部落 fallback，清洗空转但 `success=True` 假报成功 | 高 | 统一规则命名与映射；无规则生效时置失败 |
| clean_engine.py:933-960 | 含 disabled 规则的清洗任务 | `total_steps=len(rules)+2` 含被跳过规则 → 进度百分比溢出/错位 | 低 | 按实际生效步骤计数 |
| factor_calculators.py:1687-1690 | RSI 持续上涨（loss=0） | inf→NaN→fillna(50)，超买被填成中性 | 高 | `rs==inf` 置 RSI=100，仅 0/0 填 50 |
| factor_calculators.py:334/387/1384/1437/1326 | PE/PB/换手率/量比/Sharpe 分母为 0 | inf 直入因子序列；ETF 入库只滤 NaN 不滤 inf（etf_factor_daily.py:138） | 高 | 分母 replace(0,nan) + 入库 isinf 过滤 |
| utils/factor_calculator.py:187-188 | 多实例计算同一因子不同参数 | 类级 `FACTOR_CONFIGS` 共享可变对象被 `params.update(kwargs)` 原地修改 → 参数跨调用泄漏 | 中 | `{**config, **kwargs}` 拷贝 |
| quality_service.py:292-306 / 357-359 / 402-403 | 质量检查无 ts_code / 股票列表 / 全市场覆盖 | 写入硬编码假指标（得分=92.9 等来自虚构数据） | 高 | 真实 SQL 聚合统计 |
| market_state_classifier.py:38-42 | 配置读取失败 | 回退硬编码口令 `postgres/123456` → 凭据泄露风险 | 中 | 无配置即报错 |
| market_state_classifier.py:203-211 | trend_strength 归一化 | 绝对价格斜率/波动率×100 后 clamp，量纲导致序列近乎 0/1 二值，区分度差 | 中 | 斜率改相对单位（%/日） |
| market_state_classifier.py:127-132 | momentum_score | docstring 称标准化 [0,1]，实现为原始 20 日收益，且被 etf_factor_daily.py:208 直接当策略因子 | 中 | 统一口径并明确消费方契约 |
| market/limit_service.py:60-65 | exchange 过滤 | `b.exchange='SSE'` 与 screener 的 'SH' 口径不一致，传 'SH' 静默空结果 | 中 | 统一/映射校验 |
| market/screener_service.py:65-84 | PE/PB 过滤与 page=0 | NULL PE 全纳入、负 PE 可入选、page=0 → 负 OFFSET 报 500 | 中 | 明确 NULL/负值策略 + 参数校验 |
| market/stock_service.py:289-297 | before_date 非 ISO 格式 | `date.fromisoformat` 抛 ValueError → 500 | 低 | 正则/捕获 |
| market_service.py:444 / 445 | 缓存未启动 | `elif use_cache and self._cache is None` 仅打日志，缓存键为 None 时跳过写入——行为正确但日志误导 | 低 | 修正日志文案 |
| market_service.py:2044-2056 | `include_financial=True` | `self.financial_repo` 在 `if session:` 分支从未赋值（:348-360）→ AttributeError → 恒返回 error | 高 | 初始化 financial_repo |
| quality_engine.py:1285-1427 | 每 (表,规则) 重复执行同一种 `check_data_quality`，`rule.check_query` 未用、阈值硬编码覆盖 rule.threshold | 同质检查执行 N×M 次，规则粒度失效 | 中 | 每表查一次后按规则过滤评分 |
| quality_engine.py:1357-1368 | `data_type_map` 把 stock_minute/trade_calendar 映射为 daily_quotes | 分钟线按日线口径做质量检查，误判 | 中 | 修正映射 |
| quality_engine.py:897-902 | 调度器在 minute==0 时无去重创建 FULL_CHECK 任务（队列无上限） | 任务堆积、重复检查 | 中 | 调度去重标记 |
| quality_engine.py:1192 | `asyncio.timeout(...)` 为 py3.11+ API，pyproject 声明 >=3.8 | 3.8-3.10 运行 AttributeError（待确认实际版本） | 高 | 改 `asyncio.wait_for` |

## 4. 性能问题清单

| 位置 | 问题 | 影响 | 优化建议 |
|---|---|---|---|
| main_engine.py:230-256 | 日终 9 种数据类型**串行**同步，每类型 3-60 分钟 | 日终流水线总时长数小时，且当天行情就绪前策略无法运行 | 改 `batch_sync_data`（Semaphore(5) 跨类型并发，sync_service.py:1098） |
| sync_service.py:2465 / 3625 | 分钟行情/ETF分钟 **串行**逐标的循环，无并发 | 100 只 × 0.3s ≈ 30min+，且每次只同步 7 天 | 并入 `_parallel_for_each` 或按时间段并行 |
| sync_service.py:3446-3459 | stk_factor_pro 全量模式逐股按年 36 次 HTTP 串行（1990-今） | 5000 股全量同步需数十小时量级 | 按年并发 + 按日批量接口（如 trade_date 全市场） |
| handlers.py:1024 | `get_historical_quotes` 无 ts_code 时 `get_many()` **无 limit 全表扫描**（stock_daily 千万级） | OOM/超时 | 强制 ts_code 或服务端分页 |
| handlers.py:179-197 | `get_factor_data` 先分页后内存过滤日期 + 全表 `count()` | 翻页丢数据、总数错误、全表 count 慢 | 过滤下沉 SQL + 条件 count |
| handlers.py:812-839 | `get_stock_list` 过滤条件构建后未传入查询 | 搜索/市场/行业过滤全部失效 + 全表 count | 把 filters 传入查询 |
| handlers.py:1773 | `get_sync_tasks` 对每 batch 任务再查 children | N+1 查询，列表页慢 | 一次 IN 查询 |
| market/dashboard_service.py:193-211 + connection_pool.py:64-65 | 每次 dashboard 请求开 **8 个独立 DB session**（pool 10+5） | 2 个并发请求即接近耗尽连接池，其余阻塞 | 单 session 串行 8 查询或限 2-3 并行 + Redis 缓存 |
| market/market_state_service.py:48-58 | 涨跌停家数历史对 stock_daily **全表 GROUP BY**，LIMIT 无法下推 | 每次 /dashboard/state 全表聚合 | 按日预聚合/物化视图 |
| market/financial_service.py:43-51 | 分位查询对 stock_fina_indicators 全表 PERCENT_RANK | 全表排序，延迟高 | 限定最新报告期或预计算 |
| market/limit_service.py:97-119 | 连续涨停 CTE 无历史长度限制，逐股扫全部历史 | 涨停家数多时线性变慢 | 加 `trade_date >= 基准-60天` |
| market_state_classifier.py:89-141 | 全部指标 Python 级 O(n×window) 循环 | 全历史指数计算慢 | pandas rolling 向量化 |
| factor_calculators.py:1254-1267 / 2543 / 2355-2358 | Beta/OBV/波动相关仍逐日/逐元素循环 | 全市场重算慢 | rolling.cov/np.sign/groupby.rolling 向量化 |
| factor_calculators.py:2005-2752 | 38 个 ETF 因子重复计算公共中间量 | 日终任务重复开销放大 | 抽公共中间量缓存 |
| etf_factor_daily.py:129-146 | 每因子对全量 250 天×25 ETF 行 `iterrows()` 过滤今日 | 38 因子 ≈ 24 万次 Python 行迭代 | 先按 trade_date 过滤再构造 records |
| market_service.py:579-595 | `get_multiple_historical_quotes` 串行逐股 | N 股 N 次串行查询 | asyncio.gather 并发 |
| market_service.py:1511-1529 | 复权因子查询用 f-string 拼 IN 子句（限 500 个） | 代码内嵌 SQL 且截断风险 | 参数化 ANY(:codes) |
| market_service.py:1719-1747 | `_get_total_market_cap` 全表拉股票到内存求和 | 全量内存 + Python 循环 | SQL SUM |
| market/market_state_service.py:124-131 | get_style_rotation 指数查询无日期下限，每次拉取全部历史 | 数据量随年份线性增长 | 加 `trade_date >= 最新-N 交易日` |
| market/index_service.py:24-38 | MAX(trade_date) 子查询执行两次（count + items） | 轻微重复 | CTE 复用 |
| market/stock_service.py:82-99/233-235 | `_fetch_latest_data` 查最新行，但 latest_quote 优先取 klines[-1]，绝大多数请求白查一次 | 单股详情多一次无谓查询 | 删除冗余查询 |
| market/screener_service.py:95-147 | count 与分页各执行一遍完整 LATERAL 连接（~5000 股 × 3） | 双份成本 | count 与 query 合并（窗口函数） |
| clean_service.py:1392-1414 | `_fix_outlier_quotes` 逐异常日单条 UPDATE | 慢 | 批量 UPDATE |
| quality_service.py:611-616/944-949 | `get_many` 全量拉取后 Python 排序/过滤（limit 1000 页内排序） | 分页无效、内存放大 | 下推 order_by/where |

## 5. 业务闭环与 bug 清单

| 位置 | 问题描述 | 严重度(高/中/低) | 修复建议 |
|---|---|---|---|
| create_table.sql:1396-1415 vs business_models.py:939 | data_sync_tasks 缺 `parent_task_id` 列：batch 子任务创建、cancel 级联、parent_only 列表/统计查询全链路报 UndefinedColumn | 高 | 补列并同步 DDL；部署后执行 ALTER |
| engine_base.py:1922-1932 + sync_engine.py:893-924 | 引擎 `_publish_event` 把业务事件改写为 `EngineLifecycleEvent`（`engine.*` 前缀），按规范类型 `data.sync.completed` 订阅的下游收不到 | 高 | 业务事件改 `event_engine.put(具体事件)` |
| quality_engine.py:348-354 vs events/types.py:34/62/76 | 订阅字符串 `"data_sync_completed"` 等与实际 `"data.sync.completed"` 不一致 → 同步后自动质量检查永不触发，sync→quality 闭环断裂 | 高 | 用 DataEventType 常量订阅 |
| quality_engine.py:1444-1454 + clean_engine.py:503 | quality→clean 修复闭环事件类型不匹配（`quality_issue_found` vs QUALITY_ISSUE_FOUND） | 中 | 统一事件类型常量 |
| sync_engine.py:547-551/603-617 | 重试仅在异常传播路径触发，而 `_perform_sync` 捕获全部异常返回 success=False → 失败路径永不重试 | 高 | 失败结果同样进入重试决策 |
| sync_engine.py:449-498 | 并发满时"取出→放回→sleep 5s"，队头阻塞 + task_done 不配对 | 低 | 队列调度重构 |
| handlers.py:2867-2887 | handler 直改 `engine.tasks/active_tasks/stats` 注入 RUNNING 任务，与引擎队列双轨并行，引擎无完成感知，超时检查可能误杀 | 中 | 提供官方外部任务注册 API |
| handlers.py:338-343 | 研究并发上限 `available=max(1, max_concurrent-running)` → 超限仍至少启动 1 个，上限形同虚设；running_count 检查-后-动作竞态 | 中 | 超限启动 0 个并排队；DB 原子占位 |
| handlers.py:1160 vs 2857 | 批量任务 pending→running 覆盖竞态（见 §3） | 高 | 见 §3 修复 |
| handlers.py:1830-1831 + 1855 | cancel 对 pending 任务有效但 DB 更新依赖 parent_task_id 列（见首行）；cancel 端点捕获 ValueError 但 handler 抛 ValidationException → 错误码 500 | 低 | 捕获 ValidationException |
| handlers.py:1024-1082 | 历史行情"复权类型过滤"未实现：`request.adjust` 仅回显到 metadata（:1080），价格未复权 | 中 | 接入复权逻辑或明确不支持 |
| handlers.py:2852-2854 | `engine.sync_service = sync_service` 单槽共享，并发批量任务互相覆盖 | 低 | 改 task_id→service 映射 |
| daily_strategy_runner.py:86/125 | `_step_generate_adjusted_prices` 用不存在的 `self.db` → 每日复权价格生成恒失败（静默降级为在线复权兜底） | 高 | 注入 session 参数 |
| adjusted_price_generator.py:126-140 + market_service.py:1554-1564 | 后复权公式错误（÷ 应为 ×）；前复权增量写入锚定漂移（历史行不重算） | 高 | 修正公式 + 全表重锚或记录 anchor 因子 |
| quality_service.py:434-493 | `_check_financial_data_quality` 引用的 `_check_financial_data_integrity` 整段被注释（方法不存在），若被分派必 AttributeError | 中 | 删除或重写 |
| market_router.py:340/354 vs auth.py:88/119 | watchlist 用 `current_user.get("user_id","")` 但依赖返回键为 `"id"` → 恒空串，所有用户自选股共用一行、互相覆盖 | 高 | 统一取 `current_user["id"]` |
| market/dashboard_service.py:101-118 | 主力资金榜用 stock_daily 最新日查询 moneyflow（moneyflow 通常滞后）→ 恒空 | 高 | 独立查 moneyflow MAX(trade_date) |
| market/stock_service.py:325-362 | `get_stock_factor_scores` 在 EAV 表 factor_data 上按宽表逻辑，latest 行仅含 factor_value，365 天历史混算全部 factor_code 的分位 → 无意义数值 | 高 | 按 factor_code 分组逐因子分位 |
| market/market_state_service.py:51-52 + dashboard_service.py:70-71 + market_service.py:1631-1636 | 涨停/跌停用 `pct_chg ≥9.8/≤-9.8` 近似：漏 ST（±5%）、误计创业板/科创板（±20% 未触板）；与 limit_service 真实涨跌停价口径分裂 | 高 | 统一用 stock_daily_limit 或板块动态阈值 |
| market/market_state_service.py:150-162 | 行业强度 `(MAX-MIN)/MIN` 实为区间振幅非涨跌幅，波动行业被高估 | 中 | 首尾收盘价收益率 |
| market/financial_service.py:15-59 | metrics 参数未用 + 分位跨报告期混排 | 中 | 实现过滤 + 限定报告期 |
| market/stock_service.py:36-43 | is_st 通过无日期过滤 JOIN st_list 历史表 → 摘帽股可能误标（待确认同步只存当前名单） | 中 | DISTINCT ON 取最新 |
| market/moneyflow_service.py:22-43 | direction 未校验，非 "net_inflow" 一律按净流出 ASC | 低 | 白名单校验 |
| market/index_service.py:67-77 | ETF 基准查询 LIMIT 1 无 ORDER BY → 结果不确定 | 低 | 加确定性排序 |
| market/limit_service.py:132 | `up/down` 中 down=0 时 ratio=up 家数（如 60.0），语义应为 ∞/None | 低 | down=0 返回 null |
| market_service.py:470-516 | 历史行情缓存未命中时**同步直调 Tushare**（async 方法内阻塞调用 source.get_daily，未走 executor）→ 阻塞事件循环 + 查询 API 打真实数据源 | 中 | 走 executor + 失败降级空结果 |
| market_service.py:172 | 分钟线频率转换直接返回日线并告警——功能缺口 | 低 | 明确不支持或接分钟表 |
| market/__init__.py:36-65 | __all__ 与路由实际导出集合漂移（缺 10+ 个 handler） | 低 | 同步补齐 |
| sync_engine.py:754-767 | 取消时发布 `SYNC_FAILED`（代码 TODO 自认）+ `DataSyncFailedEvent(sync_type="unknown")`，`SYNC_CANCELLED`（types.py:36）从未发布 → 取消被下游当失败 | 中 | 使用 SYNC_CANCELLED 专用事件 |
| clean_engine.py:497-500 | `await self.event_engine.register_handler(...)` 对同步方法 await → TypeError 被 except 吞掉，QUALITY_ISSUE_FOUND 处理器永不注册；且 register 内部用 create_task 异步注册存在竞态 | 高 | 去掉 await + 注册等待完成 |
| sync_engine.py:705-722 | `start_sync_task` 同时经 `_publish_event`（engine.* 前缀）与 `event_engine.put(DataSyncStartedEvent)` 双发 started 事件 | 低 | 只发一种 |
| quality_engine.py:2002-2030/2076 | `_last_execution_times` 仅内存，重启后全部规则立即执行；cron 解析未实现（TODO） | 中 | 持久化执行时间 + 实现 cron |
| handlers.py:3397-3412/3462-3475 | 僵尸任务清理：仅启动时清理 30 天前/1 小时前的 pending 记录，运行中崩溃的任务无心跳回收 | 中 | 定期清理 + 心跳超时 |
| handlers.py:1618-1620 | 状态查询用 `RedisCache()` 无参构造（忽略配置 host/port），与 :2217-2222 带参构造不一致 | 低 | 统一从 settings 构造 |
| handlers.py:1855 等 | 用 naive `datetime.now()` 写 timezone-aware 列（business_models.py:953） | 低 | 统一 timezone.utc |
| handlers.py:1304-1305 | quick_sync 硬编码 estimated_stocks=5000/records=35000 | 低 | 查库或去掉 |
| market_state_classifier.py:38-42/45-59 | 硬编码 DB 回退（localhost/123456/quant_signals_dev），独立运行连错库 | 低 | 去掉硬编码回退 |
| market/stock_service.py:205-212 | `_fetch_st_risk` 查询 `LIMIT 1` 无 ORDER BY，结果不确定 | 低 | 加确定性排序 |
| market/dashboard_service.py:64-83 | `_query_breadth` 返回 dict 的 data_date 恒为 None（查询未选列），schema 亦无此字段 | 低 | 删除死字段 |

## 6. 严重度汇总表（Top 20）

| # | 严重度 | 维度 | 位置 | 问题摘要 | 修复方案摘要 |
|---|---|---|---|---|---|
| 1 | 高 | 业务bug | create_table.sql:1396-1415 vs business_models.py:939 | data_sync_tasks 缺 parent_task_id 列，批量同步/取消/任务列表全链路 UndefinedColumn | 补列 + 同步 DDL |
| 2 | 高 | 事件闭环 | engine_base.py:1922-1932 | 引擎 `_publish_event` 改写事件类型为 engine.*，规范订阅者收不到 | 业务事件直接 put |
| 3 | 高 | 事件闭环 | quality_engine.py:348-354 | 质量引擎订阅字符串与真实事件类型不匹配，自动质量检查永不触发 | 用 DataEventType 常量 |
| 4 | 高 | 死代码 | data_manager.py:57 | DataManager 无实例化点，Clean/Quality/Research 引擎 + execute_data_pipeline 整链死 | 删除或接入 initialize |
| 5 | 高 | 业务bug | sync_engine.py:583-584 | DataType 与 DataSyncType 枚举错配，引擎队列任务必 ValueError | 建映射 |
| 6 | 高 | 业务bug | clean_engine.py:1560-1567 | 清洗规则 rule_type 与 check_methods 映射零匹配，清洗空转假报成功 | 统一规则命名映射 |
| 7 | 高 | 业务bug | handlers.py:1024 | 历史行情无 ts_code 时全表扫描 + 复权未实现 | 强制 ts_code/分页 + 复权 |
| 8 | 高 | 业务bug | handlers.py:812-839 | 股票列表过滤条件未生效 + 全表 count | filters 传入查询 |
| 9 | 高 | 业务bug | handlers.py:184-197 | 因子数据分页后内存过滤 + 全表 count | 过滤下沉 SQL |
| 10 | 高 | PIT | clean_service.py:1267-1316/1403 | 停牌日前向填充假行情、除权跳空被异常覆盖、以最新价回填 | 停牌留缺失 + pre_close 基准 + 前一日价 |
| 11 | 高 | PIT/公式 | adjusted_price_generator.py:126-140 | 后复权公式错误；前复权增量写入锚定漂移 | 修正公式 + 全表重锚 |
| 12 | 高 | 假数据 | quality_service.py:292-306/357-359 | 质量检查写入硬编码假指标，质量分不可信 | 真实 SQL 聚合 |
| 13 | 高 | 取消竞态 | handlers.py:2857-2863 | token 创建前取消窗口：cancelled 被覆盖为 running | 写 running 前查 DB |
| 14 | 高 | 业务bug | market_router.py:340/354 vs auth.py | watchlist 用户键 user_id/id 不匹配，自选股串号 | 统一取 id |
| 15 | 高 | 业务bug | dashboard_service.py:101-118 | 主力资金榜用错日期基准，滞后恒空 | 独立查 moneyflow MAX |
| 16 | 高 | 业务bug | stock_service.py:325-362 | 因子分位在 EAV 表按宽表逻辑混算 | 按 factor_code 分组 |
| 17 | 高 | 性能 | main_engine.py:230-256 | 日终 9 类型串行同步数小时 | batch_sync_data 并发 |
| 18 | 高 | 分类正确性 | market_state_service.py:51-52 等 | 涨跌停 9.8% 近似口径漏 ST 误计创业板 | 统一 stock_daily_limit |
| 19 | 高 | 性能 | dashboard_service.py:193-211 | 每次请求 8 个 DB session 压垮连接池 | 单 session + 缓存 |
| 20 | 高 | 边界 | create_table.sql:2822-2834 | stock_minutes 无唯一约束，重复同步产生重复分钟数据 | 补唯一索引 |

> 备注：除上述 Top20 外，中等级问题约 30 项见 §3-§5（含 RSI fillna(50) 数值错误、minute 串行、任务队列调度、ETF 因子重复计算、硬编码 DB 口令、时区混用、`asyncio.timeout` 与 py3.8 声明不兼容（待确认运行版本）等）。审查全程只读；"待确认"项：hfq 复权口径是否为项目自定义、`ANY(:codes)` 列表参数在 asyncpg 直连下的兼容性、运行 Python 实际版本、st_list 是否仅存当前名单。

## 7. 业界标准对照

> 本节将 §2-§6 已列问题按业界公认标准归类，标注判定依据（标准名 — 条款/坏味道）。判定标准来源：Google 工程实践 Code Review（eng-practices）、Robert C. Martin《Clean Code》、SOLID 五原则、Martin Fowler《重构》坏味道清单、PEP 8 / Brett Slatkin《Effective Python》、ETL 工程实践（幂等/断点续传/限流/批处理）、数据工程最佳实践（质量门禁/PIT/可观测性/性能）。

### 7.1 Google Code Review 规范（Code Health）

> Google eng-practices 核心：CL 保持小、可读、无死代码、无未使用参数/变量、命名准确、测试覆盖、不留无用抽象。

| 依据 | 对应问题（位置） | 判定说明 |
|---|---|---|
| Code Health — 不引入死代码 | §2 清单全部 19 项（data_manager.py:57、limit_service.py:142 等） | 死类/死函数/未用参数应在 PR 中移除而非沉淀进主干 |
| Code Health — 命名与实参一致 | market_state_classifier.py:172 | `_calc_volume_ratio(closes, ...)` 把收盘价当成交量传入，函数名与实参语义不符 |
| Code Health — 生产代码不含测试替身 | quality_service.py:292-306 / 357-359 | 硬编码"假指标"返回值是测试桩误入生产路径（§1.3） |
| Code Health — 可测试性 | sync_service.py:1823-1920（90 分位批量路径）、handlers.py:2857-2863（取消竞态窗口） | 关键分支逻辑无单测覆盖（tests/ 目录仅 test_data_router、test_real_sync_to_database 两个文件） |

### 7.2 Clean Code（Robert C. Martin）

| 依据 | 对应问题（位置） | 判定说明 |
|---|---|---|
| 小函数 / 单一职责（Long Method） | sync_service.py:2160-2420（`_sync_daily_quotes` 260+ 行）；handlers.py:2810-3063（`_execute_async_data_sync` 250+ 行） | 一个函数承载日期推断/并发调度/统计/事件/缓存多职责，违反"函数只做一件事" |
| 错误处理显式化（失败要响亮） | sync_service.py:3796-3797；sync_engine.py:721-722/766-767；handlers.py:3015-3020 | `except Exception: pass` 吞噬异常，任务假成功、数据静默缺失（§3/§5） |
| 无注释掉的代码 | sync_service.py:3567-3581/3811-3825 等 `# [DEAD]`/整段注释块 | 注释掉的代码应删除，历史由 VCS 保存 |
| 消除魔法数字 | quality_service.py:402-403（缺失估算系数 100）；market_state_service.py:51-52（9.8 涨停阈值）；limit_service.py:132 | 阈值/系数内嵌且多处不一致，应提炼命名常量统一管理（§5 口径分裂即由此） |
| 命名准确 | create_table.sql:1407-1409 `records_processed` 与 `records_succeeded` 语义重叠；sync_service.py:2008-2013 两字段互相错位写入 | 字段名与写入语义不一致，易被误用（§1.1） |

### 7.3 SOLID 原则

| 依据 | 对应问题（位置） | 判定说明 |
|---|---|---|
| SRP — 单一职责 | data_manager.py:57（一个 Manager 编排 sync/clean/quality/research 四类引擎）；daily_strategy_runner.py:22（同步+复权+信号+策略四职责且多为 stub） | 职责混装导致大半实现无法独立启用、沦为死代码（§2） |
| OCP / 信息隐藏（封装） | handlers.py:2867-2887 直改 `engine.tasks/active_tasks/stats` 内部状态；clean_engine.py:1633 调用 clean_service 私有方法 `_clean_cache_after_cleaning` | 跨对象篡改内部状态/调用私有 API，破坏封装，是引擎双轨状态不一致（§5）的根源 |
| DIP — 依赖倒置 | market_service.py:1781-1794（`_get_index_performance` 内部自建 session）；handlers.py:2852-2854（引擎单槽挂 service，并发互相覆盖） | 隐式依赖/全局单槽，难以注入替换与并发隔离，测试困难 |

### 7.4 Martin Fowler《重构》坏味道清单

| 依据 | 对应问题（位置） | 判定说明 |
|---|---|---|
| Duplicated Code（重复代码） | sync_service.py 20+ 个 `_sync_*` 复制 `_process_one` 骨架（2160/2504/2579/2664/2868…）；`_clean()` 在 market_service.py:26、stock_service.py:26、limit_service.py:23 三份相同实现 | 复制粘贴式同步方法：改一处漏多处，`_sync_audit_opinion` 误用 StockExpress 列集合（sync_service.py:4870）即复制错误的实证 |
| Long Method（过长函数） | 见 7.2 | — |
| Speculative Generality（夸夸其谈的通用性） | sync_engine.py:107-1026 队列/优先级/重试/超时全套机制从未被 API 路径使用；events/factor_calculation_events.py"v4.0 预留"；market/events/market_events.py 4 个无人订阅事件 | 为假想需求设计的抽象全部空转（§2），符合 Fowler"只为当下需求做设计"的告诫 |
| Dead Code（死代码） | §2 清单 19 项（含 limit_service.py:142 `_count_consecutive` 被窗口函数版替代后未删除） | 典型"新实现上线、旧实现未删" |
| Comments（误导性注释） | main_engine.py:357/362/369 调度时间：FIXME(16:30)/注释(20:00)/配置(21:20)/日志(22:42) 互矛盾；sync_service.py:1043-1048 文档称串行实际并行 | 注释与代码漂移比没有注释更危险，应按 Fowler 建议删误导注释 |
| Data Clumps（数据泥团，低优先） | handlers.py:320-343 并发计数/排队逻辑散落多处（running_count 三处计算） | 可抽为统一的并发控制对象 |

### 7.5 PEP 8 / Effective Python（Brett Slatkin）

| 依据 | 对应问题（位置） | 判定说明 |
|---|---|---|
| Effective Python — 避免共享可变状态 | utils/factor_calculator.py:187-188 类级 `FACTOR_CONFIGS` 被 `params.update(kwargs)` 原地修改 | 与"默认参数共享可变对象"同类陷阱：一次计算污染所有实例（§3） |
| Effective Python — 使用 tz-aware 时间 | handlers.py:1855 等 naive `datetime.now()` 写入 tz-aware 列（business_models.py:953） | 时区混用，跨时区部署/夏令时场景出错（§5） |
| Effective Python — 异常要显式 | 见 7.2 错误处理 | — |
| Effective Python — 版本特性声明 | quality_engine.py:1192 `asyncio.timeout`（py3.11+）vs pyproject.toml 声明 `>=3.8` | 使用了未声明的语言版本特性（待确认实际运行版本） |
| PEP 8 — 模块级副作用 | utils/factor_calculator.py:29 `warnings.filterwarnings('ignore')` 全局屏蔽 | 导入即屏蔽整个进程警告，应使用 `warnings.catch_warnings()` 局部化 |
| PEP 8 — 表达力与可读性 | sync_service.py 大量 `;` 压缩多语句行（如 3979、4211）、单行 if 赋值 | 牺牲可读性换取行数，不符合"显式优于隐式" |

### 7.6 ETL 业界实践（幂等 / 断点续传 / 限流 / 批处理）

| 依据 | 对应问题（位置） | 判定说明 |
|---|---|---|
| 幂等（任意次重跑结果一致） | create_table.sql:2822-2834 `stock_minutes` 无唯一约束 → 重复同步产生重复行（§1.1） | 违反 ETL 黄金法则；`batch_insert` upsert 依赖唯一约束反射（hyper_repository_base.py:146-169），无约束时退化为不设防插入 |
| 断点续传 | sync_engine.py:171-174/685-696 任务队列/状态纯内存，进程重启丢全部任务 | 违反断点续传要求；服务层四模式推断（sync_service.py:1519-1576）达标，引擎层缺失 |
| 限流（上游配额保护） | sync_service.py:1753-1755 令牌桶在请求完成后才取令牌；sync_engine.py:547-551/603-617 重试仅在异常传播路径生效（实际永不触发） | 突发窗口不控速 + 失败重试失效，属限流/重试机制不完整（§1.2/§5） |
| 批处理（批量写入） | hyper_repository_base.py:103-173 chunk=1000 规避 32767 参数上限 | ✅ 达标项 |
| 增量 vs 全量策略 | sync_service.py:1519-1576 四模式智能推断 | ✅ 达标项 |
| 任务血缘与审计 | create_table.sql:1396-1415 缺 `parent_task_id` 列（ORM 有 business_models.py:939） | 父子任务血缘断裂，无法追溯批量任务构成（§3/§5 首行） |

### 7.7 数据工程最佳实践（质量门禁 / PIT / 可观测性 / 性能）

| 依据 | 对应问题（位置） | 判定说明 |
|---|---|---|
| 数据就绪门禁（质量闸门） | main_engine.py:303-329 驱动策略前校验 stock_daily 最新交易日+条数≥4000 | ✅ 达标项，符合业界"数据就绪检查"范式，建议推广到其他下游 |
| 质量指标必须真实可验证 | quality_service.py:292-306/357-359/402-403 硬编码假指标写入 data_quality_checks 表 | 违反可验证性：虚构分数污染质量表，前端展示假质量分（§1.3） |
| PIT / 不臆造缺失数据 | clean_service.py:1267-1316 停牌日前向填充假行情；:1403 以"最新价"回填异常日 | 数据工程红线：缺失应显式标记/保持缺失，禁止用假值充数（§1.5） |
| 复权基准一致性 | adjusted_price_generator.py:62-73 前复权增量写入锚定"当次最新因子"，历史行不重算 | 表内 qfq 序列跨期不在同一基准，属数据一致性缺陷（§1.5） |
| 可观测性 / 数据新鲜度标记 | market_state_service.py:36-45 无新鲜度标记，过期数据静默展示；sync_engine.py:754-767 取消被发布为失败事件 | 下游无法判断数据时效；事件语义失真（§5） |
| 大数据查询性能（索引/预聚合） | market_state_service.py:48-58 涨跌停统计全表 GROUP BY；dashboard_service.py:193-211 每请求 8 连接 | 应走索引/按日预聚合/物化视图（§4） |
| 凭据安全基线 | market_state_classifier.py:38-42 硬编码明文 DB 口令（postgres/123456）作回退 | 凭据不得入源码（§3），无配置时应显式报错 |
