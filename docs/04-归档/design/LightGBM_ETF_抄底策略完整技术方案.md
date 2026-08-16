# LightGBM ETF 抄底策略 — 完整技术方案

> 基于：[[因子研究管线技术文档]]、[[特征集管理方案]]、[[基于LightGBM的ETF抄底策略逻辑文档]]
> 版本 v1.0 | 2026-07-19

---

## 一、方案总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                  LightGBM ETF 抄底策略 — 技术架构                      │
│                                                                      │
│  ① 数据层       ② 因子/特征层       ③ 训练层        ④ 策略层          │
│  ─────────────────────────────────────────────────────────────────── │
│                                                                      │
│  etf_daily      因子研究管线       离线训练脚本     LightGBMBottom     │
│  etf_shares     ┌─────────────┐    ┌───────────┐   Strategy           │
│  stock_money-   │ 特征集管理   │    │ 标签构造   │   ┌─────────────┐   │
│  flow           │ ┌─────────┐ │    │ TimeSeries │   │ on_bar:      │   │
│  index_daily    │ │ETF底部   │ │───→│ Split      │──→│  提取特征     │   │
│  index_daily-   │ │ 特征集   │ │    │ LightGBM   │   │  model.pre-  │   │
│  basic          │ │~80因子  │ │    │ 训练+早停   │   │  dict_proba  │   │
│  market_state   │ │4个子集  │ │    │ 阈值优化    │   │  信号过滤    │   │
│  daily          │ └─────────┘ │    │ 模型持久化  │   │  仓位映射    │   │
│                 └─────────────┘    └───────────┘   └─────────────┘   │
│                                                                      │
│  已有基础设施     需要新建/扩展         离线执行         策略运行时      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、特征选择与因子组合方案

### 2.1 特征集总体设计

基于策略文档的七大特征类别，结合系统已注册的 29 个计算器 + `stock_factor_pro_daily` 表的 200+ 预计算因子，设计 **4 个子特征集**，共约 80 个因子：

```
ETF 底部特征集 (etf_bottom_fishing) 
├── etf_bottom_oversold     超跌与价格偏离     ~22 因子
├── etf_bottom_volume_flow  量价与资金流向     ~24 因子  
├── etf_bottom_valuation    估值与安全边际     ~18 因子
└── etf_bottom_market_regime 市场状态与情绪    ~16 因子
```

### 2.2 子特征集详细定义

#### 2.2.1 超跌与价格偏离（etf_bottom_oversold）— 22 因子

| # | 因子代码 | 名称 | 来源 | 计算方式 | LightGBM 预期方向 |
|:---|:---|:---|:---|:---|:---|
| 1 | `drawdown_20d` | 20日回撤 | 新增 | (close - max(high, 20)) / max(high, 20) | 值越低→越超跌→信号越强 |
| 2 | `drawdown_60d` | 60日回撤 | 新增 | 同上，窗口60 | 同上 |
| 3 | `drawdown_120d` | 120日回撤 | 新增 | 同上，窗口120 | 同上 |
| 4 | `rsi_6` | 6日RSI | stock_factor_pro | pro 表 `rsi_6_bfq` | <30 超卖 |
| 5 | `rsi_14` | 14日RSI | 已有计算器 | `rsi_14` | <30 超卖 |
| 6 | `rsi_28` | 28日RSI | 新增计算器 | 扩展窗口 | <35 超卖 |
| 7 | `rsi_low_days` | RSI<30持续天数 | 新增 | 连续低于30的天数 | 值越高→恐慌越深 |
| 8 | `boll_pct_b` | %B | stock_factor_pro | `boll_pct_b_bfq` | <0.1 下轨下方 |
| 9 | `boll_width` | 布林带宽 | stock_factor_pro | `boll_width_bfq` | 宽→高波动 |
| 10 | `ma_disparity_20` | 20日均线偏离 | 新增 | (close - ma20) / ma20 | 负值越大→超跌 |
| 11 | `ma_disparity_60` | 60日均线偏离 | 新增 | 同上，窗口60 | 负值越大→趋势下行 |
| 12 | `ma_disparity_120` | 120日均线偏离 | 新增 | 同上，窗口120 | 负值越大→长期下行 |
| 13 | `close_to_low_20d` | 收盘相对20日低点 | 新增 | (close - min(low,20)) / close | 接近0→靠近低点 |
| 14 | `std_20d` | 20日波动率 | 已有计算器 | `std_20d` | 高→恐慌 |
| 15 | `atr_14` | ATR(14) | 已有计算器 | `atr_14` | 高→高波动 |
| 16 | `atr_ratio_20` | ATR相对值 | 新增 | atr14 / close | 高→波动相对大 |
| 17 | `amplitude_5d` | 5日平均振幅 | 新增 | mean((h-l)/pre_close, 5) | 高→分歧大 |
| 18 | `max_dd_duration` | 最大回撤持续天数 | 新增 | 从最近高点至今的天数 | 长→趋势衰竭 |
| 19 | `price_position_250d` | 250日价格位置 | 新增 | (close-min(low,250))/(max(high,250)-min(low,250)) | 低→在低位 |
| 20 | `momentum_3d` | 3日动量 | stock_factor_pro | `momentum_3d` | 负→短期急跌 |
| 21 | `momentum_5d` | 5日动量 | 新增 | 5日涨跌幅 | 负→近期下跌 |
| 22 | `consecutive_down_days` | 连续下跌天数 | 新增 | close < pre_close 的连续天数 | 多→情绪恐慌 |

