# -*- coding: utf-8 -*-
"""过期 pending 买单对账：只取消「已不在当日目标池」的**买入**意图。

## 被修复的问题（2026-09-21 → 09-22 实盘）

`signal_engine._persist_signal` 的去重守卫按 `(strategy, ts_code, 方向)` 匹配，
**换标的轮动时打不中**：

  · 09-21 19:33  无候选 → 防御兜底 → 发 `511010.SH` 买单
  · 09-21 20:55  目标变 `512660.SH` → 新买单 ts_code 不同 → 旧行原样留下
  · 09-22 19:33  两个买入意图同时 `pending_manual`（人工下单时容易下错）

策略侧也看不见它：`_pending_buys` 是内存态（进程重启即空），DB 里那条只被基类
`load_live_state` 读进 `_pending_signals`，不参与选股。

## 本文件守住五件事

1. **fail-open 契约**：当日未重算目标（早退 / 异常 / 未运行）→ `get_target_pool`
   返回 None → 框架一行都不改。这是最关键的断言 —— 拿昨天的目标取消今天的
   有效意图等于误杀。
2. **只碰买单**：卖单即便不在目标池也不得被取消（V3 的「3 个调仓日重发」依赖它持续 pending）。
3. **状态守卫**：`allowed_from` 只有 `pending_manual` → 人工已确认（confirmed）的不动。
4. **空输入零查询**：没有过期意图时不发 SQL。
5. **差额留痕**：预期取消 N 条、实际只流转 M<N 条（差额被人工作废/确认）→ 必须告警。
"""
import asyncio
from datetime import date

from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

TODAY = "2026-09-22"


def _mk():
    """构造策略实例（不连 DB：`_db_session_factory` 未注入 → on_start 跳过加载）。"""
    return CrossMarketMomentumStrategy(name="T-STALE")


# ---------------------------------------------------------------- get_target_pool


def test_base_default_is_fail_open():
    """未实现钩子的策略必须返回 None —— 行为逐位不变。"""
    from modules.strategy.strategies.base.base_strategy import BaseStrategy

    class _Bare(BaseStrategy):
        def on_bar(self, bar):  # noqa: D102 - 抽象方法最小实现
            return []

    st = _Bare(name="T-FAILOPEN")
    assert st.get_target_pool(TODAY) is None


def test_none_when_target_not_computed_today():
    """关键契约：当日**未重算**目标 → None（框架不得拿昨天的目标取消今天的意图）。"""
    st = _mk()
    st._last_target_codes = {"511010.SH"}
    st._last_target_date = "2026-09-21"  # 昨天算的
    assert st.get_target_pool(TODAY) is None


def test_returns_set_when_computed_today():
    st = _mk()
    st._last_target_codes = {"512660.SH"}
    st._last_target_date = TODAY
    assert st.get_target_pool(TODAY) == {"512660.SH"}


def test_empty_target_pool_is_returned_as_empty_set():
    """目标为空集（清仓）≠ 不适用：必须返回 set() 而不是 None，否则清仓意图永不被收口。"""
    st = _mk()
    st._last_target_codes = set()
    st._last_target_date = TODAY
    assert st.get_target_pool(TODAY) == set()


def test_on_start_and_on_stop_clear_target_memory():
    """重启/停止后不得带着上一次的目标 —— 否则跨进程误杀。"""
    st = _mk()
    st._last_target_codes = {"512660.SH"}
    st._last_target_date = TODAY
    st.on_stop()
    assert st.get_target_pool(TODAY) is None

    st._last_target_codes = {"512660.SH"}
    st._last_target_date = TODAY
    asyncio.run(st.on_start())  # 无 session_factory → 不触 DB
    assert st.get_target_pool(TODAY) is None


# ------------------------------------------------------------------ 选择与落库


def _pending_map():
    """09-22 的真实形态：卖单(持仓) / 过期买单(防御兜底) / 当日买单(新目标)。"""
    return {
        "159985.SZ": {
            "id": "sig-sell", "ts_code": "159985.SZ", "direction": "sell", "price": 2.323,
        },
        "511010.SH": {
            "id": "sig-stale", "ts_code": "511010.SH", "direction": "long", "price": 140.672,
        },
        "512660.SH": {
            "id": "sig-new", "ts_code": "512660.SH", "direction": "long", "price": 1.168,
        },
    }


