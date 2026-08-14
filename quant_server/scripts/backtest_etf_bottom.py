# -*- coding: utf-8 -*-
"""
LightGBM ETF 底部策略 — 快速信号级回测
=======================================
加载训练好的模型 → 在测试集上生成信号 → 模拟持仓退出 → 计算绩效

执行: cd quant_server && .venv/Scripts/python.exe scripts/backtest_etf_bottom.py
"""
import asyncio, logging, math, sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

import asyncpg
import joblib
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB = {"host": "localhost", "port": 5432, "user": "postgres", "password": "123456", "database": "quant_signals_dev"}
MODEL_PATH = Path(__file__).resolve().parent.parent / "storage" / "models"

# ── 回测参数 ──
THRESHOLD = None        # None=使用模型 artifact 的最优阈值（推荐）

# P2: 分 Regime 阈值调整系数
# 理念：震荡市中底部信号质量最高（积极），牛/熊市中假信号多（谨慎）
# market_regime: 0=BEAR(熊), 1=NEUTRAL(震荡), 2=BULL(牛)
REGIME_THRESHOLD_FACTOR = {
    0: 1.10,  # 熊市：阈值上浮10%，只接最确定的高赔率底
    1: 0.85,  # 震荡市：阈值下调15%，积极捕捉每个底部信号
    2: 1.08,  # 牛市：阈值上浮8%，牛回调多为假底，不追
}
# 默认 regime（当 factor_data 中没有 market_regime 时使用）
DEFAULT_REGIME = 1  # 默认当作震荡市
MAX_POSITIONS = 5      # 最大持仓数
STOP_LOSS = -0.05      # 硬止损 -5%
TRAIL_ACTIVATE = 0.05  # 移动止盈启动（左侧适配）
TRAIL_DISTANCE = 0.05  # 回撤容忍
MAX_HOLD_DAYS = 20     # 最大持有天数（左侧适配，给磨底留时间）
COOLING_DAYS = 2       # 冷却天数

# ── P3: 波动率前置过滤 ──
VOL_FILTER_ENABLED = True
VOL_FILTER_ATR_MIN = 0.015   # ATR(14)/close >= 1.5%

# ── P4: 入场确认延迟 ──
CONFIRM_ENABLED = True

# ── P5: 极端值清洗 ──
EXTREME_FILTER_ENABLED = True
EXTREME_GAP_THRESHOLD = 0.12
INITIAL_CAPITAL = 1_000_000
COMMISSION = 0.0001    # 万分之一佣金（万一免五）


async def load_model():
    """加载最新模型"""
    files = sorted(MODEL_PATH.glob("etf_bottom_v1_*.joblib"))
    if not files:
        raise FileNotFoundError("No model found")
    path = files[-1]
    logger.info("加载模型: %s", path.name)
    artifact = joblib.load(path)
    return (
        artifact["model"],
        artifact["feature_names"],
        artifact.get("scaler_params", {}),
        float(artifact.get("threshold", THRESHOLD)),
    )


