# 06 account + analysis + monitor + system 模块审查报告

> **审查基准日期**：2026-08-14（代码以当前工作区为准，git 分支 dev）
> **审查性质**：只读审查，未修改任何业务代码；唯一写入物为本报告。
> **审查文件清单**：account 模块 32 个 .py（engines/settlement_engine、tasks/settlement_tasks、reconciliation_tasks、services×5、calculators×3、managers×2、events×4、utils×2 等）；analysis 模块 46 个 .py（engines、analyzers×6、services×5、events×8、tasks×2、managers×2、visualizers×2 等）；monitor 模块 39 个 .py（engines×4、alerters×3、collectors×3、services×5、tasks×2、events×5、managers×2 等）；system 模块 29 个 .py + `api/dependencies/auth.py` + `shared/security/` 5 个 .py，合计 **152 个目标文件**；交叉核对约 20 个关联文件（core/engines/base/engine_base.py、core/engines/system/event_engine.py、shared/config/config_manager.py、shared/database/models/business_models.py、utils/core_utils/math_utils/financial_calculator.py、api/routers/system_router.py、modules/strategy/engines/performance_tracker.py、modules/trade/engines/execution_engine.py、config.yaml、docs/sql/create_table.sql 等）。
> **审查方法**：通读 + 全库 grep 引用验证 + 跨模块事件/字段核对。

---

## 1. 业界对比分析

### 1.1 日终结算 vs 券商清算最佳实践（幂等/防重/对账）
- **幂等性不足**：`account_daily_performance` 已有 `(account_id, trade_date)` 幂等 upsert（`modules/account/tasks/settlement_tasks.py:545-573`），但结算记录 `account_statements` 通过 `create_settlement_record`（`shared/database/repositories/account/asset/account_repo.py:804`）每次**无条件 INSERT**，无唯一约束 → 同日重复执行结算会产生多条结算记录。券商清算实践要求"结算批次号 + (account_id, trade_date, type) 唯一键 + 先查后插/状态机"。
- **防重仅靠内存防抖**：`SettlementEngine` 5 分钟防抖（`settlement_engine.py:31-32,104-142`）为进程内存态，多实例/重启即失效；且防抖定时器键与账户键不一致（见 §5-3），合并逻辑本身有缺陷。
- **对账闭环断裂**：日终对账 `daily_reconciliation_task` 用 `account.account_id` 取值（`reconciliation_tasks.py:92`），而 `Account` 模型只有 `id` 字段（`business_models.py:388`）→ AttributeError，对账 100% 失败；"与券商对账"实际从本地库自取自比（`reconciliation_tasks.py:289-367`），无真实券商数据源。
- **跨日时间戳**：结算事件携带的 `settlement_date` 被存成 isoformat **字符串**（`settlement_events.py:56`），引擎原样透传（`settlement_engine.py:93`），到 `_get_net_deposit` 的 `datetime.combine(trading_day,...)`（`settlement_tasks.py:429-430`）直接 TypeError（见 §5-1）。

### 1.2 绩效指标计算 vs 业界标准（年化/夏普/卡玛/回撤口径）
- **夏普口径三处不一致**：① `pnl_calculator.py:355-368` 日超额=日收益-rf/252、`np.std` 默认 ddof=0（总体标准差）；② `FinancialCalculator.sharpe_ratio`（`financial_calculator.py:216-241`）把年化 rf 转成**日** rf 后从**年化**收益中扣除（维度错误，rf 调整≈0）；③ `exposure_calculator.py:467-471` 完全不含无风险利率。同一账户三处夏普不可比。业界标准：年化超额/年化波动（样本标准差 ddof=1）。
- **回撤符号口径不统一**：`pnl_calculator.py:388-396`、`risk_analyzer.py:744-747`、`financial_calculator.py:308` 输出**负值**回撤，而 `performance_service.py:281`、`statistic_utils.py:126-138`、`position_processor.py:747-759` 输出**正值**；`comparison_service.py:440-444` 按"越小越好"排名，在负值口径下**排名方向反转**。
- **年化基准不一致**：`performance_service.py:181,409` 用自然日/365.25；`pnl_calculator.py:324-328` 用自然日/365；`FinancialCalculator` 用交易日/252 —— 同一平台三套年化。
- **日盈亏口径错误**：`pnl_calculator.py:182-195` 的"日盈亏"把**当前全部未平仓累计浮盈**计入当日（position_pnl_change 实为累计值），与 `performance_service` 的 `pct_change` 日收益口径不一致。
- **无卡玛比率**：`PerformanceMetrics` 虽含 calmar_ratio 字段（`analysis/models.py:36`），但 account 侧 `pnl_calculator.calculate_account_performance`（`pnl_calculator.py:288-339`）根本不返回卡玛；卡玛仅 FinancialCalculator 一处实现。
- **绩效逐日重算无缓存**：`performance_service`/`attribution_service` 每次调用全量重算（见 §4），业界通常落库快照+增量计算。

### 1.3 告警引擎 vs Alertmanager 模式（去重/分组/静默/升级）
| 能力 | Alertmanager | 本项目现状 |
|---|---|---|
| 去重 | label fingerprint + repeat_interval | **失效**：`AlertService.check_duplicate` 默认 `within_hours=0`（`alert_service.py:95`），SQL 生成 `created_at >= now`（`monitor_alert_repo.py:134-138`）恒查不到 → 去重永不命中 |
| 分组 | group_by + group_wait | **无**：逐条创建、逐渠道分发（`alert_manager.py:38-102`） |
| 静默 | silence API | **无**：仅 `AlertStatus.SUPPRESSED` 枚举值（`constants.py:21`），无实现 |
| 升级/重复提醒 | repeat_interval | **无**：仅发送时 3 次退避重试（`alert_manager.py:77-88`），无时间级升级 |
| 抑制 | inhibit_rules | **无** |
| 路由 | routing tree | **无**：渠道硬编码（`alert_engine.py:305` 交易信号强制 wechat）或默认 email |
| 状态闭环 | resolved/expired | **无**：告警永为 active，清理逻辑永不执行（`alerting_tasks.py:32-38`） |
| 落库 | 批量 | 单条告警 4~6 次 DB 往返（见 §4） |
| 事件一致性 | 统一事件模型 | 发布侧经 `engine_base.py:1922-1940 _publish_event` 包装成 `EngineLifecycleEvent`，订阅侧用裸字符串（`alert_engine.py:74-85`），**两端对不上**（见 §5-13） |

