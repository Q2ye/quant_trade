# -*- coding: utf-8 -*-
"""
V2 strategy parameter sweep -- Phase 1 + Phase 2

Usage:
  cd quant_server
  PYTHONPATH=. .venv/Scripts/python.exe scripts/v2_param_sweep.py
"""

import asyncio, csv, logging, os, time as _time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("v2_sweep")
logger.setLevel(logging.INFO)

# =============================================================================
# Asset pools
# =============================================================================

POOL_OLD = [
    "513100.SH", "513500.SH", "513030.SH", "513520.SH", "159920.SZ",
    "510300.SH", "159915.SZ", "518880.SH", "159985.SZ", "511260.SH",
]
US_PAIR_OLD = ["513100.SH", "513500.SH"]

POOL_NEW = [
    "513100.SH",  # Nasdaq 100
    "159915.SZ",  # Chinext
    "518880.SH",  # Gold
    "159985.SZ",  # Soybean meal
    "511260.SH",  # 10Y Treasury
    "512880.SH",  # Securities
    "512480.SH",  # Semiconductor
    "513050.SH",  # China Internet
    "512660.SH",  # Military
    "512100.SH",  # CSI 1000
    "513030.SH",  # DAX
    "513520.SH",  # Nikkei
]
US_PAIR_NEW = []

CASH_ANCHOR = "511990.SH"
DEFENSE_ASSET = "511260.SH"

COMMISSION = 0.0001  # 万分之一佣金（万一免五）
SLIPPAGE = 0.0001
INITIAL_CAPITAL = 1_000_000.0


@dataclass
class SimResult:
    name: str = ""
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe: float = 0.0
    max_dd: float = 0.0
    calmar: float = 0.0
    num_trades: int = 0
    stop_count: int = 0
    defense_months: int = 0
    total_months: int = 0
    params: Dict = None


# =============================================================================
# Momentum calculation (identical to _calc_asset_return in strategy)
# =============================================================================


def _momentum_ret(closes, momentum_window, skip_window):
    needed = momentum_window + skip_window
    if len(closes) < needed:
        return None
    end_idx = -(skip_window + 1)
    start_idx = -(momentum_window + skip_window)
    end_price = closes[end_idx]
    start_price = closes[start_idx]
    if start_price <= 0 or np.isnan(start_price) or np.isnan(end_price):
        return None
    return float(end_price / start_price - 1.0)


# =============================================================================
# Phase 3 helpers: ATR & momentum-weighted allocation
# =============================================================================


def _calc_atr_pct(closes, window=20):
    """Approximate ATR as a percentage of price using close-to-close changes."""
    if len(closes) < window + 1:
        return 0.02  # default 2%
    changes = np.abs(np.diff(closes[-window - 1:]))
    atr = float(np.mean(changes)) if len(changes) > 0 else 0.0
    price = closes[-1]
    return atr / price if price > 0 else 0.02


def _pool_median_atr(closes_cache, asset_pool):
    """Compute median ATR% across the pool for normalization."""
    atrs = []
    for code in asset_pool:
        vals = closes_cache.get(code, [])
        if len(vals) >= 21:
            atrs.append(_calc_atr_pct(vals))
    return float(np.median(atrs)) if atrs else 0.02


# =============================================================================
# Single simulation run
# =============================================================================


