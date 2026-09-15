# -*- coding: utf-8 -*-
"""一次性诊断：ETF 底部策略 — 门控 + 持仓/出场 全链路诊断模拟（只读，不写库）

目的：量化「模型的信息量」与「策略实际收割到的收益」之间的差，并定位差额漏在哪条规则。
口径：逐字复刻活跃行 cebe247d 的参数与 on_bar / _check_exit / _make_entry：
      - 入场：候选日(low 为信号价) → 次日确认(close>信号价 且 vol_ratio>=1.0) → 成本=确认日收盘
      - 出场：牛市清仓 / 动态止损(max(min(base,-2.5*atr), base*1.5)) / 到期(hold>=maxd 且 pnl<=2%)
              / 移动止盈(track_high 用收盘价，(high-entry)/entry>=act 且 回撤>=dist)
      - 冷却 2 日、持仓上限 regime_max_positions、候选上限同值、权重=target[regime]/rmax
      同日顺序近似为：先出后进（实盘按 bar 到达顺序，标的影响有限）
      本脚本是策略内部记账口径（收盘判定，不含滑点/手续费），不是平台回测的替代。
执行：cd quant_server && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/_probe_etf_bottom_trade_sim.py [base_threshold]
"""
import sys
from datetime import date
from collections import defaultdict

import psycopg2, joblib, numpy as np

POOL = ['510050.SH','510300.SH','510500.SH','159919.SZ','510880.SH','512880.SH','512660.SH',
        '512800.SH','512100.SH','159915.SZ','159949.SZ','518880.SH','513100.SH','513050.SH',
        '511010.SH','511260.SH','510310.SH','159865.SZ','159825.SZ','159781.SZ','512170.SH',
        '159806.SZ','516510.SH','159840.SZ','512400.SH']
P = dict(  # 活跃行 cebe247d（2026-09-14 DB 实读）
    regime_adj={0: 0.06, 1: 0.0, 2: 0.06},
    regime_max_pos={0: 5, 1: 3, 2: 4},
    regime_max_hold={0: 25, 1: 14, 2: 20},
    regime_stop={0: -0.08, 1: -0.06, 2: -0.07},
    regime_trail_act={0: 0.06, 1: 0.04, 2: 0.05},
    regime_trail_dist={0: 0.10, 1: 0.06, 2: 0.08},
    market_target_pos={0: 0.55, 1: 0.75, 2: 0.0},
    atr_min=0.015, gate_band=0.03, cooling_days=2, min_warmup=60,
)
BASE_T = float(sys.argv[1]) if len(sys.argv) > 1 else 0.44
NO_BULL_EXIT = "nobull" in sys.argv        # 反事实：关闭「牛市清仓」
EXEC_OPEN = "open" in sys.argv             # 反事实：成交价用次日开盘（不改状态机）
NO_TRAIL = "notrail" in sys.argv           # 反事实：关闭移动止盈
NO_STOP = "nostop" in sys.argv             # 反事实：关闭止损
FIXED_STOP = "fixedstop" in sys.argv       # 反事实：止损不按 ATR 放宽（只用 regime_stop）
CAPITAL = 1_000_000.0
LABEL_N, LABEL_X, LABEL_Y = 10, 0.03, -0.05
RN = {0: "熊", 1: "震", 2: "牛"}
CFG = dict(host="localhost", port=5432, user="postgres", password="123456",
           database="quant_signals_dev")

art = joblib.load("storage/models/etf_bottom_v5_20260816.joblib")
model, feats = art["model"], art["feature_names"]
mu = np.array(art["scaler_params"]["mu"]); sg = np.array(art["scaler_params"]["sigma"]) + 1e-8

conn = psycopg2.connect(**CFG); cur = conn.cursor()
cur.execute("""SELECT ts_code, trade_date::text, factor_code, factor_value FROM factor_data
               WHERE ts_code = ANY(%s) AND factor_code = ANY(%s) AND trade_date >= '2020-06-01'""",
            (POOL, feats))
fac = defaultdict(lambda: defaultdict(dict))
for c, d, f, v in cur.fetchall():
    fac[c][d[:10]][f] = float(v) if v is not None else np.nan
cur.execute("""SELECT ts_code, trade_date::text, open, high, low, close FROM etf_daily
               WHERE ts_code = ANY(%s) AND trade_date >= '2020-06-01' ORDER BY ts_code, trade_date""",
            (POOL,))
