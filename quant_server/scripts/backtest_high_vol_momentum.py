# -*- coding: utf-8 -*-
"""
高波动动量轮动策略 — 信号级冒烟回测
=======================================
独立运行（不走完整 BacktestEngine），验证策略在真实行情上的信号生成闭环：
on_bar 缓存 → on_bar_batch_end 调仓/风控 → 信号 → 简化持仓模拟 → NAV。

成交口径：order_mode="open" —— 买卖信号均次日开盘成交（与策略声明、rolling_start_analysis.py 一致）。
执行: cd quant_server && .venv/Scripts/python.exe scripts/backtest_high_vol_momentum.py [start] [end]
默认区间: 2026-08-03 ~ 2026-09-04（4 周；全市场预热 + 逐日取数约 15 秒/交易日，长区间请显式传参）
验收（strategy-gates）: 至少 1 笔交易、无 NaN、收益率 ∈ [-95%, +500%]

修复记录 2026-09-10:
  1) daily_bars 原只从预热缓存构建（而预热截止 = 回测起始日）→ 除首日外全部 continue，
     信号恒为 0、自带断言必然失败。现改为预热只填 start 之前的 bar + 逐日从 DB 取当日行情。
  2) 入场原按"信号当日收盘"成交，与 order_mode="open" 不符 → 统一为次日开盘成交。
"""
import asyncio
import logging
import sys
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.engines.types.entities import BarData

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 1_000_000.0
LOT = 100          # A股最小手数
START = "2026-08-03"
END = "2026-09-04"


class SmokePortfolio:
    """简化持仓模拟（order_mode="open" 口径：买卖均次日开盘成交，对齐实盘 T+1）。

    修复 2026-09-10：原实现入场按"信号当日收盘"成交、离场按次日开盘，
    与策略声明的 order_mode="open"（买卖均次日开盘）以及 rolling_start_analysis.py
    的口径都不一致 → 回测偏乐观。现统一为买卖均次日开盘，与 RollingPortfolio 同序（先卖后买）。
    """

    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.cash = initial_capital
        self.holdings: Dict[str, Dict] = {}           # {code: {"qty": int, "cost": float}}
        self.pending_entries: Dict[str, float] = {}   # {code: weight} 次日开盘买
        self.pending_exits: List[str] = []            # [code] 次日开盘卖

    def equity(self, prices: Dict[str, float]) -> float:
        mv = sum(h["qty"] * prices.get(c, h["cost"]) for c, h in self.holdings.items())
        return self.cash + mv

    def fill_pending(self, prices_open: Dict[str, float]) -> None:
        """次日开盘结算：先平仓（释放现金）→ 再开仓（与 RollingPortfolio 同序）。"""
        # 1) 平仓：停牌/无价则保留待次日重试，避免凭空蒸发市值
        still_pending = []
        for code in self.pending_exits:
            price = prices_open.get(code, 0.0)
            h = self.holdings.get(code)
            if h and price > 0:
                self.cash += h["qty"] * price
                self.holdings.pop(code, None)
            elif h:
                still_pending.append(code)
        self.pending_exits = still_pending

        # 2) 开仓：按总权益 × 权重（与真实 Sizer 一致），并以可用现金封顶
        for code, weight in self.pending_entries.items():
            if code in self.holdings:
                continue  # 防重复买入
            price = prices_open.get(code, 0.0)
            if price <= 0:
                continue
            equity = self.equity(prices_open)
            amount = min(equity * weight, self.cash)
            qty = int(amount / price / LOT) * LOT
            if qty <= 0:
                continue
            self.cash -= qty * price
            self.holdings[code] = {"qty": qty, "cost": price}
        self.pending_entries.clear()

    def apply_signal(self, sig, prices: Dict[str, float], trade_date: str) -> None:
        """只登记成交意图，实际成交在次日开盘（fill_pending）。prices/trade_date 仅留兼容签名。"""
        code = sig.ts_code
        from modules.strategy.constants import SignalDirection
        if sig.direction == SignalDirection.LONG:
            if code not in self.holdings and code not in self.pending_entries:
                self.pending_entries[code] = float(getattr(sig, "weight", 0.1) or 0.1)
        elif sig.direction == SignalDirection.CLOSE_LONG:
            if code in self.holdings and code not in self.pending_exits:
                self.pending_exits.append(code)


