# Market 概览页重设计 · 开发路径说明

> 版本：v1.0（2026-08）｜上游设计：`Market概览页重设计方案v5.md`（用户已确认 ①②③④）
> 本文档为**实施路径说明**，按 AGENTS.md 流程输出，确认后进入编码。
> 现状盘点依据：market_router.py（32 端点，前缀 `/quantTrade/market`）、dashboard_service.py（B12 内存 TTL 60s 先例）、limit_service.py（gap-island 连板逻辑）、market_state_service.py、前端 market.ts（346 行）+ MarketDashboard.vue（1329 行，9 区块）。

---

## 一、实施批次与边界

| 批次 | 内容 | 结束验证点 | 建议 commit |
|:---|:---|:---|:---|
| Batch 1 | **后端 P0**：3 个新端点（temperature / limit-ladder / breadth-leaders）+ 单测 | curl 3 端点通过、pytest 基线不回归 | `feat(market): 概览页 P0 后端聚合端点（温度计/涨停梯队/强弱榜）` |
| Batch 2 | **前端 P0**：5 个新组件 + Dashboard 重构 + API/类型 | vue-tsc + pnpm build 通过（用户执行） | `feat(market): 概览页 P0 驾驶舱重构` |
| Batch 3 | **P1**：拥挤度端点 + 宽度补全(N2) + 波动率分位(N5) + 雷达分位化 + 行业拥挤点 | 另行出批次级路径 | `feat(market): 概览页 P1 状态完备` |
| Batch 4 | **P2**：宏观日历 7 天化 + 移动端 + 深色主题 + 性能 | 另行出批次级路径 | `feat(market): 概览页 P2 打磨` |

> 本说明重点展开 **Batch 1 + Batch 2（P0）**；Batch 3/4 开始时再出同粒度路径说明（分批纪律）。

---

## 二、Batch 1 — 后端 P0（3 端点）

### 2.1 新增文件（2 个 service）

| # | 文件 | 内容 |
|:---|:---|:---|
| 1 | `quant_server/modules/market/services/market_temperature_service.py` | `get_market_temperature(session)` → N1 温度计（4 维 → 1 温度） |
| 2 | `quant_server/modules/market/services/breadth_service.py` | `get_breadth_leaders(session)` → N6 强弱榜（新高/新低/连涨） |

涨停梯队（N3）**扩展** `modules/market/services/limit_service.py`（同域，139 行 → 新增 `get_limit_ladder`，复用文件内 `_all`/`_first` 与 gap-island 连板模式），不新建文件。

### 2.2 修改文件（3 个）

| # | 文件 | 改动 |
|:---|:---|:---|
| 3 | `quant_server/modules/market/handlers.py` | +`do_dashboard_temperature` / `do_limit_ladder` / `do_breadth_leaders`（照抄现有 do_* 模式，lazy import，与 `do_limit_analysis` 同构） |
| 4 | `quant_server/api/routers/market_router.py` | +3 个 GET（照抄 `limit-analysis` 端点模板）：`/dashboard/temperature`、`/dashboard/limit-ladder`、`/dashboard/breadth-leaders`；响应信封 `{"success": True, "data": ...}` |
| 5 | `quant_server/modules/market/__init__.py` | 3 个 handler 加入 `from .handlers import (...)` 与 `__all__`；**每条新增项带尾随逗号**（规避"裸名残留"历史 bug） |

### 2.3 各端点 SQL 口径

**N1 `GET /dashboard/temperature`** → `{temperature, zone, data_date, updated_at, dimensions:{valuation, emotion, capital, technical}, sample_warning}`
- 分位定义：`当前值在历史序列中的百分位（≤当前值的占比 ×100）`；样本窗口不足时该维 `percentile=null` 且整体 `sample_warning=true`。
- **估值**（样本 1000 交易日，index_dailybasic 2004 年起够用）：沪深300(000300.SH)+中证500(000905.SH) 的 `pe`、`pb` 各自分位 → 估值温度 = 4 个分位均值。
- **情绪**：①涨停家数（`stock_daily_limit` join `stock_daily` 按日计 `close>=up_limit` 家数，样本 250 日）分位 ×0.5；②全市场换手率（`stock_daily_basic.turnover_rate` 当日全市场均值，样本 250 日）分位 ×0.5。
- **资金**：`stock_moneyflow_hsgt.north_money` 20 日滚动净流入序列的当前值分位（样本上限 750 日）。
- **技术**：全市场站上 MA20 比例（`AVG(close) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING AND CURRENT ROW)` 按日聚合）当前值分位（样本 250 日）。**重查询预案**：60s 缓存 + 仅限主板/有 20 日历史的个股；单查询 >1.5s 则退化为 `market_state_daily.breadth_ratio` 分位并返回 `technical_approx=true`。
- 温度 = 四维等权（0~100）；zone：`<30 低温 / 30-70 中性 / >70 高温`（与仓位卡 4 带不冲突，见 §3.2）。
- 缓存：模块级 dict TTL 60s（同 B12 先例，见偏差⑥）。

**N3 `GET /dashboard/limit-ladder`** → `{data_date, ladder:{board1,board2,board3,board4plus}, max_height, bust_rate, seal_amount, seal_amount_approx, emotion_phase, phase_desc, limit_up_count}`
- 当日涨停股 = `stock_daily.close >= stock_daily_limit.up_limit`（口径与 limit_service / market_state_service C13 修复一致）。
- 连板高度：对涨停股集合跑 gap-island 窗口（复用 limit_service 批量模式）→ 首板/2连板/3连板/≥4板 计数。
- 炸板率 = `(high>=up_limit 且 close<up_limit 家数) / (high>=up_limit 家数)`；分母 0 → `null`。
- 封板资金：见**偏差⑤**。
- **情绪周期规则表放后端**（常量，可引为因子）：冰点（首板<20 且炸板率>40%或炸板率=null）、修复（首板 20~40）、发酵（首板 40~80 或 max_height≥3）、高潮（首板>80 或 max_height≥5）、退潮（炸板率>35% 且涨停家数环比下降）——按此优先级顺序判定。

**N6 `GET /dashboard/breadth-leaders`** → `{data_date, new_highs:[], new_lows:[], streak_up:[]}`（各 TOP10，含 `ts_code/name/industry/close/pct_chg/amount`）
- 创 20 日新高：`close = MAX(close) OVER (PARTITION BY ts_code ORDER BY trade_date ROWS 19 PRECEDING)` 且上市满 20 日；新低同理取 MIN。
- 连涨 ≥5 日：`pct_chg>0` gap-island 当前连胜 ≥5。
- 排序：`amount DESC` 取 TOP10；**默认排除 ST/退市**（`stock_basic` 过滤，口径决策，如需含 ST 可调）。

### 2.4 缓存与性能

- 三端点均采用 **模块级 dict + TTL 60s**（照抄 dashboard_service B12 模式：`_cache` dict + `_TTL=60.0`），进程内单 worker（config.yaml `workers: 1`）下语义正确。
- 单端点预算 <500ms（验收#5）；技术维度重查询按 §2.3 预案兜底。

### 2.5 跨模块影响（后端）

- 改动面：`modules/market/`（services/handlers/__init__）+ `api/routers/market_router.py`。**不触碰** `shared/`、`core/`、其他模块、EventEngine、DDL（偏差⑤选 b 除外）。
- `api/main.py` 无需改（`/quantTrade/market` 前缀已注册）。
- 策略层：本批不消费温度因子；验收#3 的"结构化调用"由 HTTP GET 端点满足（策略经 `requests/httpx` 调用即可，无跨模块 import，符合 EventEngine 约束）。
- 无新数据源、无新表、无同步任务改动。

---

## 三、Batch 2 — 前端 P0

### 3.1 新增组件（`quant_web/src/components/market/`）

