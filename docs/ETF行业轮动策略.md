# 行业轮动策略 V2 — 设计方案

> 版本：v1.0
> 日期：2026-07-02
> 基于：申万一级行业多因子评分 + 行业→ETF 映射
> 策略目标：在 31 个申万行业中识别即将上涨的行业，买入对应 ETF，在趋势见顶前卖出

---

## 一、架构定位

```
modules/strategy/
├── strategies/rotation/
│   ├── __init__.py                     # 导出 IndustryRotationStrategy
│   ├── etf_rotation_strategy.py        # [保留] V1 旧策略，标记 deprecated
│   └── industry_rotation_strategy.py   # [新增] V2 行业轮动策略
│
├── services/
│   ├── industry_scoring_service.py     # [新增] 行业多因子评分服务
│   └── etf_industry_mapper.py          # [新增] 行业→ETF 映射服务
│
└── enums/
    ├── sector_groups.py                # [新增] 板块分组枚举

依赖方向:
  strategy → services → shared/database/repositories/
  策略层        服务层          数据访问层
```

---

## 二、数据流全景

```
┌─────────────────────────────────────────────────────┐
│                   IndustryRotationStrategy            │
│                     on_bar() 驱动                      │
│                                                     │
│  on_bar(bar: BarData)  →  追加 ETF 收盘价到缓存       │
│    │                                                 │
│    │ 每5个交易日触发一次                                │
│    ▼                                                 │
│  _rebalance()                                       │
│    │                                                 │
│    ├─(1)─→ IndustryScoringService.score_all()        │
│    │         │                                        │
│    │         ├→ IndexSwDailyRepository               │
│    │         │  读取31行业日线 + PE/PB + 流通市值       │
│    │         │                                        │
│    │         ├→ 计算 8 个子因子值                      │
│    │         ├→ 横截面 z-score 归一化                  │
│    │         ├→ 加权合成 → 行业综合得分                  │
│    │         └→ 返回排名                               │
│    │                                                 │
│    ├─(2)─→ EtfIndustryMapper.resolve(行业排名)         │
│    │         │                                        │
│    │         ├→ 行业→ETF映射表（静态配置 + 动态筛选）    │
│    │         ├→ 流动性/规模/费率/跟踪误差过滤           │
│    │         └→ 返回 Top N 行业对应的最优 ETF           │
│    │                                                 │
│    ├─(3)─→ 板块分组去重（同一板块 ≤ 2 个）              │
│    │         │                                        │
│    │         ├→ L1 得分差距 > 0.05 → 分高者留          │
│    │         ├→ L2 边际变化 → 要加速的、不要减速的       │
│    │         └→ L3 因子相似度 → 同一故事不重复下注       │
│    │                                                 │
│    ├─(4)─→ 对比当前持仓，生成买卖信号                    │
│    │         │                                        │
│    │         ├→ 排名 ≤ 5  & 未持仓 → ENTRY            │
│    │         ├→ 排名 > 8 & 已持仓 → EXIT              │
│    │         └→ 排名 6-8 & 已持仓 → 持有不动（缓冲）    │
│    │                                                 │
│    └─(5)─→ 返回 TradingSignal[]                      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 三、因子体系 —— 8 个子因子 × 3 大类

### 因子架构

```
行业综合得分 = 0.45 × 趋势动量 + 0.30 × 资金量价 + 0.25 × 估值空间
           = 0.45 × (A1权重0.5 + A2权重0.25 + A3权重0.25)
           + 0.30 × (B1权重0.4 + B2权重0.35 + B3权重0.25)
           + 0.25 × (C1权重0.4 + C2权重0.35 + C3权重0.25)
