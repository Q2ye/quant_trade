# -*- coding: utf-8 -*-
"""一次性复核：逐条验证前一轮结论（不提交）。

V1 09-11 数据量   V2 strategy_parameters 是否在运行后回写   V3 前复权 vs 原始价
V4 weak_confirm_days   V5 严格复刻实盘 trigger 的重放方式    V6 159985 三道门实测
V7 负 R² 的下界（最坏情形）
"""
import asyncio
import importlib.util
import sys
from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

SID = "07651265-9e26-4849-89eb-6c5cdba61187"
TD = "2026-09-11"


def load_cls():
    import os

    path = os.environ.get("CM_CODE", "logs/_db_code_0911.py")
    print(f"  [加载策略代码] {path}")
    spec = importlib.util.spec_from_file_location("db_cm", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CrossMarketMomentumStrategy


ETF_SQL = """
    SELECT e.ts_code, e.trade_date::text,
           e.open  * COALESCE(f.adj_factor,1) / lf.latest_factor AS open,
           e.high  * COALESCE(f.adj_factor,1) / lf.latest_factor AS high,
           e.low   * COALESCE(f.adj_factor,1) / lf.latest_factor AS low,
           e.close * COALESCE(f.adj_factor,1) / lf.latest_factor AS close,
           e.vol, e.amount,
           e.close AS raw_close, COALESCE(f.adj_factor,1) AS adj, lf.latest_factor
    FROM etf_daily e
    LEFT JOIN fund_adj_factor f
      ON f.ts_code = e.ts_code AND f.trade_date = e.trade_date
    LEFT JOIN (SELECT DISTINCT ON (ts_code) ts_code, adj_factor AS latest_factor
               FROM fund_adj_factor ORDER BY ts_code, trade_date DESC) lf
      ON lf.ts_code = e.ts_code
    WHERE e.ts_code = ANY(:c) AND e.trade_date BETWEEN :a AND :b
    ORDER BY e.ts_code, e.trade_date
"""


async def main() -> None:
    Cls = load_cls()
    strat = Cls(name="复核")
    strat.context = SimpleNamespace(positions={}, total_assets=20_000.0,
                                    available_capital=20_000.0)
    etfs = list(strat.global_pool) + list(strat.china_pool) + [strat.defensive_etf]

    from sqlalchemy import text
    from core.engines.types.entities import BarData
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    print("=" * 100)
    print("V1  09-11 数据量 + trade_calendar")
    print("=" * 100)
    async with sf() as s:
        for tbl in ("etf_daily", "index_daily", "fund_adj_factor", "stock_daily"):
            r = await s.execute(text(
                f"SELECT count(*) FROM {tbl} WHERE trade_date='2026-09-11'"))
            print(f"  {tbl:<20} = {r.fetchone()[0]}")
        r = await s.execute(text(
            "SELECT cal_date::text, is_open FROM trade_calendar "
            "WHERE cal_date BETWEEN '2026-09-09' AND '2026-09-14' ORDER BY cal_date"))
        print("  交易日历:", r.fetchall())

        print()
        print("=" * 100)
        print("V2  strategy_parameters 现状（21:26 手动运行之后；看是否回写）")
        print("=" * 100)
        r = await s.execute(text(
            "SELECT param_name, param_value::text, updated_at::text "
            "FROM strategy_parameters WHERE strategy_id=:i ORDER BY param_name"), {"i": SID})
        for x in r.fetchall():
            print(f"  {x[0]:<22} = {str(x[1])[:30]:<32} updated_at={x[2]}")

        print()
        print("=" * 100)
        print("V3  159985.SZ 前复权 vs 原始价（检查 adj_factor / latest_factor）")
        print("=" * 100)
        r = await s.execute(text("""
            SELECT e.trade_date::text, e.close AS raw_close,
                   COALESCE(f.adj_factor,1) AS adj,
                   (SELECT adj_factor FROM fund_adj_factor x WHERE x.ts_code=e.ts_code
                    ORDER BY trade_date DESC LIMIT 1) AS latest
            FROM etf_daily e LEFT JOIN fund_adj_factor f
              ON f.ts_code=e.ts_code AND f.trade_date=e.trade_date
            WHERE e.ts_code='159985.SZ' AND e.trade_date BETWEEN '2026-09-04' AND '2026-09-11'
            ORDER BY e.trade_date"""))
        for d, raw, adj, latest in r.fetchall():
            qfq = float(raw) * float(adj) / float(latest)
            print(f"  {d}  raw={float(raw):.4f}  adj={adj}  latest={latest}  "
                  f"→ qfq={qfq:.4f}  {'相同' if abs(qfq - float(raw)) < 1e-9 else '★不同'}")

        print()
        print("=" * 100)
        print("V4  regime 参数")
        print("=" * 100)
        for k in ("weak_enter_votes", "weak_exit_votes", "weak_confirm_days",
                  "max_weak_days", "weak_period_ma_lookback", "loss",
                  "enable_loss_filter", "enable_ma_filter", "enable_volume_check",
                  "lookback_days"):
            print(f"  {k:<26} = {getattr(strat, k, '不存在')}")

        # ---- 数据 ----
        async with sf() as s:
            for c in strat.weak_indices:
                r = await s.execute(text(
                    "SELECT trade_date, close FROM index_daily WHERE ts_code=:c "
                    "ORDER BY trade_date"), {"c": c})
                strat._index_cache[c] = {str(d)[:10]: float(v) for d, v in r.fetchall()}
            r = await s.execute(text(ETF_SQL), {"c": etfs, "a": date(2025, 1, 1), "b": date(2026, 9, 11)})
            rows = r.fetchall()
    await pool.close()

    df = pd.DataFrame(rows, columns=["code", "d", "open", "high", "low", "close",
                                     "vol", "amt", "raw_close", "adj", "latest"])
    for c in ("open", "high", "low", "close", "vol", "amt", "raw_close", "adj", "latest"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["qfq"] = df["raw_close"] * df["adj"] / df["latest"]
    print()
    print("=" * 100)
    print("V5  严格复刻实盘 trigger：预热只喂 on_bar，最后只调一次 on_bar_batch_end(09-11)")
    print("=" * 100)
    days = sorted(df["d"].unique())
    warm = [d for d in days if d < TD]
    for d in warm:
        for _, x in df[df["d"] == d].iterrows():
            strat.on_bar(BarData(ts_code=x["code"], period="daily", trade_date=d,
                                 open=x["open"], high=x["high"], low=x["low"],
                                 close=x["close"],
                                 volume=x["vol"] if pd.notna(x["vol"]) else 0.0,
                                 amount=x["amt"] if pd.notna(x["amt"]) else 0.0))
    print(f"  预热: {len(warm)} 个交易日, _data_cache={len(strat._data_cache)} 只, "
          f"_is_weak={strat._is_weak}(预热未跑调仓)")
    for _, x in df[df["d"] == TD].iterrows():
        strat.on_bar(BarData(ts_code=x["code"], period="daily", trade_date=TD,
                             open=x["open"], high=x["high"], low=x["low"], close=x["close"],
                             volume=x["vol"] if pd.notna(x["vol"]) else 0.0,
                             amount=x["amt"] if pd.notna(x["amt"]) else 0.0))
    sigs = strat.on_bar_batch_end(TD)
    print(f"  调仓后: _is_weak={strat._is_weak}  days={strat._weak_days_count}/"
          f"{strat.max_weak_days}  holdings={list(strat._holdings)}")
    print(f"  信号数={len(sigs)}")
    for g in sigs:
        print(f"    {getattr(g, 'ts_code', '?')} {getattr(g, 'direction', '?')} "
              f"px={getattr(g, 'price', None)} qty={getattr(g, 'quantity', None)}")

    print()
    print("=" * 100)
    print("V6  走弱期池 11 只 + 159985 的隐藏门（走弱期被跳过的那三道）")
    print("=" * 100)
    pool_used = strat.global_pool if strat._is_weak else (strat.global_pool + strat.china_pool)
    print(f"  池 = {'全球池' if strat._is_weak else '全球+中国'} ({len(pool_used)} 只)")
    print(f"  {'标的':<11}{'raw':>9}{'R²':>9}{'动量门':>7}{'R²门':>6}{'相强门':>7}"
          f"{'均线门*':>8}{'量比门*':>8}{'3日跌门*':>9}   走弱期入选")
    for c in pool_used:
        m = strat._score_candidate(c)
        if m is None:
            print(f"  {c:<11}{'-- 无当日数据/不满足前置 --':>52}")
            continue
        ok = m["passed_momentum"] and m["passed_r2"] and m["passed_rel_strength"]
        star = "" if strat._is_weak else ""
        _raw = m.get("raw_score", m["annualized"] * m["r2"])
        print(f"  {c:<11}{_raw:>9.3f}{m['r2']:>9.4f}"
              f"{'OK' if m['passed_momentum'] else '×':>7}"
              f"{'OK' if m['passed_r2'] else '×':>6}"
              f"{'OK' if m['passed_rel_strength'] else '×':>7}"
              f"{'OK' if m['passed_ma'] else '×':>8}"
              f"{'OK' if m['passed_volume'] else '×':>8}"
              f"{'OK' if m['passed_loss'] else '×':>9}"
              f"{'  → 选中' if ok else '':>12}")
    print("  （* = 走弱期不执行这三道门）")

    print()
    print("=" * 100)
    print("V7  负 R² 下界扫描（最坏情形：score 能被放大到多大）")
    print("=" * 100)
    tot = neg = 0
    min_r2, max_flip = 0.0, -1e9
    for code, g in df.groupby("code"):
        c = g["close"].to_numpy(dtype=np.float64)
        for i in range(strat.lookback_days, len(c)):
            sc, ann, r2 = strat._calc_momentum_score(c[: i + 1], strat.lookback_days)
            if sc is None:
                continue
            tot += 1
            if r2 < 0:
                neg += 1
                min_r2 = min(min_r2, r2)
                if ann < 0 and sc > 0:
                    max_flip = max(max_flip, sc)
    print(f"  样本 {tot:,}   r2<0 占比 {neg / tot:.2%}   最小 r2 = {min_r2:.4f}")
    print(f"  翻转后最大得分 = {max_flip:.4f}   （动量门上限 max_score_threshold="
          f"{strat.max_score_threshold}）")


if __name__ == "__main__":
    asyncio.run(main())