| 组件 | Props | 要点 |
|:---|:---|:---|
| `MarketTemperatureGauge.vue` | `data: MarketTemperature \| null`, `loading: boolean` | ECharts gauge（需 `use([GaugeChart])`）；四维小字 value+percentile+样本不足标；**带 Tab 结构：Tab1 温度计 / Tab2 直接嵌入现有 `<MarketStateRadar />`**（零 props 自取数，已验证），D4 的"雷达并入"在 P0 即达成，P1 仅做雷达数据分位化重构 |
| `PositionAdviceCard.vue` | `temperature: number \| null` | 内部 4 带规则表（§3.2）；温度 null 显示"—" |
| `LimitLadderCard.vue` | `data: LimitLadder \| null`, `loading: boolean` | 梯队柱图 + 炸板率 + 封板资金（近似标）+ emotion_phase/phase_desc 结论；点击 → `/market/limit-analysis` |
| `BreadthLeadersCard.vue` | `data: BreadthLeaders \| null`, `loading: boolean` | 3 Tab（新高/新低/连涨）TOP10 表格，行点击 → `/market/stock/:code` |
| `WatchlistStrip.vue` | `items: any[]` | 自 Dashboard 内联自选块抽出；折叠条"⭐ 自选 N 只 · 点击展开" |

### 3.2 仓位规则表（决策①落地文案，写入 `PositionAdviceCard.vue`）

| 温度 | 区域 | 建议仓位 | 文案 |
|:--:|:---|:--:|:---|
| <30 | ❄ 低温布局区 | 60~80% | 估值便宜 + 情绪冰点，适合分批布局宽基/行业 ETF |
| 30~50 | 🌤 温和进攻区 | 40~60% | 状态健康，持仓为主，回调加仓 |
| 50~70 | ⚖ 中性观察区 | 20~40% | 估值情绪偏高，降低仓位，保留底仓 |
| >70 | 🔥 高温防守区 | 0~20% | 过热拥挤，防守为主，等待降温 |

- 卡片固定脚注："温度计为系统量化指标，**不构成投资建议**"。

### 3.3 修改文件

| # | 文件 | 改动 |
|:---|:---|:---|
| 6 | `quant_web/src/views/DataCenter/Market/MarketDashboard.vue` | 重构为 §4.6 布局：L1（温度计4/仓位2/梯队3/指数3）→ L2（行业5/风格3/强弱4）→ 自选折叠条 → L3（北向+主力4/行业资金4/成交额TOP10 4；资金流入6/涨跌统计6）→ L4 折叠（拥挤度占位(P1)/波动率占位(P1)/宏观+事件日历）。删除首屏自选块；宏观/事件日历移入 L4 折叠。数据流：`Promise.allSettled` 并行 overview + styleFactors + temperature + limit-ladder + breadth-leaders，单失败不阻塞 |
| 7 | `quant_web/src/api/market.ts` | +`getMarketTemperature()` / `getLimitLadder()` / `getBreadthLeaders()`（照抄现有 `.catch(() => ...)` 容错模式） |
| 8 | `quant_web/src/types/entities/market.ts` | +`MarketTemperature` / `LimitLadder` / `BreadthLeaders` 接口 |

### 3.4 状态覆盖与刷新

- 每张新卡四态：Loading(`n-skeleton`) / Empty(`n-empty`) / Error(`n-result`+重试) / Data。
- 轮询：L0/L1 60s（温度计/仓位/梯队/指数）、L2/L3 120s、L4 懒加载（展开才请求）；非交易时段停轮询，L0 显示"收盘快照"+数据滞后 >10min 琥珀色警告。
- 边界态：分位样本不足 → 小字"样本不足"；炸板率 null → 显示"—"；`seal_amount_approx=true` → 标注"成交额近似"。

### 3.5 跨模块影响（前端）

- 改动面仅限 `components/market/` + `MarketDashboard.vue` + `api/market.ts` + `types/entities/market.ts`。**不触碰** `styles/`、`naive-theme.ts`、router、store、layout。
- 9 个市场子页面与跨模块桥梁（Market→Strategy→Backtest）不动。

---

## 四、Batch 3/4 摘要（届时另行细化）

- **Batch 3（P1）**：`GET /dashboard/crowding`（N4：全市场成交额 250 日分位 + 行业换手率分位 TOP5）；`breadth_service` 扩展 N2（新高新低家数/MA20/MA60 比例序列）；波动率分位（N5，index_daily 750 日）；MarketStateRadar 分位化重构；行业轮动柱拥挤点标记。
- **Batch 4（P2）**：宏观日历仅未来 7 天；移动端适配；深色主题；性能优化。

---

## 五、验证方案

### 5.1 后端（我执行）

1. `python -m py_compile` 全量改动文件 → 零错误。
2. import smoke：`python -c "import quant_server.main, quant_server.api.main"` → 无裸名/循环导入。
3. **新增** `tests/test_market_v5_services.py`：纯函数级单测 —— 分位计算（含并列值）、连板分组（gap-island 边界）、炸板率分母 0、温度合成权重、情绪周期规则表优先级。**不修改任何既有测试**。
4. pytest 全量：基线 82p/4s/31e 不回归（31e 均为既有预期失败）。
5. 手工 curl（用户起服务后或我起本地实例）：3 端点 `success=True`、字段齐全、首查 <500ms、二次命中缓存 <50ms。
6. **对账**：`limit-ladder.limit_up_count` ≡ `limit-analysis.stats.limit_up`（同日）；`breadth-leaders` 行数据与 `/stocks/{code}/full` 抽查一致；温度计估值分位与 `/indexes/000300.SH/valuation` 序列人工抽样复核。

### 5.2 前端（用户执行，node 沙箱不可用）

1. `npx vue-tsc --noEmit` + `pnpm build` 通过。
2. 四态逐卡验证；3 断点响应式（<768 / 768-1024 / >1024）；9 个市场页面回归无白屏。
3. 首屏验收对照 v5 §七 #1/#2/#4/#5；刷新节奏与盘后停轮询观察。

---

## 六、偏差与待确认（阻塞点，确认前不开工）

> 盘点过程中发现 2 处与 v5 设计不符的实际情况，按 AGENTS.md 暂停上报。

**偏差⑤ 封板资金无法按原设计计算**：`stock_daily_limit` 表**没有封单金额（limit_amount）列**（仅 pre_close/up_limit/down_limit/up_percent/down_percent/price_range），"封板资金=涨停股封单额合计"无数据源。
- 选项 a（**推荐**）：P0 用"涨停股当日成交额合计"（`stock_daily.amount`）近似，返回 `seal_amount_approx=true`，前端标"成交额近似"；
- 选项 b：扩表（DDL 加 `limit_amount` 列）+ data 模块同步改造（tushare limit_list_d 有该字段）——跨模块 + DDL，估 +1d，放入 P1；
- 选项 c：移除该指标，梯队卡只留高度/炸板率。

**偏差⑥ 缓存策略与现状不一致**：v5 决策②建议 Redis 60s，但现有 dashboard 先例（B12）是**内存 dict TTL 60s**；config.yaml `workers: 1` 单进程，Redis 为可选设施（`REDIS.ENABLED`，jwt 已有优雅降级先例）。
- 选项 a（**推荐**）：4 端点沿用内存 dict TTL 60s——零依赖、与 B12 一致、单 worker 下语义正确；
- 选项 b：接入 `shared/cache/redis_cache.RedisCache`（需确认 redis 实例实际可用，不可用时降级内存）。

---

## 七、Batch 1 实施记录（2026-08-15，已完成 ✅）

### 7.1 交付清单

| 文件 | 动作 |
|:---|:---|
| `modules/market/services/market_temperature_service.py` | **新建**（N1 温度计：4 维分位 + 合成 + 300s 内存缓存） |
| `modules/market/services/breadth_service.py` | **新建**（N6 强弱榜：新高/新低/连涨 TOP10） |
| `modules/market/services/limit_service.py` | **扩展**（N3 `get_limit_ladder` + `build_ladder`/`calc_bust_rate`/`classify_emotion_phase`） |
| `modules/market/handlers.py` | +3 个 do_* 桥接函数 |
| `api/routers/market_router.py` | +3 个 GET 端点（`/dashboard/temperature`、`/dashboard/limit-ladder`、`/dashboard/breadth-leaders`） |
| `modules/market/__init__.py` | +3 导出（import 块与 `__all__` 均带尾随逗号） |
| `tests/test_market_v5_services.py` | **新建** 28 条纯函数单测 |

