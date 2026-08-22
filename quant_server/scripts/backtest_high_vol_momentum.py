# -*- coding: utf-8 -*-
"""
高波动动量轮动策略 — 信号级冒烟回测
=======================================
独立运行（不走完整 BacktestEngine），验证策略在真实行情上的信号生成闭环：
on_bar 缓存 → on_bar_batch_end 调仓/风控 → 信号 → 简化持仓模拟 → NAV。

执行: cd quant_server && .venv/Scripts/python.exe scripts/backtest_high_vol_momentum.py [start] [end]
默认区间: 2025-01-01 ~ 2026-08-07（含近 1.5 年，含 2025 牛熊切换）
验收（strategy-gates）: 至少 1 笔交易、无 NaN、收益率 ∈ [-95%, +500%]
"""
import asyncio
import logging
import sys
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 1_000_000.0
LOT = 100          # A股最小手数
START = "2025-01-01"
END = "2026-08-07"


class SmokePortfolio:
    """简化持仓模拟（入场当日收盘、离场次日开盘）"""

    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.cash = initial_capital
        self.holdings: Dict[str, Dict] = {}   # {code: {"qty": int, "cost": float}}
        self.pending_exits: List[Tuple[str, int]] = []  # [(code, qty)] 次日开盘成交

    def equity(self, prices: Dict[str, float]) -> float:
        mv = sum(h["qty"] * prices.get(c, h["cost"]) for c, h in self.holdings.items())
        return self.cash + mv

    def fill_pending_exits(self, prices: Dict[str, float]) -> None:
        """次日开盘成交待平仓"""
        for code, qty in self.pending_exits:
            price = prices.get(code, 0.0)
            if price <= 0:
                continue
            self.cash += qty * price
            h = self.holdings.get(code)
            if h:
                h["qty"] -= qty
                if h["qty"] <= 0:
                    self.holdings.pop(code, None)
        self.pending_exits.clear()

    def apply_signal(self, sig, prices: Dict[str, float], trade_date: str) -> None:
        """入场当日收盘成交；离场挂次日开盘"""
        code = sig.ts_code
        price = prices.get(code, 0.0)
        if price <= 0:
            return
        from modules.strategy.constants import SignalDirection
        if sig.direction == SignalDirection.LONG:
            # 按总权益 × 权重（与真实 Sizer 一致），并以可用现金封顶
            equity = self.equity(prices)
            amount = min(equity * getattr(sig, "weight", 0.1), self.cash)
            qty = int(amount / price / LOT) * LOT
            if qty > 0:
                cost = qty * price
                self.cash -= cost
                h = self.holdings.get(code)
                if h:
                    total_qty = h["qty"] + qty
                    h["cost"] = (h["cost"] * h["qty"] + cost) / total_qty
                    h["qty"] = total_qty
                else:
                    self.holdings[code] = {"qty": qty, "cost": price}
        elif sig.direction == SignalDirection.CLOSE_LONG:
            h = self.holdings.get(code)
            if h and h["qty"] > 0:
                self.pending_exits.append((code, h["qty"]))


async def _warmup_all_market(strategy, sf, end_date: date) -> int:
    """全市场 K 线预热 — 修复：脚本此前依赖引擎预热导致 _data_cache 恒空。

    与 StrategyManager._warmup_all_market 同口径（主板代码 + qfq 复权批量加载），
    差异：DataFrame 保留 trade_date 列（兼容本脚本 dates 提取与策略 _append_data concat）。
    预热截止 end_date（回测开始日），**不含未来数据**（避免回测未来函数）。
    """
    from sqlalchemy import text
    from shared.database.repositories.market.quote.stock_adj_factor_repo import (
        StockAdjFactorRepository,
    )

    lookback = int(getattr(strategy, "lookback_days", 250) or 250)
    start_d = end_date - timedelta(days=lookback * 2)

    async with sf() as session:
        r = await session.execute(text(
            "SELECT DISTINCT ts_code FROM stock_basic "
            "WHERE (ts_code LIKE '000%' OR ts_code LIKE '002%' OR ts_code LIKE '600%' "
            "   OR ts_code LIKE '601%' OR ts_code LIKE '603%' OR ts_code LIKE '605%')"
        ))
        codes = [row[0] for row in r.fetchall()]
        rows = await StockAdjFactorRepository(session).get_adjusted_daily_batch(
            symbols=codes, start_date=start_d, end_date=end_date, adj_type="qfq",
        )

        by_code: Dict[str, list] = {}
        for row in rows:
            by_code.setdefault(row["ts_code"], []).append(row)

        populated = 0
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
            strategy._data_cache[code] = df
            populated += 1
        return populated


