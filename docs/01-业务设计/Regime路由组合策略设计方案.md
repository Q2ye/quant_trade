# 多策略资金分配方案 — 设计方案

> 2026-07-29 | 目标：ETF底部(熊市引擎) + 低吸轮动(牛市引擎) 共享资金池、动态分配

---

## 一、核心认知

### "组合"是虚拟概念

回测时选择 ETF底部 + 低吸轮动 两个策略 → 同一个账户 → 共享 Broker → **自然就是一条净值曲线**。

不需要把两个策略包在一个新类里。系统已经支持：

```
StrategyManager → 多策略并行
Broker → 共享资金池（多策略的 allocated_capital 共享同一账户）
```

**要做的事只有一件：按市场环境动态分配资金。**

---

## 二、架构

```
                       行情数据
                          ↓
            ┌─────────────┴─────────────┐
            │                           │
    ETFBottomStrategy          StockLowHighStrategy
    (现有策略，不改)            (现有策略，不改)
    allocated_capital          allocated_capital
    = 各自独立设置              = 各自独立设置
            │                           │
            └─────────────┬─────────────┘
                          ↓
                    信号汇总（T 日）
                          ↓
                 CapitalAllocator（分配器）
                 ├─ _get_regime()         → BEAR/RANGE/BULL
                 ├─ _get_volatility()     → σ 滚动缓冲区更新
                 ├─ get_allocation()      → 各策略当前权重
                 └─ sig.weight × w_i      → 缩放信号权重
                          ↓
                     Broker.submit_order()
                     （T 日挂单，T+1 撮合）
                          ↓
                     一条净值曲线
```

### 与旧方案的本质区别

| | 旧方案（RegimeCompositeStrategy） | 新方案（CapitalAllocator） |
|:---|:---|:---|
| 实现方式 | 新建策略类，内部包两个引擎 | 两个独立策略 + 一个分配配置 |
| 策略代码 | ~200 行新类 | **0 行**（纯配置） |
| 策略维护 | 组合策略跟踪底层升级 | 各自独立升级 |
| 策略各自回测 | 不能（耦合在一个类里） | 可以（独立验证单策略质量） |
| 组合回测 | 作为"一个策略"跑 | 选两个策略跑同一个 Broker |

---

## 三、资金分配机制

### 3.1 战略层：Regime 基准权重

以 2 策略为例，与 N 策略（§7.1）是同一套逻辑：

```python
# 每个策略定义自己的 Regime 亲和度（可写在策略类或 CentralAllocator 配置中）
REGIME_BASE_ALLOCATION = {
    # regime → {strategy_id: weight}
    0: {"etf_bottom": 0.8, "stock_low_high": 0.2},   # BEAR:  防御为主
    1: {"etf_bottom": 0.5, "stock_low_high": 0.5},   # RANGE: 均衡
    2: {"etf_bottom": 0.2, "stock_low_high": 0.8},   # BULL:  进攻为主
}
```

### 3.2 战术层：风险平价微调（可选，默认关闭）

纯 Regime 基准的问题是：牛市固定 80% 给低吸轮动，但如果低吸策略实际持仓波动率突然飙升，风险暴露会失控。

风险平价按逆波动率分配：

```
w_etf   = (1 / σ_etf)   / (1/σ_etf + 1/σ_stock)
w_stock = (1 / σ_stock) / (1/σ_etf + 1/σ_stock)
```

**波动率数据源**（优先级从高到低）：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| P1 | bar_dict 实时计算 | ETF 池等权日收益 / 全市场等权日收益 → 滚动 60d std → 年化。零外部依赖，回测实盘一致 |
| P2 | `factor_data` 表 `VOLATILITY_3M` | 预计算因子，适合不想维护滚动缓冲区的场景 |
| P3 | 策略自身日度绩效 | `strategy_daily_performance` 表，仅实盘可用，回测期间尚未写入 |

**P1 的实现**：CapitalAllocator 在每个交易日维护两个固定长度的 `deque`（maxlen=60），从 bar_dict 计算等权日收益后追加，取 std × √252。

### 3.3 双层混合

