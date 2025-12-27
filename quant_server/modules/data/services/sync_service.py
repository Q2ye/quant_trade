# data_sync/services/sync_service.py
"""
重构后的数据同步服务 - 核心业务逻辑
优化点：
1. 使用策略模式减少重复代码
2. 引入数据清洗服务
3. 优化并行处理
4. 增强错误处理和日志
"""
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

from sqlalchemy.orm import Session

from quant_server.db import get_db_session
from quant_server.db.data_service import DataService
from quant_server.shared.sources.tushare_source import TushareSource
from quant_server.modules.data.managers.status_manager import SyncStatusManager, SyncTask
from .clean_service import DataCleanService

logger = logging.getLogger(__name__)


class DataSyncStrategy:
	"""数据同步策略基类"""

	def __init__ (self, sync_service: 'DataSyncService'):
		self.sync_service = sync_service

	def sync (self, **kwargs) -> Dict[str, Any]:
		"""执行同步"""
		raise NotImplementedError


class BatchSyncStrategy(DataSyncStrategy):
	"""批量同步策略"""

	def sync (self, codes: List[str], start_date: str, end_date: str,
	          batch_size: int = 100, **kwargs) -> Dict[str, Any]:
		"""批量同步实现"""
		results = []
		failed_codes = []

		# 分批处理
		for i in range(0, len(codes), batch_size):
			batch_codes = codes[i:i + batch_size]
			batch_result = self._process_batch(batch_codes, start_date, end_date, **kwargs)

			results.extend(batch_result.get("success", []))
			failed_codes.extend(batch_result.get("failed", []))

			# 进度更新
			progress = min(100, int((i + len(batch_codes)) / len(codes) * 100))
			logger.info(f"批量同步进度: {progress}%")

		return {
			"success": True,
			"count": len(results),
			"failed_count": len(failed_codes),
			"failed_codes": failed_codes[:20]
		}

	def _process_batch (self, batch_codes: List[str], start_date: str,
	                    end_date: str, **kwargs) -> Dict[str, Any]:
		"""处理单批次数据"""
		raise NotImplementedError