### 1.4 JWT 认证 vs 业界最佳实践（refresh 轮换/黑名单/锁策略）
- **密钥管理**：`SECRET_KEY` 默认值为公开占位符 `"your-secret-key-here-change-in-production"`（`shared/config/config_manager.py:114`），`.env` 亦沿用占位值（待确认行 ~111）→ HS256 下任何人可伪造任意用户/超管 token。
- **refresh 轮换缺失**：`JWTManager.refresh_access_token`（`shared/security/jwt_handler.py:234-262`）仅签发新 access，**不轮换 refresh、无重用检测、无 jti**；7 天长命凭据无法吊销。
- **黑名单链路断裂**：登出路由传字面量 `"unknown"` 进黑名单（`api/routers/system_router.py:518-523`）；主认证链 `get_current_user`（`api/dependencies/auth.py:58-255`）**全程不查黑名单**；`modules/system/auth/jwt_handler.py:88-100,118-129` 的 Redis 路径在 async 环境失效（事件循环运行时跳过 Redis 只查内存）。
- **过期边界**：`leeway` 被放进 `options` 字典（`shared/security/jwt_handler.py:215`），PyJWT 的 leeway 是顶层参数 → 恒为 0，无时钟偏差容忍；签名有效但缺 `exp` 的 token 通过校验后 `payload["exp"]` KeyError → 500（`auth.py:163`）。
- **登录锁策略未接入**：`UserManager.record_login_failure`（`user_manager.py:75-110`）全库无调用（grep 验证），登录失败锁定、在线会话、并发登录控制**全部未接线**；`/auth/login` 无速率限制。
- **开关默认关闭**：`config.yaml:15` `AUTH_ENABLED: false` 且 `environments.production` 继承 defaults（`config.yaml:126-129`）→ 生产默认无认证。

---

## 2. 死代码清单

| 位置(文件:行) | 类型 | 说明 | 清理建议 |
|---|---|---|---|
| modules/monitor/alerters/email_alerter.py:15 | 类 | EmailAlerter 全库仅 `alerters/__init__.py:4,8` 引用；`alert_engine.py:87-128` 只注册 wechat/dingtalk，`email_enabled`(alert_engine.py:95) 读了不用 | 删除或接入注册并补 SMTP 配置 |
| modules/monitor/collectors/log_collector.py:17 | 类 | LogCollector 无调用方 | 删除或接入真实日志采集 |
| modules/monitor/managers/health_manager.py:17、events/health_events.py:14、services/log_service.py:17 | 类 | 均仅 `__init__.py` 导出，无发布/订阅方（log_service 还查告警表冒充日志） | 删除；日志查询改接 system 模块 LogService |
| modules/monitor/tasks/monitoring_tasks.py:14,32,53,71 + alerting_tasks.py:15,47,82 | 函数 | 7 个 scheduled_* 无调度器注册；且调用的 `RiskEngine.check_and_publish`、`AlertManager.retry_failed` 不存在（grep 无定义） | 删除或实现对应方法后接线 |
| modules/monitor/models.py:1-（整文件） | 模型 | 无任何 import；AlertRule/Alert 等与 constants.py 枚举重复定义 | 删除，统一用 constants + DB 模型 |
| modules/monitor/constants.py:87-103 EventType | 枚举 | 全库无引用（各引擎用裸字符串） | 全模块改用该枚举 |
| modules/monitor/engines/alert_engine.py:197-227 trigger_alert、events/alert_events.py:57-71、system_events.py:54-60、system_collector.py:73-99、metric_collector.py:62-87、handlers.py:50-71 | 方法/事件 | 均无调用方；get_risk_alerts 已被 301 重定向替代 | 删除 |
| modules/monitor/services/business_service.py:110-134、utils/metric_utils.py:66-74、alert_service.py:186-204 | 方法 | 无调用方 | 删除（render_template 保留可作扩展） |
| modules/system/managers/user_manager.py:14-135 | 类 | 登录锁定/在线会话/并发控制全未接入登录流程（auth_service.login 不调用） | 接入 auth_service 或删除 |
| modules/system/managers/permission_manager.py:24-88 | 类 | 无调用；`:69` 读取不存在的 `permission_type` 属性；`:73-74` 无权限默认授予 `{"data":{"can_read"}}` 违背最小权限 | 删除或修正属性并接入 auth.py |
| modules/system/auth/authorization.py:23-48 | 类 | 自带 DEPRECATED 注释，无调用 | 删除 |
| modules/system/auth/jwt_handler.py:32-58 verify_access_token | 函数 | 仅 auth/__init__.py 导出，路由全走 api/dependencies/auth.py | 合并到主认证链或删除 |
| modules/system/services/task_service.py:21-214 + events/task_events.py:9-63 | 服务/事件 | 无调用方 | 删除 |
| modules/system/events/auth_events.py、user_events.py、config_events.py、task_events.py | 事件类 | 仅 auth_service.py:194-245 构造但 `event_engine=None` 从不投递（handlers.py:388-390），无订阅方 | 删除或接线 |
| modules/system/constants.py:37-38 | 常量 | ACCESS_TOKEN_EXPIRE_MINUTES=60 无引用（死常量且与其他配置不一致） | 删除 |
| api/dependencies/auth.py:257-372 optional_auth/require_permission/require_superuser/PermissionRequired 等 | 依赖 | 全库路由仅用 get_current_user + 内联 `_require_admin` | 删除或统一接入 |
| shared/security/encryption.py:152-545 RSACipher/EncryptionManager | 类 | 无调用 | 删除 |
| shared/security/password.py:71-90,93-124,227-231,313-317 | 函数 | 无调用 | 删除 |
| shared/security/audit.py:519-702 audit_log 装饰器、jwt_handler.py:297-340 | 函数 | 无调用 | 删除 |
| modules/analysis/analyzers/performance/return_analyzer.py:17、risk_analyzer.py:21、trade/execution_analyzer.py:17、cost_analyzer.py:17、attribution/brinson_attribution.py:14 | 类×5 | 仅各 `__init__.py` 导出，无调用（backtest 另有自己的 RiskAnalyzer） | 删除或接入 performance_service |
| modules/analysis/analyzers/attribution/factor_attribution.py:16 | 类 | 被 attribution_service.py:39,93 引用，但因子数据源缺失导致**功能不可达**（见 §5-19） | 对接真实因子源后启用 |
| modules/analysis/managers/analysis_manager.py:40、report_manager.py:23 | 类 | 无实例化；analysis_manager.py:65-71 给 PerformanceService 传不存在的 backtest_repo 参数 | 删除或修正 |
| modules/analysis/tasks/daily_analysis_tasks.py:22、report_tasks.py:19 + visualizers/ 整层 | 类/层 | 仅 tasks/__init__.py 导出，无调用 → visualizers 整层随之为死代码 | 删除或接线（含其内部递归/公式 bug） |
| modules/analysis/services/attribution_service.py:909-936 _perform_factor_regression | 方法 | 从未被调用 | 删除 |
| modules/account/calculators/exposure_calculator.py:34、utils/position_processor.py:17 | 类 | 无实例化点 | 删除或接入 |
| modules/account/managers/account_manager.py:31 | 类 | 仅 managers/__init__.py 导出；内含双倍初始资金、类型错误等潜伏 bug | 删除或接入并修复 |
| modules/account/events/position_events.py:160,255,385、reconciliation_events.py:12、settlement_events.py:277,404、balance_events.py:91,166,258 | 事件类×7 | 全库无实例化（仅 events/__init__.py 导出）；且事件类型硬编码与枚举不符（见 §5-16） | 删除或接入产生方 |
| modules/account/services/account_service.py:603-651 record_daily_settlement | 方法 | 与 settlement_tasks._upsert_daily_performance 功能重复；且漏写 NOT NULL 的 account_id（business_models.py:438）→ IntegrityError | 删除，统一走结算任务幂等 upsert |
| modules/analysis/constants.py:46-47 CARINO/FRONGELLO、:23 AnalysisType.TRADE="events" | 常量 | 无引用；TRADE 值写错（应为 "trade"） | 修正/删除 |