```python
def get_allocation(regime: int, volatilities: dict, strength: float = 0.3) -> dict:
    """
    Regime 战略方向 + 风险平价战术微调 → 最终资金分配（N 策略通用）

    参数:
        regime:        0=BEAR / 1=RANGE / 2=BULL
        volatilities:  {strategy_id: 年化波动率}，活跃策略集合（weight > 0）
        strength:      风险平价混合强度，0=纯 Regime，1=纯 RP
    """
    base = REGIME_BASE_ALLOCATION[regime]  # {sid: base_weight}

    # ② 风险平价: w_i ∝ 1/σ_i
    vols = {sid: max(0.01, min(2.0, volatilities.get(sid, 0.2)))
            for sid in base}               # 钳制 [1%, 200%]
    inv_sum = sum(1/v for v in vols.values())
    rp = {sid: (1/vols[sid]) / inv_sum for sid in base} if inv_sum > 0 else base

    # ③ 混合
    blended = {sid: base[sid] * (1 - strength) + rp[sid] * strength
               for sid in base}

    # ④ 归一化 + 上下界 [5%, 95%]
    total = sum(blended.values())
    clamped = {sid: max(0.05, min(0.95, v / total))
               for sid, v in blended.items()}

    return clamped
```

**strength = 0 时完全退化为纯 Regime 固定比例，等价于旧方案。向后兼容。**

**为什么是双层而不是纯风险平价：**
- 纯 Regime：固定比例不响应波动率变化 → 牛市高波动时低吸侧敞口过大
- 纯 RP：波动率信号在 V 形反转时滞后 → 可能错过抄底窗口，且丢失了"熊市防守、牛市进攻"的 alpha
- 双层：Regime 定战略方向，RP 在 ±15% 范围内做战术调整，互为补充

**rp_blend_strength = 0 时完全退化为固定比例，等价于旧方案。向后兼容。**

### 3.4 核心参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `REGIME_BASE_ALLOCATION` | `{0: {"etf_bottom": 0.8, "stock_low_high": 0.2}, 1: {...}, 2: {...}}` | Regime → 策略 → 基准权重 |
| `risk_parity_enabled` | False | 是否启用风险平价微调 |
| `vol_lookback` | 60 | 波动率回溯窗口（交易日） |
| `vol_floor` | 0.01 | 年化波动率下限，防止 `1/σ → ∞` |
| `vol_cap` | 2.0 | 年化波动率上限，防止权重归零 |
| `rp_blend_strength` | 0.3 | RP 混合强度：0=纯 Regime，1=纯 RP |
| `rp_rebalance_freq` | "monthly" | RP 部分重算频率（daily/weekly/monthly） |

**Rebalance 触发规则**：
- **Regime 变化**：立即触发，基准权重即时切换
- **Regime 不变**：按 `rp_rebalance_freq` 周期更新 RP 权重
- 波动率缓冲区每日更新，无论是否触发 rebalance

---

## 四、回测流程

### 4.1 两种回测方式

**方式 A：组合回测（一条净值曲线）**

在回测界面勾选 ETF底部 + 低吸轮动 → 同一个账户 → BacktestEngine 同时跑两个策略：

```
Day T:
  1. Broker.match_orders(T, bar_dict)
     ↑ 撮合 T-1 日挂单（以 T 日开盘价成交）

  2. CapitalAllocator.rebalance(T)              ← ★ 分配器先跑
     ├─ _update_volatility(bar_dict)             ← 每日更新 σ 滚动缓冲区
     ├─ regime = _get_regime(bar_dict)          ← 判定当前市场状态
     │   └─ Regime 变化 → 立即触发 rebalance
     └─ alloc = get_allocation(regime, vols)    ← 得到 {sid: weight}
        # 权重在下次 rebalance 前不变（Regime 不变时按 rp_rebalance_freq）

  3. StrategyManager.handle_bar_batch(T, bars)
     ├─ for each active strategy:               ← 只跑 is_running=True 的策略
     │    for bar in bars:
     │      strategy.on_bar(bar)                → 产生信号
     │    strategy.on_bar_batch_end(T)          → 批次结束信号
     │    for sig in signals:
     │      sig.weight *= alloc[strategy_id]    ← 分配器权重缩放
     └─ return all_signals

  4. for sig in all_signals:
       Broker.submit_order(sig)                 ← 共享资金池下单
       # 资金竞争：多策略信号共享 Broker.cash

  5. Broker.mark_to_market(T, bar_dict)         ← 盯市
```

**方式 B：独立回测（各自验证）**

可以单独跑 ETF 底部或低吸轮动的回测，验证单个策略质量。独立回测和组合回测互不干扰。

### 4.2 波动率计算（回测）

回测期间不使用 `strategy_daily_performance` 表（回测结束后才写入）。CapitalAllocator 从 bar_dict 实时计算：

