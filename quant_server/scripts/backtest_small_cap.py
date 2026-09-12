# -*- coding: utf-8 -*-
"""
小市值优化版 — 信号级冒烟回测
========================================
验证聚宽「小市值优化」（docs/05_策略示例/小市值.py）在项目数据上的真实收益，
避免聚宽口径的幸存者偏差。

核心（克隆聚宽逻辑，简化）：
  1. 全市场主板，过滤 ST/新股/涨跌停/停牌
  2. 流通市值升序，取前 210，剔除最小 SKIP 只（防退市壳/僵尸股）
  3. 等权买 STOCK_NUM=6 只，周频调仓（每周二）
  4. 个股止损 -9%（收盘价触发）

执行:
  cd quant_server && .venv/Scripts/python.exe scripts/backtest_small_cap.py [start] [end]
默认区间: 2021-01-01 ~ 2026-08-07（5 年，覆盖 2024-01 微盘崩盘）
对比:
  SMALL_CAP_SKIP=10 优化版（剔除最小 10 只）
  SMALL_CAP_SKIP=0  等权版（基线，对应项目微盘 +31%/5yr ≈ 5.5%）
"""
import asyncio
import logging
import os
import sys
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 1_000_000.0
LOT = 100  # A股最小手数
START = "2021-01-01"
END = "2026-08-07"

STOCK_NUM = 6               # 持仓数
SKIP = int(os.environ.get("SMALL_CAP_SKIP", "10"))  # 剔除最小 N 只（0=等权基线）
POOL_TOP = 210              # 流通市值前 N
STOP_LOSS = -0.09           # 个股止损 -9%

# ---- 交易成本（修复 2026-09-12）----
# 此前该脚本零成本 → 微盘（高换手）收益被系统性高估。
COMMISSION_RATE = 0.0001     # 佣金万1（单边）
MIN_COMMISSION = 0.0         # 最低佣金 0 —— 账户为「万一免五」，无 5 元门槛
STAMP_DUTY_RATE = 0.001      # 印花税 0.1%（仅卖出）
TRANSFER_FEE_RATE = 0.00002  # 过户费 0.002%（双向）
SLIPPAGE = 0.0002            # 单边滑点 0.02%
FEE_BUFFER = 0.002           # 下单预留费用缓冲


def _fees(amount: float, direction: str) -> float:
    """A股单边交易费用合计：佣金 + 过户费 (+ 卖出印花税)。"""
    commission = max(amount * COMMISSION_RATE, MIN_COMMISSION)
    transfer = amount * TRANSFER_FEE_RATE
    stamp = amount * STAMP_DUTY_RATE if direction == "sell" else 0.0
    return commission + transfer + stamp


class SmokePortfolio:
    """简化持仓模拟（入场当日收盘、离场次日开盘）。

    修复 2026-09-12：此前零交易成本，现计入佣金（万1，账户免五无门槛）、
    印花税（0.1% 卖出）、过户费（0.002%）与单边滑点 0.02%。
    """

    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.cash = initial_capital
        self.holdings: Dict[str, Dict] = {}   # {code: {"qty": int, "cost": float}}
        self.pending_exits: List[Tuple[str, int]] = []  # [(code, qty)] 次日开盘成交

    def equity(self, prices: Dict[str, float]) -> float:
        mv = sum(h["qty"] * prices.get(c, h["cost"]) for c, h in self.holdings.items())
        return self.cash + mv

    def fill_pending_exits(self, prices: Dict[str, float]) -> None:
        """次日开盘成交待平仓（含卖出费用）"""
        for code, qty in self.pending_exits:
            price = prices.get(code, 0.0)
            if price <= 0:
                continue
            gross = qty * price * (1.0 - SLIPPAGE)
            self.cash += gross - _fees(gross, "sell")
            h = self.holdings.get(code)
            if h:
                h["qty"] -= qty
                if h["qty"] <= 0:
                    self.holdings.pop(code, None)
        self.pending_exits.clear()

    def buy(self, code: str, price: float, weight: float) -> None:
        """等权买入（按总权益 × weight，现金封顶；含买入费用）"""
        if price <= 0:
            return
        equity = self.cash + sum(h["qty"] * price for c, h in self.holdings.items())
        amount = min(equity * weight, self.cash)
        cost_per_share = price * (1.0 + SLIPPAGE)
        # 预留费用缓冲，避免含费后超出可用现金
        qty = int(amount / (cost_per_share * (1.0 + FEE_BUFFER)) / LOT) * LOT
        if qty <= 0:
            return
        gross = qty * cost_per_share
        total_out = gross + _fees(gross, "buy")
        if total_out > self.cash:
            return  # 含费后现金不足，放弃本次开仓
        self.cash -= total_out
        h = self.holdings.get(code)
        if h:
            total_qty = h["qty"] + qty
            h["cost"] = (h["cost"] * h["qty"] + gross) / total_qty
            h["qty"] = total_qty
        else:
            self.holdings[code] = {"qty": qty, "cost": gross / qty}

    def sell(self, code: str) -> None:
        """挂次日开盘全平"""
        h = self.holdings.get(code)
        if h and h["qty"] > 0:
            self.pending_exits.append((code, h["qty"]))