async def load_data(conn, feature_names, start, end):
    """加载特征 + 价格数据（限制 Top300 流动性 ETF 防止内存溢出）"""
    # 因子数据 — 只加载成交量最大的 N 只 ETF
    flist = "','".join(feature_names)
    rows = await conn.fetch(f"""
        WITH top_etfs AS (
            SELECT ts_code FROM etf_daily
            WHERE trade_date >= $1 AND trade_date <= $2
            GROUP BY ts_code
            ORDER BY AVG(vol) DESC
            LIMIT 500
        )
        SELECT f.ts_code, f.trade_date::text, f.factor_code, f.factor_value
        FROM factor_data f
        JOIN top_etfs t ON f.ts_code = t.ts_code
        WHERE f.trade_date >= $1 AND f.trade_date <= $2
          AND f.factor_code = ANY(ARRAY['{flist}']::varchar[])
        ORDER BY f.ts_code, f.trade_date
    """, start, end)

    # 转宽表
    factor_data = {}
    for r in rows:
        key = (r["ts_code"], r["trade_date"])
        if key not in factor_data:
            factor_data[key] = {}
        v = r["factor_value"]
        factor_data[key][r["factor_code"]] = float(v) if v is not None else np.nan
    logger.info("因子: %d samples", len(factor_data))

    # 价格数据 — 同上，只取 Top500
    prices = await conn.fetch("""
        WITH top_etfs AS (
            SELECT ts_code FROM etf_daily
            WHERE trade_date >= $1 AND trade_date <= $2
            GROUP BY ts_code
            ORDER BY AVG(vol) DESC
            LIMIT 500
        )
        SELECT e.ts_code, e.trade_date::text, e.open, e.high, e.low, e.close, e.pre_close
        FROM etf_daily e
        JOIN top_etfs t ON e.ts_code = t.ts_code
        WHERE e.trade_date >= $1 AND e.trade_date <= $2
        ORDER BY e.ts_code, e.trade_date
    """, start, end)
    price_data = {}
    for r in prices:
        key = (r["ts_code"], r["trade_date"])
        price_data[key] = {
            "open": float(r["open"]), "high": float(r["high"]),
            "low": float(r["low"]), "close": float(r["close"]),
            "pre_close": float(r["pre_close"]),
        }
    logger.info("价格: %d samples", len(price_data))

    return factor_data, price_data


def standardize(features, mu, sigma):
    """标准化特征向量"""
    if mu and sigma:
        return (features - np.array(mu)) / (np.array(sigma) + 1e-8)
    return features


def _enter_trade(etf, td, bar, proba, regime_val, positions, available, capital, day_threshold=None):
    """执行入场：计算仓位 → 扣除资金 → 记录持仓"""
    weight = max(0.03, 0.40) if day_threshold is None else \
        max(0.03, (proba - day_threshold) / max(1 - day_threshold, 0.01)) * 0.40
    alloc = available * weight
    shares = int(alloc / bar["close"] / 100) * 100
    if shares < 100:
        return 0
    cost = shares * bar["close"] * (1 + COMMISSION)
    if cost > available * 0.45:
        cost = available * 0.45
        shares = int(cost / (bar["close"] * (1 + COMMISSION)) / 100) * 100
        cost = shares * bar["close"] * (1 + COMMISSION)
    if shares < 100:
        return 0
    positions[etf] = {
        "entry_price": bar["close"],
        "entry_date": date.fromisoformat(td),
        "shares": shares,
        "cost": cost,
        "peak": bar["high"],
        "regime": regime_val,
        "entry_proba": proba,
        "entry_low": bar["low"],
    }
    return cost