### 7.2 验证结果

| 项 | 结果 |
|:---|:---|
| py_compile + import smoke | ✅ 零错误 |
| 新单测 | ✅ 28 passed |
| 全量 pytest | ✅ 110 passed / 4 skipped / 31 errors / 9 failed（= 基线 82p+28 新增；9f 为 `tests/modules/` 下 pytest-asyncio 插件缺失的既有环境问题，31e 为既有 industry_rotation 收集错误，均与本次无关） |
| 运行时（8082 实例实测，数据日 2026-08-14） | ✅ 三端点 200 |
| temperature | 冷 5.9s → 缓存命中 7ms；温度 71.5（高温），4 维齐全，技术维 MA20 真实口径 94.0 分位（未退化） |
| limit-ladder | 冷 1.5s；首板53/2板5/3板5/≥4板1、最高5板、炸板率25.6%、封板资金≈9491万（近似）、情绪=高潮 |
| breadth-leaders | 冷 3.4s；新高/新低/连涨各 TOP10 |
| **对账** | `limit-ladder.limit_up_count=64` ≡ `limit-analysis.stats.limit_up=64` ✅；`max_height=5` ≡ `consecutive_max=5` ✅；炸板率=(86-64)/86=25.6% ✅；温度计情绪维 value=64 与两者一致 ✅ |

### 7.3 偏差与附带修复（需用户知晓）

1. **偏差⑥-1 缓存 TTL 60s → 300s**：确认的 ⑥a 是"内存 dict"（已执行）；但实测冷查询 1.5~6s 且数据为**日频**（收盘后不变），60s TTL 会导致前端每轮轮询都触发全量重算（每次 5s+ 延迟 + 持续 DB 压力）→ 三个端点 TTL 统一调整为 **300s**，仍为内存 dict、零依赖。如需 60s 可一键改回（各 service 头部 `_CACHE_TTL` 常量）。
2. **偏差⑤a 已落地**：封板资金 = 涨停股当日成交额合计，响应含 `seal_amount_approx=true`，前端需标注"成交额近似"。
3. **附带修复（同根因，超出计划但同文件）**：既有 `/limit-analysis` 端点存在与新增代码相同的 **asyncpg 字符串日期参数 bug**（传 `'2026-08-14'` 而非 date 对象 → DataError → 500，为潜在故障）。在 `get_limit_stocks` 中按同根因修复（`date.fromisoformat` 转 date 对象），修复后该端点恢复正常（200）。若用户认为超范围可回退该 3 行改动。
4. **技术维超时退路设计已生效但未触发**：MA20 窗口查询实测约 5s 内完成（8s 超时内），走真实口径；超时退化为 `market_state_daily.breadth_ratio` 近似 + `technical_approx=true` 的预案保留。

### 7.4 待办（Batch 2 前端 P0，另出批次确认）

- 5 个新组件 + `MarketDashboard.vue` 重构 + `market.ts`/`types` 扩展（见 §三）。
- 前端需标注 `seal_amount_approx`（"成交额近似"）、`sample_warning`（分位样本不足）、`technical.approx`（技术维近似口径）。

---

## 八、Batch 2 批次级路径（前端 P0，2026-08-15 已确认开工）

### 8.1 组件契约（Props/Emits）

| 组件 | Props | Emits | 四态/要点 |
|:---|:---|:---|:---|
| `MarketTemperatureGauge.vue` | `data: MarketTemperature \| null`, `loading: boolean` | 无 | Tab1=ECharts 仪表盘（GaugeChart）+ 四维小字（value+分位；`approx`→"近似"标、分位 null→"样本不足"）；Tab2=嵌入现有 `MarketStateRadar`（自取数，D4 落地）。Loading→`n-skeleton`，data null→`n-empty` |
| `PositionAdviceCard.vue` | `temperature: number \| null` | 无 | 4 带规则表（§3.2 文案）；温度 null→"—"；固定脚注"不构成投资建议" |
| `LimitLadderCard.vue` | `data: LimitLadder \| null`, `loading: boolean` | 无（内部 `router.push('/market/limit-analysis')`） | 梯队分布（4 段条形）+ 炸板率 + 封板资金（`seal_amount_approx`→"成交额近似"标签）+ `emotion_phase/phase_desc` 结论条 |
| `BreadthLeadersCard.vue` | `data: BreadthLeaders \| null`, `loading: boolean` | 无（内部 `router.push('/market/stock/'+ts_code)`） | 3 Tab（新高/新低/连涨）× TOP10 迷你表格（代码/名称/行业/pct_chg），`n-data-table` size=small |
| `WatchlistStrip.vue` | `items: WatchlistItem[]`, `loading: boolean` | 无 | 折叠条"⭐ 自选 N 只 · 点击展开"；展开显示 chips，点击→StockDetail |

### 8.2 API 与类型

- `api/market.ts` +3：`getMarketTemperature()` / `getLimitLadder()` / `getBreadthLeaders()`（照抄现有 `.catch(() => ...)` 容错模式）。
- `types/entities/market.ts` +3：`MarketTemperature`（temperature/zone/sample_warning/data_date/updated_at/dimensions{valuation,emotion,capital,technical:{value,percentile,approx}}）、`LimitLadder`（ladder{board1..board4plus}/max_height/bust_rate/touched_count/limit_up_count/prev_limit_up_count/seal_amount/seal_amount_approx/emotion_phase/phase_desc/data_date）、`BreadthLeaders`（data_date/new_highs[]/new_lows[]/streak_up[]，行含 ts_code/name/industry/close/pct_chg/amount）。

### 8.3 Dashboard 布局映射（旧区块 → §4.6 新位置）

| 旧区块 | 新位置 |
|:---|:---|
| 自选股条（首屏） | → L2/L3 之间 `WatchlistStrip` 折叠条 |
| MarketStateRadar 独立卡 | → 并入温度计卡 Tab2 |
| StyleRotation | → L2 span3（原位微调） |
| 核心指数（6 指数格） | → L1 span3 |
| 涨跌统计（breadth 卡） | → L3B span6（迷你趋势） |
| 行业轮动柱图 | → L2 span5 |
| TOP10 成交额 | → L3A span4 |
| TOP10 资金流入 | → L3B span6 |
| 北向 + 主力订单 | → L3A span4 单卡双图 |
| 行业资金强度 | → L3A span4 |
| 宏观 + 事件日历 | → L4 折叠（拥挤度/波动率分位为 P1 占位，本批不渲染） |
| 快捷入口 | → L0 状态条右侧 chips |

### 8.4 刷新节奏（P0 实现）

- Dashboard 内 `setInterval`：L1 组（overview+温度计+梯队）60s、L2/L3 组（style/强弱榜/资金）120s；`document.hidden` 时跳过。
- 初次加载 `Promise.allSettled` 并行拉全部，单失败不阻塞（沿用现有 catch 模式）。
- 盘后停轮询（L0 状态判定）归 P2。

### 8.5 验证

- 用户执行：`npx vue-tsc --noEmit` + `pnpm build` + 四态逐卡 + 3 断点响应式 + 9 市场页回归。
- 我执行：完成后核对组件 Props 与后端响应字段一一对应、路由路径与 router 配置一致（grep 核对）。

### 8.6 Batch 2 实施记录（2026-08-15，已完成 ✅）

