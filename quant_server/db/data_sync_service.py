# data_sync_service.py
from datetime import datetime, timedelta
from typing import  Dict, Any
import time

from quant_server.data_sources.tushare_source import TushareSource
from quant_server.db.data_services.etf_basic_service import EtfBasicService
from quant_server.db.data_services.etf_daily_service import EtfDailyService
from quant_server.db.data_services.fund_adjFactor_service import FundAdjFactorService
from quant_server.db.data_services.stk_manager_service import StkManagerService
from quant_server.db.data_services.stk_reward_service import StkRewardService
from quant_server.db.data_services.stock_adjFactor_aervice import StockAdjFactorService
from quant_server.db.data_services.stock_basic_service import StockBasicService
from quant_server.db.data_services.stock_company_service import StockCompanyService
from quant_server.db.data_services.stock_daily_basic_service import StockDailyBasicService
from quant_server.db.data_services.stock_daily_limit_service import StockDailyLimitService
from quant_server.db.data_services.stock_daily_service import StockDailyService
from quant_server.db.data_services.stock_moneyflow_service import StockMoneyflowService
from quant_server.db.data_services.stock_monthly_service import StockMonthlyService
from quant_server.db.data_services.stock_weekly_service import StockWeeklyService
from quant_server.db.data_services.trade_calendar_service import TradeCalendarService


class DataSyncService:
    """数据同步服务"""

    def __init__(self, tushare_config: Dict[str, Any]):
        self.tushare_source = TushareSource(tushare_config)
        self.stock_basic_service = StockBasicService()
        self.stock_company_service = StockCompanyService()
        self.stk_manager_service = StkManagerService()
        self.stk_reward_service = StkRewardService()
        self.stock_daily_service = StockDailyService()
        self.stock_weekly_service = StockWeeklyService()
        self.stock_monthly_service = StockMonthlyService()
        self.stock_adj_factor_service = StockAdjFactorService()
        self.stock_daily_basic_service = StockDailyBasicService()
        self.stock_daily_limit_service = StockDailyLimitService()
        self.stock_moneyflow_service = StockMoneyflowService()
        self.etf_basic_service = EtfBasicService()
        self.etf_daily_service = EtfDailyService()
        self.fund_adj_factor_service = FundAdjFactorService()
        self.trade_calendar_service = TradeCalendarService()

    def sync_stock_basic(self):
        """同步股票基本信息"""
        print("开始同步股票基本信息...")
        data = self.tushare_source.get_stock_basic()
        result = self.stock_basic_service.batch_create(data)
        print(f"股票基本信息同步完成，共处理{len(result)}条记录")
        return result

    def sync_stock_company(self):
        """同步上市公司信息"""
        print("开始同步上市公司信息...")
        data = self.tushare_source.get_stock_company()
        result = self.stock_company_service.batch_create(data)
        print(f"上市公司信息同步完成，共处理{len(result)}条记录")
        return result

    def sync_daily_data(self, days: int = 30):
        """同步日线数据"""
        print("开始同步日线数据...")
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 获取所有股票代码
        stock_codes = [stock.ts_code for stock in self.stock_basic_service.list_active_stocks()]

        results = []
        total_count = len(stock_codes)
        for i, code in enumerate(stock_codes):
            if i % 100 == 0:
                print(f"正在处理第{i}/{total_count}只股票...")

            data = self.tushare_source.get_daily(
                ts_code=code,
                start_date=start_date,
                end_date=end_date
            )
            if data:
                results.extend(self.stock_daily_service.batch_create(data))

            # 避免请求过于频繁
            time.sleep(0.1)

        print(f"日线数据同步完成，共处理{len(results)}条记录")
        return results

    def sync_moneyflow_data(self, days: int = 30):
        """同步资金流向数据"""
        print("开始同步资金流向数据...")
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 获取所有股票代码
        stock_codes = [stock.ts_code for stock in self.stock_basic_service.list_active_stocks()]

        results = []
        total_count = len(stock_codes)
        for i, code in enumerate(stock_codes):
            if i % 100 == 0:
                print(f"正在处理第{i}/{total_count}只股票...")

            data = self.tushare_source.get_moneyflow(
                ts_code=code,
                start_date=start_date,
                end_date=end_date
            )
            if data:
                results.extend(self.stock_moneyflow_service.batch_create(data))

            # 避免请求过于频繁
            time.sleep(0.1)

        print(f"资金流向数据同步完成，共处理{len(results)}条记录")
        return results

    def sync_daily_basic_data(self, days: int = 30):
        """同步每日指标数据"""
        print("开始同步每日指标数据...")
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 获取所有股票代码
        stock_codes = [stock.ts_code for stock in self.stock_basic_service.list_active_stocks()]

        results = []
        total_count = len(stock_codes)
        for i, code in enumerate(stock_codes):
            if i % 100 == 0:
                print(f"正在处理第{i}/{total_count}只股票...")

            data = self.tushare_source.get_daily_basic(
                ts_code=code,
                start_date=start_date,
                end_date=end_date
            )
            if data:
                results.extend(self.stock_daily_basic_service.batch_create(data))

            # 避免请求过于频繁
            time.sleep(0.1)

        print(f"每日指标数据同步完成，共处理{len(results)}条记录")
        return results

    def sync_adj_factor_data(self, days: int = 30):
        """同步复权因子数据"""
        print("开始同步复权因子数据...")
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 获取所有股票代码
        stock_codes = [stock.ts_code for stock in self.stock_basic_service.list_active_stocks()]

        results = []
        total_count = len(stock_codes)
        for i, code in enumerate(stock_codes):
            if i % 100 == 0:
                print(f"正在处理第{i}/{total_count}只股票...")

            data = self.tushare_source.get_adj_factor(
                ts_code=code,
                start_date=start_date,
                end_date=end_date
            )
            if data:
                results.extend(self.stock_adj_factor_service.batch_create(data))

            # 避免请求过于频繁
            time.sleep(0.1)

        print(f"复权因子数据同步完成，共处理{len(results)}条记录")
        return results

    def sync_trade_calendar(self, start_date: str = '19900101', end_date: str = '20301231'):
        """同步交易日历"""
        print("开始同步交易日历...")
        exchanges = ['SSE', 'SZSE']  # 上交所和深交所

        results = []
        for exchange in exchanges:
            data = self.tushare_source.get_trade_cal(
                exchange=exchange,
                start_date=start_date,
                end_date=end_date
            )
            if data:
                results.extend(self.trade_calendar_service.batch_create(data))

        print(f"交易日历同步完成，共处理{len(results)}条记录")
        return results

    def sync_all_data(self):
        """同步所有数据"""
        print("开始同步所有数据...")

        # 同步基础数据
        self.sync_stock_basic()
        self.sync_stock_company()
        self.sync_trade_calendar()

        # 同步行情数据
        self.sync_daily_data(30)  # 同步最近30天的数据
        self.sync_moneyflow_data(30)
        self.sync_daily_basic_data(30)
        self.sync_adj_factor_data(30)

        print("所有数据同步完成")

    def schedule_sync(self, interval_hours: int = 24):
        """定时同步数据"""
        import schedule
        import time

        def job():
            print(f"{datetime.now()}: 开始定时数据同步")
            self.sync_all_data()
            print(f"{datetime.now()}: 定时数据同步完成")

        # 每天定时执行
        schedule.every(interval_hours).hours.do(job)

        print(f"数据同步服务已启动，每{interval_hours}小时执行一次")
        while True:
            schedule.run_pending()
            time.sleep(1)