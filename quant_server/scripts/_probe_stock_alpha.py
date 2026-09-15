# -*- coding: utf-8 -*-
"""P2 选股 alpha 前置：数据可用性 + 翻倍股基础发生率（只读，_ 前缀不入 git）。

回答三件事：
  1) 选股研究依赖的行情/估值/资金流数据，在库里的真实覆盖区间
  2) 「翻倍股」（250 日内 ≥ +100%）的基础发生率 —— 决定反例统计的样本量
  3) 跑赢指数 1.5x 的样本量（立项书 P2 的观测口径）
"""
import asyncio

import numpy as np
import pandas as pd
from sqlalchemy import text

OUT = "logs/_probe_stock_alpha.txt"
B: list = []


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        B.append("[1] 数据覆盖（选股研究依赖的表）")
        for tbl, col in (("stock_daily", "close"), ("stock_daily_basic", "*"),
                         ("stock_adjusted_prices", "close"), ("stock_moneyflow", "*"),
                         ("margin", "*"), ("factor_data", "*")):
            try:
                if col == "*":
                    r = (await s.execute(text(
                        f"SELECT COUNT(*) n, MIN(trade_date)::text mn, MAX(trade_date)::text mx "
                        f"FROM {tbl}"))).mappings().one()
                else:
                    r = (await s.execute(text(
                        f"SELECT COUNT(*) n, MIN(trade_date)::text mn, MAX(trade_date)::text mx "
                        f"FROM {tbl}"))).mappings().one()
                B.append("   %-24s 行数=%-10s %s ~ %s" % (tbl, f"{r['n']:,}", r["mn"], r["mx"]))
            except Exception as e:  # noqa: BLE001
                await s.rollback()
                B.append("   %-24s 查询失败: %s" % (tbl, str(e)[:80]))
        # 每日股票数（判断池子广度随时间）
        try:
            r = (await s.execute(text(
                "SELECT EXTRACT(YEAR FROM trade_date)::int y, COUNT(DISTINCT ts_code) codes "
                "FROM stock_daily GROUP BY 1 ORDER BY 1"))).mappings().all()
            B.append("   每年股票数: " + ", ".join(f"{x['y']}:{x['codes']}" for x in r))
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            B.append("   每年股票数查询失败: %s" % str(e)[:80])

        # 估值/市值字段可用性
        try:
            r = (await s.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='stock_daily_basic' ORDER BY ordinal_position"))).scalars().all()
            B.append("   stock_daily_basic 列: " + ", ".join(r))
        except Exception as e:  # noqa: BLE001
            await s.rollback()
            B.append("   列查询失败: %s" % str(e)[:80])

        # 全市场日线（研究样本）
        B.append("")
        B.append("[2] 载入全市场日线用于发生率统计…")
        r = await s.execute(text(
            "SELECT ts_code, trade_date, close FROM stock_daily "
            "WHERE trade_date >= DATE '2018-06-01' ORDER BY ts_code, trade_date"))
        px = pd.DataFrame(r.fetchall(), columns=["ts_code", "trade_date", "close"])
        r = await s.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code='000852.SH' "
            "AND trade_date >= DATE '2018-06-01' ORDER BY trade_date"))
        idx = pd.DataFrame(r.fetchall(), columns=["trade_date", "close"])

    B.append("   行情行数=%s  股票数=%s" % (f"{len(px):,}", px["ts_code"].nunique()))
    px["trade_date"] = px["trade_date"].astype(str).str[:10]
    px["close"] = pd.to_numeric(px["close"], errors="coerce")
    idx["trade_date"] = idx["trade_date"].astype(str).str[:10]
    idx["close"] = pd.to_numeric(idx["close"], errors="coerce")

    # 每只股票：以「每个交易日」为起点的未来 250 日收益（滚动，用于发生率）
    H = 250
    rows = []
    for code, g in px.groupby("ts_code", sort=False):
        g = g.sort_values("trade_date").reset_index(drop=True)
        if len(g) < H + 20:
            continue
        c = g["close"].values
        fwd = np.full(len(c), np.nan)
        fwd[:-H] = c[H:] / c[:-H] - 1
        sub = pd.DataFrame({"trade_date": g["trade_date"].values, "fwd": fwd})
        sub["ts_code"] = code
        rows.append(sub.dropna(subset=["fwd"]))
    allf = pd.concat(rows, ignore_index=True)
    allf["year"] = allf["trade_date"].str[:4]

    # 指数同口径未来收益（用于「跑赢指数 1.5x」口径）
    ic = idx["close"].values
    ifwd = np.full(len(ic), np.nan)
    ifwd[:-H] = ic[H:] / ic[:-H] - 1
    idx_f = pd.DataFrame({"trade_date": idx["trade_date"].values, "idx_fwd": ifwd}).dropna()
    allf = allf.merge(idx_f, on="trade_date", how="left")
    allf["excess_ratio"] = (1 + allf["fwd"]) / (1 + allf["idx_fwd"])

    B.append("")
    B.append("[3] 翻倍股（未来 250 日 ≥ +100%）基础发生率，按起始年")
    B.append("   %-6s %10s %10s %10s %10s" % ("起始年", "样本数", "翻倍数", "占比", "≥+50%占比"))
    for y, g in allf.groupby("year"):
        n = len(g)
        n2 = int((g["fwd"] >= 1.0).sum())
        n15 = int((g["fwd"] >= 0.5).sum())
        B.append("   %-6s %10s %10s %9.2f%% %9.2f%%" % (
            y, f"{n:,}", f"{n2:,}", n2 / n * 100, n15 / n * 100))
    n = len(allf)
    B.append("   %-6s %10s %10s %9.2f%% %9.2f%%" % (
        "合计", f"{n:,}", f"{int((allf['fwd'] >= 1.0).sum()):,}",
        (allf["fwd"] >= 1.0).mean() * 100, (allf["fwd"] >= 0.5).mean() * 100))

    B.append("")
    B.append("[4] 跑赢中证1000 1.5x 的样本（立项书 P2 观测口径）")
    ex = allf.dropna(subset=["excess_ratio"])
    B.append("   样本=%s  占比=%.2f%%" % (f"{len(ex):,}", (ex["excess_ratio"] >= 1.5).mean() * 100))
    for y, g in ex.groupby("year"):
        B.append("   %-6s 样本=%9s  跑赢1.5x占比=%5.2f%%" % (
            y, f"{len(g):,}", (g["excess_ratio"] >= 1.5).mean() * 100))

    B.append("")
    B.append("[5] 收益分布（未来250日，全样本）")
    q = allf["fwd"].quantile([0.1, 0.25, 0.5, 0.75, 0.9, 0.99])
    B.append("   P10=%.1f%%  P25=%.1f%%  中位=%.1f%%  P75=%.1f%%  P90=%.1f%%  P99=%.1f%%"
             % tuple(v * 100 for v in q.values))
    B.append("   均值=%.2f%%  正收益占比=%.2f%%" % (
        allf["fwd"].mean() * 100, (allf["fwd"] > 0).mean() * 100))


if __name__ == "__main__":
    import os

    try:
        asyncio.run(main())
    except Exception as e:  # noqa: BLE001
        import traceback
        B.append("[FATAL] " + repr(e))
        B.append(traceback.format_exc()[:2000])
    os.makedirs("logs", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(B))
    print("OK ->", OUT)
