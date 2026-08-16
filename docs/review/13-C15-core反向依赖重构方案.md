# C15 方案 v3：core 反向依赖重构（含重跑安全性实证）

> 2026-08 | v1→v2 修正门时序（两阶段注册）；v2→v3 修正验证方案（策略驱动重跑不安全）+ 双保险 + 实证附录
> 目标：消除 `core/engines/system/main_engine.py` 对 `modules.*` 的 6 处反向依赖；行为等价优先。

---

## 〇、第二轮评审意见处理（实证结论）

### 🔴 验证方案修正：策略驱动同日重跑不安全（实证确认）

`strategy_manager.py:1601-1622`：`_run_live_strategies` 仅过滤"昨日 pending 买入"（`_check_yesterday_pending`），**无"今日已驱动则跳过"守卫**；`state.last_run_date = trade_date`（:1626）只记录不用于跳过。同日重跑 → 再次 `handle_bar_batch` → **重复信号**。

**修正**：C15 验证**不再同日重跑策略驱动**。策略驱动无幂等本身是系统缺陷，单独列为后续修复项（见 §六），不并入 C15。

### 🟠 结算重算漂移——实证：无漂移（解除疑虑）

| 环节 | 实现（实证） | 二次结算结论 |
|:---|:---|:---|
| `_update_account_assets`（settlement_tasks:501-542） | `total_balance = total_asset` **快照式覆盖写**（非累加） | ✅ 覆盖同值，无漂移 |
| `_upsert_daily_performance`（:553-581） | `rec.total_asset = total_asset` upsert 覆盖 | ✅ 同上 |
| `_get_yesterday_total_asset`（:416-429） | 锚定 `trade_date < trading_day` 的上一快照 | ✅ 二次结算差分基准不变 |

结论：A34（对账记录幂等）+ 快照式覆盖 = **结算同日重跑安全**。

### 🟠 rebalance 净值快照——实证：upsert 幂等（解除疑虑）

`composite_service.py:529-567`：`INSERT ... ON CONFLICT DO UPDATE SET total_nav = EXCLUDED.total_nav` → upsert，重写相同值无害 ✅。`allocated_capital` 更新（:460）为覆盖写 ✅。

### 🟠 门异常保护：双保险

- 抽取门代码时**保留内部 try/except → `_drive_ok=False`**（现状 :341-343 语义）
- pipeline 外层再加 `try: gate_ok = await ... except Exception: gate_ok = False`（双保险）

### 🟠 "core→shared 合法"出处

引用 `docs/04-归档/design/量化交易系统-混合架构设计.md` 的分层定义（core=稳定骨架、shared=公共基础设施、依赖方向 modules→shared→core）——core 引用 shared 的 session/基础设施属合法方向；现状 main_engine:220 已有 `from shared.database.session import get_session_manager` 先例。

---

## 一、目标结构（两阶段注册，同 v2）

```python
class MainEngine:
    self._pre_gate_tasks:  List[Tuple[str, Callable]]   # 同步/state/因子/结算
    self._post_gate_tasks: List[Tuple[str, Callable]]   # rebalance/策略驱动

    async def register_daily_task(self, name, fn, phase="pre_gate"): ...

    async def _run_daily_pipeline(self, today):
        if not self._pre_gate_tasks and not self._post_gate_tasks:
            logger.warning("日终任务注册表为空（模块可能被禁用），流水线空转")
            return
        for name, fn in self._pre_gate_tasks:
            try: await fn(today)
            except Exception as e: logger.warning("日终任务 %s 失败（非致命）: %s", name, e)
        # 门（双保险：内部 try/except + 外层兜底）
        try:
            gate_ok = await self._data_integrity_gate(today)
        except Exception as e:
            logger.warning("数据完整性门异常: %s → 保守跳过驱动", e)
            gate_ok = False
        if not gate_ok:
            return
        for name, fn in self._post_gate_tasks:
            try: await fn(today)
            except Exception as e: logger.warning("日终任务 %s 失败（非致命）: %s", name, e)
```

## 二、modules 侧注册（同 v2）

| 模块 | 任务（phase） | 包装 |
|:---|:---|:---|
| data | sync_daily / market_state_update / etf_factor（pre_gate） | 闭包自取 session |
| account | daily_settlement（pre_gate） | 闭包自取 session |
| strategy | composite_rebalance / strategy_drive（post_gate） | 闭包捕获 main_engine |

## 三、实施步骤（6 步，同 v2）

1. main_engine 加两阶段注册表 + pipeline + 门（双保险）
2-4. 三模块注册（代码原样搬移进闭包，内部异常/日志原样保留）
5. main_engine 删 6 处 import 与内联任务体，调度闭包改调 pipeline
6. 验证（§四）

## 四、验证方案 v3（修正版）

| 验证项 | 方法 | 安全性依据 |
|:---|:---|:---|
| 门时序/日志序列 | **跨日对比**：D 日（重构前）日终日志 vs D+1 日（重构后）日终日志，结构 diff（任务序列 + 门位置 + 成功/失败标记） | 无需同日重跑 |
| 结算幂等重跑 | 同日手动重复触发**仅结算任务**（不触发整条流水线）→ 资产/绩效/对账无漂移 | 实证：快照式覆盖 + A34 ✅ |
| rebalance 重跑 | 同日重复触发 rebalance → nav/allocated_capital 值不变 | 实证：upsert ✅ |
| 策略驱动 | **不重跑**；仅验证"门跳过"路径（数据不完整时驱动不执行——该路径不生成信号，安全） | 驱动无幂等 🔴 |
| 门失败语义 | 人为屏蔽当日数据 → 门 warning + rebalance/驱动日志缺席 | 安全（不驱动） |
| 空注册表 | 清空注册表触发 → warning | — |

> 策略驱动"跨日对比"：D 日与 D+1 日信号数量自然不同（不同行情），diff 只比对**日志结构**（任务执行序列、门位置、跳过标记），不比对信号数。

## 五、风险与回滚（同 v2）

- 每步独立 commit；回滚 = revert 5 个 commit
- 任务代码原样搬移（仅闭包包装），diff 可核对无逻辑改动
- 完成后 core 恢复零 modules 依赖

## 六、本次暴露的独立缺陷（不并入 C15，单列后续修复）

| 缺陷 | 位置 | 建议 |
|:---|:---|:---|
| 🔴 策略驱动无幂等守卫 | strategy_manager.py:1552-1665 | 加"今日已驱动则跳过"（`state.last_run_date == trade_date` 早退），防手动重跑/重复调度产生重复信号——列为独立 C 类修复 |
