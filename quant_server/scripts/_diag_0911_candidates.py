# -*- coding: utf-8 -*-
"""一次性诊断：09-11 走弱期为何只剩 1 个候选（不提交）。

用 **DB 里实盘跑的代码**（logs/_db_code_0911.py）重建 242 日状态到 2026-09-11，
然后逐只打印全球池 11 只 ETF 的每道门结果。
"""
import asyncio
import importlib.util
import sys
from datetime import date
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, ".")

DB_CODE = "logs/_db_code_0911.py"
TD = "2026-09-11"
WARMUP_START = "2025-01-01"


def load_cls():
    spec = importlib.util.spec_from_file_location("db_cm", DB_CODE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.CrossMarketMomentumStrategy


async def main() -> None:
    from sqlalchemy import text
    from core.engines.types.entities import BarData
    from shared.database.session.connection_pool import get_connection_pool

    Cls = load_cls()
    strat = Cls(name="离线诊断-0911")
    strat.context = SimpleNamespace(positions={}, total_assets=20_000.0,
                                    available_capital=20_000.0)

    etfs = list(strat.global_pool) + list(strat.china_pool) + [strat.defensive_etf]
    idx_codes = list(strat.weak_indices)

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        # 指数全历史 → _index_cache（复刻 reset 里的预热）
        for c in idx_codes:
            r = await s.execute(text(
                "SELECT trade_date, close FROM index_daily WHERE ts_code=:c "
                "ORDER BY trade_date"), {"c": c})
            strat._index_cache[c] = {str(d)[:10]: float(v) for d, v in r.fetchall()}

        # ETF 前复权日线（与 get_etf_adjusted_daily_batch 同口径）
        r = await s.execute(text("""
            SELECT e.ts_code, e.trade_date::text,
                   e.open * f.adj_factor / lf.latest_factor AS open,
                   e.high * f.adj_factor / lf.latest_factor AS high,
                   e.low  * f.adj_factor / lf.latest_factor AS low,
                   e.close* f.adj_factor / lf.latest_factor AS close,
                   e.vol, e.amount
            FROM etf_daily e
            LEFT JOIN fund_adj_factor f
              ON f.ts_code = e.ts_code AND f.trade_date = e.trade_date
            LEFT JOIN (
                SELECT DISTINCT ON (ts_code) ts_code, adj_factor AS latest_factor
                FROM fund_adj_factor ORDER BY ts_code, trade_date DESC
            ) lf ON lf.ts_code = e.ts_code
            WHERE e.ts_code = ANY(:c) AND e.trade_date BETWEEN :a AND :b
            ORDER BY e.ts_code, e.trade_date
        """), {"c": etfs, "a": date.fromisoformat(WARMUP_START), "b": date.fromisoformat(TD)})
        rows = r.fetchall()
    await pool.close()

    df = pd.DataFrame(rows, columns=["code", "d", "open", "high", "low", "close", "vol", "amt"])
    for c in ("open", "high", "low", "close", "vol", "amt"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    print(f"ETF 行情 {len(df)} 行, {df['code'].nunique()} 只, "
          f"{df['d'].min()} ~ {df['d'].max()}")

    # 逐日喂 bar，逐日调仓（复刻 manager 驱动方式）
    days = sorted(df["d"].unique())
    for d in days:
        sub = df[df["d"] == d]
        for _, x in sub.iterrows():
            strat.on_bar(BarData(ts_code=x["code"], period="daily", trade_date=d,
                                 open=x["open"],
                                 high=x["high"], low=x["low"], close=x["close"],
                                 volume=x["vol"] if pd.notna(x["vol"]) else 0.0,
                                 amount=x["amt"] if pd.notna(x["amt"]) else 0.0))
        strat.on_bar_batch_end(d)

    print(f"\n最终状态: _last_trade_date={strat._last_trade_date}  "
          f"_is_weak={strat._is_weak}  days={strat._weak_days_count}/"
          f"{strat.max_weak_days}  holdings={list(strat._holdings)}")
    print(f"参数: r2_threshold={strat.r2_threshold} "
          f"trend_quality={strat.enable_trend_quality} power={strat.trend_quality_power} "
          f"rel_strength={strat.enable_rel_strength}")
    print(f"      动量区间=[{strat.min_score_threshold}, {strat.max_score_threshold}] "
          f"入场涨幅门={strat.enable_entry_gain_filter} "
          f"veto={strat.entry_gain_veto}")

    pool_used = strat.global_pool if strat._is_weak else (strat.global_pool + strat.china_pool)
    print(f"\n当前候选池 = {'全球池(走弱期)' if strat._is_weak else '全球+中国池'}，"
          f"{len(pool_used)} 只")
    print("=" * 132)
    print(f"  {'标的':<11}{'动量分':>9}{'raw':>9}{'score':>9}{'年化':>9}{'R²':>7}"
          f"{'相对超额':>10}{'动量门':>7}{'R²门':>6}{'相强门':>7}{'入选':>6}")
    print("=" * 132)
    metrics = []
    for c in pool_used:
        m = strat._score_candidate(c)
        if m is None:
            print(f"  {c:<11}{'-- 无数据/当日无bar/不满足前置 --':>50}")
            continue
        metrics.append(m)
        mark = lambda b: "OK" if b else "×"
        print(f"  {c:<11}{m.get('annualized', 0) * 100:>8.2f}%"
              f"{m.get('raw_score', m['score']):>9.3f}{m['score']:>9.3f}"
              f"{m.get('annualized', 0) * 100:>8.2f}%"
              f"{m.get('r2', 0):>7.3f}"
              f"{(m.get('rel_excess') if m.get('rel_excess') is not None else float('nan')):>10.2%}"
              f"{mark(m['passed_momentum']):>7}{mark(m['passed_r2']):>6}"
              f"{mark(m['passed_rel_strength']):>7}"
              f"{mark(m['passed_momentum'] and m['passed_r2'] and m['passed_rel_strength']):>6}")

    print("\n" + "=" * 132)
    print("  _apply_filters 后 / _select_targets 结果")
    print("=" * 132)
    filt = strat._apply_filters(metrics)
    print(f"  通过过滤: {[m['etf'] for m in filt]}")
    sel = strat._select_targets(metrics)
    print(f"  最终目标: {[(m['etf'], round(m['score'], 3)) for m in sel]}")


if __name__ == "__main__":
    asyncio.run(main())