def run_simulation(
    asset_pool, us_pair, asset_data, all_trade_dates,
    momentum_window, skip_window, max_holdings, max_single_weight,
    stop_loss, use_absolute_momentum,
    use_atr_stop=False,           # Phase 3: dynamic ATR stop
    use_momentum_weight=False,    # Phase 3: score-weighted allocation
):
    closes_cache = {code: [] for code in asset_data}
    amounts_cache = {code: [] for code in asset_data}
    date_ptr = {code: 0 for code in asset_data}

    cash = INITIAL_CAPITAL
    holdings = {}
    entry_prices = {}
    target_weights = {}
    entry_atrs = {}  # Phase 3: ATR at entry for dynamic stop

    equity_curve = [INITIAL_CAPITAL]
    daily_returns = []
    trade_count = 0
    stop_count = 0
    defense_months = 0

    last_month = ""
    stopped_today = set()
    active_months = 0
    warmup_warned = False

    for td in all_trade_dates:
        # on_bar: cache today's data
        for code in asset_data:
            ptr = date_ptr[code]
            if ptr < len(asset_data[code]) and asset_data[code][ptr][0] == td:
                _, cls, amt = asset_data[code][ptr]
                closes_cache[code].append(cls)
                amounts_cache[code].append(amt)
                date_ptr[code] = ptr + 1

        # warmup: accumulate data only, no trading before 2021-07-19
        if td < "2021-07-19":
            continue

        current_month = td[:7]

        # mark-to-market
        mv = 0.0
        for code, shares in holdings.items():
            if closes_cache[code]:
                mv += shares * closes_cache[code][-1]
        equity = cash + mv
        if equity > 0 and equity_curve[-1] > 0:
            daily_returns.append(equity / equity_curve[-1] - 1.0)
        equity_curve.append(equity)

        # warmup check
        max_len = max((len(closes_cache[c]) for c in asset_pool), default=0)
        min_history = momentum_window + skip_window
        if max_len < min_history:
            if not warmup_warned:
                warmup_warned = True
            continue

        # month change -> rebalance + stop check
        if current_month != last_month and last_month:
            active_months += 1
            stopped_today.clear()

            # Step 1: hard stop (before rebalance)
            for code in list(holdings.keys()):
                if not closes_cache[code]:
                    continue
                entry = entry_prices.get(code)
                if entry is None or entry <= 0:
                    continue
                current_price = closes_cache[code][-1]
                if current_price <= 0:
                    continue
                pnl = current_price / entry - 1.0

                # Phase 3: dynamic ATR stop
                effective_stop = stop_loss
                if use_atr_stop:
                    entry_atr = entry_atrs.get(code)
                    if entry_atr is None or entry_atr <= 0:
                        entry_atr = _calc_atr_pct(closes_cache[code])
                        entry_atrs[code] = entry_atr
                    med_atr = _pool_median_atr(closes_cache, asset_pool)
                    if med_atr > 0 and entry_atr > 0:
                        vol_ratio = entry_atr / med_atr
                        # Scale: volatile -> wider stop, stable -> tighter
                        effective_stop = max(min(stop_loss * vol_ratio, -0.08), -0.25)
                        effective_stop = min(effective_stop, stop_loss)  # don't tighten below base

                if pnl <= effective_stop:
                    sell_value = holdings[code] * current_price * (1 - SLIPPAGE) * (1 - COMMISSION)
                    cash += sell_value
                    del holdings[code]
                    entry_prices.pop(code, None)
                    entry_atrs.pop(code, None)
                    stopped_today.add(code)
                    stop_count += 1
                    trade_count += 1

            # Step 2: momentum ranking
            us_code = None
            best_amt = -1.0
            for code in us_pair:
                amts = amounts_cache.get(code, [])
                if len(amts) >= 20:
                    avg = float(np.mean(amts[-20:]))
                    if avg > best_amt:
                        best_amt = avg
                        us_code = code
            effective_pool = [c for c in asset_pool if c not in us_pair or c == us_code]

            rankings = []
            for code in effective_pool:
                ret = _momentum_ret(closes_cache.get(code, []), momentum_window, skip_window)
                if ret is not None:
                    rankings.append((code, ret))
            rankings.sort(key=lambda x: x[1], reverse=True)

            if rankings:
                cash_ret = _momentum_ret(closes_cache.get(CASH_ANCHOR, []), momentum_window, skip_window)
                if cash_ret is None:
                    cash_ret = 0.0
                defense_ret = _momentum_ret(closes_cache.get(DEFENSE_ASSET, []), momentum_window, skip_window)
                defense_code = DEFENSE_ASSET if (defense_ret is not None and defense_ret > cash_ret) else CASH_ANCHOR

                # Step 3: slot decisions
                n = min(max_holdings, len(rankings))
                raw_slots = {}
                for i in range(n):
                    code, score = rankings[i]
                    if code in stopped_today:
                        raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0
                    elif not use_absolute_momentum or score > cash_ret:
                        raw_slots[code] = raw_slots.get(code, 0.0) + 1.0
                    else:
                        raw_slots[defense_code] = raw_slots.get(defense_code, 0.0) + 1.0

                if sum(raw_slots.values()) <= 0:
                    raw_slots = {defense_code: 1.0}

                total_slots = sum(raw_slots.values())
                target_weights = {}

                if use_momentum_weight and len(rankings) >= 2:
                    # Phase 3: momentum-weighted allocation
                    scores_in_use = []
                    for code in raw_slots:
                        for rc, rs in rankings:
                            if rc == code:
                                scores_in_use.append((code, max(0.0, rs)))
                                break
                        else:
                            # defense code not in rankings -> assign median score
                            med = np.median([s for _, s in rankings[:n]]) if rankings[:n] else 0.0
                            scores_in_use.append((code, max(0.0, med)))

                    total_score = sum(s for _, s in scores_in_use)
                    if total_score > 0:
                        for code, sc in scores_in_use:
                            raw_w = (sc / total_score) * total_slots
                            target_weights[code] = min(raw_w, max_single_weight)
                    else:
                        for code, slots in raw_slots.items():
                            target_weights[code] = min(slots / total_slots, max_single_weight)
                else:
                    for code, slots in raw_slots.items():
                        w = min(slots / total_slots, max_single_weight)
                        target_weights[code] = w

                # Renormalize if cap truncated
                tw_sum = sum(target_weights.values())
                if tw_sum > 0 and abs(tw_sum - 1.0) > 0.001:
                    target_weights = {c: w / tw_sum for c, w in target_weights.items()}

                # defense month count
                defense_codes = {DEFENSE_ASSET, CASH_ANCHOR}
                if set(target_weights.keys()).issubset(defense_codes):
                    defense_months += 1

                # Step 4: execute trades
                total_mv = sum(
                    holdings.get(c, 0.0) * (closes_cache[c][-1] if closes_cache[c] else 0.0)
                    for c in holdings
                )
                total_eq = cash + total_mv

                # sell removed
                for code in list(holdings.keys()):
                    if code not in target_weights:
                        price = closes_cache[code][-1] if closes_cache[code] else 0.0
                        if price > 0:
                            sell_val = holdings[code] * price * (1 - SLIPPAGE) * (1 - COMMISSION)
                            cash += sell_val
                            trade_count += 1
                        del holdings[code]
                        entry_prices.pop(code, None)

                # buy / adjust
                for code, tw in target_weights.items():
                    price = closes_cache[code][-1] if closes_cache[code] else 0.0
                    if price <= 0:
                        continue
                    target_value = total_eq * tw
                    current_shares = holdings.get(code, 0.0)
                    current_value = current_shares * price
                    diff = target_value - current_value

                    if abs(diff) > total_eq * 0.005 and abs(diff) > 100:
                        if diff > 0:
                            buy_cost = diff * (1 + COMMISSION)
                            if buy_cost <= cash:
                                buy_shares = diff / price * (1 - SLIPPAGE)
                                cash -= buy_cost
                                holdings[code] = current_shares + buy_shares
                                trade_count += 1
                        else:
                            sell_shares = min(-diff / price, current_shares)
                            sell_val = sell_shares * price * (1 - SLIPPAGE) * (1 - COMMISSION)
                            cash += sell_val
                            holdings[code] = current_shares - sell_shares
                            if holdings[code] <= 0:
                                del holdings[code]
                            trade_count += 1

                    if code in holdings and code not in entry_prices:
                        entry_prices[code] = price
                        if use_atr_stop:
                            entry_atrs[code] = _calc_atr_pct(closes_cache[code])

        elif current_month == last_month:
            # intra-month: daily stop check only
            for code in list(holdings.keys()):
                if not closes_cache[code]:
                    continue
                entry = entry_prices.get(code)
                if entry is None or entry <= 0:
                    continue
                current_price = closes_cache[code][-1]
                if current_price <= 0:
                    continue
                pnl = current_price / entry - 1.0

                # Phase 3: dynamic ATR stop (same logic as month-change check)
                effective_stop = stop_loss
                if use_atr_stop:
                    entry_atr = entry_atrs.get(code)
                    if entry_atr is None or entry_atr <= 0:
                        entry_atr = _calc_atr_pct(closes_cache[code])
                        entry_atrs[code] = entry_atr
                    med_atr = _pool_median_atr(closes_cache, asset_pool)
                    if med_atr > 0 and entry_atr > 0:
                        vol_ratio = entry_atr / med_atr
                        effective_stop = max(min(stop_loss * vol_ratio, -0.08), -0.25)
                        effective_stop = min(effective_stop, stop_loss)

                if pnl <= effective_stop:
                    sell_val = holdings[code] * current_price * (1 - SLIPPAGE) * (1 - COMMISSION)
                    cash += sell_val
                    del holdings[code]
                    entry_prices.pop(code, None)
                    entry_atrs.pop(code, None)
                    stopped_today.add(code)
                    stop_count += 1
                    trade_count += 1

        last_month = current_month

    # ---- performance metrics ----
    if len(daily_returns) < 10:
        return SimResult(name="N/A")

    rets = np.array(daily_returns)
    years = len(rets) / 242.0

    total_return = equity_curve[-1] / equity_curve[0] - 1.0
    annual_return = (1 + total_return) ** (1.0 / max(years, 0.1)) - 1.0

    mean_ret = float(np.mean(rets))
    std_ret = float(np.std(rets, ddof=1))
    sharpe = (mean_ret / std_ret * np.sqrt(242)) if std_ret > 0 else 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak
        if dd > max_dd:
            max_dd = dd

    calmar = annual_return / max_dd if max_dd > 0 else 0.0

    return SimResult(
        total_return=total_return, annual_return=annual_return,
        sharpe=sharpe, max_dd=max_dd, calmar=calmar,
        num_trades=trade_count, stop_count=stop_count,
        defense_months=defense_months, total_months=active_months,
    )


