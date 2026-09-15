---
name: strategy-auditor
description: 策略代码质量门。在回测前运行快速自动检查，拦截look-ahead bias、survivorship bias、数据泄露、参数异常等常见量化陷阱。当涉及策略上线前检查、回测前验证、代码审查时使用。
---

# 策略质量门

> 落实 `audit.md`、`audit-backend.md`、**`audit-strategy.md`** 规则到策略领域的自动化检查。
> `audit-strategy.md` 定义了六大审计维度（未来函数/交易逻辑/计算错误/状态机/边界/语法），本 skill 将其转化为可机检的清单。
>
> ⚠️ **事实性表述一律以代码与 DDL 为准**（表名查 `docs/sql/create_table.sql`，参数取值查策略文件本身）。
> **2026-09-15 修正**：此前版本写入 `daily_quotes`（**不存在的表**，实为 `modules/data/constants.py` 的 `DataType` 枚举码）与「止损必须为负数」（与现行正数约定冲突），均已修正。
> 🚧 **待办**：本清单 🔴 四项 **100% 可脚本化**，计划落为 `quant_server/scripts/audit_strategy.py` 并接入 hook —— 届时本文件只保留「运行脚本、🔴 清零」，**不再维护事实清单**（根治规则随代码漂移的问题）。见 `docs/review/17` §1-2。

## 检查清单（按阻断级别）

### 🔴 阻断级（必须修复才能回测）

1. **Look-ahead bias**
   - `shift(-1)` / `shift(-2)` / `df[col].shift(-N)`
   - `.iloc[i+1]`、`.iloc[i+N]` 访问未来行
   - `rolling().apply()` 闭包内访问窗口右侧数据
   - → **发现即阻断**

2. **硬编码凭证**
   - `token` / `password` / `api_key` / `secret` 后跟字符串字面量
   - → **发现即阻断**
   - ⚠️ **已知遗留（尚未整改）**：`etf/bottom_strategy.py:76-78` 存在 `"db_password": "123456"` 等硬编码 DB 凭证。**新策略一律不得再出现此类写法**；该处待迁 `.env`（已登记 `docs/review/17`）。审计新策略时**不再重复引用该遗留作为"已有先例"**。

3. **除零无保护**
   - `x / y` 或 `x / (a - b)` 且无 `if y == 0` / `np.where` / `max(eps)` 包围
   - → 阻断

4. **参数越界**
   - **止损**：必须可表达为 `入场价 × (1 − 跌幅阈值)`，**跌幅阈值 ∈ (0, 1)（正数）**，判据 `price <= entry_price * (1 - stop_loss_pct)`
     - ⚠️ 负数写法（`stop_loss = -0.07` 配 `entry * (1 + stop_loss)`）属**历史遗留**，方向极易读错 → 审计时记 🟡 并建议改成正数
     - **ATR 倍数式为合法豁免形态**（如 `atr_stop_mult`），须在参数注释中显式标注
   - 止损幅度 > 止盈幅度
   - 最大持仓数 ≤ 0 或 > 100
   - 仓位比例 ∈ [0, 1]
   - → 阻断

### 🟡 警告级（建议修复，可选继续）

5. **Survivorship bias 风险** —— 标的池是否只含当前存活标的（未过滤 `delist_date`）→ 警告

6. **T+1 合规** —— 买入/卖出日至少间隔 1 个交易日；`pct_change` ≥ 9.5% 的买入、≤ −9.5% 的卖出是否跳过 → 警告

7. **数据依赖完整性**
   - 回测期 symbol 在**对应行情表**（股票 `stock_daily` / ETF `etf_daily`）覆盖率 **> 90%**（**无 `daily_quotes` 表**）
   - 所需因子在 `factor_data` 中齐备，且定义已注册到 **`factor_definitions`**（**无 `factor_metadata` 表**）
   - → 警告

8. **NaN/Inf 传播链** —— `**` 运算前底数 > 0 的守卫；`log()` / `sqrt()` 参数 ≥ 0 的守卫 → 警告

### 🟢 信息级

9. **策略代码长度** —— > 500 行建议拆分；> 1000 行强烈建议重构

10. **硬编码数字** —— 标记 `DEFAULT_PARAMS` 范围外的魔术数字

## 豁免口径（2026-09-15 新增）

`audit-strategy.md` 的「四大模块强制独立」与「止盈独立于平仓」两条，遇下列情形**以策略的显式声明为准**，不再记为违规：

| 规则 | 豁免条件 | 实例 |
|:---|:---|:---|
| 四大模块拆分 | ① `reference/` 下的参考/历史策略 ② ML 模型类策略 ③ 文件头显式声明不适用并说明理由 | `bottom_strategy.py`（ML）、`deep_drop_rebound_strategy.py`、`stock_low_high_strategy.py` |
| 止盈独立于平仓 | 策略在**文件头或方法 docstring 显式声明「本策略无主动止盈」并说明出场机制**（移动止损 / 轮动换仓 / 信号退出） | `cross_market_momentum_strategy.py:1591-1593`（「主动止盈会截断动量」）；`high_vol_momentum_strategy.py`（真实止盈是移动止损，以 `TAKE_PROFIT` 类型发信号） |

> ⚠️ **未声明 ≠ 豁免**：没有显式声明的缺失，仍按违规计。

## 检查结果模板

```
策略质量门报告：<策略名>

🔴 阻断: 0 issues
🟡 警告: 2 issues
  - [Survivorship] symbol 列表未过滤 delist_date，存在生存偏差风险
  - [T+1] 策略在 t 日买入后在 t 日卖出（需至少隔 1 日）
🟢 信息: 1 issue
  - [CodeSize] 策略文件 647 行，建议拆分为多个模块
⚪ 豁免: 1 项
  - [四模块] 文件头已显式声明不适用（ML 模型类），理由见 docstring

结论：⚠️ 有警告，建议修复后回测
```