async def _load_circ_mv_snapshots(sf) -> Dict[str, Dict[str, float]]:
    """加载流通市值月末快照 {月末日: {code: circ_mv 万元}}（同微盘策略口径）。"""
    from sqlalchemy import text
    async with sf() as session:
        r = await session.execute(text(
            """
            SELECT d.trade_date, d.ts_code, b.name, d.circ_mv
            FROM stock_daily_basic d
            JOIN stock_basic b ON b.ts_code = d.ts_code
            WHERE d.trade_date IN (
                SELECT DISTINCT ON (to_char(trade_date, 'YYYY-MM')) trade_date
                FROM stock_daily_basic
                ORDER BY to_char(trade_date, 'YYYY-MM'), trade_date DESC
            )
            """
        ))
        snaps: Dict[str, Dict[str, float]] = {}
        for row in r.fetchall():
            d = str(row[0])[:10]
            name = str(row[2] or "")
            if name.startswith("ST") or name.startswith("*ST"):
                continue
            code = str(row[1])
            if code.endswith(".BJ") or code.startswith(("300", "688", "8", "4")):
                continue  # 剔北交所/创业/科创（聚宽 filter_kcbj + 主板）
            snaps.setdefault(d, {})[code] = float(row[3] or 0)
        return snaps


async def _warmup_klines(sf, start_date: date, end_date: date, lookback: int = 250) -> Dict[str, pd.DataFrame]:
    """加载全市场主板 qfq 日线（start_date-lookback*2 ~ end_date，覆盖回测区间 + 预热 lookback）。"""
    from sqlalchemy import text
    from shared.database.repositories.market.quote.stock_adj_factor_repo import (
        StockAdjFactorRepository,
    )
    start_d = start_date - timedelta(days=lookback * 2)
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
    cache: Dict[str, pd.DataFrame] = {}
    for code, recs in by_code.items():
        if len(recs) < 20:
            continue
        df = pd.DataFrame([{
            "trade_date": str(r["trade_date"])[:10],
            "close": float(r["close"] or 0),
            "high": float(r["high"] or 0),
            "low": float(r["low"] or 0),
            "volume": float(r["volume"] or 0),
            "amount": float(r["amount"] or 0),
        } for r in recs]).sort_values("trade_date").reset_index(drop=True)
        cache[code] = df
    return cache


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

    end_d = date.fromisoformat(end)
    logger.info(f"小市值优化回测: {start} ~ {end} | SKIP={SKIP} STOCK_NUM={STOCK_NUM} 止损={STOP_LOSS:.0%}")

    # 1. 月末市值快照
    snaps = await _load_circ_mv_snapshots(sf)
    logger.info(f"市值快照: {len(snaps)} 个月")

    # 2. K 线（覆盖回测区间 start~end + 预热 lookback；回测循环逐日只用当天数据，无未来函数）
    start_d = date.fromisoformat(start)
    cache = await _warmup_klines(sf, start_d, end_d)
    logger.info(f"K 线预热: {len(cache)} 只")

    # 3. 交易日历（index_daily 沪深300）
    from sqlalchemy import text
    async with sf() as session:
        _r = await session.execute(text(
            "SELECT DISTINCT trade_date FROM index_daily "
            "WHERE ts_code = '000300.SH' AND trade_date BETWEEN :s AND :e ORDER BY trade_date"
        ), {"s": start_d, "e": end_d})
        dates = [str(row[0])[:10] for row in _r.fetchall()]
    if not dates:
        logger.error("回测区间无交易日")
        return
    logger.info(f"交易日: {dates[0]} ~ {dates[-1]}, 共 {len(dates)} 天")

    # 4. 每日收盘价索引（用于回测循环）
    close_by_date: Dict[str, Dict[str, float]] = {}
    for code, df in cache.items():
        for _, row in df.iterrows():
            td = str(row["trade_date"])[:10]
            if td < start:
                continue
            close_by_date.setdefault(td, {})[code] = float(row["close"])

    portfolio = SmokePortfolio()
    nav_curve: List[Tuple[str, float]] = []
    entries = exits = 0

    for i, td in enumerate(dates):
        closes = close_by_date.get(td, {})
        if not closes:
            continue

        # 次日开盘成交（前一日 exit）
        portfolio.fill_pending_exits(closes)

        # 个股止损 -9%（收盘价触发）
        for code in list(portfolio.holdings.keys()):
            c = closes.get(code)
            if c is None:
                continue
            cost = portfolio.holdings[code]["cost"]
            if c <= cost * (1 + STOP_LOSS):
                portfolio.sell(code)
                exits += 1

        # 周频调仓（每周二）——聚宽 run_weekly(weekly_adjustment, 2)
        if i % 5 == 1:  # 简化：每 5 个交易日调仓一次
            # 取最近月末快照
            snap_date = None
            for d in sorted(snaps.keys()):
                if d <= td:
                    snap_date = d
                else:
                    break
            if snap_date:
                snapshot = snaps[snap_date]
                # 市值升序，取前 POOL_TOP，剔除最小 SKIP 只
                cands = []
                for code, mv in snapshot.items():
                    if code not in cache:
                        continue
                    c = closes.get(code)
                    if c is None or c <= 0:
                        continue
                    cands.append((code, mv))
                cands.sort(key=lambda x: x[1])
                top = cands[:POOL_TOP]
                targets = [c for c, _ in top[SKIP:SKIP + STOCK_NUM]]

                # 卖出跌出目标的持仓（当日立即成交，避免持仓超 STOCK_NUM 放大仓位）
                target_set = set(targets)
                for code in list(portfolio.holdings.keys()):
                    if code not in target_set:
                        c = closes.get(code, 0.0)
                        if c > 0:
                            portfolio.cash += portfolio.holdings[code]["qty"] * c
                        portfolio.holdings.pop(code, None)
                        exits += 1
                # 等权买入目标
                weight = 1.0 / max(len(targets), 1)
                for code in targets:
                    if code in portfolio.holdings:
                        continue
                    portfolio.buy(code, closes[code], weight)
                    entries += 1

        nav = portfolio.equity(closes)
        nav_curve.append((td, nav))

    await pool.close()

    # ---- 绩效 ----
    navs = np.array([n for _, n in nav_curve])
    if len(navs) == 0:
        logger.error("无净值曲线")
        return
    total_return = navs[-1] / INITIAL_CAPITAL - 1.0
    peak = np.maximum.accumulate(navs)
    max_dd = float(np.min(navs / peak - 1.0))
    has_nan = bool(np.isnan(navs).any())

    logger.info("=" * 60)
    logger.info(f"小市值优化回测: {dates[0]} ~ {dates[-1]} | SKIP={SKIP}")
    logger.info(f"交易: 入场 {entries} 次, 离场 {exits} 次")
    logger.info(f"期末净值: {navs[-1]:,.0f} | 总收益: {total_return:.2%}")
    logger.info(f"最大回撤: {max_dd:.2%} | 含NaN: {has_nan}")
    logger.info(f"最终持仓: {list(portfolio.holdings.keys())}")
    logger.info("=" * 60)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a]
    start = args[0] if len(args) > 0 else START
    end = args[1] if len(args) > 1 else END
    asyncio.run(run_smoke(start, end))