# =============================================================================
# Main
# =============================================================================


async def main():
    logger.info("Loading ETF daily data...")
    from shared.database.session.connection_pool import get_connection_pool
    from sqlalchemy import text

    pool = get_connection_pool()
    if not pool._engine:
        await pool.initialize()

    session_factory = pool.get_session_factory()
    db = session_factory()

    all_symbols = list(set(POOL_OLD + POOL_NEW + [CASH_ANCHOR]))

    try:
        placeholders = ",".join(f":s{i}" for i in range(len(all_symbols)))
        query = (
            f"SELECT ts_code, trade_date, close, COALESCE(amount, 0) "
            f"FROM etf_daily WHERE ts_code IN ({placeholders}) "
            f"AND trade_date >= '2014-01-01' AND trade_date <= '2026-07-18' "
            f"ORDER BY trade_date, ts_code"
        )
        params = {f"s{i}": s for i, s in enumerate(all_symbols)}
        result = await db.execute(text(query), params)
        rows = result.fetchall()
        logger.info(f"Loaded {len(rows)} rows")
    finally:
        await db.close()

    asset_data = defaultdict(list)
    all_dates_set = set()
    for row in rows:
        code, td, cls, amt = row
        td_str = str(td)[:10] if td else ""
        if not td_str:
            continue
        asset_data[code].append((td_str, float(cls or 0), float(amt or 0)))
        all_dates_set.add(td_str)

    all_dates = sorted(d for d in all_dates_set if d >= "2018-01-01")
    logger.info(f"Ready: {len(asset_data)} symbols, {len(all_dates)} trading days")

    # =====================================================================
    # Phase 1: parameter grid (old pool)
    # =====================================================================
    param_sets = [
        ("P1-Base  (252d,top3,-10%,AM)", 252, 21, 3, 0.40, -0.10, True),
        ("P1-Mild  (126d,top4,-12%,AM)", 126, 10, 4, 0.30, -0.12, True),
        ("P1-NoAM  (126d,top4,-12%,NO)", 126, 10, 4, 0.30, -0.12, False),
        ("P1-Aggr  (63d, top4,-12%,NO)",  63,  5, 4, 0.30, -0.12, False),
        ("P1-Extrm (63d, top5,-15%,NO)",  63,  5, 5, 0.25, -0.15, False),
        ("P1-Ultra (42d, top5,-15%,NO)",  42,  3, 5, 0.25, -0.15, False),
    ]

    p1_results = []
    logger.info(f"\n{'='*80}")
    logger.info("Phase 1: Parameter grid (old pool, 10 assets)")
    logger.info(f"{'='*80}")

    for name, mw, sw, mh, msw, sl, am in param_sets:
        t0 = _time.time()
        r = run_simulation(
            asset_pool=POOL_OLD, us_pair=US_PAIR_OLD,
            asset_data=dict(asset_data), all_trade_dates=all_dates,
            momentum_window=mw, skip_window=sw,
            max_holdings=mh, max_single_weight=msw,
            stop_loss=sl, use_absolute_momentum=am,
        )
        r.name = name
        r.params = {"pool": "old(10)", "mw": mw, "sw": sw, "mh": mh, "msw": msw, "sl": sl, "am": am}
        p1_results.append(r)
        logger.info(f"  {name} -> ann={r.annual_return:.1%} mdd={r.max_dd:.1%} calmar={r.calmar:.3f} sharpe={r.sharpe:.2f} stops={r.stop_count} def={r.defense_months}/{r.total_months} ({_time.time()-t0:.1f}s)")

    # =====================================================================
    # Phase 2: pool comparison (champion params)
    # =====================================================================
    champ = (126, 10, 4, 0.30, -0.12, False)  # mw, sw, mh, msw, sl, am

    logger.info(f"\n{'='*80}")
    logger.info("Phase 2: Pool comparison (champion: 126d/top4/-12%/NO-AM)")
    logger.info(f"{'='*80}")

    p2_results = []

    t0 = _time.time()
    r = run_simulation(
        asset_pool=POOL_OLD, us_pair=US_PAIR_OLD,
        asset_data=dict(asset_data), all_trade_dates=all_dates,
        momentum_window=champ[0], skip_window=champ[1],
        max_holdings=champ[2], max_single_weight=champ[3],
        stop_loss=champ[4], use_absolute_momentum=champ[5],
    )
    r.name = "P2-OldPool(10)"
    r.params = {"pool": "old(10)", "mw": champ[0], "sw": champ[1], "mh": champ[2], "msw": champ[3], "sl": champ[4], "am": champ[5]}
    p2_results.append(r)
    logger.info(f"  OldPool(10) -> ann={r.annual_return:.1%} mdd={r.max_dd:.1%} calmar={r.calmar:.3f} ({_time.time()-t0:.1f}s)")

    t0 = _time.time()
    r = run_simulation(
        asset_pool=POOL_NEW, us_pair=US_PAIR_NEW,
        asset_data=dict(asset_data), all_trade_dates=all_dates,
        momentum_window=champ[0], skip_window=champ[1],
        max_holdings=champ[2], max_single_weight=champ[3],
        stop_loss=champ[4], use_absolute_momentum=champ[5],
    )
    r.name = "P2-NewPool(12)"
    r.params = {"pool": "new(12)", "mw": champ[0], "sw": champ[1], "mh": champ[2], "msw": champ[3], "sl": champ[4], "am": champ[5]}
    p2_results.append(r)
    logger.info(f"  NewPool(12) -> ann={r.annual_return:.1%} mdd={r.max_dd:.1%} calmar={r.calmar:.3f} ({_time.time()-t0:.1f}s)")

    # =====================================================================
    # Phase 3: Dynamic stop + momentum weighting (new pool + champion)
    # =====================================================================
    logger.info(f"\n{'='*80}")
    logger.info("Phase 3: ATR stop + momentum weight (new pool, 126d/top4/-12%/NO-AM)")
    logger.info(f"{'='*80}")

    p3_results = []

    # P3a: baseline (no enhancements, from P2)
    p3_results.append(p2_results[1])  # NewPool(12) = baseline for P3

    # P3b: ATR stop only
    t0 = _time.time()
    r = run_simulation(
        asset_pool=POOL_NEW, us_pair=US_PAIR_NEW,
        asset_data=dict(asset_data), all_trade_dates=all_dates,
        momentum_window=champ[0], skip_window=champ[1],
        max_holdings=champ[2], max_single_weight=champ[3],
        stop_loss=champ[4], use_absolute_momentum=champ[5],
        use_atr_stop=True, use_momentum_weight=False,
    )
    r.name = "P3-ATRstop"
    r.params = {"pool": "new(12)", "enhance": "ATR", "mw": champ[0], "sw": champ[1], "mh": champ[2], "msw": champ[3], "sl": champ[4], "am": champ[5]}
    p3_results.append(r)
    logger.info(f"  ATR stop        -> ann={r.annual_return:.1%} mdd={r.max_dd:.1%} calmar={r.calmar:.3f} stops={r.stop_count} ({_time.time()-t0:.1f}s)")

    # P3c: momentum weight only
    t0 = _time.time()
    r = run_simulation(
        asset_pool=POOL_NEW, us_pair=US_PAIR_NEW,
        asset_data=dict(asset_data), all_trade_dates=all_dates,
        momentum_window=champ[0], skip_window=champ[1],
        max_holdings=champ[2], max_single_weight=champ[3],
        stop_loss=champ[4], use_absolute_momentum=champ[5],
        use_atr_stop=False, use_momentum_weight=True,
    )
    r.name = "P3-MomWgt"
    r.params = {"pool": "new(12)", "enhance": "MomWgt", "mw": champ[0], "sw": champ[1], "mh": champ[2], "msw": champ[3], "sl": champ[4], "am": champ[5]}
    p3_results.append(r)
    logger.info(f"  MomWgt          -> ann={r.annual_return:.1%} mdd={r.max_dd:.1%} calmar={r.calmar:.3f} trades={r.num_trades} ({_time.time()-t0:.1f}s)")

    # P3d: both ATR + momentum
    t0 = _time.time()
    r = run_simulation(
        asset_pool=POOL_NEW, us_pair=US_PAIR_NEW,
        asset_data=dict(asset_data), all_trade_dates=all_dates,
        momentum_window=champ[0], skip_window=champ[1],
        max_holdings=champ[2], max_single_weight=champ[3],
        stop_loss=champ[4], use_absolute_momentum=champ[5],
        use_atr_stop=True, use_momentum_weight=True,
    )
    r.name = "P3-Both"
    r.params = {"pool": "new(12)", "enhance": "Both", "mw": champ[0], "sw": champ[1], "mh": champ[2], "msw": champ[3], "sl": champ[4], "am": champ[5]}
    p3_results.append(r)
    logger.info(f"  ATR+MomWgt      -> ann={r.annual_return:.1%} mdd={r.max_dd:.1%} calmar={r.calmar:.3f} stops={r.stop_count} trades={r.num_trades} ({_time.time()-t0:.1f}s)")

    # =====================================================================
    # Output
    # =====================================================================

    # Phase 1 ranking
    p1_results.sort(key=lambda r: r.calmar, reverse=True)
    print(f"\n{'='*95}")
    print("Phase 1 Results (ranked by Calmar)")
    print(f"{'='*95}")
    print(f"{'#':<3} {'Name':<34} {'Ann':>6} {'MDD':>6} {'Calmar':>7} {'Sharpe':>6} {'Stops':>5} {'DefMo':>6} {'Trd':>4}")
    print("-" * 95)
    for i, r in enumerate(p1_results, 1):
        print(f"{i:<3} {r.name:<34} {r.annual_return:>5.1%} {r.max_dd:>5.1%} {r.calmar:>6.3f} {r.sharpe:>5.2f} {r.stop_count:>4}  {r.defense_months:>3}/{r.total_months:<3} {r.num_trades:>3}")

    # Phase 2 comparison
    if len(p2_results) >= 2:
        old, new = p2_results[0], p2_results[1]
        print(f"\n{'='*95}")
        print("Phase 2 Results (Old vs New Pool)")
        print(f"{'='*95}")
        print(f"{'Metric':<20} {'Old(10)':>15} {'New(12)':>15} {'Change':>15}")
        print("-" * 70)
        metrics = [
            ("Annual Return", old.annual_return, new.annual_return, ".1%"),
            ("Max Drawdown", old.max_dd, new.max_dd, ".1%"),
            ("Calmar Ratio", old.calmar, new.calmar, ".3f"),
            ("Sharpe Ratio", old.sharpe, new.sharpe, ".2f"),
            ("Total Return", old.total_return, new.total_return, ".1%"),
            ("Stop Count", float(old.stop_count), float(new.stop_count), ".0f"),
            ("Trade Count", float(old.num_trades), float(new.num_trades), ".0f"),
            ("Defense Months", float(old.defense_months), float(new.defense_months), ".0f"),
        ]
        for label, ov, nv, fmt in metrics:
            if isinstance(ov, float) and isinstance(nv, float) and abs(ov) > 0.0001:
                change = f"{(nv - ov) / abs(ov) * 100:+.0f}%"
            else:
                change = f"{int(nv) - int(ov):+d}"
            print(f"{label:<20} {ov:>14{fmt}} {nv:>14{fmt}} {change:>15}")

    # Combined Pareto
    all_results = p1_results + p2_results + p3_results[1:]  # p3 baseline is dup of p2
    print(f"\n{'='*95}")
    print("Pareto Frontier (Annual vs MDD)")
    print(f"{'='*95}")
    pareto = []
    for r in all_results:
        dominated = any(
            r2.annual_return >= r.annual_return and r2.max_dd <= r.max_dd
            and (r2.annual_return > r.annual_return or r2.max_dd < r.max_dd)
            for r2 in all_results
        )
        if not dominated:
            pareto.append(r)
    pareto.sort(key=lambda r: r.annual_return)
    for r in pareto:
        pool_tag = r.params.get("pool", "") if r.params else ""
        print(f"  * {r.name:<34} ann={r.annual_return:.1%} mdd={r.max_dd:.1%} calmar={r.calmar:.3f} sharpe={r.sharpe:.2f} [{pool_tag}]")

    # Phase 3 comparison
    if len(p3_results) >= 2:
        base = p3_results[0]  # P2-NewPool(12) baseline
        print(f"\n{'='*95}")
        print("Phase 3 Results (Enhancements on New Pool)")
        print(f"{'='*95}")
        print(f"{'Enhancement':<22} {'Ann':>6} {'MDD':>6} {'Calmar':>7} {'Sharpe':>6} {'Stops':>5} {'Trades':>6}")
        print("-" * 70)
        for r in p3_results:
            print(f"{r.name:<22} {r.annual_return:>5.1%} {r.max_dd:>5.1%} {r.calmar:>6.3f} {r.sharpe:>5.2f} {r.stop_count:>4}  {r.num_trades:>5}")

        print(f"\n{'Enhancement':<22} {'Ann':>12} {'MDD':>12} {'Calmar':>12}")
        print("-" * 60)
        for r in p3_results[1:]:
            delta_ann = r.annual_return - base.annual_return
            delta_mdd = r.max_dd - base.max_dd
            delta_cal = r.calmar - base.calmar
            print(f"{r.name:<22} {delta_ann:>+10.1%}  {delta_mdd:>+10.1%}  {delta_cal:>+10.3f}")

    # CSV
    csv_path = os.path.join(os.path.dirname(__file__), "..", "v2_sweep_results.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Phase", "Name", "Pool", "AnnRet", "TotRet", "Sharpe", "MaxDD", "Calmar",
                     "Trades", "Stops", "DefMo", "TotMo", "mw", "sw", "mh", "msw", "sl", "am"])
        for r in p1_results + p2_results + p3_results:
            p = r.params or {}
            w.writerow([
                r.name[:3], r.name, p.get("pool", ""),
                f"{r.annual_return:.4f}", f"{r.total_return:.4f}",
                f"{r.sharpe:.4f}", f"{r.max_dd:.4f}", f"{r.calmar:.4f}",
                r.num_trades, r.stop_count, r.defense_months, r.total_months,
                p.get("mw", ""), p.get("sw", ""), p.get("mh", ""),
                p.get("msw", ""), p.get("sl", ""), p.get("am", ""),
            ])

    logger.info(f"Results saved to {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())
