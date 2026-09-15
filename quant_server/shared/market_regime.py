# -*- coding: utf-8 -*-
"""统一市场 regime 判定（单一可信源）。

策略择时、组合资金分配、回测 CapitalAllocator 三处统一调用本模块，
口径一致：CSI500 收盘 vs MA250 ±band 带。
"""

from typing import Dict, Union


def compute_regime(
    csi500_closes: Dict[Union[str, object], float],
    trade_date,
    band: float = 0.03,
) -> int:
    """CSI500 收盘 vs MA250 ±band 判定市场 regime。

    参数:
        csi500_closes: {trade_date: close}，日期键接受 "YYYY-MM-DD" 字符串或 date 对象
        trade_date: 判定日（"YYYY-MM-DD" 字符串或 date 对象）
        band: 偏离阈值（±3% 回测验证最优）

    返回:
        0 = BEAR（熊市，CSI500 < MA250×(1-band)）
        1 = RANGE（震荡）
        2 = BULL（牛市，CSI500 > MA250×(1+band)）
    数据不足 250 日 → RANGE=1。
    """

    def _key(d) -> str:
        s = str(d)
        return s[:10]

    trade_key = _key(trade_date)
    try:
        dates = sorted(d for d in csi500_closes if _key(d) <= trade_key)
    except (TypeError, ValueError):
        return 1

    if len(dates) < 250:
        return 1

    closes = [float(csi500_closes[d]) for d in dates[-250:]]
    ma250 = sum(closes) / len(closes)
    close = closes[-1]

    if close < ma250 * (1 - band):
        return 0
    if close > ma250 * (1 + band):
        return 2
    return 1


def breadth_to_regime(
    breadth,
    bear_threshold: float = 30.0,
    bull_threshold: float = 60.0,
) -> int:
    """市场宽度（全市场站上 MA250 比例，0~100）→ regime。

    替代 CSI500 年线门（单一中盘指数无法代表全市场动量票，错配致 54% 回撤）。
    市场宽度直接反映「策略实际交易的全市场股票」的整体状态。

    参数:
        breadth: 0~100 的站上 MA250 比例（market_state_daily.above_ma250_pct）
        bear_threshold: 低于此值 → 熊市(0)
        bull_threshold: 高于此值 → 牛市(2)

    返回:
        0 = BEAR（普跌，空仓）
        1 = RANGE（震荡，半仓/等待）
        2 = BULL（普涨，满仓）
    breadth 缺失/None → RANGE=1。
    """
    if breadth is None:
        return 1
    try:
        b = float(breadth)
    except (TypeError, ValueError):
        return 1
    if b < bear_threshold:
        return 0
    if b > bull_threshold:
        return 2
    return 1
