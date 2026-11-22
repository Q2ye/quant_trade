# LightGBM ETF 抄底策略 — 开发执行计划

> 基于：[[LightGBM_ETF_抄底策略完整技术方案.md]]
> 版本 v1.0 | 2026-07-19
> 状态：执行中

---

## 〇、数据流向全景图

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       数据同步链路 (已有基础设施)                           │
│                                                                          │
│  Tushare Pro API                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ fund_daily      → _sync_etf_daily()      → etf_daily             │   │
│  │ fund_basic      → _sync_etf_basic()      → etf_basic             │   │
│  │ etf_share_size  → _sync_etf_share()      → etf_shares            │   │
│  │ index_dailybasic→ _sync_index_dailybasic()→ index_dailybasic     │   │
│  │ moneyflow_hsgt  → _sync_moneyflow_hsgt() → stock_moneyflow_hsgt  │   │
│  │ sw_daily        → _sync_index_sw_daily() → index_sw_daily        │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ⚠️ market_state_daily 表有DDL但无同步逻辑 → P1 需实现分类器               │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    因子计算链路 (P1 新增)                                  │
│                                                                          │
│  训练时 (批量预计算):                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ etf_daily ────→ ~25 个 window 计算器 ┐                            │   │
│  │ etf_shares ───→ ~5 个 share 计算器   │                            │   │
│  │ index_dailybasic→ ~8 个估值分位计算器 ├→ factor_data (TimescaleDB)│   │
│  │ moneyflow_hsgt → ~3 个资金流计算器   │  ts_code + factor_code     │   │
│  │ index_sw_daily → ~2 个行业排名计算器 │  + trade_date + value     │   │
│  │ market_state_daily → 直接映射 (~8)   │                            │   │
│  │ etf_basic ─────→ ~2 个静态因子      ┘                            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  运行时 (策略 on_bar):                                                     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ SELECT factor_code, factor_value FROM factor_data                 │   │
│  │ WHERE ts_code=:c AND trade_date<=:d AND factor_code=ANY(:list)   │   │
│  │ → 组装65维特征向量 → 缺失值ffill → 时序标准化 → predict_proba     │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────┐
│                    策略信号链路 (复用现有基础设施)                          │
│                                                                          │
│  DataFeedEngine._preload_history → iter_bars → BarData                  │
│      ↓                                                                  │
│  LightGBMBottomStrategy.on_bar(bar) → List[TradingSignal]               │
│      ↓                                                                  │
│  BacktestEngine.run() / TradeEngine (已有)                               │
│                                                                          │
│  策略注册: StrategyRegistry.auto_discover()                              │
│           → strategies/etf/ → StrategyType.ML → LightGBMBottomStrategy   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 一、P0: 数据质量摸底（0.5 天）

### P0.1 验证数据覆盖度

```sql
-- ETF 日线行情覆盖
SELECT ts_code, MIN(trade_date), MAX(trade_date), COUNT(*) AS n
FROM etf_daily
WHERE ts_code = ANY(ARRAY[
  '510050.SH','510300.SH','510500.SH','159919.SZ','510880.SH',
  '512880.SH','512660.SH','512690.SH','512800.SH','512100.SH',
  '159915.SZ','159949.SZ','518880.SH','513100.SH','513050.SH',
  '511010.SH','511260.SH','510310.SH','159865.SZ','159825.SZ',
  '159766.SZ','159781.SZ','512170.SH','159806.SZ','516510.SH',
  '159840.SZ','512400.SH'])
GROUP BY ts_code ORDER BY min_date;

-- 大盘指数每日指标（PE/PB 估值因子来源）
SELECT ts_code, MIN(trade_date), MAX(trade_date), COUNT(*)
FROM index_dailybasic
WHERE ts_code IN ('000016.SH','000300.SH','000905.SH','399006.SZ','000688.SH','000001.SH')
GROUP BY ts_code;

-- ETF 份额数据
SELECT ts_code, MIN(trade_date), MAX(trade_date), COUNT(*)
FROM etf_shares
WHERE ts_code = ANY(ARRAY[/*同上 ETF 列表*/])
GROUP BY ts_code;

-- 北向资金
SELECT MIN(trade_date), MAX(trade_date), COUNT(*) FROM stock_moneyflow_hsgt;

-- 申万行业日线
SELECT COUNT(DISTINCT ts_code) AS n_industries, MIN(trade_date), MAX(trade_date)
FROM index_sw_daily;

-- 市场状态表（大概率 0 行）
SELECT COUNT(*) FROM market_state_daily;

-- feature_sets 表（大概率不存在）
SELECT EXISTS (
  SELECT FROM information_schema.tables WHERE table_name = 'feature_sets'
);

-- ETF 基本信息
SELECT ts_code, name, list_date, m_fee, fund_type, benchmark
FROM etf_basic WHERE ts_code = ANY(ARRAY[/*同上 ETF 列表*/]);

-- ETF → 跟踪指数映射（估值因子的核心桥梁）
SELECT e.ts_code, e.name, e.benchmark, i.indx_name
FROM etf_basic e
LEFT JOIN etf_index i ON e.benchmark LIKE '%' || i.indx_csname || '%'
WHERE e.ts_code = ANY(ARRAY[/*ETF 列表*/]);
```