```
每日收市后:
  etf_ret  = mean(ETF 池成分股今日 close / 昨日 close - 1)
  stock_ret = mean(全市场 00/60 开头股票今日 close / 昨日 close - 1)

  _etf_returns.append(etf_ret)     ← deque(maxlen=60)
  _stock_returns.append(stock_ret) ← deque(maxlen=60)

  σ_etf   = std(_etf_returns)   × √252  (len >= 20 时有效，否则用默认值)
  σ_stock = std(_stock_returns) × √252
```

**无冷启动问题**：第一天有 bar 就能积累收益率数据。前 20 天缓冲区不满时，波动率用已有数据计算；< 5 天时直接用 50/50 默认。

---

## 五、实盘流程

与回测完全相同的逻辑，只是 CapitalAllocator 运行在实盘 StrategyManager 之上：

```
每个交易日收盘后:
  1. DataFeedEngine 完成当日数据同步 → 发布 MarketDataReadyEvent
  2. CapitalAllocator 监听到事件:
     a. 从 bar_dict 计算当日 ETF/股票等权收益率
     b. 追加到滚动缓冲区
     c. 计算年化波动率
     d. 判定 Regime
     e. get_allocation() → 得到最新权重
     f. 更新两个策略的 allocated_capital 或信号权重乘数
  3. 策略在次日开盘前获得新的资金分配
```

**分配生效方式**（二选一）：

| 方式 | 机制 | 适用场景 |
|------|------|---------|
| A. 信号权重缩放 | `sig.weight *= alloc_ratio` | 不改策略的 `allocated_capital`，灵活 |
| B. 调整 allocated_capital | `strategy.update_capital(total × alloc_ratio)` | 更彻底，强制风控边界 |

**推荐方式 A**（信号权重缩放），因为：
- 不触及 StrategyManager 的状态变更
- 回测和实盘代码路径一致
- 每个策略仍可独立设置 `allocated_capital` 作为硬上限

---

## 六、与现有系统的关系

```
现有系统（不改）:
  StrategyManager → 多策略并行 + pause/resume
  Broker → 共享资金池 + 同标的自动合并持仓
  EventEngine → 发布/订阅
  各策略文件 → 独立维护、独立回测

新增:
  CapitalAllocator（一个配置 + 一个 rebalance 循环）
    - 读 Regime 信号（market_regime 因子 或 CSI500 MA）
    - 算波动率（bar_dict 实时算 或 factor_data 表）
    - 输出分配权重 → pause 休眠策略 / resume 活跃策略
    - 活跃策略的信号权重 × alloc_ratio → Broker
```

2 个策略和 N 个策略是同一套逻辑。加策略 = 配置表加一行。详见 §七。

---

## 七、多策略调度与冲突处理

### 7.1 N 个策略 vs 2 个策略

分配逻辑完全一样：Regime 查表 → 风险平价微调 → 归一化。唯一的变化是矩阵从 2 列变成 N 列：

```
               BEAR    RANGE    BULL
ETF底部         0.8      0.4      0.1       ← 熊市主力，牛市边缘
低吸轮动        0.1      0.3      0.5       ← 牛市主力
行业轮动          —       0.2      0.3       ← 只在非 BEAR 激活
均值回归          —       0.1      0.1       ← 只在 RANGE 激活
                ↓        ↓        ↓
             每列 sum = 1.0
```

`—` = 该 Regime 下权重为 0 → 策略休眠。

加新策略 = 配置表加一行，不改任何代码。

### 7.2 调度：哪个执行、哪个休眠

CapitalAllocator 在每次 rebalance 时，使用 StrategyManager 现有的 `pause()` / `resume()` 控制策略激活状态：

```python
def apply_allocation(allocation: dict, manager: StrategyManager):
    for strategy_id, weight in allocation.items():
        if weight > 0:
            manager.resume(strategy_id)   # 激活 → handle_bar_batch 会推送 bar
        else:
            manager.pause(strategy_id)    # 休眠 → 不收 bar、不产生信号、零 CPU
```

`handle_bar_batch` 的内部逻辑：

```python
# StrategyManager.handle_bar_batch() — 现有逻辑，不改
for strategy_id in self.running_states:
    if not state.is_running:     # ← pause() 设为 False，自动跳过
        continue
    for bar in bars:
        strategy.on_bar(bar)     # ← 只有活跃策略收到 bar
```

