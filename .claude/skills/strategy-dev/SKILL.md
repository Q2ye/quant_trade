---
name: strategy-dev
description: 量化策略开发专项。当涉及策略代码编写、因子接入、回测参数配置、策略信号链路、base_strategy继承、策略版本迭代等关键词时使用。
---

# 策略开发技能

> 架构约束见 `quantsys-architect`。本技能专注策略开发流程。
> **硬性约束与审计规则见 `.claude/rules/audit-strategy.md`** — 包含六大审计维度、四大模块拆分强制要求、边界全覆盖、交付六步结构。

## 策略开发 SOP

### 步骤 1：定位策略类型

| 分类 | 基类 | 目录 | 参考策略 |
|:---|:---|:---|:---|
| 技术指标 | `base/base_strategy.py` | `strategies/technical/` | `ma_cross_strategy.py`、`macd_strategy.py` |
| Alpha因子 | 同上 | `strategies/alpha/` | `factor_strategy.py`、`mean_reversion_strategy.py` |
| 行业/资产轮动 | 同上 | `strategies/rotation/` | `industry_rotation_strategy.py` |
| AI/ML | 同上 | `strategies/ai/` | `dl_strategy.py`、`ml_strategy.py` |
| ETF专用 | 同上 | `strategies/etf/` | `bottom_strategy.py` |

### 步骤 2：确认数据依赖

- 因子数据 → `factor_data` 表，通过 `DataService.get_factor_data()` 获取
- 行情数据 → `daily_quotes` 表（日线）/ `weekly_quotes`（周线），Tushare → DB
- 财务数据 → `financial_data` 系列表
- **新增因子必须先注册到 `factor_metadata` 表**，否则策略运行时找不到

### 步骤 3：策略代码规范

```python
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from modules.strategy.schemas import StrategyConfig, Signal

class MyStrategy(BaseStrategy):
    # 1. DEFAULT_PARAMS：所有可调参数在此集中定义
    DEFAULT_PARAMS = {
        "lookback": 60,
        "threshold": 0.02,
    }

    # 2. generate_signals()：核心逻辑，输入 df，输出 List[Signal]
    def generate_signals(self, df: pd.DataFrame) -> List[Signal]:
        # 严禁：shift(-1)、.iloc[i+1]（look-ahead）
        # 严禁：硬编码凭证
        # 必须：df.empty 检查
        # 必须：除零保护
        pass
```

### 步骤 4：策略存入 DB

**关键**：策略代码从 DB `strategies.code` 列加载运行。改完策略文件后必须同步更新 DB：
```sql
UPDATE strategies SET code = '<策略文件完整内容>' WHERE name = '<策略名>';
```
否则运行的是旧代码。

### 步骤 5：回测验证

参见 `docs/04-归档/design/策略回测业务流程说明.md`（已归档，回测流程/API 速查/信号链路）与 `docs/02-功能设计/交易模块/信号处理与执行链路设计.md`（当前依据）。核心检查清单：
- [ ] 3 个月冒烟回测通过（有交易、无 NaN、非 -100%）
- [ ] 完整 5 年回测 vs 基线对比
- [ ] 牛/熊/震荡分拆绩效
- [ ] 最大回撤时间线 + 归因
- [ ] 无 look-ahead bias / survivorship bias / 数据泄露

## 常见陷阱

| 陷阱 | 现象 | 根因 |
|:---|:---|:---|
| 预热幽灵持仓 | 策略不产生信号 | symbols 子集回测+全市场预热会冻结策略，需新鲜度守卫 |
| Mock 数据污染 | 因子值异常 | DATA_MODE 回退 simulated，.env 不进 os.environ |
| 时序污染 | 回测虚高 +20% | 未来数据泄露到训练集 |

## 已知经验法则

- A股 T+1：买入日次日才能卖出
- 涨跌停：主板 ±10%、科创板 ±20%、ST ±5%
- 止损/止盈用收盘价判断，次日开盘执行
- **系统投资哲学：赔率优先于胜率，集中持仓，非对称止盈**
