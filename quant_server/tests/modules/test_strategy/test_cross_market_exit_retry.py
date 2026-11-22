# -*- coding: utf-8 -*-
"""V3：退出信号（卖出）的重发判据 —— 间隔路径。

## 背景

`_should_retry_exit` 是 F3 修复的核心：原实现把 `_exit_pending` 当**单向阀**，
卖出 / 买入 / 止损三处全部跳过 → 退出信号一旦丢失（价格缺失 / 订单被拒 /
长期不可成交）**持仓永久冻结**。现在改为「登记 + 到期重发」。

判据（`cross_market_momentum_strategy.py:1617`）：

    (self._rebalance_seq - self._exit_pending[code]) >= self.exit_retry_days

两个量都是**内存态**、`_rebalance_seq` 只在 `_run_rebalance` 里自增：

  · 未登记（`_exit_pending` 无该 code，含**进程重启后**）→ 立即允许（这也是
    2026-09-22 实盘看到重发的原因：重启清空了登记）
  · 距上次发出 < `exit_retry_days` 个调仓日 → 跳过（防重复卖出）
  · 距上次发出 ≥ `exit_retry_days` → 重发

## 为什么用单测而不是「挂 3 个交易日等」

2026-09-22 用户决策：**不为了观察这条路径而让实盘停摆 3 天**（账户现金仅 ≈2,209，
不卖 `159985.SZ` 就买不了 `512660.SH`，等于整次调仓不执行；且观察期判据①是
「人工执行与策略意图一致」，刻意不执行会留下人为偏差）。

判据本身是**两个整数的比较**，单测即可钉死边界；「到期重发」这个**动作**
已于 2026-09-22 实盘端到端验证过（新建一行、数量取 broker 实际持仓 7700、
旧行未被改写）。真机间隔路径等自然触发（监控任务按两条路径分开记录）。
"""
from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

CODE = "159985.SZ"
RETRY = 3


def _mk(seq: int, last: int | None, retry_days: int = RETRY):
    """构造只带判据所需内存态的策略实例（不连 DB、不跑回放）。"""
    st = CrossMarketMomentumStrategy(name="T-EXITRETRY")
    st.exit_retry_days = retry_days
    st._rebalance_seq = seq
    if last is not None:
        st._exit_pending[CODE] = last
    return st


def test_unregistered_always_allowed():
    """未登记 → 立即允许。含**进程重启后**（`_exit_pending` 内存态被清空）的情形。"""
    assert _mk(seq=7, last=None)._should_retry_exit(CODE) is True


def test_skipped_before_interval():
    """距上次发出 < 3 个调仓日 → 跳过（防重复卖出）。"""
    assert _mk(seq=8, last=7)._should_retry_exit(CODE) is False   # +1
    assert _mk(seq=9, last=7)._should_retry_exit(CODE) is False   # +2


def test_resent_exactly_at_interval():
    """边界：**正好** +3 即重发（判据是 >= 而非 >，差一天会让持仓多冻结一天）。"""
    assert _mk(seq=10, last=7)._should_retry_exit(CODE) is True


def test_resent_after_interval():
    assert _mk(seq=98, last=7)._should_retry_exit(CODE) is True


def test_interval_is_per_code():
    """按标的登记：A 到期不影响 B 的间隔（多持仓轮动时必须逐标的判断）。"""
    st = _mk(seq=10, last=7)
    st._exit_pending["512660.SH"] = 10          # 本调仓日刚登记
    assert st._should_retry_exit(CODE) is True
    assert st._should_retry_exit("512660.SH") is False


def test_same_seq_never_retries():
    """同日重复驱动（`_rebalance_seq` 相等）不得重发 —— 否则同日会重复挂卖出。"""
    assert _mk(seq=7, last=7)._should_retry_exit(CODE) is False