活跃策略按**注册顺序**依次处理同一天的 bar，顺序不保证优先级——每个策略独立决策，信号独立产生。

### 7.3 同一标的被多个策略选中

Broker 按 `ts_code` 管理持仓（`self.positions = {ts_code: BrokerPosition}`），不区分哪个策略创建的。实际效果：

**场景 A：同方向（都买 / 都卖）**

```
策略 A: buy 510050, quantity=1000
策略 B: buy 510050, quantity=500
          ↓ Broker._update_position()
已有持仓 → 加权平均更新成本价，quantity = 1500
```

**自动合并，不需要 CapitalAllocator 干预。** 两笔买入合并为一个持仓，成本价按数量加权。卖出时同理，先进先出。

**场景 B：反向（一个买一个卖）**

```
策略 A: buy  510050, quantity=1000   ← 先执行
策略 B: sell 510050, quantity=300    ← 后执行（需有可用持仓）
```

如果策略 B 卖的是旧持仓 → 正常执行。  
如果策略 B 卖的是策略 A 刚买入的 → T+1 锁定，当日不可卖，订单被拒。

但这里有一个**隐性浪费**：如果两策略方向相反、净效果接近零，等于白付双倍手续费。

**处理方式**：

| 方案 | 做法 | 适用 |
|------|------|------|
| **推荐**：Universe 分离 | ETF 底部交易 510/159 开头 ETF，低吸轮动交易 00/60 开头个股。天然不重叠 | 当前 2 策略即可满足 |
| 备选：CapitalAllocator 预检 | 所有信号汇总后，检测同一 ts_code 的多空冲突，按 higher-weight 策略的方向执行，抑制另一侧 | N 策略且 Universe 有重叠时启用 |

**Universe 分离是首选**——简单、零开销、不会出 bug。如果未来某个策略确实需要和其他策略共享标的（如行业轮动和 ETF 底部都买 ETF），再启用 CapitalAllocator 预检。

### 7.4 混合策略（风险平价 N 资产扩展）

N 个策略的风险平价与 2 个完全相同：

```
w_i = (1/σ_i) / Σ(1/σ_j)    j ∈ 当前 Regime 的活跃策略（weight > 0）
```

| 活跃策略数 | 推荐方法 | 精度 |
|-----------|---------|------|
| N ≤ 3 | 逆波动率加权 `w ∝ 1/σ` | 足够 |
| N ≥ 4 | 协方差矩阵风险平价（用 `optimization_tools.py` 已有实现） | 更准确，考虑持仓相关性 |

**注意**：即使策略 Universe 不重叠，其净值仍可能因同涨同跌而相关。N ≥ 4 时协方差矩阵比简单逆波动率更可靠。

---

## 八、边界场景

| 场景 | 处理 |
|------|------|
| 冷启动（缓冲区 < 5 天） | 默认均分，不启用风险平价 |
| 波动率异常低（σ < 1%） | `vol_floor = 0.01`，防止 `1/σ → ∞` |
| 波动率异常高（σ > 200%） | `vol_cap = 2.0`，防止权重归零 |
| 某一侧长期无信号 | 不影响——波动率从 bar 算，与信号无关 |
| 两引擎同时高波（双杀） | RP 对此无效，依赖 Regime 战略层 + 全局止损 |
| risk_parity_enabled = False | 完全退化为固定比例，等价于旧方案 |
| Regime 因子缺失 | 默认 regime = 1 (RANGE, 均衡) |
| rp_rebalance_freq = "monthly" | 月度重算，抑制信号权重噪音 |
| **Regime 切换后旧仓位** | 见 §8.1 |
| **策略 resume 预热** | 见 §8.2 |

### 8.1 Regime 切换后的持仓再平衡（关键）

Regime 从 BEAR 切换到 BULL 后，ETF 分配从 80% → 20%。**已有 ETF 持仓怎么处理？**

```
被动再平衡（推荐，默认）：
  - CapitalAllocator 只影响新信号，不强制平仓
  - 权重降低后，ETF 策略的新买入信号 weight 变小 → 难以加仓
  - 现有 ETF 持仓由策略自身的退出逻辑管理（止损/止盈/最大持有天数）
  - 仓位自然衰减到新目标比例，通常 10-20 个交易日完成

主动再平衡（可选，风险平价启用时）：
  - 如果当前 ETF 仓位市值 / 总资产 > alloc_etf × 1.5（偏离 > 50%）
  - CapitalAllocator 发出降仓信号 → 策略优先平掉部分持仓
  - 代价：交易成本 + 可能打断策略自身的持仓逻辑
```