```

### 3.1 趋势动量（权重 45%）

| 子因子 | 名称 | 计算式 | 数据源 |
|:---|:---|:---|:---|
| A1 | 多窗口加权动量 | `0.15×R20 + 0.25×R60 + 0.35×R120 + 0.25×R250` | `index_sw_daily.close` |
| A2 | 动量加速度 | `R20 − R60` | 同上 |
| A3 | 相对强弱 | `R60_ind / R60_benchmark`（基准=万得全A 881001.WI） | `index_sw_daily.close` + 基准 close |

### 3.2 资金量价（权重 30%）

| 子因子 | 名称 | 计算式 | 数据源 |
|:---|:---|:---|:---|
| B1 | 量比 | `mean(vol, 5d) / mean(vol, 60d)` | `index_sw_daily.vol` |
| B2 | 价量配合度 | `(Σ涨日amount − Σ跌日amount) / Σ全部amount, 20d` | `index_sw_daily.amount + pct_change` |
| B3 | 换手加速度 | `(turnover_5d − turnover_20d) / turnover_20d` | `amount / float_mv` 全在 `index_sw_daily` |

### 3.3 估值空间（权重 25%）

| 子因子 | 名称 | 计算式 | 数据源 |
|:---|:---|:---|:---|
| C1 | PE 历史分位 | `1 − percentile(PE_curr, PE_5yr_array)` | `index_sw_daily.pe` |
| C2 | PB 历史分位 | `1 − percentile(PB_curr, PB_5yr_array)` | `index_sw_daily.pb` |
| C3 | 估值扩张方向 | `(PE_curr − PE_60d_ago) / PE_60d_ago` | `index_sw_daily.pe` |

### 3.4 归一化方法

每个子因子在 31 个行业上做横截面 z-score：

```
z_i = (x_i − mean(x_1...x_31)) / std(x_1...x_31)
score_i = 1 / (1 + exp(−z_i))        # sigmoid 到 (0, 1)
```

---

## 四、行业→ETF 映射规则

### 4.1 映射表设计

31 个申万一级行业 → 代表 ETF，存储在配置文件中（非硬编码到策略代码）：

```python
# 示例片段
INDUSTRY_ETF_MAP = {
    "银行":     {"primary": "512800.SH", "secondary": "515290.SH"},
    "医药生物":  {"primary": "512010.SH", "secondary": "159929.SZ"},
    "电子":     {"primary": "159732.SZ", "secondary": "512480.SH"},
    # ... 31 个行业
}
```

### 4.2 动态筛选规则

每次调仓时，对候选 ETF 做最后的流动性检查：

| 检查项 | 条件 | 失败处理 |
|:---|:---|:---|
| 当日有 bar | `_data_cache[ts_code]` 存在 | 跳过该行业（数据不足） |
| 日均成交额 | 近 20 日 > 1000 万 | 降级到 secondary ETF |
| 基金规模 | `etf_shares.fund_size` > 1 亿 | 降级到 secondary ETF |

### 4.3 ETF 粘性策略

```
if 当前持仓的 ETF 仍在 Top 5 行业内
  and 该 ETF 的流动性没有严重恶化（日均成交 > 500 万）
  and secondary ETF 评分没有显著优于当前（> +50%）:
    → 继续持有原 ETF（不切换）
else:
    → 切换到当前评分更高的 ETF
```

---

## 五、板块去重三层决策

### 5.1 板块分组

```python
SECTOR_GROUPS = {
    "金融": ["银行", "非银金融"],
    "周期": ["有色金属", "煤炭", "钢铁", "石油石化", "基础化工"],
    "制造": ["电力设备", "机械设备", "汽车", "国防军工"],
    "消费": ["食品饮料", "家用电器", "纺织服饰", "商贸零售", "社会服务"],
    "科技": ["电子", "计算机", "通信", "传媒"],
    "医药": ["医药生物", "美容护理"],
    "公用地产": ["公用事业", "交通运输", "建筑装饰", "建筑材料", "环保", "房地产"],
    "农林轻工": ["农林牧渔", "轻工制造"],
    "综合": ["综合"],
}
```

### 5.2 决策树

```
输入: ranked_top_8_industries = [(行业, 得分, 边际变化, 因子向量), ...]
输出: selected_top_5 = [行业, ...]

算法:
1. selected = []
2. sector_counts = {sector: 0 for sector in SECTOR_GROUPS}
3. for (industry, score, score_change, factor_vec) in ranked_top_8:
4.     sector = get_sector(industry)
5.     if sector_counts[sector] < 2:
6.         selected.append(industry)
7.         sector_counts[sector] += 1
8.     else:
9.         # 同一板块已有2个，执行三层决策
10.        worst_in_same_sector = find_worst_in_sector(selected, sector)
11.        if should_replace(worst, candidate):  # L1/L2/L3 判断
12.            selected = replace(selected, worst, candidate)
13.     if len(selected) == 5: break
14. return selected[:5]

