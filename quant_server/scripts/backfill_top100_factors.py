# -*- coding: utf-8 -*-
"""
一次性回填 Top100 ETF 的全部 OHLCV 因子
========================================
加载 etf_daily → 逐 ETF 批量计算 36 个因子 → 写入 factor_data

执行: cd quant_server && .venv/Scripts/python.exe scripts/backfill_top100_factors.py
预估耗时: ~15-20 分钟
"""
import asyncio, logging, uuid
from datetime import date
from typing import Dict, List

import asyncpg
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB = {"host": "localhost", "port": 5432, "user": "postgres", "password": "123456", "database": "quant_signals_dev"}

TOP_N = 0   # 0=不限数量，回填所有符合条件（日波动>=0.5%）的ETF
MIN_VOL = 0.005  # 最低日波动率（过滤货币/债券ETF）

# ── 因子定义: {factor_code: compute_fn(df_single_etf) -> pd.Series} ──

def _tr(df):
    """True Range"""
    pc = df["pre_close"]
    return pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs(),
    ], axis=1).max(axis=1)


def _rsi(df, period):
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.rolling(period, min_periods=period).mean()
    avg_loss = loss.rolling(period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _rsi_low_days(df, threshold=30, lookback=60):
    rsi = _rsi(df, 14)
    return (rsi < threshold).astype(int).rolling(lookback, min_periods=1).sum()


def _roll_max(series, w, mp):
    return series.rolling(w, min_periods=mp).max()


def _roll_min(series, w, mp):
    return series.rolling(w, min_periods=mp).min()


def f_drawdown_20d(df):
    rm = _roll_max(df["high"], 20, 5)
    return (df["close"] - rm) / rm


def f_drawdown_60d(df):
    rm = _roll_max(df["high"], 60, 10)
    return (df["close"] - rm) / rm


def f_drawdown_120d(df):
    rm = _roll_max(df["high"], 120, 20)
    return (df["close"] - rm) / rm


def f_rsi_6(df):
    return _rsi(df, 6)


def f_rsi_14(df):
    return _rsi(df, 14)


def f_rsi_28(df):
    return _rsi(df, 28)


def f_rsi_low_days(df):
    return _rsi_low_days(df)


def f_ma_disparity(df, w, mp):
    ma = df["close"].rolling(w, min_periods=mp).mean()
    return (df["close"] - ma) / ma


def f_ma_disparity_20(df):
    return f_ma_disparity(df, 20, 5)


def f_ma_disparity_60(df):
    return f_ma_disparity(df, 60, 10)


def f_ma_disparity_120(df):
    return f_ma_disparity(df, 120, 20)


def f_close_to_low_20d(df):
    rm = _roll_min(df["low"], 20, 5)
    return (df["close"] - rm) / df["close"]


def f_price_position_250d(df):
    lo = _roll_min(df["low"], 250, 20)
    hi = _roll_max(df["high"], 250, 20)
    denom = hi - lo
    denom = denom.replace(0, np.nan)
    return (df["close"] - lo) / denom


def f_momentum(df, n):
    return df["close"] / df["close"].shift(n) - 1


def f_momentum_3d(df):
    return f_momentum(df, 3)


def f_momentum_5d(df):
    return f_momentum(df, 5)


def f_consecutive_down_days(df):
    down = (df["close"] < df["pre_close"])
    return down.astype(int).groupby((down != down.shift()).cumsum()).cumsum().astype(float)


def f_atr(df, period):
    return _tr(df).rolling(period, min_periods=5).mean()


def f_atr_14(df):
    return f_atr(df, 14)


def f_atr_ratio_20(df):
    return f_atr(df, 14) / df["close"]


def f_atr_ratio(df):
    atr5 = f_atr(df, 5)
    atr20 = f_atr(df, 20)
    return atr5 / atr20.replace(0, np.nan)


def f_amplitude_5d(df):
    amp = (df["high"] - df["low"]) / df["pre_close"]
    return amp.rolling(5, min_periods=2).mean()


def f_max_dd_duration(df):
    roll_peak = df["close"].rolling(60, min_periods=10).max()
    below = (df["close"] < roll_peak.shift(1)).astype(int)
    return below.groupby((below != below.shift()).cumsum()).cumsum()


def f_std_20d(df):
    ret = df["close"].pct_change()
    return ret.rolling(20, min_periods=5).std()


def f_boll_width(df):
    mid = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    return 4.0 * std / mid


def f_boll_pct_b(df):
    mid = df["close"].rolling(20).mean()
    std = df["close"].rolling(20).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    denom = upper - lower
    denom = denom.replace(0, np.nan)
    return (df["close"] - lower) / denom


def f_volume_shrink(df, w, mp):
    ma = df["vol"].rolling(w, min_periods=mp).mean()
    return df["vol"] / ma


def f_volume_shrink_5d(df):
    return f_volume_shrink(df, 5, 3)


def f_volume_shrink_20d(df):
    return f_volume_shrink(df, 20, 5)


def f_volume_ma20_ratio(df):
    return f_volume_shrink(df, 20, 5)


def f_vol_trend(df):
    ma5 = df["vol"].rolling(5, min_periods=3).mean()
    ma20 = df["vol"].rolling(20, min_periods=5).mean()
    return ma5 / ma20.replace(0, np.nan)


def f_vol_decline_corr(df):
    ret = df["close"].pct_change()
    return df["vol"].rolling(20).corr(ret)


def f_vol_spike_count(df):
    ma20 = df["vol"].rolling(20, min_periods=5).mean()
    ret = df["close"].pct_change()
    spike = ((df["vol"] > 1.5 * ma20) & (ret < 0)).astype(int)
    return spike.rolling(10, min_periods=1).sum()


def f_amount_change_5d(df):
    if "amount" not in df.columns:
        return pd.Series(np.nan, index=df.index)
    ma5 = df["amount"].rolling(5, min_periods=3).mean()
    return df["amount"] / ma5


def f_pct_chg_abs_mean_5d(df):
    if "pct_chg" in df.columns:
        abs_ret = df["pct_chg"].abs()
    else:
        abs_ret = df["close"].pct_change().abs()
    return abs_ret.rolling(5, min_periods=2).mean()


def f_high_vol_days_5d(df):
    ma20 = df["vol"].rolling(20, min_periods=5).mean()
    high = (df["vol"] > 1.5 * ma20).astype(int)
    return high.rolling(5, min_periods=1).sum()


def f_turnover_change_5d(df):
    if "turnover_rate" not in df.columns:
        return pd.Series(np.nan, index=df.index)
    ma5 = df["turnover_rate"].rolling(5, min_periods=3).mean()
    return df["turnover_rate"] / ma5


def f_volume_dry_up(df):
    ret = df["close"].pct_change()
    down = (ret < 0).astype(int)
    down_streak = down.groupby((down != down.shift()).cumsum()).cumsum()
    vol = df["vol"]
    vol_dec = (
        (vol < vol.shift(1)) &
        (vol.shift(1) < vol.shift(2))
    ).astype(int)
    return ((down_streak >= 5) & (vol_dec == 1)).astype(float)


def f_vwap_distance(df):
    if "amount" not in df.columns:
        return pd.Series(np.nan, index=df.index)
    tp = (df["high"] + df["low"] + df["close"]) / 3
    vp = tp * df["vol"]
    cvp = vp.rolling(20, min_periods=5).sum()
    cvol = df["vol"].rolling(20, min_periods=5).sum()
    vwap = cvp / cvol.replace(0, np.nan)
    return (df["close"] - vwap) / vwap


def f_obv_divergence(df):
    ret = df["close"].pct_change()
    obv_sign = ret.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (obv_sign * df["vol"]).cumsum()
    close_20_low = df["close"].rolling(20, min_periods=10).min()
    obv_20_low = obv.rolling(20, min_periods=10).min()
    close_at_low = (df["close"] <= close_20_low * 1.01).astype(int)
    obv_not_at_low = (obv > obv_20_low * 1.02).astype(int)
    return (close_at_low & obv_not_at_low).astype(float)


# ── ADX 系列 ──
def f_adx_14(df):
    """ADX(14) Wilder smoothing"""
    period = 14
    h, l, c = df["high"], df["low"], df["close"]
    up_move = h - h.shift(1)
    down_move = l.shift(1) - l
    pos_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    neg_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = pd.concat([h - l, (h - c.shift(1)).abs(), (l - c.shift(1)).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100.0 * pos_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_safe
    minus_di = 100.0 * neg_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr_safe
    di_sum = plus_di + minus_di
    dx = (100.0 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan))
    return dx.ewm(alpha=1.0 / period, adjust=False).mean()


# ── 因子注册表 ──
FACTOR_REGISTRY: Dict[str, callable] = {
    "drawdown_20d": f_drawdown_20d,
    "drawdown_60d": f_drawdown_60d,
    "drawdown_120d": f_drawdown_120d,
    "rsi_6": f_rsi_6,
    "rsi_14": f_rsi_14,
    "rsi_28": f_rsi_28,
    "rsi_low_days": f_rsi_low_days,
    "ma_disparity_20": f_ma_disparity_20,
    "ma_disparity_60": f_ma_disparity_60,
    "ma_disparity_120": f_ma_disparity_120,
    "close_to_low_20d": f_close_to_low_20d,
    "price_position_250d": f_price_position_250d,
    "momentum_3d": f_momentum_3d,
    "momentum_5d": f_momentum_5d,
    "consecutive_down_days": f_consecutive_down_days,
    "atr_14": f_atr_14,
    "atr_ratio_20": f_atr_ratio_20,
    "atr_ratio": f_atr_ratio,
    "amplitude_5d": f_amplitude_5d,
    "max_dd_duration": f_max_dd_duration,
    "std_20d": f_std_20d,
    "boll_width": f_boll_width,
    "boll_pct_b": f_boll_pct_b,
    "volume_shrink_5d": f_volume_shrink_5d,
    "volume_shrink_20d": f_volume_shrink_20d,
    "volume_ma20_ratio": f_volume_ma20_ratio,
    "vol_trend": f_vol_trend,
    "vol_decline_corr": f_vol_decline_corr,
    "vol_spike_count": f_vol_spike_count,
    "amount_change_5d": f_amount_change_5d,
    "pct_chg_abs_mean_5d": f_pct_chg_abs_mean_5d,
    "high_vol_days_5d": f_high_vol_days_5d,
    "turnover_change_5d": f_turnover_change_5d,
    "volume_dry_up": f_volume_dry_up,
    "vwap_distance": f_vwap_distance,
    "obv_divergence": f_obv_divergence,
    "adx_14": f_adx_14,
}
N_FACTORS = len(FACTOR_REGISTRY)


async def main():
    conn = await asyncpg.connect(**DB)
    try:
        # 1. 获取 ETF 池：高波动 + 充足交易日 + 无已有因子数据（或强制全量时包含已有）
        #    使用两层 CTE 避免窗口函数与聚合函数混用
        limit_clause = "" if TOP_N == 0 else f"LIMIT {TOP_N}"
        rows = await conn.fetch(f"""
            WITH daily_ret AS (
                SELECT ts_code, trade_date, vol,
                       close / LAG(close) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1 AS ret
                FROM etf_daily
                WHERE trade_date >= '2024-01-01'
            ),
            etf_vol AS (
                SELECT ts_code,
                       AVG(vol) AS avg_vol,
                       STDDEV(ret) AS daily_vol,
                       COUNT(*) AS n_days
                FROM daily_ret
                WHERE ret IS NOT NULL
                GROUP BY ts_code
                HAVING COUNT(*) >= 200
                   AND STDDEV(ret) >= {MIN_VOL}
            ),
            etf_total AS (
                SELECT ts_code, COUNT(*) total_days
                FROM etf_daily
                WHERE trade_date >= '2020-01-01'
                GROUP BY ts_code
                HAVING COUNT(*) >= 250
            )
            SELECT v.ts_code, v.daily_vol, v.avg_vol, v.n_days, t.total_days
            FROM etf_vol v
            JOIN etf_total t ON v.ts_code = t.ts_code
            ORDER BY v.avg_vol DESC
            {limit_clause}
        """)
        etf_pool = [r["ts_code"] for r in rows]
        logger.info("符合条件的 ETF: %d 只 (日波动>=%.1f%%, 交易>=250天)", len(etf_pool), MIN_VOL * 100)

        # 2. 加载 etf_daily 数据
        etf_list = "','".join(etf_pool)
        rows = await conn.fetch(f"""
            SELECT ts_code, trade_date, open, high, low, close, pre_close, vol, amount, pct_chg
            FROM etf_daily
            WHERE ts_code = ANY(ARRAY['{etf_list}']::varchar[])
              AND trade_date >= '2020-01-01'
            ORDER BY ts_code, trade_date
        """)
        logger.info("加载 etf_daily: %d 行", len(rows))

        df = pd.DataFrame([dict(r) for r in rows])
        for c in ["open", "high", "low", "close", "pre_close", "vol", "amount", "pct_chg"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["trade_date"] = pd.to_datetime(df["trade_date"])

        # 3. 筛选需回填的 ETF（不去重——ON CONFLICT 自动跳过已有数据，且部分 ETF 可能缺失特定因子）
        new_etfs = list(etf_pool)
        n_skipped = 0
        logger.info("需回填: %d 只", len(new_etfs))

        if not new_etfs:
            logger.info("所有 ETF 已有因子数据，无需回填")
            return

        # 过滤数据，只保留需回填的 ETF
        df = df[df["ts_code"].isin(new_etfs)].copy()
        # 按 ts_code + trade_date 排序，确保 rolling 操作在每组内正确
        df = df.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
        logger.info("待处理数据: %d 行, %d ETFs", len(df), len(new_etfs))

        # 4. 批量 GroupBy 模式：每个因子一次计算覆盖所有 ETF
        total_written = 0
        for fidx, (fcode, calc_fn) in enumerate(FACTOR_REGISTRY.items()):
            logger.info(
                "  [%d/%d] 计算 %s ...", fidx + 1, N_FACTORS, fcode
            )
            try:
                # 按 ts_code 分组计算，确保 rolling/shift 操作不跨 ETF
                series = df.groupby("ts_code", group_keys=False).apply(
                    calc_fn, include_groups=False
                )
                # flatten multi-index if needed
                if isinstance(series, pd.DataFrame):
                    series = series.iloc[:, 0]
            except Exception as e:
                logger.warning("  %s: 计算失败 - %s", fcode, e)
                continue

            # 构建写入记录
            records = []
            for pos in range(len(series)):
                val = series.iloc[pos]
                if pd.isna(val):
                    continue
                etf_code = str(df.iloc[pos]["ts_code"])
                td = df.iloc[pos]["trade_date"]
                if hasattr(td, "date"):
                    td = td.date()
                records.append((str(uuid.uuid4()), fcode, etf_code, td, float(val)))

            logger.info(
                "    有效值: %d / %d (%.1f%%)",
                len(records), len(df), len(records) / len(df) * 100 if len(df) else 0,
            )

            # 批量写入
            batch_written = 0
            for start in range(0, len(records), 1000):
                batch = records[start : start + 1000]
                await conn.executemany(
                    """
                    INSERT INTO factor_data (id, factor_code, ts_code, trade_date, factor_value)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (ts_code, factor_code, trade_date) DO UPDATE
                    SET factor_value = EXCLUDED.factor_value
                """,
                    batch,
                )
                batch_written += len(batch)
            total_written += batch_written
            logger.info("    %s: 写入 %d 条", fcode, batch_written)

        # 4. 验证
        logger.info("=" * 50)
        logger.info("回填完成: 总计 %d 条 (跳过 %d 只已有数据)", total_written, n_skipped)
        for fc in ["drawdown_20d", "rsi_14", "atr_14", "adx_14", "vol_trend"]:
            n_etfs = await conn.fetchval(
                "SELECT COUNT(DISTINCT ts_code) FROM factor_data WHERE factor_code = $1", fc
            )
            logger.info("  %-20s => %d ETFs", fc, n_etfs)

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
