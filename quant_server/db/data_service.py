# data_service.py
import logging
from sqlalchemy.orm import Session

from quant_server.db.data_services.basket_item_service import BasketItemService
from quant_server.db.data_services.basket_service import BasketService
from quant_server.db.data_services.etf_basic_service import EtfBasicService
from quant_server.db.data_services.etf_daily_service import EtfDailyService
from quant_server.db.data_services.etf_minute_service import EtfMinuteService
from quant_server.db.data_services.fund_adjFactor_service import FundAdjFactorService
from quant_server.db.data_services.stk_manager_service import StkManagerService
from quant_server.db.data_services.stk_reward_service import StkRewardService
from quant_server.db.data_services.stock_adjFactor_aervice import StockAdjFactorService
from quant_server.db.data_services.stock_adjustedPrices_service import StockAdjustedPricesService
from quant_server.db.data_services.stock_basic_service import StockBasicService
from quant_server.db.data_services.stock_company_service import StockCompanyService
from quant_server.db.data_services.stock_daily_basic_service import StockDailyBasicService
from quant_server.db.data_services.stock_daily_limit_service import StockDailyLimitService
from quant_server.db.data_services.stock_daily_service import StockDailyService
from quant_server.db.data_services.stock_minutes_service import StockMinutesService
from quant_server.db.data_services.stock_moneyflow_service import StockMoneyflowService
from quant_server.db.data_services.stock_monthly_service import StockMonthlyService
from quant_server.db.data_services.stock_signal_service import StockSignalService
from quant_server.db.data_services.stock_weekly_service import StockWeeklyService
from quant_server.db.data_services.trade_calendar_service import TradeCalendarService

logger = logging.getLogger('data_service')


class DataService:
    """统一数据服务门面类"""

    def __init__(self, session: Session):
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

        # 交易服务
        self.trade_calendar = TradeCalendarService(session)
        self.stock_signals = StockSignalService(session)
        self.baskets = BasketService(session)
        self.basket_items = BasketItemService(session)