**推荐被动再平衡**：
1. 策略的进出场逻辑是 alpha 来源，不应被分配器打断
2. Regime 切换频率低（年线方向几个月才变一次），10-20 天延迟可接受
3. 简单——CapitalAllocator 不需要理解每个策略的持仓细节

### 8.2 策略 resume 后的数据预热

策略被 `pause()` 后，`_data_cache` 等内部状态停止更新。`resume()` 后直接跑 bar 会导致缓存缺失，技术指标计算异常。

CapitalAllocator 处理方式：resume 后回填暂停期间的 bar（**仅填充缓存，不触发信号**）：

```python
# 回测：直接 replay 暂停期间的 bar
for bar in warmup_bars:
    strategy.on_bar(bar, warmup=True)

# 实盘：从 DB 加载历史 bar 填充
```

与回测引擎现有的 `_preheat_strategy()` 逻辑一致，可直接复用。

---

## 九、实施步骤

| 步骤 | 内容 | 说明 |
|------|------|------|
| 1 | 回测界面支持**多策略选择** | 如果尚未支持 |
| 2 | 实现 CapitalAllocator 配置 + 分配逻辑 | ~80 行：Regime 查表 + 波动率缓冲区 + 混合公式 |
| 3 | P0：固定比例回测验证（rp_blend_strength=0） | 等价于旧方案预期的效果 |
| 4 | P1：接入 P1 波动率（bar_dict 实时计算） | 风险平价生效 |
| 5 | 与独立跑结果对比 | 验证净值分配的合理性 |
| 6 | 参数调优 | rp_blend_strength / vol_lookback / rebalance_freq |
| 7 | 实盘启动 | 两个策略实例 + CapitalAllocator |

---

## 十、实盘组合方案

> **前提**：实盘为半自动模式——用户手动触发策略 → 策略产生信号存入 DB（status=pending_manual）→ 用户在 SignalConfirm 页面手动确认每笔信号 → 券商端下单。不存在自动 Broker、不存在 Sizer。

### 10.1 核心架构

```
                    市场数据 / 用户手动触发
                          ↓
         ┌────────────────┴────────────────┐
         │                                 │
  ETFBottomStrategy              StockLowHighStrategy
  (allocated_capital = 可变)      (allocated_capital = 可变)
         │                                 │
         ├─ trigger_strategy()             ├─ trigger_strategy()
         │   → on_bar() → 信号列表          │   → on_bar_batch_end() → 信号列表
         │                                 │
         └────────────────┬────────────────┘
                          ↓
              CompositeSignalCoordinator（信号协调器）
              ├─ 信号合并去重
              ├─ 冲突消解（同标的、反向信号）
              ├─ 风控拦截（仓位上限、单标的集中度）
              ├─ Regime 权重标注（每笔信号标注建议权重）
              └─ 排序（风控优先 > Regime 权重 > 置信度）
                          ↓
                  存入 DB: signals 表
                  (status = pending_manual)
                          ↓
              前端 SignalConfirm.vue
              用户逐笔确认：成交价、数量、时间
                          ↓
                  券商端实际下单
                          ↓
              回系统确认成交 → trades 表
                          ↓
              CompositeAccountTracker
              计算账户级净值曲线 + 策略级归因
```

### 10.2 多策略信号处理

#### 10.2.1 触发方式

| 方式 | 操作 | 适用场景 |
|------|------|---------|
| 独立触发 | 用户分别对策略 A 和 B 调用 `trigger_strategy()` | 日常使用，灵活 |
| 组合触发 | 用户一次触发整个组合 → 依次执行各策略的 `trigger_strategy()`（跳过内部 publish）→ Coordinator 汇总处理后统一写入 DB | 一键操作，含协调逻辑 |

**组合触发的关键实现细节**：

当前 `trigger_strategy()` 内部直接调用 `_publish_signals()` 将信号写入 DB。组合触发需要抑制这个行为——先收集所有策略的原始信号，经 Coordinator 处理后再统一写入。