def run_backtest(model, feature_names, scaler, factor_data, price_data, threshold=0.30):
    """运行信号级回测"""
    mu = scaler.get("mu", [])
    sigma = scaler.get("sigma", [])

    # 收集所有交易日 + ETF
    all_dates = sorted(set(k[1] for k in price_data.keys()))
    etfs = sorted(set(k[0] for k in price_data.keys()))
    logger.info("回测区间: %s ~ %s, %d ETFs, %d 交易日",
                all_dates[0], all_dates[-1], len(etfs), len(all_dates))
    if VOL_FILTER_ENABLED or CONFIRM_ENABLED:
        filters = []
        if VOL_FILTER_ENABLED: filters.append(f"P3-vol>={VOL_FILTER_ATR_MIN:.1%}")
        if CONFIRM_ENABLED: filters.append("P4-confirm")
        if EXTREME_FILTER_ENABLED: filters.append("P5-extreme")
        logger.info("优化开关: %s", ", ".join(filters))

    # 生成每日信号
    predictions = []  # [(date, ts_code, proba, close)]
    for td in all_dates:
        for etf in etfs:
            fkey = (etf, td)
            pkey = (etf, td)
            if fkey not in factor_data or pkey not in price_data:
                continue
            # 提取特征向量
            fvals = [factor_data[fkey].get(fn, np.nan) for fn in feature_names]
            farr = np.array(fvals, dtype=np.float64)
            if np.isnan(farr).mean() > 0.5:  # >50% NaN → skip
                continue
            farr = np.nan_to_num(farr, nan=0.0)
            farr = standardize(farr.reshape(1, -1), mu, sigma)
            proba = model.predict_proba(farr)[0, 1]
            close = price_data[pkey]["close"]
            predictions.append((td, etf, proba, close))

    df = pd.DataFrame(predictions, columns=["date", "ts_code", "proba", "close"])

    # 只保留训练池 ETF（有完整因子数据 >= 1000 天 → 排除未训练的小 ETF）
    etf_factor_counts = df.groupby('ts_code')['proba'].count()
    valid_etfs = set(etf_factor_counts[etf_factor_counts > 1000].index)
    df = df[df['ts_code'].isin(valid_etfs)]
    logger.info("预测总数: %d, 有效ETF: %d", len(df), len(valid_etfs))

    df = df.sort_values(["date", "proba"], ascending=[True, False])

    # ── 模拟交易 ──
    capital = INITIAL_CAPITAL
    available = capital
    positions: Dict[str, dict] = {}
    # P3: 组合风控状态
    daily_pnl = 0.0
    weekly_pnl = 0.0
    prev_equity = capital
    consecutive_losses = 0
    circuit_breaker_until = None  # date string
    week_start_equity = capital  # ts_code → {entry_price, entry_date, shares, peak}
    cooling: Dict[str, int] = {}
    pending: Dict[str, dict] = {}   # P4: ts_code → {proba, signal_date, signal_low, close, regime}
    trades: List[dict] = []
    equity_curve = []
    p5_skipped = 0  # P5 counter

    for td in all_dates:
        day_preds = df[df["date"] == td]

        # P5 helper: check if a bar has extreme gap (data anomaly)
        def _is_extreme_bar(bar):
            if not EXTREME_FILTER_ENABLED:
                return False
            gap = abs(bar["close"] / bar["pre_close"] - 1) if bar["pre_close"] > 0 else 0
            return gap > EXTREME_GAP_THRESHOLD

        # ── 1. 检查出场 ──
        for etf in list(positions.keys()):
            pkey = (etf, td)
            if pkey not in price_data:
                continue
            bar = price_data[pkey]
            pos = positions[etf]
            pnl = bar["close"] / pos["entry_price"] - 1
            hold_days = (date.fromisoformat(td) - pos["entry_date"]).days

            # P5: 极端日不执行止损（数据异常，等下一个正常日再判）
            skip_exit_check = _is_extreme_bar(bar)

            # 更新最高价
            pos["peak"] = max(pos["peak"], bar["high"])
            if "entry_low" not in pos:
                pos["entry_low"] = pos["entry_price"]
            pos["entry_low"] = min(pos["entry_low"], bar["low"])
            dd_from_peak = (pos["peak"] - bar["close"]) / pos["peak"] if pos["peak"] > 0 else 0

            exit_reason = None
            # P5: 单笔亏损 > 15% → 数据异常 → 按-15%强平
            if pnl < -0.15:
                pnl = -0.15
                exit_reason = "data_anomaly"
            elif not skip_exit_check:
                # v10: 分阶段止损
                if hold_days <= 3:
                    effective_stop = -0.07
                    if pnl < effective_stop and pnl < -0.05:  # 收盘收回-5%内豁免
                        exit_reason = "grind_stop"
                else:
                    if bar["close"] >= pos["entry_low"]:
                        effective_stop = -0.05
                    else:
                        effective_stop = -0.07
                    if pnl < effective_stop:
                        exit_reason = "stop_loss"

                # v10: 时间止损 — 放宽到 20 天兜底（模型驱动离场仅在策略类中生效）
                if not exit_reason and MAX_HOLD_DAYS > 0 and hold_days >= 20:
                    exit_reason = "time_stop"

                # v10: 分档移动止盈
                if not exit_reason:
                    float_pnl = pos["peak"] / pos["entry_price"] - 1
                    if float_pnl >= TRAIL_ACTIVATE:
                        trail_dist = 0.06 if float_pnl >= 0.10 else 0.04
                        if dd_from_peak >= trail_dist:
                            exit_reason = "tier_trail"

            if exit_reason:
                exit_value = pos["shares"] * bar["close"] * (1 - COMMISSION)
                if exit_reason == "data_anomaly":
                    exit_value = pos["cost"] * (1 + pnl)
                pnl_amt = exit_value - pos["cost"]
                available += exit_value
                # P3: track consecutive stop losses
                if exit_reason in ('stop_loss', 'grind_stop'):
                    consecutive_losses += 1
                else:
                    consecutive_losses = max(0, consecutive_losses - 1)
                trades.append({
                    "entry_date": pos["entry_date"].isoformat(),
                    "exit_date": td,
                    "ts_code": etf,
                    "entry_price": pos["entry_price"],
                    "exit_price": bar["close"],
                    "pnl_pct": pnl,
                    "pnl_amt": pnl_amt,
                    "hold_days": hold_days,
                    "reason": exit_reason,
                    "regime": pos.get("regime", -1),
                })
                cooling[etf] = COOLING_DAYS
                del positions[etf]

        # ── 2. 更新冷却期 ──
        for etf in list(cooling.keys()):
            cooling[etf] -= 1
            if cooling[etf] <= 0:
                del cooling[etf]

        # ── 3. P4: 处理昨日的 pending 信号 → 今日确认或丢弃 ──
        if CONFIRM_ENABLED and pending:
            for etf in list(pending.keys()):
                pinfo = pending[etf]
                pkey = (etf, td)
                if pkey not in price_data:
                    continue
                bar = price_data[pkey]

                # 确认条件: 今日 close > 信号日 low（没有继续创新低）
                if bar["close"] > pinfo["signal_low"] and etf not in positions and etf not in cooling:
                    # 确认通过 → 以今日收盘价入场
                    cost = _enter_trade(
                        etf, td, bar, pinfo["proba"], pinfo["regime"],
                        positions, available, capital)
                    if cost > 0:
                        available -= cost
                # 否则丢弃信号
                del pending[etf]

        # ── 4. 计算当日 Regime 阈值 ──
        regime_val = DEFAULT_REGIME
        for etf in etfs:
            rv = factor_data.get((etf, td), {}).get("market_regime")
            if rv is not None and not np.isnan(rv):
                regime_val = int(rv)
                break
        regime_factor = REGIME_THRESHOLD_FACTOR.get(regime_val, 1.0)
        day_threshold = threshold * regime_factor

        # ── 5. 生成新信号 ──
        if len(positions) + len(pending) < MAX_POSITIONS and available > capital * 0.05:
            for _, row in day_preds.iterrows():
                etf = row["ts_code"]
                if etf in positions or etf in cooling or etf in pending:
                    continue
                if row["proba"] < day_threshold:
                    continue
                if len(positions) + len(pending) >= MAX_POSITIONS:
                    break

                pkey = (etf, td)
                if pkey not in price_data:
                    continue
                bar = price_data[pkey]

                # P5: 极端异常日跳过
                if _is_extreme_bar(bar):
                    p5_skipped += 1
                    continue

                # P3: 波动率过滤 — ATR(14)/close >= 阈值
                if VOL_FILTER_ENABLED:
                    atr_ratio = factor_data.get((etf, td), {}).get("atr_ratio_20")
                    if atr_ratio is None or np.isnan(atr_ratio) or atr_ratio < VOL_FILTER_ATR_MIN:
                        continue

                if CONFIRM_ENABLED:
                    # P4: 不立即入场，存入 pending 等待次日确认
                    pending[etf] = {
                        "proba": row["proba"],
                        "signal_date": td,
                        "signal_low": bar["low"],
                        "close": bar["close"],
                        "regime": regime_val,
                    }
                else:
                    # 直接入场
                    cost = _enter_trade(
                        etf, td, bar, row["proba"], regime_val,
                        positions, available, capital, day_threshold)
                    if cost > 0:
                        available -= cost

        # ── 6. 记录权益曲线 ──
        position_value = sum(
            positions[e]["shares"] * price_data.get((e, td), {}).get("close",
            positions[e]["entry_price"])
            for e in positions
        )
        total_equity = available + position_value
        equity_curve.append((td, total_equity, len(positions)))

    # ── 绩效分析 ──
    eq_df = pd.DataFrame(equity_curve, columns=["date", "equity", "positions"])
    eq_df["date"] = pd.to_datetime(eq_df["date"])
    eq_df["return"] = eq_df["equity"].pct_change()

    # 年化收益
    days = (eq_df["date"].iloc[-1] - eq_df["date"].iloc[0]).days
    total_return = (eq_df["equity"].iloc[-1] / INITIAL_CAPITAL - 1)
    annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

    # 最大回撤
    peak = eq_df["equity"].expanding().max()
    drawdown = (eq_df["equity"] - peak) / peak
    max_dd = drawdown.min()

    # 夏普比
    risk_free = 0.025
    excess = eq_df["return"].dropna() - risk_free / 252
    sharpe = excess.mean() / excess.std() * math.sqrt(252) if excess.std() > 0 else 0

    # 胜率
    if trades:
        win_trades = [t for t in trades if t["pnl_pct"] > 0]
        win_rate = len(win_trades) / len(trades)
        avg_win = np.mean([t["pnl_pct"] for t in win_trades]) if win_trades else 0
        avg_loss = np.mean([t["pnl_pct"] for t in trades if t["pnl_pct"] <= 0]) if len(trades) > len(win_trades) else 0
        avg_hold = np.mean([t["hold_days"] for t in trades])
        total_pnl = sum(t["pnl_amt"] for t in trades)
        profit_factor = abs(sum(t["pnl_amt"] for t in win_trades) / sum(t["pnl_amt"] for t in trades if t["pnl_pct"] <= 0)) if any(t["pnl_pct"] <= 0 for t in trades) else float("inf")
    else:
        win_rate = avg_win = avg_loss = avg_hold = total_pnl = profit_factor = 0

    # 按年分析
    trade_df = pd.DataFrame(trades)
    if not trade_df.empty:
        trade_df["exit_date"] = pd.to_datetime(trade_df["exit_date"])
        trade_df["year"] = trade_df["exit_date"].dt.year
        yearly = trade_df.groupby("year").agg(
            trades=("pnl_pct", "count"),
            win_rate=("pnl_pct", lambda x: (x > 0).mean()),
            avg_return=("pnl_pct", "mean"),
            total_pnl=("pnl_amt", "sum"),
        )
    else:
        yearly = pd.DataFrame()

    # ── 输出 ──
    print("\n" + "=" * 60)
    print("  LightGBM ETF 底部策略 — 回测结果")
    print("=" * 60)
    print(f"  回测区间: {all_dates[0]} ~ {all_dates[-1]} ({days} 天)")
    print(f"  初始资金: {INITIAL_CAPITAL:,.0f}")
    print(f"  最终资金: {eq_df['equity'].iloc[-1]:,.0f}")
    print(f"  总收益: {total_return:+.2%}")
    print(f"  年化收益: {annual_return:+.2%}")
    print(f"  最大回撤: {max_dd:.2%}")
    print(f"  夏普比: {sharpe:.2f}")
    print(f"  交易次数: {len(trades)}")
    print(f"  胜率: {win_rate:.1%}")
    print(f"  平均盈利: {avg_win:+.2%}  |  平均亏损: {avg_loss:+.2%}")
    print(f"  盈亏比: {profit_factor:.2f}")
    print(f"  平均持仓: {avg_hold:.1f} 天")
    print(f"  总盈亏: {total_pnl:+,.0f}")

    if not yearly.empty:
        print("\n  ── 分年表现 ──")
        print(f"  {'Year':<6} {'Trades':>7} {'Win%':>8} {'AvgRet':>9} {'PnL':>12}")
        for yr, row in yearly.iterrows():
            print(f"  {int(yr):<6} {int(row['trades']):>7} {row['win_rate']:>7.1%} "
                  f"{row['avg_return']:>8.2%} {row['total_pnl']:>+11,.0f}")

    # 交易频率
    if not trade_df.empty:
        print("\n  ── 出场原因分布 ──")
        for reason in ["stop_loss", "grind_stop", "time_stop", "max_hold", "tier_trail", "data_anomaly"]:
            cnt = len(trade_df[trade_df["reason"] == reason])
            print(f"  {reason}: {cnt} ({cnt/len(trade_df):.0%})")

    # P2: Regime 维度的交易统计
    REGIME_NAMES = {0: "熊市", 1: "震荡", 2: "牛市"}
    if not trade_df.empty:
        print("\n  ── 各 Regime 交易表现 ──")
        for rv in [0, 1, 2]:
            rt = trade_df[trade_df["regime"] == rv]
            if len(rt) == 0:
                continue
            wr = (rt["pnl_pct"] > 0).mean()
            avg_ret = rt["pnl_pct"].mean()
            total_pnl = rt["pnl_amt"].sum()
            print(f"  {REGIME_NAMES.get(rv, str(rv))}: "
                  f"{len(rt)}笔, 胜率{wr:.0%}, 均收益{avg_ret:+.1%}, 总PnL{total_pnl:+,.0f}")

    # Top/Bottom trades
    if len(trades) >= 5:
        sorted_trades = sorted(trades, key=lambda t: t["pnl_pct"])
        print("\n  ── 最佳 5 笔 ──")
        for t in sorted_trades[-5:]:
            print(f"  {t['ts_code']} {t['entry_date']}→{t['exit_date']}: "
                  f"{t['pnl_pct']:+.1%} ({t['hold_days']}d, {t['reason']})")
        print("  ── 最差 5 笔 ──")
        for t in sorted_trades[:5]:
            print(f"  {t['ts_code']} {t['entry_date']}→{t['exit_date']}: "
                  f"{t['pnl_pct']:+.1%} ({t['hold_days']}d, {t['reason']})")

    stats = {"p5_skipped": p5_skipped}
    if VOL_FILTER_ENABLED or CONFIRM_ENABLED or EXTREME_FILTER_ENABLED:
        print(f"\n  ── P3/P4/P5 优化统计 ──")
        if VOL_FILTER_ENABLED:
            print(f"  P3 波动率过滤: ATR/close >= {VOL_FILTER_ATR_MIN:.1%} 才入场")
        if CONFIRM_ENABLED:
            print(f"  P4 入场确认: 信号次日 close>信号日low 才入场")
        if EXTREME_FILTER_ENABLED:
            print(f"  P5 极端值清洗: 跳过 {p5_skipped} 个异常信号 (单日涨跌幅>{EXTREME_GAP_THRESHOLD:.0%})")
    return eq_df, trades


async def main():
    # 确定回测区间
    start = date(2021, 1, 1)
    end = date(2026, 7, 31)  # 覆盖完整牛熊周期：2021牛市→2022熊市→2023-2024震荡→2025修复

    model, features, scaler, saved_threshold = await load_model()
    threshold = THRESHOLD if THRESHOLD is not None else saved_threshold
    logger.info("阈值: artifact=%.2f, 回测用=%.2f", saved_threshold, threshold)

    conn = await asyncpg.connect(**DB)
    try:
        factor_data, price_data = await load_data(conn, features, start, end)
        eq_df, trades = run_backtest(model, features, scaler, factor_data, price_data, threshold)

        # 保存权益曲线
        out_path = MODEL_PATH.parent / "backtest_equity.csv"
        eq_df.to_csv(out_path, index=False)
        logger.info("权益曲线已保存: %s", out_path)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
