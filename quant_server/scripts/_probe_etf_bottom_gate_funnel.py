# -*- coding: utf-8 -*-
"""一次性诊断：ETF 底部策略 — 门控漏斗端到端复现（只读，不写库）

目的：验证「日阈值 day_t 落在模型输出支撑集之外 → 熊/牛 regime 零信号」这一结构推断。
口径：按实盘活跃行 cebe247d（熊市防守-01）的真实 DB 参数，逐日复现 on_bar 的门控链路：
      _get_regime(因子 market_regime) → day_t = threshold + adj → proba 门 → ATR 门
      → 大盘门(_market_regime: CSI500 vs MA250 ±0.03) → 次日 P4 确认(close>候选日 low 且 vol_ratio>=1.0)
      特征取用复刻 _predict / _get_factor_value 的「最近日期 ≤ d」整行回退语义。
      本脚本只做门控漏斗统计，不含持仓/资金模拟。
执行：cd quant_server && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/_probe_etf_bottom_gate_funnel.py [threshold ...]
"""
import sys
import psycopg2, joblib, numpy as np
from collections import defaultdict

POOL = ['510050.SH','510300.SH','510500.SH','159919.SZ','510880.SH','512880.SH','512660.SH',
        '512800.SH','512100.SH','159915.SZ','159949.SZ','518880.SH','513100.SH','513050.SH',
        '511010.SH','511260.SH','510310.SH','159865.SZ','159825.SZ','159781.SZ','512170.SH',
        '159806.SZ','516510.SH','159840.SZ','512400.SH']
# ── 活跃行 cebe247d 的 DB 参数（2026-09-14 读取）──
REGIME_ADJ = {0: 0.06, 1: 0.0, 2: 0.06}
ATR_MIN = 0.015
GATE_BAND = 0.03
MIN_WARMUP_BARS = 60
BASE_THRESHOLDS = [float(x) for x in sys.argv[1:]] or [0.44, 0.48]
CFG = dict(host="localhost", port=5432, user="postgres", password="123456",
           database="quant_signals_dev")
RN = {0: "熊", 1: "震", 2: "牛"}

art = joblib.load("storage/models/etf_bottom_v5_20260816.joblib")
model, feats = art["model"], art["feature_names"]
mu = np.array(art["scaler_params"]["mu"]); sg = np.array(art["scaler_params"]["sigma"]) + 1e-8
print(f"模型 v5 | 特征 {len(feats)} | artifact 阈值 {art['threshold']:.2f} | 池 {len(POOL)} 只")

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

# ── 逐 ETF-日预测（复刻 _predict：最近日期 ≤ d 的整行 + >50% NaN 跳过 + 0 填充 + 全局标准化）──
pred, atrv, volr, regf, nanr = {}, {}, {}, {}, {}
for c in POOL:
    fdates = sorted(fac[c].keys())
    pdates = sorted(px[c].keys())
    for i, d in enumerate(pdates):
        if i < MIN_WARMUP_BARS:
            continue
        near = [x for x in fdates if x <= d]
        if not near:
            continue
        row = fac[c][near[-1]]
        fv = np.array([row.get(f, np.nan) for f in feats], dtype=np.float64)
        nr = float(np.isnan(fv).mean())
        if nr > 0.5:
            continue

        def _nf(fc):
            for x in reversed(near):
                v = fac[c][x].get(fc)
                if v is not None and not (isinstance(v, float) and np.isnan(v)):
                    return float(v)
            return None

        fv0 = np.nan_to_num(fv, nan=0.0)
        pred[(c, d)] = float(model.predict_proba(((fv0 - mu) / sg).reshape(1, -1))[0, 1])
        nanr[(c, d)] = nr
        atrv[(c, d)] = _nf("atr_ratio_20")
        volr[(c, d)] = _nf("volume_ma20_ratio")
        rv = _nf("market_regime")
        regf[(c, d)] = max(0, min(2, int(rv))) if rv is not None else 1

all_dates = sorted({d for c in POOL for d in px[c].keys()})
didx = {d: i for i, d in enumerate(all_dates)}
pp = np.array(list(pred.values()))
print(f"预测样本 {len(pred)} | 交易日 {all_dates[0]} ~ {all_dates[-1]} ({len(all_dates)} 天)"
      f" | NaN 比例 中位 {np.median(list(nanr.values())):.1%} max {max(nanr.values()):.1%}")