### P0.2 判定标准

| 检查项 | 通过条件 | 不通过处理 |
|:---|:---|:---|
| etf_daily | ≥22只 ETF，最早 ≤ 2020-01-01 | 缺失 ETF 移除；不足的补同步 |
| index_dailybasic | ≥5个指数，最早 ≤ 2019-01-01 | 补同步 |
| etf_shares | ≥20只 ETF 有数据 | 缺失 ETF 的份额因子设为 NaN |
| stock_moneyflow_hsgt | ≥500 条记录 | 触发增量同步 |
| index_sw_daily | ≥28个行业 | 补同步 |
| market_state_daily | （大概率 0 行） | P1.2 实现分类器 |
| feature_sets | （大概率不存在） | P1.1 建表 |
| etf_basic | ≥25只 ETF | 缺失 ETF 移除 |

---

## 二、P1: 数据 + 因子基础设施（3-5 天）

### P1.1 建表 & DML

**文件**: `docs/sql/migration_v3.4_etf_bottom.sql`（新增）

**内容**:
- `feature_sets` 建表（从 `特征集管理方案.md` L33-46 提取 DDL）
- 4 条 `etf_bottom_*` 特征集预设 INSERT
- 50 条新因子 `factor_definitions` INSERT

### P1.2 市场状态分类器

**文件**: `quant_server/modules/data/services/market_state_classifier.py`（新增 ~200行）

**逻辑**:
```
classify_single_day(trade_date, session) → Dict
  输入: 000300.SH + 000905.SH 的 index_daily
  判定:
    BULL   ← close > MA20 > MA60 AND MA20斜率 > 0
    BEAR   ← close < MA20 < MA60 AND MA20斜率 < 0
    NEUTRAL ← 其他
  辅助指标:
    trend_strength = |MA20斜率| / volatility
    momentum_score = 20日涨跌幅
    breadth_ratio  = 全市场(上涨家数/总数)
    volume_ratio   = today_vol / MA20_vol
    volatility_pct = std(returns,20) × √252
  输出: INSERT INTO market_state_daily
```

**数据来源**：纯从已有数据库计算（`index_daily` + `stock_daily`），**不依赖 Tushare**。

### P1.3 新增 ~50 个 ETF 因子计算器

**文件**: `quant_server/modules/data/factor_calculators.py`（追加 ~600行）

#### A 组：简单窗口计算（25 个，纯 etf_daily 数据源）

每个因子 ~12 行：
```python
@register_factor(name="drawdown_20d", display_name="20日回撤",
    description="(close - max(high,20)) / max(high,20)",
    category="etf_bottom", formula="...",
    data_source="market", update_frequency="daily")
def _calc_drawdown_20d(df, parameters=None):
    roll_max = df.groupby('ts_code')['high'].transform(
        lambda x: x.rolling(20, min_periods=5).max())
    return (df['close'] - roll_max) / roll_max
```

全部A组因子：`drawdown_20d/60d/120d`, `ma_disparity_20/60/120`, `close_to_low_20d`, `atr_ratio_20`, `amplitude_5d`, `max_dd_duration`, `price_position_250d`, `consecutive_down_days`, `momentum_5d`, `rsi_28`, `rsi_low_days`, `volume_shrink_5d/20d`, `vol_decline_corr`, `vol_spike_count`, `volume_dry_up`, `turnover_change_5d`, `amount_change_5d`, `vwap_distance`, `pct_chg_abs_mean_5d`, `high_vol_days_5d`, `volume_ma20_ratio`

