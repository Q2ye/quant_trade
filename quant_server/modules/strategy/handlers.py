# -*- coding: utf-8 -*-
"""
策略模块API处理函数
负责处理HTTP请求，调用服务层完成业务逻辑
"""
import logging
from datetime import datetime
from typing import Dict, Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.strategy.constants import (
	StrategyType,
	StrategyLifecycleStatus,
)
from modules.strategy.services.execution_service import ExecutionService
from modules.strategy.services.strategy_service import StrategyService

logger = logging.getLogger(__name__)


class StrategyHandler:
	"""策略API处理器"""

	def __init__ (self, db: AsyncSession, event_engine=None):
		self.db = db
		self.event_engine = event_engine
		self.strategy_service = StrategyService(db)
		self.execution_service = ExecutionService(db, event_engine=event_engine)

	async def get_strategy_list (
			self,
			request,
			user_id: str
	) -> Dict[str, Any]:
		"""
		获取策略列表

		Args:
			request: 请求参数
			user_id: 用户ID

		Returns:
			策略列表
		"""
		try:
			# 转换状态
			status = None
			if hasattr(request, 'status') and request.status:
				try:
					status = StrategyLifecycleStatus(request.status)
				except ValueError:
					pass

			# 转换策略类型
			strategy_type = None
			if hasattr(request, 'strategy_type') and request.strategy_type:
				try:
					strategy_type = StrategyType(request.strategy_type)
				except ValueError:
					pass

			# 获取分页参数
			page = getattr(request, 'page', 1) if request else 1
			page_size = getattr(request, 'page_size', 20) if request else 20

			result = await self.strategy_service.get_strategy_list(
				user_id=user_id,
				status=status,
				strategy_type=strategy_type,
				page=page,
				page_size=page_size,
			)

			return result

		except Exception as e:
			logger.error(f"获取策略列表失败: {e}")
			return {
				"success": False,
				"error": str(e),
				"data": [],
				"pagination": {"page": 1, "page_size": 20, "total": 0}
			}

	async def get_strategy_detail (
			self,
			strategy_id: str,
			request,
			user_id: str
	) -> Dict[str, Any]:
		"""
		获取策略详情

		Args:
			strategy_id: 策略ID
			request: 请求参数
			user_id: 用户ID

		Returns:
			策略详情
		"""
		try:
			# 获取 include_positions 参数
			include_positions = getattr(request, 'include_positions', None) if request else None
			return await self.strategy_service.get_strategy_detail(
				strategy_id=strategy_id,
				user_id=user_id,
				include_positions=include_positions,
			)
		except Exception as e:
			logger.error(f"获取策略详情失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def create_strategy (
			self,
			request,
			user_id: str
	) -> Dict[str, Any]:
		"""
		创建策略

		Args:
			request: 创建请求
			user_id: 用户ID

		Returns:
			创建结果
		"""
		try:
			# 转换策略类型
			strategy_type = StrategyType.CTA
			if hasattr(request, 'strategy_type') and request.strategy_type:
				try:
					strategy_type = StrategyType(request.strategy_type)
				except ValueError:
					pass

			# 创建策略
			result = await self.strategy_service.create_strategy(
				name=request.name,
				strategy_type=strategy_type,
				code=request.code or "",
				description=request.description or "",
				parameters=request.parameters or {},
				user_id=user_id,
			)

			return result

		except Exception as e:
			logger.error(f"创建策略失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def update_strategy (
			self,
			strategy_id: str,
			request,
			user_id: str
	) -> Dict[str, Any]:
		"""
		更新策略

		Args:
			strategy_id: 策略ID
			request: 更新请求
			user_id: 用户ID

		Returns:
			更新结果
		"""
		try:
			# 转换状态
			status = None
			if hasattr(request, 'status') and request.status:
				try:
					status = StrategyLifecycleStatus(request.status)
				except ValueError:
					pass

			result = await self.strategy_service.update_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
				name=request.name,
				description=request.description,
				code=request.code,
				parameters=request.parameters,
				status=status,
			)

			return result

		except Exception as e:
			logger.error(f"更新策略失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def delete_strategy (
			self,
			strategy_id: str,
			user_id: str
	) -> None:
		"""
		删除策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID
		"""
		try:
			result = await self.strategy_service.delete_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
			)

			if not result["success"]:
				raise HTTPException(
					status_code=400,
					detail=result.get("error", "删除失败")
				)

		except HTTPException:
			raise
		except Exception as e:
			logger.error(f"删除策略失败: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	async def clone_strategy(
			self, strategy_id: str, user_id: str, new_name: str = None,
	) -> Dict[str, Any]:
		"""克隆策略为独立副本"""
		try:
			result = await self.strategy_service.clone_strategy(
				strategy_id=strategy_id, user_id=user_id, new_name=new_name,
			)
			if not result.get("success"):
				raise HTTPException(status_code=400, detail=result.get("error", "克隆失败"))
			return {"success": True, "data": result["data"]}
		except HTTPException:
			raise
		except Exception as e:
			logger.error(f"克隆策略失败: {e}")
			raise HTTPException(status_code=500, detail=str(e))

	async def start_strategy (
			self,
			strategy_id: str,
			request,
			user_id: str,
			capital: float = None
	) -> Dict[str, Any]:
		"""
		启动策略

		Args:
			strategy_id: 策略ID
			request: 启动请求
			user_id: 用户ID
			capital: 初始资金（可选）

		Returns:
			启动结果
		"""
		try:
			# 获取参数，优先使用传入的 capital，其次从 request 获取
			if capital is None:
				if hasattr(request, 'capital') and request.capital:
					capital = request.capital

			parameters = {}
			if hasattr(request, 'parameters') and request.parameters:
				parameters = request.parameters

			run_mode_str = getattr(request, 'run_mode', None) or "live"
			from modules.strategy.constants import RunMode as RM
			run_mode = getattr(RM, run_mode_str.upper(), RM.LIVE)

			execution_mode_str = getattr(request, 'execution_mode', None) or "semi_auto"
			from modules.strategy.constants import ExecutionMode as EM
			execution_mode = getattr(EM, execution_mode_str.upper(), EM.SEMI_AUTO)

			result = await self.execution_service.start_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
				capital=capital,
				parameters=parameters,
				run_mode=run_mode,
				execution_mode=execution_mode,
				account_id=getattr(request, 'account_id', None),
			)

			return result

		except Exception as e:
			logger.error(f"启动策略失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def stop_strategy (
			self,
			strategy_id: str,
			request,
			user_id: str,
			force: bool = None
	) -> Dict[str, Any]:
		"""
		停止策略

		Args:
			strategy_id: 策略ID
			request: 停止请求
			user_id: 用户ID
			force: 是否强制停止

		Returns:
			停止结果
		"""
		try:
			# 优先使用传入的 force 参数，其次从 request 获取
			if force is None:
				force = False
				if hasattr(request, 'force'):
					force = request.force

			result = await self.execution_service.stop_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
				force=force,
			)

			return result

		except Exception as e:
			logger.error(f"停止策略失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def get_strategy_performance (
			self,
			strategy_id: str,
			request,  # 未使用参数
			user_id: str
	) -> Dict[str, Any]:
		"""
		获取策略绩效

		Args:
			strategy_id: 策略ID
			request: 绩效请求
			user_id: 用户ID

		Returns:
			绩效数据
		"""
		try:
			# 先获取策略状态
			status_result = await self.execution_service.get_strategy_status(
				strategy_id=strategy_id,
				user_id=user_id,
			)

			if not status_result.get("success"):
				return status_result

			# 获取策略信息
			detail_result = await self.strategy_service.get_strategy_detail(
				strategy_id=strategy_id,
				user_id=user_id,
			)

			data = status_result.get("data", {})

			# 添加策略信息
			if detail_result.get("success"):
				data["strategy_name"] = detail_result["data"].get("name")
				data["strategy_type"] = detail_result["data"].get("strategy_type")

			# 从回测结果获取真实绩效数据
			data["performance"] = await self._fetch_real_performance(strategy_id)

			return {
				"success": True,
				"data": data
			}

		except Exception as e:
			logger.error(f"获取策略绩效失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}



	
	# ---- 策略模板 ----

	async def get_template_list(self, request, user_id: str) -> Dict[str, Any]:
		"""获取模板列表"""
		try:
			from modules.strategy.services.template_service import TemplateService
			svc = TemplateService(self.db)
			strategy_type = getattr(request, 'strategy_type', None)
			page = getattr(request, 'page', 1) or 1
			page_size = getattr(request, 'page_size', 20) or 20
			if strategy_type:
				try:
					strategy_type = StrategyType(strategy_type)
				except ValueError:
					pass
			return await svc.get_template_list(strategy_type=strategy_type, page=page, page_size=page_size)
		except Exception as e:
			logger.error(f"获取模板列表失败: {e}")
			return {"success": False, "error": str(e), "data": []}

	async def get_template_detail(self, template_id: str) -> Dict[str, Any]:
		"""获取模板详情"""
		try:
			from modules.strategy.services.template_service import TemplateService
			svc = TemplateService(self.db)
			return await svc.get_template_detail(template_id)
		except Exception as e:
			logger.error(f"获取模板详情失败: {e}")
			return {"success": False, "error": str(e)}

	async def create_template(self, request) -> Dict[str, Any]:
		"""创建模板"""
		try:
			from modules.strategy.services.template_service import TemplateService
			svc = TemplateService(self.db)
			st = StrategyType(request.strategy_type) if hasattr(request, 'strategy_type') and request.strategy_type else StrategyType.CUSTOM
			return await svc.create_template(
				name=request.name,
				strategy_type=st,
				code_template=request.code_template,
				description=getattr(request, 'description', '') or '',
				default_parameters=getattr(request, 'default_parameters', None),
				category=getattr(request, 'category', 'custom') or 'custom',
			)
		except Exception as e:
			logger.error(f"创建模板失败: {e}")
			return {"success": False, "error": str(e)}

	async def update_template(self, template_id: str, request) -> Dict[str, Any]:
		"""更新模板"""
		try:
			from modules.strategy.services.template_service import TemplateService
			svc = TemplateService(self.db)
			return await svc.update_template(
				template_id=template_id,
				name=getattr(request, 'name', None),
				description=getattr(request, 'description', None),
				code_template=getattr(request, 'code_template', None),
				default_parameters=getattr(request, 'default_parameters', None),
			)
		except Exception as e:
			logger.error(f"更新模板失败: {e}")
			return {"success": False, "error": str(e)}

	async def delete_template(self, template_id: str) -> Dict[str, Any]:
		"""删除模板"""
		try:
			from modules.strategy.services.template_service import TemplateService
			svc = TemplateService(self.db)
			return await svc.delete_template(template_id)
		except Exception as e:
			logger.error(f"删除模板失败: {e}")
			return {"success": False, "error": str(e)}

	async def create_strategy_from_template(self, template_id: str, request, user_id: str) -> Dict[str, Any]:
		"""基于模板创建策略"""
		try:
			from modules.strategy.services.template_service import TemplateService
			svc = TemplateService(self.db)
			custom_params = getattr(request, 'custom_parameters', None)
			return await svc.create_from_template(
				template_id=template_id,
				name=request.name,
				user_id=user_id,
				custom_parameters=custom_params,
			)
		except Exception as e:
			logger.error(f"基于模板创建策略失败: {e}")
			return {"success": False, "error": str(e)}

	
	async def validate_strategy_code(
			self,
			strategy_id: str,
			user_id: str
	) -> Dict[str, Any]:
		"""验证策略代码（v2.1: 不改变状态，仅做语法+依赖检查）"""
		try:
			return await self.strategy_service.validate_strategy_code(
				strategy_id=strategy_id,
				user_id=user_id,
			)
		except Exception as e:
			logger.error(f"验证策略代码失败: {e}")
			return {"success": False, "error": str(e)}
			return {"success": False, "error": str(e)}
	async def pause_strategy(
			self,
			strategy_id: str,
			user_id: str
	) -> Dict[str, Any]:
		"""暂停策略"""
		try:
			return await self.execution_service.pause_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
			)
		except Exception as e:
			logger.error(f"暂停策略失败: {e}")
			return {"success": False, "error": str(e)}
	async def resume_strategy(
			self,
			strategy_id: str,
			user_id: str
	) -> Dict[str, Any]:
		"""恢复策略"""
		try:
			return await self.execution_service.resume_strategy(
				strategy_id=strategy_id,
				user_id=user_id,
			)
		except Exception as e:
			logger.error(f"恢复策略失败: {e}")
			return {"success": False, "error": str(e)}
	async def create_portfolio_handler(self, request, user_id: str) -> Dict[str, Any]:
		try:
			from modules.strategy.services.portfolio_service import PortfolioService
			svc = PortfolioService(self.db)
			return await svc.create_portfolio(
				name=request.name,
				description=getattr(request, 'description', '') or '',
				strategy_weights=request.strategy_weights,
				user_id=user_id,
			)
		except Exception as e:
			logger.error(f"创建策略组合失败: {e}")
			return {"success": False, "error": str(e)}
	async def get_portfolio_detail_handler(self, portfolio_id: str) -> Dict[str, Any]:
		try:
			from modules.strategy.services.portfolio_service import PortfolioService
			svc = PortfolioService(self.db)
			return await svc.get_portfolio_detail(portfolio_id=portfolio_id)
		except Exception as e:
			logger.error(f"获取组合详情失败: {e}")
			return {"success": False, "error": str(e)}
	async def get_portfolio_performance_handler(self, portfolio_id: str) -> Dict[str, Any]:
		try:
			from modules.strategy.services.portfolio_service import PortfolioService
			svc = PortfolioService(self.db)
			return await svc.get_portfolio_performance(portfolio_id=portfolio_id)
		except Exception as e:
			logger.error(f"获取组合绩效失败: {e}")
			return {"success": False, "error": str(e)}
	async def update_portfolio_weights_handler(self, portfolio_id: str, request) -> Dict[str, Any]:
		try:
			from modules.strategy.services.portfolio_service import PortfolioService
			svc = PortfolioService(self.db)
			return await svc.update_portfolio_weights(
				portfolio_id=portfolio_id,
				strategy_weights=request.strategy_weights,
			)
		except Exception as e:
			logger.error(f"更新组合权重失败: {e}")
			return {"success": False, "error": str(e)}
	async def _fetch_real_performance(self, strategy_id: str) -> Dict[str, Any]:
		"""从回测结果表查询最近完成的绩效数据"""
		try:
			from shared.database.repositories.strategy.backtest.task_repo import 				BacktestTaskRepository
			task_repo = BacktestTaskRepository(self.db)
			tasks, _ = await task_repo.get_list(
				filters={"strategy_id": strategy_id, "status": "completed"},
				page=1, page_size=1,
			)
			if tasks and tasks[0].result:
				metrics = tasks[0].result.get("metrics", {})
				return {
					"total_return": metrics.get("total_return", 0.0),
					"annual_return": metrics.get("annual_return",
						metrics.get("annualized_return", 0.0)),
					"sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
					"max_drawdown": metrics.get("max_drawdown", 0.0),
					"win_rate": metrics.get("win_rate", 0.0),
					"profit_factor": metrics.get("profit_factor", 0.0),
					"num_trades": metrics.get("num_trades", metrics.get("num_signals", 0)),
					"volatility": metrics.get("volatility", 0.0),
					"source": "backtest",
				}
		except Exception as e:
			logger.warning(f"获取回测绩效失败: {e}")
		return {
			"total_return": 0.0, "annual_return": 0.0,
			"win_rate": 0.0, "max_drawdown": 0.0,
			"sharpe_ratio": 0.0, "source": "no_data",
		}
	async def get_strategy_status (
			self,
			strategy_id: str,
			user_id: str
	) -> Dict[str, Any]:
		"""
		获取策略状态
		Args:
			strategy_id: 策略ID
			user_id: 用户ID
		Returns:
			策略状态
		"""
		try:
			return await self.execution_service.get_strategy_status(
				strategy_id=strategy_id,
				user_id=user_id,
			)
		except Exception as e:
			logger.error(f"获取策略状态失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}
async def get_template_list(session: AsyncSession, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_template_list(request, user_id)


async def get_template_detail(session: AsyncSession, template_id: str):
	handler = StrategyHandler(session)
	return await handler.get_template_detail(template_id)


async def create_template(session: AsyncSession, request):
	handler = StrategyHandler(session)
	return await handler.create_template(request)


async def update_template(session: AsyncSession, template_id: str, request):
	handler = StrategyHandler(session)
	return await handler.update_template(template_id, request)


async def delete_template(session: AsyncSession, template_id: str):
	handler = StrategyHandler(session)
	return await handler.delete_template(template_id)


async def create_strategy_from_template(session: AsyncSession, template_id: str, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.create_strategy_from_template(template_id, request, user_id)



async def create_portfolio(session: AsyncSession, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.create_portfolio_handler(request, user_id)


async def get_portfolio_detail(session: AsyncSession, portfolio_id: str):
	handler = StrategyHandler(session)
	return await handler.get_portfolio_detail_handler(portfolio_id)


async def get_portfolio_performance(session: AsyncSession, portfolio_id: str):
	handler = StrategyHandler(session)
	return await handler.get_portfolio_performance_handler(portfolio_id)


async def update_portfolio_weights(session: AsyncSession, portfolio_id: str, request):
	handler = StrategyHandler(session)
	return await handler.update_portfolio_weights_handler(portfolio_id, request)



# ==================== 导出函数供router使用 ====================

async def get_strategy_list (session: AsyncSession, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_strategy_list(request, user_id)


async def get_strategy_detail (session: AsyncSession, strategy_id: str, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_strategy_detail(strategy_id, request, user_id)


async def create_strategy (session: AsyncSession, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.create_strategy(request, user_id)


async def update_strategy (session: AsyncSession, strategy_id: str, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.update_strategy(strategy_id, request, user_id)


async def delete_strategy (session: AsyncSession, strategy_id: str, user_id: str):
	handler = StrategyHandler(session)
	return await handler.delete_strategy(strategy_id, user_id)


async def clone_strategy_module(session: AsyncSession, strategy_id: str, user_id: str, new_name: str = None):
		handler = StrategyHandler(session)
		return await handler.clone_strategy(strategy_id, user_id, new_name)

async def start_strategy (session: AsyncSession, strategy_id: str, request, user_id: str, capital: float = None, event_engine=None):
	handler = StrategyHandler(session, event_engine=event_engine)
	return await handler.start_strategy(strategy_id, request, user_id, capital)


async def stop_strategy (session: AsyncSession, strategy_id: str, request, user_id: str, force: bool = None, event_engine=None):
	handler = StrategyHandler(session, event_engine=event_engine)
	return await handler.stop_strategy(strategy_id, request, user_id, force)


async def get_strategy_performance (session: AsyncSession, strategy_id: str, request, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_strategy_performance(strategy_id, request, user_id)


async def get_strategy_status (session: AsyncSession, strategy_id: str, user_id: str):
	handler = StrategyHandler(session)
	return await handler.get_strategy_status(strategy_id, user_id)



async def validate_strategy_code(session: AsyncSession, strategy_id: str, user_id: str):
	handler = StrategyHandler(session)
	return await handler.validate_strategy_code(strategy_id, user_id)


async def pause_strategy(session: AsyncSession, strategy_id: str, user_id: str, event_engine=None):
	handler = StrategyHandler(session, event_engine=event_engine)
	return await handler.pause_strategy(strategy_id, user_id)


async def resume_strategy(session: AsyncSession, strategy_id: str, user_id: str, event_engine=None):
	handler = StrategyHandler(session, event_engine=event_engine)
	return await handler.resume_strategy(strategy_id, user_id)


async def check_strategy_module_health (session: AsyncSession) -> Dict[str, Any]:
	"""检查策略模块健康状态"""
	try:
		# 简单检查数据库连接
		await session.execute(text("SELECT 1"))

		return {
			"status": "healthy",
			"module": "strategy",
			"timestamp": datetime.now().isoformat()
		}
	except Exception as e:
		logger.error(f"策略模块健康检查失败: {e}")
		return {
			"status": "unhealthy",
			"module": "strategy",
			"error": str(e),
			"timestamp": datetime.now().isoformat()
		}


async def get_builtin_strategies() -> Dict[str, Any]:
	"""v2.3: 返回 Registry 中所有已注册内置策略的元信息（含默认参数）"""
	from modules.strategy.engines.strategy_registry import StrategyRegistry
	registry = StrategyRegistry()
	# 强制重新扫描：单例可能未包含全部策略，确保最新
	if registry.get_class_count() < 3:
		logger.warning(
			"[get_builtin] registry incomplete (%d classes), triggering auto_discover",
			registry.get_class_count(),
		)
		registry.auto_discover()
	entries = registry.list_all()
	logger.info(
		"[get_builtin] entries=%d types=%s",
		len(entries), registry.get_registered_types(),
	)
	result = []
	for entry in entries:
		# 尝试获取策略类的默认参数
		default_params = {}
		try:
			cls_name = entry.get("class_name", "")
			for st, classes in registry._registry.items():
				found = False
				for cls in classes:
					if cls.__name__ == cls_name:
						try:
							tmp = cls()  # 优先用默认名（中文）
						except TypeError:
							tmp = cls(name=cls_name)
						if hasattr(tmp, "get_parameters"):
							default_params = tmp.get_parameters()
						elif hasattr(tmp, "parameters") and tmp.parameters:
							default_params = dict(tmp.parameters)
						if not default_params and hasattr(cls, "DEFAULT_PARAMS"):
							default_params = dict(getattr(cls, "DEFAULT_PARAMS", {}))
						if hasattr(tmp, "name") and tmp.name:
							entry["display_name"] = str(tmp.name)
						found = True
						break
				if found:
					break
		except Exception:
			pass

		# v2.3: read source code of strategy class
		module_path = entry.get("module", "")
		source_code = ""
		try:
			import importlib, inspect
			mod = importlib.import_module(module_path)
			for st, classes in registry._registry.items():
				for cls in classes:
					if cls.__name__ == entry.get("class_name", ""):
						source_code = inspect.getsource(cls)
						break
		except Exception:
			pass

		result.append({
			"class_name": entry.get("class_name", ""),
			"strategy_type": entry.get("strategy_type", ""),
			"display_name": entry.get("display_name", entry.get("class_name", "")),
			"module": module_path,
			"default_parameters": default_params,
			"source_code": source_code,
		})
	return {"success": True, "data": result}



async def find_or_create_builtin(
    session: AsyncSession,
    request,
    user_id: str,
) -> Dict[str, Any]:
    """查找或创建内置策略：同 class_name 已存在则更新参数返回，否则新建。"""

    svc = StrategyService(session)
    strategy_type_str = getattr(request, "strategy_type", "custom")
    try:
        strategy_type = StrategyType(strategy_type_str)
    except ValueError:
        strategy_type = StrategyType.CUSTOM

    return await svc.find_or_create_from_builtin(
        name=getattr(request, "name", ""),
        strategy_type=strategy_type,
        code=getattr(request, "code", ""),
        class_name=getattr(request, "class_name", ""),
        parameters=getattr(request, "parameters", {}) or {},
        user_id=user_id,
    )

async def trigger_strategy(
	strategy_id: str,
	request,
	main_engine=None,
) -> Dict[str, Any]:
	"""手动触发策略在指定交易日执行（v2.3 开发调试工具）"""
	from datetime import date as date_type

	if main_engine is None:
		return {"success": False, "error": "MainEngine 未注入"}

	strategy_manager = None
	if hasattr(main_engine, "_module_engines"):
		strategy_manager = main_engine._module_engines.get("strategy_manager")

	if strategy_manager is None:
		return {"success": False, "error": "StrategyManager 未找到"}

	if not hasattr(strategy_manager, "trigger_strategy"):
		return {"success": False, "error": "StrategyManager 版本过低，不支持手动触发"}

	trade_date_str = getattr(request, "trade_date", None) if request else None
	if trade_date_str:
		trade_date = date_type.fromisoformat(trade_date_str)
	else:
		trade_date = date_type.today()

	symbols = getattr(request, "symbols", None) if request else None
	skip_pending_check = getattr(request, "skip_pending_check", False) if request else False
	end_date_str = getattr(request, "end_date", None) if request else None
	end_date = date_type.fromisoformat(end_date_str) if end_date_str else None

	return await strategy_manager.trigger_strategy(
		strategy_id=strategy_id,
		trade_date=trade_date,
		end_date=end_date,
		symbols=symbols,
		skip_pending_check=skip_pending_check,
	)
