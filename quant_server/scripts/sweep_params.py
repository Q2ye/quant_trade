# -*- coding: utf-8 -*-
"""
LightGBM ETF 底部策略 — 参数扫描优化
=====================================
基于投资哲学（赔率优先、集中持仓、高波动标的、非对称止盈）扫描关键参数，
找到最大化总收益的配置。

执行: cd quant_server && .venv/Scripts/python.exe scripts/sweep_params.py
"""
import asyncio, logging, math, sys
from datetime import date
from itertools import product
from pathlib import Path
from typing import Dict, List

import asyncpg
import joblib
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DB = {"host": "localhost", "port": 5432, "user": "postgres", "password": "123456", "database": "quant_signals_dev"}
MODEL_DIR = Path(__file__).resolve().parent.parent / "storage" / "models"
INITIAL_CAPITAL = 1_000_000
COMMISSION = 0.0001  # 万分之一佣金（万一免五）

# ── ETF 池定义 ──
ALL_ETFS = [
    "510050.SH", "510300.SH", "510500.SH", "159919.SZ", "510880.SH",
    "512880.SH", "512660.SH", "512690.SH", "512800.SH", "512100.SH",
    "159915.SZ", "159949.SZ", "518880.SH", "513100.SH", "513050.SH",
    "511010.SH", "511260.SH", "510310.SH", "159865.SZ", "159825.SZ",
    "159766.SZ", "159781.SZ", "512170.SH", "159806.SZ", "516510.SH",
    "159840.SZ", "512400.SH",
]

# 高贝塔池: 剔除债券、黄金、跨境（专注A股高波动权益ETF）
HIGH_BETA_ETFS = [
    "510050.SH", "510300.SH", "510500.SH", "159919.SZ", "510880.SH",
    "512880.SH", "512660.SH", "512690.SH", "512800.SH", "512100.SH",
    "159915.SZ", "159949.SZ", "510310.SH",
    "159865.SZ", "159825.SZ", "159766.SZ", "159781.SZ",
    "512170.SH", "159806.SZ", "516510.SH", "159840.SZ", "512400.SH",
]

ETF_POOLS = {"all": ALL_ETFS, "high_beta": HIGH_BETA_ETFS}

# ── 固定参数（激进基准）──
BASE_PARAMS = {
    "max_single_position": 0.40,   # 集中重仓
    "trail_activate": 0.03,        # 尽早启动移动止盈
    "trail_distance": 0.05,        # 宽回撤容忍（让利润奔跑）
}


async def load_model():
    files = sorted(MODEL_DIR.glob("etf_bottom_v1_*.joblib"))
    path = files[-1]
    artifact = joblib.load(path)
    return (artifact["model"], artifact["feature_names"],
            artifact.get("scaler_params", {}))


async def load_data(conn, feature_names, start, end):
    flist = "','".join(feature_names)
    rows = await conn.fetch(f"""
        SELECT ts_code, trade_date::text, factor_code, factor_value
        FROM factor_data
        WHERE trade_date >= $1 AND trade_date <= $2
          AND factor_code = ANY(ARRAY['{flist}']::varchar[])
        ORDER BY ts_code, trade_date
    """, start, end)
    factor_data = {}
    for r in rows:
        key = (r["ts_code"], r["trade_date"])
        if key not in factor_data:
            factor_data[key] = {}
        v = r["factor_value"]
        factor_data[key][r["factor_code"]] = float(v) if v is not None else np.nan

    prices = await conn.fetch("""
        SELECT ts_code, trade_date::text, open, high, low, close
        FROM etf_daily WHERE trade_date >= $1 AND trade_date <= $2 ORDER BY ts_code, trade_date
    """, start, end)
    price_data = {}
    for r in prices:
        price_data[(r["ts_code"], r["trade_date"])] = {
            "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
        }
    return factor_data, price_data


