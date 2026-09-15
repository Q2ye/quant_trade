# -*- coding: utf-8 -*-
"""cross_market 策略 — 滚动起始日分析（验证单起始日 209.02% 是否撞运）。

复用冒烟脚本的 SmokePortfolio（先卖后买、order_mode=open），对多个起始日分别回测，
统计总收益/回撤的分布（中位数/下四分位/范围），判断路径依赖强度。

执行: cd quant_server && .venv/Scripts/python.exe scripts/backtest/_rolling_start_cross_market.py [start1,start2,...]
默认: 12 个起始日，覆盖牛/熊/震荡，固定结束 2026-09-08。
"""
import asyncio
import logging
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

from backtest_cross_market_momentum import SmokePortfolio, _BrokerPos, INITIAL_CAPITAL  # noqa: E402

END = "2026-09-08"
DEFAULT_STARTS = [
    "2021-09-09", "2021-11-01", "2022-01-04", "2022-03-01",
    "2022-06-01", "2022-09-01", "2022-11-01", "2023-03-01",
    "2023-09-01", "2024-03-01", "2024-09-01", "2025-03-03",
]


def _p(msg: str) -> None:
    print(msg, flush=True)


async def load_etf_data(sf, symbols, earliest: date, end: date):
    from shared.database.repositories.market.basic.etf_repo import ETFRepository
    warmup_start = earliest - timedelta(days=500)
    async with sf() as session:
        rows = await ETFRepository(session).get_etf_adjusted_daily_batch(
            symbols=symbols, start_date=warmup_start, end_date=end,
        )
    by_code = defaultdict(list)
    for r in rows:
        by_code[r["ts_code"]].append(r)
    full = {}
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


async def run_single(strategy_cls, sf, full, start: date, dates, symbols):
    from core.engines.types.entities import BarData

    strategy = strategy_cls(name=f"rolling-{start}")
    strategy._db_session_factory = sf
    strategy.initialize()
    await strategy.on_start()
    strategy.context = SimpleNamespace(
        positions={}, total_assets=INITIAL_CAPITAL, available_capital=INITIAL_CAPITAL,
    )

    start_s = start.isoformat()
    # warmup 切片 + 行指针
    dts_list = {}
    pos = {}
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

    # 构建回测日 bar 索引（>= start）
    daily_bars = defaultdict(dict)
    for code, df in full.items():
        for _, row in df[df["trade_date"] >= start_s].iterrows():
            td = str(row["trade_date"])[:10]
            daily_bars[td][code] = BarData(
                ts_code=code, period="daily",
                open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row["volume"]), amount=float(row["amount"]), trade_date=td,
            )

    portfolio = SmokePortfolio()
    navs = []
    for td in dates:
        bars_today = daily_bars.get(td, {})
        if not bars_today:
            continue
        prices_open = {c: b.open for c, b in bars_today.items()}
        portfolio.fill_pending(prices_open)
        # 同步 context（cross_market _make_exit_signal 用 broker 实际持仓数量）
        strategy.context.positions = {
            c: _BrokerPos(h["qty"]) for c, h in portfolio.holdings.items() if h["qty"] > 0
        }
        strategy.context.total_assets = portfolio.equity(prices_open)
        strategy.context.available_capital = portfolio.cash
        # 行指针推进 _data_cache 到当日
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
            portfolio.apply_signal(sig, prices_close)
        navs.append(portfolio.equity(prices_close))

    navs = np.array(navs)
    tr = navs[-1] / INITIAL_CAPITAL - 1.0 if len(navs) else 0.0
    peak = np.maximum.accumulate(navs)
    mdd = float(np.min(navs / peak - 1.0)) if len(navs) else 0.0
    return tr * 100.0, mdd * 100.0


async def main():
    from shared.database.session.connection_pool import get_connection_pool
    from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
        CrossMarketMomentumStrategy,
    )

    args = [a for a in sys.argv[1:] if a]
    starts = [date.fromisoformat(s) for s in (args or DEFAULT_STARTS)]
    end = date.fromisoformat(END)

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    tmp = CrossMarketMomentumStrategy(name="tmp")
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
        all_dates = [str(x[0])[:10] for x in _r.fetchall()]

    full = await load_etf_data(sf, symbols, starts[0], end)
    _p(f"ETF 数据加载: {len(full)} 只, 起始日 {len(starts)} 个")

    _p(f"{'起始日':<12}{'总收益':>10}{'回撤':>9}")
    _p("-" * 34)
    results = []
    for s in starts:
        dates = [d for d in all_dates if d >= s.isoformat()]
        tr, mdd = await run_single(CrossMarketMomentumStrategy, sf, full, s, dates, symbols)
        results.append((s.isoformat(), tr, mdd))
        _p(f"{s.isoformat():<12}{tr:>9.1f}%{mdd:>8.1f}%")

    await pool.close()

    rets = np.array([tr for _, tr, _ in results])
    mdds = np.array([mdd for _, _, mdd in results])
    _p("-" * 34)
    _p(f"总收益分布: min={rets.min():.1f}% 下四分={np.percentile(rets,25):.1f}% 中位={np.median(rets):.1f}% 上四分={np.percentile(rets,75):.1f}% max={rets.max():.1f}%")
    _p(f"回撤分布:   min={mdds.min():.1f}% 中位={np.median(mdds):.1f}% max={mdds.max():.1f}%")
    _p(f"收益<0 的起始日数: {int((rets < 0).sum())}/{len(rets)}")
    _p("=" * 34)


asyncio.run(main())
