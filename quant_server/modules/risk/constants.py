# -*- coding: utf-8 -*-
"""
风控模块常量

定义规则名称、默认阈值、告警级别等模块级常量。
"""

from enum import Enum


# ==================== 规则名称枚举 ====================


class RiskRuleName(str, Enum):
    """风控规则名称枚举 — 与 RiskRule.get_name() 返回值一致"""
    # 仓位规则
    POSITION_LIMIT = "position_limit"
    SINGLE_POSITION_LIMIT = "single_position_limit"
    POSITION_CONCENTRATION = "position_concentration"

    # 账户规则
    ACCOUNT_BALANCE = "account_balance"
    LOSS_LIMIT = "loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    CAPITAL_CHANGE = "capital_change"

    # 黑名单规则
    BLACKLIST = "blacklist"
    MARKET_BLACKLIST = "market_blacklist"
    SECTOR_BLACKLIST = "sector_blacklist"

    # 市场规则
    LIQUIDITY = "liquidity"
    PRICE = "price"
    VOLATILITY = "volatility"
    MARKET_STATUS = "market_status"


# ==================== 告警级别 ====================


class RiskLevel(str, Enum):
    """风险级别"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


# ==================== 默认阈值 ====================


class DefaultThreshold:
    """风控默认阈值"""

    # 仓位
    MAX_POSITION_RATIO: float = 0.80          # 总仓位上限
    MAX_SINGLE_POSITION_RATIO: float = 0.30   # 单只股票仓位上限
    MAX_TOP_N_RATIO: float = 0.60             # 前N只集中度上限
    TOP_N: int = 3                            # 前N只

    # 亏损/回撤
    MAX_LOSS_PERCENT: float = 0.05            # 最大亏损比例
    MAX_DRAWDOWN_PERCENT: float = 0.10        # 最大回撤比例
    MAX_DAILY_CHANGE_PERCENT: float = 0.15    # 单日最大资金变化

    # 市场
    MIN_LIQUIDITY: float = 1_000_000.0        # 最小流动性（成交额）
    MIN_PRICE: float = 1.0                    # 最低价格
    MAX_PRICE: float = 1000.0                 # 最高价格
    MAX_VOLATILITY: float = 0.10              # 最大波动率

    # 监控
    RISK_CHECK_INTERVAL: int = 60             # 风险检查间隔（秒）
    POSITION_RISK_THRESHOLD: float = 0.10     # 持仓风险阈值


# ==================== 模块配置 ====================


class ModuleConfig:
    """风控模块配置"""
    MODULE_NAME = "risk"
    MODULE_VERSION = "2.0.0"
    RISK_CHECK_INTERVAL: int = 60
    RISK_CHECK_ENABLED: bool = True