```python
async def trigger_composite(group_id, trade_date):
    group = await load_composite_group(group_id)
    all_raw_signals = []
    
    for cfg in group.strategy_ids:
        strategy_id = cfg["strategy_id"]
        if await was_triggered_today(strategy_id, trade_date):
            continue  # 今天已触发过，跳过
        # 调用内部方法：执行 on_bar 但不 publish
        raw = await strategy_manager._run_strategy_signals(strategy_id, trade_date)
        all_raw_signals.extend(raw)
    
    # 协调处理
    coordinator = CompositeSignalCoordinator(group)
    merged, conflicts = coordinator.process(all_raw_signals)
    
    # 统一写入 DB
    await strategy_manager._publish_signals_batch(merged)
    
    return {"signals": merged, "conflicts": conflicts, ...}
```

**"今天已触发过"的判断**：`signals` 表中查 `strategy_id + trade_date + signal_status = 'pending_manual'`，存在则说明今日已触发，组合触发时不再重复执行该策略。避免重复产生信号。

组合触发 API：

```
POST /strategy/composite/trigger
{
  "composite_group_id": "xxx",
  "trade_date": "2026-07-31",
  "symbols": null
}
→ {
  "signals": [...],
  "conflicts": [...],
  "regime": 1,
  "allocation": {...},
  "skipped_strategies": ["sid_already_triggered"]
}
```

#### 10.2.2 信号合并规则

**注意**：当前 2 策略组合（ETF 底部 vs 低吸轮动）的 Universe 天然不重叠（510/159 ETF vs 00/60 主板股票，见 §7.3），信号合并规则仅在以下场景触发：
- N 策略扩展后 Universe 有重叠（如行业轮动 + ETF 底部都买 ETF）
- 两个策略对同一标的产生同向或反向信号

在信号到达 DB 前，`CompositeSignalCoordinator` 按以下规则处理：

```
规则 1 — 同向合并（买入+买入 / 卖出+卖出）:
  ts_code 相同 + direction 相同
  → 合并为一条信号：
    quantity = qty_A + qty_B                 ← 简单求和（allocated_capital 已体现分配）
    confidence = max(各策略 confidence)
    reason = "[ETF底部] proba=0.62; [行业轮动] score=78"
    source_strategies = ["etf_bottom", "industry_rotation"]

规则 2 — 反向冲突（买入 vs 卖出）:
  ts_code 相同 + direction 相反
  → 保留 Regime 权重更高的策略的方向
  → 被抑制的信号进入 conflicts 列表（用户可查看但不执行）

规则 3 — 平仓优先（止盈/止损 vs 买入）:
  同一标的，exit 信号（stop_loss/take_profit）与 entry 信号共存
  → exit 信号优先，entry 信号被抑制

规则 4 — 不同标的（无冲突）:
  各自保留，不做修改
```

#### 10.2.3 信号排序

用户看到的信号列表按以下优先级排列：

```
1. 风控信号（stop_loss/take_profit）— 最优先
2. 退出信号（exit）
3. 高 Regime 权重策略的买入信号
4. 低 Regime 权重策略的买入信号
5. 同优先级内按置信度降序
```

每条信号标注其来源策略及该策略当前的 Regime 权重，供用户参考是否执行——但不强制（用户始终有最终决定权）。

#### 10.2.4 风控拦截

在信号存入 DB 前，`CompositeSignalCoordinator` 执行账户级风控：

```python
def intercept(signals, account, positions) -> List[Signal]:
    """账户级风控拦截"""
    for sig in signals:
        # ① 仓位上限：单标的市值 / 总资产 ≤ 20%
        if (existing_position_mv(sig.ts_code) + sig.estimated_amount) / account.total_assets > 0.20:
            sig.risk_flag = "exceeds_single_position_limit"
            continue
        
        # ② 总敞口：所有持仓市值 / 总资产 ≤ 95%
        if (total_market_value + sig.estimated_amount) / account.total_assets > 0.95:
            sig.risk_flag = "exceeds_total_exposure"
            continue
        
        # ③ 行业集中度（如有行业分类）：同行业持仓 ≤ 40%
        if sector_concentration(sig.ts_code, positions) + sig.estimated_amount_ratio > 0.40:
            sig.risk_flag = "exceeds_sector_concentration"
            continue
    
    return valid_signals
```

### 10.3 资金动态分配

#### 10.3.1 分配机制

核心机制：**调整各策略的 `allocated_capital`**——不是缩放信号 weight，不是 pause/resume。

```
每个 rebalance 周期:
  1. CapitalAllocator 判定 Regime + 计算权重
  2. new_capital[i] = 账户总可用资金 × weight[i]
  3. 调用 ExecutionService.update_allocated_capital(strategy_id, new_amount)
  4. 策略下次触发时，allocated_capital 已更新
```