px = defaultdict(dict)
for c, d, o, h, l, cl in cur.fetchall():
    px[c][d[:10]] = (float(o), float(h), float(l), float(cl))
cur.execute("""SELECT trade_date::text, close FROM index_daily
               WHERE ts_code='000905.SH' AND trade_date >= '2016-01-01' ORDER BY trade_date""")
csi = [(r[0][:10], float(r[1])) for r in cur.fetchall()]
conn.close()

# ── 逐 ETF-日：proba / atr_ratio_20 / volume_ma20_ratio / 因子 regime ──
proba, atr, volratio, freg = {}, {}, {}, {}
for c in POOL:
    fdates = sorted(fac[c].keys())
    pdates = sorted(px[c].keys())
    for i, d in enumerate(pdates):
        if i < P["min_warmup"]:
            continue
        near = [x for x in fdates if x <= d]
        if not near:
            continue

        def _nf(fc):
            for x in reversed(near):
                v = fac[c][x].get(fc)
                if v is not None and not (isinstance(v, float) and np.isnan(v)):
                    return float(v)
            return None

        row = fac[c][near[-1]]
        fv = np.array([row.get(f, np.nan) for f in feats], dtype=np.float64)
        if np.isnan(fv).mean() > 0.5:
            continue
        fv0 = np.nan_to_num(fv, nan=0.0)
        proba[(c, d)] = float(model.predict_proba(((fv0 - mu) / sg).reshape(1, -1))[0, 1])
        atr[(c, d)] = _nf("atr_ratio_20")
        volratio[(c, d)] = _nf("volume_ma20_ratio")
        rv = _nf("market_regime")
        freg[(c, d)] = max(0, min(2, int(rv))) if rv is not None else 1

all_dates = sorted({d for c in POOL for d in px[c].keys()})
D = {d: i for i, d in enumerate(all_dates)}
CSI_CL = [c for _, c in csi]
CSI_D = [d for d, _ in csi]


def mregime(d):
    m = [i for i, x in enumerate(CSI_D) if x <= d]
    if len(m) < 250:
        return 1
    j = m[-1]
    cl = CSI_CL[max(0, j - 249): j + 1]
    ma = sum(cl) / len(cl)
    if CSI_CL[j] < ma * (1 - P["gate_band"]):
        return 0
    if CSI_CL[j] > ma * (1 + P["gate_band"]):
        return 2
    return 1


def nxt_close(c, d, n):
    """d 之后第 n 个交易日收盘（用于标签口径对照）"""
    ds = [x for x in px[c] if x > d]
    ds.sort()
    return px[c][ds[n - 1]][3] if len(ds) >= n else None


def label_win(c, d):
    """标签：d 日收盘起 N 日内先触 +3%（同日双触记为胜）"""
    ds = sorted(x for x in px[c] if x > d)[:LABEL_N]
    c0 = px[c][d][3]
    for x in ds:
        _, h, l, _ = px[c][x]
        if h >= c0 * (1 + LABEL_X):
            return 1
        if l <= c0 * (1 - LABEL_Y):
            return 0
    return 0


def days_between(d1, d2):
    return (date.fromisoformat(d2[:10]) - date.fromisoformat(d1[:10])).days


buf, pos, high, cool = {}, {}, {}, {}
trades = []
cash = CAPITAL
equity_curve = []          # (date, equity, invested_ratio)