---

## 3. 边界情况清单

| 位置 | 触发场景 | 现状行为 | 风险等级 | 修复建议 |
|---|---|---|---|---|
| modules/account/tasks/settlement_tasks.py:108-120 | 同日结算重复执行（手动+定时+成交触发并发） | create_settlement_record 无唯一约束 → 重复结算记录；account_daily_performance 有幂等但结算记录无 | 高 | 加 (account_id, trade_date, settlement_type) 唯一索引 + 先查后插 |
| settlement_engine.py:92-96 + settlement_tasks.py:429-430 | 成交后事件触发结算 | event.data.settlement_date 为 isoformat 字符串 → `datetime.combine(str)` TypeError → 该账户结算必失败 | 高 | 引擎入口统一 `date.fromisoformat` 转换 |
| settlement_engine.py:93 + _process_events | 事件队列负载 | `_run_settlement` 类型标注 date 实收 str，下游查询依赖隐式转换 | 中 | 类型转换前置 |
| settlement_engine.py:117-135 | 5 分钟内同一账户重复触发 | 防抖 timer 键用 `",".join(ids)`，取消时按单账户 `pop` → 旧 timer 永不取消，可能双执行 | 中 | timer 键与账户一一对应并维护映射 |
| modules/strategy/engines/performance_tracker.py:48-51 | 补跑/跨零点结算 | 读 `trade_date` 而事件只有 `settlement_date` → 恒回退 today，绩效日期错误 | 高 | 统一读 settlement_date |
| modules/analysis/tasks/daily_analysis_tasks.py:192-194 | 节假日后的首个交易日 | prev_date 用自然日 -1（非上一交易日）→ 日收益/日盈亏错误 | 中 | 用交易日历取上一交易日 |
| modules/monitor/services/alert_service.py:95 + monitor_alert_repo.py:134-138 | 阈值持续超限（告警风暴） | dedup `within_hours=0` → `created_at>=now` 恒不命中 → 每 10-30s 落一条同内容告警 | 高 | hours<=0 时改为查最近 N 条活跃告警；按 title+source+type+状态去重 |
| modules/monitor/engines/alert_engine.py:48 | 告警风暴队列满 | `await self._event_queue.put()` 无限阻塞生产者 | 中 | put_nowait + 丢弃/降级策略 |
| modules/monitor/managers/alert_manager.py:52 | 未显式指定渠道的告警 | 默认 `["email"]` 但 email 告警器未注册 → 只落库不通知 | 高 | 默认渠道与已注册渠道求交集并告警 |
| monitor_alert_repo.py:72 vs business_models.py:1585 | 任意带 metadata 的告警 | 写入键 metadata 与列 metainfo 不符 → 静默丢弃风险详情/信号载荷 | 高 | 键名改 metainfo 或模型加列 |
| monitor_alert_repo.py:176-179 | API 认领/解决告警 | acknowledged_at/resolved_at 写 isoformat 字符串到 DateTime 列 → 类型错误 | 高 | 写 datetime 对象 |
| repository_base.py:232-236 + monitor_alert_repo.py:134 | 任意告警/记录创建 | 用 naive `datetime.now()` 覆盖模型 aware UTC 默认（business_models.py:1593），且不在 _convert_record_datetime 转换清单 → 时区口径混乱，跨时区部署下比较/展示错位 | 中 | 统一 `datetime.now(timezone.utc)` |
| modules/monitor/tasks/alerting_tasks.py:32-38 | 定时清理 | get_active_alerts 只返回 active，循环内判 `status=="resolved"` 恒 False → 清理永不执行 | 中 | SQL 批量按 resolved_at 删除 |
| api/dependencies/auth.py:101-130 | AUTH_ENABLED=false 且无 admin 用户 | 自动创建 superadmin，密码明文 "dev-no-auth-mode"（role=admin） | 高 | 随机 bcrypt 种子密码 + 仅 dev + 首登改密 |
| api/dependencies/auth.py:133-145 | 认证关闭且 DB 查询失败 | 回退返回硬编码超管身份（固定 UUID、role=super_admin、`*:*` 权限） | 高 | DB 不可用直接 503 |
| api/dependencies/auth.py:163 | 签名有效但缺 exp 的 token | verify_token 不强制 exp，随后 `payload["exp"]` KeyError → 500 | 中 | options={"require":["exp"]} |
| modules/account/services/cash_service.py:597 | 查询资金流水 | 用 `model.user_id == account_id` 过滤（写入侧存 user_id=account.user_id）→ 账户维度永远查不到 | 高 | 按 user_id 查询或加 account_id 列 |
| modules/account/services/position_service.py:237-244 | 卖出调仓 | 校验写 `position.volume < volume_change`（正数比负数恒 False）→ 卖出校验被绕过且负数变成增仓 | 高 | 统一符号约定并修复校验 |
| modules/account/calculators/exposure_calculator.py:396-397 | 存在持仓时计算风险指标 | `Decimal('1') - float` → TypeError 必然崩溃 | 高 | 统一 Decimal/float |
| exposure_calculator.py:488-491 | 计算 beta/alpha | 收盘价截断 n 个后 diff 得 n-1 收益 → 长度恒不等 → beta/alpha 恒 None | 中 | 截断 n+1 或取交集 |
| modules/account/managers/account_manager.py:346 | 配置了 message_producer 时结算 | `daily_pnl["total_pnl"]` 下标访问 pydantic 模型 → TypeError | 高 | 改 `daily_pnl.total_pnl`（:358 同文件已有正确写法） |
| modules/analysis/tasks/daily_analysis_tasks.py:513 | 每日风险任务 | `@staticmethod` 却声明 self 且被实例调用 → NameError | 高 | 去掉 @staticmethod |
| modules/analysis/services/attribution_service.py:722,833 | Brinson 归因 | 交互效应 = -配置-选择 → 三项和恒 0 ≠ active_return，分解不自洽 | 高 | 用 active_return-alloc-selec |
| attribution_service.py:585-588 | 行情返回倒序 | `_get_stock_return` 取 quotes[0]/[-1] 未排序，与 :630-633 显式排序不一致 | 中 | 统一排序 |
| modules/analysis/services/performance_service.py:340-345 | account_id="default" 且账户不存在 | 返回普通 dict 而非 PerformanceMetrics → get_performance_summary 调 to_dict() AttributeError | 中 | 返回退化对象 |
| performance_service.py:976 | 旧版 pandas | `resample('ME')` 需 pandas≥2.2（Python 3.8 栈可能旧版）→ 月度收益计算抛错 | 中（待确认 pandas 版本） | 兼容 'M' 或升级 |
| modules/account/managers/account_manager.py:327-328 | 1 月 1 日跑月度统计 | `replace(month=12, day=1)` 得到当年 12 月 1 日（未来）→ start>end | 中 | 跨年处理 |
| modules/analysis/analyzers/trade/cost_analyzer.py:799 | 滑点分析 | `stats['est_volatility']` 的 stats 是 scipy 模块而非 :790 的 aStats → TypeError | 高 | 改 `aStats['est_volatility']` |
| modules/analysis/tasks/report_tasks.py:503 | 收益汇总 | `total_return=(1+sum(r))**len(r)-1` 公式错误（应为 prod(1+r)-1）→ 指数级虚高 | 高 | `np.prod(1+r)-1` |
| modules/analysis/services/comparison_service.py:440-444 | 策略对比排名 | max_drawdown 负值口径下"越小越好"→ 排名方向反转 | 中 | 统一符号后按绝对值排序 |