async def run_smoke(start: str = START, end: str = END) -> None:
    from core.engines.types.entities import BarData
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

    from modules.strategy.strategies.rotation.high_vol_momentum_strategy import (
        HighVolMomentumStrategy,
    )

    import json, os
    params_override = json.loads(os.environ.get("HV_PARAMS", "{}"))
    strategy = HighVolMomentumStrategy(name="高波动动量轮动-冒烟", parameters=params_override)
    strategy._db_session_factory = sf
    strategy.initialize()  # 运行 on_init → 构建 universe
    await strategy.on_start()

    symbols = list(strategy.universe)
    logger.info(f"标的池: {len(symbols)}只")

    # ── 修复：预热 _data_cache（全市场 K 线，截止回测开始日，避免未来函数）──
    start_d = date.fromisoformat(start)
    warmed = await _warmup_all_market(strategy, sf, start_d)
    cache_rows = sum(len(df) for df in strategy._data_cache.values())
    logger.info(f"预热完成: {warmed} 只股票, 缓存 {cache_rows} 行")

    # 回测区间交易日（独立查询 index_daily，不依赖缓存——缓存只含 start 前数据）
    from sqlalchemy import text
    async with sf() as _sess:
        _r = await _sess.execute(text(
            "SELECT DISTINCT trade_date FROM index_daily "
            "WHERE ts_code = '000300.SH' AND trade_date BETWEEN :s AND :e ORDER BY trade_date"
        ), {"s": start_d, "e": date.fromisoformat(end)})
        dates = [str(row[0])[:10] for row in _r.fetchall()]
    if not dates:
        logger.error("回测区间无交易日数据: %s ~ %s", start, end)
        return
    logger.info(f"回测区间: {dates[0]} ~ {dates[-1]}, 共 {len(dates)} 个交易日")

    # 建立 日→symbol→bar 索引
    from collections import defaultdict
    daily_bars: Dict[str, Dict[str, BarData]] = defaultdict(dict)
    for code, df in strategy._data_cache.items():
        if "trade_date" not in df.columns or df.empty:
            continue
        for _, row in df.iterrows():
            td = str(row["trade_date"])[:10]
            daily_bars[td][code] = BarData(
                ts_code=code,
                period="daily",
                open=float(row.get("open", row["close"])),
                high=float(row.get("high", row["close"])),
                low=float(row.get("low", row["close"])),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
                amount=float(row.get("amount", 0.0)),
                trade_date=td,
            )

    portfolio = SmokePortfolio()
    nav_curve: List[Tuple[str, float]] = []
    total_signals = 0
    entries = 0
    exits = 0

    for td in dates:
        bars_today = daily_bars.get(td, {})
        if not bars_today:
            continue

        # 1. 次日开盘成交（前一日 exit 信号）
        prices_open = {c: b.open for c, b in bars_today.items()}
        portfolio.fill_pending_exits(prices_open)

        # 2. 推入当日 bar
        for code in symbols:
            bar = bars_today.get(code)
            if bar is not None:
                strategy.on_bar(bar)

        # 3. 批次结束 → 信号
        signals = strategy.on_bar_batch_end(td)
        if signals:
            total_signals += len(signals)

        # 4. 收盘价成交入场/挂离场
        prices_close = {c: b.close for c, b in bars_today.items()}
        for sig in signals:
            if sig.signal_type.value == "entry":
                entries += 1
            else:
                exits += 1
            portfolio.apply_signal(sig, prices_close, td)

        nav = portfolio.equity(prices_close)
        nav_curve.append((td, nav))

    await pool.close()

    # ---- 绩效汇总 ----
    navs = np.array([n for _, n in nav_curve])
    total_return = navs[-1] / INITIAL_CAPITAL - 1.0
    peak = np.maximum.accumulate(navs)
    max_dd = float(np.min(navs / peak - 1.0))
    has_nan = bool(np.isnan(navs).any())

    logger.info("=" * 60)
    logger.info(f"回测区间: {dates[0]} ~ {dates[-1]} | 交易日 {len(dates)}")
    logger.info(f"信号总数: {total_signals} (入场 {entries}, 离场 {exits})")
    logger.info(f"期末净值: {navs[-1]:,.0f} | 总收益: {total_return:.2%}")
    logger.info(f"最大回撤: {max_dd:.2%} | 含NaN: {has_nan}")
    logger.info(f"最终持仓: {list(portfolio.holdings.keys())}")
    logger.info("=" * 60)

    # 验收断言（strategy-gates）
    assert total_signals >= 1, "FAIL: 无交易信号"
    assert not has_nan, "FAIL: 净值含 NaN"
    assert -0.95 <= total_return <= 5.00, f"FAIL: 收益率越界 {total_return:.2%}"
    logger.info("✅ 冒烟回测通过：有交易、无 NaN、收益率在范围内")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    start = args[0] if len(args) > 0 else START
    end = args[1] if len(args) > 1 else END
    asyncio.run(run_smoke(start, end))