def run_once(model, feature_names, scaler, factor_data, price_data, config):
    """单次回测，返回绩效摘要"""
    mu = scaler.get("mu", [])
    sigma = scaler.get("sigma", [])
    threshold = config["threshold"]
    max_positions = config["max_positions"]
    stop_loss = config["stop_loss"]
    max_hold_days = config["max_hold_days"]
    etf_pool = config["etf_pool"]
    trail_activate = BASE_PARAMS["trail_activate"]
    trail_distance = BASE_PARAMS["trail_distance"]
    max_single_pos = BASE_PARAMS["max_single_position"]

    all_dates = sorted(set(k[1] for k in price_data.keys()))

    # 生成预测
    predictions = []
    for td in all_dates:
        for etf in etf_pool:
            fkey = (etf, td)
            pkey = (etf, td)
            if fkey not in factor_data or pkey not in price_data:
                continue
            fvals = [factor_data[fkey].get(fn, np.nan) for fn in feature_names]
            farr = np.array(fvals, dtype=np.float64)
            if np.isnan(farr).mean() > 0.5:
                continue
            farr = np.nan_to_num(farr, nan=0.0)
            if mu and sigma:
                farr = (farr - np.array(mu)) / (np.array(sigma) + 1e-8)
            proba = model.predict_proba(farr.reshape(1, -1))[0, 1]
            close = price_data[pkey]["close"]
            predictions.append((td, etf, proba, close))

    df = pd.DataFrame(predictions, columns=["date", "ts_code", "proba", "close"])
    df = df.sort_values(["date", "proba"], ascending=[True, False])

    # 模拟交易
    available = INITIAL_CAPITAL
    positions: Dict[str, dict] = {}
    cooling: Dict[str, int] = {}
    trades: List[dict] = []

    for td in all_dates:
        # 出场
        for etf in list(positions.keys()):
            pkey = (etf, td)
            if pkey not in price_data:
                continue
            bar = price_data[pkey]
            pos = positions[etf]
            pnl = bar["close"] / pos["entry_price"] - 1
            hold_days = (date.fromisoformat(td) - pos["entry_date"]).days
            pos["peak"] = max(pos["peak"], bar["high"])
            dd = (pos["peak"] - bar["close"]) / pos["peak"]

            exit_reason = None
            if pnl < stop_loss:
                exit_reason = "stop_loss"
            elif max_hold_days > 0 and hold_days >= max_hold_days:
                exit_reason = "time_stop"
            elif (pos["peak"] / pos["entry_price"] - 1 >= trail_activate
                  and dd >= trail_distance):
                exit_reason = "trail_stop"

            if exit_reason:
                exit_val = pos["shares"] * bar["close"] * (1 - COMMISSION)
                pnl_amt = exit_val - pos["cost"]
                available += exit_val
                trades.append({
                    "pnl_pct": pnl, "pnl_amt": pnl_amt,
                    "hold_days": hold_days, "reason": exit_reason,
                })
                cooling[etf] = 2
                del positions[etf]

        # 冷却
        for etf in list(cooling.keys()):
            cooling[etf] -= 1
            if cooling[etf] <= 0:
                del cooling[etf]

        # 入场
        if len(positions) < max_positions and available > INITIAL_CAPITAL * 0.03:
            day_preds = df[df["date"] == td]
            for _, row in day_preds.iterrows():
                etf = row["ts_code"]
                if etf in positions or etf in cooling or etf not in etf_pool:
                    continue
                if row["proba"] < threshold:
                    continue
                if len(positions) >= max_positions:
                    break

                pkey = (etf, td)
                if pkey not in price_data:
                    continue
                bar = price_data[pkey]

                weight = max(0.02, (row["proba"] - threshold) / (1 - threshold)) * max_single_pos
                alloc = available * min(weight, 1.0 / max_positions)
                shares = int(alloc / bar["close"] / 100) * 100
                if shares < 100:
                    continue
                cost = shares * bar["close"] * (1 + COMMISSION)
                available -= cost
                positions[etf] = {
                    "entry_price": bar["close"],
                    "entry_date": date.fromisoformat(td),
                    "shares": shares, "cost": cost, "peak": bar["high"],
                }

    # 绩效指标
    if not trades:
        return {"total_return": 0, "sharpe": -99, "n_trades": 0, "win_rate": 0,
                "profit_factor": 0, "max_dd": 0, "total_pnl": 0,
                "avg_hold": 0, "time_stop_pct": 0, "config_key": ""}

    final_equity = available + sum(
        positions[e]["shares"] * price_data.get((e, all_dates[-1]), {}).get("close",
        positions[e]["entry_price"]) for e in positions
    )
    total_return = final_equity / INITIAL_CAPITAL - 1

    win_trades = [t for t in trades if t["pnl_pct"] > 0]
    loss_trades = [t for t in trades if t["pnl_pct"] <= 0]
    win_rate = len(win_trades) / len(trades) if trades else 0
    total_pnl = sum(t["pnl_amt"] for t in trades)
    avg_win = np.mean([t["pnl_pct"] for t in win_trades]) if win_trades else 0
    avg_loss = np.mean([t["pnl_pct"] for t in loss_trades]) if loss_trades else 0
    profit_factor = abs(sum(t["pnl_amt"] for t in win_trades) / sum(t["pnl_amt"] for t in loss_trades)) if loss_trades else float("inf") if win_trades else 0
    avg_hold = np.mean([t["hold_days"] for t in trades])
    time_stop_pct = sum(1 for t in trades if t["reason"] == "time_stop") / len(trades)
    stop_loss_pct = sum(1 for t in trades if t["reason"] == "stop_loss") / len(trades)
    trail_pct = sum(1 for t in trades if t["reason"] == "trail_stop") / len(trades)

    # Simple daily return for Sharpe (approximate)
    daily_ret = total_return / len(all_dates) if all_dates else 0
    sharpe = (daily_ret * 252 - 0.025) / 0.15  # rough estimate

    return {
        "total_return": total_return, "n_trades": len(trades),
        "win_rate": win_rate, "total_pnl": total_pnl,
        "avg_win": avg_win, "avg_loss": avg_loss,
        "profit_factor": profit_factor, "avg_hold": avg_hold,
        "time_stop_pct": time_stop_pct, "stop_loss_pct": stop_loss_pct,
        "trail_pct": trail_pct,
    }