---

## 4. 性能问题清单

| 位置 | 问题 | 影响 | 优化建议 |
|---|---|---|---|
| modules/account/tasks/settlement_tasks.py:89,191,269 | 结算逐账户顺序处理 + `get_active_accounts(limit=100000)` 全量 | 账户多时分钟级 | 分批 + asyncio 并发 + SQL 批量重估 |
| settlement_tasks.py:471-474 | `_get_day_trade_summary` 每笔卖单调 `_get_position_cost` 全量查持仓（N+1） | 成交多时 DB 往返爆炸 | 一次性取持仓成本映射 |
| modules/account/calculators/pnl_calculator.py:85,176,240,317 | 每笔卖出交易重复 `_get_cost_price` 全量查持仓（N+1） | 同上 | 缓存持仓快照一次 |
| modules/account/services/fee_service.py:236,249,349,404 | 同一区间重复拉 3 次全量交易 + 每笔再查费用（N+1） | 交易量大时秒级延迟 | 一次取数 + 批量 in_ 查询 |
| modules/analysis/services/performance_service.py:109,305 + attribution_service.py | 绩效/归因每次全量重算，无任何缓存 | 高频 API 重复计算 | 按 (entity,start,end) 加缓存 |
| attribution_service.py:522-524,559,704,715,778,798 | 组合/基准每只股票顺序 await 一次行情查询（基准 300 只 = 300 次串行） | Brinson 归因分钟级 | asyncio.gather 或批量查询 |
| performance_service.py:519 | compare_multiple_strategies 在**同一 AsyncSession** 上 asyncio.gather 并发查询 | AsyncSession 非并发安全 → GreenletError/竞态 | 每任务独立 session |
| modules/analysis/analyzers/performance/risk_analyzer.py:1049-1058,630-631 | GARCH 同步拟合阻塞事件循环；Monte Carlo 每请求 10 万次 randn 无缓存 | 事件循环抖动、CPU 浪费 | 移入 to_thread + 缓存结果 |
| api/dependencies/auth.py:184,202,205 | 每请求 3 次 DB：get_user + update_last_login（每请求 UPDATE 写放大）+ 权限查询 | 高频接口 DB 写放大 | last_login 降频/缓存；权限码缓存 |
| modules/monitor/managers/alert_manager.py:67-99,170 | 单条告警 4~6 次 DB 往返（去重查 50 行 + INSERT + 每渠道 INSERT + UPDATE + mark_sent）逐条串行 | 风暴期 DB 压力放大 | 批量落库 + EXISTS 去重 + 合并状态更新 |
| modules/monitor/collectors/system_collector.py:46,53 | `psutil.cpu_percent(interval=0.1)` 同步阻塞在 async 循环内每 10-30s 一次，且每个 /system/metrics 请求再采一次 | 事件循环抖动、API 延迟 | interval=0 + 走引擎缓存 |
| modules/monitor/services/business_service.py:88-91 | `get_many(limit=1000)` 拉 1000 条订单在 Python 里数状态 → total 恒 ≤1000 | 指标失真 + 内存浪费 | SQL 聚合 COUNT/GROUP BY |
| modules/monitor/tasks/alerting_tasks.py:32 | `get_active_alerts(limit=10000)` 全量载入 | 内存与锁开销 | SQL 批量清理 |
| modules/account/calculators/exposure_calculator.py:250-262,300-321,616-619 | 每只持仓一条 SQL + 每只重复算相关矩阵（O(n²)）+ 重复调 4 次全量计算 | 持仓多时明显卡顿 | 批量 IN 查询、矩阵提出循环、复用 risk_metrics |
| modules/analysis/tasks/daily_analysis_tasks.py:179-183 等 | `get_many(limit=100)` 硬编码截断活跃账户 | 100 账户后静默不分析 | 分页遍历 |
| modules/monitor/engines/alert_engine.py:140-155 | 单消费者逐条串行处理告警 | 高吞吐积压 | 多 worker/批量消费 |

---

## 5. 业务闭环与 bug 清单