#### B 组：跨表因子（15 个，需 extra_data）

扩展 `_calculate_single_factor()` 支持 `parameters['extra_data']` 传递额外表数据。

全部B组因子：`share_change_5d/20d`, `north_flow_5d/20d`, `fund_size_change_20d`, `sector_rank`, `sector_flow_5d`, `hma`, `fund_flow_score`, `net_inflow_5d/20d`, `lg_buy_ratio`, `lg_sell_ratio`, `m_fee`, `fund_age_days`

#### C 组：估值分位因子（8 个，长历史窗口）

全部C组因子：`pe_percentile_5y/1y`, `pb_percentile_5y/1y`, `pe_zscore`, `pb_zscore`, `erp`, `erp_percentile_5y`, `dyr`, `pe_region`, `pb_region`

### P1.4 修改 research_service 支持跨表因子

**文件**: `quant_server/modules/data/services/research_service.py`（修改 ~50行）

在 `_calculate_single_factor()` 中：检查 `spec.parameters.get('requires')` → 加载额外表数据 → 注入 `extra_data`。

### P1.5 批量因子预计算脚本

**文件**: `quant_server/scripts/calc_etf_bottom_factors.py`（新增 ~150行）

```
批量预计算 27 ETF × 65 因子 × ~1500 天
使用现有 FactorResearchService.calculate_factor() 管线
输出: factor_data 超表 ~260万行
```

### P1.6 验证 P1 产出

```sql
SELECT name, category, jsonb_array_length(feature_columns) AS n FROM feature_sets;
SELECT COUNT(DISTINCT ts_code) etfs, COUNT(DISTINCT factor_code) factors, COUNT(*) n_rows
FROM factor_data WHERE ts_code ~ '^[0-9]';
SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM market_state_daily;
```

---

## 三、P2: 离线训练脚本（2-3 天）

**文件**: `quant_server/scripts/train_etf_bottom.py`（新增 ~350行）

```
训练流程:
  数据加载: 从 factor_data 批量加载 65 列 → 合并 etf_daily 未来收益 → 构造标签
  标签: target = AND(未来10日 max_ret≥3%, 未来10日 max_dd≥-5%)
  划分: TimeSeriesSplit → train(2020-2022) / val(2023) / test(2024-2025H1)
  训练: LGBMClassifier(boosting='gbdt', num_leaves=63, max_depth=7,
          lr=0.02, n_estimators=2000, early_stopping=50, scale_pos_weight=4)
  阈值扫描: T∈[0.5,0.95], 选最佳胜率/频率平衡点 (推荐 T=0.70)
  保存: joblib.dump → storage/models/etf_bottom_v1_YYYYMMDD.joblib
```

**依赖**: P1 全部完成

---

## 四、P3: 策略代码（2-3 天）

### P3.1 TradingSignal 加 weight 字段

**文件**: `quant_server/modules/strategy/models.py`（+3行）

```python
weight: float = 1.0  # 仓位权重 [0,1]，默认满仓，向后兼容
```

### P3.2 LightGBMBottomStrategy

**文件**:
- `quant_server/modules/strategy/strategies/etf/__init__.py`（新增 ~10行）
- `quant_server/modules/strategy/strategies/etf/bottom_strategy.py`（新增 ~450行）

```
LightGBMBottomStrategy(BaseStrategy):
  strategy_type = StrategyType.ML
  DEFAULT_PARAMS = {model_path, threshold(0.70), max_single_position(0.20),
                    stop_loss(-0.05), take_profit(0.03), max_hold_days(10),
                    cooling_days(5), etf_pool, feature_list}

  on_init()  → joblib.load(model_path)
  on_bar()   → 缓存 → 预热检查 → SQL查factor_data → 组装特征向量
             → 时序标准化 → predict_proba → 信号过滤 → 仓位映射 → TradingSignal
  _check_exit() → 止损/止盈/时间到期/冷却期
```

### P3.3 策略注册

