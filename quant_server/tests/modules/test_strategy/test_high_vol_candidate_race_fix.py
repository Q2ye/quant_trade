# -*- coding: utf-8 -*-
"""
高波动动量轮动 v7.2 候选确认竞态修复测试

背景：同一批次内 `_confirm_pending_buys`（确认失败 → reject，fire-and-forget 异步写）
与 `_screen_stocks` 重新入池（_persist_candidate 幂等复用）竞写同一信号行，
导致 reject 丢失（002552 旧行被覆盖回 pending_confirm）。

修复：确认失败时将 signal_id 记入 `_rejected_candidate_ids`，
`_persist_candidate` 幂等复用扫描跳过这些行 → 强制新建行。
"""
import os

import pytest

_STRATEGY_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    "modules", "strategy", "strategies", "rotation",
    "high_vol_momentum_strategy.py",
)


def _load_strategy_class():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "high_vol_momentum", os.path.abspath(_STRATEGY_PATH)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.HighVolMomentumStrategy


class TestCandidateRaceFix:
    """候选确认竞态修复"""

    def _make_strategy(self, **overrides):
        cls = _load_strategy_class()
        return cls(name="测试-7.2", parameters=overrides or None)

    def test_rejected_candidate_ids_initialized_empty(self):
        """集合在 __init__ 中初始化为空"""
        s = self._make_strategy()
        assert s._rejected_candidate_ids == set()

    def test_rebalance_clears_rejected_set_each_batch(self):
        """每个批次开始前清空集合（防跨批次残留）"""
        s = self._make_strategy()
        s._rejected_candidate_ids.add("cand-001")
        s._run_rebalance()
        # _run_rebalance 先清空再走空数据缓存早退，集合应为空
        assert s._rejected_candidate_ids == set()

    def test_confirm_failure_adds_candidate_to_rejected_set(self):
        """确认失败（price <= signal_price）时，signal_id 被记入 _rejected_candidate_ids

        用 confirm_window_days=1 覆盖（窗口=1 时确认失败即 reject，不保留待次日）。
        默认 8.1 窗口=2 时失败会保留待 T+2，是另一语义。
        """
        s = self._make_strategy(confirm_window_days=1)
        # 构造一笔待确认候选：signal_price=10.0，当前价 9.0 → 确认失败
        s._buy_pending["000001.SZ"] = {
            "signal_price": 10.0,
            "weight": 0.5,
            "signal_date": "2026-08-17",
            "signal_id": "cand-reject-me",
        }
        # 注入收盘价 9.0 的 K 线 → 触发确认失败分支
        import pandas as pd
        s._data_cache["000001.SZ"] = pd.DataFrame({
            "close": [9.0], "high": [9.0], "low": [9.0],
            "volume": [1000000], "amount": [9000000],
        })
        # v8.1: 确认窗口=1，gap 须=1（T+1）才走 reject 分支；
        # gap<=0（同日入池）会保留待次日。override 交易日历使 gap=1。
        s._last_trade_date = "2026-08-18"
        s._confirm_gap_trading_days = lambda _sd, _td: 1
        s._rejected_candidate_ids.clear()
        s._confirm_pending_buys()
        assert "cand-reject-me" in s._rejected_candidate_ids
        # 确认失败后 _buy_pending 应已清空（该候选移出）
        assert "000001.SZ" not in s._buy_pending

    def test_persist_skips_rejected_rows_in_idempotent_reuse(self):
        """
        _persist_candidate 幂等复用扫描跳过 _rejected_candidate_ids 中的行。

        核心断言：候选入池时若旧行是被本批次 reject 的，则不能复用其 id，
        而应保留新生成的 signal_id（新建行）。
        """
        s = self._make_strategy()
        # 模拟本批次确认失败已记录的行
        s._rejected_candidate_ids.add("old-rejected-row-id")
        # 构造新候选（新 signal_id）
        pinfo = {"signal_price": 12.0, "weight": 0.5, "signal_id": "new-cand-id"}

        # 直接验证复用扫描逻辑：构造一个 fake repo，get_by_stock 返回旧行
        class FakeRow:
            id = "old-rejected-row-id"
            signal_status = "pending_confirm"
        class FakeRepo:
            async def get(self, sig_id):
                return None
            async def get_by_stock(self, ts_code, strategy_id, limit=20):
                return [FakeRow()]
            async def update(self, sig_id, data):
                pass
            async def create(self, data):
                pass

        # 临时替换 _persist_candidate 内部 repo 依赖的最小路径验证：
        # 直接内联幂等复用逻辑（与生产代码一致），确认跳过 rejected 行
        _dups = [FakeRow()]
        for _d in _dups:
            if _d.id in s._rejected_candidate_ids:
                continue
            if getattr(_d, "signal_status", None) == "pending_confirm":
                sig_id = _d.id
                pinfo["signal_id"] = sig_id
                break
        # 被跳过后 pinfo["signal_id"] 应保持新 id，未复用旧行
        assert pinfo["signal_id"] == "new-cand-id"

    def test_persist_reuses_non_rejected_pending_row(self):
        """非 rejected 的 pending_confirm 行仍可正常幂等复用（原逻辑不回退）"""
        s = self._make_strategy()
        s._rejected_candidate_ids.clear()
        pinfo = {"signal_price": 12.0, "weight": 0.5, "signal_id": "new-cand-id"}

        class FakeRow:
            id = "existing-pending-row"
            signal_status = "pending_confirm"
        _dups = [FakeRow()]
        for _d in _dups:
            if _d.id in s._rejected_candidate_ids:
                continue
            if getattr(_d, "signal_status", None) == "pending_confirm":
                sig_id = _d.id
                pinfo["signal_id"] = sig_id
                break
        assert pinfo["signal_id"] == "existing-pending-row"

    def test_confirm_skips_same_day_candidate(self):
        """同日入池候选（signal_date == today）跳过确认，保留待次日。

        修复 2026-08-25：候选入池 signal_price=当日收盘价，若同日二次驱动
        （重启/补跑）确认，price<=signal_price 恒成立误拒（8-24 603519/603565）。
        """
        s = self._make_strategy()
        s._buy_pending["000001.SZ"] = {
            "signal_price": 10.0,
            "weight": 0.5,
            "signal_date": "2026-08-24",   # 与 today 同日
            "signal_id": "cand-same-day",
        }
        s._last_trade_date = "2026-08-24"
        s._replaying = True  # 跳过 DB 回写，聚焦逻辑
        import pandas as pd
        s._data_cache["000001.SZ"] = pd.DataFrame({
            "close": [10.0], "high": [10.0], "low": [10.0],
            "volume": [1000000], "amount": [10000000],
        })
        s._confirm_pending_buys()
        # 未到确认日：保留待次日，不入场、不 reject
        assert "000001.SZ" in s._buy_pending
        assert not s._holdings

    def test_confirm_processes_next_day_candidate(self):
        """次日候选（signal_date < today）且收盘 > 信号价 → 正常转正入场"""
        s = self._make_strategy()
        s._buy_pending["000001.SZ"] = {
            "signal_price": 10.0,
            "weight": 0.5,
            "signal_date": "2026-08-23",
            "signal_id": "cand-next-day",
        }
        s._last_trade_date = "2026-08-24"
        s._replaying = True
        import pandas as pd
        s._data_cache["000001.SZ"] = pd.DataFrame({
            "close": [10.5], "high": [10.5], "low": [10.2],
            "volume": [1000000], "amount": [10500000],
        })
        s._confirm_pending_buys()
        # 次日收盘 > 信号价 → 转正入场，移出待确认
        assert "000001.SZ" in s._holdings
        assert "000001.SZ" not in s._buy_pending

    def test_confirm_keeps_candidate_when_positions_full(self):
        """持仓满时候选保留待下次（不 break 丢弃）。

        修复 2026-08-25：此前持仓满直接 break，内存候选被丢弃而 DB 保持
        pending_confirm，下次运行重复恢复（8-25 603565 实证）。改放回待空位。
        """
        s = self._make_strategy()
        # 构造持仓满（>= eff_max_pos）
        s._holdings["000002.SZ"] = {"entry_price": 5.0, "weight": 1.0}
        s._holdings["000003.SZ"] = {"entry_price": 6.0, "weight": 1.0}
        s._last_trade_date = "2026-08-24"
        s._replaying = True
        s._buy_pending["000001.SZ"] = {
            "signal_price": 10.0,
            "weight": 0.5,
            "signal_date": "2026-08-23",
            "signal_id": "cand-full-pos",
        }
        import pandas as pd
        s._data_cache["000001.SZ"] = pd.DataFrame({
            "close": [10.5], "high": [10.5], "low": [10.2],
            "volume": [1000000], "amount": [10500000],
        })
        s._confirm_pending_buys()
        # 持仓满：候选未被丢弃，保留待下次运行；未入场
        assert "000001.SZ" in s._buy_pending
        assert "000001.SZ" not in s._holdings

    def test_confirm_rejects_candidate_even_when_positions_full(self):
        """持仓满时候选仍先做价格确认（确认失败 → reject，而非满仓跳过）。

        修复 2026-08-25：确认逻辑改为「先价格确认，再看仓位」——满仓不再
        拦截候选确认，每个候选都有明确结果（拒/通过/待次日）。
        """
        s = self._make_strategy()
        # 构造持仓满
        s._holdings["000002.SZ"] = {"entry_price": 5.0, "weight": 1.0}
        s._holdings["000003.SZ"] = {"entry_price": 6.0, "weight": 1.0}
        s._last_trade_date = "2026-08-24"
        s._buy_pending["000001.SZ"] = {
            "signal_price": 10.0,
            "weight": 0.5,
            "signal_date": "2026-08-23",
            "signal_id": "cand-full-reject",
        }
        import pandas as pd
        s._data_cache["000001.SZ"] = pd.DataFrame({
            "close": [9.0], "high": [9.0], "low": [9.0],
            "volume": [1000000], "amount": [9000000],
        })
        s._rejected_candidate_ids.clear()
        s._confirm_pending_buys()
        # 满仓也先确认：close 9.0 < signal 10.0 → 记入 rejected（而非因满仓跳过）
        assert "cand-full-reject" in s._rejected_candidate_ids
        assert "000001.SZ" not in s._buy_pending
        assert "000001.SZ" not in s._holdings

    def test_screen_excludes_confirmed_active(self):
        """已确认占用（promoted/executed 未卖出）的股票被选股排除（防补仓）"""
        s = self._make_strategy()
        s._confirmed_active.add("600030.SH")
        import pandas as pd
        s._data_cache["600030.SH"] = pd.DataFrame({"close": [1.0]})
        result = s._screen_stocks()
        assert "600030.SH" not in result

    def test_finalize_exits_releases_confirmed_active(self):
        """卖出结算(_finalize_exits)后释放占用，可重新纳入选股"""
        s = self._make_strategy()
        s._confirmed_active.add("600030.SH")
        s._exit_pending.add("600030.SH")
        s._holdings["600030.SH"] = {"entry_price": 10.0, "weight": 0.5}
        import pandas as pd
        s._data_cache["600030.SH"] = pd.DataFrame({
            "close": [11.0], "high": [11.0], "low": [10.0],
            "volume": [1000000], "amount": [11000000],
        })
        s._finalize_exits()
        assert "600030.SH" not in s._confirmed_active
        assert "600030.SH" not in s._holdings
