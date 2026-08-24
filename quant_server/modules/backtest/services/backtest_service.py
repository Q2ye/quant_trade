# -*- coding: utf-8 -*-
"""
回测服务 — BacktestService

================================================================================
职责边界
================================================================================
BacktestService 是回测模块的「服务门面」，负责：
  1. 回测任务的 CRUD 生命周期管理（创建 / 查询 / 取消 / 删除）
  2. 回测执行引擎的延迟初始化与编排
  3. 策略类的动态加载（模块导入 + exec 沙箱回退）
  4. 回测结果的持久化与查询（净值曲线 / 交易记录 / 持仓快照）
  5. 参数优化入口（委托给 OptimizationEngine）
  6. 快速回测（一步完成：创建 → 执行 → 返回结果）
  7. 报告导出（JSON / CSV 格式）

================================================================================
架构定位
================================================================================
位置：modules/backtest/services/     （灵活层 — 业务模块）
依赖方向（严格单向）：
  modules/backtest/  →  shared/      （Repository 数据访问）
                     →  core/        （EngineBase, EventEngine, 事件基类）
                     →  modules/strategy/  （DataFeedEngine, StrategyManager, 策略类）

通信机制：
  - Service → Repository：同步直接调用
  - 模块间（backtest → strategy / trade）：仅通过 EventEngine 异步事件
  - 本 Service 内：BacktestEngine 编排 DataFeedEngine + StrategyManager + BacktestBroker

================================================================================
执行链路（v1.2）
================================================================================
run_backtest(task_id) 核心流程：
  1. 建立独立 DB 会话（后台任务隔离）
  2. 更新任务状态 → "running"
  3. 加载回测配置（task.config + backtest_parameters 表）
  4. 延迟初始化重量级引擎（_init_engines）
  5. 动态加载策略类（importlib → exec 回退）
  6. 注册策略到 StrategyManager → 启动策略（创建 StrategyContext）
  7. 解析股票池（优先级：回测配置 symbols → 策略 universe → 全市场兜底 1000 只）
  8. 调用 BacktestEngine.run() 执行回测
  9. 保存 BacktestResult 到数据库
  10. 异常时标记任务失败，finally 中关闭会话

================================================================================
关键设计决策
================================================================================
- 延迟初始化：重量级引擎（DataFeed, StrategyManager, Broker 等）仅在 run_backtest()
  中调用 _init_engines() 时创建，GET 请求不会触发引擎初始化，避免资源浪费。
- 后台会话隔离：run_backtest() 通过 FastAPI BackgroundTasks 异步执行，必须创建
  独立的 DB 会话（请求 handler 的 session 在返回响应后已关闭）。
- 策略加载双路径：优先 importlib 模块导入（生产环境），失败时回退到 exec 沙箱
  执行（用户自定义策略代码），exec 环境中注入 BaseStrategy、BarData、numpy/pandas 等依赖。
- 股票池兜底：当用户既未配置 symbols 也未在策略中定义 universe 时，取全市场前 1000
  只股票兜底（仅用于快速验证代码无语法错误，结果不具备策略参考意义）。

================================================================================
版本历史
================================================================================
v1.2: 集成新版 BacktestEngine（编排 DataFeedEngine + StrategyManager + BacktestBroker）
v1.1: 新增 quick_backtest、delete_backtest_task、export_report
v1.0: 初始版本 — 回测 CRUD + 执行 + 结果查询
"""
import asyncio
import importlib
import logging
import uuid
from datetime import date as date_type, datetime
from typing import Dict, List, Any, Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# 核心框架导入
# ---------------------------------------------------------------------------
from core.engines.types.entities import EngineConfigEntity
from modules.backtest.engines.backtest_broker import BacktestBroker, BacktestBrokerConfig
# ---------------------------------------------------------------------------
# 引擎层导入 — 回测链路的核心引擎
# ---------------------------------------------------------------------------
from modules.backtest.engines.backtest_engine import BacktestEngine, BacktestResult
from modules.backtest.engines.optimization_engine import OptimizationEngine
# ---------------------------------------------------------------------------
# 共享基础设施导入
# ---------------------------------------------------------------------------
from modules.data.services.market_service import MarketDataService
from modules.strategy.constants import RunMode, StrategyType
# ---------------------------------------------------------------------------
# 策略模块导入 — 策略管理、注册、上下文
# ---------------------------------------------------------------------------
from modules.strategy.engines.data_feed_engine import DataFeedEngine
from modules.strategy.engines.strategy_manager import StrategyManager
from modules.strategy.engines.strategy_registry import StrategyRegistry
from modules.strategy.models import StrategyConfig as StrategyConfigModel
from modules.strategy.strategies.base.strategy_context import StrategyContext
# ---------------------------------------------------------------------------
# Repository 导入 — 分层数据访问（按业务域组织）
# ---------------------------------------------------------------------------
from shared.database.repositories.strategy.backtest.backtest_equity_curve_repo import \
	BacktestEquityCurveRepository
from shared.database.repositories.strategy.backtest.position_repo import BacktestPositionRepository
from shared.database.repositories.strategy.backtest.task_repo import BacktestTaskRepository
from shared.database.repositories.strategy.backtest.trade_repo import BacktestTradeRepository
from shared.database.repositories.strategy.management import StrategyRepository, \
	StrategyParameterRepository

logger = logging.getLogger(__name__)


def _is_strategy_subclass(obj: type) -> bool:
	"""
	判断 obj 是否是 BaseStrategy 的子类。

	用于 exec 沙箱加载策略代码后，从 temp_module 的全局命名空间中筛选出
	用户定义的策略类（排除 BaseStrategy 自身和 typing 特殊类型）。

	Args:
		obj: 待检测的类型对象（通常是 temp_module 中的 value）。

	Returns:
		True 表示 obj 是 BaseStrategy 的合法子类；False 表示不是
		（包括 BaseStrategy 自身、typing.Any 等特殊类型、或非类型对象）。

	Note:
		- typing.Any、typing.List 等特殊类型在调用 issubclass() 时会抛出
		  TypeError，此处统一捕获并返回 False。
		- 该函数定义在模块顶层而非类内，以便其他模块复用（如 StrategyRegistry）。
	"""
	try:
		from modules.strategy.strategies.base.base_strategy import BaseStrategy
		return obj is not BaseStrategy and issubclass(obj, BaseStrategy)
	except TypeError:
		# typing.Any, typing.List 等特殊类型 issubclass 会抛 TypeError
		return False