#### 2.2.2 量价与资金流向（etf_bottom_volume_flow）— 24 因子

| # | 因子代码 | 名称 | 来源 | 计算方式 |
|:---|:---|:---|:---|:---|
| 1 | `volume_shrink_5d` | 5日缩量比率 | 新增 | vol / mean(vol, 5) | <0.6→供应衰竭 |
| 2 | `volume_shrink_20d` | 20日缩量比率 | 新增 | vol / mean(vol, 20) |
| 3 | `volume_ratio_5d` | 5日量比 | 已有计算器 | `volume_ratio_5d` |
| 4 | `vol_decline_corr` | 量价下跌相关性 | 新增 | 近20日 vol 与 return 的相关系数 |
| 5 | `vol_spike_count` | 放量下跌次数 | 新增 | 近10日放量(>1.5x)且下跌的天数 |
| 6 | `volume_dry_up` | 缩量止跌信号 | 新增 | 跌5天+最后3天量递减 |
| 7 | `turnover_rate` | 换手率 | stock_factor_pro | `turnover_rate` |
| 8 | `turnover_change_5d` | 换手率变化 | 新增 | turnover / mean(turnover, 5) |
| 9 | `amount_change_5d` | 成交额变化 | 新增 | amount / mean(amount, 5) |
| 10 | `obv_divergence` | OBV背离 | 新增 | close新低但obv不创新低→1 |
| 11 | `share_change_5d` | 5日份额变化率 | etf_shares | (fund_size - lag5) / lag5 | 正→资金流入 |
| 12 | `share_change_20d` | 20日份额变化率 | etf_shares | 同上，窗口20 |
| 13 | `net_inflow_5d` | 5日净流入 | stock_moneyflow | sum(net_mf_amount, 5) / 1e8 | 正→聪明钱 |
| 14 | `net_inflow_20d` | 20日净流入 | stock_moneyflow | sum(net_mf_amount, 20) / 1e8 |
| 15 | `lg_buy_ratio` | 大单买入占比 | stock_moneyflow | buy_lg_amount / amount | 高→机构买入 |
| 16 | `lg_sell_ratio` | 大单卖出占比 | stock_moneyflow | sell_lg_amount / amount | 低→机构惜售 |
| 17 | `north_flow_5d` | 5日北向净流入 | moneyflow_hsgt | sum(north_money, 5) / 1e8 |
| 18 | `north_flow_20d` | 20日北向净流入 | moneyflow_hsgt | sum(north_money, 20) / 1e8 |
| 19 | `volume_ma5_ratio` | 量比MA5 | stock_factor_pro | from pro table |
| 20 | `volume_ma20_ratio` | 量比MA20 | 新增 | vol / ma(vol, 20) |
| 21 | `high_vol_days_5d` | 高波动天数 | 新增 | 近5日 vol > 1.5x mean 的天数 |
| 22 | `vwap_distance` | VWAP偏离 | 新增 | (close - vwap) / vwap |
| 23 | `pct_chg_abs_mean_5d` | 5日绝对涨跌幅均值 | 新增 | mean(abs(pct_chg), 5) |
| 24 | `fund_flow_score` | 资金流综合得分 | 新增 | net_inflow * lg_buy_ratio 合成 |