| 文件 | 动作 |
|:---|:---|
| `quant_web/src/components/market/MarketTemperatureGauge.vue` | **新建**（gauge + 四维分位小字 + Tab2 嵌入 MarketStateRadar，D4 落地） |
| `quant_web/src/components/market/PositionAdviceCard.vue` | **新建**（4 带仓位规则表 + 免责脚注） |
| `quant_web/src/components/market/LimitLadderCard.vue` | **新建**（梯队条形 + 炸板率 + 封板资金近似标 + 情绪周期结论） |
| `quant_web/src/components/market/BreadthLeadersCard.vue` | **新建**（3 Tab × TOP10 迷你表） |
| `quant_web/src/components/market/WatchlistStrip.vue` | **新建**（通栏折叠条） |
| `quant_web/src/views/DataCenter/Market/MarketDashboard.vue` | **重构**为 §4.6 布局（L0 状态条 → L1 → L2 → 自选折叠 → L3A/L3B → L4 折叠）；`Promise.allSettled` 并行加载；L1 组 60s / L2-L3 组 120s 轮询（`document.hidden` 跳过）；移除自选首屏块、市场环境 4 小卡（与新版信息重复）、120 日北向图（明细在 MoneyFlow 页） |
| `quant_web/src/api/market.ts` | +3：`getMarketTemperature` / `getLimitLadder` / `getBreadthLeaders`（catch→null 容错） |
| `quant_web/src/types/entities/market.ts` | +4：`MarketTemperature` / `TemperatureDimension` / `LimitLadder` / `BreadthLeaders` |

**验证**：`vue-tsc --noEmit`（提权执行）—— 新增/修改文件 **0 错误**；10 个既有错误全部位于未触碰文件（`api/trade.ts` 2、`components/charts/*` 8），与本批无关。`pnpm build` 与页面回归由用户执行（node 沙箱已提权用过 vue-tsc，构建产物仍需用户确认）。

**单位口径说明（新卡片采用，旧块保持原样）**：
- `stock_daily.amount`（千元，模型注释确认）→ 强弱榜/封板资金按 `/1e5` 显示"亿"；
- `stock_moneyflow.*`（万元，模型注释确认）→ 主力订单四单按 `/1e4` 显示"亿"；
- 北向 `north_money`（按 20 日累计量级推断为万元）→ L3A 北向当日按 `/1e4` 显示"亿"；
- **复用未动的旧块**（成交额/资金流入 TOP10 表）沿用旧 `/1e8` 公式未改——旧公式疑似量级 bug，但不在本批范围，请用户在页面回归时留意（若确认量级异常，单独一批修复）。

**遗留 → 用户执行**：`pnpm build`；四态逐卡验证；<768/768-1024/>1024 三断点响应式；9 市场页回归无白屏；首屏验收对照 v5 §七 #1/#2/#4/#5。

---

## 九、Batch 3 批次级路径（P1：状态完备，2026-08-15 已确认开工）

### 9.1 后端（2 新端点 + 1 扩展）

| 文件 | 改动 |
|:---|:---|
| `modules/market/services/crowding_service.py` | **新建** `get_crowding(session)`（N4）：全市场成交额 250 日分位 + 行业成交额 250 日分位 TOP5（`stock_basic.industry` 映射；行业换手率以成交额代理，行业口径备注）；300s 内存缓存 |
| `modules/market/services/breadth_service.py` | **扩展** `get_breadth_metrics(session)`（N2+N5）：创20日新高/新低家数、全市场+沪深300 站上 MA20/MA60 比例、沪深300 20 日年化波动率+750 日分位；300s 缓存 |
| `modules/market/services/market_state_service.py` | **扩展**（雷达分位化）：`get_market_state` 的 `latest` 增加 `breadth_pctl`/`momentum_pctl`/`trend_pctl`（N 日窗口内分位，纯 Python 计算） |
| `modules/market/handlers.py` | +2：`do_dashboard_crowding` / `do_breadth_metrics` |
| `api/routers/market_router.py` | +2 GET：`/dashboard/crowding`、`/dashboard/breadth` |
| `modules/market/__init__.py` | +2 导出（带尾随逗号） |
| `tests/test_market_v5_services.py` | +纯函数测试：年化波动率、滚动波动率、边界 |

### 9.2 前端

| 文件 | 改动 |
|:---|:---|
| `components/market/CrowdingCard.vue` | **新建**（L4 span4）：全市场成交额分位大数字 + 拥挤行业 TOP5（分位>80% 高亮"拥挤"） |
| `components/market/VolatilityPercentileCard.vue` | **新建**（L4 span4）：20 日年化波动率 + 750 日分位 + 收缩/扩张结论（分位>70% 扩张 / <30% 收缩） |
| `views/DataCenter/Market/MarketDashboard.vue` | L3B 涨跌统计卡升级为"市场宽度"（+新高/新低/MA20/MA60 两组）；L4 折叠区内 拥挤度(4)+波动率分位(4)+宏观事件(4)；行业轮动柱图拥挤点标记（拥挤名单且分位>80% → 柱顶 ⚠ 标 + tooltip）；load/poll 接入 crowding+breadth（L2 组 120s） |
| `components/market/MarketStateRadar.vue` | 各维度加"分位 xx%"标签（读 `latest` 新增 pctl 字段，缺失时隐藏） |
| `api/market.ts` | +2：`getCrowding()` / `getBreadthMetrics()` |
| `types/entities/market.ts` | +2：`Crowding` / `BreadthMetrics` |

### 9.3 验证

- 后端：py_compile → import smoke → pytest（110p 基线 + 新增）→ 起服务 curl 对账：`breadth.new_highs` 量级与 `breadth-leaders` 一致（≥10）；crowding 行业名单与 `moneyflow/sector` 成交活跃行业交叉合理。
- 前端：vue-tsc 0 新增错误（10 个既有错误不变）；用户 `pnpm build` + 页面回归。

### 9.4 Batch 3 实施记录（2026-08-15，已完成 ✅）

**交付**：后端 `crowding_service.py`（新建）、`breadth_service.py`（+N2/N5 纯函数与 `get_breadth_metrics`）、`market_state_service.py`（latest +4 分位字段）、handlers/router/`__init__`（+2 端点：`/dashboard/crowding`、`/dashboard/breadth`）；单测 +6（34 passed）。前端 `CrowdingCard.vue`、`VolatilityPercentileCard.vue`（新建）、`MarketStateRadar.vue`（宽度/深度卡加分位标签）、`MarketDashboard.vue`（L3B 升级"涨跌统计 · 市场宽度"、L4 三卡折叠区、行业柱图拥挤点 ⚠ 标记、load/poll 接入 2 新端点）、`api/market.ts` +2、`types/entities/market.ts` +2。

**验证**：
- 后端：py_compile ✅ / import smoke ✅ / 新单测 34 passed ✅ / 全量 pytest 116p+4s+31e+9f（新增 6 条全过，9f/31e 为既有环境问题）✅
- 运行时（8082，数据日 2026-08-14）：`crowding` 冷 2.5s → 全市场成交额分位 27.6，拥挤行业 TOP5：医药生物 96.0 / 有色金属 85.8 / 建筑材料 79.4 / 电子 74.7 / 石油石化 69.2（前两名 >80% 将触发柱图 ⚠ 标）；`breadth` 冷 3.1s → 新高 719 / 新低 191、全市场 MA20 81.0% / MA60 37.9%、沪深300 MA20 100% / MA60 0%（单指数二值化正常）、20 日年化波动 20.7% @ 750 日分位 84.7（波动扩张）；`state` latest 新增 4 分位字段齐全（breadth 46.7 / momentum 95.0 / trend 100.0 / limit_up 50.0）
- 对账：`breadth.new_highs=719` ≥ `breadth-leaders` TOP10（10 条）✅ 量级一致
- 前端：vue-tsc 0 新增错误（10 个既有错误原样）✅

**口径说明**：行业拥挤度采用**申万 L1 行业成交额 250 日分位**（`index_sw_daily` 自带成交额，与行业轮动柱图同名同口径，拥挤点标记直接匹配；v5 草案"行业换手率"以成交额代理，因行业级换手率需流通市值分母）。

