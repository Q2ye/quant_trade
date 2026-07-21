# -*- coding: utf-8 -*-
"""
因子计算器模块（Factor Calculators）
=====================================

本模块将 28 个内建因子计算函数从 ``FactorResearchService`` 中提取为独立模块，
使用 **装饰器-based 自动注册** 模式来管理因子计算器。

架构设计
--------

每个因子计算器通过 ``@register_factor`` 装饰器注册到全局 ``_registry`` 字典中，
同时携带 ``FactorSpec`` 元数据（名称、显示名、类别、公式、数据源、更新频率等）。

模块提供三个查询 API：

- ``get_calculator(name)`` — 按因子名获取 ``FactorSpec``（含计算器函数）
- ``get_all_factors()`` — 获取全部已注册的 ``{name: FactorSpec}`` 字典
- ``get_metadata_list(factor_name, category)`` — 获取因子元数据列表（支持过滤）

使用方式
--------

.. code-block:: python

    from modules.data.factor_calculators import get_calculator, get_all_factors

    # 获取单个因子计算器
    spec = get_calculator("PE")
    if spec:
        result = spec.calculator(df, financial_data)

    # 获取所有因子
    all_factors = get_all_factors()
    for name, spec in all_factors.items():
        print(f"{name}: {spec.display_name} ({spec.category})")

因子分类
--------

- **估值 (value)**: PE, PB, PS
- **质量 (quality)**: ROE, ROA, GROSS_MARGIN, OPERATING_MARGIN, DEBT_RATIO, current_ratio, quick_ratio
- **规模 (size)**: MARKET_CAP
- **动量 (momentum)**: RET_1M, RET_3M, RET_6M, RET_12M
- **波动 (volatility)**: VOLATILITY_1M, VOLATILITY_3M, VOLATILITY_12M, BETA, sharpe_ratio
- **流动性 (liquidity)**: TURNOVER_RATE, volume_ratio
- **技术 (technical)**: MA, EMA, MACD, RSI, BOLL, KDJ

函数签名约定
-----------

- ``data_source`` 为 ``"both"`` 或 ``"financial"`` 的因子：
  ``calculator(df: pd.DataFrame, financial_data: Optional[pd.DataFrame] = None) -> pd.Series``

- ``data_source`` 为 ``"market"`` 或 ``"technical"`` 的因子：
  ``calculator(df: pd.DataFrame, parameters: Optional[Dict] = None) -> pd.Series``

设计原则
--------

1. **单一职责**：每个函数只负责一个因子的数值计算，不涉及 I/O 或状态管理
2. **纯函数**：所有计算器均为纯函数（接收输入、返回输出），无副作用
3. **统一接口**：通过 FactorSpec 提供标准的元数据访问和计算器调用方式
4. **自注册**：通过 @register_factor 装饰器，新增因子只需编写函数并添加装饰器即可
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd
from pandas import DataFrame

from modules.data.constants import FactorCategoryCode, StandardFactors

logger = logging.getLogger(__name__)


# ==================== Data Classes ====================


@dataclass
class FactorSpec:
    """
    因子规格数据类，包含一个因子的完整元数据及其计算函数。

    Attributes
    ----------
    name : str
        因子名称（如 ``"PE"``、``"RET_1M"``），与 ``StandardFactors`` 常量对齐
    display_name : str
        中文显示名称（如 ``"市盈率"``）
    description : str
        因子描述，说明其含义和用途
    category : str
        因子类别代码，取值于 ``FactorCategoryCode``（value/quality/size/momentum/
        volatility/liquidity/technical）
    formula : str
        因子计算公式（人类可读形式）
    data_source : str
        数据源类型，决定调用签名：
        - ``"both"`` — 需要行情 + 财务数据 → ``calculator(df, financial_data)``
        - ``"financial"`` — 仅需财务数据 → ``calculator(df, financial_data)``
        - ``"market"`` — 仅需行情数据 → ``calculator(df, parameters)``
        - ``"technical"`` — 技术指标 → ``calculator(df, parameters)``
    update_frequency : str
        更新频率（如 ``"daily"``、``"quarterly"``）
    calculator : Callable
        因子计算函数，签名为 ``(df, financial_data/parameters) -> pd.Series``
    parameters : Optional[Dict]
        默认计算参数，None 时使用各函数内置默认值
    """

    name: str
    display_name: str
    description: str
    category: str
    formula: str
    data_source: str
    update_frequency: str
    calculator: Callable
    parameters: Optional[Dict] = field(default=None)


# ==================== Global Registry ====================

_registry: Dict[str, FactorSpec] = {}


# ==================== Decorator ====================


def register_factor(
    name: str,
    display_name: str,
    description: str,
    category: str,
    formula: str,
    data_source: str,
    update_frequency: str,
    parameters: Optional[Dict] = None,
) -> Callable:
    """
    因子计算器注册装饰器。

    将因子计算函数装饰后自动注册到全局 ``_registry`` 中，并关联 ``FactorSpec``
    元数据。被装饰的函数本身保持不变，可直接独立调用。

    Parameters
    ----------
    name : str
        因子名称（如 ``"PE"``）
    display_name : str
        中文显示名称
    description : str
        因子描述
    category : str
        因子类别代码
    formula : str
        计算公式
    data_source : str
        数据源类型
    update_frequency : str
        更新频率
    parameters : Optional[Dict]
        默认参数

    Returns
    -------
    Callable
        装饰器函数，接收因子计算函数并注册后返回原函数
    """

    def decorator(func: Callable) -> Callable:
        spec = FactorSpec(
            name=name,
            display_name=display_name,
            description=description,
            category=category,
            formula=formula,
            data_source=data_source,
            update_frequency=update_frequency,
            calculator=func,
            parameters=parameters,
        )
        _registry[name] = spec
        return func

    return decorator


# ==================== Query Functions ====================


def get_calculator(name: str) -> Optional[FactorSpec]:
    """
    按因子名称获取计算器规格。

    Parameters
    ----------
    name : str
        因子名称（如 ``"PE"``、``"RET_1M"``）

    Returns
    -------
    Optional[FactorSpec]
        匹配的 ``FactorSpec``，未注册时返回 None
    """
    return _registry.get(name)


def get_all_factors() -> Dict[str, FactorSpec]:
    """
    获取所有已注册的因子计算器。

    Returns
    -------
    Dict[str, FactorSpec]
        因子名称到 ``FactorSpec`` 的完整映射字典
    """
    return dict(_registry)


def get_metadata_list(
    factor_name: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    获取因子元数据列表，支持按名称和/或类别过滤。

    此方法提供与 ``FactorResearchService._get_standard_factor_metadata()``
    兼容的输出格式，返回字典列表而非 ``FactorSpec`` 对象。

    Parameters
    ----------
    factor_name : Optional[str]
        因子名称过滤，None 时不按名称过滤
    category : Optional[str]
        因子类别过滤，None 时不按类别过滤

    Returns
    -------
    List[Dict[str, Any]]
        符合条件的因子元数据字典列表，每个字典包含：
        ``factor_name``, ``display_name``, ``description``, ``category``,
        ``formula``, ``data_source``, ``update_frequency``
    """
    results = []
    for name, spec in _registry.items():
        if factor_name and name != factor_name:
            continue
        if category and spec.category != category:
            continue
        results.append(
            {
                "factor_name": spec.name,
                "display_name": spec.display_name,
                "description": spec.description,
                "category": spec.category,
                "formula": spec.formula,
                "data_source": spec.data_source,
                "update_frequency": spec.update_frequency,
            }
        )
    return results


# ============================================================
#  Factor Calculator Functions (28 total)
# ============================================================
#  Functions are organized by category:
#    Value     (3): PE, PB, PS
#    Quality   (7): ROE, ROA, GM, NPM, debt_to_asset, current_ratio, quick_ratio
#    Size      (1): market_cap
#    Momentum  (4): ret_1m, ret_3m, ret_6m, ret_12m
#    Volatility(5): vol_1m, vol_3m, vol_12m, beta, sharpe
#    Liquidity (2): turnover_rate, volume_ratio
#    Technical (6): MA, EMA, MACD, RSI, BOLL, KDJ
# ============================================================


# -------------------- Value Factors (3) --------------------


