# validation.py            # 数据验证工具
"""
数据验证工具模块
"""

from typing import Dict, Any
from decimal import Decimal


def validate_amount(amount: Decimal, min_value: Decimal = Decimal("0.01")) -> bool:
    """
    验证金额

    Args:
        amount: 金额
        min_value: 最小金额

    Returns:
        bool: 是否验证通过

    Raises:
        ValueError: 金额不符合要求
    """
    if not isinstance(amount, Decimal):
        raise ValueError("金额必须是 Decimal 类型")
    if amount < min_value:
        raise ValueError(f"金额必须大于等于 {min_value}")
    return True


def validate_account_data(data: Dict[str, Any]) -> bool:
    """
    验证账户数据

    Args:
        data: 账户数据

    Returns:
        bool: 是否验证通过
    """

    # 验证必需字段
    required_fields = ['account_info', 'assets_summary', 'daily_pnl_summary']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"缺少必需字段: {field}")

    # 验证账户信息
    account_info = data.get('account_info', {})
    if 'account_id' not in account_info:
        raise ValueError("缺少account_id")

    # 验证资产数据
    assets = data.get('assets_summary', {})
    if 'total_asset' in assets and assets['total_asset'] < 0:
        raise ValueError("总资产不能为负数")

    if 'cash_balance' in assets and assets['cash_balance'] < 0:
        raise ValueError("现金余额不能为负数")

    # 验证盈亏数据
    pnl = data.get('daily_pnl_summary', {})
    if 'total_pnl' in pnl and not isinstance(pnl['total_pnl'], (int, float)):
        raise ValueError("总盈亏必须是数字类型")

    return True


def validate_position_data(data: Dict[str, Any]) -> bool:
    """
    验证持仓数据

    Args:
        data: 持仓数据

    Returns:
        bool: 是否验证通过
    """

    # 验证必需字段
    required_fields = ['security_id', 'current_quantity']
    for field in required_fields:
        if field not in data:
            raise ValueError(f"持仓数据缺少必需字段: {field}")

    # 验证数量字段
    current_quantity = data.get('current_quantity', 0)
    if current_quantity < 0:
        raise ValueError("持仓数量不能为负数")

    # 验证成本价格
    if 'cost_price' in data:
        cost_price = data['cost_price']
        if not isinstance(cost_price, (int, float)):
            raise ValueError("成本价格必须是数字类型")
        if cost_price < 0:
            raise ValueError("成本价格不能为负数")

    # 验证市值
    if 'market_value' in data:
        market_value = data['market_value']
        if not isinstance(market_value, (int, float)):
            raise ValueError("市值必须是数字类型")
        if market_value < 0:
            raise ValueError("市值不能为负数")

    return True