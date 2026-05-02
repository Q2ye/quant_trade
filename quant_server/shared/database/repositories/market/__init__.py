# quant_server/shared/database/repositories/market/__init__.py
"""
市场数据领域Repository包初始化
遵循混合架构设计：只包含市场数据相关的Repository，按业务子域组织
"""

# 1. 基础信息子域
from .basic import (
    # 股票相关
    StockBasicRepository,
    CompanyRepository,
    STListRepository,

    # ETF相关
    ETFRepository,

    # 指数相关
    IndexBasicRepository,
    IndexWeightRepository,
    IndexRepository,
)

# 2. 行情数据子域（时序超表）
from .quote import (
    StockDailyRepository,      # 股票日行情 [超表]
    StockMinuteRepository,      # 股票分钟行情 [超表]
    StockWeeklyRepository,      # 股票周行情 [超表]
    StockMonthlyRepository,     # 股票月行情 [超表]
    StockAdjFactorRepository,   # 股票复权因子 [超表]
    StockAdjustedPriceRepository,  # 股票复权价格 [超表]
    StockDailyLimitRepository,  # 股票涨跌停价格 [超表]
    EtfDailyRepository,         # ETF日行情 [超表]
    EtfMinuteRepository,        # ETF分钟行情 [超表]
    FundAdjFactorRepository,    # 基金复权因子 [超表]
)



# 3. 基本面数据子域
from .fundamental import (
    StockDailyBasicRepository,  # 股票每日基础指标 [超表]
    StockMoneyflowRepository,   # 股票资金流向 [超表]
    FinancialStatementRepository,  # 财务报表数据
)

# 4. 公司治理子域
from .governance import (
    ManagerRepository,          # 上市公司管理层表
    RewardRepository,           # 股票分红送股表
)

# 5. 参考数据子域
from .reference import (
    TradeCalendarRepository,    # 交易日历表 [超表]
    BasketRepository,           # 股票篮子表
)

__all__ = [
    # === 基础信息 ===
    "StockBasicRepository",
    "CompanyRepository",
    "STListRepository",
    "ETFRepository",
    "IndexBasicRepository",
    "IndexWeightRepository",
    "IndexRepository",

    # === 行情数据 ===
    "StockDailyRepository",
    "StockMinuteRepository",
    "StockWeeklyRepository",
    "StockMonthlyRepository",
    "StockAdjFactorRepository",
    "StockAdjustedPriceRepository",
    "StockDailyLimitRepository",
    "EtfDailyRepository",
    "EtfMinuteRepository",
    "FundAdjFactorRepository",

    # === 基本面数据 ===
    "StockDailyBasicRepository",
    "StockMoneyflowRepository",
    "FinancialStatementRepository",

    # === 公司治理 ===
    "ManagerRepository",
    "RewardRepository",

    # === 参考数据 ===
    "TradeCalendarRepository",
    "BasketRepository",
]