#### 2.2.3 估值与安全边际（etf_bottom_valuation）— 18 因子

| # | 因子代码 | 名称 | 来源 | 计算方式 |
|:---|:---|:---|:---|:---|
| 1 | `pe_ttm` | 市盈率TTM | index_dailybasic | pe_ttm |
| 2 | `pb` | 市净率 | index_dailybasic | pb |
| 3 | `pe_percentile_5y` | PE 5年分位 | 新增 | pe_ttm 在最近 1260 个交易日中的分位 |
| 4 | `pb_percentile_5y` | PB 5年分位 | 新增 | pb 在最近 1260 个交易日中的分位 |
| 5 | `pe_percentile_1y` | PE 1年分位 | 新增 | pe_ttm 在最近 252 个交易日中的分位 |
| 6 | `pb_percentile_1y` | PB 1年分位 | 新增 | 同上 |
| 7 | `pe_zscore` | PE Z-Score | 因子管线 | factor_data.z_score（如已研究） |
| 8 | `pb_zscore` | PB Z-Score | 因子管线 | factor_data.z_score |
| 9 | `erp` | 股权风险溢价 | 新增 | 1/pe_ttm - 10y_bond_yield |
| 10 | `erp_percentile_5y` | ERP 5年分位 | 新增 | 同上分位计算 |
| 11 | `dyr` | 股息率风险溢价 | 新增 | dv_ratio - 10y_bond_yield |
| 12 | `total_mv_log` | 总市值对数 | index_dailybasic | log(total_mv) |
| 13 | `turnover_rate_idx` | 指数换手率 | index_dailybasic | turnover_rate |
| 14 | `pe_region` | PE区域标记 | 新增 | pe_ttm分位 ∈ [0,0.1,0.3,0.5,0.7,0.9]→0-5 |
| 15 | `pb_region` | PB区域标记 | 新增 | 同上 |
| 16 | `fund_size_change_20d` | ETF规模变化 | etf_shares | fund_vol 20日变化率 |
| 17 | `m_fee` | 管理费率 | etf_basic | 越小越适合底部持有 |
| 18 | `fund_age_days` | ETF上市天数 | etf_basic | 越大流动性越确定 |

#### 2.2.4 市场状态与情绪（etf_bottom_market_regime）— 16 因子

| # | 因子代码 | 名称 | 来源 | 计算方式 |
|:---|:---|:---|:---|:---|
| 1 | `market_regime` | 市场状态 | market_state_daily | BULL=2/NEUTRAL=1/BEAR=0 |
| 2 | `breadth_ratio` | 上涨家数占比 | market_state_daily | 0-1 小数 |
| 3 | `breadth_ma5` | 上涨家数5日均值 | 新增 | mean(breadth_ratio, 5) |
| 4 | `breadth_ma20` | 上涨家数20日均值 | 新增 | mean(breadth_ratio, 20) |
| 5 | `breadth_extreme` | 极端宽度标记 | 新增 | breadth < 0.25 → 极度悲观 |
| 6 | `ma_regime_index` | 指数均线状态 | index_daily | close vs ma20/ma60 → 编码 |
| 7 | `index_ma_disparity` | 指数均线偏离 | 新增 | (close - ma60) / ma60 |
| 8 | `index_drawdown_60d` | 指数60日回撤 | 新增 | 对标 index_daily |
| 9 | `index_volatility` | 指数波动率 | 新增 | std(return, 20) |
| 10 | `index_momentum_20d` | 指数20日动量 | 新增 | 对标 index_daily |
| 11 | `sector_rank` | 行业相对强度 | index_sw_daily | 该 ETF 基准在申万一级中的排名分位 |
| 12 | `sector_flow_5d` | 行业资金流入 | moneyflow | 按行业聚合的 net_mf_amount |
| 13 | `trend_strength` | 趋势强度 | market_state_daily | from classifier |
| 14 | `momentum_score` | 动量评分 | market_state_daily | from classifier |
| 15 | `volatility_pct` | 波动率百分位 | market_state_daily | 市场整体波动水平 |
| 16 | `hma` | 赫尔移动平均方向 | 新增 | HMA 方向判定 |

