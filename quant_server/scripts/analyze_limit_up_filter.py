# -*- coding: utf-8 -*-
"""
连板涨停过滤 — 5年历史数据影响分析
====================================
在 5 年历史数据上统计 P2 连板过滤拦截了多少候选股，
以及这些被过滤的股票后续表现如何。

分析维度：
  A. 拦截量：每天有多少股票被 P2 过滤掉
  B. 拦截质量：被过滤的股票如果买入，N 日后盈亏如何
  C. 分年统计：不同市场环境下拦截量的差异

执行: cd quant_server && .venv/Scripts/python.exe scripts/analyze_limit_up_filter.py
"""
import asyncio, logging, sys
from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, List, Set, Tuple

import asyncpg
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB = {"host": "localhost", "port": 5432, "user": "postgres", "password": "123456", "database": "quant_signals_dev"}

ALLOW_PREFIX = ('000', '002', '600', '603', '601', '605')

# ── 主板股票池 ──
async def load_universe(conn):
    rows = await conn.fetch("SELECT ts_code, list_date FROM stock_basic WHERE ts_code LIKE '00%' OR ts_code LIKE '60%' ORDER BY ts_code")
    codes = []
    listing = {}
    for r in rows:
        code = r["ts_code"]
        stock_code = code.split(".")[0]
        if stock_code.startswith(ALLOW_PREFIX):
            codes.append(code)
            if r["list_date"]:
                listing[code] = str(r["list_date"])[:10]
    logger.info("主板股票池: %d 只", len(codes))
    return codes, listing

# ── 加载 ST 列表 ──
async def load_st_list(conn):
    rows = await conn.fetch("SELECT ts_code FROM stock_basic WHERE name LIKE '%ST%'")
    return {r["ts_code"] for r in rows}

# ── 加载每日行情数据 ──
async def load_daily_data(conn, codes, start, end):
    """加载 OHLCV 数据，返回 {ts_code: DataFrame}"""
    batch_size = 500
    all_data = {}
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        code_list = "','".join(batch)
        rows = await conn.fetch(f"""
            SELECT ts_code, trade_date, open, high, low, close, pre_close, vol, amount
            FROM stock_daily
            WHERE ts_code = ANY(ARRAY['{code_list}']::varchar[])
              AND trade_date >= $1 AND trade_date <= $2
            ORDER BY ts_code, trade_date
        """, start, end)
        for r in rows:
            code = r["ts_code"]
            if code not in all_data:
                all_data[code] = []
            all_data[code].append({
                "trade_date": str(r["trade_date"])[:10],
                "open": float(r["open"] or 0),
                "high": float(r["high"] or 0),
                "low": float(r["low"] or 0),
                "close": float(r["close"] or 0),
                "pre_close": float(r["pre_close"] or 0),
                "vol": float(r["vol"] or 0),
                "amount": float(r["amount"] or 0),
            })
        if i % 2000 == 0:
            logger.info("  加载行情: %d/%d stocks", min(i + batch_size, len(codes)), len(codes))

    result = {}
    for code, rows in all_data.items():
        df = pd.DataFrame(rows).sort_values("trade_date").reset_index(drop=True)
        result[code] = df
    logger.info("加载完成: %d 只有效数据", len(result))
    return result


def count_recent_limit_ups(df, lookback=5):
    """统计近 N 日涨停天数（涨幅 >= 9.5%）"""
    if df is None or len(df) < lookback + 1:
        return 0
    closes = df["close"].values.astype(np.float64)
    count = 0
    for i in range(-lookback, 0):
        prev = closes[i - 1]
        cur = closes[i]
        if prev > 0 and (cur / prev - 1.0) >= 0.095:
            count += 1
    return count


def passes_screen_basic(df, code, st_set, listing_dates, trade_date, annual_gate):
    """基础筛选条件（不含连板过滤）"""
    if df is None or len(df) < 25:
        return False
    # ST 过滤
    if code in st_set:
        return False
    # 新股过滤（30天 ≈ 45个自然日）
    list_d = listing_dates.get(code)
    if list_d:
        try:
            d0 = date.fromisoformat(list_d)
            d1 = date.fromisoformat(trade_date)
            if (d1 - d0).days < 45:
                return False
        except ValueError:
            pass
    try:
        closes = df["close"].values.astype(np.float64)
        volumes = df["vol"].values.astype(np.float64)
        opens = df["open"].values.astype(np.float64)

        # 条件1: 昨日收阳 + 涨幅 >= 0.7%
        close_yest = closes[-2]
        open_yest = opens[-2]
        close_pre = closes[-3] if len(closes) >= 3 else close_yest
        if close_pre <= 0:
            return False
        is_up_bar = close_yest > open_yest
        rise_rate = (close_yest - close_pre) / close_pre
        if not (is_up_bar and rise_rate >= 0.007):
            return False

        # 条件2: MA5 > MA20
        ma5 = float(np.mean(closes[-5:]))
        ma20 = float(np.mean(closes[-20:]))
        if ma5 < ma20:
            return False

        # 条件3: 量比 >= 1.2
        avg_vol_20 = float(np.mean(volumes[-20:]))
        last_vol = float(volumes[-1])
        if avg_vol_20 > 0 and last_vol / avg_vol_20 < 1.2:
            return False

        # 条件4: ROC(10) > 5
        roc_10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if len(closes) >= 11 else 0
        if roc_10 < 5.0:
            return False

        # 条件5: MACD 多头 (简化)
        if len(closes) < 35:
            return False
        s = pd.Series(closes, dtype="float64")
        ema12 = s.ewm(span=12, adjust=False).mean()
        ema26 = s.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        if float(dif.iloc[-1]) <= float(dea.iloc[-1]) or float(dif.iloc[-1]) <= 0:
            return False

        # 条件6: 距 20 日新高 0.15%~8%
        hhv_20 = float(np.max(closes[-20:]))
        if hhv_20 <= 0:
            return False
        below_high = (hhv_20 - closes[-1]) / hhv_20
        if below_high < 0.0015:
            return False
        if closes[-1] < hhv_20 * 0.92:
            return False

        return True
    except Exception:
        return False