class DataSyncService:
	"""重构后的数据同步服务"""

	def __init__ (self, session: Session = None, enable_clean: bool = True):
		# 环境配置
		self.is_test_env = os.environ.get('TEST_ENV', 'False').lower() == 'true'

		# 数据库和外部服务
		self.session = session or get_db_session()
		self.data_service = DataService(self.session)

		if not self.is_test_env:
			self.tushare_source = TushareSource()

		# 新增服务
		self.status_manager = SyncStatusManager()
		self.clean_service = DataCleanService() if enable_clean else None

		# 线程池
		self.executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="data_sync")

		# 配置映射
		self._init_config_mappings()

	def _init_config_mappings (self):
		"""初始化配置映射"""
		# 数据类型到Tushare方法的映射
		self.tushare_methods = {
			"stock_basic": self.tushare_source.get_stock_basic if not self.is_test_env else None,
			"daily": self.tushare_source.get_daily if not self.is_test_env else None,
			"weekly": self.tushare_source.get_weekly if not self.is_test_env else None,
			"monthly": self.tushare_source.get_monthly if not self.is_test_env else None,
			"adj_factor": self.tushare_source.get_adj_factor if not self.is_test_env else None,
			"daily_basic": self.tushare_source.get_daily_basic if not self.is_test_env else None,
			"moneyflow": self.tushare_source.get_moneyflow if not self.is_test_env else None,
			"daily_limit": self.tushare_source.get_daily_limit if not self.is_test_env else None,
			"fund_basic": self.tushare_source.get_fund_basic if not self.is_test_env else None,
			"fund_daily": self.tushare_source.get_fund_daily if not self.is_test_env else None,
			"index_weight": self.tushare_source.get_index_weight if not self.is_test_env else None,
			"stk_managers": self.tushare_source.get_stk_managers if not self.is_test_env else None,
			"stk_rewards": self.tushare_source.get_stk_rewards if not self.is_test_env else None,
			"trade_calendar": self.tushare_source.get_trade_cal if not self.is_test_env else None,
		}

		# 数据类型到DataService方法的映射
		self.data_service_methods = {
			"stock_basic": self.data_service.stock_basic.batch_create,
			"daily": self.data_service.stock_daily.batch_create,
			"weekly": self.data_service.stock_weekly.batch_create,
			"monthly": self.data_service.stock_monthly.batch_create,
			"adj_factor": self.data_service.stock_adj_factor.batch_create,
			"daily_basic": self.data_service.stock_daily_basic.batch_create,
			"moneyflow": self.data_service.stock_moneyflow.batch_create,
			"daily_limit": self.data_service.stock_daily_limit.batch_create,
			"fund_basic": self.data_service.etf_basic.batch_create,
			"fund_daily": self.data_service.etf_daily.batch_create,
			"stk_managers": self.data_service.stk_managers.batch_create,
			"stk_rewards": self.data_service.stk_rewards.batch_create,
			"trade_calendar": self.data_service.trade_calendar.batch_create,
		}

	def create_sync_task (self, task_type: str, parameters: Dict[str, Any]) -> Optional[SyncTask]:
		"""创建同步任务记录"""
		try:
			task_data = {
				"task_type": task_type,
				"status": "running",
				"start_time": datetime.now(),
				"parameters": parameters
			}
			return self.data_service.data_sync_task.create(task_data)
		except Exception as e:
			logger.error(f"创建同步任务失败: {str(e)}")
			return None

	def _get_stock_codes (self, specified_codes: Optional[List[str]] = None) -> List[str]:
		"""获取股票代码列表"""
		if specified_codes:
			return specified_codes

		if self.is_test_env:
			return ["000001.SZ", "000002.SZ"]

		try:
			stocks = self.data_service.stock_basic.list_active_stocks()
			return [stock.ts_code for stock in stocks]
		except Exception as e:
			logger.error(f"获取股票列表失败: {str(e)}")
			return []

	def sync_with_retry (self, data_type: str, sync_func: Callable,
	                     max_retries: int = 3, **kwargs) -> Dict[str, Any]:
		"""
		带重试机制的同步

		Args:
			data_type: 数据类型
			sync_func: 同步函数
			max_retries: 最大重试次数
			**kwargs: 同步参数

		Returns:
			同步结果
		"""
		for attempt in range(max_retries):
			try:
				return sync_func(**kwargs)
			except Exception as e:
				if attempt == max_retries - 1:
					logger.error(f"{data_type}同步失败，已达到最大重试次数: {str(e)}")
					return {"success": False, "error": str(e)}

				wait_time = 2 ** attempt  # 指数退避
				logger.warning(f"{data_type}同步失败，{wait_time}秒后重试: {str(e)}")
				time.sleep(wait_time)

		return {"success": False, "error": "未知错误"}

	def _process_data (self, data_type: str, raw_data: List[Dict],
	                   clean_config: Optional[Dict] = None) -> List[Dict]:
		"""
		处理数据：清洗 -> 保存

		Args:
			data_type: 数据类型
			raw_data: 原始数据
			clean_config: 清洗配置

		Returns:
			处理后的数据
		"""
		if not raw_data:
			return []

		# 1. 数据清洗
		cleaned_data = raw_data
		if self.clean_service:
			try:
				cleaned_data = self.clean_service.clean_data(
					data_type, raw_data, **(clean_config or {})
				)
			except Exception as e:
				logger.error(f"{data_type}数据清洗失败: {str(e)}")
			# 清洗失败时使用原始数据

		# 2. 数据保存
		try:
			save_method = self.data_service_methods.get(data_type)
			if save_method:
				return save_method(cleaned_data)
			else:
				logger.warning(f"未找到{data_type}的数据保存方法")
				return cleaned_data
		except Exception as e:
			logger.error(f"{data_type}数据保存失败: {str(e)}")
			return []

	# ========== 具体同步方法 ==========

	def sync_stock_basic (self, exchange: str = '', list_status: str = 'L',
	                      clean_config: Optional[Dict] = None) -> Dict[str, Any]:
		"""同步股票基本信息"""
		logger.info(f"开始同步股票基本信息...")

		try:
			# 获取数据
			if self.is_test_env:
				from .test_data import get_test_data
				data = get_test_data("stock_basic")
			else:
				data = self.tushare_source.get_stock_basic(
					exchange=exchange, list_status=list_status
				)

			# 处理数据
			result = self._process_data("stock_basic", data, clean_config)

			logger.info(f"股票基本信息同步完成，共处理{len(result)}条记录")
			return {"success": True, "count": len(result)}

		except Exception as e:
			logger.error(f"股票基本信息同步失败: {str(e)}")
			return {"success": False, "error": str(e)}

	def sync_daily_data (self, days: int = 30, stock_codes: Optional[List[str]] = None,
	                     batch_size: int = 100, clean_config: Optional[Dict] = None) -> Dict[str, Any]:
		"""同步日线数据"""
		return self._sync_period_data("daily", days, stock_codes, batch_size, clean_config)

	def sync_weekly_data (self, days: int = 30, stock_codes: Optional[List[str]] = None,
	                      batch_size: int = 100, clean_config: Optional[Dict] = None) -> Dict[str, Any]:
		"""同步周线数据"""
		return self._sync_period_data("weekly", days, stock_codes, batch_size, clean_config)

	def sync_monthly_data (self, days: int = 30, stock_codes: Optional[List[str]] = None,
	                       batch_size: int = 100, clean_config: Optional[Dict] = None) -> Dict[str, Any]:
		"""同步月线数据"""
		return self._sync_period_data("monthly", days, stock_codes, batch_size, clean_config)

	def _sync_period_data (self, data_type: str, days: int, stock_codes: Optional[List[str]],
	                       batch_size: int, clean_config: Optional[Dict]) -> Dict[str, Any]:
		"""同步周期数据通用方法"""
		logger.info(f"开始同步{data_type}数据...")

		try:
			# 获取日期范围
			end_date = datetime.now().strftime('%Y%m%d')
			start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

			# 获取股票代码
			codes = self._get_stock_codes(stock_codes)
			if not codes:
				return {"success": False, "error": "未找到有效的股票代码"}

			# 并行处理
			results = []
			failed_codes = []
			total_batches = (len(codes) + batch_size - 1) // batch_size

			futures = {}
			for i in range(0, len(codes), batch_size):
				batch_codes = codes[i:i + batch_size]
				future = self.executor.submit(
					self._process_batch_period_data,
					data_type, batch_codes, start_date, end_date, clean_config
				)
				futures[future] = batch_codes

			# 收集结果
			for future in as_completed(futures):
				batch_codes = futures[future]
				try:
					batch_result = future.result()
					results.extend(batch_result["success"])
					failed_codes.extend(batch_result["failed"])
				except Exception as e:
					logger.error(f"处理批次失败: {str(e)}")
					failed_codes.extend(batch_codes)

			logger.info(f"{data_type}数据同步完成，成功: {len(results)}条，失败: {len(failed_codes)}只代码")
			return {
				"success": True,
				"count": len(results),
				"failed_count": len(failed_codes),
				"failed_codes": failed_codes[:20]
			}

		except Exception as e:
			logger.error(f"{data_type}数据同步失败: {str(e)}")
			return {"success": False, "error": str(e)}

	def _process_batch_period_data (self, data_type: str, batch_codes: List[str],
	                                start_date: str, end_date: str, clean_config: Optional[Dict]) -> Dict[str, Any]:
		"""处理批次周期数据"""
		success_results = []
		failed_codes = []

		tushare_method = self.tushare_methods.get(data_type)
		if not tushare_method:
			return {"success": [], "failed": batch_codes}

		for code in batch_codes:
			try:
				# 获取数据
				data = tushare_method(
					ts_code=code,
					start_date=start_date,
					end_date=end_date
				)

				if data:
					# 处理数据
					processed_data = self._process_data(data_type, data, clean_config)
					success_results.extend(processed_data)

				# 控制请求频率
				time.sleep(0.05)

			except Exception as e:
				logger.error(f"代码{code}的{data_type}数据同步失败: {str(e)}")
				failed_codes.append(code)

		return {"success": success_results, "failed": failed_codes}

	# ========== 批量同步接口 ==========

	def batch_sync (self, data_types: List[str], request_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		批量同步接口

		Args:
			data_types: 数据类型列表
			request_data: 请求参数

		Returns:
			同步结果
		"""
		logger.info(f"开始批量同步: {data_types}")

		results = {}
		total_records = 0

		for i, data_type in enumerate(data_types):
			try:
				# 更新状态
				self.status_manager.update_task_progress(
					request_data.get("task_id", ""),
					current_task=f"正在同步: {data_type}",
					completed_tasks=i
				)

				# 执行同步
				sync_result = self._execute_single_sync(data_type, request_data)
				results[data_type] = sync_result

				# 统计记录数
				if sync_result.get("success") and "count" in sync_result:
					total_records += sync_result["count"]

				logger.info(f"数据类型 {data_type} 同步完成")

			except Exception as e:
				error_msg = f"数据类型 {data_type} 同步失败: {str(e)}"
				logger.error(error_msg)
				results[data_type] = {"success": False, "error": error_msg}

		return {
			"success": True,
			"results": results,
			"total_records": total_records
		}

	def _execute_single_sync (self, data_type: str, request_data: Dict[str, Any]) -> Dict[str, Any]:
		"""执行单个数据类型同步"""
		# 提取参数
		days = request_data.get("days", 30)
		stock_codes = request_data.get("stock_codes")
		batch_size = request_data.get("batch_size", 100)
		clean_config = request_data.get("clean_config", {})

		# 根据数据类型调用不同的同步方法
		if data_type == "stock_basic":
			exchange = request_data.get("exchange")
			return self.sync_stock_basic(exchange=exchange, clean_config=clean_config)

		elif data_type == "daily":
			return self.sync_daily_data(days, stock_codes, batch_size, clean_config)

		elif data_type == "weekly":
			return self.sync_weekly_data(days, stock_codes, batch_size, clean_config)

		elif data_type == "monthly":
			return self.sync_monthly_data(days, stock_codes, batch_size, clean_config)

		elif data_type == "adj_factor":
			return self._sync_period_data("adj_factor", days, stock_codes, batch_size, clean_config)

		elif data_type == "daily_basic":
			return self._sync_period_data("daily_basic", days, stock_codes, batch_size, clean_config)

		elif data_type == "moneyflow":
			return self._sync_period_data("moneyflow", days, stock_codes, batch_size, clean_config)

		elif data_type == "daily_limit":
			return self._sync_period_data("daily_limit", days, stock_codes, batch_size, clean_config)

		else:
			return {"success": False, "error": f"不支持的数据类型: {data_type}"}

	# ========== 辅助方法 ==========

	def get_supported_data_types (self) -> Dict[str, Any]:
		"""获取支持的数据类型列表"""
		return {
			"stock_basic": {"name": "股票基本信息", "description": "股票基础信息"},
			"daily": {"name": "日线数据", "description": "A股日线行情数据"},
			"weekly": {"name": "周线数据", "description": "周线行情数据"},
			"monthly": {"name": "月线数据", "description": "月线行情数据"},
			"adj_factor": {"name": "复权因子数据", "description": "股票复权因子"},
			"daily_basic": {"name": "每日指标数据", "description": "每日基本面指标"},
			"moneyflow": {"name": "资金流向数据", "description": "资金流向数据"},
			"daily_limit": {"name": "每日涨跌停价格", "description": "每日涨跌停价格"},
			"trade_calendar": {"name": "交易日历", "description": "交易所交易日历"},
			"fund_basic": {"name": "基金基本信息", "description": "ETF基础信息"},
			"fund_daily": {"name": "基金日线行情", "description": "ETF日线行情"},
			"index_weight": {"name": "指数成分股", "description": "指数成分股权重"},
		}

	def cleanup (self):
		"""清理资源"""
		self.executor.shutdown(wait=True)
		logger.info("数据同步服务资源已清理")