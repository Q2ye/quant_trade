# -*- coding: utf-8 -*-
"""一次性脚本：滚动起始日 × 趋势质量(③) 对照（不提交）。

复用 `_rolling_start_cross_market.py` 的数据加载与撮合（SmokePortfolio），
但注入参数（原脚本 `strategy_cls(name=...)` 不传 parameters，故 CM_PARAMS 对其无效）。

用法: python scripts/_cm_rolling_tq.py <arm>
  arm ∈ {OFF, TQ, PLACEBO}    （OFF 仅用于自检：应与原脚本输出逐位一致）
"""
import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, ".")
sys.path.insert(0, "scripts")

import numpy as np  # noqa: E402

# ⚠️ `_rolling_start_cross_market.py` 模块级直接 `asyncio.run(main())`（无 __main__ 守卫）
# → 不能 import，改为 exec 源码并剥掉最后那行。该文件是 git 长期资产，**不做任何修改**。
_SRC = Path("scripts/_rolling_start_cross_market.py").read_text(encoding="utf-8")
_SRC = _SRC.replace("\nasyncio.run(main())", "\n")
_ns: dict = {
    "__file__": str(Path("scripts/_rolling_start_cross_market.py").resolve()),
    "__name__": "_rolling_start_cross_market",
}
exec(compile(_SRC, "_rolling_start_cross_market", "exec"), _ns)  # noqa: S102
DEFAULT_STARTS = _ns["DEFAULT_STARTS"]
END = _ns["END"]
load_etf_data = _ns["load_etf_data"]
run_single = _ns["run_single"]

ARM = sys.argv[1] if len(sys.argv) > 1 else "TQ"
PARAMS = {
    "OFF": {},
    "TQ": {"enable_trend_quality": True},
    "PLACEBO": {"enable_trend_quality": True, "trend_quality_lag": 20},
    "TQ2": {"enable_trend_quality": True, "trend_quality_power": 2.0},
    "TQ3": {"enable_trend_quality": True, "trend_quality_power": 3.0},
    "PLACEBO2": {"enable_trend_quality": True, "trend_quality_power": 2.0, "trend_quality_lag": 20},
    "PLACEBO3": {"enable_trend_quality": True, "trend_quality_power": 3.0, "trend_quality_lag": 20},
    "REL": {"enable_rel_strength": True},
    "REL_PLACEBO": {"enable_rel_strength": True, "rel_strength_lag": 20},
}[ARM]


async def main() -> None:
    from shared.database.session.connection_pool import get_connection_pool
    from modules.strategy.strategies.rotation.cross_market_momentum_strategy import (
        CrossMarketMomentumStrategy,
    )
    from sqlalchemy import text

    class ParamStrategy(CrossMarketMomentumStrategy):
        def __init__(self, name="x", strategy_type=None, parameters=None):
            super().__init__(name=name, parameters={**PARAMS, **(parameters or {})})

    starts = [date.fromisoformat(s) for s in DEFAULT_STARTS]
    end = date.fromisoformat(END)

    pool = get_connection_pool()
    try:
        sf = pool.get_session_factory()
    except RuntimeError:
        await pool.initialize()
        sf = pool.get_session_factory()

    tmp = ParamStrategy(name="tmp")
    tmp._db_session_factory = sf
    tmp.initialize()
    await tmp.on_start()
    symbols = list(tmp.universe)

    async with sf() as _s:
        _r = await _s.execute(text(
            "SELECT DISTINCT trade_date FROM index_daily "
            "WHERE ts_code='000300.SH' AND trade_date BETWEEN :s AND :e ORDER BY trade_date"
        ), {"s": starts[0], "e": end})
        all_dates = [str(x[0])[:10] for x in _r.fetchall()]

    full = await load_etf_data(sf, symbols, starts[0], end)
    print(f"[{ARM}] params={PARAMS}  ETF 数据 {len(full)} 只, 起始日 {len(starts)} 个", flush=True)
    print(f"{'起始日':<12}{'总收益':>10}{'回撤':>9}", flush=True)
    print("-" * 34, flush=True)
    results = []
    for s in starts:
        dates = [d for d in all_dates if d >= s.isoformat()]
        tr, mdd = await run_single(ParamStrategy, sf, full, s, dates, symbols)
        results.append((s.isoformat(), tr, mdd))
        print(f"{s.isoformat():<12}{tr:>9.1f}%{mdd:>8.1f}%", flush=True)
    await pool.close()

    rets = np.array([tr for _, tr, _ in results])
    mdds = np.array([m for _, _, m in results])
    print("-" * 34, flush=True)
    print(f"[{ARM}] 收益: min={rets.min():.1f}% 下四分={np.percentile(rets,25):.1f}% "
          f"中位={np.median(rets):.1f}% 上四分={np.percentile(rets,75):.1f}% max={rets.max():.1f}%", flush=True)
    print(f"[{ARM}] 回撤: min={mdds.min():.1f}% 中位={np.median(mdds):.1f}%", flush=True)
    print(f"[{ARM}] 亏损起始日 {(rets < 0).sum()}/12", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