### 2.3 特征集的因子管线集成方式

每个子特征集对应 `feature_sets` 表的一条记录：

```sql
INSERT INTO feature_sets (name, description, category, feature_columns) VALUES
('etf_bottom_oversold',     'ETF抄底-超跌与价格偏离',     'etf_bottom',
 '["drawdown_20d","drawdown_60d","rsi_6","rsi_14","boll_pct_b",...22项]'),
('etf_bottom_volume_flow',  'ETF抄底-量价与资金流向',     'etf_bottom',
 '["volume_shrink_5d","net_inflow_5d","lg_buy_ratio",...24项]'),
('etf_bottom_valuation',    'ETF抄底-估值与安全边际',     'etf_bottom',
 '["pe_percentile_5y","pb_percentile_5y","erp",...18项]'),
('etf_bottom_market_regime','ETF抄底-市场状态与情绪',     'etf_bottom',
 '["market_regime","breadth_ratio","index_drawdown_60d",...16项]');
```

**因子计算两个来源**：

| 来源 | 实现方式 | 适用因子数 |
|:---|:---|:---|
| **已注册计算器** | 在 `factor_calculators.py` 中 `@register_factor` 注册，走现有计算管线（`research_service.calculate_factor`） | ~15 个 |
| **新增计算器** | 在 `factor_calculators.py` 中新增注册（~40 个 ETF 特有因子），遵循现有的 `FactorSpec(calculator=fn)` 模式 | ~40 个 |
| **stock_factor_pro_daily 表** | 直接从 DB 读取预计算值（已有 200+ 列），省去实时计算 | ~25 个 |

**策略运行时因子获取**：

```python
# LightGBMBottomStrategy._load_factor_data(ts_code, trade_date)
# 两条路径并发：
#   路径A: SELECT * FROM factor_data WHERE ts_code=:c AND trade_date <= :d
#           → 覆盖已研究的因子（含 z_score/percentile）
#   路径B: SELECT * FROM stock_factor_pro_daily WHERE ts_code=:c AND trade_date=:d
#           → 覆盖预计算的技术因子
#   + etf_shares, stock_moneyflow, market_state_daily 等表专项查询
# → 合并为单行特征向量（80维）→ 缺失值用历史均值填充
```

### 2.4 特征预处理

遵循因子管线已有的规范：

- **缺失值**：`stock_factor_pro_daily` 和 `factor_data` 已覆盖大部分因子。新增 ETF 因子首次计算时，缺失值用 `ffill` 填充
- **极端值**：Winsorize (1%/99% 分位数) — 比因子管线的 5%/95% 更保守，因为 ETF 价格变化范围小于个股
- **标准化**：横截面不做标准化（ETF 之间不可比）。时序标准化：每只 ETF 独立做 `StandardScaler`（滚动 252 日窗口的 μ 和 σ）
- **标签**：仅对训练集做 `fit()`，验证集和测试集 `transform()` — 防止前视

---

## 三、标签构造与训练方案

### 3.1 标签定义

```
target = 1 (底部成功) if:
  未来 N=10 个交易日内：
    max_return = max(high_1..high_N) / close_today - 1  ≥ X=3%
    AND
    max_drawdown = min(low_1..low_N) / close_today - 1   ≥ -Y=5%
  否则 target = 0
```

**参数网格**（训练时对比）：

| 参数 | 候选值 |
|:---|:---|
| N (持有期) | 5, 10, 15, 20 |
| X (目标涨幅) | 2%, 3%, 5% |
| Y (最大回撤容忍) | 3%, 5%, 8% |

