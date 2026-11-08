# -*- coding: utf-8 -*-
"""信号置换检验 —— 块置换（只读 · Phase A 单进程）

## 这个脚本回答什么

`docs/06-标准规范/05_策略过拟合检验标准.md` §三 Step 2 要求「真实信号须胜过安慰剂臂」，
但现行做法是**单臂 lag 对照**（跑一条固定错位臂比大小）→ 只能给「更好 / 相当 / 更差」的
定性判定，**给不出 p 值**。本脚本把它升级为**置换分布**：

    零假设 H0：机制读取的历史窗口与未来收益之间没有对齐关系
    做法    ：把特征窗口的偏移量按块随机化，重跑 N 次 → 零分布 + p 值 + 分位

## 判据（必须前置冻结 —— `02_研究阶段标准流程.md` §纪律一）

| 情形 | 判定 |
|:---|:---|
| 真实 > 零分布 **P95** 且 > 单 lag 臂 | **维持** |
| 真实 ∈ **[P25, P75]** | **判为噪声** |
| 真实 ∈ **(P75, P95]** | **弱支持** —— **不予采纳为证据**，亦不作移除依据 |
| 真实 < 零分布**中位** | **否决** |
| p 值 | **只登记，不作否决依据**（`05` §五/§六 过渡期豁免） |

> ⚠️ **P75~P95 这一档是 2026-09-19 补的**：初版判据只有三档，PM-02（`rel_strength` 单独，真实值≈P85）
> 恰好落进空档，脚本只能输出"待定" —— 那是**判据不完备**，不是实质结论。

> ⚠️ 概念澄清：置换的 `N` 是 **MC 采样数**，**不进入** SR0 / DSR 的试验次数；
> 进台账 N 的是「**被挑过的配置数**」。

## 三条关键设计约束（实证来源，勿擅改）

1. **只做特征级错位** —— 只改 `*_lag`（错位**特征窗口**的 `end` 偏移），
   **不动** `_data_cache` 的「当前价」语义：`_score_candidate:1155` 用 `closes[-1]` 当今日价、
   `_get_price:1731` 用 `df["close"].iloc[-1]`。若改成注入「置换后的历史」，
   止损 / 跌幅过滤 / 对账 / 峰值都会基于错位价 —— 那是**另一种语义**，
   与现有已采纳机制的安慰剂口径不一致，新旧结论将不可比。
2. **必须用 rolling 式全历史注入**（`_data_cache[code] = full[code].iloc[:p]`）：
   冒烟 harness 走 `_flush_pending_rows:1769`（`keep = lookback_days + mainline_days + 30 = 60` 行）
   → `trend_quality` 的 lag 上限只有 **34**；全历史注入不受此限。
   （`_bench_return:1069` 用的 `_index_cache` 本就是全历史。）
3. **零生产代码改动** —— `*_lag` 都是在**调用时**读取 `self.<x>_lag`
   （`:1073` / `:1103` / `:1130`），脚本在 `on_bar_batch_end(td)` **之前**覆写属性即可。
   这是**进程内临时覆写**：不落盘、不入 DB、不影响 `DEFAULT_PARAMS`。

## 边界（不可越）

- **只读**：SELECT-only；不写 DB、不改 `DEFAULT_PARAMS`、不改任何模块代码。
- 参数取自**磁盘 `DEFAULT_PARAMS`**（构造器 `merged = DEFAULT_PARAMS` + 传入项；
  `BaseStrategy.initialize()` 只调 `on_init()`，**不读 DB `strategy_parameters`**）。
  → 若生产实例在 DB 有参数覆盖，本脚本的「真实臂」**不等于**线上配置（输出已显式提示）。
- 预热窗口固定 500 自然日（与 `_rolling_start_cross_market.py` 逐字一致）→ 口径可比。
- Phase A **单进程**。N=50 约 15 分钟；N=200 约 1 小时（并发版属 Phase B）。

## 用法

    cd quant_server && .venv/Scripts/python.exe scripts/quality/permutation_test.py --n 0
    cd quant_server && .venv/Scripts/python.exe scripts/quality/permutation_test.py --fixed-lag 60
    cd quant_server && .venv/Scripts/python.exe scripts/quality/permutation_test.py --n 50 --mechanism all

退出码：0 = 正常；1 = 冒烟门不过（无交易 / 含 NaN / 收益率越界）。
"""
import argparse
import asyncio
import logging
import math
import sys
import time
from bisect import bisect_left
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent            # scripts/quality/
QUANT_SERVER = SCRIPT_DIR.parent.parent
BACKTEST_DIR = QUANT_SERVER / "scripts" / "backtest"
for _p in (str(QUANT_SERVER), str(BACKTEST_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:  # Windows 控制台默认 GBK，中文输出会炸
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

from backtest_cross_market_momentum import (  # noqa: E402
    INITIAL_CAPITAL,
    SmokePortfolio,
    _BrokerPos,
)

# ⚠️ 上一步 import 的模块在顶层调了 logging.basicConfig(level=INFO) → 策略 INFO 日志会淹没输出。
# 50 条臂 × ~1400 交易日 = 数万行，必须压回 WARNING。
logging.getLogger().setLevel(logging.WARNING)

DEFAULT_START = "2021-01-01"
DEFAULT_END = "2026-09-08"
WARMUP_DAYS = 500                 # 与 _rolling_start_cross_market.py 一致（口径可比）
TRADING_DAYS_PER_YEAR = 244.0
MECHANISMS = ("trend_quality", "rel_strength")
RET_MIN, RET_MAX = -0.95, 5.00    # 项目统一冒烟口径（**针对 3 个月冒烟**，见 SMOKE_MAX_TRADING_DAYS）
SMOKE_MAX_TRADING_DAYS = 250      # 窗口 > ≈1 年时，上界降级为提示（7 年窗口 +944% 属正常，非缺陷）
#: 分段方向一致性下限（`--segments` 提供时成为**附加必要条件**）。
#: 依据 `02_研究阶段标准流程.md` §R1 判据②「**分年度方向一致**（不能只靠 2007/2015 这类单一年份）」。
#: 不设此门会出一类错误结论：7.6 年窗口整体 p≈0.020 判「维持」，但效应**全部来自 2020 一年**
#: （实测 `rel_strength` 逐年真实−OFF = 2020 +43.2pp，其余 4 年逐位 0.00%，一致性 3/8=38%）。
SEG_MIN_CONSISTENCY = 0.60


def _p(msg: str) -> None:
    print(msg, flush=True)


# =============================================================================
# 数据准备（一次性，所有臂复用）
# =============================================================================
async def _load_full(sf, symbols: List[str], earliest: date, end: date) -> Dict[str, pd.DataFrame]:
    """加载 ETF 前复权全历史日线（含 500 自然日预热），按 ts_code 键。"""
    from shared.database.repositories.market.basic.etf_repo import ETFRepository

    warmup_start = earliest - timedelta(days=WARMUP_DAYS)
    async with sf() as session:
        rows = await ETFRepository(session).get_etf_adjusted_daily_batch(
            symbols=symbols, start_date=warmup_start, end_date=end,
        )
    by_code: Dict[str, list] = defaultdict(list)
    for r in rows:
        by_code[r["ts_code"]].append(r)

    full: Dict[str, pd.DataFrame] = {}
    for code, recs in by_code.items():
        df = pd.DataFrame([{
            "trade_date": str(r["trade_date"])[:10],
            "open": float(r["open"] or 0),
            "high": float(r["high"] or 0),
            "low": float(r["low"] or 0),
            "close": float(r["close"] or 0),
            "volume": float(r["volume"] or 0),
            "amount": float(r["amount"] or 0),
        } for r in recs]).sort_values("trade_date").reset_index(drop=True)
        full[code] = df
    return full


async def _load_dates(sf, start: date, end: date) -> List[str]:
    """回测区间交易日（以沪深300 为日历基准，与既有脚本一致）。"""
    from sqlalchemy import text

    async with sf() as session:
        r = await session.execute(text(
            "SELECT DISTINCT trade_date FROM index_daily "
            "WHERE ts_code = '000300.SH' AND trade_date BETWEEN :s AND :e ORDER BY trade_date"
        ), {"s": start, "e": end})
        return [str(row[0])[:10] for row in r.fetchall()]


async def _load_index_cache(sf, codes: List[str]) -> Dict[str, Dict[str, float]]:
    """**一次性**加载 regime / 基准指数收盘价序列（键与 `on_start` 构建的同形）。

    ## 为什么必须预加载（实测教训，2026-09-19）

    `on_start` 里那次查询失败时**只打 WARNING 并继续**，后果是**双重静默降级**：
      ① `_index_cache` 空 → 走弱期判定「降级为常正常」（策略不再切防御）
      ② `_bench_return:1069` 返回 None → `_rel_strength_excess` → **相对强度门静默 fail-open**
         —— 即**被测机制之一被整个关掉**，而该臂仍会照常输出一个"看起来正常"的绩效数字。

    实测已被命中过一次（`InvalidCachedStatementError`：TimescaleDB chunk 变更使缓存计划失效，
    属**随机可复现**的环境故障）→ 若沿用每臂 `on_start` 拉数据，零分布里会随机混入不可比的臂。

    预加载 + 硬校验同时解决三件事：消除随机降级、让每条臂**零 DB 访问**（完全确定）、省 50 次往返。
    """
    from sqlalchemy import text

    out: Dict[str, Dict[str, float]] = {}
    async with sf() as session:
        for code in codes:
            rows = (await session.execute(text(
                "SELECT trade_date, close FROM index_daily WHERE ts_code = :c ORDER BY trade_date"
            ), {"c": code})).fetchall()
            out[code] = {str(r[0])[:10]: float(r[1]) for r in rows}
    return out


def _prepare_grid(full: Dict[str, pd.DataFrame], dates: List[str]):
    """预构建（一次性）：
      · daily_bars[td][code] → BarData（取 open/close 用）
      · end_idx[td][code]    → 该 code 截至 td 的**行数**（= iloc 上界，含当日）
      · warmup[code]         → 回测开始前最后一段缓存（让 len(_data_cache) >= 3 尽早成立）
    """
    from core.engines.types.entities import BarData

    date_set = set(dates)
    daily_bars: Dict[str, Dict[str, "BarData"]] = defaultdict(dict)
    end_idx: Dict[str, Dict[str, int]] = defaultdict(dict)

    for code, df in full.items():
        dts = df["trade_date"].tolist()
        opens = df["open"].to_numpy(dtype=float)
        highs = df["high"].to_numpy(dtype=float)
        lows = df["low"].to_numpy(dtype=float)
        closes = df["close"].to_numpy(dtype=float)
        vols = df["volume"].to_numpy(dtype=float)
        amts = df["amount"].to_numpy(dtype=float)
        for i, td in enumerate(dts):
            if td not in date_set:
                continue
            daily_bars[td][code] = BarData(
                ts_code=code, period="daily",
                open=float(opens[i]), high=float(highs[i]), low=float(lows[i]),
                close=float(closes[i]), volume=float(vols[i]), amount=float(amts[i]),
                trade_date=td,
            )
            end_idx[td][code] = i + 1

    warmup: Dict[str, pd.DataFrame] = {}
    if dates:
        start_s = dates[0]
        for code, df in full.items():
            dts = df["trade_date"].tolist()
            i = bisect_left(dts, start_s) - 1
            if i >= 0:
                warmup[code] = df.iloc[: i + 1]
    return daily_bars, end_idx, warmup


# =============================================================================
# 单臂回测
# =============================================================================
def _metrics(navs: np.ndarray, entries: int, exits: int,
             invested_days: int, n_days: int,
             nav_dates: Optional[List[str]] = None) -> Dict[str, object]:
    if navs.size == 0:
        return {"total_return": 0.0, "sharpe": float("nan"), "mdd": 0.0,
                "entries": entries, "exits": exits,
                "invested_days": invested_days, "n_days": n_days, "has_nan": True,
                "navs": navs, "nav_dates": nav_dates or []}
    rets = navs[1:] / navs[:-1] - 1.0 if navs.size > 1 else np.zeros(1)
    sd = float(np.std(rets, ddof=1)) if rets.size > 1 else 0.0
    sharpe = float(np.mean(rets) / sd * math.sqrt(TRADING_DAYS_PER_YEAR)) if sd > 0 else float("nan")
    peak = np.maximum.accumulate(navs)
    return {
        "total_return": float(navs[-1] / INITIAL_CAPITAL - 1.0),
        "sharpe": sharpe,
        "mdd": float(np.min(navs / peak - 1.0)),
        "entries": entries, "exits": exits,
        "invested_days": invested_days, "n_days": n_days,
        "has_nan": bool(np.isnan(navs).any()),
        "navs": navs, "nav_dates": nav_dates or [],
    }


def _forward_window_dist(navs: np.ndarray, w: int) -> Dict[str, object]:
    """**固定 W 交易日前瞻收益**的分布 —— `06_策略实盘准入标准` §3.1 判据 3 的标尺。

    为什么必须固定期限：滚动起始日脚本给的是**区间总收益**（各窗终点相同、长度 1.5~5 年不等），
    把它当月收益的标尺是量纲错误（见 `实盘策略验证报告` 缺口 12）。

    ⚠️ **重叠 vs 不重叠**：重叠样本（每一步取一个窗口）相邻窗口高度相关，
    **有效样本数远小于 T−W** → 同时给出 stride=W 的不重叠版本对照；
    两者中位若相差大，说明分布被少数路径带偏，不可直接当阈值用。
    """
    if navs.size <= w:
        return {}
    fwd = navs[w:] / navs[:-w] - 1.0
    nonov = fwd[::w]

    def _st(a: np.ndarray) -> Dict[str, float]:
        q = np.percentile(a, [5, 25, 50, 75, 95])
        return {"n": int(a.size), "p5": float(q[0]), "p25": float(q[1]), "p50": float(q[2]),
                "p75": float(q[3]), "p95": float(q[4]),
                "mean": float(np.mean(a)), "neg": float(np.mean(a < 0))}

    return {"overlap": _st(fwd), "nonoverlap": _st(nonov), "window": w}


async def _run_arm(full, daily_bars, end_idx, warmup, dates,
                   lag_map: Dict[str, Dict[str, int]],
                   index_cache: Dict[str, Dict[str, float]], tag: str,
                   params: Optional[Dict] = None,
                   record: bool = False) -> Dict[str, object]:
    """跑一条臂。`lag_map` 为空 = 真实臂（lag 恒 0）；否则按日覆写 `*_lag`。

    **每条臂零 DB 访问**：不设 `_db_session_factory` → `on_start` 跳过它自己的指数查询
    （该查询失败时会静默降级，见 `_load_index_cache` 的说明），改为主进程预加载后注入。

    `params`：DEFAULT_PARAMS 覆盖（消融用，如 `{"enable_rel_strength": False}`）。
    `record`：记录 (a) 每日候选的 `passed_rel_strength`/`rel_excess`、(b) 每日持仓 → 供否决率统计。
    """
    from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
        CrossMarketMomentumStrategy,
    )

    # ⚠️ 参数只来自磁盘 DEFAULT_PARAMS（+ 此处仅覆盖 verbose_logging 以降噪）
    merged_params: Dict = {"verbose_logging": False}
    merged_params.update(params or {})
    strategy = CrossMarketMomentumStrategy(name=tag, parameters=merged_params)
    strategy._db_session_factory = None
    strategy.initialize()
    await strategy.on_start()
    strategy._index_cache = index_cache          # 预加载注入（on_start 已 clear 为空，只读共享）
    strategy.context = SimpleNamespace(
        positions={}, total_assets=INITIAL_CAPITAL, available_capital=INITIAL_CAPITAL,
    )

    # 预热注入（on_start 会清缓存，故必须在其后）
    for code, df in warmup.items():
        strategy._data_cache[code] = df
        strategy._bar_dates[code] = str(df["trade_date"].iloc[-1])[:10]

    tq_map = lag_map.get("trend_quality") or {}
    rs_map = lag_map.get("rel_strength") or {}

    portfolio = SmokePortfolio()
    nav_curve: List[float] = []
    nav_dates: List[str] = []
    entries = exits = invested_days = 0

    # ---- 否决率记录（非侵入：包裹 _score_candidate 读它返回的字段，不改策略逻辑）----
    # ⚠️ 记录**完整 metrics dict**（不只 5 元组）：`--veto-stats` 需要复刻 `_apply_filters`
    #    的除 rel_strength 外的全部门，才能算出「否决是否命中头号候选」。
    cand_records: List[Tuple[str, str, Dict]] = []
    hold_records: List[Tuple[str, Tuple[str, ...]]] = []
    weak_by_day: Dict[str, bool] = {}
    if record:
        _orig_score = strategy._score_candidate
        _cur_td = [""]

        def _score_wrapped(code: str):
            m = _orig_score(code)
            if m is not None:
                cand_records.append((_cur_td[0], code, m))
            return m

        strategy._score_candidate = _score_wrapped      # type: ignore[method-assign]

    for td in dates:
        bars_today = daily_bars.get(td)
        if not bars_today:
            continue

        # 1. 次日开盘成交 + 同步 context（broker 实际持仓，供 _reconcile_holdings 对账）
        prices_open = {c: b.open for c, b in bars_today.items()}
        portfolio.fill_pending(prices_open)
        strategy.context.positions = {
            c: _BrokerPos(h["qty"]) for c, h in portfolio.holdings.items() if h["qty"] > 0
        }
        strategy.context.total_assets = portfolio.equity(prices_open)
        strategy.context.available_capital = portfolio.cash

        # 2. ★ 置换注入：只错位**特征窗口**，不动「当前价」语义
        strategy.trend_quality_lag = tq_map.get(td, 0)
        strategy.rel_strength_lag = rs_map.get(td, 0)
        if record:
            _cur_td[0] = td

        # 3. 全历史注入（rolling 式）：只推进「当日有行情」的标的
        for code, p in end_idx[td].items():
            strategy._bar_dates[code] = td
            strategy._data_cache[code] = full[code].iloc[:p]

        # 4. 调仓
        signals = strategy.on_bar_batch_end(td)
        prices_close = {c: b.close for c, b in bars_today.items()}
        for sig in signals:
            if getattr(getattr(sig, "signal_type", None), "value", "") == "entry":
                entries += 1
            else:
                exits += 1
            portfolio.apply_signal(sig, prices_close)

        nav_curve.append(portfolio.equity(prices_close))
        nav_dates.append(td)
        if portfolio.holdings:
            invested_days += 1
        if record:
            hold_records.append(
                (td, tuple(sorted(c for c, h in portfolio.holdings.items() if h["qty"] > 0)))
            )
            weak_by_day[td] = bool(strategy._is_weak)

    if not strategy._index_cache:      # 防御性：预加载注入后此处永远非空，空了说明 harness 被改动
        raise RuntimeError("指数缓存为空 → 走弱期判定与 rel_strength 均会静默降级，该臂不可比")

    out = _metrics(np.asarray(nav_curve, dtype=np.float64),
                   entries, exits, invested_days, len(dates), nav_dates)
    out["cand"] = cand_records
    out["holds"] = hold_records
    out["weak_by_day"] = weak_by_day
    # 门开关快照：`--veto-stats` 复刻 `_apply_filters` 需要（否则门序/开关不一致会算错）
    out["flags"] = {
        "r2": bool(strategy.enable_r2_filter),
        "rel": bool(strategy.enable_rel_strength),
        "gain": bool(strategy.enable_entry_gain_filter and not strategy.entry_gain_veto),
        "ma": bool(strategy.enable_ma_filter),
        "vol": bool(strategy.enable_volume_check),
        "loss": bool(strategy.enable_loss_filter),
        "mainline": bool(strategy.enable_super_mainline),
        "defensive": str(strategy.defensive_etf or ""),
    }
    return out


# =============================================================================
# 置换：块随机 lag
# =============================================================================
def _block_lags(dates: List[str], block: int, lag_min: int, lag_max: int,
                rng: np.random.Generator) -> Dict[str, int]:
    """逐块抽一个 lag，块内固定（B 个交易日），跨块独立。

    同日同 lag 的三个理由：① 保持横截面可比性；② `_bench_return` 与候选读同一个
    `self.rel_strength_lag` → 两侧错位到**同一天**，相对强度语义不被破坏；③ 块内固定
    保留短程结构，避免逐日抖成「比真实信号更差的信号」。
    """
    m: Dict[str, int] = {}
    for i in range(0, len(dates), block):
        lag = int(rng.integers(lag_min, lag_max + 1))
        for td in dates[i: i + block]:
            m[td] = lag
    return m


def _segment_returns(navs: np.ndarray, nav_dates: List[str],
                     mode: str) -> Dict[str, float]:
    """把净值序列切成 **非重叠时间段**（`year` / `month`）并算各段收益。

    ## 为什么需要它（2026-09-19）

    PM-02（5.6 年，p≈0.137 弱支持）与 PM-04（7.6 年，p≈0.020 维持）**结论相反** →
    单窗口置换结论**可能随窗口翻转**。要判断"是真证据还是某一段的运气"，
    唯一办法是**看效应在时间上的分布**（方向一致性），而不是再换一个窗口
    （换窗口只会得到"另一个单点结论"）。

    段收益口径：段内**首个交易日净值 → 末个交易日净值**（不含段前一日），
    对真实臂与所有对照臂**用同一约定**，故差值是干净的。
    少于 `min_bars` 个交易日的段不输出（<1 个月，噪声主导）。
    """
    if mode in ("", "none") or navs.size == 0 or not nav_dates:
        return {}
    min_bars = 20
    idx: Dict[str, List[int]] = {}
    for i, td in enumerate(nav_dates):
        key = td[:4] if mode == "year" else td[:7]
        idx.setdefault(key, []).append(i)
    out: Dict[str, float] = {}
    for key in sorted(idx):
        iis = idx[key]
        if len(iis) < min_bars:
            continue
        i0, i1 = iis[0], iis[-1]
        if navs[i0] <= 0:
            continue
        out[key] = float(navs[i1] / navs[i0] - 1.0)
    return out


def _parse_param(s: str) -> Tuple[str, object]:
    """`--param key=value` → (key, value)；bool/int/float 自动识别。"""
    k, _, v = s.partition("=")
    v = v.strip()
    if v.lower() in ("true", "false"):
        return k.strip(), v.lower() == "true"
    for cast in (int, float):
        try:
            return k.strip(), cast(v)
        except ValueError:
            continue
    return k.strip(), v


def _fixed_lags(dates: List[str], lag: int) -> Dict[str, int]:
    return {td: lag for td in dates}


# =============================================================================
# 输出与判定
# =============================================================================
def _fmt_pct(x: float) -> str:
    return f"{x * 100:+.2f}%"


def _pct_line(name: str, null_vals: List[float], real_val: float,
              as_pct: bool = False) -> str:
    f = (lambda v: _fmt_pct(v)) if as_pct else (lambda v: f"{v:.4f}")
    if not null_vals:      # --n 0：只报真实值
        return f"  {name:<12} 真实 {f(real_val):>9} | 零分布 （未跑置换）"
    a = np.asarray(null_vals, dtype=float)
    q = np.percentile(a, [5, 25, 50, 75, 95])
    return (f"  {name:<12} 真实 {f(real_val):>9} | 零分布 "
            f"P5 {f(q[0]):>9}  P25 {f(q[1]):>9}  中位 {f(q[2]):>9}  "
            f"P75 {f(q[3]):>9}  P95 {f(q[4]):>9}")


def _judge(real_sharpe: float, null_sharpes: List[float],
           fixed_sharpe: Optional[float], fixed_lag: Optional[int],
           seg_consistency: Optional[float] = None) -> Tuple[str, str]:
    """按前置冻结判据给判定。返回 (判定, 说明)。"""
    if not null_sharpes:
        return "n/a", "未跑置换（--n 0）"
    a = np.asarray(null_sharpes, dtype=float)
    p95, p25, p75, med = np.percentile(a, [95, 25, 75, 50])
    n_ge = int((a >= real_sharpe).sum())
    p_est = (1.0 + n_ge) / (1.0 + a.size)

    detail = (f"真实 {real_sharpe:.4f} vs 零分布 中位 {med:.4f} / P95 {p95:.4f}；"
              f"null ≥ real 的个数 {n_ge}/{a.size} → p ≈ {p_est:.3f}")
    if fixed_sharpe is not None:
        detail += f"；单 lag 臂(lag={fixed_lag}) {fixed_sharpe:.4f}"

    if real_sharpe > p95 and (fixed_sharpe is None or real_sharpe > fixed_sharpe):
        verdict = "维持"
    elif real_sharpe < med:
        verdict = "否决"
    elif p25 <= real_sharpe <= p75:
        verdict = "噪声"
    elif real_sharpe <= p95:
        # P75~P95：**原判据空档**（2026-09-19 评审发现，PM-02 正落此带）
        # 明确定为「弱支持」= 不予采纳为证据，但也不构成移除依据（与 05 §五/§六 的
        # 过渡期豁免一致：p 值只登记，不作否决依据）。
        verdict = "弱支持（不予采纳为证据）"
    else:
        verdict = "待定"

    # ★ 附加必要条件：**分段方向一致性**（`02` §R1 判据②「不能只靠单一年份」）
    if seg_consistency is not None:
        detail += f"；分段方向一致性 {seg_consistency:.0%}（下限 {SEG_MIN_CONSISTENCY:.0%}）"
        if seg_consistency < SEG_MIN_CONSISTENCY and verdict == "维持":
            verdict = "弱支持（分段方向不一致）"
            detail += ("\n  ⚠️ **整窗 p 达标但分段方向不一致 → 按 `02` §R1② 不得判「维持」**："
                       "效应可能只来自某一段（需看逐段表）")
    return verdict, detail


async def main() -> int:
    ap = argparse.ArgumentParser(description="信号置换检验（块置换 · 只读）")
    ap.add_argument("--mechanism", default="all", choices=("all",) + MECHANISMS,
                    help="置换哪个机制的特征窗口（all = 两者用同一错位量）")
    ap.add_argument("--n", type=int, default=50, help="置换次数（MC 采样数）")
    ap.add_argument("--block", type=int, default=20, help="块长（交易日）")
    ap.add_argument("--lag-min", type=int, default=5, help="偏移量下界（≥5 保证破坏对齐）")
    ap.add_argument("--lag-max", type=int, default=250, help="偏移量上界")
    ap.add_argument("--seed", type=int, default=20260919, help="随机种子")
    ap.add_argument("--fixed-lag", type=int, default=None,
                    help="额外跑一条固定 lag 臂（交叉校验用，如 60）")
    ap.add_argument("--rolling-window", type=int, default=0,
                    help=">0 时输出固定 N 交易日前瞻收益分布（06 §3.1 判据 3 的标尺）")
    ap.add_argument("--export-nav", default=None,
                    help="导出真实臂逐日净值 CSV 到该路径（默认不落盘）")
    ap.add_argument("--param", action="append", default=None,
                    help="覆盖 DEFAULT_PARAMS，如 --param enable_rel_strength=false（可重复）")
    ap.add_argument("--veto-stats", action="store_true",
                    help="统计 rel_strength 过滤层的实际咬合率 + 与 OFF 臂的持仓差异天数")
    ap.add_argument("--segments", default="none", choices=("none", "year", "month"),
                    help="walk-forward 分段（year/month）：逐段对照，判断效应是否只来自某一段")
    ap.add_argument("--vs-param", action="append", default=None,
                    help="跑一条对照臂（如 --vs-param enable_trend_quality=false）"
                         "并纳入 --segments 逐年对照（可重复）")
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=DEFAULT_END)
    args = ap.parse_args()

    if args.lag_min < 1 or args.lag_max <= args.lag_min:
        _p("✗ 参数错误：需 1 <= lag-min < lag-max")
        return 1

    t_all = time.time()
    pool = None
    try:
        from shared.database.session.connection_pool import get_connection_pool
        from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
            CrossMarketMomentumStrategy,
            _BENCH_CODE,
        )

        pool = get_connection_pool()
        try:
            sf = pool.get_session_factory()
        except RuntimeError:
            if not await pool.initialize():
                _p("✗ 数据库连接池初始化失败")
                return 1
            sf = pool.get_session_factory()

        start_d, end_d = date.fromisoformat(args.start), date.fromisoformat(args.end)

        probe = CrossMarketMomentumStrategy(name="probe", parameters={"verbose_logging": False})
        symbols = list(probe.universe)
        active = {
            "trend_quality": bool(probe.enable_trend_quality),
            "rel_strength": bool(probe.enable_rel_strength),
        }

        _p("=" * 100)
        _p("信号置换检验（块置换 · 只读）")
        _p("=" * 100)
        _p(f"区间 {args.start} ~ {args.end} | 标的 {len(symbols)} 只 | 持仓数 {probe.normal_holdings_num} | "
           f"harnes rolling 式（全历史注入）| 预热 {WARMUP_DAYS} 自然日")
        _p(f"机制开关（DEFAULT_PARAMS）：" + " / ".join(f"{k}={'ON' if v else 'OFF'}" for k, v in active.items()))
        _p("⚠️ 参数取自磁盘 DEFAULT_PARAMS，**不含 DB strategy_parameters 覆盖** → "
           "若线上实例有覆盖，本真实臂不等于线上配置")
        if not active.get(args.mechanism if args.mechanism != "all" else "trend_quality", True):
            _p(f"⚠️ 机制 {args.mechanism} 在当前 DEFAULT_PARAMS 下为 OFF，置换可能不改变任何行为")

        full = await _load_full(sf, symbols, start_d, end_d)
        dates = await _load_dates(sf, start_d, end_d)
        if not dates:
            _p("✗ 区间内无交易日数据")
            return 1

        # ★ 指数缓存一次性预加载 + 硬校验（缺了会让 rel_strength 静默 fail-open，见函数注释）
        index_cache = await _load_index_cache(sf, list(probe.weak_indices))
        bench_len = len(index_cache.get(_BENCH_CODE, {}))
        if bench_len == 0:
            _p(f"✗ 基准指数 {_BENCH_CODE} 无收盘价数据 → rel_strength 会静默 fail-open，拒绝运行")
            return 1
        _p(f"指数缓存（预加载，全局复用）：" +
           " / ".join(f"{c}:{len(v)}" for c, v in index_cache.items()))

        daily_bars, end_idx, warmup = _prepare_grid(full, dates)
        warm_med = int(np.median([len(v) for v in warmup.values()])) if warmup else 0
        need = probe.lookback_days + 1 + args.lag_max
        _p(f"数据：{len(full)} 只 ETF | 交易日 {len(dates)} | 预热行长中位 {warm_med} | "
           f"lag_max={args.lag_max} 需要预热 ≥{need} 行 → {'✅' if warm_med >= need else '⚠️ 偏紧（初期部分臂会退化）'}")

        # 数据已全部入内存 → 立刻关池：置换阶段**零 DB 依赖**，不受 TimescaleDB chunk 变更等环境故障影响
        await pool.close()
        pool = None

        # ---- 门 1：真实臂（lag=0）----
        _p("-" * 100)
        _p("[门 1] 真实臂（lag=0）…")
        t0 = time.time()
        real = await _run_arm(full, daily_bars, end_idx, warmup, dates, {},
                              index_cache, "perm-real",
                              params=dict(_parse_param(p) for p in (args.param or [])),
                              record=True)
        dt_real = time.time() - t0
        _p(f"  总收益 {_fmt_pct(real['total_return'])} | 夏普 {real['sharpe']:.4f} | "
           f"MDD {_fmt_pct(real['mdd'])} | 入场 {real['entries']} 笔 / 离场 {real['exits']} 笔 | "
           f"在场 {real['invested_days']}/{real['n_days']} 日 | 耗时 {dt_real:.1f}s")

        # ---- 门 4：冒烟（项目统一口径）----
        # ⚠️ [−95%, +500%] 是为「3 个月冒烟」定的约定；长窗口（>1 年）收益天然越界
        #    （实测 7.2 年窗口 +944%，与完整引擎 +1013.8% 同量级）→ 上界降级为提示，不判失败。
        over_max = real["total_return"] > RET_MAX
        long_win = real["n_days"] > SMOKE_MAX_TRADING_DAYS
        ok_smoke = (real["entries"] >= 1 and not real["has_nan"]
                    and real["total_return"] >= RET_MIN
                    and (not over_max or long_win))
        _p(f"[门 4] 冒烟门（≥1 笔交易 / 无 NaN / 收益 ∈ [{RET_MIN:.0%}, {RET_MAX:.0%}]）："
           f"{'✅ 通过' if ok_smoke else '❌ 不通过'}")
        if over_max and long_win:
            _p(f"  ⚠️ 收益 {_fmt_pct(real['total_return'])} 超冒烟上界 {RET_MAX:.0%}，但窗口 "
               f"{real['n_days']} 交易日 > {SMOKE_MAX_TRADING_DAYS}（≈1 年）→ **上界不适用，降级为提示**")
        if not ok_smoke:
            return 1

        # ---- 判据 3 的标尺：固定窗口滚动收益分布（--rolling-window N）----
        if args.rolling_window > 0:
            _p("-" * 100)
            dist = _forward_window_dist(np.asarray(real["navs"], dtype=float), args.rolling_window)
            if not dist:
                _p(f"⚠️ 净值长度 {len(real['navs'])} ≤ 窗口 {args.rolling_window}，无法计算滚动分布")
            else:
                ov, no = dist["overlap"], dist["nonoverlap"]
                _p(f"[判据 3 标尺] 固定 {args.rolling_window} 交易日前瞻收益分布（真实臂净值，窗口内每一步取样）")
                _p(f"  重叠    n={ov['n']:<5} P5 {_fmt_pct(ov['p5'])}  P25 {_fmt_pct(ov['p25'])}  "
                   f"中位 {_fmt_pct(ov['p50'])}  P75 {_fmt_pct(ov['p75'])}  P95 {_fmt_pct(ov['p95'])}  "
                   f"均值 {_fmt_pct(ov['mean'])}  为负占比 {ov['neg']:.0%}")
                _p(f"  不重叠  n={no['n']:<5} P5 {_fmt_pct(no['p5'])}  P25 {_fmt_pct(no['p25'])}  "
                   f"中位 {_fmt_pct(no['p50'])}  P75 {_fmt_pct(no['p75'])}  P95 {_fmt_pct(no['p95'])}")
                _p(f"  → 判据 3 用法：实盘 {args.rolling_window} 交易日收益落在 "
                   f"[{_fmt_pct(ov['p5'])}, {_fmt_pct(ov['p95'])}] 内 = 未偏离；"
                   f"超出（含上界）= 暂停归因")
                _p("  ⚠️ 重叠样本相关 → 有效样本远小于 n；不重叠版仅 "
                   f"{no['n']} 个独立样本，分位数误差大，阈值应留余量")

        if args.export_nav:
            out = Path(args.export_nav)
            rows = "\n".join(f"{td},{v:.2f}" for td, v in zip(real["nav_dates"], real["navs"]))
            out.write_text("trade_date,nav\n" + rows + "\n", encoding="utf-8")
            _p(f"[导出] 真实臂净值 {len(real['nav_dates'])} 行 → {out}")

        # ---- rel_strength 否决率 + rank 位次（回答「该层是否近似 no-op」）----
        off_arm: Optional[Dict] = None
        if args.veto_stats:
            cand = real.get("cand") or []
            _p("-" * 100)
            _p("[否决率] `rel_strength` 过滤层的实际咬合（真实臂 = ON）")
            if not cand:
                _p("  ⚠️ 无候选记录（该区间无候选进入打分）")
            else:
                n = len(cand)
                n_veto = sum(1 for _td, _c, m in cand if not m.get("passed_rel_strength", True))
                exc = np.asarray([m["rel_excess"] for _td, _c, m in cand
                                  if m.get("rel_excess") is not None], dtype=float)
                _p(f"  候选样本 **{n}** 个 / {len(real['nav_dates'])} 交易日")
                _p(f"  被 `passed_rel_strength=False` 否决 **{n_veto}** 个 = **{n_veto / n:.2%}**")
                if exc.size:
                    q = np.percentile(exc, [5, 25, 50, 75, 95])
                    _p(f"  `rel_excess` 分布 n={exc.size}: P5 {_fmt_pct(q[0])}  P25 {_fmt_pct(q[1])}  "
                       f"中位 {_fmt_pct(q[2])}  P75 {_fmt_pct(q[3])}  P95 {_fmt_pct(q[4])}  "
                       f"**为负占比 {float((exc < 0).mean()):.0%}**")

                # ===== rank 位次分析：否决是否命中「除它以外全通过的最优候选」=====
                flags = real.get("flags") or {}
                weak_by_day = real.get("weak_by_day") or {}
                by_day: Dict[str, List[Dict]] = {}
                for td, _c, m in cand:
                    by_day.setdefault(td, []).append(m)

                def _passes_others(m: Dict, is_weak: bool) -> bool:
                    """复刻 `_apply_filters`（门序一致），**只去掉 rel_strength 这一道门**。"""
                    if not m.get("passed_momentum"):
                        return False
                    if flags.get("r2") and not m.get("passed_r2"):
                        return False
                    if flags.get("gain") and not m.get("passed_entry_gain"):
                        return False
                    if not is_weak:
                        if flags.get("ma") and not m.get("passed_ma"):
                            return False
                        if flags.get("vol") and not m.get("passed_volume"):
                            return False
                        if flags.get("loss") and not m.get("passed_loss"):
                            return False
                    return True

                n_others_days = n_hit_top = n_fallback = 0
                vetoed_rank: List[int] = []
                for td, ms in by_day.items():
                    is_weak = bool(weak_by_day.get(td, False))
                    others = [m for m in ms if _passes_others(m, is_weak)]
                    if not others:
                        continue
                    n_others_days += 1
                    ranked = sorted(others, key=lambda x: float(x.get("score", 0.0)), reverse=True)
                    worst = next((i + 1 for i, m in enumerate(ranked)
                                  if not m.get("passed_rel_strength", True)), None)
                    if worst is not None:
                        vetoed_rank.append(worst)
                    best = ranked[0]
                    if not best.get("passed_rel_strength", True):
                        n_hit_top += 1
                        if not any(m.get("passed_rel_strength", True) for m in ranked[1:]):
                            n_fallback += 1
                _p(f"  **`rel_strength` 否决「除它以外全通过的最优候选」的天数 "
                   f"{n_hit_top}/{n_others_days} = {n_hit_top / max(1, n_others_days):.2%}**"
                   f"  ← 只有这些天才真正改变选择")
                _p(f"     └ 其中「否决后无其他候选通过」→ 退防御/空仓：**{n_fallback}** 天")
                if vetoed_rank:
                    r = np.asarray(vetoed_rank, dtype=float)
                    _p(f"     被否决者的最优名次分布（1 = 头号）：中位 {np.median(r):.0f}，"
                       f"名次=1 占 {float((r == 1).mean()):.0%}，≥3 占 {float((r >= 3).mean()):.0%}")

            # 结局层：ON vs OFF 的持仓差异天数
            off = await _run_arm(full, daily_bars, end_idx, warmup, dates, {},
                                 index_cache, "veto-off",
                                 params={"enable_rel_strength": False}, record=True)
            off_arm = off
            _p(f"  [对照] `enable_rel_strength=False` 臂：总收益 {_fmt_pct(off['total_return'])} / "
               f"夏普 {off['sharpe']:.4f} / 入场 {off['entries']} 笔")
            d_on, d_off = dict(real["holds"]), dict(off["holds"])
            common = [td for td in d_on if td in d_off]
            diff = [td for td in common if d_on[td] != d_off[td]]
            _p(f"  **持仓序列不同的天数 {len(diff)}/{len(common)} = "
               f"{len(diff) / max(1, len(common)):.2%}**  ← 「改变持有什么」的实测占比")
            for td in diff[:5]:
                _p(f"    {td}  ON={list(d_on[td]) or '空'}  OFF={list(d_off[td]) or '空'}")
            if len(diff) > 5:
                _p(f"    …（共 {len(diff)} 天，仅列前 5）")

            # 差异日**性质分类**：该层到底在"避险切换"还是在"选谁"？
            # （5.6 年窗口全为"进攻→国债"，7.6 年出现"进攻→进攻"，故必须分开数）
            def_etf = (real.get("flags") or {}).get("defensive") or ""

            def _cls(codes: Tuple[str, ...]) -> str:
                if not codes:
                    return "空仓"
                return "防御" if set(codes) <= {def_etf} else "进攻"

            buckets: Dict[str, int] = {}
            for td in diff:
                key = f"ON={_cls(d_on[td])} / OFF={_cls(d_off[td])}"
                buckets[key] = buckets.get(key, 0) + 1
            if buckets:
                _p("  **差异日性质分解**（该层在做什么）：")
                for k, v in sorted(buckets.items(), key=lambda x: -x[1]):
                    _p(f"    {k:<22}{v:>4} 天（{v / len(diff):.0%}）")

        # ---- 通用对照臂（--vs-param）：纳入 --segments 逐年对照 ----
        if args.vs_param and off_arm is None:
            vs_params = dict(_parse_param(p) for p in args.vs_param)
            _p("-" * 100)
            _p(f"[对照臂] 覆盖参数 {vs_params}")
            off_arm = await _run_arm(full, daily_bars, end_idx, warmup, dates, {},
                                     index_cache, "vs-param", params=vs_params)
            _p(f"  总收益 {_fmt_pct(off_arm['total_return'])} / 夏普 "
               f"{off_arm['sharpe']:.4f} / MDD {_fmt_pct(off_arm['mdd'])} / "
               f"入场 {off_arm['entries']} 笔")

        # ---- 固定 lag 臂（门 2 交叉校验用）----
        fixed_sharpe = None
        if args.fixed_lag is not None:
            _p("-" * 100)
            _p(f"[门 2] 固定 lag 臂 lag={args.fixed_lag}（与已发布安慰剂臂交叉校验）…")
            m = {k: _fixed_lags(dates, args.fixed_lag) for k in MECHANISMS}
            if args.mechanism != "all":
                m = {args.mechanism: _fixed_lags(dates, args.fixed_lag)}
            fx = await _run_arm(full, daily_bars, end_idx, warmup, dates, m,
                                index_cache, f"perm-lag{args.fixed_lag}")
            fixed_sharpe = fx["sharpe"]
            _p(f"  总收益 {_fmt_pct(fx['total_return'])} | 夏普 {fx['sharpe']:.4f} | "
               f"MDD {_fmt_pct(fx['mdd'])} | 入场 {fx['entries']} 笔")

        # ---- 置换臂 ----
        rng = np.random.default_rng(args.seed)
        nulls: List[Dict[str, float]] = []
        if args.n > 0:
            _p("-" * 100)
            _p(f"[置换] N={args.n} block={args.block} lag∈[{args.lag_min},{args.lag_max}] "
               f"seed={args.seed} → 预计 {dt_real * args.n / 60:.1f} 分钟（单进程）")
            for i in range(args.n):
                shared = _block_lags(dates, args.block, args.lag_min, args.lag_max, rng)
                lag_map = ({k: shared for k in MECHANISMS} if args.mechanism == "all"
                           else {args.mechanism: shared})
                m = await _run_arm(full, daily_bars, end_idx, warmup, dates, lag_map,
                                   index_cache, f"perm-{i:03d}")
                nulls.append(m)
                if (i + 1) % 5 == 0 or i == 0:
                    el = time.time() - t0
                    eta = (el / (i + 2)) * (args.n - i - 1)
                    _p(f"  [{i + 1}/{args.n}] 夏普 {m['sharpe']:.4f} 收益 {_fmt_pct(m['total_return'])} "
                       f"| ETA {eta / 60:.1f} min")

        # ---- 汇总 ----
        _p("=" * 100)
        _p("结果")
        _p("=" * 100)
        _p(_pct_line("夏普", [x["sharpe"] for x in nulls], real["sharpe"]))
        _p(_pct_line("总收益", [x["total_return"] for x in nulls], real["total_return"], as_pct=True))
        _p(_pct_line("MDD", [x["mdd"] for x in nulls], real["mdd"], as_pct=True))
        # 暴露 / 换手检查：防「靠多在场 / 多交易」取胜（动量失效闸门的失败根因）
        _p(_pct_line("在场天数", [float(x["invested_days"]) for x in nulls],
                     float(real["invested_days"])))
        _p(_pct_line("入场笔数", [float(x["entries"]) for x in nulls], float(real["entries"])))

        if nulls and any(x["has_nan"] for x in nulls):
            _p("⚠️ 部分置换臂含 NaN —— 该臂结果不可用")

        # ---- walk-forward 分段：效应在时间上的分布（--segments）----
        seg_consistency: Optional[float] = None
        if args.segments != "none":
            _p("-" * 100)
            _p(f"[walk-forward 分段 · {args.segments}] 效应在时间上的分布（判断是否只靠某一段）")
            real_seg = _segment_returns(np.asarray(real["navs"], dtype=float),
                                        real["nav_dates"], args.segments)
            if not real_seg:
                _p("  ⚠️ 无足够分段（窗口太短或段内交易日 < 20）")
            else:
                null_segs = [_segment_returns(np.asarray(x["navs"], dtype=float),
                                              x["nav_dates"], args.segments) for x in nulls]
                off_seg = (_segment_returns(np.asarray(off_arm["navs"], dtype=float),
                                            off_arm["nav_dates"], args.segments)
                           if off_arm else {})
                _p(f"  {'段':<7}{'真实':>10}{'零中位':>10}{'零P95':>10}{'逐段p':>8}"
                   f"{'OFF臂':>10}{'真−OFF':>10}  判定")
                n_seg = n_better_med = n_with_null = n_off = n_beat_off = 0
                for key in sorted(real_seg):
                    r = real_seg[key]
                    n_seg += 1
                    vals = [ns[key] for ns in null_segs if key in ns]
                    if vals:
                        n_with_null += 1
                        med = float(np.median(vals))
                        p95: Optional[float] = float(np.percentile(vals, 95))
                        p_seg: Optional[float] = (1 + sum(1 for v in vals if v >= r)) / (1 + len(vals))
                        if r >= med:
                            n_better_med += 1
                        med_s, p95_s = _fmt_pct(med), _fmt_pct(p95)
                        p_s = f"{p_seg:.3f}"
                        mark = "✅" if p_seg <= 0.2 else ("⚠️" if p_seg <= 0.5 else "❌")
                    else:
                        med_s = p95_s = p_s = "—"
                        mark = ""
                    off_s = off_d_s = "—"
                    if key in off_seg:
                        n_off += 1
                        if r >= off_seg[key]:
                            n_beat_off += 1
                        off_s, off_d_s = _fmt_pct(off_seg[key]), _fmt_pct(r - off_seg[key])
                    _p(f"  {key:<7}{_fmt_pct(r):>10}{med_s:>10}{p95_s:>10}"
                       f"{p_s:>8}{off_s:>10}{off_d_s:>10}  {mark}")
                if n_with_null:
                    seg_consistency = n_better_med / n_with_null
                    _p(f"  **方向一致性：真实 ≥ 零分布中位 的段数 {n_better_med}/{n_with_null} = "
                       f"{n_better_med / n_with_null:.0%}**"
                       f"　← 判定附加门：须 ≥ {SEG_MIN_CONSISTENCY:.0%}（`02` §R1②）")
                else:
                    _p("  （未跑置换 → 无零分布；本表为 **真实臂 vs OFF 臂** 的逐年对照）")
                if n_off:
                    if seg_consistency is None:
                        seg_consistency = n_beat_off / n_off
                    _p(f"  **真实 ≥ OFF 臂 的段数 {n_beat_off}/{n_off} = "
                       f"{n_beat_off / n_off:.0%}**（段数少 → 仅作方向参考）")
                _p(f"  共识：共 {n_seg} 段；单段交易日少（年≈250）→ 逐段 p 的**功效与分辨率都低**："
                   f"**看方向一致性，不要看单段显著性**")

        verdict, detail = _judge(real["sharpe"], [x["sharpe"] for x in nulls],
                                 fixed_sharpe, args.fixed_lag, seg_consistency)
        _p("-" * 100)
        _p(f"判定：{verdict}")
        _p(f"依据：{detail}")
        _p("判据（前置冻结，05 §三）：真实 > P95 且 > 单 lag 臂 = 维持 ｜ ∈[P25,P75] = 噪声 ｜ "
           "(P75,P95] = 弱支持·不予采纳为证据 ｜ < 中位 = 否决 ｜ p 值只登记不作否决依据")
        _p(f"附加必要条件（`--segments` 时生效，`02` §R1②）：分段方向一致性 ≥ "
           f"{SEG_MIN_CONSISTENCY:.0%}，否则「维持」降为「弱支持」")

        if args.n > 0:
            today = date.today().isoformat()          # YYYY-MM-DD
            _p("-" * 100)
            _p("台账行（粘贴至 docs/台账/研究试验台账.md，编号自查）")
            _p(f"| PM-__ | {today[5:]} | 置换检验 | "
               f"{args.mechanism} block={args.block} N={args.n} lag∈[{args.lag_min},{args.lag_max}] / "
               f"{args.start}~{args.end} | 夏普 {real['sharpe']:.4f} vs 零分布 P95 "
               f"{np.percentile([x['sharpe'] for x in nulls], 95):.4f} | {verdict} |")

        _p("-" * 100)
        _p(f"总耗时 {(time.time() - t_all) / 60:.1f} min")
        return 0
    finally:
        if pool is not None:
            try:
                await pool.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