| 位置 | 问题描述 | 严重度(高/中/低) | 修复建议 |
|---|---|---|---|
| settlement_engine.py:93 + settlement_tasks.py:429-430 | 结算事件日期为字符串 → datetime.combine TypeError，成交触发结算全账户失败（execution_engine.py:267-271 为触发源） | 高 | 引擎入口 date.fromisoformat 统一转换 |
| settlement_engine.py:173-187 + settlement_tasks.py:141-154 | AccountSettlementCompletedEvent **双发**（引擎与任务各发一次），下游 performance_tracker 被触发两次 | 高 | 二选一，引擎只收不发或任务不发 |
| modules/account/tasks/reconciliation_tasks.py:92 | `account.account_id` 属性不存在（Account 只有 id）→ 日终对账 100% 失败 | 高 | 改 `account.id` |
| modules/strategy/engines/performance_tracker.py:48 | 读 `trade_date` vs 结算事件 `settlement_date`（线索①确认）→ 恒回退 today | 高 | 统一字段名 |
| api/routers/system_router.py:518-523 + api/dependencies/auth.py:58-255 | 登出黑名单传字面量 "unknown"，且主认证链不查黑名单 → **登出完全无效** | 高 | Depends 取真实 token + 主链强制黑名单检查 |
| shared/config/config_manager.py:114 | JWT SECRET_KEY 为公开占位符（.env 同值，待确认行~111）→ 可伪造任意 token | 高 | 强随机密钥 + 环境注入 + 轮换 |
| modules/system/auth/authentication.py:97-101 | 改密/旧 AES 自动迁移时 `migrated` 被当新密码存储 + update_password 二次加密（user_repo.py:106-111）→ 下次登录必失败（双重加密 bug） | 高 | update_password 直接存传入值，migrated 分支只回写哈希 |
| api/dependencies/auth.py:105-106 | AUTH_ENABLED=false 种子用户 superadmin 明文密码 "dev-no-auth-mode"（线索⑤确认） | 高 | bcrypt 随机 + dev 隔离 + 首登改密 |
| modules/analysis/services/integration_service.py:127,205,293 | `event_engine.publish(...)` 方法不存在（EventEngine 仅 :442 `async def put`）→ 分析完成事件全部发布失败 | 高 | 改 `await put(...)` |
| modules/analysis/engines/analysis_engine.py:158-164,191-197 | 调 `analyze_portfolio_attribution(..., session=session)` 而签名无 session（integration_service.py:218-224）→ TypeError | 高 | 去掉 session 参数 |
| analysis_engine.py:94-96,108-110,119 | handle_* 不传 session（integration_service 签名要求 session）→ 事件驱动自动分析空转；handle_strategy_executed 还多传 execution_result（:94）→ TypeError | 高 | 传 session、删多余参数 |
| modules/monitor/engines/alert_engine.py:75,79 + core/engines/base/engine_base.py:1922-1940 | 订阅 "monitor.risk.alert.triggered" 而 risk 引擎实际发 "risk.alert.triggered"（risk_events.py:118）；系统健康事件经 _publish_event 被包装成 EngineLifecycleEvent → **风险/系统告警链路断裂** | 高 | 统一事件名 + 发布侧直接 put 类型化事件 |
| modules/monitor/services/alert_service.py:95 | 告警去重失效（within_hours=0 语义错误）→ 告警风暴无防护 | 高 | 修复时间语义并默认开启 N 小时去重 |
| modules/monitor/handlers.py:126-135,163-167 + system_monitor.py:103 | 告警规则写入 monitor_thresholds，但运行期评估只用硬编码 DEFAULT_THRESHOLDS → **规则配置闭环断裂**（且 alert_rules 表不存在，线索确认：无此表，实为 monitor_thresholds） | 高 | 引擎启动加载阈值表；修正阈值方向语义 |
| modules/account/services/cash_service.py:110,201,292,388,501,513 vs docs/sql/create_table.sql:609 | cash_flows 注释枚举 `deposit/withdrawal/transfer/dividend/fee` 与实际写入 `freeze/unfreeze/transfer_in/transfer_out` 不符（线索③确认） | 中 | 更新表注释并统一枚举常量 |
| modules/account/events/position_events.py:191,285,415 + settlement_events.py:301,433 + reconciliation_events.py:34 | 事件类型硬编码 `"events.position.opened"` 等，与 AccountEventType 枚举（types.py:15-31）不符（线索②确认）→ 按枚举订阅者收不到 | 中 | 全部改用枚举值 |
| quant_server/config.yaml:14 + shared/config/config_manager.py:115 + modules/system/constants.py:37 | token 有效期三处不一致 600/30/60 分钟（线索④确认）；实际生效 30（JWTManager 走 Settings()，config.yaml 的 600 未消费，main.py:698 又向外报 600 误导） | 高 | 单一配置源 + 统一读取路径 |
| modules/system/handlers.py:463-483 + system_router.py:574-649 | 密码重置/邮箱验证 501（线索⑥确认）；request_password_reset 返回假成功"已发送"但未发邮件 | 中 | 接入 SMTP+一次性 token，或明确下线 |
| modules/account/managers/account_manager.py:91-102 | create_user_account 先 account_service.create_account（已写入 initial_balance）再 cash_service.deposit 同额 → **初始资金双倍** | 高 | 二选一 |
| modules/account/services/account_service.py:635-640 | record_daily_settlement 写 account_daily_performance 漏 NOT NULL account_id → IntegrityError | 高 | 补 account_id（或删该方法） |
| modules/analysis/tasks/daily_analysis_tasks.py:1236,1294 | get_market_overview / analyze_index_performance **自递归调用自身** → RecursionError 被吞，市场摘要恒空 | 高 | 改为调用 Repository |
| daily_analysis_tasks.py:209-213,662-665,1132-1135 + report_tasks.py:472-473 | 用 `trade_repo.get_many(trade_date=...)` / `hasattr(t,'trade_date')` 过滤，而 Trade 模型只有 trade_time 列（business_models.py:620）→ SQL 列不存在报错 / 过滤恒空 | 高 | 改用 trade_time 区间查询 |
| modules/analysis/handlers/event_handler.py:65,81,94 | 同步回调内调用 async trigger_* 未 await → 协程永不执行 | 高 | 回调改 async 并 await |
| modules/analysis/services/attribution_service.py:893-898,260 | SMB/HML/UMD 无数据源时 `return None` → 调用方 `None.empty` AttributeError → 因子归因（Fama-French/Carhart）恒失败 | 高 | 对接真实因子源或返回空 DataFrame 明确降级 |
| modules/monitor/tasks/monitoring_tasks.py:45 + alerting_tasks.py:70 | 调用不存在的 `RiskEngine.check_and_publish`、`AlertManager.retry_failed` | 中 | 删除或实现 |
| modules/monitor/engines/business_monitor.py:90-99 + monitor/__init__.py:108-116 | 业务监控引擎空壳：__init__ 未注入 db_session_factory → session 恒 None，BusinessMonitorService 永远输出全零指标；且若传入 async context manager 型 factory，`:92` `await self._db_session_factory()` 对 async generator 直接 TypeError | 高 | 注入 session factory 并改用 `async with`；或移除该引擎 |
| modules/account/services/cash_service.py:597,653-657 | get_cash_flows 按 account_id 过滤 user_id 列 → 查询恒空，余额汇总恒 0 | 高 | 按 user_id 查询或加 account_id 维度 |
| modules/account/calculators/pnl_calculator.py:182-195,304 | "日盈亏"含累计浮盈（口径错）；calculate_account_performance 用 user 维度绩效混入多账户数据 | 高 | 只算当日变动；按 account_id 过滤 |
| modules/analysis/services/performance_service.py:895-902,904 | 胜率分母含 pnl=0 的买单（计入亏损）；:901-902 直接 `t.pnl` 可能 AttributeError | 中 | 只统计卖单并安全取值 |
| modules/account/handlers.py:313-314 | `logger` 未定义（handlers.py 无 logging 导入）→ 绩效附加查询失败时 NameError 致整个列表接口 500 | 高 | 补 `logger = logging.getLogger(__name__)` |
| api/dependencies/auth.py:342 vs :110 | require_superuser 只认 super_admin/superadmin，种子 admin 用户无法通过；角色字符串三处混用 | 中 | 统一 ADMIN_ROLES 常量 |
| modules/system/handlers.py:562-565 | `from modules.system.managers.config_manager import get_config_manager` 不存在该符号 → /cache/clear 恒 cleared=False | 中 | 改导入路径 |
| modules/system/services/auth_service.py:115-117 | 注册密码强度校验被注释掉 → 弱密码可注册 | 中 | 恢复校验 |
| modules/account/managers/account_manager.py:242 | get_account_overview 今日交易统计 `get_by_trade_date(today, user_id=None)` 查全用户 | 高 | 按 account_id 过滤 |
| modules/account/events/types.py:46-54 | `is_balance_event` 等实例方法内引用 `cls`（模块级 import 自 sqlalchemy.sql.coercions）→ 调用即 AttributeError | 中 | 改用 self.__class__ 或类名 |
| modules/monitor/engines/alert_engine.py:305 | 交易信号强制 channels=["wechat"]，忽略 config.yaml 渠道开关与 `alert_interval:300`（config.yaml:93 全库未用） | 低 | 渠道/节流走配置 |
| modules/monitor/handlers.py:293-312 | check_monitor_module_health 恒返回 healthy | 低 | 纳入引擎/队列指标 |
| 事件命名 | 多处 module="events"（settlement_events.py:44 等）与裸字符串事件名，不符合 `{module}.{domain}.{action}.{status}` 规范 | 低 | 统一枚举+规范命名 |
| scripts/fix_token.py:50-56 | 可签发 100 年"永久"超管 token | 低 | 仅限运维且密钥轮换后作废 |

