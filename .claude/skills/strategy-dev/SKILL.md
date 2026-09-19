---
name: strategy-dev
description: 量化策略开发专项。当涉及策略代码编写、因子接入、回测参数配置、策略信号链路、base_strategy继承、策略版本迭代等关键词时使用。
---

# 策略开发技能

> 架构约束见 `quantsys-architect`。本技能专注策略开发流程。
> 硬性约束与审计规则见 `.claude/rules/audit-strategy.md`（六大审计维度、四大模块、边界全覆盖、交付六步）。
> **上线准入判定见 `docs/06-标准规范/06_策略实盘准入标准.md`**（六道门 G0–G5 + 分层 20 项）。
>
> ⚠️ **本文件事实性表述一律以代码为准**：表名以 `docs/sql/create_table.sql` 为准，策略清单以 CLAUDE.md《实际策略清单》为准。
> **2026-09-15 修正**：此前版本写入了 6 处**不存在**的名称（`technical/` `alpha/` `ai/` 目录、`ma_cross`/`macd`/`factor`/`mean_reversion`/`industry_rotation`/`dl`/`ml` 策略、`daily_quotes`、`financial_data`、`factor_metadata` 表、`DataService` 类、`generate_signals()` 方法），已全部改为真实名称。

## 策略开发 SOP

### 步骤 1：定位策略类型（并**先声明类型**）

**实际目录与策略（代码实证，2026-09-15）**：

| 定位 | 策略 | 文件 |
|:---|:---|:---|
| 主池进攻 | 高波动动量轮动 v7.1 | `rotation/high_vol_momentum_strategy.py` |
| 主池避险 | 跨市场动量避险轮动 | `rotation/cross_market_momentum_strategy.py` |
| 主池防守 | ETF 底部抄底（LightGBM） | `etf/bottom_strategy.py` |
| 卫星·事件 | 恐慌抄底 | `panic/panic_bottom_strategy.py` |
| 卫星·进攻 | 微盘股 + 双指数择时 | `microcap/microcap_strategy.py` |
| 参考/历史 | 低吸轮动 | `reference/stock_low_high_strategy.py` |
| 参考/历史 | 深跌反包 | `reference/deep_drop_rebound_strategy.py` |
| 基类 | BaseStrategy 生命周期 | `base/base_strategy.py` + `base/strategy_context.py` |

⚠️ 旧文档所列 `technical/` `alpha/` `ai/` 目录与上述 7 个参考策略文件**代码中均不存在**，勿再引用。

⚠️ **新策略必须先声明类型**（**进攻 / 防守 / 卫星赔率**）再回测 —— 准入标准 §4.3 的定位线按类型分档，**事后挑线不被接受**。

### 步骤 2：确认数据依赖

| 数据 | 真实表 | 获取方式 |
|:---|:---|:---|
| 行情（日线） | `stock_daily` / `etf_daily` / `index_daily` | ⚠️ **无 `daily_quotes` 表** —— 那是 `modules/data/constants.py` 的 `DataType` 枚举码 |
| 因子数值 | `factor_data` | `FactorResearchService.get_factor_data()` 或 `FactorDataRepository.get_factor_data()`（⚠️ **无 `DataService` 类**） |
| 因子定义 | `factor_definitions` | ⚠️ **无 `factor_metadata` 表**；新增因子必须在此注册 |
| 财务 | `financial_income` / `financial_balance` / `financial_cashflow` | ⚠️ **无 `financial_data` 表** |

⚠️ **PIT 红线**：财务数据必须按 `f_ann_date`（公告日）对齐，**禁止按报告期 `end_date` + 日历日 ffill**（实测可达 4 个月前视，`docs/review/17` §2-1）。

### 步骤 3：策略代码规范

**生命周期**（`base/base_strategy.py`，`on_bar` 是唯一 `@abstractmethod`）：

| 钩子 | 性质 | 用途 |
|:---|:---|:---|
| `on_bar(bar)` | **必须实现** | 逐 bar 推送，累积数据 |
| `on_bar_batch_end(trade_date)` | **可选**（框架 `getattr` 调用，`strategy_manager.py:714,1961`） | 当日全部 bar 推送完后回调 —— **调仓逻辑写在这里** |
| `on_init` / `on_start` / `on_stop` / `load_live_state` | 可选 | 初始化与实盘状态恢复 |

现有 6 个策略实现了 `on_bar_batch_end`（`bottom_strategy.py` 未实现）。