@register_factor(
    name=StandardFactors.PE,
    display_name="市盈率",
    description="股价除以每股收益，衡量股票估值水平",
    category=FactorCategoryCode.VALUE,
    formula="Price / EPS",
    data_source="both",
    update_frequency="quarterly",
)
def _calculate_pe(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算市盈率（Price-to-Earnings Ratio）。

    **公式**::

        PE_t = Price_t / EPS_t

    其中 ``EPS_t`` 优先取 ``financial_data['basic_eps']``，fallback 到
    ``financial_data['diluted_eps']``，最终在 ``_get_financial_data()`` 中
    统一为 ``'eps'`` 列，并向前填充（ffill）到每个交易日。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，index=trade_date，必须包含 ``'close'`` 列
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，index=report_date，已 ffill 到日频。
        必须包含 ``'eps'`` 列。None 时返回空序列。

    Returns
    -------
    pd.Series
        PE 值序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回 ``pd.Series(dtype=float, index=df.index)``
    - ``financial_data`` 为 None 或缺少 ``'eps'`` 列 → 返回空序列
    - EPS 为 0 或 NaN → 对应日期的 PE 为 inf/NaN，由上层过滤
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    if financial_data is not None and 'eps' in financial_data.columns:
        eps = financial_data['eps']
        pe = df['close'] / eps
        return pe
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.PB,
    display_name="市净率",
    description="股价除以每股净资产，衡量股票价值",
    category=FactorCategoryCode.VALUE,
    formula="Price / Book Value per Share",
    data_source="both",
    update_frequency="quarterly",
)
def _calculate_pb(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算市净率（Price-to-Book Ratio）。

    **公式**::

        PB_t = Price_t / BPS_t

    其中 ``BPS_t`` 为每股净资产（Book Value per Share），由
    ``_get_financial_data()`` 计算后向前填充到日频。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，index=trade_date，必须包含 ``'close'`` 列
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'bps'`` 列（已 ffill 到日频）。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        PB 值序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空 ``pd.Series(dtype=float, index=df.index)``
    - ``financial_data`` 为 None 或缺少 ``'bps'`` 列 → 返回空序列
    - BPS 为 0 或 NaN → PB 为 inf/NaN，上层过滤
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    if financial_data is not None and 'bps' in financial_data.columns:
        bps = financial_data['bps']
        pb = df['close'] / bps
        return pb
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.PS,
    display_name="市销率",
    description="股价除以每股销售收入",
    category=FactorCategoryCode.VALUE,
    formula="Price / Sales per Share",
    data_source="both",
    update_frequency="quarterly",
)
def _calculate_ps(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算市销率（Price-to-Sales Ratio）。

    **公式**::

        PS_t = Market_Cap_t / Revenue_t
             = (Close_t × Total_Shares_t) / Revenue_t

    ``revenue`` 和 ``float_shares``（总股本）由
    ``_get_financial_data()`` 提供并 ffill 到日频。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，index=trade_date，必须包含 'close' 列
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 'revenue' 和 'float_shares' 列。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        PS 值序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - 'close' 列缺失 → 返回空序列
    - financial_data 为 None 或缺少必需列 → 返回空序列
    - revenue <= 0 时 PS 为 inf/NaN，上层过滤
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    if (financial_data is not None
            and 'revenue' in financial_data.columns
            and 'float_shares' in financial_data.columns):
        # PS = (close × total_shares / 10000) / revenue
        # v3.2: 市值改为万元单位，避免 NUMERIC(18,6) 溢出
        # pandas 自动按 index 对齐 df 和 financial_data
        mkt_cap = df['close'] * financial_data['float_shares'] / 10000
        ps = mkt_cap / financial_data['revenue'].replace(0, np.nan)
        return ps
    else:
        return pd.Series(dtype=float, index=df.index)


# -------------------- Quality Factors (7) --------------------


@register_factor(
    name=StandardFactors.ROE,
    display_name="净资产收益率",
    description="净利润除以净资产，衡量公司盈利能力",
    category=FactorCategoryCode.QUALITY,
    formula="Net Income / Equity",
    data_source="financial",
    update_frequency="quarterly",
)
def _calculate_roe(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算净资产收益率（Return on Equity）。

    **公式**::

        ROE_t = Net_Income_t / Equity_t

    其中 ``Net_Income_t`` 取值于 ``financial_data['n_income']``
    （归属母公司股东的净利润），``Equity_t`` 为净资产。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame（本方法不使用，保留以统一接口）
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'n_income'`` 列。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        ROE 值序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``financial_data`` 为 None → 返回空序列
    - **当前 limitations**：``_get_financial_data()`` 中 ``roe`` 恒为 None
      （Income 表不含资产负债表数据，无法计算 Equity），因此 ROE 实际总是返回空序列
    """
    if financial_data is not None and 'roe' in financial_data.columns:
        return financial_data['roe']
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.ROA,
    display_name="总资产收益率",
    description="净利润除以总资产，衡量资产使用效率",
    category=FactorCategoryCode.QUALITY,
    formula="Net Income / Total Assets",
    data_source="financial",
    update_frequency="quarterly",
)
def _calculate_roa(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算总资产收益率（Return on Assets）。

    **公式**::

        ROA_t = Net_Income_t / Total_Assets_t

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame（本方法不使用，保留以统一接口）
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'n_income'`` 和总资产数据。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        ROA 值序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``financial_data`` 为 None → 返回空序列
    - **当前 limitations**：``_get_financial_data()`` 中 ``roa`` 恒为 None
      （缺少资产负债表数据）
    """
    if financial_data is not None and 'roa' in financial_data.columns:
        return financial_data['roa']
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.GROSS_MARGIN,
    display_name="毛利率",
    description="毛利润除以营业收入，衡量产品盈利能力",
    category=FactorCategoryCode.QUALITY,
    formula="(Revenue - Cost) / Revenue",
    data_source="financial",
    update_frequency="quarterly",
)
def _calculate_gm(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算毛利率（Gross Margin）。

    **公式**::

        GM_t = (Revenue_t - Operating_Cost_t) / Revenue_t

    其中 ``Revenue_t`` 取值于 ``financial_data['revenue']``，
    ``Operating_Cost_t`` 取值于 ``financial_data['oper_cost']``。
    ``_get_financial_data()`` 在 revenue > 0 时计算该值并存入 ``'gross_margin'`` 列。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame（本方法不使用）
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'gross_margin'`` 列（已 ffill）。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        毛利率序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``financial_data`` 为 None 或缺少 ``'gross_margin'`` → 返回空序列
    - revenue <= 0 时 ``gross_margin`` 为 None（由 ``_get_financial_data()`` 保证）
    """
    if financial_data is not None and 'gross_margin' in financial_data.columns:
        return financial_data['gross_margin']
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.OPERATING_MARGIN,
    display_name="净利率",
    description="净利润除以营业收入，衡量整体盈利能力",
    category=FactorCategoryCode.QUALITY,
    formula="Net Profit / Revenue",
    data_source="financial",
    update_frequency="quarterly",
)
def _calculate_np_margin(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算净利率（Net Profit Margin）。

    **公式**::

        NPM_t = Net_Income_t / Revenue_t

    其中 ``Net_Income_t`` 取值于 ``financial_data['n_income']``，
    ``Revenue_t`` 取值于 ``financial_data['revenue']``。
    ``_get_financial_data()`` 在 revenue > 0 时计算并存入 ``'net_profit_margin'`` 列。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame（本方法不使用）
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'net_profit_margin'`` 列（已 ffill）。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        净利率序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``financial_data`` 为 None 或缺少 ``'net_profit_margin'`` → 返回空序列
    - revenue <= 0 时 net_profit_margin 为 None（由 ``_get_financial_data()`` 保证）
    """
    if financial_data is not None and 'net_profit_margin' in financial_data.columns:
        return financial_data['net_profit_margin']
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.DEBT_RATIO,
    display_name="资产负债率",
    description="总负债除以总资产，衡量财务杠杆",
    category=FactorCategoryCode.QUALITY,
    formula="Total Debt / Total Assets",
    data_source="financial",
    update_frequency="quarterly",
)
def _calculate_debt_to_asset(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算资产负债率（Debt-to-Asset Ratio）。

    **公式**::

        Debt_to_Asset_t = Total_Liabilities_t / Total_Assets_t

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame（本方法不使用）
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'debt_to_asset'`` 列。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        资产负债率序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - **当前 limitations**：``_get_financial_data()`` 中 ``debt_to_asset`` 恒为 None
      （Income 表不含资产负债表数据），始终返回空序列
    """
    if financial_data is not None and 'debt_to_asset' in financial_data.columns:
        return financial_data['debt_to_asset']
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.CURRENT_RATIO,
    display_name="流动比率",
    description="流动资产除以流动负债，衡量短期偿债能力",
    category=FactorCategoryCode.QUALITY,
    formula="Current Assets / Current Liabilities",
    data_source="financial",
    update_frequency="quarterly",
)
def _calculate_current_ratio(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算流动比率（Current Ratio）。

    **公式**::

        Current_Ratio_t = Current_Assets_t / Current_Liabilities_t

    衡量企业用流动资产偿还流动负债的能力。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame（本方法不使用）
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'current_ratio'`` 列。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        流动比率序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - **当前 limitations**：``_get_financial_data()`` 中 ``current_ratio`` 恒为 None
      （缺少资产负债表数据）
    """
    if financial_data is not None and 'current_ratio' in financial_data.columns:
        return financial_data['current_ratio']
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.QUICK_RATIO,
    display_name="速动比率",
    description="速动资产除以流动负债，衡量即时偿债能力",
    category=FactorCategoryCode.QUALITY,
    formula="(Current Assets - Inventory) / Current Liabilities",
    data_source="financial",
    update_frequency="quarterly",
)
def _calculate_quick_ratio(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算速动比率（Quick Ratio / Acid-Test Ratio）。

    **公式**::

        Quick_Ratio_t = (Current_Assets_t - Inventory_t) / Current_Liabilities_t

    比流动比率更严格，剔除了变现较慢的存货。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame（本方法不使用）
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'quick_ratio'`` 列。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        速动比率序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - **当前 limitations**：``_get_financial_data()`` 中 ``quick_ratio`` 恒为 None
      （缺少资产负债表数据）
    """
    if financial_data is not None and 'quick_ratio' in financial_data.columns:
        return financial_data['quick_ratio']
    else:
        return pd.Series(dtype=float, index=df.index)


# -------------------- Size Factor (1) --------------------


@register_factor(
    name=StandardFactors.MARKET_CAP,
    display_name="市值",
    description="总股本乘以股价，衡量公司规模",
    category=FactorCategoryCode.SIZE,
    formula="Close * Float Shares",
    data_source="both",
    update_frequency="daily",
)
def _calculate_market_cap(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算流通市值（Market Capitalization）。

    **公式**::

        Market_Cap_t = Price_t * Float_Shares_t

    其中 ``Float_Shares_t`` 为流通股本（万股），由 ``_get_financial_data()``
    获取并向前填充。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，index=trade_date，必须包含 ``'close'`` 列
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'float_shares'`` 列（已 ffill 到日频）。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        流通市值序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空序列
    - ``financial_data`` 为 None 或缺少 ``'float_shares'`` → 返回空序列
    - **当前 limitations**：``_get_financial_data()`` 中 ``float_shares`` 恒为 None
      （Income 表不含股本数据），因此市值实际总是返回空序列
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    if financial_data is not None and 'float_shares' in financial_data.columns:
        float_shares = financial_data['float_shares']
        # v3.2: 市值单位改为万元（元 → 万），避免 NUMERIC(18,6) 溢出
        # 原始值 = close(元) × float_shares(股) → 元
        # 万元值 = 元 / 10000
        market_cap = df['close'] * float_shares / 10000
        return market_cap
    else:
        return pd.Series(dtype=float, index=df.index)


# -------------------- Momentum Factors (4) --------------------


@register_factor(
    name=StandardFactors.RET_1M,
    display_name="1个月收益率",
    description="过去1个月的收益率",
    category=FactorCategoryCode.MOMENTUM,
    formula="(Close_t / Close_{t-20}) - 1",
    data_source="market",
    update_frequency="daily",
)
def _calculate_return_1m(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 1 个月动量收益率（约 20 个交易日）。

    **公式**::

        Ret_1M_t = (Close_t / Close_{t-window}) - 1

    等价于 ``df['close'].pct_change(periods=window)``，
    ``window`` 默认 20 个交易日（约 1 个日历月）。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，index=trade_date，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        计算参数，可选 key ``"window"`` 自定义回看窗口（默认 20）

    Returns
    -------
    pd.Series
        1 月收益率序列，前 window 个值为 NaN（pct_change 特性）

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空 ``pd.Series(dtype=float)``
    - 数据长度不足 window+1 → 全部为 NaN，上层可安全过滤
    - 参数为 None 时使用默认 window=20
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 20) if parameters else 20
    returns = df['close'].pct_change(periods=window)

    return returns


@register_factor(
    name=StandardFactors.RET_3M,
    display_name="3个月收益率",
    description="过去3个月的收益率",
    category=FactorCategoryCode.MOMENTUM,
    formula="(Close_t / Close_{t-60}) - 1",
    data_source="market",
    update_frequency="daily",
)
def _calculate_return_3m(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 3 个月动量收益率（约 60 个交易日）。

    **公式**::

        Ret_3M_t = (Close_t / Close_{t-window}) - 1

    默认 ``window=60``（约 3 个日历月）。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key ``"window"`` 自定义回看窗口（默认 60）

    Returns
    -------
    pd.Series
        3 月收益率序列

    Edge Cases
    ~~~~~~~~~~
    - 同 ``_calculate_return_1m``：缺列返回空，短序列全 NaN
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 60) if parameters else 60
    returns = df['close'].pct_change(periods=window)

    return returns


@register_factor(
    name=StandardFactors.RET_6M,
    display_name="6个月收益率",
    description="过去6个月的收益率",
    category=FactorCategoryCode.MOMENTUM,
    formula="(Close_t / Close_{t-120}) - 1",
    data_source="market",
    update_frequency="daily",
)
def _calculate_return_6m(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 6 个月动量收益率（约 120 个交易日）。

    **公式**::

        Ret_6M_t = (Close_t / Close_{t-window}) - 1

    默认 ``window=120``（约 6 个日历月）。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key ``"window"`` 自定义回看窗口（默认 120）

    Returns
    -------
    pd.Series
        6 月收益率序列

    Edge Cases
    ~~~~~~~~~~
    - 同 ``_calculate_return_1m``
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 120) if parameters else 120
    returns = df['close'].pct_change(periods=window)

    return returns


@register_factor(
    name=StandardFactors.RET_12M,
    display_name="12个月收益率",
    description="过去12个月的收益率",
    category=FactorCategoryCode.MOMENTUM,
    formula="(Close_t / Close_{t-240}) - 1",
    data_source="market",
    update_frequency="daily",
)
def _calculate_return_12m(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 12 个月动量收益率（约 240 个交易日）。

    **公式**::

        Ret_12M_t = (Close_t / Close_{t-window}) - 1

    默认 ``window=240``（约 12 个日历月）。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key ``"window"`` 自定义回看窗口（默认 240）

    Returns
    -------
    pd.Series
        12 月收益率序列

    Edge Cases
    ~~~~~~~~~~
    - 同 ``_calculate_return_1m``
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 240) if parameters else 240
    returns = df['close'].pct_change(periods=window)

    return returns


# -------------------- Volatility Factors (5) --------------------


@register_factor(
    name=StandardFactors.VOLATILITY_1M,
    display_name="1个月波动率",
    description="过去1个月的收益率波动率",
    category=FactorCategoryCode.VOLATILITY,
    formula="Std(Returns, 20d) * sqrt(252)",
    data_source="market",
    update_frequency="daily",
)
def _calculate_volatility_1m(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 1 个月年化波动率。

    **公式**::

        r_t = (Close_t / Close_{t-1}) - 1           （日收益率）
        Vol_1M_t = std(r_{t-window:t}) * sqrt(252)   （年化）

    默认 ``window=20`` 个交易日。
    ``sqrt(252)`` 为 A 股年化系数（约 252 个交易日/年）。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key ``"window"`` 自定义滚动窗口（默认 20）

    Returns
    -------
    pd.Series
        年化波动率序列，前 window 个值为 NaN

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空 ``pd.Series(dtype=float)``
    - 滚动窗口内数据不足 → NaN，上层安全过滤
    - 日收益率为常数 → std=0，波动率为 0
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 20) if parameters else 20
    returns = df['close'].pct_change()
    volatility = returns.rolling(window=window).std() * np.sqrt(252)

    return volatility


@register_factor(
    name=StandardFactors.VOLATILITY_3M,
    display_name="3个月波动率",
    description="过去3个月的收益率波动率",
    category=FactorCategoryCode.VOLATILITY,
    formula="Std(Returns, 60d) * sqrt(252)",
    data_source="market",
    update_frequency="daily",
)
def _calculate_volatility_3m(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 3 个月年化波动率。

    **公式**::

        Vol_3M_t = std(r_{t-60:t}) * sqrt(252)

    默认 ``window=60`` 个交易日。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key ``"window"`` 自定义滚动窗口（默认 60）

    Returns
    -------
    pd.Series
        年化波动率序列

    Edge Cases
    ~~~~~~~~~~
    - 同 ``_calculate_volatility_1m``
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 60) if parameters else 60
    returns = df['close'].pct_change()
    volatility = returns.rolling(window=window).std() * np.sqrt(252)

    return volatility


@register_factor(
    name=StandardFactors.VOLATILITY_12M,
    display_name="12个月波动率",
    description="过去12个月的收益率波动率",
    category=FactorCategoryCode.VOLATILITY,
    formula="Std(Returns, 240d) * sqrt(252)",
    data_source="market",
    update_frequency="daily",
)
def _calculate_volatility_12m(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 12 个月年化波动率。

    **公式**::

        Vol_12M_t = std(r_{t-window:t}) * sqrt(252)

    默认 ``window=240`` 个交易日（约 12 个日历月）。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key ``"window"`` 自定义滚动窗口（默认 240）

    Returns
    -------
    pd.Series
        年化波动率序列

    Edge Cases
    ~~~~~~~~~~
    - 同 ``_calculate_volatility_1m``
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 240) if parameters else 240
    returns = df['close'].pct_change()
    volatility = returns.rolling(window=window).std() * np.sqrt(252)

    return volatility


@register_factor(
    name=StandardFactors.BETA,
    display_name="Beta系数",
    description="股票收益与市场收益的协方差除以市场收益的方差",
    category=FactorCategoryCode.VOLATILITY,
    formula="Cov(Ret_stock, Ret_market) / Var(Ret_market)",
    data_source="market",
    update_frequency="daily",
)
def _calculate_beta(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 Beta 系数（市场敏感度）。

    **公式**::

        r_i = Close.pct_change()                 （个股日收益率）
        r_m = benchmark_returns                   （市场指数日收益率）
        Beta = Cov(r_i, r_m) / Var(r_m)           （滚动窗口内）

    ``benchmark_returns`` 由 ``_get_benchmark_returns()`` 预先获取并
    通过 ``parameters['benchmark_returns']`` 传入。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 'close' 列
    parameters : Optional[Dict]
        - ``window``: 滚动窗口（交易日），默认 60
        - ``benchmark_returns``: pd.Series，市场指数日收益率

    Returns
    -------
    pd.Series
        Beta 值序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - 'close' 列缺失 → 返回空序列
    - benchmark_returns 缺失或为空 → 返回空序列
    - 窗口内数据不足 → 对应日期 Beta 为 NaN
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    if parameters is None:
        return pd.Series(dtype=float, index=df.index)

    benchmark_returns = parameters.get('benchmark_returns')
    if benchmark_returns is None or benchmark_returns.empty:
        return pd.Series(dtype=float, index=df.index)

    window = parameters.get('window', 60)

    # 个股日收益率
    stock_returns = df['close'].pct_change()

    # 对齐个股与指数的交易日（取交集）
    common_idx = stock_returns.index.intersection(benchmark_returns.index)
    if len(common_idx) < window:
        return pd.Series(dtype=float, index=df.index)

    r_i = stock_returns.loc[common_idx]
    r_m = benchmark_returns.loc[common_idx]

    # 滚动窗口计算 Beta = Cov(r_i, r_m) / Var(r_m)
    beta = pd.Series(np.nan, index=df.index, dtype=float)
    for i in range(window - 1, len(common_idx)):
        end = i + 1
        start = end - window
        win_i = r_i.iloc[start:end]
        win_m = r_m.iloc[start:end]
        # 去除 NaN
        valid = win_i.notna() & win_m.notna()
        if valid.sum() < 2:
            continue
        cov = np.cov(win_i[valid], win_m[valid])[0, 1]
        var = np.var(win_m[valid])
        if var > 1e-12:
            beta.loc[common_idx[i]] = cov / var

    return beta


@register_factor(
    name=StandardFactors.SHARPE_RATIO,
    display_name="夏普比率",
    description="(年化收益 - 无风险利率) / 年化波动率",
    category=FactorCategoryCode.VOLATILITY,
    formula="(E[Ret] - Rf) / sigma",
    data_source="market",
    update_frequency="daily",
)
def _calculate_sharpe_ratio(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算滚动夏普比率（Rolling Sharpe Ratio）。

    **公式**::

        r_t = (Close_t / Close_{t-1}) - 1
        annual_return_t = mean(r_{t-window:t}) * 252
        annual_vol_t     = std(r_{t-window:t}) * sqrt(252)
        Sharpe_t         = (annual_return_t - R_f) / annual_vol_t

    默认 ``window=240``（约 1 年），无风险利率 ``R_f = 0.03``（3%）。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key：
        - ``"window"``: 滚动窗口大小（默认 240）
        - ``"risk_free_rate"``: 无风险利率（默认 0.03）

    Returns
    -------
    pd.Series
        滚动夏普比率序列，前 window 个值为 NaN

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空 ``pd.Series(dtype=float)``
    - ``annual_vol_t`` 为 0 → Sharpe 为 inf/Nan，上层安全过滤
    - 数据不足 window+1 → 全 NaN
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 240) if parameters else 240
    returns = df['close'].pct_change()

    annual_return = returns.rolling(window=window).mean() * 252
    annual_vol = returns.rolling(window=window).std() * np.sqrt(252)

    risk_free_rate = parameters.get("risk_free_rate", 0.03) if parameters else 0.03
    sharpe_ratio = (annual_return - risk_free_rate) / annual_vol

    return sharpe_ratio


# -------------------- Liquidity Factors (2) --------------------


@register_factor(
    name=StandardFactors.TURNOVER_RATE,
    display_name="换手率",
    description="成交量除以流通股本，衡量股票流动性",
    category=FactorCategoryCode.LIQUIDITY,
    formula="Volume / Float Shares * 100",
    data_source="both",
    update_frequency="daily",
)
def _calculate_turnover_rate(
    df: DataFrame,
    financial_data: Optional[DataFrame] = None,
) -> pd.Series:
    """
    计算换手率（Turnover Rate）。

    **公式**::

        Turnover_Rate_t = (Volume_t / Float_Shares_t) * 100

    其中 Volume 为成交量（股），Float_Shares 为流通股本（股或万股，
    取决于数据源单位）。结果以百分比表示。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'volume'`` 列
    financial_data : Optional[pd.DataFrame]
        财务数据 DataFrame，必须包含 ``'float_shares'`` 列（已 ffill）。
        None 时返回空序列。

    Returns
    -------
    pd.Series
        换手率序列（%），index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``'volume'`` 列缺失 → 返回空序列
    - ``financial_data`` 为 None 或缺少 ``'float_shares'`` → 返回空序列
    - **当前 limitations**：``_get_financial_data()`` 中 ``float_shares`` 恒为 None
      （Income 表不含股本数据），因此换手率实际总是返回空序列
    - Volume 和 Float_Shares 单位需一致（一般 Volume 为股，float_shares 为万股，
      需乘以 10000）
    """
    if 'volume' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    if financial_data is not None and 'float_shares' in financial_data.columns:
        float_shares = financial_data['float_shares']
        turnover_rate = df['volume'] / float_shares * 100
        return turnover_rate
    else:
        return pd.Series(dtype=float, index=df.index)


@register_factor(
    name=StandardFactors.VOLUME_RATIO,
    display_name="量比",
    description="当前成交量除以过去N日平均成交量",
    category=FactorCategoryCode.LIQUIDITY,
    formula="Volume_t / Avg(Volume_{t-N:t-1})",
    data_source="market",
    update_frequency="daily",
)
def _calculate_volume_ratio(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算量比（Volume Ratio）。

    **公式**::

        VR_t = Volume_t / SMA(Volume, N)_t

    其中 ``SMA(Volume, N)_t = mean(Volume_{t-N+1:t})``，默认 ``N=5``。

    量比 > 1 表示当日成交量高于近期均值（放量），< 1 表示缩量。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'volume'`` 列
    parameters : Optional[Dict]
        可选 key ``"window"`` 自定义均值窗口（默认 5）

    Returns
    -------
    pd.Series
        量比序列，与 df 同 index。前 window-1 个值为 NaN

    Edge Cases
    ~~~~~~~~~~
    - ``'volume'`` 列缺失 → 返回空 ``pd.Series(dtype=float)``
    - 滚动均值窗口内成交量全为 0 → VR 为 inf，上层过滤
    - 成交量 NaN → 传播到 VR
    """
    if 'volume' not in df.columns:
        return pd.Series(dtype=float)

    window = parameters.get("window", 5) if parameters else 5
    avg_volume = df['volume'].rolling(window=window).mean()
    volume_ratio = df['volume'] / avg_volume

    return volume_ratio


# -------------------- Technical Factors (6) --------------------


@register_factor(
    name=StandardFactors.MA,
    display_name="移动平均线",
    description="移动平均线，支持简单移动平均（SMA）和加权移动平均（WMA）",
    category=FactorCategoryCode.TECHNICAL,
    formula="SMA(Close, N); WMA weighted",
    data_source="market",
    update_frequency="daily",
)
def _calculate_ma(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算移动平均线（Moving Average）。

    **支持两种类型**::

        SMA_t  = (1/N) * sum(Close_{t-N+1:t})          — 简单移动平均
        WMA_t  = sum(w_i * Close_i) / sum(w_i)          — 加权移动平均
        w_i    = 1, 2, ..., N                           （线性递增权重）

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key：
        - ``"period"``: 移动窗口大小（默认 20）
        - ``"type"``: ``"simple"`` | ``"weighted"``（默认 ``"simple"``）

    Returns
    -------
    pd.Series
        MA 值序列，index 与 df 对齐，前 period-1 个值为 NaN

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回 ``pd.Series(dtype=float, index=df.index)``
    - ``period`` 超过数据长度 → 全 NaN
    - ``type`` 未识别 → fallback 到 ``"simple"``
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    period = parameters.get("period", 20) if parameters else 20
    ma_type = parameters.get("type", "simple") if parameters else "simple"

    if ma_type == "simple":
        ma = df['close'].rolling(window=period).mean()
    elif ma_type == "weighted":
        weights = np.arange(1, period + 1)
        ma = df['close'].rolling(window=period).apply(
            lambda x: np.average(x, weights=weights), raw=True
        )
    else:
        ma = df['close'].rolling(window=period).mean()

    return ma


@register_factor(
    name=StandardFactors.EMA,
    display_name="指数移动平均线",
    description="指数移动平均线，越近的价格权重越大",
    category=FactorCategoryCode.TECHNICAL,
    formula="EMA_t = alpha*Close_t + (1-alpha)*EMA_{t-1}",
    data_source="market",
    update_frequency="daily",
)
def _calculate_ema(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算指数移动平均线（Exponential Moving Average）。

    **分两种调用模式**::

        直接指定 alpha:    EMA_t = alpha * Close_t + (1-alpha) * EMA_{t-1}
        指定 span/period:   alpha = 2 / (period + 1)  ← pandas ewm 默认

    使用 pandas ``ewm(span=period)`` 或 ``ewm(alpha=alpha)`` 计算。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key：
        - ``"period"``: 等效 period（默认 12），alpha = 2/(period+1)
        - ``"alpha"``: 平滑因子（0-1），直接指定时优先于 period
        - ``"adjust"``: 是否使用调整权重（默认 False）

    Returns
    -------
    pd.Series
        EMA 值序列，index 与 df 对齐

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空序列
    - ``alpha=0`` → EMA 恒等于初始值（不平滑）
    - ``alpha=1`` → EMA 恒等于最新 Close（完全跟随）
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    period = parameters.get("period", 12) if parameters else 12
    adjust = parameters.get("adjust", False) if parameters else False
    alpha = parameters.get("alpha", None) if parameters else None

    if alpha:
        ema = df['close'].ewm(alpha=alpha, adjust=adjust).mean()
    else:
        ema = df['close'].ewm(span=period, adjust=adjust).mean()

    return ema


@register_factor(
    name=StandardFactors.MACD,
    display_name=StandardFactors.MACD,
    description="指数平滑异同移动平均线（DIF 线）",
    category=FactorCategoryCode.TECHNICAL,
    formula="EMA(12) - EMA(26)",
    data_source="market",
    update_frequency="daily",
)
def _calculate_macd(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 MACD 指标的 DIF 线（快慢均线差值）。

    **公式**::

        EMA_fast = EMA(Close, span=fast_period)    — 默认 12
        EMA_slow = EMA(Close, span=slow_period)    — 默认 26
        DIF_t    = EMA_fast_t - EMA_slow_t

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key：
        - ``"fast_period"``: 快线周期（默认 12）
        - ``"slow_period"``: 慢线周期（默认 26）

    Returns
    -------
    pd.Series
        DIF 线序列（仅 DIF，不含 DEA 和柱状图）

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空序列
    - 数据 < slow_period → EMA 未充分收敛，前段值不稳定
    - 若需要完整 MACD(12,26,9) 三线，需额外计算 ``DEA = EMA(DIF, 9)``
      和 ``MACD Bar = 2 * (DIF - DEA)``
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    fast_period = parameters.get("fast_period", 12) if parameters else 12
    slow_period = parameters.get("slow_period", 26) if parameters else 26

    ema_fast = df['close'].ewm(span=fast_period, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow_period, adjust=False).mean()
    macd = ema_fast - ema_slow

    return macd


@register_factor(
    name=StandardFactors.RSI,
    display_name=StandardFactors.RSI,
    description="相对强弱指标，衡量价格动量和超买超卖状态",
    category=FactorCategoryCode.TECHNICAL,
    formula="100 - 100/(1 + RS), Wilder smoothing",
    data_source="market",
    update_frequency="daily",
)
def _calculate_rsi(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算相对强弱指标（Relative Strength Index, RSI）。

    **Wilder's Smoothing Method**（默认）::

        delta_t = Close_t - Close_{t-1}
        gain_t  = delta_t   if delta_t > 0 else 0
        loss_t  = -delta_t  if delta_t < 0 else 0
        avg_gain_t = ewm(gain, alpha=1/N)_t
        avg_loss_t = ewm(loss, alpha=1/N)_t
        RS_t       = avg_gain_t / avg_loss_t
        RSI_t      = 100 - 100 / (1 + RS_t)

    默认 ``N=14``。

    当 avg_gain 和 avg_loss 均为 0 时（如横盘），RSI 填充为 50（中性）。

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key：
        - ``"period"``: RSI 周期 N（默认 14）
        - ``"method"``: ``"wilder"``（平滑）| ``"standard"``（简单 SMA，默认 ``"wilder"``）

    Returns
    -------
    pd.Series
        RSI 值序列（0-100），index 与 df 对齐，NaN 填充为 50

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空 ``pd.Series(dtype=float, index=df.index)``
    - gain 和 loss 同时为 0（横盘） → RS 为 0/0 = NaN，RSI fillna(50)
    - loss=0 且 gain>0 → RS 为 inf，replace 为 NaN 后 RSI=100-100/(1+NaN)=NaN，需后续处理
    - 数据不足 period → Wilder 方法依赖 ewm 可收敛，Standard 方法前 period 个值为 NaN
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    period = parameters.get("period", 14) if parameters else 14
    method = parameters.get("method", "wilder") if parameters else "wilder"

    delta = df['close'].diff()

    if method == "wilder":
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1 / period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1 / period, adjust=False).mean()
    else:
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rs = rs.replace([np.inf, -np.inf], np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.fillna(50)

    return rsi


@register_factor(
    name=StandardFactors.BOLL,
    display_name="布林带中轨",
    description="布林带中轨（SMA），衡量价格相对位置",
    category=FactorCategoryCode.TECHNICAL,
    formula="SMA(Close, 20)",
    data_source="market",
    update_frequency="daily",
)
def _calculate_boll(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算布林带中轨（Bollinger Bands Middle Line）。

    **公式**::

        MIDDLE_t = SMA(Close, period)_t

    默认 ``period=20``。仅返回中轨，上轨/下轨暂未计算。
    完整布林带公式：
    - MIDDLE = SMA(Close, 20)
    - UPPER  = MIDDLE + k * std(Close, 20)，k 默认 2
    - LOWER  = MIDDLE - k * std(Close, 20)

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'close'`` 列
    parameters : Optional[Dict]
        可选 key ``"period"``（默认 20）

    Returns
    -------
    pd.Series
        布林带中轨序列，前 period-1 个值为 NaN

    Edge Cases
    ~~~~~~~~~~
    - ``'close'`` 列缺失 → 返回空序列
    - period > 数据长度 → 全 NaN
    """
    if 'close' not in df.columns:
        return pd.Series(dtype=float, index=df.index)

    period = parameters.get("period", 20) if parameters else 20

    middle = df['close'].rolling(window=period).mean()

    return middle


@register_factor(
    name=StandardFactors.KDJ,
    display_name="KDJ-K值",
    description="随机指标 K 值，反映价格在近期高低区间的相对位置",
    category=FactorCategoryCode.TECHNICAL,
    formula="RSV=100*(C-L)/(H-L); K=EMA(RSV,1/3)",
    data_source="market",
    update_frequency="daily",
)
def _calculate_kdj(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """
    计算 KDJ 指标的 K 值（快速随机指标）。

    **公式**::

        L_min_t   = min(Low_{t-N+1:t})
        H_max_t   = max(High_{t-N+1:t})
        RSV_t     = 100 * (Close_t - L_min_t) / (H_max_t - L_min_t)
        K_t       = EMA(RSV, alpha=1/M1)_t

    默认 ``N=9``（RSV 窗口），``M1=3``（K 值平滑周期）。
    当 ``H_max = L_min``（一字板）时，RSV 分母为 0，填充为 50（中性）。

    完整 KDJ 三线：
    - K = EMA(RSV, 1/M1)
    - D = EMA(K, 1/M2)，M2 默认 3
    - J = 3*K - 2*D

    Parameters
    ----------
    df : pd.DataFrame
        行情 DataFrame，必须包含 ``'high'``, ``'low'``, ``'close'`` 列
    parameters : Optional[Dict]
        可选 key：
        - ``"n"``: RSV 计算窗口（默认 9）
        - ``"m1"``: K 值平滑因子（默认 3），alpha = 1/m1

    Returns
    -------
    pd.Series
        KDJ 的 K 值序列（仅 K 线），NaN 填充为 50

    Edge Cases
    ~~~~~~~~~~
    - 缺少 ``'high'`` / ``'low'`` / ``'close'`` 任一一列 → 返回空序列
    - 连续一字板 → H_max = L_min，RSV 分母为 0，fillna(50)
    - 前 N-1 个值缺少完整窗口 → RSV 为 NaN，fillna(50)
    """
    required_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return pd.Series(dtype=float, index=df.index)

    n = parameters.get("n", 9) if parameters else 9
    m1 = parameters.get("m1", 3) if parameters else 3

    low_min = df['low'].rolling(window=n).min()
    high_max = df['high'].rolling(window=n).max()

    rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
    rsv = rsv.fillna(50)

    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()

    return k


# -------------------- ATR (Average True Range) --------------------

@register_factor(
    name="ATR",
    display_name="平均真实波幅",
    description="Average True Range，衡量价格波动幅度",
    category=FactorCategoryCode.VOLATILITY,
    formula="max(H-L, |H-C_prev|, |L-C_prev|) 的 N 日移动平均",
    data_source="market",
    update_frequency="daily",
)
def _calculate_atr(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """计算 ATR（Average True Range）"""
    required_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return pd.Series(dtype=float, index=df.index)

    period = parameters.get("period", 14) if parameters else 14

    high = df['high']
    low = df['low']
    close = df['close']
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = true_range.rolling(window=period).mean()
    return atr


# -------------------- ADX (Average Directional Index) --------------------


def _calc_directional_movement(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
):
    """计算 +DI / -DI / ADX（Wilder 平滑法，标准定义）。

    返回值: (+DI, -DI, ADX) — 三个 pd.Series
    """
    prev_high = high.shift(1)
    prev_low = low.shift(1)
    prev_close = close.shift(1)

    up_move = high - prev_high
    down_move = prev_low - low

    # +DM: 上涨幅度 > 下跌幅度 且 上涨幅度 > 0
    pos_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    # -DM: 下跌幅度 > 上涨幅度 且 下跌幅度 > 0
    neg_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    # True Range = max(H-L, |H-C_prev|, |L-C_prev|)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    # Wilder's smoothing (alpha = 1/period)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    smoothed_pos_dm = pos_dm.ewm(alpha=1.0 / period, adjust=False).mean()
    smoothed_neg_dm = neg_dm.ewm(alpha=1.0 / period, adjust=False).mean()

    # +DI / -DI（分母保护：ATR 为 0 时设为 NaN）
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100.0 * smoothed_pos_dm / atr_safe
    minus_di = 100.0 * smoothed_neg_dm / atr_safe

    # DX = |+DI - -DI| / (+DI + -DI) * 100
    di_sum = plus_di + minus_di
    dx = (100.0 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan))

    # ADX = Wilder's EMA of DX
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()

    return plus_di, minus_di, adx


@register_factor(
    name="ADX",
    display_name="平均趋向指数",
    description="Average Directional Index，衡量趋势强度(>25趋势,<20震荡)，Wilder平滑",
    category=FactorCategoryCode.TECHNICAL,
    formula="+DM/-DM → +DI/-DI → DX → ADX (Wilder EMA, 14)",
    data_source="market",
    update_frequency="daily",
)
def _calculate_adx(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """计算 ADX（Average Directional Index）。

    Wilder's Method (标准定义):
        +DM_t = H_t - H_{t-1}  (if positive and > -DM)
        -DM_t = L_{t-1} - L_t  (if positive and > +DM)
        +DI = 100 * EMA(+DM, 1/N) / ATR
        -DI = 100 * EMA(-DM, 1/N) / ATR
        DX  = 100 * |+DI - -DI| / (+DI + -DI)
        ADX = EMA(DX, 1/N)

    默认 N=14。ADX > 25 趋势市，ADX < 20 震荡市。

    Edge Cases
    ~~~~~~~~~~
    - 缺 high/low → 返回带 NaN 的 Series（index 与 df 对齐）
    - ATR=0（一字板）→ +DI/-DI 为 NaN，ADX 随之 NaN
    - +DI + -DI = 0 → DX 为 NaN
    """
    required_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return pd.Series(np.nan, index=df.index, dtype=float)

    period = parameters.get("period", 14) if parameters else 14
    _, _, adx = _calc_directional_movement(df['high'], df['low'], df['close'], period)
    return adx


@register_factor(
    name="PLUS_DI",
    display_name="上升动向指标",
    description="Positive Directional Indicator (+DI)，衡量多头力量",
    category=FactorCategoryCode.TECHNICAL,
    formula="100 * EMA(+DM, 1/N) / ATR",
    data_source="market",
    update_frequency="daily",
)
def _calculate_plus_di(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """计算 +DI（上升动向指标）。"""
    required_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return pd.Series(np.nan, index=df.index, dtype=float)

    period = parameters.get("period", 14) if parameters else 14
    plus_di, _, _ = _calc_directional_movement(df['high'], df['low'], df['close'], period)
    return plus_di


@register_factor(
    name="MINUS_DI",
    display_name="下降动向指标",
    description="Negative Directional Indicator (-DI)，衡量空头力量",
    category=FactorCategoryCode.TECHNICAL,
    formula="100 * EMA(-DM, 1/N) / ATR",
    data_source="market",
    update_frequency="daily",
)
def _calculate_minus_di(
    df: DataFrame,
    parameters: Optional[Dict] = None,
) -> pd.Series:
    """计算 -DI（下降动向指标）。"""
    required_cols = ['high', 'low', 'close']
    if not all(col in df.columns for col in required_cols):
        return pd.Series(np.nan, index=df.index, dtype=float)

    period = parameters.get("period", 14) if parameters else 14
    _, minus_di, _ = _calc_directional_movement(df['high'], df['low'], df['close'], period)
    return minus_di


# ============================================================
#  ETF 抄底策略专用因子 (LightGBM ETF Bottom Fishing)
#  类别: etf_bottom
# ============================================================

# ---------- A组: 简单窗口计算 (纯 OHLCV) ----------

@register_factor(
    name="drawdown_20d",
    display_name="20日回撤",
    description="(close - max(high,20)) / max(high,20)，负值越大→超跌",
    category="etf_bottom",
    formula="(close - max_high_20) / max_high_20",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 20},
)
def _calc_drawdown_20d(df: pd.DataFrame, parameters=None) -> pd.Series:
    """20日滚动回撤"""
    w = (parameters or {}).get("window", 20)
    roll_max = df.groupby('ts_code')['high'].transform(
        lambda x: x.rolling(w, min_periods=max(5, w // 4)).max())
    return (df['close'] - roll_max) / roll_max


@register_factor(
    name="drawdown_60d",
    display_name="60日回撤",
    description="(close - max(high,60)) / max(high,60)",
    category="etf_bottom",
    formula="(close - max_high_60) / max_high_60",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 60},
)
def _calc_drawdown_60d(df: pd.DataFrame, parameters=None) -> pd.Series:
    w = (parameters or {}).get("window", 60)
    roll_max = df.groupby('ts_code')['high'].transform(
        lambda x: x.rolling(w, min_periods=max(10, w // 6)).max())
    return (df['close'] - roll_max) / roll_max


@register_factor(
    name="drawdown_120d",
    display_name="120日回撤",
    description="(close - max(high,120)) / max(high,120)",
    category="etf_bottom",
    formula="(close - max_high_120) / max_high_120",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 120},
)
def _calc_drawdown_120d(df: pd.DataFrame, parameters=None) -> pd.Series:
    w = (parameters or {}).get("window", 120)
    roll_max = df.groupby('ts_code')['high'].transform(
        lambda x: x.rolling(w, min_periods=max(20, w // 6)).max())
    return (df['close'] - roll_max) / roll_max


@register_factor(
    name="rsi_28",
    display_name="28日RSI",
    description="28日相对强弱指标",
    category="etf_bottom",
    formula="RSI(period=28)",
    data_source="market",
    update_frequency="daily",
    parameters={"period": 28},
)
def _calc_rsi_28(df: pd.DataFrame, parameters=None) -> pd.Series:
    """28日 RSI"""
    period = (parameters or {}).get("period", 28)
    delta = df.groupby('ts_code')['close'].transform(lambda x: x.diff())
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.groupby(df['ts_code']).transform(
        lambda x: x.rolling(period, min_periods=period).mean())
    avg_loss = loss.groupby(df['ts_code']).transform(
        lambda x: x.rolling(period, min_periods=period).mean())
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


@register_factor(
    name="rsi_low_days",
    display_name="RSI低位持续天数",
    description="RSI(14)<30 的连续天数",
    category="etf_bottom",
    formula="count(rsi_14 < 30, rolling_lookback)",
    data_source="market",
    update_frequency="daily",
    parameters={"threshold": 30, "lookback": 60},
)
def _calc_rsi_low_days(df: pd.DataFrame, parameters=None) -> pd.Series:
    """RSI 低于阈值持续天数"""
    threshold = (parameters or {}).get("threshold", 30)
    lookback = (parameters or {}).get("lookback", 60)
    # 复用 RSI(14) 计算
    period = 14
    delta = df.groupby('ts_code')['close'].transform(lambda x: x.diff())
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.groupby(df['ts_code']).transform(
        lambda x: x.rolling(period, min_periods=period).mean())
    avg_loss = loss.groupby(df['ts_code']).transform(
        lambda x: x.rolling(period, min_periods=period).mean())
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    below = (rsi < threshold).astype(int)
    # 连续低于阈值天数
    result = below.groupby(df['ts_code']).transform(
        lambda x: x.rolling(lookback, min_periods=1).sum())
    return result


@register_factor(
    name="ma_disparity_20",
    display_name="20日均线偏离",
    description="(close - MA20) / MA20",
    category="etf_bottom",
    formula="(close - MA20) / MA20",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 20},
)
def _calc_ma_disparity_20(df: pd.DataFrame, parameters=None) -> pd.Series:
    w = (parameters or {}).get("window", 20)
    ma = df.groupby('ts_code')['close'].transform(lambda x: x.rolling(w, min_periods=5).mean())
    return (df['close'] - ma) / ma


@register_factor(
    name="ma_disparity_60",
    display_name="60日均线偏离",
    description="(close - MA60) / MA60",
    category="etf_bottom",
    formula="(close - MA60) / MA60",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 60},
)
def _calc_ma_disparity_60(df: pd.DataFrame, parameters=None) -> pd.Series:
    w = (parameters or {}).get("window", 60)
    ma = df.groupby('ts_code')['close'].transform(lambda x: x.rolling(w, min_periods=10).mean())
    return (df['close'] - ma) / ma


@register_factor(
    name="ma_disparity_120",
    display_name="120日均线偏离",
    description="(close - MA120) / MA120",
    category="etf_bottom",
    formula="(close - MA120) / MA120",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 120},
)
def _calc_ma_disparity_120(df: pd.DataFrame, parameters=None) -> pd.Series:
    w = (parameters or {}).get("window", 120)
    ma = df.groupby('ts_code')['close'].transform(lambda x: x.rolling(w, min_periods=20).mean())
    return (df['close'] - ma) / ma


@register_factor(
    name="close_to_low_20d",
    display_name="收盘相对20日低点",
    description="(close - min(low,20)) / close，接近0→靠近低点",
    category="etf_bottom",
    formula="(close - min_low_20) / close",
    data_source="market",
    update_frequency="daily",
)
def _calc_close_to_low_20d(df: pd.DataFrame, parameters=None) -> pd.Series:
    roll_min = df.groupby('ts_code')['low'].transform(
        lambda x: x.rolling(20, min_periods=5).min())
    return (df['close'] - roll_min) / df['close']


@register_factor(
    name="price_position_250d",
    display_name="250日价格位置",
    description="(close-min(low,250))/(max(high,250)-min(low,250))，值越低→在低位",
    category="etf_bottom",
    formula="(close - low_250) / (high_250 - low_250)",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 250},
)
def _calc_price_position_250d(df: pd.DataFrame, parameters=None) -> pd.Series:
    w = (parameters or {}).get("window", 250)
    lo = df.groupby('ts_code')['low'].transform(lambda x: x.rolling(w, min_periods=20).min())
    hi = df.groupby('ts_code')['high'].transform(lambda x: x.rolling(w, min_periods=20).max())
    denom = hi - lo
    denom = denom.replace(0, np.nan)
    return (df['close'] - lo) / denom


@register_factor(
    name="momentum_5d",
    display_name="5日动量",
    description="close / close_5d_ago - 1",
    category="etf_bottom",
    formula="close / lag(close,5) - 1",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 5},
)
def _calc_momentum_5d(df: pd.DataFrame, parameters=None) -> pd.Series:
    w = (parameters or {}).get("window", 5)
    lag = df.groupby('ts_code')['close'].transform(lambda x: x.shift(w))
    return df['close'] / lag - 1


@register_factor(
    name="consecutive_down_days",
    display_name="连续下跌天数",
    description="连续 close < pre_close 的天数",
    category="etf_bottom",
    formula="sum(close < pre_close, consecutive)",
    data_source="market",
    update_frequency="daily",
)
def _calc_consecutive_down_days(df: pd.DataFrame, parameters=None) -> pd.Series:
    """连续下跌天数"""
    down = (df['close'] < df.groupby('ts_code')['pre_close'].transform(lambda x: x))
    result = down.groupby(df['ts_code']).transform(
        lambda x: x.astype(int).groupby((x != x.shift()).cumsum()).cumsum())
    return result.astype(float)


@register_factor(
    name="atr_ratio_20",
    display_name="ATR相对值",
    description="ATR(14) / close，值越高→波动相对大",
    category="etf_bottom",
    formula="ATR14 / close",
    data_source="market",
    update_frequency="daily",
)
def _calc_atr_ratio_20(df: pd.DataFrame, parameters=None) -> pd.Series:
    """ATR相对价格"""
    high, low, close = df['high'], df['low'], df['close']
    prev_close = close.groupby(df['ts_code']).transform(lambda x: x.shift(1))
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.groupby(df['ts_code']).transform(lambda x: x.rolling(14, min_periods=5).mean())
    return atr14 / close


@register_factor(
    name="atr_ratio",
    display_name="多周期ATR比率",
    description="ATR(5) / ATR(20)，短期波动放大=regime转换领先信号；值>1→波动扩张(趋势启动)，<1→波动收缩(震荡)",
    category="etf_bottom",
    formula="ATR(5) / ATR(20)",
    data_source="market",
    update_frequency="daily",
)
def _calc_atr_ratio(df: pd.DataFrame, parameters=None) -> pd.Series:
    """多周期 ATR 比率：短期波动 / 长期波动，预报 regime 转换"""
    high, low, close = df['high'], df['low'], df['close']
    prev_close = close.groupby(df['ts_code']).transform(lambda x: x.shift(1))
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr5 = tr.groupby(df['ts_code']).transform(lambda x: x.rolling(5, min_periods=5).mean())
    atr20 = tr.groupby(df['ts_code']).transform(lambda x: x.rolling(20, min_periods=20).mean())
    return atr5 / atr20.replace(0, np.nan)


@register_factor(
    name="amplitude_5d",
    display_name="5日平均振幅",
    description="mean((high-low)/pre_close, 5)",
    category="etf_bottom",
    formula="mean((h-l)/pre_close, 5)",
    data_source="market",
    update_frequency="daily",
)
def _calc_amplitude_5d(df: pd.DataFrame, parameters=None) -> pd.Series:
    amp = (df['high'] - df['low']) / df['pre_close']
    return amp.groupby(df['ts_code']).transform(lambda x: x.rolling(5, min_periods=2).mean())


@register_factor(
    name="max_dd_duration",
    display_name="最大回撤持续天数",
    description="从近期高点至今的持续天数",
    category="etf_bottom",
    formula="days_since_rolling_peak(60)",
    data_source="market",
    update_frequency="daily",
)
def _calc_max_dd_duration(df: pd.DataFrame, parameters=None) -> pd.Series:
    """从60日高点的天数"""
    roll_peak = df.groupby('ts_code')['close'].transform(
        lambda x: x.rolling(60, min_periods=10).max())
    peak_dates = df.groupby('ts_code')['close'].transform(
        lambda x: x.rolling(60, min_periods=10).apply(lambda y: y.argmax(), raw=False))
    # 简化：当前是否低于60日高点 + 持续天数
    below_peak = (df['close'] < roll_peak.shift(1)).astype(int)
    return below_peak.groupby(df['ts_code']).transform(
        lambda x: x.groupby((x != x.shift()).cumsum()).cumsum())


# ---------- 量价因子 ----------

@register_factor(
    name="volume_shrink_5d",
    display_name="5日缩量比",
    description="vol / mean(vol,5)，<0.6→供应衰竭",
    category="etf_bottom",
    formula="vol / MA(vol, 5)",
    data_source="market",
    update_frequency="daily",
)
def _calc_volume_shrink_5d(df: pd.DataFrame, parameters=None) -> pd.Series:
    ma5 = df.groupby('ts_code')['vol'].transform(lambda x: x.rolling(5, min_periods=3).mean())
    return df['vol'] / ma5


@register_factor(
    name="volume_shrink_20d",
    display_name="20日缩量比",
    description="vol / mean(vol,20)",
    category="etf_bottom",
    formula="vol / MA(vol, 20)",
    data_source="market",
    update_frequency="daily",
)
def _calc_volume_shrink_20d(df: pd.DataFrame, parameters=None) -> pd.Series:
    ma20 = df.groupby('ts_code')['vol'].transform(lambda x: x.rolling(20, min_periods=5).mean())
    return df['vol'] / ma20


@register_factor(
    name="vol_trend",
    display_name="量能趋势",
    description="MA(vol, 5) / MA(vol, 20)，放量→资金进场/趋势启动信号；值>1.2→显著放量，<0.8→缩量",
    category="etf_bottom",
    formula="MA(vol, 5) / MA(vol, 20)",
    data_source="market",
    update_frequency="daily",
)
def _calc_vol_trend(df: pd.DataFrame, parameters=None) -> pd.Series:
    """量能趋势：短周期均量 / 长周期均量"""
    ma5 = df.groupby('ts_code')['vol'].transform(lambda x: x.rolling(5, min_periods=3).mean())
    ma20 = df.groupby('ts_code')['vol'].transform(lambda x: x.rolling(20, min_periods=5).mean())
    return ma5 / ma20.replace(0, np.nan)


@register_factor(
    name="vol_decline_corr",
    display_name="量价下跌相关性",
    description="近20日成交量与收益率的相关系数",
    category="etf_bottom",
    formula="rolling_corr(vol, ret, 20)",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 20},
)
def _calc_vol_decline_corr(df: pd.DataFrame, parameters=None) -> pd.Series:
    w = (parameters or {}).get("window", 20)
    ret = df.groupby('ts_code')['close'].transform(lambda x: x.pct_change())
    return df.groupby('ts_code').apply(
        lambda g: g['vol'].rolling(w).corr(ret.loc[g.index]),
        include_groups=False,
    ).reset_index(level=0, drop=True)


@register_factor(
    name="vol_spike_count",
    display_name="放量下跌次数",
    description="近10日放量(>1.5x均量)+下跌的天数",
    category="etf_bottom",
    formula="count(vol > 1.5*MA20 AND ret < 0, 10)",
    data_source="market",
    update_frequency="daily",
)
def _calc_vol_spike_count(df: pd.DataFrame, parameters=None) -> pd.Series:
    ma20 = df.groupby('ts_code')['vol'].transform(lambda x: x.rolling(20, min_periods=5).mean())
    ret = df.groupby('ts_code')['close'].transform(lambda x: x.pct_change())
    spike = ((df['vol'] > 1.5 * ma20) & (ret < 0)).astype(int)
    return spike.groupby(df['ts_code']).transform(lambda x: x.rolling(10, min_periods=1).sum())


@register_factor(
    name="turnover_change_5d",
    display_name="换手率变化",
    description="turnover / mean(turnover, 5)",
    category="etf_bottom",
    formula="turnover / MA(turnover, 5)",
    data_source="market",
    update_frequency="daily",
)
def _calc_turnover_change_5d(df: pd.DataFrame, parameters=None) -> pd.Series:
    if 'turnover_rate' not in df.columns:
        return pd.Series(np.nan, index=df.index)
    ma5 = df.groupby('ts_code')['turnover_rate'].transform(lambda x: x.rolling(5, min_periods=3).mean())
    return df['turnover_rate'] / ma5


@register_factor(
    name="amount_change_5d",
    display_name="成交额变化",
    description="amount / mean(amount, 5)",
    category="etf_bottom",
    formula="amount / MA(amount, 5)",
    data_source="market",
    update_frequency="daily",
)
def _calc_amount_change_5d(df: pd.DataFrame, parameters=None) -> pd.Series:
    if 'amount' not in df.columns:
        return pd.Series(np.nan, index=df.index)
    ma5 = df.groupby('ts_code')['amount'].transform(lambda x: x.rolling(5, min_periods=3).mean())
    return df['amount'] / ma5


@register_factor(
    name="high_vol_days_5d",
    display_name="高波动天数",
    description="近5日vol>1.5x均量天数",
    category="etf_bottom",
    formula="count(vol > 1.5*MA20, 5)",
    data_source="market",
    update_frequency="daily",
)
def _calc_high_vol_days_5d(df: pd.DataFrame, parameters=None) -> pd.Series:
    ma20 = df.groupby('ts_code')['vol'].transform(lambda x: x.rolling(20, min_periods=5).mean())
    high = (df['vol'] > 1.5 * ma20).astype(int)
    return high.groupby(df['ts_code']).transform(lambda x: x.rolling(5, min_periods=1).sum())


@register_factor(
    name="pct_chg_abs_mean_5d",
    display_name="5日绝对涨跌幅均值",
    description="mean(|pct_chg|, 5)",
    category="etf_bottom",
    formula="mean(abs(pct_chg), 5)",
    data_source="market",
    update_frequency="daily",
)
def _calc_pct_chg_abs_mean_5d(df: pd.DataFrame, parameters=None) -> pd.Series:
    if 'pct_chg' not in df.columns:
        ret = df.groupby('ts_code')['close'].transform(lambda x: x.pct_change())
        abs_ret = ret.abs()
    else:
        abs_ret = df['pct_chg'].abs()
    return abs_ret.groupby(df['ts_code']).transform(lambda x: x.rolling(5, min_periods=2).mean())


@register_factor(
    name="boll_pct_b",
    display_name="布林带%B",
    description="(close - BOLL_lower) / (BOLL_upper - BOLL_lower)",
    category="etf_bottom",
    formula="(close - lower) / (upper - lower)",
    data_source="market",
    update_frequency="daily",
    parameters={"period": 20, "nbdev": 2},
)
def _calc_boll_pct_b(df: pd.DataFrame, parameters=None) -> pd.Series:
    period = (parameters or {}).get("period", 20)
    nbdev = (parameters or {}).get("nbdev", 2)
    mid = df.groupby('ts_code')['close'].transform(lambda x: x.rolling(period).mean())
    std = df.groupby('ts_code')['close'].transform(lambda x: x.rolling(period).std())
    upper = mid + nbdev * std
    lower = mid - nbdev * std
    denom = upper - lower
    denom = denom.replace(0, np.nan)
    return (df['close'] - lower) / denom


# ---------- B组: 量价高级因子 ----------

@register_factor(
    name="volume_dry_up",
    display_name="缩量止跌信号",
    description="连续下跌5天 + 最后3天量递减 → 供应衰竭",
    category="etf_bottom",
    formula="down5 AND vol_dec3",
    data_source="market",
    update_frequency="daily",
)
def _calc_volume_dry_up(df: pd.DataFrame, parameters=None) -> pd.Series:
    """缩量止跌：跌≥5天 且 最后3天量递减 → 1.0，否则 0.0"""
    ret = df.groupby('ts_code')['close'].transform(lambda x: x.pct_change())
    down = (ret < 0).astype(int)
    # 连续下跌 ≥5 天
    down_streak = down.groupby(df['ts_code']).transform(
        lambda x: x.groupby((x != x.shift()).cumsum()).cumsum())
    # 近3天量递减
    vol = df['vol']
    vol_dec = (
        (vol < vol.groupby(df['ts_code']).transform(lambda x: x.shift(1))) &
        (vol.groupby(df['ts_code']).transform(lambda x: x.shift(1)) <
         vol.groupby(df['ts_code']).transform(lambda x: x.shift(2)))
    ).astype(int)
    result = ((down_streak >= 5) & (vol_dec == 1)).astype(float)
    return result


@register_factor(
    name="vwap_distance",
    display_name="VWAP偏离",
    description="(close - VWAP_20) / VWAP_20，负值→低于均价",
    category="etf_bottom",
    formula="(close - vwap_20) / vwap_20",
    data_source="market",
    update_frequency="daily",
    parameters={"window": 20},
)
def _calc_vwap_distance(df: pd.DataFrame, parameters=None) -> pd.Series:
    """20日 VWAP 偏离度"""
    w = (parameters or {}).get("window", 20)
    if 'amount' not in df.columns:
        return pd.Series(np.nan, index=df.index)
    tp = (df['high'] + df['low'] + df['close']) / 3
    vp = tp * df['vol']
    cum_vp = vp.groupby(df['ts_code']).transform(lambda x: x.rolling(w, min_periods=5).sum())
    cum_vol = df['vol'].groupby(df['ts_code']).transform(lambda x: x.rolling(w, min_periods=5).sum())
    vwap = cum_vp / cum_vol.replace(0, np.nan)
    return (df['close'] - vwap) / vwap


@register_factor(
    name="volume_ma20_ratio",
    display_name="量比MA20",
    description="vol / MA(vol, 20)",
    category="etf_bottom",
    formula="vol / MA(vol, 20)",
    data_source="market",
    update_frequency="daily",
)
def _calc_volume_ma20_ratio(df: pd.DataFrame, parameters=None) -> pd.Series:
    """成交量与20日均量之比"""
    ma20 = df.groupby('ts_code')['vol'].transform(lambda x: x.rolling(20, min_periods=5).mean())
    return df['vol'] / ma20


@register_factor(
    name="obv_divergence",
    display_name="OBV背离信号",
    description="close创20日新低 但 OBV未创新低 → 背离=1.0",
    category="etf_bottom",
    formula="close_new_low_20 AND NOT obv_new_low_20",
    data_source="market",
    update_frequency="daily",
)
def _calc_obv_divergence(df: pd.DataFrame, parameters=None) -> pd.Series:
    """OBV 底背离：价格新低但 OBV 不创新低"""
    ret = df.groupby('ts_code')['close'].transform(lambda x: x.pct_change())
    obv_sign = ret.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv_inc = (obv_sign * df['vol']).groupby(df['ts_code']).transform(
        lambda x: x.cumsum())
    close_20_low = df.groupby('ts_code')['close'].transform(
        lambda x: x.rolling(20, min_periods=10).min())
    obv_20_low = obv_inc.groupby(df['ts_code']).transform(
        lambda x: x.rolling(20, min_periods=10).min())
    close_at_low = (df['close'] <= close_20_low * 1.01).astype(int)
    obv_not_at_low = (obv_inc > obv_20_low * 1.02).astype(int)
    return (close_at_low & obv_not_at_low).astype(float)


# ---------- C组: 补充技术因子 (对标 stock_factor_pro_daily，从 OHLCV 计算) ----------

@register_factor(
    name="rsi_6",
    display_name="6日RSI",
    description="6日相对强弱指标，短期超卖信号",
    category="etf_bottom",
    formula="RSI(period=6)",
    data_source="market",
    update_frequency="daily",
    parameters={"period": 6},
)
def _calc_rsi_6(df: pd.DataFrame, parameters=None) -> pd.Series:
    period = (parameters or {}).get("period", 6)
    delta = df.groupby('ts_code')['close'].transform(lambda x: x.diff())
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.groupby(df['ts_code']).transform(
        lambda x: x.rolling(period, min_periods=period).mean())
    avg_loss = loss.groupby(df['ts_code']).transform(
        lambda x: x.rolling(period, min_periods=period).mean())
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


@register_factor(
    name="rsi_14",
    display_name="14日RSI",
    description="14日相对强弱指标，经典超买超卖",
    category="etf_bottom",
    formula="RSI(period=14)",
    data_source="market",
    update_frequency="daily",
    parameters={"period": 14},
)
def _calc_rsi_14(df: pd.DataFrame, parameters=None) -> pd.Series:
    period = (parameters or {}).get("period", 14)
    delta = df.groupby('ts_code')['close'].transform(lambda x: x.diff())
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.groupby(df['ts_code']).transform(
        lambda x: x.rolling(period, min_periods=period).mean())
    avg_loss = loss.groupby(df['ts_code']).transform(
        lambda x: x.rolling(period, min_periods=period).mean())
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


@register_factor(
    name="boll_width",
    display_name="布林带宽",
    description="(BOLL_upper - BOLL_lower) / BOLL_mid，高值→高波动",
    category="etf_bottom",
    formula="(upper - lower) / mid",
    data_source="market",
    update_frequency="daily",
    parameters={"period": 20, "nbdev": 2},
)
def _calc_boll_width(df: pd.DataFrame, parameters=None) -> pd.Series:
    period = (parameters or {}).get("period", 20)
    nbdev = (parameters or {}).get("nbdev", 2)
    mid = df.groupby('ts_code')['close'].transform(lambda x: x.rolling(period).mean())
    std = df.groupby('ts_code')['close'].transform(lambda x: x.rolling(period).std())
    upper = mid + nbdev * std
    lower = mid - nbdev * std
    return (upper - lower) / mid


@register_factor(
    name="momentum_3d",
    display_name="3日动量",
    description="close / lag(close,3) - 1，短期急跌识别",
    category="etf_bottom",
    formula="close / lag(close,3) - 1",
    data_source="market",
    update_frequency="daily",
)
def _calc_momentum_3d(df: pd.DataFrame, parameters=None) -> pd.Series:
    lag = df.groupby('ts_code')['close'].transform(lambda x: x.shift(3))
    return df['close'] / lag - 1


@register_factor(
    name="std_20d",
    display_name="20日波动率",
    description="20日收益率标准差，衡量波动水平",
    category="etf_bottom",
    formula="std(ret, 20)",
    data_source="market",
    update_frequency="daily",
)
def _calc_std_20d(df: pd.DataFrame, parameters=None) -> pd.Series:
    ret = df.groupby('ts_code')['close'].transform(lambda x: x.pct_change())
    return ret.groupby(df['ts_code']).transform(lambda x: x.rolling(20, min_periods=5).std())


@register_factor(
    name="atr_14",
    display_name="ATR(14)",
    description="14日平均真实波幅，衡量绝对波动幅度",
    category="etf_bottom",
    formula="ATR(period=14)",
    data_source="market",
    update_frequency="daily",
    parameters={"period": 14},
)
def _calc_atr_14(df: pd.DataFrame, parameters=None) -> pd.Series:
    period = (parameters or {}).get("period", 14)
    high, low, close = df['high'], df['low'], df['close']
    prev_close = close.groupby(df['ts_code']).transform(lambda x: x.shift(1))
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.groupby(df['ts_code']).transform(lambda x: x.rolling(period, min_periods=5).mean())


# ============================================================
#  Convenience: factor name → calculator function mapping
#  (used by LightGBMBottomStrategy for on_bar prediction)
# ============================================================
FACTOR_CALCULATORS_MAP = {
    "drawdown_20d": _calc_drawdown_20d,
    "drawdown_60d": _calc_drawdown_60d,
    "drawdown_120d": _calc_drawdown_120d,
    "rsi_28": _calc_rsi_28,
    "rsi_low_days": _calc_rsi_low_days,
    "ma_disparity_20": _calc_ma_disparity_20,
    "ma_disparity_60": _calc_ma_disparity_60,
    "ma_disparity_120": _calc_ma_disparity_120,
    "close_to_low_20d": _calc_close_to_low_20d,
    "price_position_250d": _calc_price_position_250d,
    "momentum_5d": _calc_momentum_5d,
    "consecutive_down_days": _calc_consecutive_down_days,
    "atr_ratio_20": _calc_atr_ratio_20,
    "amplitude_5d": _calc_amplitude_5d,
    "max_dd_duration": _calc_max_dd_duration,
    "volume_shrink_5d": _calc_volume_shrink_5d,
    "volume_shrink_20d": _calc_volume_shrink_20d,
    "vol_decline_corr": _calc_vol_decline_corr,
    "vol_spike_count": _calc_vol_spike_count,
    "amount_change_5d": _calc_amount_change_5d,
    "pct_chg_abs_mean_5d": _calc_pct_chg_abs_mean_5d,
    "high_vol_days_5d": _calc_high_vol_days_5d,
    "boll_pct_b": _calc_boll_pct_b,
    "turnover_change_5d": _calc_turnover_change_5d,
    "volume_dry_up": _calc_volume_dry_up,
    "vwap_distance": _calc_vwap_distance,
    "volume_ma20_ratio": _calc_volume_ma20_ratio,
    "obv_divergence": _calc_obv_divergence,
    "rsi_6": _calc_rsi_6,
    "rsi_14": _calc_rsi_14,
    "boll_width": _calc_boll_width,
    "momentum_3d": _calc_momentum_3d,
    "std_20d": _calc_std_20d,
    "atr_14": _calc_atr_14,
    "atr_ratio": _calc_atr_ratio,
    "vol_trend": _calc_vol_trend,
}