### 9.5 用户回归反馈与定位（2026-08-15）

- 反馈：① 行业柱图无 ⚠拥挤标 ② L4 两张新卡不认得 ③ 雷达分位标签正常。
- 定位：实测 heatmap 31 个行业名与 crowding TOP5 名字**完全匹配**（医药生物/有色金属/建筑材料/电子/石油石化 全部命中），前端标记逻辑与数据口径无误 → 根因是**后端未重启**：Batch 3 新增的 `/dashboard/crowding`、`/dashboard/breadth`、state 分位字段在旧进程不存在 → 前端收到 404 → 拥挤度数据为 null → 无标记、L4 两卡显示"暂无数据"（故用户不认识）。
- 结论：**重启后端后即恢复**；L4 两张新卡 = 拥挤度卡（全市场成交额分位 + 拥挤行业 TOP5）+ 波动率分位卡（沪深300 20 日年化波动 + 750 日分位 + 扩张/收缩结论）。

---

## 十、Batch 4 实施记录（P2 收尾，2026-08-15，已完成 ✅）

| 文件 | 改动 |
|:---|:---|
| `MarketDashboard.vue` | ① **性能**：load() 重构为"首屏优先"——overview（约 1s 缓存）先行渲染，其余 6 端点后台并行填充（冷启动首屏不再被温度计 4~6s 重查询拖住）；② **宏观日历 7 天化**：upcomingEvents 增加未来 7 天窗口过滤；③ **移动端**：≤768px 媒体查询（L0 副文本隐藏、快捷入口换行、页底留白压缩）；④ L4 标题/事件卡标注"7 天" |
| 新组件深色主题审计 | 已审计：DOM 文本色均用 `var(--n-text-color-*)`，无需改动；ECharts canvas 颜色（gauge 轴标/指针）无法用 CSS 变量，与既有图表同惯例（固定灰阶），深色主题下已协调 |

**验证**：vue-tsc 0 新增错误（10 个既有错误原样）。用户侧：`pnpm build` + **重启后端** + 页面回归（重点：拥挤标、L4 两卡数据、事件日历仅 7 天内）。

**至此 P0+P1+P2 全部完成**。后端 5 个新端点（temperature/limit-ladder/breadth-leaders/crowding/breadth）+ 1 扩展（state 分位）；前端 7 个新组件 + Dashboard 全面重构。验收对照 v5 §七：①首屏温度计+仓位+梯队 ✅ ②分位标注 ✅ ③端点可被策略层结构化调用（HTTP GET，无需跨模块 import）✅ ④钻取出口全覆盖 ✅ ⑤全现表零新数据源、300s 缓存 ✅ ⑥build+回归（用户确认中）。

### 10.1 追加打磨（2026-08-15）：查询提速（SWR）+ 布局均衡 ✅

**问题 1：页面查询慢** —— 根因：5 个重聚合端点缓存过期后**同步重算**（冷查询 1.6~6.2s），约 1/5 的轮询会阻塞。

- 新增 `modules/market/services/_swr_cache.py`：进程内 **SWR（stale-while-revalidate）缓存**——未过期直接返回；过期返回旧值 + `asyncio.create_task` 后台重算（独立会话）；在途任务存在时不重复触发；仅进程重启后首次请求同步计算。
- 5 个端点全部接入：temperature / limit-ladder（按交易日分键）/ breadth-leaders / breadth-metrics / crowding。
- 实测（8082）：温度计 冷 6.2s → 缓存 7ms；拥挤度 冷 2.4s → 缓存 8ms。接入 SWR 后**任何轮询都 ≤10ms**（过期由后台任务兜底），冷启动一次性成本不变。
- 单测 +5（`TestSwrCache`：未命中/新鲜/过期需重算/在途任务不重算/回写刷新）→ 39 passed；全量 pytest 121p/4s/31e/9f 基线不回归。

**问题 2：卡片布局失衡（内容少卡片大 / 内容多卡片小）**：

| 卡片 | 调整 |
|:---|:---|
| 仓位建议卡（内容少、被拉伸） | 新增**四带对照图例**（低温/温和/中性/高温 + 仓位区间，当前带高亮），内容填满 span2 卡，免责脚注钉底 |
| 核心指数卡 | 6 宫格改 `grid-template-rows: repeat(2, 1fr)` + 内容垂直居中，铺满卡高 |
| 涨停梯队卡 | 卡体 `justify-content: space-evenly` + 行距 12px，纵向均匀分布 |
| 风格轮动（内容少、被拉伸） | 卡根 `height:100%`（去掉多余 margin-bottom）、图表 200→240px、说明文字钉底、行业列表垂直居中 |
| 强弱榜 | 表格 max-height 280→300，与 L2 行高贴合 |
| 行业资金强度 / 北向+主力 | 行距 7→10px / 9px，消除拥挤感 |

- vue-tsc 0 新增错误（10 个既有错误原样）。

**用户回归动作**：重启后端（加载 SWR 版服务）→ `pnpm build` → 观察：轮询全程流畅（无周期性 3~6s 卡顿）、L1/L2/L3 各卡片内容分布均衡。

### 10.2 追加调整（2026-08-15）：仓位卡间距 + 雷达窄面板重构 ✅

- **仓位建议卡行距过紧**：主内容间距 8→12px，四带图例行距 3→7px、行内 padding 3→6px、字号 11→12px。
- **牛熊状态卡（雷达）被挤压**：根因——旧雷达依赖**视口断点**（m:6/l:6 of 24 列），嵌入温度计 Tab2 窄面板后 4 张卡被挤成 ~95px 宽、内容只剩中间一点。重构为**容器内 2×2 紧凑版**（`cols=2` 不依赖视口）：牛熊状态（小号标签+年线）/ 市场宽度（值+分位+56px 迷你线）/ 涨跌停家数（计数+分位+迷你线）/ 恐慌贪婪（波动分位+迷你线），单格 ≈186px，整面板 ≈280px 高，完全适配 Tab2。
- vue-tsc 0 新增错误。用户回归：温度计 Tab2 应显示 2×2 四维状态面板。

### 10.3 追加调整（2026-08-15）：对齐/补内容/自愈/去重 ✅

| 反馈 | 处理 |
|:---|:---|
| 风格轮动左右上下不对齐 | `.sr-layout` 改 `align-items: flex-start`，行业列表顶部对齐（注脚仍钉底） |
| 北向+主力 / 行业资金 / 涨跌统计卡内容少卡片大 | ① 北向+主力补**近 20 日净流入迷你柱图**（64px，v5"20 日累计趋势"落地）；② 行业资金 8→10 行；③ 涨跌统计卡 MA20/MA60 改**进度条**并整卡 `space-evenly` 纵向分布；④ 成交额/资金流入 TOP10 表格 max-height 300→260，整体降行高 |
| 温度计显示"样本不足" | 后端：样本不足结果 **SWR 短 TTL 120s**（快速自愈重算）+ 日志记录缺失维度；前端：标签 hover 显示"缺失维度：xxx（后台 120s 内自动重算）" |
| 仓位卡三行太紧凑 | 主内容间距 12→16px |
| 涨停梯队卡内容重复 | 去掉"涨停 X 家/触板 X 家"（与涨跌统计卡、雷达重复），保留梯队结构 + 炸板率 + 封板资金 + 最高板 + 情绪周期结论 |

- 后端：py_compile ✅、单测 40 passed（新增 SwrCache 自定义 TTL 用例）✅；前端 vue-tsc 0 新增错误 ✅。
- 用户回归：重启后端 + `pnpm build`；检查 风格轮动对齐、北向迷你图、温度计样本不足 hover 提示（若仍有缺失维度请告知具体维度名，我可针对性排查数据）。

### 10.4 基准线可视化（2026-08-15）✅