`StrategyRegistry.auto_discover()` 自动扫描 `strategies/etf/` 目录并注册到 `StrategyType.ML`。

### P3.4 创建策略的 DB 记录

```json
POST /api/strategy
{
  "name": "ETF底部-v1",
  "class_name": "LightGBMBottomStrategy",
  "module_path": "modules.strategy.strategies.etf.bottom_strategy",
  "strategy_type": "ml",
  "parameters": {
    "model_path": "storage/models/etf_bottom_v1_20260718.joblib",
    "threshold": 0.70
  }
}
```

---

## 五、P4: 回测验证（1-2 天）

使用已有 `BacktestEngine`：

```bash
curl -X POST /api/backtest/tasks -d '{
  "strategy_id": "...",
  "config": {
    "start_date": "2020-01-01", "end_date": "2025-06-30",
    "initial_capital": 1000000,
    "symbols": ["510050.SH","510300.SH",...]
  }
}'
```

验证清单：
- [ ] 5 年回测无崩溃、无 NaN/Inf
- [ ] 年化收益 > 0, Sharpe > 0.3
- [ ] 胜率 50-65%
- [ ] `weight` 字段正确传递到 trade 模块
- [ ] 冷却期机制生效
- [ ] 分年分析正常

---

## 六、P5: 前端集成（1 天）

- `FeatureSetSelector.vue` — category 筛选增加 `etf_bottom`
- `StrategyList.vue` — 创建策略时 model_path 参数输入

---

## 七、文件变更总清单

```
新增文件（8 个）
═══════════════════════════════════════════════════════════
docs/sql/migration_v3.4_etf_bottom.sql             建表 + 特征集预设 + 因子定义
quant_server/modules/data/services/                 市场状态分类器
  market_state_classifier.py
quant_server/scripts/calc_etf_bottom_factors.py     批量因子预计算
quant_server/scripts/train_etf_bottom.py             离线训练脚本
quant_server/modules/strategy/strategies/etf/
  __init__.py                                        ETF 策略包
  bottom_strategy.py                                 LightGBMBottomStrategy
quant_server/storage/models/                        模型文件目录

修改文件（4 个）
═══════════════════════════════════════════════════════════
quant_server/modules/data/factor_calculators.py    +~600行，~50个 @register_factor
quant_server/modules/data/services/                +~50行，跨表因子支持
  research_service.py
quant_server/modules/strategy/models.py            +3行，TradingSignal.weight
quant_web/src/components/strategy/                 前端 etf_bottom 支持
  FeatureSetSelector.vue

不受影响的核心文件
═══════════════════════════════════════════════════════════
BaseStrategy / StrategyRegistry / BacktestEngine
DataFeedEngine / EventEngine / DataSyncService
```

---

## 八、里程碑

| 里程碑 | 验收标准 | 预估 |
|:---|:---|:---|
| **M0** | ≥22 ETF 数据完整；缺失表已建 | 0.5天 |
| **M1** | factor_data ≥200万行；feature_sets 4条；market_state_daily ≥1200天 | 3-5天 |
| **M2** | 模型文件存在；AUC≥0.65 | 2-3天 |
| **M3** | 策略可被 Registry 发现/创建/启动 | 2-3天 |
| **M4** | 5年回测通过；Sharpe≥0.3 | 1-2天 |
| **M5** | 前端可见 etf_bottom 特征集 | 1天 |

---

## 九、数据链路关键发现

| 发现 | 影响 | 处理 |
|:---|:---|:---|
| `market_state_daily` 有 DDL 无同步 | 16个市场状态因子中 8 个无法取值 | P1.2 实现分类器 |
| `stock_factor_pro_daily` 是个股表 | ETF 代码不在此表，~25个因子不能从此读取 | 走 `factor_data` 统一路径 |
| `stock_moneyflow` 是个股资金流 | ETF 无法获取 `lg_buy_ratio` 等 | 用 `etf_shares.fund_vol` 代理资金流 |
| `feature_sets` 表未建 | DDL 在 docs 但未执行 | P1.1 执行建表 |
| 因子管线仅通过研究 API 触发 | 无法直接批量调用 | P1.5 脚本直接调用 service |
| `TradingSignal` 无 `weight` 字段 | 仓位权重无法传递到 trade 模块 | P3.1 新增字段 |