**推荐初始值**：N=10, X=3%, Y=5%（策略文档建议，兼顾信号频率和胜率）。

### 3.2 数据划分

```
训练集:    2020-01-01 ~ 2022-12-31   (3年，约720个交易日 × 25只ETF ≈ 18,000样本)
验证集:    2023-01-01 ~ 2023-12-31   (1年，用于阈值优化 + 早停)
测试集:    2024-01-01 ~ 2025-06-30   (1.5年，最终评估)
```

**数据来源 ETF**：`DEFAULT_ETF_POOL` 中的 27 只有效 ETF（除去 501018.SH 无数据），覆盖宽基、行业、跨境、债券。

**样本平衡**：预计正样本比例约 15-25%（大部分日子不是"底部"）→ 使用 `scale_pos_weight` 或 `is_unbalance=True`。

### 3.3 训练配置

```python
model = lgb.LGBMClassifier(
    objective='binary',
    metric='auc',
    boosting_type='gbdt',   # 初始用 gbdt；如过拟合严重切 dart
    num_leaves=63,
    max_depth=7,
    learning_rate=0.02,
    n_estimators=2000,
    subsample=0.8,
    colsample_bytree=0.7,
    reg_alpha=0.1,
    reg_lambda=0.5,
    scale_pos_weight=4,     # 根据实际正负比例调整
    random_state=42,
    verbosity=-1,
)

model.fit(
    X_train, y_train,
    eval_set=[(X_valid, y_valid)],
    eval_metric='auc',
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
)
```

**特征重要性筛选**：训练后保留 `feature_importances_ > 0` 的因子（通常 50-60 个），丢弃零贡献因子降低过拟合。

### 3.4 阈值优化

在验证集上扫描概率阈值 T ∈ [0.5, 0.95]，计算：

| T | 信号数 | 胜率 | 平均收益 | 夏普比 |
|:---|:---|:---|:---|:---|
| 0.5 | 450 | 38% | +1.2% | 0.35 |
| 0.6 | 280 | 45% | +1.8% | 0.52 |
| 0.7 | 150 | 53% | +2.4% | 0.68 |
| 0.8 | 65 | 62% | +2.9% | 0.71 |
| 0.85 | 30 | 68% | +3.1% | 0.65 |  ← 信号太少

选择 **T=0.7**（平衡胜率和频率），可根据用户偏好调整为保守（T=0.8）或激进（T=0.55）。

### 3.5 模型持久化

```python
# 训练完成后保存
import joblib
joblib.dump({
    'model': model,
    'feature_names': feature_names,
    'scaler_params': {'mu': mu, 'sigma': sigma},  # 每个ETF的滚动标准化参数
    'threshold': 0.7,
    'metadata': {'train_end': '2022-12-31', 'auc': 0.72, 'features_n': 62},
}, f'storage/models/etf_bottom_v1_{date}.joblib')
```

策略启动时：

```python
# LightGBMBottomStrategy.on_init()
artifact = joblib.load(self.model_path)
self.model = artifact['model']
self.threshold = artifact['threshold']
self.scaler_params = artifact['scaler_params']
```

---

## 四、策略信号生成逻辑

### 4.1 策略类结构

```python
class LightGBMBottomStrategy(BaseStrategy):
    """
    LightGBM ETF 抄底策略。

    策略类型：StrategyType.ML
    数据需求：etf_daily (OHLCV) + etf_shares + stock_moneyflow
             + market_state_daily + index_dailybasic
    预热需求：至少 252 个交易日（用于 PE 分位 + 时序标准化窗口）
    """

    strategy_type = StrategyType.ML

    DEFAULT_PARAMS = {
        "model_path": "",           # 训练好的模型文件路径
        "threshold": 0.70,          # 概率阈值
        "max_single_position": 0.20,  # 单 ETF 最大仓位
        "stop_loss": -0.05,         # 硬止损线
        "take_profit": 0.03,        # 止盈线（持有期 N=10 时）
        "max_hold_days": 10,        # 最大持有天数（时间止损）
        "min_confidence": 0.70,     # 最低置信度
        "etf_pool": None,           # ETF 候选池（None=默认池）
        "cooling_days": 5,          # 出场后冷却天数
    }

    def __init__(self, name, strategy_type, parameters):
        ...
        self.model = None              # LightGBM 模型
        self._feature_cache = {}       # {ts_code: DataFrame} 特征缓存
        self._position_entry = {}      # {ts_code: (entry_date, entry_price)}
        self._cooling = {}             # {ts_code: remaining_days}
```

