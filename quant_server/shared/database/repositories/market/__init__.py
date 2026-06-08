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

    # 财务衍生
    StockForecastRepository,  # 业绩预告
    StockExpressRepository,   # 业绩快报
    StockDividendRepository,  # 分红送股
    StockFinaIndicatorRepository,  # 财务指标
    StockAuditOpinionRepository,  # 审计意见
    StockBusinessIncomeRepository,  # 主营业务构成
    CompanyAnnouncementRepository,  # 公司公告
    StockSuspendInfoRepository,  # 停复牌

    # ETF
    EtfShareRepository,  # ETF份额规模

    # Phase 1 (P0 轻量)
    StockHsgtRepository,  # 沪深港通列表
    StockStRiskRepository,  # ST风险警示板
    DisclosureDateRepository,  # 财报披露日期
    StockShareFloatRepository,  # 限售股解禁

    # Phase 2 (P0 逐股)
    StockHoldernumberRepository,  # 股东人数
    StockTop10HoldersRepository,  # 前十大股东
    StockTop10FloatHoldersRepository,  # 前十大流通股东
    StockPledgeStatRepository,  # 股权质押统计
    StockHoldertradeRepository,  # 股东增减持

    # Phase 3 (P1 申万+预测+资金)
    IndexSwClassifyRepository,  # 申万行业分类
    IndexSwMemberRepository,  # 申万行业成分
    IndexSwDailyRepository,  # 申万行业日线
    IndexDailyBasicRepository,  # 大盘指数每日指标
    StockForecastProRepository,  # 券商盈利预测
    StockMoneyflowHsgtRepository,  # 沪深港通资金流向

    # Phase 4 (修复+P2)
    IndexWeeklyRepository,  # 指数周线
    StockDailyLimitRepository,  # 涨跌停价格
    StockFactorDailyRepository,  # 技术因子(基础)
    StockFactorProDailyRepository,  # 技术因子(专业)
    IndexFactorProDailyRepository,  # 指数技术因子(专业)
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
    # 财务衍生
    "StockForecastRepository",
    "StockExpressRepository",
    "StockDividendRepository",
    "StockFinaIndicatorRepository",
    "StockAuditOpinionRepository",
    "StockBusinessIncomeRepository",
    "CompanyAnnouncementRepository",
    "StockSuspendInfoRepository",
    # ETF
    "EtfShareRepository",
    # Phase 1
    "StockHsgtRepository",
    "StockStRiskRepository",
    "DisclosureDateRepository",
    "StockShareFloatRepository",
    # Phase 2
    "StockHoldernumberRepository",
    "StockTop10HoldersRepository",
    "StockTop10FloatHoldersRepository",
    "StockPledgeStatRepository",
    "StockHoldertradeRepository",
    # Phase 3
    "IndexSwClassifyRepository",
    "IndexSwMemberRepository",
    "IndexSwDailyRepository",
    "IndexDailyBasicRepository",
    "StockForecastProRepository",
    "StockMoneyflowHsgtRepository",
    # Phase 4
    "IndexWeeklyRepository",
    "StockDailyLimitRepository",
    "StockFactorDailyRepository",
    "StockFactorProDailyRepository",
    "IndexFactorProDailyRepository",

    # === 公司治理 ===
    "ManagerRepository",
    "RewardRepository",

    # === 参考数据 ===
    "TradeCalendarRepository",
    "BasketRepository",
]