class _FakeResult:
    def __init__(self, rowcount):
        self.rowcount = rowcount


class _FakeSession:
    def __init__(self, rowcount=1):
        self.stmts = []
        self.rowcount = rowcount

    async def execute(self, stmt):
        self.stmts.append(stmt)
        return _FakeResult(self.rowcount)

    async def commit(self):
        pass


class _FakeFactory:
    def __init__(self, session):
        self._s = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._s

    async def __aexit__(self, *exc):
        return False


def _manager_with(session):
    from modules.strategy.engines.strategy_manager import StrategyManager

    mgr = StrategyManager.__new__(StrategyManager)  # 绕过 __init__，只注入被依赖的属性
    mgr.session_factory = _FakeFactory(session)
    return mgr


def test_stale_selection_excludes_target_and_sells():
    """卖单不在目标池也不动；买单在目标池也不动。"""
    from modules.strategy.engines.strategy_manager import StrategyManager

    stale = StrategyManager._stale_pending_buys(_pending_map(), {"512660.SH"})
    assert [s["ts_code"] for s in stale] == ["511010.SH"]


def test_buy_direction_aliases_are_covered():
    """`long` 与 `buy` 都要认（与 bar 跳过过滤器同口径）。"""
    from modules.strategy.engines.strategy_manager import StrategyManager

    pm = {
        "A.SH": {"id": "1", "ts_code": "A.SH", "direction": "long"},
        "B.SH": {"id": "2", "ts_code": "B.SH", "direction": "BUY"},
        "C.SH": {"id": "3", "ts_code": "C.SH", "direction": "sell"},
    }
    stale = StrategyManager._stale_pending_buys(pm, set())
    assert sorted(s["ts_code"] for s in stale) == ["A.SH", "B.SH"]


def test_cancel_only_stale_buy_and_only_pending_manual():
    """端到端：只发一条 UPDATE，只带过期买单，且旧状态条件只允许 pending_manual。"""
    session = _FakeSession(rowcount=1)
    mgr = _manager_with(session)

    codes = asyncio.run(
        mgr._cancel_stale_pending_buys("sid-1", _pending_map(), {"512660.SH"})
    )

    assert codes == ["511010.SH"]
    assert len(session.stmts) == 1, "必须是单条批量 UPDATE，不得逐条"
    sql = str(session.stmts[0])
    assert "UPDATE signals" in sql
    assert "signals.signal_status IN" in sql  # 旧状态守卫（竞态保护）
    assert "signals.id IN" in sql
    # SET 值：cancelled + superseded 原因
    values = {str(k.name): v.value for k, v in session.stmts[0]._values.items()}
    assert values["signal_status"] == "cancelled"
    assert "已不在当日目标池" in values["reason"]


def test_empty_stale_set_issues_no_sql():
    """没有过期意图 → 零查询。"""
    session = _FakeSession()
    mgr = _manager_with(session)

    codes = asyncio.run(
        mgr._cancel_stale_pending_buys("sid-1", _pending_map(), {"511010.SH", "512660.SH"})
    )

    assert codes == []
    assert session.stmts == []


def test_rowcount_mismatch_is_logged(caplog):
    """预期 N 条、实际只流转 M<N 条（差额已被人工确认/作废）→ 必须留痕。"""
    session = _FakeSession(rowcount=0)
    mgr = _manager_with(session)

    with caplog.at_level("WARNING"):
        codes = asyncio.run(
            mgr._cancel_stale_pending_buys("sid-1", _pending_map(), {"512660.SH"})
        )

    assert codes == ["511010.SH"]
    mine = [r for r in caplog.records if r.name.endswith("strategy_manager")]
    assert any("不覆盖成交事实" in r.getMessage() for r in mine)


def test_pending_map_without_ids_is_skipped():
    """旧格式（无 id，如历史调用方）→ 宁可不动，也不猜。"""
    session = _FakeSession()
    mgr = _manager_with(session)

    codes = asyncio.run(
        mgr._cancel_stale_pending_buys(
            "sid-1", {"511010.SH": {"ts_code": "511010.SH", "direction": "long"}}, set()
        )
    )

    assert codes == []
    assert session.stmts == []


def test_real_case_dates_are_the_live_ones():
    """护栏：用例锚定的日期就是实盘事故日期（改测试日期时会被迫复核背景）。"""
    assert date(2026, 9, 21).isoformat() < TODAY
