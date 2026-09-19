# -*- coding: utf-8 -*-
"""
高波动动量轮动 v7.1+T1 — 滚动起始日分析
==========================================
对多个起始日分别跑同一套策略（磁盘加载），统计真实分布：
单笔期望 / 胜率 / 盈亏比 / 最大回撤 / 总收益。

目的：坐实「单笔期望 ~+2.5%」是否撞运起始日的假象，支撑 GO/NO-GO 决策。

撮合：order_mode=open（买卖均次日开盘成交），含万1佣金 + 0.02% 滑点。

执行: cd quant_server && .venv/Scripts/python.exe scripts/backtest/rolling_start_analysis.py [start1,start2,...]
默认: 6 个起始日，覆盖牛/熊/震荡多段行情，固定结束 2026-09-04。
"""
import asyncio
import logging
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RESULTS_FILE = str(Path(__file__).resolve().parent.parent.parent / "logs" / "rolling_start_results.txt")


def _progress(msg: str) -> None:
    """进度输出：立即 flush 到 stdout + 追加写结果文件（防中断丢失）。"""
    line = f"{msg}"
    print(line, flush=True)
    try:
        with open(RESULTS_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
    except Exception:
        pass

INITIAL_CAPITAL = 1_000_000.0
LOT = 100
END = "2026-09-04"
COST = 0.0001 + 0.0002  # 万1佣金 + 0.02%滑点（单边）
DEFAULT_STARTS = ["2021-09-07", "2022-03-01", "2022-11-01", "2023-09-01", "2024-09-01", "2025-03-03"]


class RollingPortfolio:
    """order_mode=open 撮合：买卖均次日开盘成交，记录每笔平仓盈亏。"""

    def __init__(self, capital: float = INITIAL_CAPITAL):
        self.cash = capital
        self.holdings: Dict[str, Dict] = {}       # {code: {qty, entry_price, entry_date}}
        self.pending_entries: Dict[str, float] = {}  # {code: weight} 次日开盘买
        self.pending_exits: List[str] = []           # [code] 次日开盘卖
        self.closed_trades: List[Dict] = []          # 平仓记录

    def fill_pending(self, prices_open: Dict[str, float], td: str) -> None:
        # 先平仓（停牌/无价则保留持仓，次日重试，避免凭空蒸发市值）
        still_pending = []
        for code in self.pending_exits:
            price = prices_open.get(code, 0.0)
            h = self.holdings.get(code)
            if h and price > 0 and h["entry_price"] > 0:
                pnl = (price - h["entry_price"]) / h["entry_price"]
                self.closed_trades.append({
                    "code": code, "pnl_pct": pnl,
                    "entry_date": h["entry_date"], "exit_date": td,
                })
                self.cash += h["qty"] * price * (1.0 - COST)
                self.holdings.pop(code, None)
            elif h:
                still_pending.append(code)
        self.pending_exits = still_pending

        # 再开仓
        for code, weight in self.pending_entries.items():
            if code in self.holdings:
                continue  # 防重复买入
            price = prices_open.get(code, 0.0)
            if price <= 0:
                continue
            mv = sum(h["qty"] * prices_open.get(c, h["entry_price"]) for c, h in self.holdings.items())
            equity = self.cash + mv
            amount = min(equity * weight, self.cash)
            qty = int(amount / price / LOT) * LOT
            if qty <= 0:
                continue
            self.cash -= qty * price * (1.0 + COST)
            self.holdings[code] = {"qty": qty, "entry_price": price, "entry_date": td}
        self.pending_entries.clear()

    def equity(self, prices: Dict[str, float]) -> float:
        mv = sum(h["qty"] * prices.get(c, h["entry_price"]) for c, h in self.holdings.items())
        return self.cash + mv

    def apply_signal(self, sig) -> None:
        from modules.strategy.constants import SignalDirection
        if sig.direction == SignalDirection.LONG:
            w = float(getattr(sig, "weight", 0.0) or 0.0)
            if sig.ts_code not in self.holdings and sig.ts_code not in self.pending_entries:
                self.pending_entries[sig.ts_code] = w
        elif sig.direction == SignalDirection.CLOSE_LONG:
            if sig.ts_code in self.holdings and sig.ts_code not in self.pending_exits:
                self.pending_exits.append(sig.ts_code)


def compute_stats(trades: List[Dict], navs: np.ndarray, total_return: float) -> Dict:
    n = len(trades)
    pnls = np.array([t["pnl_pct"] for t in trades], dtype=np.float64)
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]
    avg_win = float(np.mean(wins)) if len(wins) else 0.0
    avg_loss = float(np.mean(losses)) if len(losses) else 0.0
    win_rate = float(len(wins) / n) if n else 0.0
    payoff = float(avg_win / abs(avg_loss)) if avg_loss < 0 else float("inf")
    expectancy = float(np.mean(pnls)) if n else 0.0
    peak = np.maximum.accumulate(navs)
    max_dd = float(np.min(navs / peak - 1.0)) if len(navs) else 0.0
    return {
        "trades": n,
        "expectancy_pct": expectancy * 100.0,
        "win_rate_pct": win_rate * 100.0,
        "payoff": payoff,
        "avg_win_pct": avg_win * 100.0,
        "avg_loss_pct": avg_loss * 100.0,
        "max_dd_pct": max_dd * 100.0,
        "total_return_pct": total_return * 100.0,
    }


