# -*- coding: utf-8 -*-
"""跨市场策略：同一天 bar 重复入 `_data_cache` 不得影响打分。

## 被修复的问题（2026-09-21 实盘假信号）

框架预热（`strategy_manager._warmup_strategy`）的区间是 `end_date = today` ——
**当日行情已入库时，预热就包含当日**。随后当日日常驱动又通过 `on_bar` 推一遍当日 bar
→ 同一交易日在 `_data_cache` 里出现**两次**（`_flush_pending_rows` 原先只 `pd.concat`、不去重）。

危害：25 日动量窗口里多一根**零收益重复点** → `_calc_momentum_score` 的加权 log 回归
R² 被抬高。实测 2026-09-21 选出 `512660.SH` 就是靠这个：

    R² 0.356（干净） → 0.526（重复） → 越过 r2_threshold=0.47 → 假信号

触发条件（两者同时满足）：进程在**当日数据入库之后**启动（预热含当日）+ 当日有驱动。
旁证：09-17 同日两次驱动，预热 267 天（未含当日）→ score=0.93；
      预热 268 天（含当日）+ 再推一次 → score=0.80。

## 本文件守住三件事

1. `_flush_pending_rows` 对**同一批** pending 行去重（预热 + 驱动同批入缓存的情形）
2. 对**已入缓存**的行同样去重（同日二次驱动、无重启的情形）
3. **打分逐位不变**：重复喂当日 bar 与只喂一次得到完全相同的 score/raw/r2
   —— 这是能真正拦住该 bug 的断言（只断言"行数"会漏掉数值层面的污染）
"""
import math
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
    CrossMarketMomentumStrategy,
)

CODE = "512660.SH"
D0, D1 = "2026-09-10", "2026-09-11"
_N = 40          # > lookback_days(25)+1，保证可打分


def _seq_dates(n: int = _N):
    d = date(2026, 7, 1)
    out = []
    for _ in range(n):
        out.append(d.isoformat())
        d += timedelta(days=1)
    return out


#: 带轻微振荡的上升序列（保证上下行收益都存在 → `_trend_quality` 可算，不 fail-open）
_CLOSES = [100.0 * math.exp(0.004 * i) * (1.0 + 0.01 * math.sin(i)) for i in range(_N)]
_DATES = _seq_dates()


def _bar(td: str, close: float) -> SimpleNamespace:
    return SimpleNamespace(ts_code=CODE, trade_date=td, open=close, high=close,
                           low=close, close=close, volume=1e6, amount=close * 1e6)


def _feed(dup_last: bool = False) -> CrossMarketMomentumStrategy:
    """按日喂 bar；`dup_last=True` 时把最后一天再喂一次（复现预热含当日 + 当日驱动）。"""
    s = CrossMarketMomentumStrategy(name="DUP-测试")
    for td, c in zip(_DATES, _CLOSES):
        s.on_bar(_bar(td, c))
    if dup_last:
        s.on_bar(_bar(_DATES[-1], _CLOSES[-1]))
    s._flush_pending_rows()
    return s


class TestFlushDedupesTradeDate:
    """`_flush_pending_rows` 的去重语义。"""

    def test_dedupes_within_pending_batch(self):
        """同一批 pending 行里同一天出现两次 → 只留一行，且保留**后写入**的值。"""
        s = CrossMarketMomentumStrategy(name="DUP-测试")
        s._pending_rows[CODE] = [
            [D0, 1, 1, 1, 10.0, 1e6, 1e7],   # 预热那根
            [D0, 1, 1, 1, 11.0, 1e6, 1e7],   # 驱动那根（应胜出）
            [D1, 1, 1, 1, 12.0, 1e6, 1e7],
        ]
        s._flush_pending_rows()

        df = s._data_cache[CODE]
        assert list(df["trade_date"]) == [D0, D1]
        assert float(df.loc[df["trade_date"] == D0, "close"].iloc[0]) == 11.0

    def test_dedupes_against_existing_cache(self):
        """同日**二次驱动**（缓存已有该日）→ 不得变成两行。"""
        s = CrossMarketMomentumStrategy(name="DUP-测试")
        s._pending_rows[CODE] = [[D0, 1, 1, 1, 10.0, 1e6, 1e7]]
        s._flush_pending_rows()
        assert len(s._data_cache[CODE]) == 1

        s._pending_rows[CODE] = [[D0, 1, 1, 1, 10.5, 1e6, 1e7]]   # 同日再推一次
        s._flush_pending_rows()
        df = s._data_cache[CODE]
        assert list(df["trade_date"]) == [D0], "同一天不得出现两行"
        assert float(df["close"].iloc[0]) == 10.5

    def test_no_duplicate_leaves_rows_untouched(self):
        """无重复时行为不变（回测每日只推一次 → 走的就是这条路径）。"""
        s = _feed(dup_last=False)
        df = s._data_cache[CODE]
        assert list(df["trade_date"]) == _DATES
        assert [float(x) for x in df["close"].tolist()] == pytest.approx(_CLOSES)


class TestScoreUnaffectedByDuplicate:
    """重复喂当日 bar 不得改变任何打分——**这是能拦住该 bug 的断言**。"""

    def test_dup_does_not_change_score(self):
        clean = _feed(dup_last=False)
        dup = _feed(dup_last=True)
        assert len(dup._data_cache[CODE]) == len(_DATES), "缓存里当日应只有一行"

        m_clean = clean._score_candidate(CODE)
        m_dup = dup._score_candidate(CODE)
        assert m_clean is not None and m_dup is not None
        for key in ("score", "raw_score", "r2", "annualized"):
            assert m_dup[key] == pytest.approx(m_clean[key]), f"{key} 被重复 bar 改变"
        assert m_dup["passed_r2"] == m_clean["passed_r2"]

    def test_dup_does_not_change_selected_targets(self):
        clean, dup = _feed(dup_last=False), _feed(dup_last=True)

        def _targets(s):
            metrics = [m for m in (s._score_candidate(c) for c in [CODE]) if m]
            return [t["etf"] for t in s._select_targets(metrics)]

        assert _targets(dup) == _targets(clean)
