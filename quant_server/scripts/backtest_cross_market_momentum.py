# -*- coding: utf-8 -*-
"""
跨市场动量避险轮动策略 — 信号级冒烟回测
=========================================
独立运行（不走完整 BacktestEngine），验证策略信号生成闭环 + 简化撮合 + NAV。

撮合模型：order_mode=open → 买卖信号均「次日开盘成交」（对齐实盘 T+1，比 high_vol
冒烟的「入场当日收盘」更贴近真实引擎）。

执行: cd quant_server && .venv/Scripts/python.exe scripts/backtest_cross_market_momentum.py [start] [end]
默认区间: 2021-01-01 ~ 2026-08-07（跨 A股牛熊切换 + 海外/商品多轮行情）
验收（strategy-gates）: 至少 1 笔交易、无 NaN、收益率 ∈ [-95%, +500%]
"""
import asyncio
import logging
import sys
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 1_000_000.0
LOT = 100
START = "2021-01-01"
END = "2026-08-07"
COMMISSION_RATE = 0.0001   # 万1（ETF 佣金，单边）
SLIPPAGE = 0.0002          # 0.02%（流动性 ETF 单边滑点）
COST_PER_SIDE = COMMISSION_RATE + SLIPPAGE


class SmokePortfolio:
    """简化持仓模拟：买卖均次日开盘成交（order_mode=open）。"""

    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.cash = initial_capital
        self.holdings: Dict[str, Dict] = {}
        self.pending_entries: List[Tuple[str, float]] = []  # [(code, weight)] 次日开盘成交
        self.pending_exits: List[Tuple[str, int]] = []       # [(code, qty)] 次日开盘成交

    def equity(self, prices: Dict[str, float]) -> float:
        mv = sum(h["qty"] * prices.get(c, h["cost"]) for c, h in self.holdings.items())
        return self.cash + mv

    def fill_pending(self, prices_open: Dict[str, float]) -> None:
        """次日开盘：先成交离场（回笼现金），再成交入场（用可用现金）。"""
        for code, qty in self.pending_exits:
            price = prices_open.get(code, 0.0)
            if price <= 0:
                continue
            self.cash += qty * price * (1.0 - COST_PER_SIDE)
            h = self.holdings.get(code)
            if h:
                h["qty"] -= qty
                if h["qty"] <= 0:
                    self.holdings.pop(code, None)
        self.pending_exits.clear()

        for code, weight in self.pending_entries:
            price = prices_open.get(code, 0.0)
            if price <= 0:
                continue
            mv = sum(h["qty"] * prices_open.get(c, h["cost"]) for c, h in self.holdings.items())
            equity = self.cash + mv
            amount = min(equity * weight, self.cash)
            qty = int(amount / price / LOT) * LOT
            if qty <= 0:
                continue
            self.cash -= qty * price * (1.0 + COST_PER_SIDE)
            h = self.holdings.get(code)
            if h:
                total_qty = h["qty"] + qty
                h["cost"] = (h["cost"] * h["qty"] + qty * price) / total_qty
                h["qty"] = total_qty
            else:
                self.holdings[code] = {"qty": qty, "cost": price}
        self.pending_entries.clear()

    def apply_signal(self, sig, prices_close: Dict[str, float]) -> None:
        from modules.strategy.constants import SignalDirection
        if sig.direction == SignalDirection.LONG:
            self.pending_entries.append((sig.ts_code, float(getattr(sig, "weight", 0.0) or 0.0)))
        elif sig.direction == SignalDirection.CLOSE_LONG:
            h = self.holdings.get(sig.ts_code)
            if h and h["qty"] > 0:
                self.pending_exits.append((sig.ts_code, h["qty"]))


class _BrokerPos:
    """对账用最小持仓对象（只暴露 quantity）。"""

    def __init__(self, quantity: int):
        self.quantity = quantity


async def _load_data(strategy, sf, start: date, end: date):
    """加载 ETF 前复权日线，按日期切分：warmup(<start) 注入 _data_cache，backtest(>=start) 建索引。"""
    from shared.database.repositories.market.basic.etf_repo import ETFRepository

    symbols = list(strategy.universe)
    warmup_start = start - timedelta(days=500)
    async with sf() as session:
        rows = await ETFRepository(session).get_etf_adjusted_daily_batch(
            symbols=symbols, start_date=warmup_start, end_date=end,
        )

    by_code: Dict[str, list] = defaultdict(list)
    for r in rows:
        by_code[r["ts_code"]].append(r)

    start_s = start.isoformat()
    daily_bars: Dict[str, Dict[str, "BarData"]] = defaultdict(dict)
    populated = 0
    from core.engines.types.entities import BarData

    for code, recs in by_code.items():
        if len(recs) < 2:
            continue
        df = pd.DataFrame([{
            "trade_date": str(r["trade_date"])[:10],
            "open": float(r["open"] or 0),
            "high": float(r["high"] or 0),
            "low": float(r["low"] or 0),
            "close": float(r["close"] or 0),
            "volume": float(r["volume"] or 0),
            "amount": float(r["amount"] or 0),
        } for r in recs])
        df = df.sort_values("trade_date").reset_index(drop=True)

        warmup_df = df[df["trade_date"] < start_s]
        if len(warmup_df) > 0:
            strategy._data_cache[code] = warmup_df.reset_index(drop=True)

        for _, row in df[df["trade_date"] >= start_s].iterrows():
            td = str(row["trade_date"])[:10]
            daily_bars[td][code] = BarData(
                ts_code=code, period="daily",
                open=float(row.get("open", row["close"])),
                high=float(row.get("high", row["close"])),
                low=float(row.get("low", row["close"])),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
                amount=float(row.get("amount", 0.0)),
                trade_date=td,
            )
        populated += 1
    return populated, daily_bars


