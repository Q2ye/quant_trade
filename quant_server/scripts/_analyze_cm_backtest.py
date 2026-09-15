# -*- coding: utf-8 -*-
"""跨市场动量避险轮动 v1.0（实盘实例 4eab20a9）7.6 年回测归因 —— 一次性诊断脚本。

用法: cd quant_server && .venv/Scripts/python.exe scripts/_analyze_cm_backtest.py [task_id]

输出：
  1. 总览 + 年度收益（vs 沪深300）
  2. 月度收益矩阵
  3. 回撤区间（>5%）逐段
  4. 逐标的净现金流贡献（谁赚钱谁亏钱）
  5. 持有期统计
  6. regime（走弱期）分段盈亏 —— 从日志解析逐日 regime
"""
import asyncio
import re
import sys
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
from typing import Optional

TASK = sys.argv[1] if len(sys.argv) > 1 else "a5b10bff-4705-49c2-830c-436846de07a8"
LOG = Path(__file__).resolve().parent.parent / "logs" / "quant_server.log"
OUT = Path(__file__).resolve().parent.parent / "logs" / "_cm_backtest_attribution.txt"

_lines: list[str] = []


def p(msg: str = "") -> None:
    print(msg, flush=True)
    _lines.append(msg)


# ---------------------------------------------------------------- 日志解析