for d in all_dates:
    g = mregime(d)
    # ── 1) 出场管理 ──
    for c in list(pos.keys()):
        if d not in px[c]:
            continue
        close = px[c][d][3]
        ed, ep, sh, w = pos[c]
        high[c] = max(high.get(c, ep), close)
        r = freg.get((c, d), 1)
        reason = None
        if g == 2 and not NO_BULL_EXIT:
            reason = "牛市清仓"
        else:
            pnl = close / ep - 1
            ar = atr.get((c, d))
            bs = P["regime_stop"].get(r, -0.07)
            if FIXED_STOP or not ar or ar <= 0:
                ds_ = bs
            else:
                ds_ = max(min(bs, -2.5 * ar), bs * 1.5)
            hd = days_between(ed, d)
            md = P["regime_max_hold"].get(r, 20)
            ta = P["regime_trail_act"].get(r, 0.05)
            td = P["regime_trail_dist"].get(r, 0.08)
            dd = (high[c] - close) / high[c] if high[c] > 0 else 0
            if not NO_STOP and pnl < ds_:
                reason = "动态止损"
            elif hd >= md and pnl <= 0.02:
                reason = "到期"
            elif not NO_TRAIL and (high[c] - ep) / ep >= ta and dd >= td:
                reason = "移动止盈"
        if reason:
            cash += sh * close
            ret = close / ep - 1
            lb = label_win(c, ed)
            f10 = nxt_close(c, ed, LABEL_N)
            # 次日开盘成交变体：入场用 ed 之后第一个交易日开盘，出场用 d 之后第一个交易日开盘
            def _next_open(cc, dd_):
                ds2 = sorted(x for x in px[cc] if x > dd_)
                return px[cc][ds2[0]][0] if ds2 else None
            eo, xo = _next_open(c, ed), _next_open(c, d)
            trades.append(dict(code=c, ed=ed, xd=d, reason=reason, ret=ret,
                               ret_open=(xo / eo - 1) if (eo and xo) else np.nan,
                               hold_cal=days_between(ed, d), hold_bar=sum(1 for x in all_dates if ed < x <= d),
                               regime=freg.get((c, ed), 1), label=lb,
                               fwd10=(f10 / px[c][ed][3] - 1) if f10 else np.nan,
                               pnl_at_expiry=close / ep - 1))
            del pos[c]; high.pop(c, None); cool[c] = P["cooling_days"]

    # ── 2) 冷却递减 ──
    for c in list(cool.keys()):
        cool[c] -= 1
        if cool[c] <= 0:
            del cool[c]

    # ── 3) P4 确认（T+1：候选日的次日）──
    for c in list(buf.keys()):
        if d not in px[c]:
            continue
        if c in cool:
            buf.pop(c); continue
        if c in pos:
            continue
        r = freg.get((c, d), 1)
        gi = g
        if gi == 2:
            buf.pop(c); continue
        if len(pos) >= P["regime_max_pos"].get(r, 5):
            buf.pop(c); continue
        pinfo = buf.pop(c)
        if pinfo["sig_date"] >= d:          # T+1 守卫
            buf[c] = pinfo; continue
        w = P["market_target_pos"].get(r, 0.0) / max(P["regime_max_pos"].get(r, 3), 1)
        if w <= 0:
            continue
        close = px[c][d][3]
        if close > pinfo["sig_low"]:
            vr = volratio.get((c, d))
            if vr is not None and vr < 1.0:
                continue
            sh = max(int(cash * w / close / 100) * 100, 100)
            if sh * close > cash:
                sh = int(cash / close / 100) * 100
            if sh < 100:
                continue
            cash -= sh * close
            pos[c] = (d, close, sh, w)
            high[c] = close

    # ── 4) 新候选（按 proba 降序确定性口径）──
    if g != 2:
        cands = sorted([c for c in POOL if (c, d) in proba],
                       key=lambda c: -proba[(c, d)])
        for c in cands:
            if c in buf or c in pos or c in cool:
                continue
            r = freg.get((c, d), 1)
            if proba[(c, d)] < BASE_T + P["regime_adj"].get(r, 0.0):
                continue
            a = atr.get((c, d))
            if a is None or a < P["atr_min"]:
                continue
            if P["market_target_pos"].get(r, 0.0) / max(P["regime_max_pos"].get(r, 3), 1) <= 0:
                continue
            if len(pos) >= P["regime_max_pos"].get(r, 5):
                continue
            if len(buf) >= P["regime_max_pos"].get(r, 2):
                continue
            buf[c] = dict(proba=proba[(c, d)], sig_low=px[c][d][2], sig_date=d)

    # ── 5) 记录日终权益 ──
    mv = sum(sh * px[c][d][3] for c, (ed_, ep_, sh, w_) in pos.items() if d in px[c])
    eq = cash + mv
    equity_curve.append((d, eq, mv / eq if eq > 0 else 0.0))

# ── 汇总 ──
n = len(trades)
if not n:
    print("无交易"); sys.exit()
# ── 权益曲线（日频，含未平仓市值）──
eqs = np.array([e for _, e, _ in equity_curve])
util = np.array([u for _, _, u in equity_curve])
yrs = (date.fromisoformat(equity_curve[-1][0]) - date.fromisoformat(equity_curve[0][0])).days / 365.25
cagr = (eqs[-1] / eqs[0]) ** (1 / yrs) - 1
peak = np.maximum.accumulate(eqs)
mdd = float(((eqs - peak) / peak).min())
dret = np.diff(eqs) / eqs[:-1]
print(f"【权益】终止 {eqs[-1]:,.0f} / 起始 {eqs[0]:,.0f} → 总收益 {eqs[-1]/eqs[0]-1:+.2%}"
      f" | 年化 {cagr:+.2%} | MDD {mdd:.2%} | 年化波动 {dret.std()*np.sqrt(244):.2%}"
      f" | 平均仓位利用率 {util.mean():.1%}（中位 {np.median(util):.1%}）"
      f" | 空仓天数占比 {(util<0.01).mean():.1%}")
