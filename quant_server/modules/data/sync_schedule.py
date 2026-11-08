# -*- coding: utf-8 -*-
"""日终 / 夜间同步的类型清单（唯一配置源）。

分两层：
- ``DAILY_STRATEGY_TYPES``：19:20 日终（交易日）同步，**只放策略执行、
  数据完整性门、market_state / ETF 因子真正读取的表**；
- ``NIGHT_SYNC_TYPES``：00:00 夜班同步，放**其余全部类型**（含财务、因子、
  目录、治理、周月线、宏观）。

不纳入夜班的 4 个类型：
  * ``MINUTE_QUOTES`` / ``TICK_QUOTES`` / ``ETF_MINUTE``：分钟/tick，数据量
    与既有决定（不做分钟/tick）不符；
  * ``FINANCIAL_DATA``：三表合并的旧类型，无独立同步方法；由
    ``FINANCIAL_INCOME`` / ``FINANCIAL_BALANCE`` / ``FINANCIAL_CASHFLOW``
    分别同步。

改动本文件等于改生产日终时序：新增类型前先确认它是否被当前 running
策略或数据完整性门读取。依据见
``docs/09-交付记录/REQ-20261108-sync-tiering/01-需求.md``。
"""

from __future__ import annotations

from typing import Tuple

from modules.data.constants import DataType

# 19:20 必须同步（少一张会导致策略缺数据或数据完整性门失败）
DAILY_STRATEGY_TYPES: Tuple[DataType, ...] = (
    DataType.DAILY_QUOTES,       # stock_daily：门 + market_state + 高波动
    DataType.ADJ_FACTOR,         # stock_adj_factor：股票复权（高波动恢复时必需）
    DataType.DAILY_BASIC,        # stock_daily_basic：门 + market_state + 微盘
    DataType.DAILY_LIMIT,        # stock_daily_limit：market_state
    DataType.ETF_DAILY,          # etf_daily：running 跨市场 + ETF 因子 + 门
    DataType.FUND_ADJ_FACTOR,    # fund_adj_factor：ETF 复权（跨市场）
    DataType.INDEX_DAILY,        # index_daily：regime + market_state + 门
)

# 明确不纳入夜班的类型（不是「忘了」）
EXCLUDED_FROM_NIGHT: Tuple[DataType, ...] = (
    DataType.MINUTE_QUOTES,
    DataType.TICK_QUOTES,
    DataType.ETF_MINUTE,
    DataType.FINANCIAL_DATA,     # 用 income/balance/cashflow 三个独立类型
)

# 其余全部类型 → 00:00 夜班（含 stk_factor / stk_factor_pro / 财务 / 目录 / 治理）
NIGHT_SYNC_TYPES: Tuple[DataType, ...] = tuple(
    dt for dt in DataType
    if dt not in DAILY_STRATEGY_TYPES and dt not in EXCLUDED_FROM_NIGHT
)

__all__ = [
    "DAILY_STRATEGY_TYPES",
    "NIGHT_SYNC_TYPES",
    "EXCLUDED_FROM_NIGHT",
]
