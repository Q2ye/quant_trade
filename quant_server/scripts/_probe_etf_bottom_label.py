# -*- coding: utf-8 -*-
"""一次性诊断：ETF 底部策略 — 标签口径下的实际胜率/赔率（只读，不写库）

问题：标签 N=10 / X=+3% / Y=-5% → 赔率 0.6:1 → 需要 >62.5% 胜率才不亏。
     实现用阈值 0.44~0.48。那么在标签口径下，该阈值处的实际 precision 是多少？
执行：cd quant_server && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/_probe_etf_bottom_label.py
"""
import psycopg2, joblib, numpy as np
from collections import defaultdict
from datetime import date

POOL = ['510050.SH','510300.SH','510500.SH','159919.SZ','510880.SH','512880.SH','512660.SH',
        '512800.SH','512100.SH','159915.SZ','159949.SZ','518880.SH','513100.SH','513050.SH',
        '511010.SH','511260.SH','510310.SH','159865.SZ','159825.SZ','159781.SZ','512170.SH',
        '159806.SZ','516510.SH','159840.SZ','512400.SH']
N, X, Y = 10, 0.03, -0.05
CFG = dict(host="localhost", port=5432, user="postgres", password="123456",
           database="quant_signals_dev")

art = joblib.load("storage/models/etf_bottom_v5_20260816.joblib")
model, feats = art["model"], art["feature_names"]
mu = np.array(art["scaler_params"]["mu"]); sg = np.array(art["scaler_params"]["sigma"]) + 1e-8
print(f"模型 v5 | 特征 {len(feats)} | artifact 阈值 {art['threshold']:.2f}")

conn = psycopg2.connect(**CFG); cur = conn.cursor()
cur.execute("""SELECT ts_code, trade_date::text, factor_code, factor_value FROM factor_data
               WHERE ts_code = ANY(%s) AND factor_code = ANY(%s) AND trade_date >= '2025-01-01'""",
            (POOL, feats))
fac = defaultdict(dict)
for c, d, f, v in cur.fetchall():
    fac[(c, d[:10])][f] = float(v) if v is not None else np.nan

cur.execute("""SELECT ts_code, trade_date::text, high, low, close FROM etf_daily
               WHERE ts_code = ANY(%s) AND trade_date >= '2025-01-01' ORDER BY ts_code, trade_date""",
            (POOL,))
px = defaultdict(list)
for c, d, h, l, cl in cur.fetchall():
    px[c].append((d[:10], float(h), float(l), float(cl)))
conn.close()

dates_by_code = {c: [r[0] for r in v] for c, v in px.items()}
keys = sorted(fac.keys())
rows = []
for c, d in keys:
    if c not in px:
        continue
    fv = np.array([fac[(c, d)].get(f, np.nan) for f in feats], dtype=np.float64)
    if np.isnan(fv).mean() > 0.5:
        continue
    fv = np.nan_to_num(fv, nan=0.0)
    p = float(model.predict_proba(((fv - mu) / sg).reshape(1, -1))[0, 1])
    ds = dates_by_code[c]
    if d not in ds:
        continue
    i = ds.index(d)
    if i + N >= len(ds):          # 标签窗口不完整 → 丢弃（避免未来信息缺失下的假胜）
        continue
    c0 = px[c][i][3]
    lab, first = 0, None
    for j in range(i + 1, i + 1 + N):
        _, h, l, _ = px[c][j]
        up, dn = h >= c0 * (1 + X), l <= c0 * (1 - Y)
        if up and dn:
            first = "both"       # 同日双向触发，无法在日线上定序 → 记 both
            break
        if up:
            first = "up"; break
        if dn:
            first = "down"; break
    lab = 1 if first in ("up", "both") else 0
    ret10 = px[c][i + N][3] / c0 - 1     # 第 N 日收盘的实际收益（引用用）
    rows.append((d, c, p, lab, ret10, first))

print(f"有效样本 {len(rows)} | 标签正例占比 {np.mean([r[3] for r in rows]):.1%}"
      f" | 基准平均10日收益 {np.mean([r[4] for r in rows]):+.2%}")
_p = np.array([r[2] for r in rows])
print("模型输出分布: max=%.4f p99.9=%.4f p99=%.4f p95=%.4f 中位=%.4f"
      % (_p.max(), np.percentile(_p, 99.9), np.percentile(_p, 99), np.percentile(_p, 95), np.median(_p)))
print("\n阈值 →  信号数   胜率(标签)   平均10日收益   中位10日收益")
for t in (0.30, 0.40, 0.44, 0.48, 0.52, 0.55, 0.60, 0.65, 0.70, 0.80):
    sel = [r for r in rows if r[2] >= t]
    if not sel:
        print(f"  {t:.2f} →      0"); continue
    w = np.mean([r[3] for r in sel]); rr = [r[4] for r in sel]
    print(f"  {t:.2f} → {len(sel):5d}   {w:6.1%}      {np.mean(rr):+7.2%}      {np.median(rr):+7.2%}")

for tag, lo, hi in (("样本外 2026-07~09", "2026-07-01", "2026-09-30"),
                    ("验证期 2025-07~2026-06", "2025-07-01", "2026-06-30")):
    sub = [r for r in rows if lo <= r[0] <= hi]
    if not sub:
        print(f"\n{tag}: 无样本"); continue
    print(f"\n{tag}（{len(sub)} 样本，正例 {np.mean([r[3] for r in sub]):.1%}）")
    for t in (0.30, 0.44, 0.48, 0.55, 0.70):
        s = [r for r in sub if r[2] >= t]
        if s:
            print(f"   thr={t:.2f} n={len(s):4d} 胜率={np.mean([r[3] for r in s]):5.1%}"
                  f" 均收益={np.mean([r[4] for r in s]):+.2%}")
