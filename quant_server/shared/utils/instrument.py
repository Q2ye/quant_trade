# -*- coding: utf-8 -*-
"""标的类型判别工具（单一事实源）。

背景：`_is_etf` 原先在 `modules/strategy/engines/strategy_manager.py` 与
`modules/strategy/engines/data_feed_engine.py` 各有一份实现，且两份规则并**不一致**：

  - strategy_manager：`ts_code[:2] in ("51","56","58","15")` 或 `.OF` 后缀，
    要求 `len(ts_code) >= 6`，不支持无后缀的裸代码；
  - data_feed_engine：剥离 `.` 后缀后按 `"51"/"159"/"16"/"56"/"58"` 前缀匹配，
    支持裸代码，但不认 `.OF`。

回测券商的费用模型（场内基金免征印花税与过户费）还需要第三份判别，故此处
收敛为唯一定义，三处引用。
"""

from typing import Final, Tuple

# 场内基金（ETF/LOF）代码前缀。
#   上交所：51xxxx 股票/行业/跨境/商品 ETF、56xxxx 行业 ETF、58xxxx 科创 ETF
#   深交所：159xxx 各类 ETF、16xxxx LOF
_ETF_PREFIXES: Final[Tuple[str, ...]] = ("51", "56", "58", "159", "16")


def is_etf(ts_code: str) -> bool:
    """判断标的是否为场内基金（ETF/LOF）。

    Args:
        ts_code: 标的代码，带或不带交易所后缀均可（如 "510050.SH" / "510050"）。

    Returns:
        True 表示场内基金（ETF/LOF）；False 表示股票/指数/空值。

    Examples:
        >>> is_etf("510050.SH")
        True
        >>> is_etf("159915.SZ")
        True
        >>> is_etf("588080.SH")
        True
        >>> is_etf("600519.SH")
        False
    """
    if not ts_code:
        return False
    if ts_code.endswith(".OF"):  # 场外基金
        return True
    code = ts_code.split(".")[0]
    return code.startswith(_ETF_PREFIXES)