should_replace(incumbent, challenger):
    # L1: 得分差 > 0.05 → 不换（保留分高的）
    if abs(incumbent.score - challenger.score) > 0.05:
        return challenger.score > incumbent.score
    # L2: 边际变化
    if challenger.score_change > 0 and incumbent.score_change < 0:
        return True  # 换：要加速的
    if challenger.score_change < 0 and incumbent.score_change > 0:
        return False  # 不换：要减速的
    # L3: 因子相似度
    if cosine_similarity(incumbent.factors, challenger.factors) > 0.9:
        return challenger.score > incumbent.score
    return False  # 默认不换
```

---

## 六、买卖信号生成

### 6.1 入场条件（AND）

| 条件 | 逻辑 | 参数 |
|:---|:---|:---|
| 排名触发 | 行业排名 ≤ 5 | `top_n=5` |
| 趋势确认 | R20 > 0 | 短期方向必须向上 |
| 量能确认 | 量比 B1 ≥ 0.8 | 不能是无量空涨 |
| 非过热 | RSI < 75 | 不在超买区追高 |
| 冷却期 | 卖出后 10 个交易日内不重买 | 防反复触发 |

### 6.2 出场条件（OR）

| 条件 | 逻辑 | 参数 |
|:---|:---|:---|
| 排名掉队 | 排名 > 8 | `buffer_rank=8` |
| 趋势反转 | R20 < 0 AND R60 < R120 | 中短期都弱于长期 |
| 量能枯竭 | 量比 B1 < 0.5 持续 3 天 | 资金已在撤离 |
| 硬止损 | 浮亏 > 8% | 风控底线 |
| 止盈 | 浮盈 > 25% AND RSI14 > 70 | 锁定利润 |

### 6.3 仓位分配

- 持仓数：5 个行业（板块去重后）
- 等权分配：每行业 19%（5% 现金保留）
- 波动率调整：`w_i = (1/σ_i) / Σ(1/σ_j) × 95%`
    - σ_i = 近 60 日年化波动率
    - 单行业上限 25%（防止波动率极低行业过度集中）

### 6.4 调仓频率

- 评分更新：每日
- 调仓执行：每 5 个交易日（参数可调）
- 信号执行：次日开盘价

---

## 七、信号类型与方向

| 场景 | SignalType | SignalDirection |
|:---|:---|:---|
| 新行业进入 Top 5，首次建仓 | `ENTRY` | `LONG` |
| 行业从 6-8 名重新挤进 Top 5 | `ENTRY` | `LONG` |
| 行业跌出排名 > 8 | `EXIT` | `CLOSE_LONG` |
| 硬止损触发 | `STOP_LOSS` | `CLOSE_LONG` |
| 止盈触发 | `TAKE_PROFIT` | `CLOSE_LONG` |
| 冷却期重新允许买入（无动作） | — | — |

---

## 八、与 V1 的关键差异

| 维度 | V1 (etf_rotation) | V2 (industry_rotation) |
|:---|:---|:---|
| 分析对象 | 10 只 ETF 直接排名 | 31 个申万行业 → 映射到 ETF |
| 股票池 | 硬编码，宽基+行业混杂 | 动态映射，31 行业全覆盖 |
| 因子体系 | 单一多窗口动量（3 因子） | 趋势+量价+估值（8 子因子） |
| 归一化 | 无（原始收益率直接加权） | 横截面 z-score + sigmoid |
| 板块去重 | 无（可能全买金融） | 三层决策去重 |
| 缓冲区 | 无（Top N 进出即交易） | 6-8 名缓冲，防边缘反复 |
| 冷却期 | 无 | 卖出后 10 天不重买 |
| 止损止盈 | 无 | 硬止损 -8% / 止盈 +25% |
| ETF 切换 | 调仓即切换 | 粘性策略，只在必要时换 |