print("模型输出分布: max=%.4f p99.9=%.4f p99=%.4f p95=%.4f 中位=%.4f"
      % (pp.max(), np.percentile(pp, 99.9), np.percentile(pp, 99), np.percentile(pp, 95), np.median(pp)))
yr = defaultdict(int)
for (c, d) in pred:
    yr[d[:4]] += 1
print("按年样本量:", dict(sorted(yr.items())))


def market_regime(d):
    """复刻 _market_regime：CSI500 vs MA250 ±0.03"""
    cl = [c for dd, c in csi if dd <= d]
    if len(cl) < 250:
        return 1
    ma = sum(cl[-250:]) / 250.0
    if cl[-1] < ma * (1 - GATE_BAND):
        return 0
    if cl[-1] > ma * (1 + GATE_BAND):
        return 2
    return 1


def funnel(base_t):
    """门控漏斗：返回各 regime 的统计 + 按 regime 的候选/确认明细"""
    st = {k: defaultdict(int) for k in
          ("days", "passer", "days_with_pass", "after_atr", "days_with_cand", "cand", "confirm")}
    rej = defaultdict(int)                 # 确认失败原因
    maxp = defaultdict(float)
    gate_block = 0
    for d in all_dates:
        g = market_regime(d)
        per_reg = defaultdict(list)
        for c in POOL:
            if (c, d) not in pred:
                continue
            r = regf[(c, d)]
            st["days"][r] += 1
            maxp[r] = max(maxp[r], pred[(c, d)])
            if pred[(c, d)] >= base_t + REGIME_ADJ.get(r, 0.0):
                st["passer"][r] += 1
                per_reg[r].append(c)
        for r in per_reg:
            st["days_with_pass"][r] += 1
        if g == 2:                          # 大盘门：牛市整日跳过，不产生候选
            gate_block += 1
            continue
        for r, cs in per_reg.items():
            cs = sorted(cs, key=lambda c: -pred[(c, d)])
            for c in cs:
                a = atrv.get((c, d))
                if a is None or a < ATR_MIN:
                    continue
                st["after_atr"][r] += 1
                st["cand"][r] += 1
                nd = all_dates[didx[d] + 1] if didx[d] + 1 < len(all_dates) else None
                if nd is None or nd not in px[c]:
                    rej["无次日数据"] += 1; continue
                if px[c][nd][3] <= px[c][d][2]:
                    rej["次日收盘未过候选日低点"] += 1; continue
                vr = volr.get((c, nd))
                if vr is not None and vr < 1.0:
                    rej["量能不足"] += 1; continue
                st["confirm"][r] += 1
        for r in per_reg:
            if any(atrv.get((c, d)) is not None and atrv[(c, d)] >= ATR_MIN for c in per_reg[r]):
                st["days_with_cand"][r] += 1
    return st, rej, maxp, gate_block


for bt in BASE_THRESHOLDS:
    st, rej, maxp, gate_block = funnel(bt)
    print("\n" + "=" * 92)
    print(f"【阈值 base={bt:.2f}】日阈值 day_t = base + adj  →  熊 {bt+0.06:.2f} / 震 {bt:.2f} / 牛 {bt+0.06:.2f}")
    print(f"{'regime':>4s} {'ETF-日':>7s} {'过阈值':>7s} {'过阈值天数':>10s} {'过ATR天数':>10s}"
          f" {'候选数':>7s} {'次日确认':>8s} {'该regime最高proba':>17s}")
    for r in (0, 1, 2):
        st["days_with_cand"][r]
        tot_days = sum(1 for d in all_dates
                       if any((c, d) in pred and regf[(c, d)] == r for c in POOL))
        print(f"{RN[r]:>4s} {st['days'][r]:7d} {st['passer'][r]:7d} "
              f"{st['days_with_pass'][r]:6d}/{tot_days:<3d} {st['days_with_cand'][r]:8d}/{tot_days:<3d}"
              f" {st['cand'][r]:7d} {st['confirm'][r]:8d} {maxp[r]:17.4f}")
    print(f"  确认失败明细: {dict(rej)} | 牛市被大盘门整日拦截 {gate_block} 天")
    print(f"  合计: 候选 {sum(st['cand'].values())} 笔 → 实际买入信号 {sum(st['confirm'].values())} 笔")