**为什么是调整 allocated_capital 而不是缩放 signal.weight？**

用户手动确认信号时看到的是 `quantity`（建议数量），不是 `weight`。`quantity` 由策略根据自身 `allocated_capital` 计算。调整 capital 比改 weight 更直接——用户看到的就是正确数量。

#### 10.3.2 分配规则

| 参数 | 值 | 说明 |
|------|-----|------|
| 触发时机 | Regime 变化 → 立即；无变化 → 每周一 | 避免频繁调整 |
| 步长 | ≥ 10,000 元 | 最小调整单位 |
| 下限 | 10,000 元 | 不为 0——即使熊市低吸也要保留最小额度管理已有持仓的止盈止损 |
| 上限 | 总资金 × 80% | 单策略不超过 80%，剩余 20% 作为安全垫 |
| 调整方式 | 渐进式，每次不超过前值的 ±30% | 避免 capital 剧烈跳变导致策略仓位震荡 |

#### 10.3.3 分配落地

```python
async def apply_allocation(allocation: dict, account_total: float):
    """将分配权重落地到各策略的 allocated_capital"""
    targets = {}
    for strategy_id, weight in allocation.items():
        target = account_total * weight
        current = await get_strategy_allocated_capital(strategy_id)
        
        # 渐进式调整：单次不超过 ±30%
        target = max(current * 0.7, min(current * 1.3, target))
        # 下限钳制
        target = max(10000, min(account_total * 0.8, target))
        # 取下整到万元
        target = round(target / 10000) * 10000
        targets[strategy_id] = target
    
    # 硬约束：总和不得超过账户总资金
    total_allocated = sum(targets.values())
    if total_allocated > account_total:
        # 等比例缩减
        scale = account_total / total_allocated
        targets = {sid: round(v * scale / 10000) * 10000 for sid, v in targets.items()}
    
    for strategy_id, target in targets.items():
        await execution_service.update_allocated_capital(strategy_id, target)
```

**`update_allocated_capital()` 实现**：

`ExecutionService` 当前没有此方法，需新增。逻辑：更新 `strategies.allocated_capital` 字段 + 更新策略实例的 `StrategyContext.available_capital`。如果策略正在运行，通过 EventEngine 发布 `StrategyCapitalUpdatedEvent` 通知 StrategyManager 更新内存中的 context。

### 10.4 账户净值曲线

#### 10.4.1 数据模型

```
composite_account_snapshots（账户级快照——每日一条）
  trade_date:    DATE
  total_nav:     NUMERIC(16,4)      ← 账户总净值（cash + 所有持仓市值）
  daily_return:  NUMERIC(10,6)
  cash:          NUMERIC(16,4)
  market_value:  NUMERIC(16,4)
  
  -- 策略级归因
  per_strategy:  JSONB              ← [{
      strategy_id: "...",
      allocated_capital: 800000,
      nav_contribution: 820000,       ← 该策略贡献的净值
      daily_pnl: 5000,
      position_count: 3,
      positions_market_value: 620000
    }, ...]
  
  regime:        INT
  allocation:    JSONB              ← {"sid1": 0.8, "sid2": 0.2}
```

#### 10.4.2 归因拆分

每个策略的 P&L 通过对该策略产生的交易记录 + 当前持仓变动来归因：

```
策略 A 当日盈亏 = 
  sum(当日成交的 trade.pnl)          ← 已实现盈亏
  + sum(当日持仓浮动盈亏变动)          ← 未实现盈亏（收盘价 vs 昨日收盘价）
  - 当日手续费/税费
```

**与回测的一致性**：
- 回测：`Broker.get_equity_curve()` → 每日 snapshot → `BacktestResult.equity_curve`
- 实盘：`CompositeAccountTracker` → 每日 snapshot → 同结构输出
- 输出格式对齐 `BacktestResult.to_dict()`，前端同一套图表组件复用

#### 10.4.3 时间粒度

| 场景 | 粒度 | 说明 |
|------|------|------|
| 日常记录 | 日频 | 每个交易日收盘后生成一条 snapshot |
| 实时展示 | 分钟级 | 持仓市值按最新行情估算（非精确结算） |
| 月度报表 | 月频 | 按月汇总，含各策略贡献 |

### 10.5 数据库变更

