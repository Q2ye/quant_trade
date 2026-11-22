# 回测任务登记（REQ-20261114-highvol-moneyflow-select）

> 执行环境：生产库 `quant_signals`（用户 2026-11-14 裁决：不建独立测试库，只建 draft 回测副本，不碰 live 实例与账户）
> API：`POST http://127.0.0.1:8888/quantTrade/backtest/tasks`（`AUTH_ENABLED=false`）
> 回测副本策略：`b9924ab2-5831-431f-acbb-4fa8c73ef3c6`（`高波动-资金流-验证`，`draft/backtest`）
> 副本代码与磁盘逐字节一致：md5 `01c99df990f2dee1ab86f5f8ecfcb0d0`，57,708 字符

| 臂 | 参数 | task_id | 状态 |
|:--|:--|:--|:--|
| BASE | `{}` | `e4faeeaf-d6ff-418a-b330-e94639ec545d` | 已提交 |
| A | `{"enable_moneyflow_factor": true, "moneyflow_weight": 1.0}` | `f9754f77-ca98-4618-89c7-4b6d292762e8` | 已提交 |
| B | `{"moneyflow_min": 0}` | `cd741335-546a-4c22-ae9f-e33d3b93d38a` | 已提交 |

固定项：`2021-09-20 ~ 2026-09-19`、`initial_capital=1,000,000`、`commission=0.0001`、`slippage=0.0001`、`benchmark=000300.SH`

## 结果读取

```sql
select name, status,
       (result->>'total_return')::numeric total_return,
       (result->>'max_drawdown')::numeric max_dd,
       (result->>'sharpe_ratio')::numeric sharpe,
       (result->>'win_rate')::numeric win_rate,
       (result->>'num_trades')::int num_trades
from backtest_tasks
where id in ('e4faeeaf-…','f9754f77-…','cd741335-…');
```

「7 天内失败笔数」需从 `backtest_trades` 配对计算（脚本待建：`scripts/_diag/_hv_arm_compare.py`）。

## 复核与重跑（2026-11-15）

**现金修复验证**：task `ef131432-b1e2-4202-b60a-9d5467f15154`（2026-06-01~2026-09-19）
→ 收益 **+54.3%**、16 笔；**资金不足 0 / 持仓不足 0 / 订单验证失败 0**。

**三臂重跑**（参数写入各臂 draft 的 `strategy_parameters`）：

| 臂 | strategy_id | task_id |
|:--|:--|:--|
| BASE v2 | `b9924ab2-5831-431f-acbb-4fa8c73ef3c6` | `a4d37b55-387e-46e7-b203-b68d3d6ec3c7` |
| A v2 | `50a9c07f-be0b-4042-8dea-d483a9f0e3d4` | `d8bab705-5179-4ce8-8ea4-5e7f2318048f` |
| B v2 | `546f0632-9140-4952-acfe-c8d74fed1fe9` | `4eab023c-0f28-4d52-b6c5-120dced3100a` |

旧三臂（`e4faeeaf` / `f9754f77` / `cd741335`）作废：执行损坏 + 参数未生效。

## dev schema 三臂（2026-11-15，8080 服务）

服务：`quant_trade/quant_server/main.py --mode development --port 8080`（`quant_dev` → `dev` schema）
代码：磁盘版（含现金修复 + 资金流参数），三臂各自 draft 携带 `strategy_parameters`。

| 臂 | strategy_id | task_id |
|:--|:--|:--|
| BASE | `76adead8-385d-4301-8be4-b617d9ffb4b7` | `a5302b0c-3f75-4d07-869c-f8810675b922` |
| A | `9887940c-d33b-4071-982a-fa2f0d25ff7c` | `b565d4c3-7c27-4819-835f-da4204dedc53` |
| B | `76b03e9e-044d-407c-8cb5-19def6eeed02` | `9d03d1ee-69d7-4956-ac18-532521b28090` |

隔离验证：提交后 `dev.backtest_tasks=3`，`public.backtest_tasks=196` 不变。

## 方案 1：熊市空仓（2026-11-17）

依据：归因显示熊市 46 笔亏 −177k（占总亏损 89%），胜率与牛市相同（30.4%）但期望 −2.4% vs +0.2%。

| 臂 | 参数 | strategy_id | task_id |
|:--|:--|:--|:--|
| C 熊市空仓 | `bear_max_positions=0` | `9b2bee6e-024d-4c2b-b95d-48f33c7b3991` | `28468139-d23b-4f35-a799-986c7d1f76e0` |

对照：BASE = `a5302b0c-…`（−50.4% / MDD 75.9% / 92 往返）。

## BASE 12 起始日分布（2026-11-22，阶段0）

统一 end_date=2026-09-19，strategy=HV_DEV_BASE `76adead8`。回测池上限 10，分批提交。

| 起始日 | task_id |
|:--|:--|
| 2021-09-20 | 2153ce9c-123d-4a1c-a0fe-3e94756d1f1d |
| 2021-12-01 | c94d1cb3-52ad-49b2-a7e0-9e67614a3557 |
| 2022-03-01 | 8beab7d8-8791-4404-bad1-9fea3a501f05 |
| 2022-06-01 | b79c7b4d-cd5b-40d2-b9b4-f003c41e6d88 |
| 2022-09-01 | 7e713898-bbc7-4b13-b943-60a15a4f872d |
| 2022-12-01 | d44e859b-b0b4-4448-991c-143e3da7b3ff |
| 2023-03-01 | f13cd0eb-e9c7-4e01-ab46-818c548452e9 |
| 2023-09-01 | 10516375-fdd8-417a-a00c-75a0e3b8d485 |
| 2024-03-01 | c980eb60-195c-490a-94e9-e2e3ac1ea2ae |
| 2024-09-02 | e06eea92-3b19-4960-8ef3-749d3643117f |
| 2025-03-03 | ⏳ 待补（池满） |
| 2025-09-01 | 7286a157-2bfe-4497-92b2-aaa00a8b9c51 |