### 4.2 on_bar 信号生成流程

```
on_bar(bar: BarData) → List[TradingSignal]:

  1. 缓存 BarData → self._data_cache[ts_code].append(bar)

  2. if 缓存天数 < 252: return []  # 预热期（PE分位需要1年数据）

  3. 更新特征:
     _update_features(ts_code, bar.trade_date):
       ├─ 路径A: factor_data 表查询（已研究的因子）
       ├─ 路径B: stock_factor_pro_daily 查询（技术因子）  
       ├─ 专项查询: etf_shares, stock_moneyflow, market_state_daily
       ├─ 新增计算: drawdown_*, ma_disparity_*, volume_shrink_*, etc.
       └─ 时序标准化: (value - mu_252d) / sigma_252d

  4. 特征向量 → 模型预测:
     proba = self.model.predict_proba(feature_vector)[0, 1]
     # proba = P(success) ∈ [0, 1]

  5. 信号过滤:
     if proba < self.threshold: return []
     if ts_code in self._cooling: return []           # 冷却期
     if self._has_position(ts_code): return []         # 已有持仓
     if self._position_count >= self.max_positions: return []

  6. 仓位计算:
     weight = max(0, (proba - threshold) / (1 - threshold)) * max_single_position
     # 例: proba=0.85, T=0.70 → weight = 0.15/0.30 × 20% = 10%

  7. 生成信号:
     signal = TradingSignal(
         ts_code=ts_code,
         signal_type=SignalType.ENTRY,
         direction=SignalDirection.LONG,
         price=bar.close,
         confidence=proba,             # 模型概率作为置信度
         reason=f"底部概率{proba:.1%}, 权重{weight:.0%}",
     )
     signal.weight = weight
     self._position_entry[ts_code] = (bar.trade_date, bar.close)
     return [signal]
```

### 4.3 出场逻辑

```python
def _check_exit(self, ts_code, bar) -> Optional[TradingSignal]:
    entry_date, entry_price = self._position_entry.get(ts_code, (None, None))
    if entry_price is None:
        return None
    pnl = bar.close / entry_price - 1
    hold_days = (bar.trade_date - entry_date).days

    # 规则 0: 硬止损 — 亏损超 5%
    if pnl < self.stop_loss:
        return _make_exit(ts_code, f"硬止损: {pnl:.1%}", SignalType.STOP_LOSS)

    # 规则 1: 时间止损 — 持有超 N 天未触发止盈
    if hold_days >= self.max_hold_days:
        return _make_exit(ts_code, f"时间止损: 持有{hold_days}天", SignalType.EXIT)

    # 规则 2: 止盈 — 达到目标涨幅
    if pnl >= self.take_profit:
        return _make_exit(ts_code, f"止盈: {pnl:.1%}", SignalType.TAKE_PROFIT)

    return None
```

### 4.4 信号示例

**模型输出**：
```
[2024-03-15] 
  512880.SH (证券ETF): proba=0.82 → ENTRY, weight=10%
    Top SHAP features: drawdown_60d=-18%, pe_percentile_5y=0.08, volume_shrink_5d=0.42
  
  512660.SH (军工ETF): proba=0.71 → ENTRY, weight=1%
    (接近阈值，lower weight)
  
  518880.SH (黄金ETF): proba=0.35 → SKIP
    (不是底部)
```

---

## 五、与现有技术架构的对接路径

### 5.1 对接总览