```sql
-- 组合分组
CREATE TABLE composite_groups (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    account_id VARCHAR(36) NOT NULL,
    strategy_ids JSONB NOT NULL,              -- [{"strategy_id": "...", "allocator_id": "etf_bottom"}]
    allocator_config JSONB NOT NULL,
    current_regime INT DEFAULT 1,
    current_allocation JSONB,
    last_rebalance_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 策略表加反向引用（便于从策略查到所属组合）
ALTER TABLE strategies ADD COLUMN composite_group_id VARCHAR(36);
CREATE INDEX idx_strategies_composite_group ON strategies(composite_group_id);

-- 账户快照
CREATE TABLE composite_account_snapshots (
    id VARCHAR(36) PRIMARY KEY,
    composite_group_id VARCHAR(36) REFERENCES composite_groups(id),
    trade_date DATE NOT NULL,
    total_nav NUMERIC(16,4),
    daily_return NUMERIC(10,6),
    cash NUMERIC(16,4),
    market_value NUMERIC(16,4),
    per_strategy JSONB,                       -- 策略级归因
    regime INT,
    allocation JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(composite_group_id, trade_date)
);
```

### 10.6 边界场景

| 场景 | 处理 |
|------|------|
| 策略 A 今日已触发过、策略 B 未触发 | 组合触发时跳过已触发的策略，仅触发策略 B |
| 同一标的被两个策略选中（同向） | 合并信号，quantity 按 Regime 权重加权（§10.2.2 规则1） |
| 同一标的被两个策略选中（反向） | 保留高权重策略方向，抑制低权重方向（§10.2.2 规则2） |
| 某个策略 `allocated_capital` 降到下限 | 不再降，保留 1 万元管理已有持仓 |
| Regime 切换后旧仓位如何处理 | 被动再平衡：`allocated_capital` 降低 → 策略难以加仓，已有仓位由策略自身退出逻辑管理（同回测 §8.1） |
| 账户数据未到齐时触发组合 | 等待或跳过——依赖数据就绪状态 |
| 策略被手动停止（不在组合中操作） | 组合触发时检测策略状态，stopped/error 的策略跳过，权重重新归一化 |
| 组合中增加/移除策略 | 调用 `add_strategy_to_composite()` / `remove_strategy_from_composite()` → 重新归一化权重 |
| `allocated_capital` 被降到低于当前已部署仓位 | 不强制平仓——策略不能加仓，但已有仓位由策略自身止盈止损管理。属于被动再平衡（同 §8.1） |
| `allocated_capital` 总和超过账户总资金 | `apply_allocation()` 中硬约束 + 等比例缩减（§10.3.3） |

### 10.7 实施步骤

| 步骤 | 内容 | 依赖 |
|------|------|------|
| 1 | `CompositeSignalCoordinator` — 信号合并/去重/冲突消解/风控拦截 | 无 |
| 2 | `POST /strategy/composite/trigger` — 组合触发 API + 信号协调 | 1 |
| 3 | `ExecutionService.update_allocated_capital()` — 运行时调整 capital | 无 |
| 4 | `CapitalAllocator` 集成实盘（Regime 判定 + 计算权重 + 渐进式落地） | P0 CapitalAllocator, 3 |
| 5 | `CompositeAccountTracker` — 每日快照 + 策略归因 | 无 |
| 6 | `composite_groups` + `composite_account_snapshots` 表 | 无 |
| 7 | 前端：组合触发按钮 + 信号确认页显示 Regime 权重标注 | 2, 4 |
| 8 | 前端：账户净值曲线页（复用回测图表组件） | 5 |
| 9 | 模拟盘跑 1 个月验收 | 全部 |

---

## 十一、与独立跑的对比

| 维度 | 独立跑（两个策略各自） | 组合（共享资金池 + 分配器） |
|:---|:---|:---|
| 回测 | 各自跑 + 手工合成净值 | 勾选两个策略 → 一条净值曲线 |
| 实盘 | 两个策略实例，独立账户 | 两个策略实例，共享账户 |
| 资金利用率 | 各有闲置（熊市低吸停买，资金闲置） | 资金向活跃侧流动 |
| 策略代码 | 不改 | **不改** |
| 分配逻辑 | 无 | CapitalAllocator（~80 行） |
| 策略各自升级 | 无影响 | **无影响**（完全解耦） |
| 策略独立回测 | ✅ | ✅（仍可单独跑） |
| Regime 自适应 | 无 | ✅ 熊市 ETF 多，牛市股票多 |
| 波动率自适应 | 无 | ✅ 可选启用 |