async def load_full_data(sf, codes: List[str], earliest: date, end: date) -> Dict[str, pd.DataFrame]:
    from shared.database.repositories.market.quote.stock_adj_factor_repo import (
        StockAdjFactorRepository,
    )
    warmup_start = earliest - timedelta(days=500)
    async with sf() as session:
        rows = await StockAdjFactorRepository(session).get_adjusted_daily_batch(
            symbols=codes, start_date=warmup_start, end_date=end, adj_type="qfq",
        )
    by_code: Dict[str, list] = defaultdict(list)
    for r in rows:
        by_code[r["ts_code"]].append(r)
    full: Dict[str, pd.DataFrame] = {}
    for code, recs in by_code.items():
        df = pd.DataFrame([{
            "trade_date": str(r["trade_date"])[:10],
            "open": float(r["open"] or 0),
            "high": float(r["high"] or 0),
            "low": float(r["low"] or 0),
            "close": float(r["close"] or 0),
            "volume": float(r["volume"] or 0),
            "amount": float(r["amount"] or 0),
        } for r in recs]).sort_values("trade_date").reset_index(drop=True)
        full[code] = df
    return full


async def run_single(sf, strategy_cls, full: Dict[str, pd.DataFrame], start: date,
                     dates: List[str], symbols: List[str]) -> Dict:
    from core.engines.types.entities import BarData

    strategy = strategy_cls(name=f"rolling-{start}")
    strategy._db_session_factory = sf
    strategy.initialize()
    await strategy.on_start()
    # 2026-09-19：**降级门禁** —— regime 指数不可用时策略退化为「只持防御标的」，
    # 而冒烟门对满仓国债免疫 → 研究路径必须硬失败，不得静默产出不可比结果。
    if getattr(strategy, "_index_cache_ok", True) is False:
        raise RuntimeError(
            f"regime 指数缓存不可用（_index_cache_ok=False，起始日 {start}）→ 本臂会退化为"
            f"『只持防御标的』，该滚动起始日的结果不可作为口径；"
            f"请检查 index_daily 覆盖率与 DB 连接后重跑"
        )

    start_s = start.isoformat()
    # warmup：截止 start 前（视图切片 + 行指针，避免逐 bar 创建 DataFrame）
    dts_list: Dict[str, list] = {}
    pos: Dict[str, int] = {}
    for code, df in full.items():
        dts = df["trade_date"].tolist()
        dts_list[code] = dts
        idx = -1
        for i in range(len(dts) - 1, -1, -1):
            if dts[i] < start_s:
                idx = i
                break
        pos[code] = idx
        if idx >= 0:
            strategy._data_cache[code] = df.iloc[:idx + 1]

    # 构建 backtest 日索引（>= start）
    daily_bars: Dict[str, Dict[str, BarData]] = defaultdict(dict)
    for code, df in full.items():
        for _, row in df[df["trade_date"] >= start_s].iterrows():
            td = str(row["trade_date"])[:10]
            daily_bars[td][code] = BarData(
                ts_code=code, period="daily",
                open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row["volume"]), amount=float(row["amount"]), trade_date=td,
            )

    portfolio = RollingPortfolio()
    nav_curve: List[float] = []
    for td in dates:
        bars_today = daily_bars.get(td, {})
        if not bars_today:
            continue
        prices_open = {c: b.open for c, b in bars_today.items()}
        portfolio.fill_pending(prices_open, td)
        # 推进行指针到当日（O(1) 摊销，替代逐 bar on_bar —— v7.1 _append_data 极慢）
        for code in bars_today:
            strategy._bar_dates[code] = td
            dts = dts_list[code]
            p = pos[code] + 1
            while p < len(dts) and dts[p] <= td:
                p += 1
            pos[code] = p - 1
            strategy._data_cache[code] = full[code].iloc[:p]
        signals = strategy.on_bar_batch_end(td)
        prices_close = {c: b.close for c, b in bars_today.items()}
        for sig in signals:
            portfolio.apply_signal(sig)
        nav_curve.append(portfolio.equity(prices_close))

    navs = np.array(nav_curve)
    total_return = navs[-1] / INITIAL_CAPITAL - 1.0 if len(navs) else 0.0
    return compute_stats(portfolio.closed_trades, navs, total_return)


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool
    from modules.strategy.strategies.rotation.high_vol_momentum_strategy import HighVolMomentumStrategy

    args = [a for a in sys.argv[1:] if a]
    starts = [date.fromisoformat(s) for s in (args or DEFAULT_STARTS)]
    end = date.fromisoformat(END)

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    # 用临时策略加载 universe + 交易日历
    tmp = HighVolMomentumStrategy(name="tmp")
    tmp._db_session_factory = sf
    tmp.initialize()
    await tmp.on_start()
    symbols = list(tmp.universe)

    from sqlalchemy import text
    async with sf() as _s:
        _r = await _s.execute(text(
            "SELECT DISTINCT trade_date FROM index_daily "
            "WHERE ts_code='000300.SH' AND trade_date BETWEEN :s AND :e ORDER BY trade_date"
        ), {"s": starts[0], "e": end})
        all_dates = [str(row[0])[:10] for row in _r.fetchall()]

    full = await load_full_data(sf, symbols, starts[0], end)
    _progress(f"全市场数据加载: {len(full)} 只股票, 起始日 {len(starts)} 个")

    header = f"{'起始日':<12}{'笔数':>5}{'单笔期望':>10}{'胜率':>8}{'盈亏比':>8}{'平均盈':>9}{'平均亏':>9}{'回撤':>8}{'总收益':>10}"
    _progress("=" * 100)
    _progress(header)
    _progress("-" * 100)

    results: List[Tuple[str, Dict]] = []
    for s in starts:
        dates = [d for d in all_dates if d >= s.isoformat()]
        stats = await run_single(sf, HighVolMomentumStrategy, full, s, dates, symbols)
        results.append((s.isoformat(), stats))
        _progress(
            f"{s.isoformat():<12}{stats['trades']:>5}{stats['expectancy_pct']:>9.2f}%{stats['win_rate_pct']:>7.1f}%"
            f"{stats['payoff']:>8.2f}{stats['avg_win_pct']:>8.1f}%{stats['avg_loss_pct']:>8.1f}%"
            f"{stats['max_dd_pct']:>7.1f}%{stats['total_return_pct']:>9.1f}%"
        )

    await pool.close()

    # 汇总分布
    _progress("-" * 100)
    exp = [st["expectancy_pct"] for _, st in results]
    wr = [st["win_rate_pct"] for _, st in results]
    po = [st["payoff"] for _, st in results]
    ret = [st["total_return_pct"] for _, st in results]
    dd = [st["max_dd_pct"] for _, st in results]
    # 修复 2026-09-12：补下四分位（P25）。项目标准要求看「中位数 / 下四分位」，
    # 而此前只报 min/中位/max；_rolling_start_cross_market.py 已有 P25，口径不一致。
    _progress(f"单笔期望分布: min={min(exp):.2f}% P25={np.percentile(exp,25):.2f}% 中位={np.median(exp):.2f}% max={max(exp):.2f}%")
    _progress(f"胜率分布:     min={min(wr):.1f}% P25={np.percentile(wr,25):.1f}% 中位={np.median(wr):.1f}% max={max(wr):.1f}%")
    _progress(f"盈亏比分布:   min={min(po):.2f} P25={np.percentile(po,25):.2f} 中位={np.median(po):.2f} max={max(po):.2f}")
    _progress(f"总收益分布:   min={min(ret):.1f}% P25={np.percentile(ret,25):.1f}% 中位={np.median(ret):.1f}% max={max(ret):.1f}%")
    _progress(f"回撤分布:     min={min(dd):.1f}% P25={np.percentile(dd,25):.1f}% 中位={np.median(dd):.1f}% max={max(dd):.1f}%")
    _progress("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
