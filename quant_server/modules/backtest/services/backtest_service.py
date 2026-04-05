# -*- coding: utf-8 -*-
"""
回测服务

负责回测任务的管理和执行
"""
import logging
from datetime import datetime
from typing import Dict, List, Any

from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.modules.backtest.engines.backtest_engine import BacktestEngine
from quant_server.modules.backtest.engines.optimization_engine import OptimizationEngine
from quant_server.modules.backtest.engines.report_engine import ReportEngine
from quant_server.modules.backtest.engines.simulation_engine import SimulationEngine
from quant_server.modules.data.services.market_service import MarketDataService
from quant_server.modules.strategy.strategies.base.strategy_context import StrategyContext
from quant_server.shared.database.repositories.strategy.backtest.backtest_equity_curve_repo import \
	BacktestEquityCurveRepository
from quant_server.shared.database.repositories.strategy.backtest.position_repo import BacktestPositionRepository
from quant_server.shared.database.repositories.strategy.backtest.task_repo import BacktestTaskRepository
from quant_server.shared.database.repositories.strategy.backtest.trade_repo import BacktestTradeRepository
from quant_server.shared.database.repositories.strategy.management import StrategyRepository, StrategyParameterRepository
import importlib

logger = logging.getLogger(__name__)


class BacktestService:
	"""
	回测服务

	负责回测任务的管理和执行
	"""

	def __init__ (self, db: AsyncSession):
		"""
		初始化回测服务

		Args:
			db: 数据库会话
		"""
		self.db = db

		# 初始化引擎
		from quant_server.core.engines.types.entities import EngineConfig
		self.backtest_engine = BacktestEngine(EngineConfig(name="BacktestEngine", engine_type="backtest"))
		self.simulation_engine = SimulationEngine(EngineConfig(name="SimulationEngine", engine_type="simulation"))
		self.optimization_engine = OptimizationEngine(EngineConfig(name="OptimizationEngine", engine_type="optimization"))
		self.report_engine = ReportEngine(EngineConfig(name="ReportEngine", engine_type="report"))
		self.market_service = MarketDataService(db)

		# 初始化仓库
		self.task_repo = BacktestTaskRepository(db)
		self.trade_repo = BacktestTradeRepository(db)
		self.position_repo = BacktestPositionRepository(db)
		self.equity_curve_repo = BacktestEquityCurveRepository(db)
		self.strategy_repo = StrategyRepository(db)
		self.param_repo = StrategyParameterRepository(db)

	async def create_backtest_task (self, request, user_id: int) -> Dict[str, Any]:
		"""
		创建回测任务

		Args:
			request: 回测创建请求
			user_id: 用户ID

		Returns:
			回测任务信息
		"""
		try:
			# 获取策略参数
			strategy_params = {}
			try:
				params = await self.param_repo.get_by_strategy_id(str(request.strategy_id))
				for param in params:
					strategy_params[param.param_name] = param.param_value
			except Exception as e:
				logger.error(f"获取策略参数失败: {str(e)}")

			# 创建回测任务记录
			task = await self.task_repo.create({
				"name": request.name,
				"strategy_id": str(request.strategy_id),
				"config": {
					"start_date": request.start_date,
					"end_date": request.end_date,
					"initial_capital": request.initial_capital,
					"commission_rate": request.commission_rate,
					"slippage_rate": request.slippage_rate
				},
				"status": "pending",
				"user_id": user_id,
				"created_at": datetime.now()
			})

			# 保存回测参数到backtest_parameters表
			try:
				from quant_server.shared.database.repositories.strategy.backtest.parameter_repo import BacktestParameterRepository
				param_repo = BacktestParameterRepository(self.db)
				
				# 保存成本参数
				await param_repo.create({
					'task_id': task.id,
					'param_category': 'cost',
					'param_name': 'commission_rate',
					'param_value': float(request.commission_rate),
					'description': '佣金费率'
				})
				
				await param_repo.create({
					'task_id': task.id,
					'param_category': 'cost',
					'param_name': 'slippage_rate',
					'param_value': float(request.slippage_rate),
					'description': '滑点费率'
				})
				
				# 保存资金参数
				await param_repo.create({
					'task_id': task.id,
					'param_category': 'capital',
					'param_name': 'initial_capital',
					'param_value': float(request.initial_capital),
					'description': '初始资金'
				})
				
				# 保存策略参数
				for param_name, param_value in strategy_params.items():
					await param_repo.create({
						'task_id': task.id,
						'param_category': 'strategy',
						'param_name': param_name,
						'param_value': param_value,
						'description': f'策略参数: {param_name}'
					})
			except Exception as e:
				logger.error(f"保存回测参数失败: {str(e)}")

			logger.info(f"创建回测任务成功: {task.id}, {request.name}")

			return {
				"task_id": task.id,
				"status": task.status
			}
		except Exception as e:
			logger.error(f"创建回测任务失败: {str(e)}")
			raise

	async def get_backtest_task (self, task_id: str, user_id: int) -> Dict[str, Any]:
		"""
		获取回测任务详情

		Args:
			task_id: 任务ID
			user_id: 用户ID

		Returns:
			回测任务详情
		"""
		try:
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")

			# 检查权限
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			config = task.config or {}
			return {
				"id": task.id,
				"name": task.name,
				"strategy_id": task.strategy_id,
				"start_date": config.get('start_date'),
				"end_date": config.get('end_date'),
				"initial_capital": config.get('initial_capital'),
				"commission_rate": config.get('commission_rate'),
				"slippage_rate": config.get('slippage_rate'),
				"status": task.status,
				"result": task.result,
				"created_at": task.created_at,
				"updated_at": task.updated_at
			}
		except Exception as e:
			logger.error(f"获取回测任务详情失败: {str(e)}")
			raise

	async def get_backtest_task_list (self, request, user_id: int) -> Dict[str, Any]:
		"""
		获取回测任务列表

		Args:
			request: 回测列表请求
			user_id: 用户ID

		Returns:
			回测任务列表
		"""
		try:
			# 构建查询条件
			filters = {"user_id": user_id}
			if request.status:
				filters["status"] = request.status

			# 分页查询
			tasks, total = await self.task_repo.get_list(
				filters=filters,
				page=request.page,
				page_size=request.page_size
			)

			# 格式化结果
			data = []
			for task in tasks:
				data.append({
					"id": task.id,
					"name": task.name,
					"strategy_id": task.strategy_id,
					"status": task.status,
					"created_at": task.created_at,
					"updated_at": task.updated_at
				})

			return {
				"data": data,
				"pagination": {
					"page": request.page,
					"page_size": request.page_size,
					"total": total
				}
			}
		except Exception as e:
			logger.error(f"获取回测任务列表失败: {str(e)}")
			raise

	async def cancel_backtest_task (self, task_id: str, user_id: int) -> Dict[str, Any]:
		"""
		取消回测任务

		Args:
			task_id: 任务ID
			user_id: 用户ID

		Returns:
			取消结果
		"""
		try:
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")

			# 检查权限
			if task.user_id != user_id:
				raise ValueError("无权限操作该回测任务")

			# 只有pending或running状态的任务可以取消
			if task.status not in ["pending", "running"]:
				raise ValueError(f"任务状态为 {task.status}，无法取消")

			# 更新任务状态
			await self.task_repo.update(task_id, {
				"status": "cancelled",
				"updated_at": datetime.now()
			})

			logger.info(f"取消回测任务成功: {task_id}")

			return {
				"task_id": task_id,
				"status": "cancelled"
			}
		except Exception as e:
			logger.error(f"取消回测任务失败: {str(e)}")
			raise

	async def get_backtest_equity_curve (self, task_id: str, user_id: int) -> List[Dict[str, Any]]:
		"""
		获取回测净值曲线

		Args:
			task_id: 任务ID
			user_id: 用户ID

		Returns:
			净值曲线数据
		"""
		try:
			# 验证任务存在且用户有权限
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			# 获取净值曲线数据
			equity_curves = await self.equity_curve_repo.get_equity_curve(task_id)

			# 格式化结果
			data = []
			for curve in equity_curves:
				data.append({
					"date": curve.trade_date,
					"equity": float(curve.equity),
					"drawdown": 0.0  # BacktestEquityCurve模型中没有drawdown字段
				})

			return data
		except Exception as e:
			logger.error(f"获取回测净值曲线失败: {str(e)}")
			raise

	async def get_backtest_trades (self, task_id: str, user_id: int) -> Dict[str, Any]:
		"""
		获取回测交易记录

		Args:
			task_id: 任务ID
			user_id: 用户ID

		Returns:
			交易记录列表
		"""
		try:
			# 验证任务存在且用户有权限
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			# 获取交易记录
			trades = await self.trade_repo.get_by_task_id(task_id)
			total = len(trades)

			# 格式化结果
			data = []
			for trade in trades:
				data.append({
					"id": trade.id,
					"symbol": trade.ts_code,
					"side": trade.direction,
					"price": float(trade.price),
					"volume": trade.volume,
					"datetime": trade.trade_time,
					"profit": 0.0,  # BacktestTrade模型中没有profit字段
					"profit_pct": 0.0  # BacktestTrade模型中没有profit_pct字段
				})

			return {
				"data": data,
				"pagination": {
					"page": 1,
					"page_size": 20,
					"total": total
				}
			}
		except Exception as e:
			logger.error(f"获取回测交易记录失败: {str(e)}")
			raise

	async def get_backtest_positions (self, task_id: str, trade_date: str, user_id: int) -> List[Dict[str, Any]]:
		"""
		获取回测持仓快照

		Args:
			task_id: 任务ID
			trade_date: 交易日期
			user_id: 用户ID

		Returns:
			持仓快照数据
		"""
		try:
			# 验证任务存在且用户有权限
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			# 将字符串日期转换为date类型
			from datetime import datetime
			trade_date_obj = datetime.strptime(trade_date, "%Y-%m-%d").date()

			# 获取持仓快照
			positions = await self.position_repo.get_daily_positions(
				task_id=task_id,
				trade_date=trade_date_obj
			)

			# 格式化结果
			data = []
			for position in positions:
				data.append({
					"symbol": position.ts_code,
					"volume": position.volume,
					"cost_price": float(position.cost_price),
					"current_price": 0.0,  # BacktestPosition模型中可能没有current_price字段
					"profit": 0.0,  # BacktestPosition模型中可能没有profit字段
					"profit_pct": 0.0  # BacktestPosition模型中可能没有profit_pct字段
				})

			return data
		except Exception as e:
			logger.error(f"获取回测持仓快照失败: {str(e)}")
			raise

	async def get_backtest_result (self, task_id: str, user_id: int) -> Dict[str, Any]:
		"""
		获取回测结果

		Args:
			task_id: 任务ID
			user_id: 用户ID

		Returns:
			回测结果
		"""
		try:
			# 验证任务存在且用户有权限
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			# 检查任务状态
			if task.status != "completed":
				raise ValueError(f"任务状态为 {task.status}，尚未完成")

			# 返回结果
			return task.result or {}
		except Exception as e:
			logger.error(f"获取回测结果失败: {str(e)}")
			raise

	async def run_backtest (self, task_id: str) -> None:
		"""
		执行回测任务

		Args:
			task_id: 任务ID
		"""
		# 导入datetime模块
		from datetime import datetime
		try:
			# 更新任务状态为running
			await self.task_repo.update(task_id, {
				"status": "running",
				"updated_at": datetime.now()
			})

			# 获取任务信息
			task = await self.task_repo.get(task_id)

			# 加载策略
			# 从策略模块加载策略
			strategy = await self.strategy_repo.get_by_id(task.strategy_id)
			if not strategy:
				raise ValueError(f"策略不存在: {task.strategy_id}")

			# 获取历史数据配置
			config = task.config or {}
			
			# 从backtest_parameters表获取配置数据
			try:
				from quant_server.shared.database.repositories.strategy.backtest.parameter_repo import BacktestParameterRepository
				param_repo = BacktestParameterRepository(self.db)
				
				# 获取所有回测参数
				params = await param_repo.get_task_parameters(task.id)
				for param in params:
					if param.param_category in ['market', 'cost', 'capital']:
						config[param.param_name] = param.param_value
				logger.info(f"从backtest_parameters表获取配置数据成功: {len(params)} 个参数")
			except Exception as e:
				logger.error(f"从backtest_parameters表获取配置数据失败: {str(e)}")
				# 继续使用task.config

			# 动态加载策略模块
			strategy_class = None
			try:
				# 构建策略模块路径
				module_path = strategy.module_path
				class_name = strategy.class_name

				# 导入策略模块
				module = importlib.import_module(module_path)
				# 获取策略类
				strategy_class = getattr(module, class_name)
			except Exception:
				# 如果动态导入失败，尝试从策略代码直接执行
				try:
					# 创建临时模块
					temp_module = {}
					exec(strategy.code, temp_module)
					# 查找策略类
					for name, obj in temp_module.items():
						if isinstance(obj, type) and name == strategy.class_name:
							strategy_class = obj
							break
					if not strategy_class:
						# 如果没有找到指定的类，尝试查找第一个类
						for name, obj in temp_module.items():
							if isinstance(obj, type):
								strategy_class = obj
								break
					if not strategy_class:
						raise ValueError("策略代码中未找到策略类")
				except Exception as e:
					logger.error(f"加载策略失败: {str(e)}")
					raise

			# 加载策略到回测引擎
			from quant_server.modules.strategy.constants import StrategyType
			from quant_server.modules.strategy.models import StrategyConfig

			# 注册策略类
			self.backtest_engine.register_strategy(StrategyType.CUSTOM, strategy_class)

			# 创建策略配置
			strategy_config = StrategyConfig(
				name=strategy.name,
				initial_capital=float(config.get('initial_capital', 1000000)),
				commission_rate=float(config.get('commission_rate', 0.0003)),
				slippage=float(config.get('slippage_rate', 0.0001))
			)

			# 获取策略参数
			parameters = {}
			try:
				strategy_params = await self.param_repo.get_by_strategy_id(task.strategy_id)
				for param in strategy_params:
					parameters[param.param_name] = param.param_value
				logger.info(f"获取策略参数成功: {len(parameters)} 个参数")
			except Exception as e:
				logger.error(f"获取策略参数失败: {str(e)}")
				# 继续执行，使用空参数
				parameters = {}

			# 加载策略
			self.backtest_engine.load_strategy(
				strategy_id=task.strategy_id,
				name=strategy.name,
				strategy_type=StrategyType.CUSTOM,
				code=strategy.code,
				parameters=parameters,
				config=strategy_config
			)

			# 获取历史数据
			# 将字符串日期转换为datetime对象
			start_date = None
			end_date = None
			if config.get('start_date'):
				start_date = datetime.strptime(config.get('start_date'), "%Y-%m-%d")
			if config.get('end_date'):
				end_date = datetime.strptime(config.get('end_date'), "%Y-%m-%d")
			
			# 检查股票代码是否存在
			ts_code = config.get('ts_code') or parameters.get('ts_code')
			if not ts_code:
				raise ValueError("股票代码不能为空，请在回测配置或策略参数中设置ts_code")
			
			# 获取历史数据
			try:
				data = await self.market_service.get_historical_quotes(
					ts_code=ts_code,
					start_date=start_date,
					end_date=end_date
				)
				if not data:
					raise ValueError(f"获取历史数据失败: 股票 {ts_code} 无数据")
			except Exception as e:
				logger.error(f"获取历史数据失败: {str(e)}")
				raise

			# 创建策略上下文
			context = StrategyContext(
				strategy_id=task.strategy_id,
				strategy_name="Backtest Strategy",
				user_id=task.user_id,
				initial_capital=float(config.get('initial_capital', 1000000)),
				commission_rate=float(config.get('commission_rate', 0.0003)),
				slippage=float(config.get('slippage_rate', 0.0001))
			)

			# 执行回测
			# 假设 run_backtest 方法不是异步的，移除 await
			# 将 data 转换为 DataFrame
			import pandas as pd
			try:
				data_df = pd.DataFrame(data)
				if data_df.empty:
					raise ValueError(f"历史数据为空: 股票 {ts_code}")
				
				# 确保数据包含必要的列
				required_columns = ['open', 'high', 'low', 'close', 'volume']
				missing_columns = [col for col in required_columns if col not in data_df.columns]
				if missing_columns:
					raise ValueError(f"历史数据缺少必要的列: {missing_columns}")
				
				# 使用实际的股票代码作为键
				result = self.backtest_engine.run_backtest(
					strategy_id=task.strategy_id,
					data={ts_code: data_df},  # 使用实际的股票代码作为键
					context=context
				)
			except Exception as e:
				logger.error(f"执行回测失败: {str(e)}")
				raise

			# 计算绩效指标
			metrics = self.backtest_engine.calculate_metrics(task.strategy_id)

			# 生成净值曲线
			equity_curve = self._generate_equity_curve(result.get("signals", []), float(config.get('initial_capital', 1000000)))

			# 生成回测结果
			backtest_result = {
				"metrics": metrics,
				"trades": result.get("signals", []),
				"equity_curve": equity_curve
			}

			# 保存结果
			await self.task_repo.update(task_id, {
				"status": "completed",
				"result": backtest_result,
				"updated_at": datetime.now()
			})

			logger.info(f"回测任务执行完成: {task_id}")
		except Exception as e:
			logger.error(f"回测任务执行失败: {str(e)}")
			# 更新任务状态为failed
			await self.task_repo.update(task_id, {
				"status": "failed",
				"result": {"error": str(e)},
				"updated_at": datetime.now()
			})

	async def optimize_parameters (self, request) -> Dict[str, Any]:
		"""
		参数优化

		Args:
			request: 参数优化请求

		Returns:
			优化结果
		"""
		try:
			# 执行参数优化
			result = await self.optimization_engine.optimize(
				strategy_id=request.strategy_id,
				parameters=request.parameters,
				method=request.optimization_method
			)

			logger.info(f"参数优化完成: {request.strategy_id}")

			# 生成任务ID（基于时间戳）
			import time
			task_id = str(int(time.time() * 1000))

			return {
				"task_id": task_id,
				"result": result
			}
		except Exception as e:
			logger.error(f"参数优化失败: {str(e)}")
			raise

	@staticmethod
	def _generate_equity_curve (signals, initial_capital):
		"""
		生成净值曲线

		Args:
			signals: 交易信号列表
			initial_capital: 初始资金

		Returns:
			净值曲线数据
		"""
		equity_curve = []
		equity = initial_capital
		max_equity = initial_capital
		drawdown = 0

		# 添加初始点
		equity_curve.append({
			"date": signals[0].datetime if signals else None,
			"equity": equity,
			"drawdown": drawdown
		})

		# 计算每笔交易后的净值和回撤
		for signal in signals:
			if hasattr(signal, 'profit'):
				equity += signal.profit
				if equity > max_equity:
					max_equity = equity
				drawdown = (max_equity - equity) / max_equity if max_equity > 0 else 0

				equity_curve.append({
					"date": signal.datetime,
					"equity": equity,
					"drawdown": drawdown
				})

		return equity_curve