---

## 6. 严重度汇总表（Top 20）

| # | 严重度 | 维度 | 位置 | 问题摘要 | 修复方案摘要 |
|---|---|---|---|---|---|
| 1 | 高 | 业务bug | api/dependencies/auth.py:58-255 + system_router.py:518-523 | 主认证链不查黑名单 + 登出传 "unknown" → 注销后 token 仍可用；AUTH_ENABLED=false 默认开放 | 黑名单接入主链 + 真实 token 登出 + 生产强制开启认证 |
| 2 | 高 | 业务bug | shared/config/config_manager.py:114 | JWT 密钥为公开占位符，可伪造任意身份 token | 强随机密钥环境注入 + 轮换 |
| 3 | 高 | 业务bug | modules/system/auth/authentication.py:97-101 + user_repo.py:106-111 | 改密/密码自动迁移双重加密 → 下次登录必失败 | 统一 bcrypt 存储，修正 migrated 分支 |
| 4 | 高 | 业务bug | settlement_engine.py:93 + settlement_tasks.py:429-430 | 结算事件日期字符串 → datetime.combine TypeError，成交触发结算全失败 | 引擎入口统一 date 类型 |
| 5 | 高 | 业务bug | settlement_engine.py:173-187 + settlement_tasks.py:141-154 | AccountSettlementCompletedEvent 双发 | 单一发布方 |
| 6 | 高 | 业务bug | modules/account/tasks/reconciliation_tasks.py:92 | account.account_id AttributeError → 日终对账 100% 失败 | 改 account.id |
| 7 | 高 | 业务bug | modules/strategy/engines/performance_tracker.py:48 | trade_date vs settlement_date 字段不一致 → 补结算日期错写（线索①） | 统一字段 |
| 8 | 高 | 业务bug | analysis_engine.py:94,158 + integration_service.py:127,218 | 事件驱动分析链 4 处签名/方法不存在（publish/session/execution_result）→ 自动分析空转 | 对齐签名 + await put |
| 9 | 高 | 业界对比 | alert_engine.py:75,79 + engine_base.py:1922-1940 | 告警事件类型两端不一致 → 风险/系统告警链路断裂 | 统一事件名，发布侧 put 类型化事件 |
| 10 | 高 | 业界对比 | alert_service.py:95 + monitor_alert_repo.py:134-138 | 告警去重失效（hours=0→created_at>=now）→ 告警风暴 | 修复去重语义并默认开启 |
| 11 | 高 | 边界 | alert_manager.py:52 + alert_engine.py:87-128 | 默认渠道 email 未注册 → 告警只落库不通知 | 渠道求交集 + 告警日志 |
| 12 | 高 | 边界 | monitor_alert_repo.py:72 vs business_models.py:1585 | metadata vs metainfo 键名不符 → 告警详情静默丢失 | 统一列名 |
| 13 | 高 | 边界 | api/dependencies/auth.py:101-130,133-145 | 种子 superadmin 明文密码；DB 故障回退硬编码超管身份（线索⑤） | bcrypt 随机密码 + 503 兜底 |
| 14 | 高 | 业务bug | account_manager.py:91-102 | 初始资金双倍入账 | 去重入金逻辑 |
| 15 | 高 | 业务bug | cash_service.py:597 + position_service.py:237-244 | 资金流水按 account_id 查 user_id 列恒空；卖出校验符号反转绕过 | 维度修正 + 符号统一 |
| 16 | 高 | 业务bug | pnl_calculator.py:182-195,304 | 日盈亏含累计浮盈；账户绩效混用 user 维度 | 单日口径 + account_id 过滤 |
| 17 | 高 | 业务bug | daily_analysis_tasks.py:1236,1294 | 自递归导致市场摘要恒空 | 改调 Repository |
| 18 | 高 | 业界对比 | config.yaml:14 + config_manager.py:115 + system/constants.py:37 | token 有效期 30/600/60 三处不一致，实际生效 30（线索④） | 单一配置源 |
| 19 | 高 | 业务bug | attribution_service.py:893-898 | SMB/HML/UMD 无数据源 → 因子归因恒失败 | 对接因子源或明确降级 |
| 20 | 高 | 业务bug | account/handlers.py:313-314 + report_tasks.py:503 + cost_analyzer.py:799 | logger 未定义致 500；收益公式指数级虚高；滑点分析变量错 | 补 logger/修正公式/改 aStats |

