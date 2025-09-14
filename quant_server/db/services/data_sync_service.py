# data_sync_service.py
import os
from asyncio import as_completed
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, Any, List
import time
import logging
import schedule

from sqlalchemy.orm import Session
from sqlalchemy.sql.functions import random

from quant_server.db import get_db_session
from ..data_service import DataService
from ..sources.tushare_source import TushareSource

logger = logging.getLogger(__name__)


def get_supported_data_types() -> Dict[str, Any]:
    """获取支持的数据类型列表"""
    return {
        "stock_basic": "股票基本信息",
        "stock_company": "上市公司信息",
        "stk_managers": "上市公司管理层信息",
        "stk_rewards": "管理层薪酬和持股信息",
        "daily": "日线数据",
        "weekly": "周线数据",
        "monthly": "月线数据",
        "adj_factor": "复权因子数据",
        "daily_basic": "每日指标数据",
        "moneyflow": "资金流向数据",
        "trade_calendar": "交易日历",
        "fund_basic": "基金基本信息",
        "fund_daily": "基金日线行情",
        "index_weight": "指数成分股",
        "daily_limit": "每日涨跌停价格"
    }


def _get_test_data(data_type: str, **kwargs) -> List[Dict]:
    """生成测试数据"""
    logger.info(f"使用测试数据模拟 {data_type}")

    # 根据数据类型返回不同的测试数据
    if data_type == "stock_basic":
        return [
            {"ts_code": "000001.SZ", "symbol": "000001", "name": "平安银行", "area": "深圳", "industry": "银行",
             "list_date": "19910403", "market": "主板"},
            {"ts_code": "000002.SZ", "symbol": "000002", "name": "万科A", "area": "深圳", "industry": "全国地产",
             "list_date": "19910129", "market": "主板"},
            {"ts_code": "000004.SZ", "symbol": "000004", "name": "国农科技", "area": "深圳", "industry": "生物制药",
             "list_date": "19910114", "market": "主板"},
            {"ts_code": "000005.SZ", "symbol": "000005", "name": "世纪星源", "area": "深圳", "industry": "房产服务",
             "list_date": "19901210", "market": "主板"},
            {"ts_code": "000006.SZ", "symbol": "000006", "name": "深振业A", "area": "深圳", "industry": "区域地产",
             "list_date": "19920427", "market": "主板"},
            {"ts_code": "000007.SZ", "symbol": "000007", "name": "全新好", "area": "深圳", "industry": "酒店餐饮",
             "list_date": "19920413", "market": "主板"},
            {"ts_code": "000008.SZ", "symbol": "000008", "name": "神州高铁", "area": "北京", "industry": "运输设备",
             "list_date": "19920507", "market": "主板"},
            {"ts_code": "000009.SZ", "symbol": "000009", "name": "中国宝安", "area": "深圳", "industry": "综合类",
             "list_date": "19910625", "market": "主板"},
            {"ts_code": "000010.SZ", "symbol": "000010", "name": "美丽生态", "area": "深圳", "industry": "建筑施工",
             "list_date": "19951027", "market": "主板"},
            {"ts_code": "000011.SZ", "symbol": "000011", "name": "深物业A", "area": "深圳", "industry": "区域地产",
             "list_date": "19920330", "market": "主板"},
            {"ts_code": "000012.SZ", "symbol": "000012", "name": "南玻A", "area": "深圳", "industry": "玻璃",
             "list_date": "19920228", "market": "主板"},
            {"ts_code": "000014.SZ", "symbol": "000014", "name": "沙河股份", "area": "深圳", "industry": "全国地产",
             "list_date": "19920602", "market": "主板"},
            {"ts_code": "000016.SZ", "symbol": "000016", "name": "深康佳A", "area": "深圳", "industry": "家用电器",
             "list_date": "19920327", "market": "主板"},
            {"ts_code": "000017.SZ", "symbol": "000017", "name": "深中华A", "area": "深圳", "industry": "文教休闲",
             "list_date": "19920331", "market": "主板"},
            {"ts_code": "000018.SZ", "symbol": "000018", "name": "神州长城", "area": "深圳", "industry": "装修装饰",
             "list_date": "19920616", "market": "主板"},
            {"ts_code": "000019.SZ", "symbol": "000019", "name": "深深宝A", "area": "深圳", "industry": "软饮料",
             "list_date": "19921012", "market": "主板"},
            {"ts_code": "000020.SZ", "symbol": "000020", "name": "深华发A", "area": "深圳", "industry": "元器件",
             "list_date": "19920428", "market": "主板"},
            {"ts_code": "000021.SZ", "symbol": "000021", "name": "深科技", "area": "深圳", "industry": "电脑设备",
             "list_date": "19940202", "market": "主板"},
            {"ts_code": "000022.SZ", "symbol": "000022", "name": "深赤湾A", "area": "深圳", "industry": "港口",
             "list_date": "19930505", "market": "主板"},
            {"ts_code": "000023.SZ", "symbol": "000023", "name": "深天地A", "area": "深圳", "industry": "其他建材",
             "list_date": "19930429", "market": "主板"},
            {"ts_code": "000025.SZ", "symbol": "000025", "name": "特力A", "area": "深圳", "industry": "汽车服务",
             "list_date": "19930621", "market": "主板"}
        ]
    elif data_type == "stock_company":
        return [
            {"ts_code": "000001.SZ", "chairman": "谢永林", "manager": "胡跃飞", "province": "广东", "city": "深圳"},
            {"ts_code": "000002.SZ", "chairman": "郁亮", "manager": "祝九胜", "province": "广东", "city": "深圳"}
        ]
    elif data_type == "daily":
        # 生成近几天的日线测试数据
        dates = []
        for i in range(5):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
            dates.append(date)

        result = []
        for ts_code in ["000001.SZ", "000002.SZ"]:
            base_price = 10.0 if ts_code == "000001.SZ" else 20.0
            for i, date in enumerate(dates):
                price_change = random.uniform(-0.5, 0.5)
                result.append({
                    "ts_code": ts_code,
                    "trade_date": date,
                    "open": base_price + price_change,
                    "high": base_price + price_change + random.uniform(0, 1),
                    "low": base_price + price_change - random.uniform(0, 1),
                    "close": base_price + price_change + random.uniform(-0.2, 0.2),
                    "vol": random.randint(100000, 500000),
                    "amount": random.uniform(1000000, 5000000)
                })
        return result
    elif data_type == "weekly":
        # 生成近几周的周线测试数据
        return [
            {"ts_code": "000001.SZ", "trade_date": "20230106", "close": 10.5, "vol": 500000},
            {"ts_code": "000001.SZ", "trade_date": "20230113", "close": 10.8, "vol": 520000}
        ]
    elif data_type == "monthly":
        # 生成近几月的月线测试数据
        return [
            {"ts_code": "000001.SZ", "trade_date": "202212", "close": 10.2, "vol": 2000000},
            {"ts_code": "000001.SZ", "trade_date": "202301", "close": 10.7, "vol": 2200000}
        ]
    elif data_type == "adj_factor":
        # 生成复权因子测试数据
        return [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "adj_factor": 1.0},
            {"ts_code": "000001.SZ", "trade_date": "20230102", "adj_factor": 1.0}
        ]
    elif data_type == "daily_basic":
        # 生成每日指标测试数据
        return [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "pe": 8.5, "pb": 0.9},
            {"ts_code": "000001.SZ", "trade_date": "20230102", "pe": 8.6, "pb": 0.92}
        ]
    elif data_type == "moneyflow":
        # 生成资金流向测试数据
        return [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "buy_sm_vol": 100000, "sell_sm_vol": 80000},
            {"ts_code": "000001.SZ", "trade_date": "20230102", "buy_sm_vol": 120000, "sell_sm_vol": 90000}
        ]
    elif data_type == "trade_cal":
        # 生成交易日历测试数据
        exchange = kwargs.get('exchange', 'SSE')
        return [
            {"exchange": exchange, "cal_date": "20230103", "is_open": 1},
            {"exchange": exchange, "cal_date": "20230104", "is_open": 1}
        ]
    elif data_type == "fund_basic":
        # 生成基金基本信息测试数据
        return [
            {"ts_code": "510300.SH", "name": "沪深300ETF", "market": "E", "fund_type": "ETF"},
            {"ts_code": "510500.SH", "name": "中证500ETF", "market": "E", "fund_type": "ETF"}
        ]
    elif data_type == "stk_managers":
        # 生成上市公司管理层信息测试数据
        return [
            {"ts_code": "000001.SZ", "name": "谢永林", "position": "董事长"},
            {"ts_code": "000001.SZ", "name": "胡跃飞", "position": "行长"}
        ]
    elif data_type == "stk_rewards":
        # 生成管理层薪酬和持股信息测试数据
        return [
            {"ts_code": "000001.SZ", "name": "谢永林", "salary": 5000000, "hold_vol": 100000},
            {"ts_code": "000001.SZ", "name": "胡跃飞", "salary": 4500000, "hold_vol": 80000}
        ]
    elif data_type == "daily_limit":
        # 生成每日涨跌停价格测试数据
        return [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "pre_close": 10.0, "up_limit": 11.0, "down_limit": 9.0},
            {"ts_code": "000001.SZ", "trade_date": "20230102", "pre_close": 10.5, "up_limit": 11.55, "down_limit": 9.45}
        ]
    else:
        return [{"ts_code": "TEST", "data_type": data_type, "test": True}]