async def _load_main_board_codes(sf) -> List[str]:
    """主板代码清单（与 StrategyManager._warmup_all_market 同口径）。"""
    from sqlalchemy import text
    async with sf() as session:
        r = await session.execute(text(
            "SELECT DISTINCT ts_code FROM stock_basic "
            "WHERE (ts_code LIKE '000%' OR ts_code LIKE '002%' OR ts_code LIKE '600%' "
            "   OR ts_code LIKE '601%' OR ts_code LIKE '603%' OR ts_code LIKE '605%')"
        ))
        return [row[0] for row in r.fetchall()]


async def _load_bars(sf, codes: List[str], start_d: date, end_d: date) -> Dict[str, pd.DataFrame]:
    """批量加载 [start_d, end_d] 的 qfq 复权日线 → {code: DataFrame(按 trade_date 升序)}。"""
    from shared.database.repositories.market.quote.stock_adj_factor_repo import (
        StockAdjFactorRepository,
    )
    async with sf() as session:
        rows = await StockAdjFactorRepository(session).get_adjusted_daily_batch(
            symbols=codes, start_date=start_d, end_date=end_d, adj_type="qfq",
        )
    by_code: Dict[str, list] = {}
    for row in rows:
        by_code.setdefault(row["ts_code"], []).append(row)

    out: Dict[str, pd.DataFrame] = {}
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
        out[code] = df.sort_values("trade_date").reset_index(drop=True)
    return out


async def _load_day_bars(sf, codes: List[str], td: date) -> Dict[str, BarData]:
    """加载某交易日全市场 qfq 日线 → {code: BarData}（逐日取数，内存占用可控）。"""
    from shared.database.repositories.market.quote.stock_adj_factor_repo import (
        StockAdjFactorRepository,
    )
    async with sf() as session:
        rows = await StockAdjFactorRepository(session).get_adjusted_daily_batch(
            symbols=codes, start_date=td, end_date=td, adj_type="qfq",
        )
    out: Dict[str, BarData] = {}
    for r in rows:
        code = r["ts_code"]
        out[code] = BarData(
            ts_code=code,
            period="daily",
            open=float(r["open"] or 0),
            high=float(r["high"] or 0),
            low=float(r["low"] or 0),
            close=float(r["close"] or 0),
            volume=float(r["volume"] or 0),
            amount=float(r["amount"] or 0),
            trade_date=str(r["trade_date"])[:10],
        )
    return out


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

    symbols = list(strategy.universe) or await _load_main_board_codes(sf)
    logger.info(f"标的池: {len(symbols)}只")

    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)

    # 回测区间交易日（独立查询 index_daily，不依赖缓存）
    from sqlalchemy import text
    async with sf() as _sess:
        _r = await _sess.execute(text(
            "SELECT DISTINCT trade_date FROM index_daily "
            "WHERE ts_code = '000300.SH' AND trade_date BETWEEN :s AND :e ORDER BY trade_date"
        ), {"s": start_d, "e": end_d})
        dates = [str(row[0])[:10] for row in _r.fetchall()]
    if not dates:
        logger.error("回测区间无交易日数据: %s ~ %s", start, end)
        return
    logger.info(f"回测区间: {dates[0]} ~ {dates[-1]}, 共 {len(dates)} 个交易日")

    # ── 修复 2026-09-10 ──
    # 原实现把 daily_bars 只从"预热缓存"构建，而预热截止 = 回测起始日，
    # 于是 for td in dates 里除首日外的交易日全部 continue → 信号恒为 0，
    # 脚本自带的 `assert total_signals >= 1` 必然失败（质量门实际失效）。
    # 现改为：预热只填 start 之前的 bar（不含 start，无未来数据）+ 逐日从 DB 取当日行情。
    lookback = int(getattr(strategy, "lookback_days", 250) or 250)
    warm = await _load_bars(sf, symbols, start_d - timedelta(days=lookback * 2), start_d - timedelta(days=1))
    for code, df in warm.items():
        strategy._data_cache[code] = df
    cache_rows = sum(len(df) for df in strategy._data_cache.values())
    logger.info(f"预热完成: {len(warm)} 只股票, 缓存 {cache_rows} 行（截止 {start_d - timedelta(days=1)}）")
    del warm

    portfolio = SmokePortfolio()
    nav_curve: List[Tuple[str, float]] = []
    total_signals = 0
    entries = 0
    exits = 0

    for td in dates:
        bars_today = await _load_day_bars(sf, symbols, date.fromisoformat(td))
        if not bars_today:
            continue

        # 1. 次日开盘成交（前一日登记的买卖意图，先卖后买）
        prices_open = {c: b.open for c, b in bars_today.items()}
        portfolio.fill_pending(prices_open)

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