> 补充：另有 `modules/system/handlers.py:463-483` 密码重置/邮箱验证 501、`account_daily_performance` 写入维度（account_id vs user_id）混用、`modules/monitor` 规则配置（monitor_thresholds）与运行期硬编码阈值脱节、`AUTH_ENABLED=false` 被 production 继承等中高危项，详见 §3/§5。所有条目均已在正文给出 文件:行号 实证；标注"待确认"的仅有：`.env:111` 密钥占位符行号、pandas 版本对 `resample('ME')` 的兼容性。

> 本报告为只读审查产出，未修改任何业务代码。如需按优先级出具修复清单（P0/P1/P2 拆分 + 单测建议），可继续安排。

---

## 7. 业界标准对照（问题 → 判定依据映射）

> 说明：本报告各问题"是否成立、严重度如何"均以业界公认 review/工程标准为判定依据。下表把 §2-§6 已列问题显式映射到对应标准。判定依据分八类：
> **GCR**=Google Code Review 规范（Code Health）；**CC**=Clean Code（Bob Martin）；**SOLID**=SOLID 原则；**RF**=Martin Fowler《重构》坏味道清单；**BROKER**=券商清算最佳实践（幂等/防重/对账）；**PERF**=绩效计算行业标准（GIPS/年化口径）；**AM**=Alertmanager/SRE 告警规范；**SEC**=OWASP Top 10 / JWT 最佳实践（RFC 7519、RFC 8725、NIST SP 800-63B）。

### 7.1 认证与安全（依据 SEC：OWASP Top 10 / JWT 最佳实践）

| 报告位置 | 问题 | 依据标准 | 判定要点（标准要求 vs 现状） |
|---|---|---|---|
| §5 / Top20#2（config_manager.py:114） | JWT 密钥公开占位符 | SEC — OWASP A02:2021 密码学失败；硬编码凭据；RFC 8725 §3.1 | 密钥须 ≥256bit 随机、环境注入、可轮换；现状为公开占位符 → 任意伪造 token |
| §5 / Top20#1（auth.py:58-255、system_router.py:518-523） | 登出无效/黑名单未接入主认证链 | SEC — OWASP A05:2021 访问控制失效；JWT 最佳实践（token 撤销、黑名单须在每次验证生效） | 注销后的 token 在 30 分钟有效期内仍可用 → 访问控制失效 |
| §1.4（jwt_handler.py:234-262） | refresh 不轮换、无 jti/重用检测 | SEC — RFC 8725（refresh token rotation + reuse detection）；NIST SP 800-63B | 7 天长命凭据被盗后无法吊销；应轮换 refresh 并记录 family |
| §3（auth.py:163、jwt_handler.py:215） | 缺 exp 校验/leeway 无效 | SEC — RFC 7519 §4.1.4（exp 必验）；RFC 8725 §3.3（时钟偏差容忍） | 缺 exp token 通过后 KeyError→500；leeway 传错位置恒 0 |
| §3 / 线索⑤（auth.py:101-145） | 明文种子密码 + DB 故障回退硬编码超管 | SEC — OWASP A02/A07；NIST SP 800-63B（口令哈希 bcrypt/argon2，禁明文） | 公开密码可登录超管；DB 故障时以超管身份开放系统 → 应 fail-closed |
| §1.4 / §2（user_manager.py 死代码） | 登录无锁定/无速率限制 | SEC — OWASP A07:2021 身份认证失败（暴力破解防护） | 失败锁定与在线会话逻辑存在但未接线 → 认证防护形同虚设 |
| §1.4（config.yaml:15,126-129） | AUTH_ENABLED=false 默认且 production 继承 | SEC — 纵深防御/Fail-secure 原则 | 生产默认跳过认证 → 安全开关应环境隔离、默认开启 |
| §5（auth.py:208-213,342） | 权限码生成失真、角色字符串三处混用 | SEC — OWASP A01:2021 越权（最小权限、统一授权模型） | 权限判定依赖字符串拼写且存在默认授 execute → 越权风险 |
| §5（system_router.py:552-571） | /auth/token-info 无签名解码任意 token | SEC — OWASP A05（信息暴露）；JWT 最佳实践（解码须验签） | 泄露 userId/exp 元信息，可探测 |

### 7.2 券商清算最佳实践（依据 BROKER：幂等/防重/对账）

| 报告位置 | 问题 | 依据标准 | 判定要点（标准要求 vs 现状） |
|---|---|---|---|
| §3-1（settlement_tasks.py:108-120） | 结算记录无唯一键、重复执行重复落库 | BROKER — 清算幂等（idempotency key：结算批次 + (account, trade_date, type) 唯一约束 + 先查后插） | 券商日终清算必须可重跑不产生重复；现状同日多触发即多记录 |
| §1.1 / §3（settlement_engine.py:31-142） | 防重仅进程内存 5 分钟防抖，且 timer 键错位 | BROKER — 分布式防重（Redis SETNX / DB 唯一约束 / 结算状态机） | 多实例/重启即失效；应落库状态机（pending→completed→reconciled） |
| §5 / Top20#6（reconciliation_tasks.py:92） | 日终对账 100% 失败（account.account_id） | BROKER — 清算对账闭环（双边核对、差异可追溯、差错处理） | 对账是券商清算的强制环节；现状功能不可用且"券商数据"实为本地自取自比 |
| §5-1（settlement_engine.py:93 + settlement_tasks.py:429-430） | 结算日期跨层类型断裂（str→datetime.combine） | BROKER — 数据契约强类型边界；批处理日期参数校验 | 成交触发结算链路整体失败 → 违背"T+1 日终处理必须可靠" |
| §2（account_service.py:603-651 record_daily_settlement） | 结算写表重复实现且漏写 account_id | BROKER + CC — 单一数据写入路径、表约束完整 | 与 settlement_tasks._upsert_daily_performance 双实现 → 口径漂移风险 |

### 7.3 绩效计算行业标准（依据 PERF：GIPS / 年化口径）