def forward_returns(df, trade_date, days=10):
    """计算买入后 N 日的未来收益"""
    if df is None:
        return None
    dates = df["trade_date"].values
    closes = df["close"].values.astype(np.float64)
    # 找到 trade_date 对应的 index
    idx = np.where(dates == trade_date)[0]
    if len(idx) == 0:
        return None
    i = idx[0]
    if i + days >= len(closes):
        return None
    entry = closes[i]
    future_closes = closes[i + 1 : i + 1 + days]
    if len(future_closes) == 0:
        return None
    max_ret = (np.max(future_closes) - entry) / entry
    max_dd = (np.min(future_closes) - entry) / entry
    final_ret = (future_closes[-1] - entry) / entry
    return {"max_ret": max_ret, "max_dd": max_dd, "final_ret": final_ret}


async def main():
    start = date(2021, 7, 19)
    end = date(2026, 7, 18)
    logger.info("分析区间: %s ~ %s", start, end)

    conn = await asyncpg.connect(**DB)
    try:
        # 1. 加载数据
        universe, listing_dates = await load_universe(conn)
        st_set = await load_st_list(conn)
        daily_data = await load_daily_data(conn, universe, start, end)

        # 2. 收集所有交易日
        all_dates_set = set()
        for df in daily_data.values():
            for d in df["trade_date"]:
                all_dates_set.add(d)
        all_dates = sorted(all_dates_set)
        logger.info("交易日: %d 天", len(all_dates))

        # 3. 逐日分析
        # 统计:
        stats_by_year = defaultdict(lambda: {
            "total_passed": 0,           # 基础筛选通过的
            "filtered_by_limit_up": 0,   # 被连板过滤拦截的
            "filtered_returns_5d": [],   # 被过滤股票 5日后的表现
            "filtered_returns_10d": [],
            "filtered_returns_20d": [],
            "passed_returns_5d": [],     # 通过筛选股票的5日表现(样本)
            "passed_returns_10d": [],
            "passed_returns_20d": [],
        })

        sample_passed = 0  # 只采样部分通过股做对比

        for td in all_dates:
            year = int(td[:4])
            for code, df in daily_data.items():
                # 截断到当前日期（防前视）
                df_slice = df[df["trade_date"] <= td]
                if df_slice.empty or df_slice["trade_date"].iloc[-1] != td:
                    continue

                # 基础筛选
                if not passes_screen_basic(df_slice, code, st_set, listing_dates, td, True):
                    continue

                stats_by_year[year]["total_passed"] += 1

                # P2 连板过滤
                limit_ups = count_recent_limit_ups(df_slice, 5)
                if limit_ups >= 2:
                    stats_by_year[year]["filtered_by_limit_up"] += 1
                    # 跟踪被过滤股票的未来表现
                    ret5 = forward_returns(df, td, 5)
                    ret10 = forward_returns(df, td, 10)
                    ret20 = forward_returns(df, td, 20)
                    if ret5:
                        stats_by_year[year]["filtered_returns_5d"].append(ret5["final_ret"])
                    if ret10:
                        stats_by_year[year]["filtered_returns_10d"].append(ret10["final_ret"])
                    if ret20:
                        stats_by_year[year]["filtered_returns_20d"].append(ret20["final_ret"])
                else:
                    # 采样通过股做对比（每天最多 5 只）
                    if sample_passed < 5000:
                        ret10 = forward_returns(df, td, 10)
                        if ret10:
                            stats_by_year[year]["passed_returns_10d"].append(ret10["final_ret"])
                            sample_passed += 1

        # 4. 输出报告
        print("\n" + "=" * 90)
        print("  连板涨停过滤 (P2) — 5 年历史数据分析")
        print("=" * 90)
        print(f"{'Year':<8} {'Passed':>8} {'Filtered':>9} {'Rate':>7} "
              f"{'Filt5dRet':>10} {'Filt10dRet':>10} {'Filt20dRet':>10} "
              f"{'Pass10dRet':>10}")
        print("-" * 90)

        total_passed = 0
        total_filtered = 0
        all_filt_5d = []
        all_filt_10d = []
        all_filt_20d = []

        for year in sorted(stats_by_year.keys()):
            s = stats_by_year[year]
            rate = s["filtered_by_limit_up"] / s["total_passed"] * 100 if s["total_passed"] > 0 else 0
            f5 = np.mean(s["filtered_returns_5d"]) * 100 if s["filtered_returns_5d"] else 0
            f10 = np.mean(s["filtered_returns_10d"]) * 100 if s["filtered_returns_10d"] else 0
            f20 = np.mean(s["filtered_returns_20d"]) * 100 if s["filtered_returns_20d"] else 0
            p10 = np.mean(s["passed_returns_10d"]) * 100 if s["passed_returns_10d"] else 0

            print(f"{year:<8} {s['total_passed']:>8} {s['filtered_by_limit_up']:>9} {rate:>6.1f}% "
                  f"{f5:>9.2f}% {f10:>9.2f}% {f20:>9.2f}% {p10:>9.2f}%")

            total_passed += s["total_passed"]
            total_filtered += s["filtered_by_limit_up"]
            all_filt_5d.extend(s["filtered_returns_5d"])
            all_filt_10d.extend(s["filtered_returns_10d"])
            all_filt_20d.extend(s["filtered_returns_20d"])

        # 汇总
        print("-" * 90)
        rate = total_filtered / total_passed * 100 if total_passed > 0 else 0
        f5 = np.mean(all_filt_5d) * 100 if all_filt_5d else 0
        f10 = np.mean(all_filt_10d) * 100 if all_filt_10d else 0
        f20 = np.mean(all_filt_20d) * 100 if all_filt_20d else 0
        print(f"{'Total':<8} {total_passed:>8} {total_filtered:>9} {rate:>6.1f}% "
              f"{f5:>9.2f}% {f10:>9.2f}% {f20:>9.2f}%")

        # 5. 被过滤股票的质量分析
        print("\n" + "=" * 60)
        print("  被过滤股票的质量分析")
        print("=" * 60)

        if all_filt_5d:
            arr5 = np.array(all_filt_5d)
            arr10 = np.array(all_filt_10d)
            arr20 = np.array(all_filt_20d)
            print(f"  5日收益:  均值={np.mean(arr5)*100:+.2f}%  中位数={np.median(arr5)*100:+.2f}%  正收益率={(arr5>0).mean()*100:.1f}%")
            print(f"  10日收益: 均值={np.mean(arr10)*100:+.2f}%  中位数={np.median(arr10)*100:+.2f}%  正收益率={(arr10>0).mean()*100:.1f}%")
            print(f"  20日收益: 均值={np.mean(arr20)*100:+.2f}%  中位数={np.median(arr20)*100:+.2f}%  正收益率={(arr20>0).mean()*100:.1f}%")

            # 被过滤的股票 vs 正常通过股票
            all_passed_10d = []
            for s in stats_by_year.values():
                all_passed_10d.extend(s["passed_returns_10d"])
            if all_passed_10d:
                arr_p10 = np.array(all_passed_10d)
                print(f"\n  对比: 通过股 10日收益 均值={np.mean(arr_p10)*100:+.2f}%  "
                      f"中位数={np.median(arr_p10)*100:+.2f}%  正收益率={(arr_p10>0).mean()*100:.1f}%")
                delta = np.mean(arr10) - np.mean(arr_p10)
                print(f"  → 被过滤股 比 通过股 10日收益 {'高' if delta>0 else '低'} {abs(delta)*100:.2f}%")

            # 极端情况：被过滤股票中有多少是大赢家(>20%)
            big_win_5d = (arr5 > 0.20).mean() * 100
            big_win_10d = (arr10 > 0.20).mean() * 100
            big_loss_10d = (arr10 < -0.10).mean() * 100
            print(f"\n  被过滤股票中:")
            print(f"    5日内大涨>20%: {big_win_5d:.1f}%")
            print(f"    10日内大涨>20%: {big_win_10d:.1f}%")
            print(f"    10日内大跌>10%: {big_loss_10d:.1f}%")

        # 6. 结论
        print("\n" + "=" * 60)
        print("  结论")
        print("=" * 60)
        print(f"  连板过滤拦截比例: {rate:.1f}% of 基础筛选通过股")
        print(f"  年平均拦截: {total_filtered / len(stats_by_year):.0f} 只")
        if all_filt_10d:
            avg_filt_ret = np.mean(all_filt_10d) * 100
            if avg_filt_ret < -1:
                print(f"  ⭐ 被过滤股 10日平均收益 {avg_filt_ret:+.2f}%（负面），过滤有效！")
            elif avg_filt_ret < 0:
                print(f"  ✅ 被过滤股 10日平均收益 {avg_filt_ret:+.2f}%（轻微负面），过滤有边际改善")
            else:
                print(f"  ⚠️ 被过滤股 10日平均收益 {avg_filt_ret:+.2f}%（正面），过滤可能误杀了一些好标的")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