def parse_regime(thread_tag: Optional[str] = None) -> pd.DataFrame:
    """从日志逐日抓 走弱期 / 候选数 / 目标 / top1。

    日志顺序：先 `走弱期=...`（可能多行）后 `[handle_bar_batch] <date> 完成`。

    Args:
        thread_tag: 只取该工作线程的行（回测日志的线程名列带任务后缀，如
            `backtest-de07a8`）。**同一日志文件里跑过多次回测时必须指定**，
            否则同一交易日会有多份记录。为 None 时保留首次出现的那份。
    """
    pat_regime = re.compile(r"走弱期=(\w+) above=(\d+) below=(\d+)")
    pat_cand = re.compile(r"候选=(\d+) 目标=\[([^\]]*)\] top1=(\S+?)\(score=([\d.]+)\)")
    pat_date = re.compile(r"\[handle_bar_batch\] (\d{4}-\d{2}-\d{2}) 完成")

    rows, cur = [], {}
    with open(LOG, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if thread_tag and thread_tag not in line:
                continue
            m = pat_regime.search(line)
            if m:
                cur["weak"] = m.group(1) == "True"
                cur["above"] = int(m.group(2))
                cur["below"] = int(m.group(3))
                continue
            m = pat_cand.search(line)
            if m:
                cur["n_cand"] = int(m.group(1))
                cur["target"] = m.group(2).replace("'", "")
                cur["top1"] = m.group(3)
                cur["top1_score"] = float(m.group(4))
                continue
            m = pat_date.search(line)
            if m:
                rows.append({"trade_date": m.group(1), **cur})
                cur = {}
    df = pd.DataFrame(rows)
    for c in ("weak", "above", "below", "n_cand", "target", "top1", "top1_score"):
        if c not in df.columns:
            df[c] = np.nan
    # 未指定线程时，同一日期可能有多轮回测的记录 → 保留首次出现（= 最早跑的那轮）
    return df.drop_duplicates(subset="trade_date", keep="first").reset_index(drop=True)


# ---------------------------------------------------------------- 数据加载

async def load() -> tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    from shared.database.session.connection_pool import get_connection_pool
    from sqlalchemy import text

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    async with sf() as s:
        r = await s.execute(text(
            "SELECT trade_date, equity, cash, market_value FROM backtest_equity_curves "
            "WHERE task_id=:t ORDER BY trade_date"), {"t": TASK})
        eq = pd.DataFrame(r.fetchall(), columns=["trade_date", "equity", "cash", "market_value"])

        r = await s.execute(text(
            "SELECT trade_date, ts_code, volume, market_value FROM backtest_positions "
            "WHERE task_id=:t ORDER BY trade_date"), {"t": TASK})
        allpos = pd.DataFrame(r.fetchall(),
                              columns=["trade_date", "ts_code", "volume", "market_value"])
        allpos["trade_date"] = pd.to_datetime(allpos["trade_date"]).dt.strftime("%Y-%m-%d")
        allpos["market_value"] = allpos["market_value"].astype(float)
        allpos["volume"] = allpos["volume"].astype(int)
        open_pos = allpos[allpos["trade_date"] == allpos["trade_date"].max()]

        r = await s.execute(text(
            "SELECT trade_time, ts_code, direction, price, volume, value, commission, tax "
            "FROM backtest_trades WHERE task_id=:t ORDER BY trade_time, direction DESC"),
            {"t": TASK})
        tr = pd.DataFrame(r.fetchall(), columns=[
            "trade_date", "ts_code", "direction", "price", "volume", "value", "commission", "tax"])
        # trade_time 存的是「北京零点」转 UTC（16:00 前一日）→ 必须转回东八区才是成交日
        tr["trade_date"] = (
            pd.to_datetime(tr["trade_date"], utc=True)
            .dt.tz_convert("Asia/Shanghai").dt.strftime("%Y-%m-%d")
        )

        r = await s.execute(text(
            "SELECT name, config, result FROM backtest_tasks WHERE id=:t"), {"t": TASK})
        row = r.fetchone()
        cfg = row[1] if isinstance(row[1], dict) else {}
        res = row[2] if isinstance(row[2], dict) else {}
        meta = {"name": row[0], "initial_capital": 1_000_000.0,
                "commission_rate": 0.0001, "slippage_rate": 0.0001, **cfg,
                **{k: res.get(k) for k in (
                    "total_return", "annual_return", "sharpe_ratio", "max_drawdown", "win_rate",
                    "num_trades", "profit_factor", "calmar_ratio", "volatility",
                    "avg_holding_days", "avg_trade_return", "max_consecutive_losses",
                    "max_drawdown_period", "excess_metrics", "risk_violations")}}

        r = await s.execute(text(
            "SELECT trade_date, close FROM index_daily WHERE ts_code='000300.SH' "
            "AND trade_date BETWEEN :s AND :e ORDER BY trade_date"),
            {"s": eq["trade_date"].iloc[0], "e": eq["trade_date"].iloc[-1]})
        bm = pd.DataFrame(r.fetchall(), columns=["trade_date", "close"])

    await pool.close()
    for d in (eq, tr, bm):
        d["trade_date"] = pd.to_datetime(d["trade_date"]).dt.strftime("%Y-%m-%d")
    for c in ("equity", "cash", "market_value"):
        eq[c] = eq[c].astype(float)
    for c in ("price", "value", "commission", "tax"):
        tr[c] = tr[c].astype(float)
    tr["volume"] = tr["volume"].astype(int)
    bm["close"] = bm["close"].astype(float)
    return eq, tr, meta, bm, open_pos, allpos


# ---------------------------------------------------------------- 回撤区间

def drawdown_episodes(eq: pd.DataFrame, threshold: float = 0.05) -> list[dict]:
    """经典口径：从「创新高」到「重新收复该高点」为一个不重叠的回撤区间。"""
    e = eq["equity"].values
    dates = eq["trade_date"].values
    n = len(e)
    eps, pk = [], 0          # pk = 当前运行最高点的下标（= 上一个回撤的起点）
    for i in range(1, n):
        if e[i] >= e[pk]:
            if pk < i - 1:                       # 中间不是单调上升 → 存在一段回撤
                seg = slice(pk, i)
                k = pk + int(np.argmin(e[seg]))
                depth = e[k] / e[pk] - 1
                if depth <= -threshold:
                    eps.append({
                        "peak": dates[pk], "trough": dates[k], "recover": dates[i],
                        "depth": float(depth), "days_to_trough": k - pk,
                        "days_to_recover": i - k, "days_total": i - pk,
                    })
            pk = i
    if pk < n - 1:                                # 末尾未收复
        seg = slice(pk, n)
        k = pk + int(np.argmin(e[seg]))
        depth = e[k] / e[pk] - 1
        if depth <= -threshold:
            eps.append({
                "peak": dates[pk], "trough": dates[k], "recover": None,
                "depth": float(depth), "days_to_trough": k - pk,
                "days_to_recover": None, "days_total": n - 1 - pk,
            })
    return eps


# ---------------------------------------------------------------- 逐标的 FIFO

def round_trips(tr: pd.DataFrame) -> pd.DataFrame:
    """FIFO 配对成完整的持仓回合，算单笔已实现盈亏。"""
    out = []
    for code, g in tr.groupby("ts_code", sort=False):
        lots: deque = deque()
        for _, r in g.iterrows():
            if r["direction"] == "buy":
                lots.append([r["price"], r["volume"], r["trade_date"], r["commission"]])
            else:
                qty, sell_v, sell_c, sell_t = r["volume"], r["value"], r["commission"], r["tax"]
                sell_v -= sell_c + sell_t
                while qty > 0 and lots:
                    lot = lots[0]
                    take = min(qty, lot[1])
                    cost = lot[0] * take + lot[3] * (take / lot[1] if lot[1] else 0)
                    out.append({
                        "ts_code": code, "entry_date": lot[2], "exit_date": r["trade_date"],
                        "qty": take, "entry_px": lot[0], "exit_px": r["price"],
                        "pnl": sell_v * (take / r["volume"]) - cost,
                        "ret": r["price"] / lot[0] - 1.0,
                    })
                    lot[1] -= take
                    qty -= take
                    if lot[1] == 0:
                        lots.popleft()
    return pd.DataFrame(out)


# ---------------------------------------------------------------- 主流程

async def main() -> None:
    eq, tr, meta, bm, open_pos, allpos = await load()
    reg = parse_regime()

    p("=" * 88)
    p(f"跨市场动量避险轮动 v1.0 回测归因  task={TASK}")
    p(f"{meta['name']}  {str(meta['start_date'])[:10]} ~ {str(meta['end_date'])[:10]}  "
      f"初始={float(meta['initial_capital']):,.0f}  佣金={float(meta['commission_rate']):.4%}  "
      f"滑点={float(meta['slippage_rate']):.4%}")
    p(f"总收益={float(meta['total_return']):.2%}  年化={float(meta['annual_return']):.2%}  "
      f"夏普={float(meta['sharpe_ratio']):.3f}  Calmar={float(meta['calmar_ratio']):.3f}  "
      f"最大回撤={float(meta['max_drawdown']):.2%}")
    # ⚠️ avg_trade_return 单位是**元/笔**（不是比率）—— 曾误用 :.2% 格式化，凭空放大 100 倍。
    #    口径见 backtest_engine.py:1266 `sum(trade_pnls)/len(trade_pnls)`，trade_pnls 是金额列表。
    p(f"胜率={float(meta['win_rate']):.1%}（按成交行 773 行统计，非往返）  笔数={meta['num_trades']}  "
      f"盈亏比={float(meta['profit_factor']):.3f}  单笔均值={float(meta['avg_trade_return']):,.0f} 元/行  "
      f"平均持有={float(meta['avg_holding_days']):.1f}日  最大连亏={meta['max_consecutive_losses']}")
    p(f"最大回撤区间: {meta['max_drawdown_period']}   超额: {meta['excess_metrics']}")
    p(f"风控违规: {meta['risk_violations']}")
    p("=" * 88)

    eq = eq.sort_values("trade_date").reset_index(drop=True)
    e = eq["equity"].values
    eq["ret"] = eq["equity"].pct_change().fillna(0.0)
    years = (pd.to_datetime(eq["trade_date"].iloc[-1]) - pd.to_datetime(eq["trade_date"].iloc[0])).days / 365.25
    cagr = (e[-1] / e[0]) ** (1 / years) - 1
    vol = eq["ret"].std() * np.sqrt(252)

    bm = bm.sort_values("trade_date").reset_index(drop=True)
    bm["ret"] = bm["close"].pct_change().fillna(0.0)
    bm_years = (pd.to_datetime(bm["trade_date"].iloc[-1]) - pd.to_datetime(bm["trade_date"].iloc[0])).days / 365.25
    bm_cagr = (bm["close"].iloc[-1] / bm["close"].iloc[0]) ** (1 / bm_years) - 1

    p(f"区间 {years:.2f} 年  年化={cagr:.2%}  年化波动={vol:.2%}  基准年化={bm_cagr:.2%}  "
      f"超额年化={cagr - bm_cagr:+.2%}")

    # ---- 1. 年度 ----
    p("\n【1】年度收益（策略 vs 沪深300）")
    eq["y"] = eq["trade_date"].str[:4]
    bm["y"] = bm["trade_date"].str[:4]
    p(f"  {'年份':<6}{'策略':>10}{'基准':>10}{'超额':>10}{'年内最大回撤':>14}{'年末权益':>16}")
    for y, g in eq.groupby("y"):
        r = g["equity"].iloc[-1] / g["equity"].iloc[0] - 1
        bg = bm[bm["y"] == y]
        br = bg["close"].iloc[-1] / bg["close"].iloc[0] - 1 if len(bg) else np.nan
        mdd = (g["equity"] / g["equity"].cummax() - 1).min()
        p(f"  {y:<6}{r:>10.2%}{br:>10.2%}{r - br:>+10.2%}{mdd:>14.2%}{g['equity'].iloc[-1]:>16,.0f}")

    # ---- 2. 月度 ----
    p("\n【2】月度收益矩阵（%）  — 正/负月数统计")
    eq["ym"] = eq["trade_date"].str[:7]
    m = eq.groupby("ym")["equity"].last()
    first = eq.groupby("ym")["equity"].first()
    mret = (m / first - 1) * 100
    piv = mret.reset_index()
    piv["Y"] = piv["ym"].str[:4]
    piv["M"] = piv["ym"].str[5:7]
    table = piv.pivot(index="Y", columns="M", values="equity")
    p("       " + "".join(f"{c:>8}" for c in table.columns))
    for y, row in table.iterrows():
        p(f"  {y}  " + "".join(f"{v:>8.2f}" if pd.notna(v) else f"{'--':>8}" for v in row))
    pos, neg = (mret > 0).sum(), (mret < 0).sum()
    p(f"  正收益月 {pos} / 负收益月 {neg} / 合计 {len(mret)}  "
      f"胜率={pos / len(mret):.1%}  最好={mret.max():.2f}%  最差={mret.min():.2f}%  中位={mret.median():.2f}%")

    # ---- 3. 回撤 ----
    p("\n【3】回撤区间（不重叠口径：从创新高到收复，深度 > 5%）")
    eps = drawdown_episodes(eq, 0.05)
    p(f"  {'峰值日':<12}{'谷底日':<12}{'恢复日':<12}{'深度':>8}{'下跌天数':>10}{'修复天数':>10}{'合计':>8}")
    for ep in eps:
        p(f"  {ep['peak']:<12}{ep['trough']:<12}{(ep['recover'] or '未恢复'):<12}"
          f"{ep['depth']:>8.2%}{ep['days_to_trough']:>10}"
          f"{(ep['days_to_recover'] if ep['days_to_recover'] is not None else '-'):>10}"
          f"{ep['days_total']:>8}")
    tot_dd_days = sum(ep["days_total"] for ep in eps)
    p(f"  共 {len(eps)} 段，在回撤中 {tot_dd_days} 个交易日 / 全区间 {len(eq)} 日 = {tot_dd_days / len(eq):.1%}")
    p(f"  >10% 的大回撤：")
    for ep in [x for x in eps if x["depth"] <= -0.10]:
        p(f"    {ep['peak']} → {ep['trough']} ({ep['depth']:.2%}, {ep['days_to_trough']}日) "
          f"收复 {ep['recover'] or '未收复'}（再 {ep['days_to_recover']} 日）")

    # ---- 4. 逐标的 ----
    p("\n【4】逐标的贡献（净现金流 = 卖出净收入 − 买入含费成本；未平仓部分计入持仓市值）")
    tr["cashflow"] = np.where(tr["direction"] == "buy",
                              -(tr["value"] + tr["commission"]),
                              tr["value"] - tr["commission"] - tr["tax"])
    by = tr.groupby("ts_code")["cashflow"].sum().sort_values(ascending=False)
    if len(open_pos):
        by = by.add(open_pos.set_index("ts_code")["market_value"], fill_value=0.0)
    by = by.sort_values(ascending=False)
    buy_cnt = tr[tr["direction"] == "buy"].groupby("ts_code").size()
    p(f"  {'代码':<12}{'总贡献':>14}{'买入次数':>10}{'占总盈亏':>10}")
    total_pnl = by.sum()
    for code, v in by.items():
        p(f"  {code:<12}{v:>14,.0f}{int(buy_cnt.get(code, 0)):>10}{v / total_pnl:>10.1%}")
    p(f"  {'合计':<12}{total_pnl:>14,.0f}{'':>10}{1.0:>10.1%}")
    p(f"  校验: 期末权益 {e[-1]:,.0f} − 初始 {e[0]:,.0f} = {e[-1] - e[0]:,.0f}  "
      f"(差 {e[-1] - e[0] - total_pnl:,.0f})")
    p(f"  期末未平仓：")
    for _, r in open_pos.sort_values("market_value", ascending=False).iterrows():
        p(f"    {r['ts_code']:<12} {int(r['volume']):>10,} 股  市值 {r['market_value']:>14,.0f}")

    # 盈亏分布
    win = by[by > 0]
    los = by[by < 0]
    p(f"  盈利标的 {len(win)} 个合计 +{win.sum():,.0f} / 亏损标的 {len(los)} 个合计 {los.sum():,.0f}"
      f" / 盈亏比 {abs(win.sum() / los.sum()) if len(los) and los.sum() else float('nan'):.2f}")

    # ---- 4.5 按「入场时 regime」归因每一笔完整交易（规避日频对齐问题）----
    rt0 = round_trips(tr)
    if len(rt0) and len(reg):
        rw = reg.set_index("trade_date")["weak"]
        rt0["入场弱"] = rt0["entry_date"].map(rw)
        rt0["出场弱"] = rt0["exit_date"].map(rw)
        p("\n【4.5】按「建仓时所处 regime」归因完整交易（经济单元口径）")
        for w, g in rt0.dropna(subset=["入场弱"]).groupby("入场弱"):
            p(f"  {'走弱期建仓' if w else '非走弱建仓'}: {len(g)} 笔  平均单笔={g['ret'].mean():+.2%}  "
              f"中位={g['ret'].median():+.2%}  胜率={(g['ret'] > 0).mean():.1%}  合计盈亏={g['pnl'].sum():>+12,.0f}")
        p(f"  （对照）全部 {len(rt0)} 笔：平均单笔={rt0['ret'].mean():+.2%}  "
          f"胜率={(rt0['ret'] > 0).mean():.1%}  合计盈亏={rt0['pnl'].sum():>+12,.0f}")
        # 按年看「建仓 regime」分布
        rt0["y"] = rt0["entry_date"].str[:4]
        p("  逐年：")
        for y, g in rt0.groupby("y"):
            gw = g[g["入场弱"] == True]
            p(f"    {y}: 共{len(g):>3} 笔  走弱建仓 {len(gw):>3} 笔（盈亏 {gw['pnl'].sum():>+12,.0f}）  "
              f"非弱建仓 {len(g) - len(gw):>3} 笔（盈亏 {g[g['入场弱'] == False]['pnl'].sum():>+12,.0f}）")

    # ---- 5. 持有期 ----
    rt = round_trips(tr)
    if len(rt):
        rt["days"] = (pd.to_datetime(rt["exit_date"]) - pd.to_datetime(rt["entry_date"])).dt.days
        p("\n【5】完整持仓回合统计（FIFO 配对）")
        p(f"  回合数={len(rt)}  平均单笔={rt['ret'].mean():+.2%}  中位={rt['ret'].median():+.2%}  "
          f"胜率={(rt['ret'] > 0).mean():.1%}  盈亏比="
          f"{abs(rt[rt['ret'] > 0]['ret'].sum() / rt[rt['ret'] < 0]['ret'].sum()):.2f}")
        p(f"  平均持有自然日={rt['days'].mean():.1f}  中位={rt['days'].median():.0f}  "
          f"最长={rt['days'].max():.0f}")
        p(f"  最好一笔={rt['ret'].max():+.1%}  最差一笔={rt['ret'].min():+.1%}")
        p("  分标的回合：")
        for code, g in rt.groupby("ts_code"):
            p(f"    {code:<12} n={len(g):<4} 均值={g['ret'].mean():>+7.2%} "
              f"胜率={(g['ret'] > 0).mean():>6.1%} 合计盈亏={g['pnl'].sum():>14,.0f}")

    # ---- 6. regime ----
    if len(reg):
        p("\n【6】regime 分段盈亏（走弱期 = MA 下方指数数 > 上方；日志逐日解析）")
        d = eq.merge(reg, on="trade_date", how="inner")
        p(f"  对齐交易日 {len(d)} / 净值 {len(eq)} / 日志 {len(reg)}")
        d["seg"] = (d["weak"] != d["weak"].shift()).cumsum()
        rows = []
        for sid, g in d.groupby("seg"):
            r = g["equity"].iloc[-1] / g["equity"].iloc[0] - 1
            rows.append({"弱": bool(g["weak"].iloc[0]), "起": g["trade_date"].iloc[0],
                         "止": g["trade_date"].iloc[-1], "天数": len(g), "段收益": r,
                         "日均bp": r / len(g) * 1e4})
        s = pd.DataFrame(rows)
        # 逐日复利累乘：这才与总收益严格自洽（分段累计会漏掉每段首日收益）
        d["log1p"] = np.log1p(d["ret"])
        tot = 1.0
        for w, g in d.groupby("weak"):
            wd = len(g)
            contrib = float(np.expm1(g["log1p"].sum()))
            tot *= 1 + contrib
            sg = s[s["弱"] == w]
            p(f"  {'走弱期' if w else '非走弱期'}: {wd} 日 ({wd / len(d):.1%})  "
              f"逐日累乘贡献={contrib:+.1%}  段数={len(sg)}  段胜率={(sg['段收益'] > 0).mean():.1%}")
        p(f"  校验: (1+走弱)×(1+非走弱) − 1 = {tot - 1:+.1%}  vs 实际总收益 "
          f"{e[-1] / e[0] - 1:+.1%}")
        # 同期性偏差对照：regime 判据用**当日**收盘 vs MA10，与当日收益同源。
        # 持仓收益实际由**前一日**决策的 regime 决定 → 用 ret[t] 对 weak[t-1] 再算一遍。
        d["weak_lag"] = d["weak"].shift(1)
        dd = d.dropna(subset=["weak_lag"])
        tot2 = 1.0
        line = []
        for w, g in dd.groupby("weak_lag"):
            c = float(np.expm1(g["log1p"].sum()))
            tot2 *= 1 + c
            line.append(f"{'走弱' if w else '非弱'}={c:+.1%}")
        p(f"  ⚠️ 同期性偏差对照（按**前一日** regime 归属当日收益）：{'  '.join(line)}"
          f"  → 合计 {tot2 - 1:+.1%}")
        flips = int((d["weak"] != d["weak"].shift()).sum() - 1)
        p(f"  regime 翻转 {flips} 次 / {len(d)} 日 → 平均每 {len(d) / flips:.1f} 个交易日翻转一次")
        p("\n  最长 10 段（按天数）：")
        for _, r in s.nlargest(10, "天数").iterrows():
            p(f"    {'走弱' if r['弱'] else '非弱'} {r['起']}~{r['止']} {int(r['天数']):>4}日 "
              f"{r['段收益']:>+8.2%}  日均{r['日均bp']:>+7.2f}bp")
        # 每日收益按 regime 拆
        p("\n  日收益分布：")
        for w, g in d.groupby("weak"):
            p(f"    {'走弱期' if w else '非走弱期'}: 日胜率={(g['ret'] > 0).mean():.1%}  "
              f"日均={g['ret'].mean() * 100:+.3f}%  日波动={g['ret'].std() * 100:.2f}%  "
              f"最好={g['ret'].max():+.2%} 最差={g['ret'].min():+.2%}")
        d["held"] = d["top1"].ffill()
        p("\n  Top10 单日盈利：")
        for _, r in d.nlargest(10, "ret").iterrows():
            p(f"    {r['trade_date']} {r['ret']:>+7.2%}  {'走弱' if r['weak'] else '非弱'} "
              f"当日选中={r.get('held') if pd.notna(r.get('held')) else '-'}")
        p("\n  Top10 单日亏损：")
        for _, r in d.nsmallest(10, "ret").iterrows():
            p(f"    {r['trade_date']} {r['ret']:>+7.2%}  {'走弱' if r['weak'] else '非弱'} "
              f"当日选中={r.get('held') if pd.notna(r.get('held')) else '-'}")

    # ---- 7. 换手 / 空仓 ----
    p("\n【7】仓位与换手")
    eq["pos_pct"] = eq["market_value"] / eq["equity"]
    empty = (eq["pos_pct"] < 0.01).sum()
    p(f"  平均仓位={eq['pos_pct'].mean():.1%}  中位={eq['pos_pct'].median():.1%}  "
      f"空仓天数={empty} ({empty / len(eq):.1%})  满仓(>95%)天数={(eq['pos_pct'] > 0.95).sum()}")
    n_buy = int((tr["direction"] == "buy").sum())
    p(f"  总买入 {n_buy} 次 / 总卖出 {len(tr) - n_buy} 次 → 年化换手约 {n_buy / years:.0f} 次/年")
    p(f"  累计费用: 佣金={tr['commission'].sum():,.0f}  印花税={tr['tax'].sum():,.0f}  "
      f"合计={tr['commission'].sum() + tr['tax'].sum():,.0f} "
      f"(占期末权益 {(tr['commission'].sum() + tr['tax'].sum()) / e[-1]:.2%})")
    p(f"  单笔平均手续费={tr['commission'].mean():,.1f} 元  平均单笔金额={tr['value'].mean():,.0f} 元")

    # ---- 8. 与基准的关系 ----
    p("\n【8】与沪深300 的关系（月度）")
    eq["ym"] = eq["trade_date"].str[:7]
    bm["ym"] = bm["trade_date"].str[:7]
    sm = eq.groupby("ym")["equity"].last() / eq.groupby("ym")["equity"].first() - 1
    bmr = bm.groupby("ym")["close"].last() / bm.groupby("ym")["close"].first() - 1
    j = pd.concat([sm.rename("s"), bmr.rename("b")], axis=1).dropna()
    p(f"  月度相关={j['s'].corr(j['b']):.3f}  月度beta={j['s'].cov(j['b']) / j['b'].var():.3f}")
    dn = j[j["b"] < 0]
    up = j[j["b"] > 0]
    p(f"  基准上涨月 {len(up)} 个：策略均值={up['s'].mean():+.2%}  胜率={(up['s'] > 0).mean():.1%}")
    p(f"  基准下跌月 {len(dn)} 个：策略均值={dn['s'].mean():+.2%}  胜率={(dn['s'] > 0).mean():.1%}  "
      f"→ 下跌月策略平均跑赢基准 {(dn['s'] - dn['b']).mean():+.2%}")

    # ---- 9. 近期逐月与当前持仓 ----
    p("\n【9】最近 12 个月逐月")
    last12 = mret.tail(12)
    for ym, v in last12.items():
        bg = bmr.get(ym, np.nan)
        tag = "走弱" if (len(reg) and reg[reg["trade_date"].str[:7] == ym]["weak"].mean() > 0.5) else "非弱"
        p(f"    {ym}  策略={v:>+7.2f}%  基准={bg * 100:>+7.2f}%  超额={v - bg * 100:>+7.2f}%  [{tag}为主]")
    p(f"\n  期末持仓（2026-09-10）：")
    for _, r in open_pos.iterrows():
        p(f"    {r['ts_code']}  {int(r['volume']):,} 股  市值 {r['market_value']:,.0f}  "
          f"占期末权益 {r['market_value'] / e[-1]:.1%}")

    # ---- 10. 逐年 regime 拆分 ----
    if len(reg):
        p("\n【10】逐年 regime 拆分（各年走弱/非走弱日分别累乘贡献）")
        d["y"] = d["trade_date"].str[:4]
        p(f"  {'年份':<6}{'走弱日':>7}{'走弱贡献':>11}{'非弱日':>7}{'非弱贡献':>11}{'合计':>11}")
        for y, g in d.groupby("y"):
            gw = g[g["weak"]]
            gn = g[~g["weak"]]
            cw = float(np.expm1(gw["log1p"].sum())) if len(gw) else 0.0
            cn = float(np.expm1(gn["log1p"].sum())) if len(gn) else 0.0
            p(f"  {y:<6}{len(gw):>7}{cw:>+11.2%}{len(gn):>7}{cn:>+11.2%}{(1 + cw) * (1 + cn) - 1:>+11.2%}")

    # ---- 11. 持仓标的 × regime 归因 ----
    if len(reg) and len(allpos):
        p("\n【11】走弱期/非走弱期 实际持仓标的归因（用持仓快照反推每只 ETF 的日收益）")
        mv = allpos.pivot_table(index="trade_date", columns="ts_code",
                                values="market_value", aggfunc="last")
        vol = allpos.pivot_table(index="trade_date", columns="ts_code",
                                 values="volume", aggfunc="last")
        px = (mv / vol.replace(0, np.nan)).sort_index()
        r_etf = px.pct_change()
        # 每日实际持仓 = 市值最大的那只
        hold = mv.idxmax(axis=1)
        w = mv.max(axis=1) / eq.set_index("trade_date")["equity"]
        hh = pd.DataFrame({"code": hold, "w": w}).reset_index().rename(
            columns={"index": "trade_date"})
        hh = hh.merge(reg[["trade_date", "weak"]], on="trade_date", how="inner")
        # 每只 ETF 在各自 regime 下的日收益贡献
        rows = []
        for _, r in hh.iterrows():
            c = r["code"]
            if pd.isna(c) or r["trade_date"] not in r_etf.index:
                continue
            v = r_etf.at[r["trade_date"], c] if c in r_etf.columns else np.nan
            if pd.isna(v):
                continue
            rows.append({"code": c, "weak": bool(r["weak"]), "w": float(r["w"]),
                         "r": float(v), "contrib": float(r["w"]) * float(v)})
        hr = pd.DataFrame(rows)
        p(f"  【按 regime】")
        bmr2 = bm[["trade_date", "ret"]].rename(columns={"ret": "bm"})
        jj = d[["trade_date", "weak", "ret"]].merge(bmr2, on="trade_date", how="left")
        for wk, g in hr.groupby("weak"):
            bg = jj[jj["weak"] == wk]
            p(f"    {'走弱期' if wk else '非走弱期'}: 持仓日 {len(g)}  "
              f"持仓标的日收益均值={g['r'].mean():+.3%}  "
              f"加权贡献合计={g['contrib'].sum():+.1%}（算术叠加，非复利）"
              f"  ｜ 沪深300 同期日均={bg['bm'].mean():+.3%}")
        for wk, g in hr.groupby("weak"):
            p(f"    {'走弱期' if wk else '非走弱期'} 持仓构成：国债 {int((g['code'] == '511010.SH').sum())} 日 "
              f"/ 全球池 {int(g['code'].isin(['518880.SH','513100.SH','513500.SH','513030.SH','513520.SH','159920.SZ','513050.SH','513330.SH','513180.SH','159980.SZ','159985.SZ']).sum())} 日 "
              f"/ 中国池 {int(g['code'].isin(['510050.SH','510300.SH','510500.SH','512100.SH','159915.SZ','159949.SZ','588080.SH','512880.SH','515880.SH','512480.SH','512400.SH','512660.SH','512800.SH','512690.SH','512170.SH','512010.SH','515030.SH']).sum())} 日")
        p(f"  【走弱期持仓明细】")
        gw = hr[hr["weak"]]
        for code, g in gw.groupby("code"):
            p(f"    {code:<12} 持有{len(g):>4}日  平均日收益={g['r'].mean():>+7.3%}  "
              f"累计贡献={g['contrib'].sum():>+7.1%}")
        p(f"  【非走弱期持仓明细（Top10 贡献）】")
        gn = hr[~hr["weak"]]
        agg = gn.groupby("code").agg(日数=("r", "size"), 平均日收益=("r", "mean"),
                                    累计贡献=("contrib", "sum"))
        for code, r in agg.sort_values("累计贡献", ascending=False).head(10).iterrows():
            p(f"    {code:<12} 持有{int(r['日数']):>4}日  平均日收益={r['平均日收益']:>+7.3%}  "
              f"累计贡献={r['累计贡献']:>+7.1%}")
        p(f"  【非走弱期最亏的 5 只】")
        for code, r in agg.sort_values("累计贡献").head(5).iterrows():
            p(f"    {code:<12} 持有{int(r['日数']):>4}日  平均日收益={r['平均日收益']:>+7.3%}  "
              f"累计贡献={r['累计贡献']:>+7.1%}")

    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[已写入 {OUT}]")


if __name__ == "__main__":
    asyncio.run(main())