| 报告位置 | 问题 | 依据标准 | 判定要点（标准要求 vs 现状） |
|---|---|---|---|
| §1.2（pnl_calculator.py:355-368 vs financial_calculator.py:216-241 vs exposure_calculator.py:467-471） | 夏普三套公式（ddof=0/年化减日 rf/不含 rf） | PERF — GIPS 一致性与可比性；CFA 绩效衡量（夏普=年化超额/年化波动，样本标准差 ddof=1） | 同账户三处夏普不可比；FinancialCalculator 年化收益减日 rf 为维度错误 |
| §1.2（回撤符号 负值 vs 正值；comparison_service.py:440-444） | 最大回撤符号口径不统一导致排名反转 | PERF — GIPS（指标定义须统一并在报告披露口径） | 同一平台回撤一会 -0.2 一会 0.2 → 排名/阈值判定方向相反 |
| §1.2（performance_service.py:181,409 vs financial_calculator.py:182-185 vs pnl_calculator.py:324-328） | 年化基准 365.25 自然日 vs 252 交易日三套 | PERF — GIPS（年化须明确 252 交易日并统一）；业绩比较基准一致 | 年化收益相差可达数个百分点 |
| §1.2 / Top20#16（pnl_calculator.py:182-195） | 日盈亏把累计浮盈计入当日 | PERF — 日频收益 mark-to-market 口径（当日盈亏=Δ市值+Δ现金-出入金，不含历史浮盈） | 单日盈亏被历史浮盈污染 → 净值曲线与日收益失真 |
| §1.2（PerformanceMetrics 无 account 侧卡玛） | 卡玛比率缺失 | PERF — 风险调整收益指标体系（Calmar=年化收益/|MaxDD|，业界标准指标） | 绩效报告不完整 |
| §4（performance_service/attribution_service 无缓存） | 绩效逐日全量重算 | PERF — 绩效计算可复现 + 快照落库增量计算 | 无缓存导致口径漂移与资源浪费 |

### 7.4 告警系统规范（依据 AM：Alertmanager / SRE 最佳实践）

| 报告位置 | 问题 | 依据标准 | 判定要点（标准要求 vs 现状） |
|---|---|---|---|
| §1.3 / Top20#10（alert_service.py:95 + monitor_alert_repo.py:134-138） | 去重失效（hours=0→created_at>=now） | AM — Alertmanager repeat_interval 去重语义 | 同内容告警风暴无防护 → SRE 告警疲劳 |
| §1.3（无分组/静默/升级/抑制） | 功能矩阵缺失 | AM — group_by/group_wait、silence、repeat_interval、inhibit_rules | 未达 Alertmanager 基线能力 |
| Top20#9（alert_engine.py:75,79 + engine_base.py:1922-1940） | 发布-订阅事件类型两端不一致 | AM + 事件契约（API 版本一致性）；SRE 可观测性（告警必须可靠送达） | 风险/系统告警链路断裂 → 监控盲区 |
| §1.3 / §3（无 resolved 闭环；alerting_tasks.py:32-38 清理永不执行） | 告警永为 active、表无限膨胀 | AM — 告警生命周期 firing→resolved 自动闭环 | 状态机缺失 + 清理失效 |
| §3（alert_manager.py:52 默认 email 未注册） | 告警只落库不通知 | AM — 通知路由可靠性（未注册渠道须显式失败并告警） | 高优告警静默丢失 |
| §4（alert_manager.py:67-99 单条 4-6 次 DB 往返） | 告警落库无批量 | AM/性能 — 告警高吞吐写入 | 风暴期 DB 压力放大 |
| Top20#12（monitor_alert_repo.py:72 vs business_models.py:1585） | metadata 与 metainfo 列名不符致静默丢失 | AM + CC — 显式失败优于静默丢失（fail loud） | 告警上下文（风险详情/信号载荷）不可追溯 |

### 7.5 代码质量（依据 GCR：Code Health）

| 报告位置 | 问题 | 依据标准 | 判定要点（标准要求 vs 现状） |
|---|---|---|---|
| §2 全表（30+ 处死代码） | 未引用的类/方法/事件/枚举 | GCR — Code Health 明确将死代码列为必须清理项（dead code 应删除，git 可追溯） | 保留死代码增加维护与误导成本 |
| §2（两套 JWT 实现、monitor models.py 与 constants.py 枚举重复、record_daily_settlement 与 upsert 重复） | 重复实现 | RF — Duplicated Code（坏味道）；GCR — 避免重复逻辑 | 双实现必然口径漂移（如 token 有效期、枚举值） |
| §5（settlement_engine + settlement_tasks 双发事件；performance_service/attribution_service/pnl_calculator 三套公式） | 重复发布/重复计算逻辑 | RF — Duplicated Code、Shotgun Surgery；SOLID SRP | 一处修改多处遗漏 → 事件双发、口径分裂 |
| §2/§5（attribution_service 936 行、reconciliation_manager 1008 行、daily_analysis_tasks 1314 行、settlement_events 538 行） | 超长文件/超长方法 | GCR — 文件超过 400 行应拆分；RF — Long Method、God Class | 可读性差、职责混杂、易引入自递归等错误 |
| §5（analysis_engine.py:94,158 vs integration_service.py:127,218 签名不符） | 调用签名与实现签名不一致 | SOLID — LSP/接口契约一致性；依赖倒置（按接口编程） | 调用即 TypeError，事件驱动链整体失效 |
| §5（position/reconciliation 事件硬编码 event_type vs 枚举） | 字符串常量替代枚举 | SOLID — OCP（对扩展开放，对修改封闭）；CC — 用枚举/常量替代魔法字符串 | 订阅方按枚举永远收不到事件 |
| §5（account/handlers.py:313-314 logger 未定义；account_manager.py:346 下标访问 pydantic 模型） | 未定义符号/类型误用 | GCR — 编译期/静态检查；CC — 正确性与防御式编程 | 运行时 500，且异常路径比正常路径更易触发 |
| §3（config.yaml:14、config_manager.py:115、system/constants.py:37 三处 token 值） | 同一配置三处定义 | CC — 单一事实来源（Single Source of Truth）；DRY | 配置漂移（600 vs 30 vs 60） |
| §4（limit=100000/limit=100/252/0.03 等散落魔法数） | 魔法数字散落 | CC — 命名常量/配置化 | 阈值与口径不可配置、不可审计 |
| §5（event_handler.py:65,81,94 未 await 协程） | 异步调用遗漏 await | GCR — 异步代码审查要点（lint/类型检查强制）；CC — 显式异步契约 | 协程永不执行，自动分析链空转 |

### 7.6 标准覆盖结论

- **SEC**：命中 OWASP A01/A02/A05/A07 共 9 项 → 认证安全为本报告最高优先级域（Top20 前 3 位均为 SEC 域）。
- **BROKER**：清算幂等、防重、对账三要素全部缺失或断裂 → 结算可靠性不达券商基线。
- **PERF**：GIPS 一致性与口径统一原则被多处违反（夏普/回撤/年化/日盈亏）。
- **AM**：Alertmanager 基线能力（去重/分组/静默/升级/闭环）基本为零，且基础送达链路断裂。
- **GCR/SOLID/RF**：死代码、重复实现、超长文件、签名不一致构成系统性代码健康问题，是上述业务缺陷的根因放大器。
- 修复优先级建议：SEC（密钥/认证开关/黑名单）→ BROKER（结算幂等与日期类型）→ AM（去重/事件契约）→ PERF（口径统一）→ GCR 清理（死代码/重复实现）。