class BacktestService:
	"""
	回测服务 — 回测模块的统一入口。

	职责：
	- 回测任务生命周期管理：创建、查询、取消、删除
	- 回测执行编排：策略加载 → 引擎初始化 → 执行 → 结果持久化
	- 结果数据查询：净值曲线、交易记录、持仓快照、绩效指标
	- 参数优化：委托给 OptimizationEngine（网格搜索 / 遗传算法 / 贝叶斯优化）
	- 快速回测：创建 + 执行 + 返回结果一步完成（不进入后台队列）
	- 报告导出：支持 JSON / CSV 格式

	设计要点：
	- 仓库（Repository）在 __init__ 中创建，轻量无状态，每次请求复用
	- 引擎（Engine）在 _init_engines() 中延迟创建，仅在执行回测时初始化
	  （GET 类请求不会触发重量级引擎初始化，避免资源浪费）
	- 事件引擎（EventEngine）可选注入，用于进度推送和模块间通信

	Attributes:
		db: 异步数据库会话（AsyncSession），由调用方注入
		event_engine: 事件引擎引用（可选），用于推送回测进度事件
		task_repo: 回测任务仓库
		trade_repo: 回测交易记录仓库
		position_repo: 回测持仓快照仓库
		equity_curve_repo: 回测净值曲线仓库
		strategy_repo: 策略管理仓库
		param_repo: 策略参数仓库
		data_feed: 数据馈送引擎（延迟初始化）
		strategy_registry: 策略注册表（延迟初始化）
		strategy_manager: 策略管理器（延迟初始化）
		broker: 回测券商模拟器（延迟初始化）
		backtest_engine: 回测引擎（延迟初始化，编排 DataFeed + Manager + Broker）
		simulation_engine: 仿真引擎（延迟初始化）
		optimization_engine: 参数优化引擎（延迟初始化）
		report_engine: 报告生成引擎（延迟初始化）
		market_service: 市场数据服务（延迟初始化）
	"""

	def __init__(self, db: AsyncSession, event_engine=None):
		"""
		初始化回测服务。

		创建所有 Repository 实例（轻量），引擎引用置为 None，
		等待 _init_engines() 延迟初始化。

		Args:
			db: 异步数据库会话（AsyncSession），由 FastAPI 依赖注入提供。
			event_engine: 事件引擎（可选）。传入后可用于：
				- 回测进度推送（ProgressEvent）
				- 模块间通信（如推送交易信号到 Trade 模块）
				默认为 None，不推送事件。
		"""
		self.db = db
		self.event_engine = event_engine

		# v1.3: 活跃回测的取消事件 {task_id: asyncio.Event}
		# 用于 cancel_backtest_task() 向 run_backtest() 发送取消信号
		self._active_cancellations: Dict[str, "asyncio.Event"] = {}

		# =====================================================================
		# 仓库（Repository）— 轻量，每次请求都需要，在 __init__ 中创建
		# 职责：纯数据访问（CRUD），不包含业务逻辑
		# =====================================================================
		self.task_repo = BacktestTaskRepository(db)
		self.trade_repo = BacktestTradeRepository(db)
		self.position_repo = BacktestPositionRepository(db)
		self.equity_curve_repo = BacktestEquityCurveRepository(db)
		self.strategy_repo = StrategyRepository(db)
		self.param_repo = StrategyParameterRepository(db)

		# =====================================================================
		# 引擎（Engine）— 重量级，仅在执行回测时初始化
		# 初始值均为 None，由 _init_engines() 懒加载
		# =====================================================================
		self.data_feed: Optional[DataFeedEngine] = None
		self.strategy_registry: Optional[StrategyRegistry] = None
		self.strategy_manager: Optional[StrategyManager] = None
		self.broker: Optional[BacktestBroker] = None
		self.backtest_engine: Optional[BacktestEngine] = None
		self.optimization_engine: Optional[OptimizationEngine] = None
		self.market_service: Optional[MarketDataService] = None

	def _init_engines(self, db: AsyncSession = None) -> None:
		"""
		延迟初始化回测引擎链（仅在执行回测时调用）。

		初始化以下引擎并建立依赖关系：
		DataFeedEngine → StrategyManager → BacktestBroker → BacktestEngine
		                          → OptimizationEngine

		重要变更 (v1.3): 每次调用均创建全新引擎实例，不再复用。
		- 原因 1: 后台任务拥有独立的 DB 会话，HTTP 请求的 session 已关闭，
		  引擎若持有旧 session 会导致数据加载失败。
		- 原因 2: 多次并发回测共享同一个引擎实例会导致策略注册表、
		  Broker 持仓等状态互相覆盖（竞态条件）。

		Args:
		    db: 数据库会话。传入时使用该会话创建所有引擎。
		        为 None 时使用 self.db（HTTP 请求上下文）。

		默认参数（可通过回测配置覆盖）：
			- initial_capital: 1,000,000（100万）
			- commission_rate: 0.0001（万分之一佣金（万一免五））
			- slippage: 0.001（千一滑点）
		"""
		_session = db or self.db

		# ---- 数据馈送引擎 ----
		self.data_feed = DataFeedEngine(_session)

		# ---- 策略注册表 + 管理器 ----
		self.strategy_registry = StrategyRegistry()
		# 获取 session_factory（供策略 on_start 通过 IndexDailyRepository 加载中证500数据）
		_csi500_factory = None
		try:
			from shared.database.session.connection_pool import get_connection_pool
			_csi500_factory = get_connection_pool().get_session_factory()
		except Exception:
			_csi500_factory = None
		self.strategy_manager = StrategyManager(
			event_engine=self.event_engine,
			registry=self.strategy_registry,
			session_factory=_csi500_factory,
		)

		# ---- 回测券商模拟器（含交易成本配置） ----
		broker_config = BacktestBrokerConfig(
			initial_capital=1_000_000,  # 初始资金 100 万
			commission_rate=0.0001,  # 佣金费率 万三
			slippage=0.001,  # 滑点 千一
		)
		self.broker = BacktestBroker(config=broker_config, event_engine=self.event_engine)

		# ---- 回测引擎（核心编排器） ----
		# 编排链路：DataFeedEngine → StrategyManager → BacktestBroker
		self.backtest_engine = BacktestEngine(
			config=EngineConfigEntity(name="BacktestEngine", engine_type="backtest"),
			event_engine=self.event_engine,
			data_feed=self.data_feed,
			strategy_manager=self.strategy_manager,
			broker=self.broker,
		)

		# ---- 辅助引擎 ----
		self.optimization_engine = OptimizationEngine(
			EngineConfigEntity(name="OptimizationEngine", engine_type="optimization"),
			event_engine=self.event_engine,
			db=_session,
		)
		self.market_service = MarketDataService(_session)

	async def recover_orphan_tasks(self) -> int:
		"""
		恢复孤儿任务 — 将启动时残留的 "running" 状态任务标记为 failed。

		服务器异常重启后，BackgroundTasks 中运行的 run_backtest()
		协程会丢失，但 DB 中的任务状态仍为 "running"。此方法在服务
		初始化或首次查询时扫描并修复这些孤儿任务。

		Returns:
			修复的任务数量
		"""
		try:
			from sqlalchemy import update, CursorResult
			from shared.database.models.business_models import BacktestTask
			from datetime import datetime

			stmt = (
				update(BacktestTask)
				.where(BacktestTask.status == "running")
				.values(
					status="failed",
					result={"error": "Server restarted during backtest execution"},
					updated_at=datetime.now(),
				)
			)
			result: CursorResult = await self.db.execute(stmt)
			await self.db.commit()

			recovered = result.rowcount
			if recovered > 0:
				logger.warning(f"恢复 {recovered} 个孤儿回测任务（running → failed）")
			return recovered
		except Exception as e:
			logger.error(f"恢复孤儿任务失败: {e}")
			return 0

	async def create_backtest_task(self, request, user_id: str) -> Dict[str, Any]:
		"""
		创建回测任务。

		流程：
		1. 从 StrategyParameterRepository 获取策略默认参数
		2. 在 backtest_tasks 表创建任务记录（状态：pending）
		3. 将回测参数拆分后写入 backtest_parameters 表：
		   - cost 类：commission_rate, slippage_rate
		   - capital 类：initial_capital
		   - market 类：ts_code（股票代码）
		   - strategy 类：用户自定义策略参数
		4. 显式 commit，确保后台任务能从独立 session 读到新任务

		Args:
			request: 回测创建请求（BacktestCreateRequest schema），包含：
				- name: 任务名称
				- strategy_id: 关联策略 ID
				- start_date / end_date: 回测区间
				- initial_capital: 初始资金
				- commission_rate / slippage_rate: 交易成本
				- symbols: 股票池
				- parameters: 可选参数字典（ts_code, strategy_params）
			user_id: 当前登录用户 ID

		Returns:
			{"task_id": str, "status": "pending"}

		Raises:
			各种数据库异常均会被捕获并记录日志后重新抛出。
		"""
		try:
			# ---- 1. 获取策略默认参数 ----
			strategy_params = {}
			try:
				params = await self.param_repo.get_by_strategy_id(str(request.strategy_id))
				for param in params:
					strategy_params[param.param_name] = param.param_value
			except Exception as e:
				logger.error(f"获取策略参数失败: {str(e)}")

			# ---- 2. v3.3: 获取策略版本 + 参数快照 ----
			strategy_version_id = None
			try:
				from shared.database.repositories.strategy.management.strategy_version_repo import StrategyVersionRepository
				version_repo = StrategyVersionRepository(self.db)
				ver = await version_repo.get_current_version(str(request.strategy_id))
				if ver:
					strategy_version_id = ver.id
			except Exception as _ve:
				logger.debug(f"版本查找跳过: {_ve}")
			try:
				from modules.strategy.services.strategy_service import StrategyService
				snap = StrategyService(self.db, None)
				await snap.snapshot_strategy_version(str(request.strategy_id), "backtest")
			except Exception as _se:
				logger.debug(f"参数快照跳过: {_se}")

			# ---- 3. 创建回测任务主记录 ----
			task = await self.task_repo.create({
				"name": request.name,
				"strategy_id": str(request.strategy_id),
				"strategy_version_id": strategy_version_id,
				"config": {
					"start_date": request.start_date,
					"end_date": request.end_date,
					"symbols": request.symbols or [],
					"benchmark": getattr(request, "benchmark", None),
					# v2.4: commission_rate/slippage_rate/initial_capital 移入
					# backtest_parameters 表（单源原则），config 中不再冗余存储
				},
				"status": "pending",
				"user_id": user_id,
				"created_at": datetime.now()
			})

			# ---- 4. 保存回测参数到 backtest_parameters 表（分类存储） ----
			try:
				from shared.database.repositories.strategy.backtest.parameter_repo import \
					BacktestParameterRepository
				param_repo = BacktestParameterRepository(self.db)

				# 3a. 成本类参数（commission_rate, slippage_rate）
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

				# 3b. 资金类参数（initial_capital）
				await param_repo.create({
					'task_id': task.id,
					'param_category': 'capital',
					'param_name': 'initial_capital',
					'param_value': float(request.initial_capital),
					'description': '初始资金'
				})

				# 3c. 市场参数与策略参数
				if hasattr(request, 'parameters') and request.parameters:
					# 市场参数（如 ts_code）
					if 'ts_code' in request.parameters:
						await param_repo.create({
							'task_id': task.id,
							'param_category': 'market',
							'param_name': 'ts_code',
							'param_value': request.parameters['ts_code'],
							'description': '股票代码'
						})

					# 策略参数（在回测请求中直接指定的覆盖值）
					if 'strategy_params' in request.parameters:
						for param_name, param_value in request.parameters['strategy_params'].items():
							await param_repo.create({
								'task_id': task.id,
								'param_category': 'strategy',
								'param_name': param_name,
								'param_value': param_value,
								'description': f'策略参数: {param_name}'
							})
				else:
					# 未指定额外参数时，使用策略默认参数
					for param_name, param_value in strategy_params.items():
						await param_repo.create({
							'task_id': task.id,
							'param_category': 'strategy',
							'param_name': param_name,
							'param_value': param_value,
							'description': f'策略参数: {param_name}'
						})
			except Exception as e:
				logger.error(f"保存回测参数失败: {str(e)} — 回滚参数写入并继续")
				await self.db.rollback()

			# ---- 4. 显式提交 —— 确保 BackgroundTasks 新 session 能读到任务 ----
			await self.db.commit()

			logger.info(f"创建回测任务成功: {task.id}, {request.name}")

			return {
				"task_id": task.id,
				"status": task.status
			}
		except Exception as e:
			logger.error(f"创建回测任务失败: {str(e)}")
			raise

	async def create_composite_task(self, request, user_id: str) -> Dict[str, Any]:
		"""
		创建组合回测任务 — 多策略共享资金池。

		Args:
			request: BacktestCompositeCreateRequest
		"""
		try:
			sids = []
			for cfg in request.strategy_configs:
				sid = str(cfg.strategy_id)
				strategy = await self.strategy_repo.get_by_id(sid)
				if not strategy:
					raise ValueError(f"策略不存在: {sid}")
				sids.append(sid)

			if len(set(sids)) < len(sids):
				raise ValueError("策略列表中有重复 ID")

			# v6.14: allocator_id 由后端从策略组合成员关系解析，替代前端按名称猜测
			resolved_configs = []
			for cfg in request.strategy_configs:
				sid = str(cfg.strategy_id)
				aid = cfg.allocator_id or await self._resolve_allocator_id(sid)
				resolved_configs.append({
					"strategy_id": sid,
					"allocator_id": aid,
					"parameters": cfg.parameters,
				})

			# 组合分配（2026-08 修复）：用户未指定 allocator_params 时，
			# 按策略角色生成默认 REGIME_BASE_ALLOCATION（牛市防守让位进攻）。
			# 此前 allocator_id=策略UUID 与默认配置(etf_bottom/stock_low_high)不匹配
			# → fallback 等权 → 进攻策略牛市只拿 50% 资金，收益减半。
			allocator_params = request.allocator_params
			if not allocator_params:
				allocator_params = await self._default_composite_allocator_params(resolved_configs)
				logger.info(
					f"创建组合回测: 生成默认 allocator_params "
					f"(熊0.7/0.3 震0.5/0.5 牛0/1) → {allocator_params}"
				)

			config_dict = {
				"start_date": request.start_date,
				"end_date": request.end_date,
				"symbols": request.symbols or [],
				"benchmark": getattr(request, "benchmark", None),
				"initial_capital": request.initial_capital,
				"commission_rate": request.commission_rate,
				"slippage_rate": request.slippage_rate,
				"strategy_configs": resolved_configs,
				"force_regime": request.force_regime,
				"allocator_params": allocator_params,
			}

			task = await self.task_repo.create({
				"name": request.name,
				"strategy_id": None,  # 组合任务无单一策略，FK 允许 NULL
				"config": config_dict,
				"status": "pending",
				"user_id": user_id,
			})
			await self.db.commit()

			logger.info(
				f"创建组合回测成功: {task.id}, {request.name}, "
				f"策略={sids}, force_regime={request.force_regime}"
			)
			return {"task_id": task.id, "status": task.status}
		except Exception as e:
			logger.error(f"创建组合回测失败: {str(e)}")
			raise

	async def _resolve_allocator_id(self, sid: str) -> str:
		"""从策略的组合成员关系解析 allocator_id（替代前端按名称猜）。

		策略在组合里 → 用该组合 strategy_ids 中该策略的 allocator_id。
		否则回退到 strategy_id 本身（后端兜底）。
		"""
		try:
			from sqlalchemy import text
			row = (await self.db.execute(
				text("SELECT composite_group_id FROM strategies WHERE id=:sid"),
				{"sid": sid},
			)).first()
			if row and row[0]:
				grp = (await self.db.execute(
					text("SELECT strategy_ids FROM composite_groups WHERE id=:g"),
					{"g": row[0]},
				)).first()
				if grp and grp[0]:
					for m in grp[0]:
						if m.get("strategy_id") == sid:
							return m.get("allocator_id") or sid
		except Exception:
			pass
		return sid

	async def _default_composite_allocator_params(
		self, configs: List[Dict[str, Any]]
	) -> Dict[str, Any]:
		"""按策略角色生成默认组合分配 REGIME_BASE_ALLOCATION（牛市防守让位进攻）。

		防守策略（ETF底部等）承担熊/震荡防御、牛市让位进攻；
		进攻策略在牛市获得全部资金。
		权重：0(BEAR) 防守0.7/进攻0.3；1(RANGE) 0.5/0.5；2(BULL) 防守0/进攻1。
		key 用 allocator_id（与 CapitalAllocator 查表一致，避免 fallback 等权）。
		"""
		defense_ids, attack_ids = [], []
		for cfg in configs:
			if await self._is_defense_strategy(cfg["strategy_id"]):
				defense_ids.append(cfg["allocator_id"])
			else:
				attack_ids.append(cfg["allocator_id"])

		base: Dict[int, Dict[str, float]] = {}
		# 优化 2026-08：熊市 7.1 年线门空仓→防守90%；震荡 7.1 动量主场→7.1 80%
		for regime, (d_w, a_w) in ((0, (0.9, 0.1)), (1, (0.2, 0.8)), (2, (0.0, 1.0))):
			alloc: Dict[str, float] = {}
			if defense_ids:
				alloc[defense_ids[0]] = round(d_w / len(defense_ids), 4)
			if attack_ids:
				alloc[attack_ids[0]] = round(a_w / len(attack_ids), 4)
			base[regime] = alloc
		return {"REGIME_BASE_ALLOCATION": base}

	async def _is_defense_strategy(self, sid: str) -> bool:
		"""按策略类名/名称判断是否为防守策略（ETF底部等）。"""
		try:
			strategy = await self.strategy_repo.get_by_id(sid)
			if not strategy:
				return False
			marker = "{} {}".format(
				getattr(strategy, "class_name", "") or "",
				getattr(strategy, "name", "") or "",
			)
			return any(k in marker for k in ("Bottom", "bottom", "防守", "底部"))
		except Exception:
			return False

	async def run_composite_backtest(self, task_id: str) -> None:
		"""
		执行组合回测 — 调用 BacktestEngine.run_composite()。
		与 run_backtest 复用相同的策略加载、引擎初始化、股票池解析逻辑。
		"""
		start_ts = datetime.now()
		try:
			# ---- Step 1-2: 加载任务 + 更新状态 ----
			task = await self.task_repo.get_by_task_id(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			config = task.config or {}

			await self.task_repo.update(task_id, {
				"status": "running",
				"updated_at": datetime.now()
			})
			await self.db.commit()

			# ---- Step 3: 初始化引擎 ----
			self._init_engines(db=self.db)
			self.backtest_engine.set_db_session(self.db)  # v6.11: 注入 DB 会话，使 _save_results 可持久化

			strategy_configs = config.get("strategy_configs", [])
			if len(strategy_configs) < 2:
				raise ValueError("组合回测至少需要 2 个策略")

			# ---- Step 4: 加载各个策略到 StrategyManager ----
			for cfg in strategy_configs:
				sid = str(cfg["strategy_id"])
				db_strategy = await self.strategy_repo.get_by_id(sid)
				if not db_strategy:
					raise ValueError(f"策略不存在: {sid}")

				strategy_class = await self._load_strategy_class(db_strategy)
				self.strategy_manager.register_strategy_class(
					StrategyType.CUSTOM, strategy_class
				)

				params = cfg.get("parameters") or await self._get_strategy_params(sid)

				strategy_cfg = StrategyConfigModel(
					name=db_strategy.name,
					initial_capital=float(config.get("initial_capital", 1_000_000)),
					commission_rate=float(config.get("commission_rate", 0.0001)),
					slippage=float(config.get("slippage_rate", 0.0001)),
				)
				await self.strategy_manager.load_strategy(
					strategy_id=sid,
					name=db_strategy.name,
					strategy_type=StrategyType.CUSTOM,
					code=db_strategy.code,
					parameters=params,
					config=strategy_cfg,
				)

				context = StrategyContext(
					strategy_id=sid,
					strategy_name=db_strategy.name,
					user_id=task.user_id,
					run_mode=RunMode.BACKTEST,
					initial_capital=float(config.get("initial_capital", 1_000_000)),
					commission_rate=float(config.get("commission_rate", 0.0001)),
					slippage=float(config.get("slippage_rate", 0.0001)),
				)
				_warmup_end = config.get("start_date") and datetime.strptime(config["start_date"], "%Y-%m-%d").date()
				await self.strategy_manager.start_strategy(sid, context, warmup_end_date=_warmup_end)

				# 2026-08 修复：回测市场数据预加载 — 对声明 BACKTEST_PRELOAD_STATE 的策略
				# （恐慌抄底/微盘等纯数据预加载型）调用 load_live_state，注入恐慌指数/指数/市值等
				# 回测所需数据（否则状态机第一道门被空映射拦截 → 全程 0 信号）。
				_sat_obj = self.strategy_manager.get_strategy_object(sid)
				if _sat_obj and getattr(_sat_obj, "BACKTEST_PRELOAD_STATE", False):
					_bt_start = config.get("start_date")
					await _sat_obj.load_live_state(self.db, strategy_id=str(sid), start_date=_bt_start)
					logger.info(
						f"回测 {task_id}: {_sat_obj.name} 市场数据预加载完成 "
						f"(回测窗口 start_date={_bt_start})"
					)

			# ---- Step 5: 解析股票池 ----
			symbols = config.get("symbols", [])
			if not symbols:
				all_s = set()
				for cfg in strategy_configs:
					sid = str(cfg["strategy_id"])
					strategy_obj = self.strategy_manager.get_strategy_object(sid)
					if strategy_obj:
						universe = getattr(strategy_obj, "_universe", [])
						all_s.update(universe or [])
				symbols = list(all_s)
			if not symbols:
				from modules.data.services.market_service import MarketDataService
				market_svc = MarketDataService(self.db)
				stocks = await market_svc.get_stock_list(limit=1000)
				symbols = [s.ts_code for s in stocks]

			logger.info(
				f"组合回测 {task_id}: 策略={[c['strategy_id'] for c in strategy_configs]}, "
				f"symbols={len(symbols)}只"
			)

			# ---- Step 6: 执行 ----
			result = await self.backtest_engine.run_composite(
				task_id=task_id,
				strategy_configs=strategy_configs,
				symbols=symbols,
				start_date=config.get("start_date", ""),
				end_date=config.get("end_date", ""),
				initial_capital=float(config.get("initial_capital", 1000000)),
				commission_rate=float(config.get("commission_rate", 0.0001)),
				slippage=float(config.get("slippage_rate", 0.0001)),
				benchmark_ts_code=config.get("benchmark") or "000300.SH",
				allocator_params=config.get("allocator_params"),
				force_regime=config.get("force_regime"),
			)

			backtest_result = result.to_dict()
			await self.task_repo.update(task_id, {
				"status": "completed",
				"result": backtest_result,
				"updated_at": datetime.now()
			})
			await self.db.commit()

			elapsed = (datetime.now() - start_ts).total_seconds()
			logger.info(
				f"组合回测完成: {task_id} "
				f"总收益={result.total_return:.2%} 夏普={result.sharpe_ratio:.2f} "
				f"耗时={elapsed:.1f}s"
			)
		except Exception as e:
			logger.error(f"组合回测 {task_id} 失败: {type(e).__name__}: {e}", exc_info=True)
			try:
				await self.task_repo.update(task_id, {
					"status": "failed",
					"error_message": str(e),
					"updated_at": datetime.now()
				})
				await self.db.commit()
			except Exception:
				pass
			raise

	async def get_backtest_task(self, task_id: str, user_id: str) -> Dict[str, Any]:
		"""
		获取单个回测任务详情。

		包含权限校验：仅允许任务创建者访问。

		Args:
			task_id: 回测任务 ID（UUID 字符串）。
			user_id: 当前登录用户 ID，用于权限校验。

		Returns:
			任务详情字典，包含：
			- id: 任务 ID
			- name: 任务名称
			- strategy_id: 关联策略 ID
			- start_date / end_date: 回测区间（从 config JSON 中提取）
			- initial_capital / commission_rate / slippage_rate: 成本参数
			- status: 任务状态（pending / running / completed / failed / cancelled）
			- result: 回测结果 JSON（仅 completed 状态有值）
			- created_at / updated_at: 时间戳

		Raises:
			ValueError: 任务不存在或用户无权限访问。
		"""
		try:
			# ---- 1. 查询任务 ----
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")

			# ---- 2. 权限校验 ----
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			# ---- 3. 格式化返回 ----
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
				"progress": float(getattr(task, "progress", 0) or 0),
				"result": task.result,
				"created_at": task.created_at,
				"updated_at": task.updated_at
			}
		except Exception as e:
			logger.error(f"获取回测任务详情失败: {str(e)}")
			raise

	async def get_backtest_task_list(self, request, user_id: str) -> Dict[str, Any]:
		"""
		获取回测任务列表（分页）。

		支持按状态过滤，默认每页 20 条。

		Args:
			request: 列表查询请求（BacktestListRequest schema），包含：
				- status: 可选，按状态过滤（pending / running / completed / failed / cancelled）
				- page: 页码（默认 1）
				- page_size: 每页条数（默认 20）
			user_id: 当前登录用户 ID，用于数据隔离。

		Returns:
			{
				"data": [{ id, name, strategy_id, status, created_at, updated_at }, ...],
				"pagination": { page, page_size, total }
			}
		"""
		try:
			# ---- 1. 构建查询条件 ----
			filters = {"user_id": user_id}
			if request.status:
				filters["status"] = request.status

			# ---- 2. 分页查询 ----
			tasks, total = await self.task_repo.get_list(
				filters=filters,
				page=request.page or 1,
				page_size=request.page_size or 20
			)

			# ---- 3. 格式化结果（只返回摘要字段，不含完整 config/result） ----
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
					"page": request.page or 1,
					"page_size": request.page_size or 20,
					"total": total
				}
			}
		except Exception as e:
			logger.error(f"获取回测任务列表失败: {str(e)}")
			raise

	async def cancel_backtest_task(self, task_id: str, user_id: str) -> Dict[str, Any]:
		"""
		取消回测任务。

		约束：
		- 仅 pending 或 running 状态的任务可取消
		- 已完成（completed）、已失败（failed）、已取消（cancelled）的任务不可再次取消

		Args:
			task_id: 回测任务 ID。
			user_id: 当前登录用户 ID，用于权限校验。

		Returns:
			{"task_id": str, "status": "cancelled"}

		Raises:
			ValueError: 任务不存在 / 无权限 / 当前状态不允许取消。
		"""
		try:
			# ---- 1. 查询任务并校验权限 ----
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")

			if task.user_id != user_id:
				raise ValueError("无权限操作该回测任务")

			# ---- 2. 状态校验：只有 pending 或 running 可以取消 ----
			if task.status not in ["pending", "running"]:
				raise ValueError(f"任务状态为 {task.status}，无法取消")

			# ---- 3. 发送取消信号（v1.3） ----
			cancel_event = self._active_cancellations.get(task_id)
			if cancel_event:
				cancel_event.set()
				logger.info(f"已发送取消信号: {task_id}")

		# ---- 4. 更新状态 ----
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

	# =========================================================================
	# 回测结果数据查询
	# =========================================================================

	async def get_backtest_equity_curve(self, task_id: str, user_id: str) -> List[Dict[str, Any]]:
		"""
		获取回测净值曲线数据。

		从 backtest_equity_curves 表读取时序净值数据，
		用于前端绘制净值走势图和回撤曲线。

		Args:
			task_id: 回测任务 ID。
			user_id: 当前登录用户 ID，用于权限校验。

		Returns:
			净值曲线列表，每项包含：
			- date: 交易日（trade_date）
			- equity: 当日净值（float）
			- drawdown: 回撤（当前固定为 0.0，模型暂无该字段）

		Raises:
			ValueError: 任务不存在或用户无权限访问。
		"""
		try:
			# ---- 1. 权限校验 ----
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			# ---- 2. 获取净值曲线数据 ----
			equity_curves = await self.equity_curve_repo.get_equity_curve(task_id)


			# ---- 3. 格式化 + 滚动计算回撤 ----
			data = []
			peak = 0.0
			for curve in equity_curves:
				eq = float(curve.equity)
				if eq > peak:
					peak = eq
				dd = (peak - eq) / peak if peak > 0 else 0.0
				data.append({
					"trade_date": curve.trade_date,
					"equity": eq,
					"drawdown": round(dd, 4),
				})

			return data
		except Exception as e:
			logger.error(f"获取回测净值曲线失败: {str(e)}")
			raise

	async def get_backtest_trades(self, task_id: str, user_id: str,
		                               page: int = 1, page_size: int = 20) -> Dict[str, Any]:
		"""
		获取回测交易记录列表。

		从 backtest_trades 表读取交易记录（支持分页）。

		Args:
			task_id: 回测任务 ID。
			user_id: 当前登录用户 ID，用于权限校验。

		Returns:
			{
				"data": [{
					id, symbol, side, price, volume, datetime,
					profit: 0.0,  # NOTE: BacktestTrade 模型暂无利润字段
					profit_pct: 0.0
				}, ...],
				"pagination": { page, page_size, total }
			}

		Raises:
			ValueError: 任务不存在或用户无权限访问。
		"""
		try:
			# ---- 1. 权限校验 ----
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			# ---- 2. 获取交易记录（v3.3: 优先从规范化表 backtest_trades 读取（JSONB 不再含明细）） ----
			data = []
			if task.result and task.result.get("trades"):
				for t in task.result["trades"]:
					data.append({
						"id": t.get("trade_id", ""),
						"symbol": t.get("ts_code", ""),
						"side": t.get("direction", ""),
						"price": float(t.get("price", 0)),
						"volume": int(t.get("quantity", 0)),
						"datetime": t.get("trade_date", ""),
						"commission": float(t.get("commission", 0)),
						"stamp_tax": float(t.get("stamp_tax", 0)),
						"transfer_fee": float(t.get("transfer_fee", 0)),
						"amount": float(t.get("amount", 0)),
						"profit": 0.0,  # FIFO PnL 需 v1.4 合并
						"profit_pct": 0.0,
					})
			else:
				# 回退到 backtest_trades 表
				trades = await self.trade_repo.get_by_task_id(task_id)
				for trade in trades:
					data.append({
						"id": trade.id,
						"symbol": trade.ts_code,
						"side": trade.direction,
						"price": float(trade.price),
						"volume": trade.volume,
						"datetime": trade.trade_time,
						"profit": 0.0,
						"profit_pct": 0.0,
					})

			total = len(data)
			start = (page - 1) * page_size
			end = start + page_size
			return {
				"data": data[start:end],
				"pagination": {
					"page": page,
					"page_size": page_size,
					"total": total,
					"total_pages": max(1, (total + page_size - 1) // page_size),
				},
			}
		except Exception as e:
			logger.error(f"获取回测交易记录失败: {str(e)}")
			raise

	async def get_backtest_positions(self, task_id: str, trade_date: str, user_id: str) -> List[Dict[str, Any]]:
		"""
		获取指定交易日的持仓快照。

		从 backtest_positions 表读取某一天的持仓数据。

		Args:
			task_id: 回测任务 ID。
			trade_date: 交易日期字符串（格式：YYYY-MM-DD）。
			user_id: 当前登录用户 ID，用于权限校验。

		Returns:
			持仓快照列表，每项包含：
			- symbol: 股票代码
			- volume: 持仓数量
			- cost_price: 成本价（float）
			- current_price: 当前价（当前固定为 0.0，模型可能无此字段）
			- profit / profit_pct: 盈亏（当前固定为 0.0）

		Raises:
			ValueError: 任务不存在或用户无权限访问。
		"""
		try:
			# ---- 1. 权限校验 ----
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")

			# ---- 2. 日期解析 ----
			from datetime import datetime
			trade_date_obj = datetime.strptime(trade_date, "%Y-%m-%d").date()

			# ---- 3. 获取持仓快照 ----
			positions = await self.position_repo.get_daily_positions(
				task_id=task_id,
				trade_date=trade_date_obj
			)

			# ---- 4. 格式化 ----
			data = []
			for position in positions:
				data.append({
					"symbol": position.ts_code,
					"volume": position.volume,
					"cost_price": float(position.cost_price),
					"current_price": 0.0,  # NOTE: BacktestPosition 模型中可能没有 current_price 字段
					"profit": 0.0,  # NOTE: BacktestPosition 模型中可能没有 profit 字段
					"profit_pct": 0.0  # NOTE: BacktestPosition 模型中可能没有 profit_pct 字段
				})

			return data
		except Exception as e:
			logger.error(f"获取回测持仓快照失败: {str(e)}")
			raise

	async def get_backtest_result(self, task_id: str, user_id: str) -> Dict[str, Any]:
		"""
		获取回测结果（绩效指标汇总）。

		从 backtest_tasks.result JSON 字段读取已完成回测的核心指标：
		总收益率、夏普比率、最大回撤、胜率、交易笔数等。

		约束：仅 completed 状态的任务可返回结果，其他状态抛出异常。

		Args:
			task_id: 回测任务 ID。
			user_id: 当前登录用户 ID，用于权限校验。

		Returns:
			回测结果字典（BacktestResult.to_dict() 的输出），包含：
			- total_return: 总收益率
			- annual_return: 年化收益率
			- sharpe_ratio: 夏普比率
			- max_drawdown: 最大回撤
			- win_rate: 胜率
			- num_trades: 交易笔数
			- ... 等绩效指标

		Raises:
			ValueError: 任务不存在 / 无权限 / 任务未完成。
		"""
		try:
			# ---- 1. 权限校验 ----
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if task.user_id != user_id:
				raise ValueError("无权限访问该回测任务")
			# ---- 2. 返回结果（completed=绩效, failed=错误信息, 其他=进行中状态） ----
			if task.status == "completed":
				result = task.result or {}
				# 基建设计 §二：旧任务 result 无增强指标 → 用 result 内既有数据补算（无需重跑回测）
				return self._enrich_extra_metrics(result)
			if task.status == "failed":
				return task.result or {"error": "回测执行失败，未获取到错误详情"}
			# 任务进行中（running/pending/cancelled 等），正常返回状态信息，不抛异常
			return {
				"status": task.status,
				"message": f"任务状态为 {task.status}，尚未完成",
				"progress": task.progress if hasattr(task, "progress") and task.progress else None,
			}
		except Exception as e:
			logger.error(f"获取回测结果失败: {str(e)}")
			raise

	def _enrich_extra_metrics(self, result: Dict[str, Any]) -> Dict[str, Any]:
		"""基建设计 §二：旧任务 result 补算 5 个增强指标（数据在 result 内，无需重跑回测）。

		新回测（BacktestResult.to_dict() 已含新字段）直接返回；旧任务缺字段时，
		复用 backtest_engine 的纯计算函数从 equity_curve / drawdown_curve /
		monthly_returns / trades 计算填充。
		"""
		if not isinstance(result, dict) or "calmar_ratio" in result:
			return result
		try:
			from modules.backtest.engines.backtest_engine import (
				_calc_avg_holding_days,
				_calc_max_consecutive_losses,
				_calc_max_drawdown_period,
				_calc_yearly_returns,
			)
			out = dict(result)
			annual = float(result.get("annual_return", 0) or 0)
			mdd = abs(float(result.get("max_drawdown", 0) or 0))
			out["calmar_ratio"] = round(annual / mdd, 4) if mdd >= 1e-6 else 0.0
			out["yearly_returns"] = _calc_yearly_returns(result.get("equity_curve") or [])
			out["max_drawdown_period"] = _calc_max_drawdown_period(result.get("drawdown_curve") or [])
			out["max_consecutive_losses"] = _calc_max_consecutive_losses(result.get("monthly_returns") or [])
			out["avg_holding_days"] = _calc_avg_holding_days(result.get("trades") or [])
			return out
		except Exception as e:
			logger.warning(f"旧任务 result 补算增强指标失败（返回原始结果）: {e}")
			return result

	# =========================================================================
	# 回测执行核心
	# =========================================================================

	async def run_backtest(self, task_id: str) -> None:
		"""
		执行回测任务（v1.2：新版 BacktestEngine.run() 编排链路）。

		这是回测模块的核心执行方法。由 FastAPI BackgroundTasks 异步调用，
		在独立的后台协程中运行，不阻塞 HTTP 响应。

		┌─────────────────────────────────────────────────────────────────┐
		│ 执行流程（共 8 步）：                                              │
		│                                                                   │
		│ Step 1: 建立独立 DB 会话                                          │
		│   └─ 请求 handler 的 session 已关闭，需创建新 session              │
		│                                                                   │
		│ Step 2: 更新任务状态 → "running"                                  │
		│                                                                   │
		│ Step 3: 加载回测配置                                               │
		│   └─ 合并 task.config JSON + backtest_parameters 表参数            │
		│                                                                   │
		│ Step 4: 延迟初始化引擎链                                           │
		│   └─ _init_engines(): DataFeed → StrategyManager → Broker          │
		│                                                                   │
		│ Step 5: 动态加载策略类                                             │
		│   └─ _load_strategy_class(): importlib 导入 → exec 沙箱回退        │
		│                                                                   │
		│ Step 6: 注册 & 启动策略                                            │
		│   ├─ register_strategy_class() → StrategyManager                  │
		│   ├─ load_strategy() → 创建策略实例                                │
		│   └─ start_strategy() → 创建 StrategyContext + 初始化股票池        │
		│                                                                   │
		│ Step 7: 解析股票池（三级优先级）                                    │
		│   ├─ ① 回测配置 symbols（直接指定）                                │
		│   ├─ ② 策略自身 universe（on_start 从 DB 加载）                    │
		│   └─ ③ 全市场兜底 1000 只（⚠ 仅用于语法验证，不具策略参考意义）    │
		│                                                                   │
		│ Step 8: BacktestEngine.run() → 遍历交易日 → handle_bar_batch       │
		│   └─ 保存 BacktestResult 到 backtest_tasks.result                 │
		└─────────────────────────────────────────────────────────────────┘

		Args:
			task_id: 回测任务 ID（UUID 字符串）。

		Raises:
			ValueError: 任务不存在、策略不存在、股票池为空等。
			其他异常将被捕获，更新任务状态为 "failed" 并记录错误信息。

		Note:
			- 该方法设计为由 FastAPI BackgroundTasks 调用，不直接返回结果。
			  结果通过 backtest_tasks.result 字段异步获取。
			- finally 块确保 DB 会话被关闭，防止连接泄漏。
		"""
		start_ts = datetime.now()
		try:
			# =================================================================
			# Step 1: 创建独立 DB 会话
			#
			# 背景任务运行在独立协程中，原始 HTTP 请求的 session 已在响应
			# 返回后关闭。必须通过连接池获取新的 session factory 来创建会话。
			# =================================================================
			from shared.database.session.connection_pool import get_connection_pool

			_session_factory = get_connection_pool().get_session_factory()
			self.db = _session_factory()
			self.task_repo = BacktestTaskRepository(self.db)
			self.strategy_repo = StrategyRepository(self.db)
			self.param_repo = StrategyParameterRepository(self.db)
			self.trade_repo = BacktestTradeRepository(self.db)
			self.position_repo = BacktestPositionRepository(self.db)
			self.equity_curve_repo = BacktestEquityCurveRepository(self.db)

			# =================================================================
			# Step 2: 更新任务状态 → "running"
			# =================================================================
			task = await self.task_repo.update(task_id, {
				"status": "running",
				"updated_at": datetime.now()
			})
			await self.db.commit()

			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")

			# ---- 获取关联策略 ----
			strategy = await self.strategy_repo.get_by_id(task.strategy_id)
			if not strategy:
				raise ValueError(f"策略不存在: {task.strategy_id}")

			# =================================================================
			# Step 3: 加载回测配置（合并 task.config + backtest_parameters）
			# =================================================================
			config = await self._load_backtest_config(task)

			logger.info(
				f"回测 {task_id}: 开始 — 策略={strategy.name}, "
				f"日期={config.get('start_date')}~{config.get('end_date')}, "
				f"初始资金={float(config.get('initial_capital', 1_000_000)):,.0f}"
			)

			# =================================================================
			# Step 4: 延迟初始化引擎链
			#
			# 仅在真正执行回测时初始化重量级引擎。
			# GET /tasks/{id} 等只读请求不会触发此初始化。
			# =================================================================
			self._init_engines(db=self.db)

			# =================================================================
			# Step 5: 动态加载策略类
			#
			# 双路径策略：
			#   - 路径 A（生产环境）：importlib 模块导入
			#   - 路径 B（用户策略）：exec 沙箱执行策略代码字符串
			# 详见 _load_strategy_class() 方法。
			# =================================================================
			strategy_class = await self._load_strategy_class(strategy)
			logger.info(
				f"回测 {task_id}: 策略类加载完成 — "
				f"{getattr(strategy_class, '__name__', str(strategy_class))}"
			)

			# =================================================================
			# Step 6a: 注册策略类到 StrategyManager
			#
			# 将策略类注册到全局策略注册表，使 Manager 可通过 StrategyType.CUSTOM
			# 查找到对应的策略类。
			# =================================================================
			self.strategy_manager.register_strategy_class(
				StrategyType.CUSTOM, strategy_class
			)

			# ---- 获取策略参数 ----
			parameters = await self._get_strategy_params(task.strategy_id)
			# 修复 2026-08（P1-4A）: 合并 backtest_parameters 中 strategy 类覆写参数。
			# 此前 create_backtest_task 将请求 strategy_params 写入 backtest_parameters，
			# 但此处只读 strategy_parameters 表 → 请求级参数覆写被静默忽略（死代码路径）。
			# 合并顺序：strategy_parameters 表值 → backtest 任务覆写（后者优先）。
			try:
				from shared.database.repositories.strategy.backtest.parameter_repo import \
					BacktestParameterRepository
				_bp_repo = BacktestParameterRepository(self.db)
				_strategy_overrides = await _bp_repo.get_parameters_by_category(task.id, "strategy")
				if _strategy_overrides:
					parameters.update(_strategy_overrides)
					logger.info(
						f"回测 {task_id}: 合并 {len(_strategy_overrides)} 个策略参数覆写 "
						f"({sorted(_strategy_overrides.keys())})"
					)
			except Exception as _pe:
				logger.warning(f"回测 {task_id}: 读取策略参数覆写失败: {_pe}")
			# v2.5: 单策略回测时，用 initial_capital 覆盖 DB 中的 allocated_capital，
			# 避免策略仅部署少量资金而闲置大部分本金。
			_initial_cap = float(config.get('initial_capital', 1_000_000))
			if parameters and 'allocated_capital' in parameters:
				_db_alloc = parameters.get('allocated_capital')
				if _db_alloc and float(_db_alloc) != _initial_cap:
					logger.info(
						f"回测 {task_id}: allocated_capital 从 DB 值 {_db_alloc} "
						f"覆盖为 initial_capital {_initial_cap}"
					)
				parameters['allocated_capital'] = _initial_cap
			if parameters:
				logger.info(f"回测 {task_id}: 策略参数 — {parameters}")

			# =================================================================
			# Step 6b: 构建策略配置 → 加载策略实例到 Manager
			#
			# StrategyConfigModel 包含交易成本等核心参数，与 BacktestBrokerConfig
			# 保持一致。
			# =================================================================
			strategy_config = StrategyConfigModel(
				name=strategy.name,
				initial_capital=_initial_cap,
				commission_rate=float(config.get('commission_rate', 0.0001)),
				slippage=float(config.get('slippage_rate', 0.0001)),
			)

			# 修复 2026-08（C9）：执行时优先用版本快照代码（此前记录快照却执行当前代码，回测不可复现）
			_exec_code = strategy.code
			if getattr(task, "strategy_version_id", None):
				try:
					from shared.database.repositories.strategy.management.strategy_version_repo import (
						StrategyVersionRepository,
					)
					_vrepo = StrategyVersionRepository(self.db)
					_ver = await _vrepo.get(str(task.strategy_version_id))
					if _ver and getattr(_ver, "code_content", None):
						_exec_code = _ver.code_content
					else:
						logger.warning("版本快照无代码内容，回退当前代码: %s", task.strategy_id)
				except Exception as _ver_e:
					logger.warning("读取版本快照失败，回退当前代码: %s", _ver_e)

			await self.strategy_manager.load_strategy(
				strategy_id=task.strategy_id,
				name=strategy.name,
				strategy_type=StrategyType.CUSTOM,
				code=_exec_code,
				parameters=parameters,
				config=strategy_config,
			)

			# =================================================================
			# Step 6c: 启动策略 — 创建 StrategyContext + 注入回调
			#
			# on_start 会初始化策略自身的股票池（_universe），
			# 此操作需要先于数据加载执行，确保后续 Step 7 能从策略对象
			# 读取 universe 作为股票池来源。
			# =================================================================
			context = StrategyContext(
				strategy_id=task.strategy_id,
				strategy_name=strategy.name,
				user_id=task.user_id,
				run_mode=RunMode.BACKTEST,
				initial_capital=float(config.get('initial_capital', 1_000_000)),
				commission_rate=float(config.get('commission_rate', 0.0001)),
				slippage=float(config.get('slippage_rate', 0.0001)),
			)
			_warmup_end = config.get('start_date') and datetime.strptime(config['start_date'], "%Y-%m-%d").date()
			await self.strategy_manager.start_strategy(task.strategy_id, context, warmup_end_date=_warmup_end)

			# 2026-08 修复：回测市场数据预加载 — 对声明 BACKTEST_PRELOAD_STATE 的策略
			# （恐慌抄底/微盘等纯数据预加载型）调用 load_live_state，注入恐慌指数/指数/市值等
			# 回测所需数据（否则状态机第一道门被空映射拦截 → 全程 0 信号）。
			_sat_obj = self.strategy_manager.get_strategy_object(task.strategy_id)
			if _sat_obj and getattr(_sat_obj, "BACKTEST_PRELOAD_STATE", False):
				_bt_start = config.get('start_date')
				await _sat_obj.load_live_state(self.db, strategy_id=str(task.strategy_id), start_date=_bt_start)
				logger.info(
					f"回测 {task_id}: {_sat_obj.name} 市场数据预加载完成 "
					f"(回测窗口 start_date={_bt_start})"
				)

			# =================================================================
			# Step 7: 解析股票池（三级优先级降级策略）
			#
			# 优先级 ① > ② > ③：
			#   ① 回测配置中显式指定的 symbols 列表
			#   ② 策略 on_start 中从 DB 加载的 _universe（策略自身股票池）
			#   ③ 全市场前 1000 只兜底（⚠ 仅用于快速验证代码无语法错误，
			#      回测结果不代表策略真实表现！）
			# =================================================================
			symbols = config.get('symbols', [])
			symbol_source = "回测配置"

			if not symbols:
				# 尝试从回测配置的 ts_code 字段获取单只股票
				ts_code = config.get('ts_code', '')
				if ts_code:
					symbols = [ts_code]
					symbol_source = "回测配置 ts_code"

			if not symbols:
				# 策略自身定义了股票池（on_start 已从 DB 加载到 _universe）
				strategy_obj = self.strategy_manager.get_strategy_object(task.strategy_id)
				if strategy_obj and strategy_obj.universe:
					symbols = strategy_obj.universe
					symbol_source = "策略股票池"

			# v2.5: 若策略 universe 含 ETF 标的，自动注入 SW L1 行业指数代码，
			# 确保 data_feed_engine 加载行业日线数据用于因子评分。
			# 此逻辑独立于 DB 中可能过期的策略代码，解决策略更新后
			# DB code 不同步导致 _industry_data_cache 为空的问题。
			if symbols:
				_has_etf = any(
					s.split(".")[0][:2] in ("51", "56", "58") or
					s.split(".")[0][:3] in ("159", "16")
					for s in symbols
				)
				if _has_etf:
					from modules.strategy.config.industry_etf_map import SW_L1_INDUSTRY_CODES
					sw_codes = [c for c in SW_L1_INDUSTRY_CODES if c not in symbols]
					if sw_codes:
						symbols = list(symbols) + sw_codes
						logger.info(
							f"回测 {task_id}: 自动注入 {len(sw_codes)} 个 SW L1 行业指数代码"
						)

			if not symbols:
				# 兜底：取 stock_basic 全市场前 1000 只（防内存溢出）
				logger.warning(
					f"回测 {task_id}: 未配置股票池且策略未定义 universe，"
					f"使用全市场 1000 只兜底 — 回测结果不具有策略参考意义！"
				)
				try:
					from sqlalchemy import text
					db_result = await self.db.execute(
						text(
							"SELECT ts_code FROM stock_basic "
							"WHERE ts_code LIKE '0%' OR ts_code LIKE '3%' OR ts_code LIKE '6%' "
							"LIMIT 1000"
						)
					)
					symbols = [r[0] for r in db_result.fetchall()]
					symbol_source = "全市场兜底"
				except Exception:
					pass

			if not symbols:
				raise ValueError("股票代码不能为空，请在回测配置中添加股票或确保策略定义了股票池")

			logger.info(
				f"回测 {task_id}: 股票池来源={symbol_source}, "
				f"数量={len(symbols)}, 前5={symbols[:5]}"
			)

			# =================================================================
			# Step 8: 注入 DB 会话 → 执行回测 → 持久化结果
			# =================================================================
			self.backtest_engine.set_db_session(self.db)

			# v1.3: 注册取消事件（先创建再注入到引擎）
			cancel_event = asyncio.Event()
			self._active_cancellations[task_id] = cancel_event
			self.backtest_engine._cancel_event = cancel_event

			# ---- 执行新版回测引擎（v1.2 编排链路） ----
			logger.info(f'回测 {task_id}: benchmark={config.get("benchmark") or "000300.SH (default)"}')
			result: BacktestResult = await self.backtest_engine.run(
				task_id=task_id,
				strategy_id=task.strategy_id,
				symbols=symbols,
				start_date=config.get('start_date', ''),
				end_date=config.get('end_date', ''),
				initial_capital=float(config.get('initial_capital', 1000000)),
				parameters=parameters,
				commission_rate=float(config.get('commission_rate', 0.0001)),
				slippage=float(config.get('slippage_rate', 0.0001)),
				benchmark_ts_code=config.get('benchmark') or '000300.SH',
				# TODO: progress_callback 待 BacktestEngine 支持后启用
				#       用于通过 WebSocket 推送实时进度到前端
			)

			# ---- 保存回测结果到 backtest_tasks.result（JSON 字段） ----
			backtest_result = result.to_dict()
			await self.task_repo.update(task_id, {
				"status": "completed",
				"result": backtest_result,
				"updated_at": datetime.now()
			})
			await self.db.commit()  # v1.3: 显式提交状态更新

			elapsed = (datetime.now() - start_ts).total_seconds()
			logger.info(
				f"回测 {task_id}: 完成 — "
				f"总收益={result.total_return:.2%} "
				f"夏普={result.sharpe_ratio:.2f} "
				f"最大回撤={result.max_drawdown:.2%} "
				f"胜率={result.win_rate:.1%} "
				f"交易笔数={result.num_trades} "
				f"耗时={elapsed:.1f}s"
			)

		except asyncio.CancelledError:
			# =================================================================
			# 用户取消 — 标记任务为 cancelled
			# =================================================================
			elapsed = (datetime.now() - start_ts).total_seconds()
			logger.info(f"回测 {task_id}: 已取消 (耗时={elapsed:.1f}s)")
			try:
				await self.task_repo.update(task_id, {
					"status": "cancelled",
					"result": {"message": "用户取消"},
					"updated_at": datetime.now()
				})
				await self.db.commit()
			except Exception:
				await self.db.rollback()
		except Exception as e:
			# =================================================================
			# 异常处理：标记任务失败，记录错误信息
			# =================================================================
			elapsed = (datetime.now() - start_ts).total_seconds()
			logger.error(
				f"回测 {task_id}: 失败 — {e} (耗时={elapsed:.1f}s)",
				exc_info=True
			)
			try:
				# 更新任务状态为 failed，将异常信息存入 result
				await self.task_repo.update(task_id, {
					"status": "failed",
					"result": {"error": str(e)},
					"updated_at": datetime.now()
				})
				await self.db.commit()
			except Exception as e:
				# 如果连写入失败信息都失败了，回滚以免残留未提交事务
				await self.db.rollback()
		finally:
			# =================================================================
			# 资源清理：取消事件 + 关闭 DB 会话
			# =================================================================
			self._active_cancellations.pop(task_id, None)
			try:
				await self.db.close()
			except Exception:
				pass

	# =========================================================================
	# v1.2 辅助方法 — 供 run_backtest() 内部调用
	# =========================================================================

	async def _load_backtest_config(self, task) -> Dict[str, Any]:
		"""
		加载回测配置（合并 task.config JSON + backtest_parameters 表参数）。

		合并策略：
		1. 以 task.config JSON 为基础
		2. 从 backtest_parameters 表读取 market / cost / capital 三类参数
		3. 表参数覆盖 config 中的同名键（后者优先级更高）

		Args:
			task: 回测任务 ORM 对象（需包含 id 和 config 属性）。

		Returns:
			合并后的配置字典，包含 start_date, end_date, initial_capital,
			commission_rate, slippage_rate, symbols, ts_code 等键。
		"""
		config = dict(task.config or {})

		# v2.4: 提供合理默认值（config 中不再冗余存储 cost/capital 参数）
		config.setdefault("initial_capital", 1000000)
		config.setdefault("commission_rate", 0.0001)
		config.setdefault("slippage_rate", 0.0001)

		try:
			from shared.database.repositories.strategy.backtest.parameter_repo import \
				BacktestParameterRepository
			param_repo = BacktestParameterRepository(self.db)
			backtest_params = await param_repo.get_task_parameters(task.id)
			# 只合并市场、成本、资金类参数（策略参数在 _get_strategy_params 中单独处理）
			for param in backtest_params:
				if param.param_category in ('market', 'cost', 'capital'):
					config[param.param_name] = param.param_value
			logger.info(f"从backtest_parameters表获取配置: {len(backtest_params)} 个参数")
		except Exception as e:
			logger.warning(f"从backtest_parameters表获取配置失败，使用默认值: {e}")

		return config

	async def _load_strategy_class(self, strategy):
		"""
		动态加载策略类（双路径策略）。

		┌──────────────────────────────────────────────────────────────────┐
		│ 路径 A：importlib 模块导入（优先）                                │
		│   └─ 适用于标准策略，策略代码以 .py 文件形式存在于 modules/ 下    │
		│   └─ 使用 strategy.module_path + strategy.class_name 定位        │
		│                                                                   │
		│ 路径 B：exec 沙箱执行（回退）                                     │
		│   └─ 适用于用户通过 Web 编辑器创建的策略（代码存储在 DB 中）      │
		│   └─ exec 环境中注入以下依赖：                                    │
		│       - BaseStrategy（策略基类）                                 │
		│       - StrategyType, SignalDirection, TimeFrame（策略常量）     │
		│       - TradingSignal, Position（策略数据模型）                  │
		│       - BarData（K 线数据结构）                                  │
		│       - pd（pandas）, np（numpy）                                │
		│       - typing（类型标注支持）                                   │
		│   └─ 策略类匹配策略：                                            │
		│       ① 优先按 class_name 精确匹配 BaseStrategy 子类             │
		│       ② 回退到第一个 BaseStrategy 子类（兼容旧数据）              │
		└──────────────────────────────────────────────────────────────────┘

		Args:
			strategy: 策略 ORM 对象，需包含：
				- module_path: 策略模块路径（路径 A）
				- class_name: 策略类名
				- code: 策略源代码字符串（路径 B）

		Returns:
			策略类对象（type），是 BaseStrategy 的子类。

		Raises:
			ValueError: 模块导入失败、代码语法错误、缺少依赖模块、
					   或代码中未找到 BaseStrategy 子类。
		"""
		# =====================================================================
		# 路径 A：importlib 模块导入
		# 适用场景：策略代码是已安装的 Python 模块
		# =====================================================================
		try:
			module = importlib.import_module(strategy.module_path)
			strategy_class = getattr(module, strategy.class_name)
			logger.info(f"策略类加载成功 (import): {strategy.module_path}.{strategy.class_name}")
			return strategy_class
		except (ImportError, AttributeError, ValueError):
			# 模块导入失败，静默回退到 exec 路径
			pass

		# =====================================================================
		# 路径 B：exec 沙箱执行策略代码字符串
		#
		# 适用场景：用户通过 Web 编辑器创建的策略，代码存储在 DB 的 code 字段中。
		# exec 环境注入了策略开发所需的全部依赖，使用受限的 temp_module 字典
		# 隔离 exec 执行的副作用（不污染当前模块的全局命名空间）。
		# =====================================================================
		try:
			# ---- B1. 构建 exec 沙箱环境 ----
			from modules.strategy.strategies.base.base_strategy import BaseStrategy
			from datetime import datetime as _dt
			from modules.strategy.constants import StrategyType as ST, SignalDirection, TimeFrame, SignalType as SigType, RunMode
			from modules.strategy.models import TradingSignal, Position
			from core.engines.types.entities import BarData
			import numpy as np
			import logging as _logging

			# temp_module 是 exec 的全局命名空间字典，exec 执行后其中将包含策略类定义
			temp_module = {
				'logging': _logging,
				'logger': _logging.getLogger(__name__),
				'BaseStrategy': BaseStrategy,
				'StrategyType': ST,
				'SignalDirection': SignalDirection,
				'SignalType': SigType,
				'TimeFrame': TimeFrame,
				'RunMode': RunMode,
				'TradingSignal': TradingSignal,
				'Position': Position,
				'BarData': BarData,
				'pd': pd,
				'np': np,
				'datetime': _dt,
			}

			# 注入 typing 模块，避免用户在代码中使用 "import List" 等错误写法时
			# 因找不到模块而报 ModuleNotFoundError（常见误写会在下方捕获并给出提示）
			import typing as _typing
			temp_module["typing"] = _typing
			# v2.4: 注入常用 typing 名称，避免策略代码中裸用 Optional 报 NameError
			for _tname in ("Optional", "List", "Dict", "Tuple", "Set", "Union", "Any", "Callable", "Type"):
				if hasattr(_typing, _tname):
					temp_module[_tname] = getattr(_typing, _tname)

			# v2.5: 注入策略专用依赖（兜底：防止旧策略代码仅含类体、缺少 import 导致 NameError）
			try:
				from modules.strategy.services.industry_scoring_service import (
					IndustryScore, IndustryScoringService, ScoringConfig,
				)
				temp_module["IndustryScore"] = IndustryScore
				temp_module["IndustryScoringService"] = IndustryScoringService
				temp_module["ScoringConfig"] = ScoringConfig
			except ImportError:
				pass
			try:
				from modules.strategy.services.etf_industry_mapper import (
					EtfIndustryMapper, EtfSelection,
				)
				temp_module["EtfIndustryMapper"] = EtfIndustryMapper
				temp_module["EtfSelection"] = EtfSelection
			except ImportError:
				pass
			try:
				from modules.strategy.enums.sector_groups import get_sector
				temp_module["get_sector"] = get_sector
			except ImportError:
				pass

			# v2.4: exec() 沙箱加固 — 全量 builtins，仅移除危险函数
			import builtins as _b
			temp_module["__builtins__"] = dict(vars(_b))
			for _danger in ("eval", "exec", "compile", "open", "input", "breakpoint"):
				temp_module["__builtins__"].pop(_danger, None)
			# v2.6: 使用正确的模块路径，确保策略日志能传播到 root 的文件 handler
			temp_module["__builtins__"]["__name__"] = "modules.strategy.strategies.custom"

			# ---- B2. 执行策略代码 ----
			# v2.5: 若策略代码不含 from __future__ import annotations，
			# 则自动注入，避免类型注解（如 List[IndustryScore]）引发 NameError
			_code_to_exec = strategy.code or ""
			if "from __future__" not in _code_to_exec[:200]:
				_code_to_exec = "from __future__ import annotations\n" + _code_to_exec
			try:
				exec(_code_to_exec, temp_module)
				# 确保 exec 后 logger/logging 可用
				if "logging" not in temp_module:
					temp_module["logging"] = _logging
				if "logger" not in temp_module:
					temp_module["logger"] = _logging.getLogger("strategy")
			except ModuleNotFoundError as e:
				# 策略代码中 import 了 exec 沙箱未提供的模块
				missing = e.name or str(e)
				# 常见误写提示 — 帮助用户快速定位问题
				_typing_names = {"Any", "List", "Dict", "Optional", "Tuple", "Set", "Union", "Type", "Callable"}
				if missing in _typing_names:
					hint = (
						f"（'{missing}' 不是模块名，它是 typing 库中的类型。"
						f"请将 'import {missing}' 改为 'from typing import {missing}'）"
					)
				elif missing == "jqdata":
					hint = (
						"（该代码来源为聚宽平台，使用了 jqdata SDK。"
						"jqdata 是聚宽专有模块，无法在本地回测引擎中运行"
						"）"
					)
				else:
					hint = ""
				raise ValueError(f"缺少依赖模块: {missing}{hint}") from e
			except SyntaxError as e:
				raise ValueError(f"策略代码语法错误: {e}") from e

			# ---- B3. 从 temp_module 中提取策略类 ----
			#
			# 匹配策略（两级回退）：
			#   ① 精确匹配：类名 = strategy.class_name 的 BaseStrategy 子类
			#   ② 模糊回退：任意第一个 BaseStrategy 子类（兼容旧数据中 class_name 不匹配的情况）
			#

			# 优先：按 class_name 精确匹配
			for name, obj in temp_module.items():
				if (
						isinstance(obj, type)
						and _is_strategy_subclass(obj)
						and name == strategy.class_name
				):
					logger.info(f"策略类加载成功 (exec): {strategy.class_name}")
					return obj

			# 回退：返回第一个找到的 BaseStrategy 子类
			for name, obj in temp_module.items():
				if isinstance(obj, type) and _is_strategy_subclass(obj):
					logger.info(f"策略类加载成功 (exec, fallback): {name}")
					return obj

			# 未找到任何 BaseStrategy 子类
			raise ValueError("策略代码中未找到继承 BaseStrategy 的策略类")
		except Exception as e:
			logger.error(f"加载策略失败: {e}")
			raise

	async def _get_strategy_params(self, strategy_id: str) -> Dict[str, Any]:
		"""
		获取策略参数（从 strategy_parameters 表）。

		将参数列表转换为 {param_name: param_value} 字典，便于
		StrategyManager.load_strategy() 和 BacktestEngine.run() 使用。

		Args:
			strategy_id: 策略 ID（UUID 字符串）。

		Returns:
			参数字典，如 {"ma_short": 5, "ma_long": 20}。
			未找到参数时返回空字典 {}。
		"""
		try:
			params_list = await self.param_repo.get_by_strategy_id(strategy_id)
			params = {}
			for p in params_list:
				val = p.param_value
				if isinstance(val, str) and (val.startswith('[') or val.startswith('{')):
					try:
						import json
						val = json.loads(val)
					except json.JSONDecodeError:
						pass
				params[p.param_name] = val
			logger.info(f"获取策略参数: {len(params)} 个")
			return params
		except Exception as e:
			logger.warning(f"获取策略参数失败: {e}")
			return {}

	# =========================================================================
	# 回测任务删除与报告导出
	# =========================================================================

	async def delete_backtest_task(self, task_id: str, user_id: str) -> None:
		"""
		删除回测任务（级联删除关联数据）。

		删除顺序：
		1. 级联删除关联数据（忽略各步骤异常，尽力删除）：
		   - backtest_equity_curves（净值曲线）
		   - backtest_trades（交易记录）
		   - backtest_positions（持仓快照）
		   - backtest_parameters（回测参数）
		2. 删除主记录（backtest_tasks）

		Args:
			task_id: 回测任务 ID。
			user_id: 当前登录用户 ID，用于权限校验。

		Raises:
			ValueError: 任务不存在或用户无权限删除。
		"""
		try:
			# ---- 1. 权限校验 ----
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if hasattr(task, 'user_id') and task.user_id != user_id:
				raise ValueError("无权限删除该回测任务")

			# ---- 2. cascade delete child records (raw SQL) ----
			from sqlalchemy import text
			for tbl in ["backtest_equity_curves", "backtest_trades", "backtest_positions", "backtest_parameters"]:
				await self.db.execute(text(f"DELETE FROM {tbl} WHERE task_id = :tid"), {"tid": task_id})

			# ---- 3. delete main record ----
			await self.task_repo.delete(task_id)
			logger.info(f"回测任务已删除: {task_id}")

		except Exception as e:
			logger.error(f"删除回测任务失败: {e}")
			raise

	async def export_report(self, task_id: str, user_id: str, report_format: str = 'json') -> Dict[str, Any]:
		"""
		导出回测报告。

		支持的导出格式：
		- json（默认）：直接返回 task.result 原始 JSON
		- csv：将 equity_curve 数据转换为 CSV 字符串

		Args:
			task_id: 回测任务 ID。
			user_id: 当前登录用户 ID，用于权限校验。
			report_format: 导出格式，可选 "json" 或 "csv"，默认 "json"。

		Returns:
			- JSON 格式：直接返回原始结果字典
			- CSV 格式：{"format": "csv", "content": "<CSV 字符串>"}

		Raises:
			ValueError: 任务不存在或用户无权限。
		"""
		try:
			# ---- 1. 权限校验 ----
			task = await self.task_repo.get(task_id)
			if not task:
				raise ValueError(f"回测任务不存在: {task_id}")
			if hasattr(task, 'user_id') and task.user_id != user_id:
				raise ValueError("无权限")

			result_data = task.result or {}

			# ---- 2. 按格式导出 ----
			if report_format == 'json':
				return result_data
			elif report_format == 'csv':
				# 生成 CSV 格式的净值曲线数据
				import io, csv as csv_mod
				output = io.StringIO()
				writer = csv_mod.writer(output)
				# CSV 表头
				writer.writerow(['trade_date', 'total_assets', 'cumulative_return', 'max_drawdown'])
				# CSV 数据行
				for row in result_data.get('equity_curve', []):
					writer.writerow([
						row.get('trade_date', ''),
						row.get('total_assets', 0),
						row.get('cumulative_return', 0),
						row.get('max_drawdown', 0)
					])
				return {"format": "csv", "content": output.getvalue()}
			else:
				# 不支持的格式，回退到 JSON
				return result_data
		except Exception as e:
			logger.error(f"导出报告失败: {e}")
			raise

	# =========================================================================
	# 快速回测与参数优化
	# =========================================================================

	async def quick_backtest(self, request, user_id: str) -> Dict[str, Any]:
		"""
		快速回测：一步完成「创建任务 → 执行回测 → 返回结果」。

		与标准回测的区别：
		- 标准回测：create → 放入 BackgroundTasks 队列 → 前端轮询结果
		- 快速回测：同步执行，直接返回结果（适用于策略编辑器中的即时验证）

		流程：
		1. 生成临时任务 ID（quick_{uuid}）
		2. 调用 create_backtest_task() 创建任务记录
		3. 同步调用 run_backtest() 执行回测（不放入后台队列）
		4. 读取并返回执行结果

		Args:
			request: 回测创建请求（与标准回测相同的 schema）。
			user_id: 当前登录用户 ID。

		Returns:
			回测结果字典（BacktestResult.to_dict() 的输出）。

		Raises:
			ValueError: 任务创建失败或回测执行异常。
		"""
		try:
			# ---- 1. 创建临时任务 ----
			import uuid
			temp_task_id = f"quick_{uuid.uuid4().hex[:12]}"
			request.name = getattr(request, 'name', f"快速回测_{temp_task_id[:8]}")

			create_result = await self.create_backtest_task(request, user_id)

			# ---- 2. 同步执行回测（不放入后台任务，当前协程阻塞等待） ----
			await self.run_backtest(create_result.get('task_id', temp_task_id))

			# ---- 3. 读取结果 ----
			task = await self.task_repo.get(create_result.get('task_id'))
			if not task:
				raise ValueError("回测任务创建后丢失")

			return task.result or {}
		except Exception as e:
			logger.error(f"快速回测失败: {e}")
			raise

	async def optimize_parameters(self, request) -> Dict[str, Any]:
		"""
		参数优化 — 委托给 OptimizationEngine 执行。

		支持三种优化方法（由 OptimizationEngine 实现）：
		- grid_search: 网格搜索（暴力穷举参数组合）
		- genetic_algorithm: 遗传算法（进化搜索）
		- bayesian_optimization: 贝叶斯优化（概率模型引导搜索）

		Args:
			request: 参数优化请求（OptimizationRequest schema），包含：
				- strategy_id: 策略 ID
				- parameters: 待优化参数及其取值范围
				  e.g. {"ma_short": [5, 10, 20], "ma_long": [30, 60, 120]}
				- optimization_method: 优化方法（"grid_search" | "genetic_algorithm" | "bayesian_optimization"）

		Returns:
			{
				"task_id": str,  # 基于时间戳生成的临时 ID
				"result": { ... }  # OptimizationEngine 返回的优化结果
			}
		"""
		try:
			# ---- 委托给 OptimizationEngine 执行参数优化 ----
			result = await self.optimization_engine.optimize(
				strategy_id=request.strategy_id,
				parameters=request.parameters,
				method=request.optimization_method
			)

			logger.info(f"参数优化完成: {request.strategy_id}")

			# ---- 生成任务 ID（基于时间戳，用于追踪） ----
			import time
			task_id = str(int(time.time() * 1000))

			return {
				"task_id": task_id,
				"result": result
			}
		except Exception as e:
			logger.error(f"参数优化失败: {str(e)}")
			raise

	# =========================================================================
	# v3.3: 独立场景回测 + 晋升逻辑
	# =========================================================================

	async def run_scenario(
		self, user_id, name, code, parameters=None, config=None,
		template_id=None, source_strategy_id=None,
	):
		"""独立场景回测：不依赖策略，直接用代码+参数运行回测。"""
		try:
			from shared.database.repositories.strategy.backtest.scenario_repo import BacktestScenarioRepository
			scenario_repo = BacktestScenarioRepository(self.db)
			scenario = await scenario_repo.create({
				"scenario_name": name, "code": code,
				"parameters": parameters or {}, "market_conditions": config or {},
				"template_id": template_id, "source_strategy_id": source_strategy_id,
				"created_by": user_id, "status": "draft", "created_at": datetime.now(),
			})
			await self.db.commit()
			task = await self.task_repo.create({
				"name": name, "scenario_id": scenario.id,
				"config": config or {}, "status": "pending",
				"user_id": user_id, "created_at": datetime.now(),
			})
			await self.db.commit()
			return {"scenario_id": scenario.id, "task_id": task.id}
		except Exception as e:
			logger.error(f"场景回测创建失败: {e}")
			raise

	async def promote_scenario_to_strategy(self, scenario_id, user_id, strategy_name=None):
		"""场景晋升为策略"""
		try:
			import re as _re
			from shared.database.repositories.strategy.backtest.scenario_repo import BacktestScenarioRepository
			from shared.database.repositories.strategy.management.strategy_repo import StrategyRepository
			from shared.database.repositories.strategy.management.strategy_parameter_repo import StrategyParameterRepository
			from shared.database.repositories.strategy.management.strategy_version_repo import StrategyVersionRepository
			from modules.strategy.constants import StrategyType
			scenario_repo = BacktestScenarioRepository(self.db)
			scenario = await scenario_repo.get_by_id(scenario_id)
			if not scenario:
				return {"success": False, "error": "场景不存在"}
			m = _re.search(r'class\s+(\w+)\s*\(', scenario.code or '')
			class_name = m.group(1) if m else "CustomStrategy"
			strategy_repo = StrategyRepository(self.db)
			strategy = await strategy_repo.create({
				"name": strategy_name or getattr(scenario, "scenario_name", name) or "未命名",
				"code": scenario.code, "class_name": class_name,
				"module_path": f"strategies.user_{user_id}.{class_name.lower()}",
				"strategy_type": StrategyType.CUSTOM.value,
				"status": "backtested", "user_id": user_id,
				"promoted_from_scenario_id": scenario_id,
				"created_at": datetime.now(), "updated_at": datetime.now(),
			})
			params = scenario.parameters or {}
			param_repo = StrategyParameterRepository(self.db)
			for key, value in params.items():
				await param_repo.create({"strategy_id": strategy.id, "param_name": key,
					"param_type": type(value).__name__, "param_value": value})
			version_repo = StrategyVersionRepository(self.db)
			await version_repo.create({"strategy_id": strategy.id, "version_number": "1.0.0",
				"code_content": scenario.code or "", "parameters": params,
				"is_current": True, "description": f"从场景 {scenario_id} 晋升", "created_at": datetime.now()})
			from sqlalchemy import update as _up, text as _txt
			await self.db.execute(_up(_txt("backtest_tasks")).where(_txt("scenario_id = :sid"))
				.values(strategy_id=strategy.id), {"sid": scenario_id})
			await scenario_repo.update_by({"id": scenario_id}, {"status": "promoted"})
			await self.db.commit()
			return {"success": True, "strategy_id": strategy.id}
		except Exception as e:
			logger.error(f"场景晋升失败: {e}")
			await self.db.rollback()
			raise


	# =========================================================================
	# 静态工具方法
	# =========================================================================