async def main():
    model, features, scaler = await load_model()
    logger.info("模型: %d features", len(features))

    conn = await asyncpg.connect(**DB)
    try:
        factor_data, price_data = await load_data(conn, features, date(2024, 1, 1), date(2025, 6, 30))
    finally:
        await conn.close()

    # ── 参数网格 ──
    grid = list(product(
        [0.30, 0.35, 0.38],           # threshold
        [3, 5],                         # max_positions
        [-0.05, -0.06],                # stop_loss
        [12, 15],                       # max_hold_days
        ["all", "high_beta"],           # etf_pool
    ))

    logger.info("扫描 %d 组参数...", len(grid))
    results = []
    for threshold, max_pos, stop_loss, max_hold, pool_name in grid:
        config = {
            "threshold": threshold,
            "max_positions": max_pos,
            "stop_loss": stop_loss,
            "max_hold_days": max_hold,
            "etf_pool": ETF_POOLS[pool_name],
        }
        key = f"T={threshold:.2f} P={max_pos} SL={stop_loss:.0%} H={max_hold}d {pool_name}"
        try:
            r = run_once(model, features, scaler, factor_data, price_data, config)
            r["config_key"] = key
            r["config"] = config
            results.append(r)
        except Exception as e:
            logger.warning("Failed: %s — %s", key, str(e)[:80])

    # 排序：按总收益
    results.sort(key=lambda r: r["total_return"], reverse=True)

    print("\n" + "=" * 100)
    print("  LightGBM ETF 底部策略 — 参数扫描结果（按总收益排序）")
    print("=" * 100)
    header = f"{'Rank':<5} {'Threshold':>8} {'Pos':>4} {'StopLoss':>8} {'HoldDays':>6} {'Pool':<10} {'Return':>8} {'Trades':>6} {'Win%':>6} {'PF':>6} {'AvgWin':>7} {'AvgLoss':>7} {'TimeStop':>8} {'Config'}"
    print(header)
    print("-" * 100)
    for i, r in enumerate(results[:20]):
        cfg = r["config"]
        print(f"{i+1:<5} {cfg['threshold']:>8.2f} {cfg['max_positions']:>4} "
              f"{cfg['stop_loss']:>8.0%} {cfg['max_hold_days']:>6} "
              f"{'high_beta' if len(cfg['etf_pool'])==22 else 'all':<10} "
              f"{r['total_return']:>7.2%} {r['n_trades']:>6} {r['win_rate']:>5.1%} "
              f"{r['profit_factor']:>5.1f} {r['avg_win']:>6.1%} {r['avg_loss']:>6.1%} "
              f"{r['time_stop_pct']:>7.0%}")

    # Best config
    best = results[0]
    print("\n" + "=" * 60)
    print("  🏆 最优配置")
    print("=" * 60)
    cfg = best["config"]
    pool_label = "high_beta (22 ETFs)" if len(cfg["etf_pool"]) == 22 else "all (27 ETFs)"
    print(f"  threshold:         {cfg['threshold']:.2f}")
    print(f"  max_positions:     {cfg['max_positions']}")
    print(f"  stop_loss:         {cfg['stop_loss']:.0%}")
    print(f"  max_hold_days:     {cfg['max_hold_days']}")
    print(f"  trail_activate:    {BASE_PARAMS['trail_activate']:.0%}")
    print(f"  trail_distance:    {BASE_PARAMS['trail_distance']:.0%}")
    print(f"  max_single_pos:    {BASE_PARAMS['max_single_position']:.0%}")
    print(f"  etf_pool:          {pool_label}")
    print(f"  ─────────────────────────────")
    print(f"  总收益:            {best['total_return']:+.2%}")
    print(f"  交易次数:          {best['n_trades']}")
    print(f"  胜率:              {best['win_rate']:.1%}")
    print(f"  平均盈利:          {best['avg_win']:+.1%}")
    print(f"  平均亏损:          {best['avg_loss']:+.1%}")
    print(f"  盈亏比:            {best['profit_factor']:.1f}")
    print(f"  time_stop 占比:    {best['time_stop_pct']:.0%}")
    print(f"  trail_stop 占比:   {best['trail_pct']:.0%}")
    print(f"  stop_loss 占比:    {best['stop_loss_pct']:.0%}")
    print(f"  平均持仓天数:      {best['avg_hold']:.1f}")

    # vs baseline
    baseline = [r for r in results if r["config"]["threshold"] == 0.40
                and r["config"]["max_positions"] == 5
                and r["config"]["stop_loss"] == -0.08
                and r["config"]["max_hold_days"] == 20
                and len(r["config"]["etf_pool"]) == 27]
    if baseline:
        bl = baseline[0]
        print(f"\n  vs 保守基线 (T=0.40 P=5 SL=-8% H=20d all):")
        print(f"    收益: {bl['total_return']:+.2%} → {best['total_return']:+.2%} "
              f"({best['total_return']/bl['total_return']-1:+.0%})")
        print(f"    交易: {bl['n_trades']} → {best['n_trades']}")
        print(f"    胜率: {bl['win_rate']:.1%} → {best['win_rate']:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