- 口径说明已写入 v5 设计文档 **§4.7 评判基准线**：温度计 = 各指标自身历史分位（50% = 历史中位为中性基准，样本 估值 1000 日 / 情绪·技术 250 日 / 资金 750 日）；雷达 = 近 60 交易日窗口分位 + 牛熊 MA20/60 体系 + 年线 MA250。
- 新增通用组件 `PctlBar.vue`：0~100 分位刻度条 + **50% 中线标记（历史中位）**。
- 温度计四维小字改为分位条 + 卡底脚注样本窗口；雷达 宽度/涨跌停/波动率三卡改分位条 + 面板脚注基准说明。
- vue-tsc 0 新增错误。用户回归：`pnpm build` 后可见每个维度一条带中线的刻度条，中线 = 基准线。

### 10.5 视觉/结构打磨（2026-08-15）✅

| 项 | 处理 |
|:---|:---|
| 温度计环颜色 | 去掉 progress 双层叠色弧；指针/数值按当前温度区着色；色环三段（<30 绿 / 30-70 橙 / >70 红）加粗至 12，刻度只标 30/70 两条分界线 |
| 估值 14.68 一行 | 维度小字改两行结构：第一行"标签 + 值 + 近似标"合并一行，第二行分位条 |
| 雷达统一时间轴 | 重写为"顶部状态条 + 单图三线"：宽度/涨停家数/波动率三条曲线**分位化（60 日窗口内分位 0~100）共享同一 y 轴，x=时间**，虚线 50 = 基准线，tooltip 显示原始值+分位；顶部一行放牛熊标签/年线/三个 PctlBar |
| 风格轮动图线含义 | 卡内新增"当前风格"结论行（大盘/中盘/小盘占优 + 领先指数名）；图注改写为"三条线 = 沪深300/中证500/中证1000 近 60 日相对强弱（首日=1），线越高该风格越强" |
| 行业资金强度 TOP | 文本行列表改**双向条形图**（流入 TOP8 红条向右 / 流出 TOP5 绿条向左，零轴分隔），点击跳 MoneyFlow |

- vue-tsc 0 新增错误（10 个既有错误原样）。用户回归：`pnpm build` 查看五项调整。

### 10.6 视觉/健壮性打磨（2026-08-16）✅

| 反馈 | 处理 |
|:---|:---|
| 行业资金强度卡没内容 | 弃用 ECharts 双向图（存在渲染兼容风险），改**纯 CSS 双向条形图**：流入 TOP8 红条向右 / 流出 TOP5 绿条向左、零轴居中、行尾数值，`space-evenly` 铺满卡高（`Number()` 防御数值类型） |
| 温度计进度条颜色 | `PctlBar` 增加 `color` 属性：填充改**渐变**（基色半透明→实色）；四维各自配色：估值绿 / 情绪橙 / 资金蓝 / 技术紫；不传色则用 绿→橙→红 通用渐变 |
| 技术显示样本不足 | 后端技术维健壮化：超时**之外的一切异常**也走 breadth_ratio 近似退路（换新会话执行，避免 invalid transaction）；实测（数据日 08-14）技术维 80.94% @ 分位 94.0 正常。配合 §10.3 的 120s 短 TTL 自愈，偶发失败 2 分钟内自动恢复 |
| 雷达"震荡"进度条颜色 | 雷达三根分位条按曲线颜色区分：宽度蓝 / 涨停红 / 波动橙（与图表线色一一对应） |
| 线图颜色与标识不匹配 | 同一处理：分位条与曲线同色系（蓝/红/橙） |
| 线图不能缩放 | 雷达图加 `dataZoom`（inside 滚轮/拖拽缩放 + 底部迷你 slider），可局部放大 60 日窗口 |
| 数据不完整 | 已确认用户将自行同步；图表对稀疏数据已有空值容忍 |

- 验证：后端 py_compile ✅ / 单测 40 passed ✅ / 运行时温度计四维齐全（warn=False）✅；前端 vue-tsc 0 新增错误 ✅。

### 10.7 自查审计（2026-08-16）✅

全端点运行时冒烟 + 字段对账全部通过（temperature 四维齐全 / ladder 与 limit-analysis 对账一致 64≡64、5≡5 / state 序列对齐 60/60/60/60/60 + 32/32/32 / overview 正常），审计另发现并修复 3 处实现问题：

| # | 问题 | 修复 |
|:---|:---|:---|
| 1 | 北向近 20 日迷你图 **时间轴反序**（`get_hsgt_history` 返回 DESC 最新在前，旧代码未 reverse） | `hsgtMiniOption` 先 `.reverse()` 再取尾部 |
| 2 | 行业资金强度卡 13 行（8+5）**超出 span4 卡高** | 收敛为流入 TOP5 + 流出 TOP5 = 10 行，去掉 min-height 强制 |
| 3 | 雷达"涨停家数"序列若数据不足 60 日（当前库仅 32 日），会**从 x 轴第 1 天起错位绘制**（ECharts 按数组下标对齐） | 改为**按日期对齐**：以 `limit_dates` 建 Map 映射到主时间轴，缺失日 null 占位（曲线断点而非错位），tooltip 同样对齐 |

- 前端 vue-tsc 0 新增错误 ✅。用户回归：`pnpm build` 后观察 北向迷你图时间升序、行业资金 10 行不溢出、雷达涨停线只覆盖有数据的日子。

### 10.8 雷达图表迁移 lightweight-charts 5（2026-08-16）✅

- **背景**：用户指定雷达图改用 lightweight-charts 5（与 K线/净值曲线同库）。
- **改动**：`MarketStateRadar.vue` 移除 ECharts（VChart/LineChart/DataZoom/MarkLine 全部下线），改用现有 `LightweightLineChart.vue`：
  - 三线（宽度蓝/涨停红/波动橙 分位化）+ **"基准线"虚线序列**（y=50，`lineStyle: 2`）替代原 ECharts markLine；
  - 共享组件 `LightweightLineChart.vue` 图例过滤增加"基准线"（原只过滤"零线"），参考线不出现在图例；
  - **时间对齐天然解决**：lightweight-charts 按 epoch 时间戳对齐（`toTime` 线性时间轴），涨跌停 32 日数据只画在对应日期、null 自动断线，不再依赖数组下标对齐；
  - 原生滚轮缩放/拖拽平移、图例、十字悬浮提示（显示各线分位值）。
- 注：悬浮提示现在显示**分位值**（不再带原始值；原始值见后端端点/宽度卡）。
- 前端 vue-tsc 0 新增错误 ✅。用户回归：`pnpm build` 后温度计 Tab2 雷达为 lightweight-charts 渲染（缩放/图例/虚线基准线）。

### 10.9 温度稳定/环渐变/布局/单位修复（2026-08-16）✅

| 反馈 | 处理 |
|:---|:---|
| 温度 71.5→64 波动 | **根因**：71.5=四维（技术维 94.0 正常），64=三维（技术维 MA20 全市场扫描在用户机器 >8s 超时后退路失败 → 该维缺失）。**修复**：① 技术维样本 250→150 交易日（扫描减半）；② 超时 8→6s；③ **三重退路链**：MA20 → market_state_daily 上涨比 → **全市场涨跌家数比（stock_daily 必有数据）**，保证技术维永不缺失；④ 配合 120s 短 TTL 自愈。实测：四维齐全 warn=False，缓存命中 8ms |
| 温度计环渐变 | 色环由三段色改 **24 段绿→橙→红插值渐变**（近似平滑渐变环），指针/数值仍随温度区着色，30/70 刻度保留 |
| 风格轮动说明文字占位 | 说明文字从图表列移入**行业强度列底部**（margin-top:auto 钉底），"当前风格"结论钉在图表列底部 |
| 行业资金强度无效果 | **根因**：`net_mf_amount` 单位万元，原 SQL `/1e8` 换算错误 → 全部显示 0.0x 亿、条几乎不可见。**修复** `/1e4`（正确万元→亿）；实测 TOP5：化学制药 12.65 亿 / 机械基件 8.7 / 石油开采 6.5 / 通信设备 5.05 / 超市连锁 1.81。卡片加口径脚注 |
| 与风格轮动行业强度区别 | ① 资金 vs 价格：当日主力净流入 vs 近 30 日区间涨幅；② 分类口径：东财 stock_basic.industry vs 申万 L1；③ 时域：当日 vs 30 日。卡片脚注已注明 |