class DataSyncService:
    """数据同步服务 - 优化版"""

    def __init__(self, session: Session = None):
        self.is_test_env = os.environ.get('TEST_ENV', 'False').lower() == 'true'
        if not self.is_test_env:
            self.tushare_source = TushareSource()
        # 使用传入的会话或全局会话
        self.session = session or get_db_session()
        # 创建DataService实例来复用已初始化的服务
        self.data_service = DataService(self.session)
        # 线程池执行器，用于并行处理
        self.executor = ThreadPoolExecutor(max_workers=5)

    def _create_sync_task(self, task_type: str, parameters: Dict[str, Any] = None) -> Any:
        """创建同步任务记录"""
        task_data = {
            "task_type": task_type,
            "status": "running",
            "start_time": datetime.now(),
            "parameters": parameters or {}
        }
        return self.data_service.data_sync_task.create(task_data)

    def _complete_sync_task(self, task_id: int, total_records: int = 0) -> bool:
        """完成同步任务"""
        return self.data_service.data_sync_task.complete_task(task_id, total_records) is not None

    def _fail_sync_task(self, task_id: int, error_message: str) -> bool:
        """标记同步任务失败"""
        return self.data_service.data_sync_task.fail_task(task_id, error_message) is not None

    def sync_stock_basic(self, exchange: str = '', list_status: str = 'L') -> Dict[str, Any]:
        """同步股票基本信息"""
        task = self._create_sync_task("stock_basic", {"exchange": exchange, "list_status": list_status})
        logger.info("开始同步股票基本信息...")
        try:
            if self.is_test_env:
                data = _get_test_data("stock_basic", exchange=exchange, list_status=list_status)
            else:
                data = self.tushare_source.get_stock_basic(exchange=exchange, list_status=list_status)

            result = self.data_service.stock_basic.batch_create(data)
            logger.info(f"股票基本信息同步完成，共处理{len(result)}条记录")

            # 更新任务状态
            self._complete_sync_task(task.id, len(result))

            return {"success": True, "count": len(result), "data": result[:10]}  # 只返回前10条作为示例
        except Exception as e:
            logger.error(f"股票基本信息同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_stock_company(self, exchange: str = '') -> Dict[str, Any]:
        """同步上市公司信息"""
        task = self._create_sync_task("stock_company", {"exchange": exchange})
        logger.info("开始同步上市公司信息...")
        try:
            if self.is_test_env:
                data = _get_test_data("stock_company", exchange=exchange)
            else:
                data = self.tushare_source.get_stock_company(exchange=exchange)

            result = self.data_service.stock_company.batch_create(data)
            logger.info(f"上市公司信息同步完成，共处理{len(result)}条记录")

            self._complete_sync_task(task.id, len(result))
            return {"success": True, "count": len(result), "data": result[:10]}
        except Exception as e:
            logger.error(f"上市公司信息同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_stk_managers(self, ts_code: str = '', ann_date: str = '') -> Dict[str, Any]:
        """同步上市公司管理层信息"""
        task = self._create_sync_task("stk_managers", {"ts_code": ts_code, "ann_date": ann_date})
        logger.info("开始同步上市公司管理层信息...")
        try:
            if self.is_test_env:
                data = _get_test_data("stk_managers", ts_code=ts_code, ann_date=ann_date)
            else:
                data = self.tushare_source.get_stk_managers(ts_code=ts_code, ann_date=ann_date)

            result = self.data_service.stk_managers.batch_create(data)
            logger.info(f"上市公司管理层信息同步完成，共处理{len(result)}条记录")

            self._complete_sync_task(task.id, len(result))
            return {"success": True, "count": len(result), "data": result[:10]}
        except Exception as e:
            logger.error(f"上市公司管理层信息同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_stk_rewards(self, ts_code: str = '', end_date: str = '') -> Dict[str, Any]:
        """同步管理层薪酬和持股信息"""
        task = self._create_sync_task("stk_rewards", {"ts_code": ts_code, "end_date": end_date})
        logger.info("开始同步管理层薪酬和持股信息...")
        try:
            if self.is_test_env:
                data = _get_test_data("stk_rewards", ts_code=ts_code, end_date=end_date)
            else:
                data = self.tushare_source.get_stk_rewards(ts_code=ts_code, end_date=end_date)

            result = self.data_service.stk_rewards.batch_create(data)
            logger.info(f"管理层薪酬和持股信息同步完成，共处理{len(result)}条记录")

            self._complete_sync_task(task.id, len(result))
            return {"success": True, "count": len(result), "data": result[:10]}
        except Exception as e:
            logger.error(f"管理层薪酬和持股信息同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_daily_limit_data(self, days: int = 30, stock_codes: List[str] = None,
                              batch_size: int = 100) -> Dict[str, Any]:
        """同步每日涨跌停价格数据"""
        task = self._create_sync_task("daily_limit",
                                      {"days": days, "stock_codes": stock_codes, "batch_size": batch_size})
        logger.info("开始同步每日涨跌停价格数据...")
        try:
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

            # 获取所有股票代码或指定股票代码
            if not stock_codes:
                if self.is_test_env:
                    stock_codes = ["000001.SZ", "000002.SZ"]  # 测试环境使用固定代码
                else:
                    stock_codes = [stock.ts_code for stock in self.data_service.stock_basic.list_active_stocks()]

            total_count = len(stock_codes)
            results = []
            failed_codes = []

            # 如果是测试环境，简化处理
            if self.is_test_env:
                logger.info("测试环境: 模拟同步每日涨跌停价格数据")
                try:
                    test_data = _get_test_data("daily_limit")
                    if test_data:
                        results.extend(self.data_service.stock_daily_limit.batch_create(test_data))
                    logger.info(f"每日涨跌停价格数据同步完成，共处理{len(results)}条记录")
                    self._complete_sync_task(task.id, len(results))
                    return {
                        "success": True,
                        "count": len(results),
                        "failed_count": 0,
                        "failed_codes": []
                    }
                except Exception as e:
                    logger.error(f"测试环境每日涨跌停价格数据同步失败: {str(e)}")
                    self._fail_sync_task(task.id, str(e))
                    return {
                        "success": False,
                        "count": 0,
                        "failed_count": total_count,
                        "failed_codes": stock_codes[:20],
                        "error": str(e)
                    }

            # 生产环境使用线程池并行处理
            futures = {}
            for i in range(0, total_count, batch_size):
                batch_codes = stock_codes[i:i + batch_size]
                # todo
                future = self.executor.submit(self._process_daily_limit_batch, batch_codes, start_date, end_date)
                futures[future] = batch_codes

            # 处理完成的任务
            completed = 0
            for future in as_completed(futures):
                batch_codes = futures[future]
                try:
                    batch_result = future.result()
                    results.extend(batch_result["success"])
                    failed_codes.extend(batch_result["failed"])
                    completed += len(batch_codes)

                    # 记录进度
                    progress = min(100, int(completed / total_count * 100))
                    logger.info(f"每日涨跌停价格数据同步进度: {progress}%")

                except Exception as e:
                    logger.error(f"处理批次失败: {str(e)}")
                    failed_codes.extend(batch_codes)

            logger.info(f"每日涨跌停价格数据同步完成，成功: {len(results)}条，失败: {len(failed_codes)}只股票")
            self._complete_sync_task(task.id, len(results))
            return {
                "success": True,
                "count": len(results),
                "failed_count": len(failed_codes),
                "failed_codes": failed_codes[:20]  # 只返回前20个失败的代码
            }
        except Exception as e:
            logger.error(f"每日涨跌停价格数据同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def _process_daily_limit_batch(self, batch_codes: List[str], start_date: str, end_date: str) -> Dict[str, Any]:
        """处理一批股票的每日涨跌停价格数据"""
        success_results = []
        failed_codes = []

        for code in batch_codes:
            try:
                data = self.tushare_source.get_daily_limit(
                    ts_code=code, start_date=start_date, end_date=end_date
                )
                if data:
                    success_results.extend(self.data_service.stock_daily_limit.batch_create(data))

                # 控制请求频率
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"股票{code}的每日涨跌停价格数据同步失败: {str(e)}")
                failed_codes.append(code)

        return {"success": success_results, "failed": failed_codes}

    def _sync_stock_data_parallel(self, sync_func, data_type: str, days: int = 30,
                                  stock_codes: List[str] = None, batch_size: int = 100) -> Dict[str, Any]:
        """并行同步股票数据通用方法"""
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 获取所有股票代码或指定股票代码
        if not stock_codes:
            if self.is_test_env:
                stock_codes = ["000001.SZ", "000002.SZ"]  # 测试环境使用固定代码
            else:
                stock_codes = [stock.ts_code for stock in self.data_service.stock_basic.list_active_stocks()]

        total_count = len(stock_codes)
        results = []
        failed_codes = []

        # 如果是测试环境，简化处理
        if self.is_test_env:
            logger.info(f"测试环境: 模拟同步{data_type}数据")
            try:
                # 直接生成测试数据并保存
                test_data = _get_test_data(data_type)
                if test_data:
                    # 根据数据类型调用不同的服务保存数据
                    if data_type == "daily":
                        results.extend(self.data_service.stock_daily.batch_create(test_data))
                    elif data_type == "weekly":
                        results.extend(self.data_service.stock_weekly.batch_create(test_data))
                    elif data_type == "monthly":
                        results.extend(self.data_service.stock_monthly.batch_create(test_data))
                    elif data_type == "adj_factor":
                        results.extend(self.data_service.stock_adj_factor.batch_create(test_data))
                    elif data_type == "daily_basic":
                        results.extend(self.data_service.stock_daily_basic.batch_create(test_data))
                    elif data_type == "moneyflow":
                        results.extend(self.data_service.stock_moneyflow.batch_create(test_data))

                logger.info(f"{data_type}数据同步完成，共处理{len(results)}条记录")
                return {
                    "success": True,
                    "count": len(results),
                    "failed_count": 0,
                    "failed_codes": []
                }
            except Exception as e:
                logger.error(f"测试环境{data_type}数据同步失败: {str(e)}")
                return {
                    "success": False,
                    "count": 0,
                    "failed_count": total_count,
                    "failed_codes": stock_codes[:20],
                    "error": str(e)
                }

        # 生产环境使用线程池并行处理
        futures = {}
        for i in range(0, total_count, batch_size):
            batch_codes = stock_codes[i:i + batch_size]

            # 提交批量任务到线程池
            future = self.executor.submit(self._process_batch, sync_func, batch_codes,
                                          start_date, end_date, data_type)
            futures[future] = batch_codes

        # 处理完成的任务
        completed = 0
        for future in as_completed(futures):
            batch_codes = futures[future]
            try:
                batch_result = future.result()
                results.extend(batch_result["success"])
                failed_codes.extend(batch_result["failed"])
                completed += len(batch_codes)

                # 记录进度
                progress = min(100, int(completed / total_count * 100))
                logger.info(f"{data_type}数据同步进度: {progress}%")

            except Exception as e:
                logger.error(f"处理批次失败: {str(e)}")
                failed_codes.extend(batch_codes)

        logger.info(f"{data_type}数据同步完成，成功: {len(results)}条，失败: {len(failed_codes)}只股票")
        return {
            "success": True,
            "count": len(results),
            "failed_count": len(failed_codes),
            "failed_codes": failed_codes[:20]  # 只返回前20个失败的代码
        }

    def _process_batch(self, sync_func, batch_codes: List[str],
                       start_date: str, end_date: str, data_type: str) -> Dict[str, Any]:
        """处理一批股票数据"""
        success_results = []
        failed_codes = []

        for code in batch_codes:
            try:
                # 根据数据类型调用不同的Tushare方法
                if data_type == "daily":
                    data = self.tushare_source.get_daily(
                        ts_code=code, start_date=start_date, end_date=end_date
                    )
                    if data:
                        success_results.extend(self.data_service.stock_daily.batch_create(data))

                elif data_type == "weekly":
                    data = self.tushare_source.get_weekly(
                        ts_code=code, start_date=start_date, end_date=end_date
                    )
                    if data:
                        success_results.extend(self.data_service.stock_weekly.batch_create(data))

                elif data_type == "monthly":
                    data = self.tushare_source.get_monthly(
                        ts_code=code, start_date=start_date, end_date=end_date
                    )
                    if data:
                        success_results.extend(self.data_service.stock_monthly.batch_create(data))

                elif data_type == "adj_factor":
                    data = self.tushare_source.get_adj_factor(
                        ts_code=code, start_date=start_date, end_date=end_date
                    )
                    if data:
                        success_results.extend(self.data_service.stock_adj_factor.batch_create(data))

                elif data_type == "daily_basic":
                    data = self.tushare_source.get_daily_basic(
                        ts_code=code, start_date=start_date, end_date=end_date
                    )
                    if data:
                        success_results.extend(self.data_service.stock_daily_basic.batch_create(data))

                elif data_type == "moneyflow":
                    data = self.tushare_source.get_moneyflow(
                        ts_code=code, start_date=start_date, end_date=end_date
                    )
                    if data:
                        success_results.extend(self.data_service.stock_moneyflow.batch_create(data))

                # 控制请求频率
                time.sleep(0.05)

            except Exception as e:
                logger.error(f"股票{code}的{data_type}数据同步失败: {str(e)}")
                failed_codes.append(code)

        return {"success": success_results, "failed": failed_codes}

    def sync_daily_data(self, days: int = 30, stock_codes: List[str] = None,
                        batch_size: int = 100) -> Dict[str, Any]:
        """同步日线数据"""
        task = self._create_sync_task("daily", {"days": days, "stock_codes": stock_codes, "batch_size": batch_size})
        logger.info("开始同步日线数据...")
        try:
            result = self._sync_stock_data_parallel(
                self.tushare_source.get_daily, "daily", days, stock_codes, batch_size
            )
            self._complete_sync_task(task.id, result.get('count', 0))
            return result
        except Exception as e:
            logger.error(f"日线数据同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_weekly_data(self, days: int = 30, stock_codes: List[str] = None,
                         batch_size: int = 100) -> Dict[str, Any]:
        """同步周线数据"""
        task = self._create_sync_task("weekly", {"days": days, "stock_codes": stock_codes, "batch_size": batch_size})
        logger.info("开始同步周线数据...")
        try:
            result = self._sync_stock_data_parallel(
                self.tushare_source.get_weekly, "weekly", days, stock_codes, batch_size
            )
            self._complete_sync_task(task.id, result.get('count', 0))
            return result
        except Exception as e:
            logger.error(f"周线数据同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_monthly_data(self, days: int = 30, stock_codes: List[str] = None,
                          batch_size: int = 100) -> Dict[str, Any]:
        """同步月线数据"""
        task = self._create_sync_task("monthly", {"days": days, "stock_codes": stock_codes, "batch_size": batch_size})
        logger.info("开始同步月线数据...")
        try:
            result = self._sync_stock_data_parallel(
                self.tushare_source.get_monthly, "monthly", days, stock_codes, batch_size
            )
            self._complete_sync_task(task.id, result.get('count', 0))
            return result
        except Exception as e:
            logger.error(f"月线数据同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_adj_factor_data(self, days: int = 30, stock_codes: List[str] = None,
                             batch_size: int = 100) -> Dict[str, Any]:
        """同步复权因子数据"""
        task = self._create_sync_task("adj_factor",
                                      {"days": days, "stock_codes": stock_codes, "batch_size": batch_size})
        logger.info("开始同步复权因子数据...")
        try:
            result = self._sync_stock_data_parallel(
                self.tushare_source.get_adj_factor, "adj_factor", days, stock_codes, batch_size
            )
            self._complete_sync_task(task.id, result.get('count', 0))
            return result
        except Exception as e:
            logger.error(f"复权因子数据同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_daily_basic_data(self, days: int = 30, stock_codes: List[str] = None,
                              batch_size: int = 100) -> Dict[str, Any]:
        """同步每日指标数据"""
        task = self._create_sync_task("daily_basic",
                                      {"days": days, "stock_codes": stock_codes, "batch_size": batch_size})
        logger.info("开始同步每日指标数据...")
        try:
            result = self._sync_stock_data_parallel(
                self.tushare_source.get_daily_basic, "daily_basic", days, stock_codes, batch_size
            )
            self._complete_sync_task(task.id, result.get('count', 0))
            return result
        except Exception as e:
            logger.error(f"每日指标数据同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_moneyflow_data(self, days: int = 30, stock_codes: List[str] = None,
                            batch_size: int = 100) -> Dict[str, Any]:
        """同步资金流向数据"""
        task = self._create_sync_task("moneyflow", {"days": days, "stock_codes": stock_codes, "batch_size": batch_size})
        logger.info("开始同步资金流向数据...")
        try:
            result = self._sync_stock_data_parallel(
                self.tushare_source.get_moneyflow, "moneyflow", days, stock_codes, batch_size
            )
            self._complete_sync_task(task.id, result.get('count', 0))
            return result
        except Exception as e:
            logger.error(f"资金流向数据同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_trade_calendar(self, exchanges: List[str] = None,
                            start_date: str = '19900101', end_date: str = '20301231') -> Dict[str, Any]:
        """同步交易日历"""
        task = self._create_sync_task("trade_calendar",
                                      {"exchanges": exchanges, "start_date": start_date, "end_date": end_date})
        logger.info("开始同步交易日历...")
        if not exchanges:
            exchanges = ['SSE', 'SZSE']  # 默认上交所和深交所

        results = []
        for exchange in exchanges:
            try:
                if self.is_test_env:
                    data = _get_test_data("trade_cal", exchange=exchange,
                                          start_date=start_date, end_date=end_date)
                else:
                    data = self.tushare_source.get_trade_cal(
                        exchange=exchange, start_date=start_date, end_date=end_date
                    )

                if data:
                    results.extend(self.data_service.trade_calendar.batch_create(data))
            except Exception as e:
                logger.error(f"交易所{exchange}的交易日历同步失败: {str(e)}")

        logger.info(f"交易日历同步完成，共处理{len(results)}条记录")
        self._complete_sync_task(task.id, len(results))
        return {"success": True, "count": len(results), "data": results[:10]}

    def sync_fund_basic(self, market: str = '') -> Dict[str, Any]:
        """同步基金基本信息"""
        task = self._create_sync_task("fund_basic", {"market": market})
        logger.info("开始同步基金基本信息...")
        try:
            if self.is_test_env:
                data = _get_test_data("fund_basic", market=market)
            else:
                data = self.tushare_source.get_fund_basic(market=market)

            result = self.data_service.etf_basic.batch_create(data)
            logger.info(f"基金基本信息同步完成，共处理{len(result)}条记录")

            self._complete_sync_task(task.id, len(result))
            return {"success": True, "count": len(result), "data": result[:10]}
        except Exception as e:
            logger.error(f"基金基本信息同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_fund_daily(self, days: int = 30, ts_codes: List[str] = None) -> Dict[str, Any]:
        """同步基金日线行情"""
        task = self._create_sync_task("fund_daily", {"days": days, "ts_codes": ts_codes})
        logger.info("开始同步基金日线行情...")
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

        # 获取所有基金代码或指定基金代码
        if not ts_codes:
            # 这里需要实现获取所有基金代码的逻辑
            ts_codes = []

        results = []
        failed_codes = []

        for code in ts_codes:
            try:
                data = self.tushare_source.get_fund_daily(
                    ts_code=code, start_date=start_date, end_date=end_date
                )
                if data:
                    results.extend(self.data_service.etf_daily.batch_create(data))

                # 控制请求频率
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"基金{code}日线行情同步失败: {str(e)}")
                failed_codes.append(code)

        logger.info(f"基金日线行情同步完成，成功: {len(results)}条，失败: {len(failed_codes)}只基金")
        self._complete_sync_task(task.id, len(results))
        return {
            "success": True,
            "count": len(results),
            "failed_count": len(failed_codes),
            "failed_codes": failed_codes[:10]
        }

    def sync_index_weight(self, index_code: str = '', trade_date: str = '') -> Dict[str, Any]:
        """同步指数成分股"""
        task = self._create_sync_task("index_weight", {"index_code": index_code, "trade_date": trade_date})
        logger.info("开始同步指数成分股...")
        try:
            if not trade_date:
                trade_date = datetime.now().strftime('%Y%m%d')
            if self.is_test_env:
                data = _get_test_data("index_weight", index_code=index_code, trade_date=trade_date)
            else:
                data = self.tushare_source.get_index_weight(index_code=index_code, trade_date=trade_date)
            # todo  这里需要创建对应的Service来处理指数成分股数据
            # result = self.index_weight_service.batch_create(data)
            result = data  # 暂时直接返回数据

            logger.info(f"指数成分股同步完成，共处理{len(result)}条记录")
            self._complete_sync_task(task.id, len(result))
            return {"success": True, "count": len(result), "data": result[:10]}
        except Exception as e:
            logger.error(f"指数成分股同步失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def sync_all_data(self, days: int = 30, batch_size: int = 100) -> Dict[str, Any]:
        """同步所有数据"""
        task = self._create_sync_task("all", {"days": days, "batch_size": batch_size})
        logger.info("开始同步所有数据...")
        try:
            if self.is_test_env:
                logger.info("测试环境: 使用模拟数据验证流程")

            results = {
                "stock_basic": self.sync_stock_basic(),
                "stock_company": self.sync_stock_company(),
                "stk_managers": self.sync_stk_managers(),
                "stk_rewards": self.sync_stk_rewards(),
                "trade_calendar": self.sync_trade_calendar(),
                "daily": self.sync_daily_data(days=days, batch_size=batch_size),
                "weekly": self.sync_weekly_data(days=days, batch_size=batch_size),
                "monthly": self.sync_monthly_data(days=days, batch_size=batch_size),
                "adj_factor": self.sync_adj_factor_data(days=days, batch_size=batch_size),
                "daily_basic": self.sync_daily_basic_data(days=days, batch_size=batch_size),
                "moneyflow": self.sync_moneyflow_data(days=days, batch_size=batch_size),
                "daily_limit": self.sync_daily_limit_data(days=days, batch_size=batch_size),
                "fund_basic": self.sync_fund_basic(),
                "fund_daily": self.sync_fund_daily(days=days),
                "index_weight": self.sync_index_weight()
            }

            # 计算总记录数
            total_records = 0
            for key, value in results.items():
                if isinstance(value, dict) and value.get("success") and "count" in value:
                    total_records += value["count"]

            logger.info("所有数据同步完成")
            self._complete_sync_task(task.id, total_records)
            return {"success": True, "results": results, "total_records": total_records}
        except Exception as e:
            logger.error(f"同步所有数据失败: {str(e)}")
            self._fail_sync_task(task.id, str(e))
            return {"success": False, "error": str(e)}

    def schedule_sync(self, interval_hours: int = 24):
        """定时同步数据"""

        def job():
            logger.info(f"{datetime.now()}: 开始定时数据同步")
            self.sync_all_data()
            logger.info(f"{datetime.now()}: 定时数据同步完成")

        # 每天定时执行
        schedule.every(interval_hours).hours.do(job)

        logger.info(f"数据同步服务已启动，每{interval_hours}小时执行一次")
        while True:
            schedule.run_pending()
            time.sleep(1)