async def run_smoke(start: str = START, end: str = END) -> None:
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        ok = await pool.initialize()
        if not ok:
            logger.error("数据库连接池初始化失败")
            return
        sf = pool.get_session_factory()

    from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
        CrossMarketMomentumStrategy,
    )

    import json, os
    params_override = json.loads(os.environ.get("CM_PARAMS", "{}"))
    strategy = CrossMarketMomentumStrategy(name="跨市场动量避险-冒烟", parameters=params_override)
    strategy._db_session_factory = sf
    strategy.initialize()
    await strategy.on_start()

    # 注入最小 context（positions 对账用），模拟真实引擎的 broker 持仓反馈
    from types import SimpleNamespace
    strategy.context = SimpleNamespace(
        positions={}, total_assets=INITIAL_CAPITAL, available_capital=INITIAL_CAPITAL,
    )

    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    populated, daily_bars = await _load_data(strategy, sf, start_d, end_d)
    cache_rows = sum(len(df) for df in strategy._data_cache.values())
    logger.info(f"数据加载: {populated} 只 ETF, 预热 {cache_rows} 行, 回测 bar 天数 {len(daily_bars)}")

    # 回测区间交易日
    from sqlalchemy import text
    async with sf() as _sess:
        _r = await _sess.execute(text(
            "SELECT DISTINCT trade_date FROM index_daily "
            "WHERE ts_code = '000300.SH' AND trade_date BETWEEN :s AND :e ORDER BY trade_date"
        ), {"s": start_d, "e": end_d})
        dates = [str(row[0])[:10] for row in _r.fetchall()]
    if not dates:
        logger.error("回测区间无交易日数据: %s ~ %s", start, end)
        await pool.close()
        return
    logger.info(f"回测区间: {dates[0]} ~ {dates[-1]}, 共 {len(dates)} 个交易日")

    portfolio = SmokePortfolio()
    nav_curve: List[Tuple[str, float]] = []
    total_signals = 0
    entries = 0
    exits = 0
    weak_days = 0
    invested_days = 0
    candidate_days = 0
    defensive_days = 0
    empty_days = 0
    def_etf = strategy.defensive_etf
    symbols = list(strategy.universe)

    for td in dates:
        bars_today = daily_bars.get(td, {})
        if not bars_today:
            continue

        # 1. 次日开盘成交（前一日买卖信号）
        prices_open = {c: b.open for c, b in bars_today.items()}
        portfolio.fill_pending(prices_open)

        # 1.5 同步 context.positions（broker 实际持仓），供策略 _reconcile_holdings 对账
        strategy.context.positions = {
            c: _BrokerPos(h["qty"]) for c, h in portfolio.holdings.items() if h["qty"] > 0
        }
        strategy.context.total_assets = portfolio.equity(prices_open)
        strategy.context.available_capital = portfolio.cash

        # 2. 推入当日 bar
        for code in symbols:
            bar = bars_today.get(code)
            if bar is not None:
                strategy.on_bar(bar)

        # 3. 批次结束 → 信号
        signals = strategy.on_bar_batch_end(td)
        if signals:
            total_signals += len(signals)

        # 4. 记录信号（挂次日开盘）
        prices_close = {c: b.close for c, b in bars_today.items()}
        for sig in signals:
            if sig.signal_type.value == "entry":
                entries += 1
            else:
                exits += 1
            portfolio.apply_signal(sig, prices_close)

        nav = portfolio.equity(prices_close)
        nav_curve.append((td, nav))
        if strategy._is_weak:
            weak_days += 1
        if portfolio.holdings:
            invested_days += 1
        hkeys = set(portfolio.holdings.keys())
        if hkeys == {def_etf}:
            defensive_days += 1
        elif hkeys:
            candidate_days += 1
        else:
            empty_days += 1

    await pool.close()

    navs = np.array([n for _, n in nav_curve])
    if navs.size == 0:
        logger.error("净值曲线为空")
        return
    total_return = navs[-1] / INITIAL_CAPITAL - 1.0
    peak = np.maximum.accumulate(navs)
    max_dd = float(np.min(navs / peak - 1.0))
    has_nan = bool(np.isnan(navs).any())

    logger.info("=" * 60)
    logger.info(f"回测区间: {dates[0]} ~ {dates[-1]} | 交易日 {len(dates)}")
    logger.info(f"信号总数: {total_signals} (入场 {entries}, 离场 {exits})")
    logger.info(f"期末净值: {navs[-1]:,.0f} | 总收益: {total_return:.2%}")
    logger.info(f"最大回撤: {max_dd:.2%} | 含NaN: {has_nan}")
    logger.info(f"走弱期天数: {weak_days}/{len(nav_curve)} ({weak_days/len(nav_curve):.0%}) | 持仓天数: {invested_days}/{len(nav_curve)} ({invested_days/len(nav_curve):.0%})")
    logger.info(f"状态占比: 候选ETF {candidate_days}d / 防御国债 {defensive_days}d / 空仓 {empty_days}d")
    logger.info(f"最终持仓: {list(portfolio.holdings.keys())}")
    logger.info("=" * 60)

    assert total_signals >= 1, "FAIL: 无交易信号"
    assert not has_nan, "FAIL: 净值含 NaN"
    assert -0.95 <= total_return <= 5.00, f"FAIL: 收益率越界 {total_return:.2%}"
    logger.info("✅ 冒烟回测通过：有交易、无 NaN、收益率在范围内")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    start = args[0] if len(args) > 0 else START
    end = args[1] if len(args) > 1 else END
    asyncio.run(run_smoke(start, end))