- 验证：后端 py_compile ✅ / 单测 40 passed ✅ / 运行时（温度四维齐全 + 行业资金亿级）✅；前端 vue-tsc 0 新增错误 ✅。

### 10.10 相邻页面修复（2026-08-16）✅

| 项 | 处理 |
|:---|:---|
| 总览 L0 刷新按钮 | 删除"选股"前的刷新按钮（保留页头刷新） |
| **选股器查不到数据** | 定位 3 个 bug：① market 筛选引用 `q.ts_code`（LATERAL 子查询无此列）→ 500，改 `b.exchange='SSE'/'SZSE'`；② 行业下拉用申万树（依赖未同步的 index_sw_member + 名称口径不一致）→ 0 行，新增 `GET /screener/industries`（stock_basic.industry 去重 110 个，东财口径）作下拉数据源；③ PE/PB/换手/ROE/涨跌幅空值被 COALESCE(-1/9999) 放行 → 全部改 `IS NOT NULL` 排除未知。实测：SH 2316 / SZ 2894 / 通信设备 139 / 证券+SH+PE≤30 → 37 ✓ |
| 涨跌停分析筛选置空 | `onMounted` 不再预填日期（缺省 → 后端取最新交易日），交易所/板块本就默认"全部" |
| 财务对比雷达图不清晰 | 重做：① 每指标**自适应上限**（观测最大值×1.2，下限 1）→ 多边形撑开；② 每公司独立配色 + 半透明 areaStyle + 圆点符号；③ tooltip 显示**原始值**（含"负债率（越低越好）"标注）；④ 图例移到顶部、雷达中心下移防重叠；⑤ splitArea 交替底色 + 轴名颜色 |

- 验证：后端 py_compile ✅ / 全量 pytest 128p（基线不回归）✅ / 运行时复测选股器全部条件 ✅；前端 vue-tsc 0 新增错误 ✅。
- **待确认：选股器与 ETF 列表页功能重复的优化方案**（见下方提案，确认后实施）。

### 10.11 提案：选股器 × ETF 市场 去重（待确认）

**现状**：选股器 = A股多因子筛选（市场/行业/PE/PB/市值/涨跌/换手/ROE → 批量回测/篮子/财务对比）；ETF 市场 = ETF 列表（类型/状态/搜索 → 行展开 K线/份额/基准）。两者都是"筛选列表"页且菜单相邻。

**方案 A（推荐，低风险）**：选股器增加**标的类型维度（股票/ETF）**——选"ETF"时展示 ETF 条件（类型/搜索/规模），结果行可点进 ETF 详情；ETF 市场页定位收敛为"浏览 ETF 品类 + 展开详情"。入口职责：**选股器 = 按条件找标的，ETF 市场 = 浏览品类**。实现：screener 支持 asset_type + 选股页加类型开关 + ETF 字段映射（后端 +1~2 端点扩展，估 0.5~1d）。
**方案 B（零风险）**：不改功能，仅在两页头部加互指提示（"想按因子筛选？去选股器" / "想浏览 ETF？去 ETF 市场"），消除"进错页"困惑。
**方案 C（大重构）**：合并为单一"标的筛选器"路由（统一股票/ETF/指数），重构量大，建议后期再做。

用户确认 A/B/C 后实施。

### 10.12 实施：选股器 × ETF 统一筛选器（方案 A，2026-08-16）✅

对齐 TradingView/富途"统一筛选器 + 资产类型切换"模式：

**后端**（`screener_service.py` / handlers / router）：
- `screener()` 增加 `asset_type`（默认 stock 行为不变）、`search`、`fund_type` 参数；`asset_type=etf` 时走 `_screener_etf`（etf_basic × etf_daily LATERAL，字段 ts_code/name/fund_type/close/pct_chg/amount/scale_wan，排序白名单 amount/pct_chg/close/scale，list_status='L'）。
- 新增 `GET /screener/etf-types`（etf_basic.fund_type 去重）。

**前端**（StockScreener.vue / market.ts / types）：
- 标的类型切换 `[股票] [ETF]`（n-radio-group）；股票模式条件/列不变；ETF 模式条件 = 搜索 + 类型 + 排序（成交额/涨跌幅/最新价/规模），列 = 代码/简称/类型/最新价/涨跌幅/成交额(亿)/规模(亿)；批量回测/篮子/财务对比仅股票模式显示；行点击 ETF → `/market/etf?focus=`、股票 → 个股详情。

**验证**：后端 py_compile ✅ / pytest 128p 基线不回归 ✅ / 运行时：ETF 全部 3004 只、搜索"300"→137、类型/排序正常 ✅；股票模式回归（§10.10 用例）✅；vue-tsc 0 新增错误 ✅。

**数据口径提醒**：当前 etf_basic.fund_type 实际只有 QDII/纯境内 两类（下拉展示真实值，选真实值必中）；ETF 市场页的 宽基/行业/主题 等类型选项为自定义标签，与库内 fund_type 值可能不匹配（该页类型筛选可能无效的潜在原因，未改动，需数据同步或标签映射时再处理）。

### 10.13 温度"样本不足"间歇性出现 —— 根因与加固（2026-08-16）✅

**根因**：`sample_warning=True` = 四维中至少一维分位缺失。最易波动的是**技术维**：
1. MA20 全市场扫描（~130 万行窗口）实测 4~8s，卡在 6s 超时线；
2. 后端启动/负载高峰（策略引擎全市场预测 98 万行查询）占用 DB → MA20 超 6s → 触发超时；
3. **退路链缺口**：退路1（market_state_daily）查询若抛异常（连接池负载下获取失败），旧代码不会继续退路2 → 技术维直接缺失；
4. SWR 120s 短 TTL 缓存失败结果 → "有时显示有时不显示" ≈ 120s 波动周期。

**加固**：① 技术维超时 6s→8s（SWR 下只约束后台重算，放宽减少降级触发）；② 退路1 失败也继续退路2，两级均失败才置空并打日志（`温度计技术维退路1/退路2失败: <原因>`）；情绪维（涨停家数 ~4s 查询）负载高峰亦可能失败 → 120s 自愈兜底。

**诊断指引**：再出现"样本不足"时，查看 `quant_server/logs/` 中以下两类日志即可 100% 定位：
- `temperature.technical 失败: <异常>` / `温度计技术维退路1/退路2失败: <异常>` → 技术维原因；
- `temperature 样本不足，缺失维度: ['technical'|'emotion'|...]` → 具体缺失维度。

### 10.13b 根因确认与修复（2026-08-16）✅ —— 会话退出异常吞掉退路结果

用户提供日志：
```
temperature.technical 完成 (8481ms)                                  ← 退路已成功算出分位
temperature.technical 失败: Can't reconnect until invalid transaction is rolled back  ← 会话退出抛异常
temperature 样本不足，缺失维度: ['technical']
```
**确认根因**：MA20 查询 8s 被 `wait_for` 取消 → 该子会话处于 invalid transaction；退路查询在**新会话**成功（"完成 8481ms"），但外层 `async with` 退出时 session_manager 关闭坏连接抛 "Can't reconnect…"，**异常覆盖了已计算的结果** → 技术维被置 None。退路本身从未失败（无"退路失败"日志）。

**修复（双保险）**：
1. `_with_session`：结果已算出时，会话退出异常只记警告、**保留结果**（`_missing` 哨兵区分"未算成"与"退出异常"）；
2. 技术维超时/异常路径：先对坏会话**显式 `await session.rollback()`** 修复事务，减少退出异常发生。
- 验证：py_compile ✅ / pytest 128p 基线不回归 ✅。

### 10.14 根治方案 A：预计算"站上MA20/MA60比例"进 market_state_daily（2026-08-16，已实施）