```python
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from modules.strategy.models import StrategyConfig, TradingSignal
# ⚠️ 是 models 不是 schemas；项目里没有名为 Signal 的类

class MyStrategy(BaseStrategy):
    DEFAULT_PARAMS = {
        "lookback": 60,
        "stop_loss_pct": 0.08,   # 正数，见下方符号约定
    }

    def on_bar(self, bar) -> List[TradingSignal]:
        ...                      # 严禁 shift(-N) / .iloc[i+1] / 硬编码凭证
        return []

    def on_bar_batch_end(self, trade_date=None) -> List[TradingSignal]:
        ...                      # 调仓 / 信号生成
```

⚠️ **`generate_signals(self, df)` 在项目中不存在**（旧版本文档写错过）—— 全库策略无此方法。

**止损符号约定（2026-09-15 统一为正数）**：

- ✅ 统一写 `stop_loss_pct ∈ (0, 1)`，语义「跌此比例止损」，判据 `price <= entry_price * (1 - stop_loss_pct)`
- ⚠️ 旧策略里的负数写法（`stop_loss = -0.07` 配 `entry * (1 + stop_loss)`）**方向极易读错** —— 正是 `rules/audit.md` 第一条「不等式方向检查」要防的翻车模式，迁移在做
- ATR 倍数式（`atr_stop_mult`，如 `high_vol_momentum_strategy.py` 的 2.0）是**合法形态**，须在参数注释里显式标注为 ATR 形态

**禁止项**：`shift(-N)` / `.iloc[i+1]` / 硬编码凭证 / `except Exception: pass` / **不设止损的裸策略**

### 步骤 4：策略存入 DB（**最容易漏的一步**）

策略**运行时从 DB `strategies.code` 加载（`exec()`）**，回测引擎同样如此 —— **改磁盘 `.py` 不影响实盘与回测**。

- 同步：`UPDATE strategies SET code = <文件完整内容> WHERE ...`
- ⚠️ 一个策略可能存在**多处 DB 副本**（多个 `strategies` 实例 + `strategy_templates.code_template`），必须**全部**更新
- ⚠️ 改参数默认值还须同步 `strategy_parameters` 覆盖 —— **JSON 列会盖掉 `DEFAULT_PARAMS`**
- 带 dry-run 的同步脚本范式：`scripts/_sync_cross_market_code.py`（不带 `--apply` 只查，带则 UPDATE 全部副本）

### 步骤 5：回测验证

依据：`docs/06-标准规范/04_回测分析标准流程.md`（**现行真相源**）+ 准入标准 §二「六道门」。
（旧文档曾指向 `docs/04-归档/design/策略回测业务流程说明.md` —— 已归档，**勿再作依据**。）

信号级冒烟（磁盘加载，不走 DB）：

```bash
cd quant_server && .venv/Scripts/python.exe scripts/backtest_<策略名>.py [start] [end]
```

**冒烟口径（全项目统一）**：有交易 / 无 NaN / 收益率 ∈ **[−95%, +500%]**。
（旧文档的「非 −100%」「收益率合理」两种表述已废弃，统一为这一条。）

检查清单：

- [ ] 3 个月冒烟（口径同上）
- [ ] 完整历史回测 + 分年度归因（与市场环境对得上）
- [ ] **滚动起始日分布** —— 路径依赖策略**必须**；看**中位 / 下四分位 / 最差**，禁单起始日结论
- [ ] **样本外两段**（判据事先定死，须同向改善）+ **安慰剂对照**
- [ ] 参数 ±20% 不翻转
- [ ] 无 look-ahead / survivorship / 数据泄露（过 `strategy-auditor`）

## 常见陷阱

| 陷阱 | 现象 | 根因 |
|:---|:---|:---|
| 预热幽灵持仓 | 策略不产生信号 | symbols 子集回测 + 全市场预热会冻结策略，需新鲜度守卫 |
| Mock 数据污染 | 因子值异常 | DATA_MODE 回退 simulated，`.env` 不进 `os.environ` |
| 时序污染 | 回测虚高 +20% | 未来数据泄露到训练集 |
| **磁盘改了但没生效** | 实盘/回测跑旧代码 | 策略从 DB `strategies.code` 加载，改文件必须同步 DB |
| **参数改了但没生效** | 默认值不生效 | `strategy_parameters` 覆盖盖掉 `DEFAULT_PARAMS` |
| **单起始日自欺** | 收益看起来很高 | 路径依赖策略的起跑日红利，须看滚动分布 |

## 已知经验法则

- A股 T+1：买入日次日才能卖出
- 涨跌停：主板 ±10%、科创板 ±20%、ST ±5%
- 止损/止盈用**收盘价判断、次日开盘执行**（`order_mode="open"`）→ ⚠️ 8% 是阈值不是最大亏损，跳空低开会亏更多
- **系统投资哲学：赔率优先于胜率，集中持仓，非对称止盈**（见 `docs/01-业务设计/系统目标与投资哲学.md` §三）
