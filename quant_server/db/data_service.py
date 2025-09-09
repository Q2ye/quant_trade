import logging
from sqlalchemy.orm import Session

from quant_server.data_services.etf_basic_service import EtfBasicService
from quant_server.data_services.etf_daily_service import EtfDailyService
from quant_server.data_services.etf_minute_service import EtfMinuteService
from quant_server.data_services.fund_adjFactor_service import FundAdjFactorService
from quant_server.data_services.stk_manager_service import StkManagerService
from quant_server.data_services.stk_reward_service import StkRewardService
from quant_server.data_services.stock_adjFactor_aervice import StockAdjFactorService
from quant_server.data_services.stock_adjustedPrices_service import StockAdjustedPricesService
from quant_server.data_services.stock_basic_service import StockBasicService
from quant_server.data_services.stock_company_service import StockCompanyService
from quant_server.data_services.stock_daily_basic_service import StockDailyBasicService
from quant_server.data_services.stock_daily_limit_service import StockDailyLimitService
from quant_server.data_services.stock_daily_service import StockDailyService
from quant_server.data_services.stock_minutes_service import StockMinutesService
from quant_server.data_services.stock_moneyflow_service import StockMoneyflowService
from quant_server.data_services.stock_monthly_service import StockMonthlyService
from quant_server.data_services.stock_weekly_service import StockWeeklyService

from quant_server.data_services.sys_user_service import SysUserService, SysPermissionService
from quant_server.data_services.strategy_service import StrategyService, StrategyRunService, StrategyDailyPerformanceService
from quant_server.data_services.trading_service import OrderService, TradeService, PositionService
from quant_server.data_services.risk_service import RiskRuleService, RiskEventService
from quant_server.data_services.performance_service import AccountDailyPerformanceService
from quant_server.data_services.basket_service import BasketService, BasketItemService
from quant_server.data_services.data_sync_service import DataSyncService
from quant_server.data_services.data_sync_task_service import DataSyncTaskService
from quant_server.data_services.signal_service import SignalService

logger = logging.getLogger(__name__)

class DataService:
    """统一数据服务门面类"""

    def __init__(self, session: Session):
        # 数据服务
        # 股票信息服务
        self.stock_basic = StockBasicService(session)
        self.stock_company = StockCompanyService(session)
        self.stk_managers = StkManagerService(session)
        self.stk_rewards = StkRewardService(session)

        # 市场数据服务
        self.stock_daily = StockDailyService(session)
        self.stock_minutes = StockMinutesService(session)
        self.stock_weekly = StockWeeklyService(session)
        self.stock_monthly = StockMonthlyService(session)
        self.stock_adjusted_prices = StockAdjustedPricesService(session)
        self.stock_adj_factor = StockAdjFactorService(session)
        self.stock_daily_basic = StockDailyBasicService(session)
        self.stock_daily_limit = StockDailyLimitService(session)
        self.stock_moneyflow = StockMoneyflowService(session)

        # ETF服务
        self.etf_basic = EtfBasicService(session)
        self.etf_daily = EtfDailyService(session)
        self.etf_minute = EtfMinuteService(session)
        self.fund_adj_factor = FundAdjFactorService(session)

        # 业务服务
        # 用户管理
        self.sys_user = SysUserService(session)
        self.sys_permission = SysPermissionService(session)
        # 策略配置服务
        self.strategy = StrategyService(session)
        self.strategy_run = StrategyRunService(session)
        # 交易服务
        self.order = OrderService(session)
        self.trade = TradeService(session)
        self.signals = SignalService(session)
        self.position = PositionService(session)
        # 股票篮子服务
        self.baskets = BasketService(session)
        self.basket_items = BasketItemService(session)
        # 风控管理
        self.risk_rule = RiskRuleService(session)
        self.risk_event = RiskEventService(session)
        # 绩效分析服务
        self.account_daily_performance = AccountDailyPerformanceService(session)
        self.strategy_daily_performance = StrategyDailyPerformanceService(session)
        # 交易信号记录
        self.signal = SignalService(session)
        # 数据同步服务
        self.data_sync = DataSyncService(session)
        self.data_sync_task = DataSyncTaskService(session)