```
现有组件                        新增/改造                       LightGBM 策略
──────────────────────────────────────────────────────────────────
factor_calculators.py   →    新增 ~40 个 ETF 因子计算器
feature_sets 表         →    新增 4 条 etf_bottom_* 预设
factor_data 超表         →    复用：存储计算的因子值
stock_factor_pro_daily   →    复用：读取预计算技术因子
                                                              ↓
research_service.py     →    新增 batch_calculate_features()  训练脚本
                                                              ↓
                                                         joblib 持久化
                                                              ↓
BaseStrategy            →    LightGBMBottomStrategy          策略运行时
strategies/ai/          →    新增 ml/bottom_strategy.py
MLStrategy 骨架          →    参考其 on_bar 模式
DataFeedEngine          →    复用 _preload_history + iter_bars
BacktestEngine          →    复用 BacktestEngine.run()
```

### 5.2 实施阶段

| 阶段 | 工作 | 文件 | 依赖 |
|:---|:---|:---|:---|
| **P1: 数据+因子** | etf_daily 加 IOPV/折溢价列、新增 ~40 因子注册、4 个特征集预设 | `create_table.sql`, `factor_calculators.py`, `feature_sets` DML | 无 |
| **P2: 训练脚本** | 离线 notebook/script：标签构造、特征提取、训练、阈值优化、保存 | `scripts/train_etf_bottom.py` | P1 |
| **P3: 策略代码** | `LightGBMBottomStrategy` 实现：on_bar、特征更新、预测、出场 | `strategies/ai/bottom_strategy.py` | P1+P2 |
| **P4: 回测验证** | 5 年回测、分年分析、参数敏感性、SHAP 分析 | `BacktestEngine` | P3 |
| **P5: 集成前端** | 特征集选择器支持 etf_bottom 分类、策略创建支持模型路径参数 | `FeatureSetSelector.vue`, `StrategyList.vue` | P3 |

### 5.3 关键文件清单

| 类型 | 文件路径 | 操作 |
|:---|:---|:---|
| 因子 | `modules/data/factor_calculators.py` | 新增 ~40 注册 |
| 因子 | `docs/sql/create_table.sql` | etf_daily 加列 |
| 因子 | `docs/sql/migration_v3.4_etf_bottom_factors.sql` | 新增 migration |
| 特征集 | DML SQL | 新增 4 条 INSERT |
| 训练 | `scripts/train_etf_bottom.py` | 新增 |
| 策略 | `modules/strategy/strategies/ai/bottom_strategy.py` | 新增 (~400行) |
| 策略 | `modules/strategy/strategies/ai/__init__.py` | 修改（导出） |
| 配置 | `config.yaml` | 新增 `strategies.bottom_etf` 节 |
| 前端 | `src/api/strategy.ts` | 追加 feature set API |
| 模型 | `storage/models/` | 新增目录 |

### 5.4 与现有策略的互补定位

| 策略 | 风格 | 适用市场 | 换手率 |
|:---|:---|:---|:---|
| `multi_asset_trend_strategy` | 右侧追涨 | 趋势市 | 中(10天) |
| `stock_low_high_strategy` | 等待回调 | 震荡市 | 低 |
| **LightGBM ETF 底部** | 左侧抄底 | 熊市/急跌后 | 极低(持有期10天) |

三者覆盖牛/熊/震荡全周期，形成完整的 ETF 策略组合。

---

## 六、风险与注意事项

| 风险 | 缓解 |
|:---|:---|
| 样本不平衡（正例<20%） | `scale_pos_weight` + AUC 评估（不用准确率） |
| 特征共线性 | LightGBM 对共线性不敏感（树模型）；训练后删 `importance=0` 的因子 |
| 市场风格切换 | PSI 监控 + 季度重训练；特征分布漂移 >0.25 → 触发告警 |
| 过拟合 | TimeSeriesSplit + 早停 + 参数 `reg_alpha/lambda`；AUC 训练/测试差 >0.15 → 简化模型 |
| 流动性不足（小 ETF） | 仅选 `fund_size > 5亿` + `turnover_rate > 0.5%` 的 ETF |
| 策略拥挤 | 多 ETF 分散 + 仓位上限 20% |
| 因子管线串行瓶颈 | 训练时批量预计算全部因子到 `factor_data`，运行时只读不写 |