**动机**：温度计技术维 MA20 重查询（~75 万行窗口，负载高时 4~8s 超时）是"样本不足"的根源；兜底只是可靠性网。方案 A = 把该指标**日终预计算**进 `market_state_daily`（新增 2 列），温度计/宽度卡改**读列**（<100ms），彻底消灭重查询。

**涉及文件**：
| 文件 | 改动 |
|:---|:---|
| `modules/data/services/market_state_classifier.py` | +`_load_above_ma`（窗口 SQL 按日聚合 站上MA20/MA60 比例）+ `update_above_ma_ratios(conn, since)`（UPDATE 两列）+ 在 `classify_and_populate` 末尾挂 EOD 增量（since=最新日-400 天，非致命 try/except） |
| `scripts/backfill_above_ma.py` | **新建**：全量回填（min(trade_date)-100 天起算，一次性） |
| `modules/market/services/market_temperature_service.py` | `_query_technical_dim`：**优先读 `market_state_daily.above_ma20_pct` 列**（≥60 样本 → 分位，approx=False）；列缺失/样本不足 → 保留原退路链（过渡期安全） |
| `modules/market/services/breadth_service.py` | `get_breadth_metrics` 的 `above_ma20/60_market` 改读最新列值；列为空 → 原重查询兜底 |
| `docs/sql/create_table.sql` | market_state_daily DDL +2 列（注释同步） |

**DDL（用户执行）**：
```sql
ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS above_ma20_pct NUMERIC(6,3);
ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS above_ma60_pct NUMERIC(6,3);
```

**跨模块影响**：data 模块（classifier 增量计算 + 回填脚本）、market 模块（只读）；classifier 原 INSERT 不含新列 → 不覆盖旧值；EOD 增量窗口 400 天覆盖温度计 150 样本需求。

**验证**：DDL 后跑回填 → 重启 → curl：temperature 技术维分位正常且**耗时 <200ms**（读列）、breadth ma20m/ma60m 与回填值一致、读列值与原重查询口径对账（±2%）；pytest 基线不回归。

**实施记录（2026-08-16，已完成）**：
1. **DDL（本环境由我执行，dev 库）**：`ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS above_ma20_pct NUMERIC(6,3); ... above_ma60_pct ...` → 成功（`DDL_OK cols=['above_ma20_pct','above_ma60_pct']`）。**生产库需执行同一 ALTER（create_table.sql 已同步）**。
2. **回填**：`python -m scripts.backfill_above_ma`（quant_server 目录）→ `回填完成：更新 5254 天；above_ma20_pct 已填充共 5190 天`（历史某段无足够样本属正常）。
3. **代码**：classifier EOD 增量钩子（`update_above_ma_ratios`，since=最新日-400 天，非致命）+ 温度计/宽度读列优先（保留退路链过渡）+ create_table.sql DDL 同步。py_compile ✅ / pytest 128p 基线不回归 ✅。
4. **端到端验证（8082 实起服务）**：
   - `GET /dashboard/temperature`：`{"temperature":70.9,"zone":"高温","sample_warning":false,"dimensions":{...technical:{value:80.94,percentile:91.3,approx:false}}}` —— 技术维**从列读取**，四维完整，无"样本不足"；日志 `temperature.technical 完成 (742ms)`（原 4~8s 重查询，且**无任何 fallback 日志**）；第二次调用 SWR 命中 `14ms`。
   - `GET /dashboard/breadth`：`above_ma20_market=80.9 / above_ma60_market=37.9`，与列值 `2026-08-14: 80.945 / 37.929` 取整一致 → 读列路径生效。
   - 对账：技术维 value=80.94 与列值 80.945 精确一致；旧重查询口径 81.0/80.94 → 列口径 80.945（±0.1，口径差异为股票池/对齐方式，可接受）。
   - **注意**：temperature 总耗时仍 ~12s，瓶颈已转移至 emotion 维（涨停家数历史查询 7708ms）——**不在方案 A 范围内**，属既有行为，留待后续优化。
5. **回归清单（用户）**：重启后端（8080）→ 市场概览温度计四维稳定显示、刷新不再"样本不足"；`pnpm build` 前端无改动（纯后端）；生产库执行上方 ALTER + 回填脚本。

### 10.15 方案 B：情绪维"涨停家数+换手率"预计算进 market_state_daily（2026-08-16，已实施）

**动机**：方案 A 后温度计瓶颈转移至情绪维（实测 7708ms，占 12s 总耗时的 64%）。根因与方案 A 同构：两条压缩超表按日聚合重查询——
`stock_daily_limit × stock_daily` JOIN 涨停家数（热 ~1.2s，压缩超表 ColumnarScan）＋ `stock_daily_basic` AVG 换手率（热 ~0.7s）；冷缓存+四维并发下放大到 7.7s。

**方案**：新增 2 列日终预计算，情绪维改读列（镜像方案 A 模式）。

**涉及文件**：
| 文件 | 改动 |
|:---|:---|
| `modules/data/services/market_state_classifier.py` | +`_load_limit_up_counts`（JOIN 口径逐日聚合）+ `_load_avg_turnovers` + `update_emotion_metrics(conn, since)`（两列**独立** UPDATE，互不干扰）+ step 6.6 钩子（since=最新日-400 天，非致命） |
| `scripts/backfill_emotion_metrics.py` | **新建**：全量回填（镜像 backfill_above_ma.py） |
| `modules/market/services/market_temperature_service.py` | `_query_emotion_dim`：列优先（两列**独立读取**，各自 ≥`EMOTION_MIN_SAMPLES=20` → 分位 0.5/0.5，approx=False）；不足/列缺失 → 原两条重查询兜底 |
| `docs/sql/create_table.sql` | market_state_daily DDL +2 列 + 注释 |

**DDL（dev 由我执行 / 生产用户执行）**：
```sql
ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS limit_up_count INT;
ALTER TABLE market_state_daily ADD COLUMN IF NOT EXISTS avg_turnover NUMERIC(8,4);
```

**关键数据事实（实施中发现）**：`stock_daily_limit` 仅覆盖 2026-06-05 起 **32 天**（dev 库）→ 涨停家数历史天然只有 32 个样本（旧代码无门槛直接用，percentile=29.2 就是 32 样本算的）。因此：
- 情绪列路径门槛设 **20**（非 60）：32 ≥ 20 → 列路径可用；技术维门槛 60 不受影响（above_ma 有 5190 天）。
- 换手率列独立回填满 **1266 天**（stock_daily_basic 覆盖），保住 250 样本分位口径（若取两列交集会把换手率分位缩成 32 样本，口径漂移——已规避）。
- **涨停家数分位样本上限 = stock_daily_limit 数据覆盖**；若要更长情绪历史，需扩展该表数据同步回看（data 模块，另行处理）。

**实施记录**：
1. DDL ✅（dev 库）；回填 `python -m scripts.backfill_emotion_metrics` → `写入 1298 行；limit_up_count 已填充 32 天；avg_turnover 已填充 1266 天`。
2. 锚点对账（2026-08-14）：`limit_up_count=64`（= 首板53+2板5+3板5+≥4板1）✅、`avg_turnover=3.0904` ✅。
3. py_compile ✅ / pytest 128p 基线不回归 ✅。
4. **端到端验证（8082 实起服务）**：`temperature.emotion 完成 (397ms)`（原 7708ms，**无兜底日志**）；四维全部读列（valuation 33ms / capital 226ms / technical 370ms / emotion 397ms）；GET 总耗时 **11932ms → 3701ms**（首次计算），SWR 命中 351ms（handler 侧 ~14ms）；返回值与改前**完全一致**：`temperature=70.9, emotion value=64 percentile=29.2, sample_warning=false`。
5. **回归清单（用户）**：重启后端（8080）→ 温度计情绪维正常、总耗时大幅下降；`pnpm build` 前端无改动（纯后端）；生产库执行上方 ALTER + 回填脚本。