rets = np.array([t["ret"] for t in trades])
fwds = np.array([t["fwd10"] for t in trades], dtype=np.float64)
holds = np.array([t["hold_bar"] for t in trades])
print(f"【base={BASE_T:.2f}】交易 {n} 笔 | 区间 {all_dates[0]} ~ {all_dates[-1]}")
print(f"实现收益: 等权平均 {rets.mean():+.2%} 中位 {np.median(rets):+.2%} 胜率 {(rets>0).mean():.1%}"
      f" 最好 {rets.max():+.1%} 最差 {rets.min():+.1%} | 简单累加 {rets.sum():+.1%}")
print(f"标签口径同期: 10日远期收益 平均 {np.nanmean(fwds):+.2%} 中位 {np.nanmedian(fwds):+.2%}"
      f" | 标签胜率 {np.mean([t['label'] for t in trades]):.1%}")
print(f"持有: 交易日 平均 {holds.mean():.1f} 中位 {np.median(holds):.0f} 最长 {holds.max()}"
      f" | 超过 regime 上限的笔数 {sum(1 for t in trades if t['hold_bar'] > P['regime_max_hold'].get(t['regime'],20))}")
print("\n出场原因分布:")
for r in sorted({t["reason"] for t in trades}):
    s = [t for t in trades if t["reason"] == r]
    sr = np.array([t["ret"] for t in s])
    print(f"  {r:6s} {len(s):4d} 笔 ({len(s)/n:5.1%}) | 平均 {sr.mean():+7.2%} 胜率 {(sr>0).mean():5.1%}"
          f" | 平均持有 {np.mean([t['hold_bar'] for t in s]):5.1f} 日")
print("\n按入场 regime:")
for r in (0, 1, 2):
    s = [t for t in trades if t["regime"] == r]
    if s:
        sr = np.array([t["ret"] for t in s])
        print(f"  {RN[r]} {len(s):4d} 笔 | 平均 {sr.mean():+7.2%} 胜率 {(sr>0).mean():5.1%}")
print("\n【核心对照】标签判胜 vs 实盘结果:")
win = [t for t in trades if t["label"] == 1]
lose = [t for t in trades if t["label"] == 0]
print(f"  标签判胜 {len(win)} 笔 → 实盘盈利 {sum(1 for t in win if t['ret']>0)} 笔"
      f" ({sum(1 for t in win if t['ret']>0)/max(len(win),1):.1%})，平均实现收益 {np.mean([t['ret'] for t in win]):+.2%}")
print(f"  标签判负 {len(lose)} 笔 → 实盘盈利 {sum(1 for t in lose if t['ret']>0)} 笔"
      f" ({sum(1 for t in lose if t['ret']>0)/max(len(lose),1):.1%})，平均实现收益 {np.mean([t['ret'] for t in lose]):+.2%}")
gap = np.array([t["ret"] - t["fwd10"] for t in trades if not np.isnan(t["fwd10"])])
print(f"  实现 − 标签口径(10日远期): 平均 {gap.mean():+.2%} 中位 {np.median(gap):+.2%}"
      f" 为正占比 {(gap>0).mean():.1%}")
ro = np.array([t["ret_open"] for t in trades], dtype=np.float64)
if not np.all(np.isnan(ro)):
    print(f"  【成交价变体】次日开盘成交: 平均 {np.nanmean(ro):+.2%} 中位 {np.nanmedian(ro):+.2%}"
          f" 胜率 {(ro>0).mean():.1%}（vs 收盘口径 {rets.mean():+.2%} / {(rets>0).mean():.1%}）")
print(f"  收益集中度: 前 5 笔贡献 {sum(sorted(rets, reverse=True)[:5]):+.1%}"
      f" / 合计 {rets.sum():+.1%} | 最大 3 笔 = {sorted(rets, reverse=True)[:3]}")
print(f"  分年交易数: {dict(sorted(__import__('collections').Counter(t['ed'][:4] for t in trades).items()))}")
