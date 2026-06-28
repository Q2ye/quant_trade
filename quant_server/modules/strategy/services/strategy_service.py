# -*- coding: utf-8 -*-
"""
策略管理服务
负责策略的CRUD操作和基本管理
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from modules.strategy.constants import (
	StrategyType,
	StrategyLifecycleStatus,
	ErrorCode,
)
from shared.database.repositories.strategy.management import (
	StrategyRepository,
	StrategyVersionRepository,
	StrategyParameterRepository,
)
from shared.database.repositories.trading.position import PositionRepository

logger = logging.getLogger(__name__)


class StrategyService:
	"""
	策略管理服务

	负责：
	- 策略的增删改查
	- 策略版本管理
	- 策略参数管理
	- 策略编译和验证
	"""

	def __init__ (self, session: AsyncSession):
		"""
		初始化服务

		Args:
			session: 数据库会话
		"""
		self.session = session
		self.strategy_repo = StrategyRepository(session)
		self.version_repo = StrategyVersionRepository(session)
		self.param_repo = StrategyParameterRepository(session)
		self.position_repo = PositionRepository(session)

	async def get_strategy_list (
			self,
			user_id: str,
			status: Optional[StrategyLifecycleStatus] = None,
			strategy_type: Optional[StrategyType] = None,
			page: int = 1,
			page_size: int = 20,
	) -> Dict[str, Any]:
		"""
		获取策略列表

		Args:
			user_id: 用户ID
			status: 状态筛选
			strategy_type: 策略类型筛选
			page: 页码
			page_size: 每页数量

		Returns:
			策略列表和分页信息
		"""
		try:
			# 确保分页参数有默认值
			page = page or 1
			page_size = page_size or 20

			# 构建过滤条件
			filters = {"user_id": user_id}
			if status:
				filters["status"] = status.value # type: ignore
			if strategy_type:
				filters["strategy_type"] = strategy_type.value # type: ignore

			# 使用 get_many 方法进行分页查询
			skip = (page - 1) * page_size

			# get_many 使用 **filters 关键字参数方式传递过滤条件
			strategies = await self.strategy_repo.get_many(
				skip=skip,
				limit=page_size,
				**filters
			)
			total = await self.strategy_repo.count(**filters)

			return {
				"success": True,
				"data": [self._to_dict(s) for s in strategies],
				"pagination": {
					"page": page,
					"page_size": page_size,
					"total": total,
					"total_pages": (total + page_size - 1) // page_size,
				}
			}
		except Exception as e:
			logger.error(f"获取策略列表失败: {e}")
			return {
				"success": False,
				"error": str(e),
				"data": [],
				"pagination": {"page": page, "page_size": page_size, "total": 0}
			}

	async def get_strategy_detail (
			self,
			strategy_id: str,
			user_id: str,
			include_positions: Optional[bool] = None,
	) -> Dict[str, Any]:
		"""
		获取策略详情

		Args:
			strategy_id: 策略ID
			user_id: 用户ID
			include_positions: 是否包含持仓信息

		Returns:
			策略详情
		"""
		try:
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			# 检查权限
			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权访问此策略",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			# 获取参数
			parameters = await self.param_repo.get_by_strategy_id(strategy_id)

			# 获取版本信息
			versions = await self.version_repo.get_by_strategy_id(strategy_id)

			# 构建返回数据
			result = {
				"id": strategy.id,
				"name": strategy.name,
				"description": strategy.description,
				"strategy_type": strategy.strategy_type,
				"status": strategy.status,
				"code": strategy.code,
				"parameters": {p.param_name: p.param_value for p in parameters},
				"versions": [self._version_to_dict(v) for v in versions],
				"created_at": strategy.created_at.isoformat() if strategy.created_at else None,
				"updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
			}

			# 获取持仓信息
			if include_positions:
				try:
					# 获取用户的所有持仓（策略关联用户的持仓）
					positions = await self.position_repo.get_user_positions(
						user_id=user_id,
						include_zero=True
					)
					result["positions"] = [
						{
							"ts_code": p.ts_code,
							"volume": p.volume,
							"available_volume": p.available_volume,
							"frozen_volume": p.frozen_volume,
							"cost_price": float(p.cost_price) if p.cost_price else 0,
							"market_value": float(p.market_value) if p.market_value else 0,
							"last_price": float(p.last_price) if p.last_price else 0,
							"pnl": float(p.pnl) if p.pnl else 0,
							"pnl_rate": float(p.pnl_rate) if p.pnl_rate else 0,
							"last_update": p.last_update.isoformat() if p.last_update else None,
						}
						for p in positions
					]
				except Exception as pos_err:
					logger.warning(f"获取持仓信息失败: {pos_err}")
					result["positions"] = []

			return {
				"success": True,
				"data": result
			}
		except Exception as e:
			logger.error(f"获取策略详情失败: {e}")
			return {
				"success": False,
				"error": str(e)
			}

	async def create_strategy (
			self,
			name: str,
			strategy_type: StrategyType,
			code: str,
			description: str = "",
			parameters: Optional[Dict[str, Any]] = None,
			user_id: str = "0",
	) -> Dict[str, Any]:
		"""
		创建策略

		Args:
			name: 策略名称
			strategy_type: 策略类型
			code: 策略代码
			description: 策略描述
			parameters: 策略参数
			user_id: 用户ID

		Returns:
			创建结果
		"""
		try:
			# 验证策略代码
			validation_result = await self._validate_strategy_code(code)
			if not validation_result["valid"]:
				return {
					"success": False,
					"error": validation_result["error"],
					"error_code": ErrorCode.STRATEGY_COMPILE_ERROR,
				}

			# 收集验证警告（依赖白名单检查），传给前端展示
			_warnings = validation_result.get("warnings", [])
			_unknown = validation_result.get("unknown_imports", [])
			if _warnings:
				logger.warning(f"策略代码依赖警告: {'; '.join(_warnings)}")

			# 从代码中提取类名
			class_name = self._extract_class_name_from_code(code)

			# 创建策略
			strategy_data = {
				"name": name,
			"description": description,
			"strategy_type": strategy_type.value,
			"code": code,
			"class_name": class_name,
			"module_path": f"strategies.user_{user_id}.{class_name.lower()}",
			"status": StrategyLifecycleStatus.DRAFT.value,
				"user_id": user_id,
				"created_at": datetime.now(),
				"updated_at": datetime.now(),
			}

			strategy = await self.strategy_repo.create(strategy_data)

			# 保存参数
			if parameters:
				for key, value in parameters.items():
					# 根据值类型推断 param_type
					param_type = type(value).__name__
					if param_type == "int":
						param_type = "int"
					elif param_type == "float":
						param_type = "float"
					elif param_type == "bool":
						param_type = "bool"
					elif param_type == "str":
						param_type = "string"
					elif param_type == "list":
						param_type = "list"
					elif param_type == "dict":
						param_type = "dict"
					else:
						param_type = "string"

					await self.param_repo.create({
						"strategy_id": strategy.id,
						"param_name": key,
						"param_type": param_type,
						"param_value": value,
						"created_at": datetime.now(),
					})

			# 保存初始版本
			await self.version_repo.create({
				"strategy_id": strategy.id,
				"version_number": "1.0.0",
				"code_content": code,
				"description": "初始版本",
				"is_current": True,
				"created_at": datetime.now(),
			})

			await self.session.commit()

			logger.info(f"创建策略成功: {strategy.id}, {name}")

			return {
				"success": True,
				"data": {
					"id": strategy.id,
					"name": strategy.name,
					"status": strategy.status,
				},
				"warnings": _warnings if _warnings else None,
				"unknown_imports": _unknown if _unknown else None,
			}
		except Exception as e:
			logger.error(f"创建策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def update_strategy (
			self,
			strategy_id: str,
			user_id: str,
			name: Optional[str] = None,
			description: Optional[str] = None,
			code: Optional[str] = None,
			parameters: Optional[Dict[str, Any]] = None,
			status: Optional[StrategyLifecycleStatus] = None,
	) -> Dict[str, Any]:
		"""
		更新策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID
			name: 策略名称
			description: 策略描述
			code: 策略代码
			parameters: 策略参数
			status: 状态

		Returns:
			更新结果
		"""
		try:
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权修改此策略",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			# 检查状态
			if strategy.status in [StrategyLifecycleStatus.RUNNING]:
				return {
					"success": False,
					"error": "策略运行中，无法修改",
					"error_code": ErrorCode.STRATEGY_NOT_RUNNING
				}

			# 更新字段
			update_data = {"updated_at": datetime.now()}
			if name:
				update_data["name"] = name # type: ignore
			if description is not None:
				update_data["description"] = description # type: ignore
			if code:
				# 验证代码
				validation_result = await self._validate_strategy_code(code)
				if not validation_result["valid"]:
					return {
						"success": False,
						"error": validation_result["error"],
						"error_code": ErrorCode.STRATEGY_COMPILE_ERROR
					}
				update_data["code"] = code # type: ignore

			if status:
				update_data["status"] = status.value # type: ignore

			await self.strategy_repo.update(strategy_id, update_data)

			# 更新参数
			if parameters:
				# 删除旧参数
				await self.param_repo.delete_by_strategy_id(strategy_id)
				# 添加新参数
				for key, value in parameters.items():
					# 根据值类型推断 param_type
					param_type = type(value).__name__
					if param_type == "int":
						param_type = "int"
					elif param_type == "float":
						param_type = "float"
					elif param_type == "bool":
						param_type = "bool"
					elif param_type == "str":
						param_type = "string"
					elif param_type == "list":
						param_type = "list"
					elif param_type == "dict":
						param_type = "dict"
					else:
						param_type = "string"

					await self.param_repo.create({
						"strategy_id": strategy_id,
						"param_name": key,
						"param_type": param_type,
						"param_value": value,
						"created_at": datetime.now(),
					})

			await self.session.commit()

			logger.info(f"更新策略成功: {strategy_id}")

			return {
				"success": True,
				"data": {"id": strategy_id}
			}
		except Exception as e:
			logger.error(f"更新策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def delete_strategy (
			self,
			strategy_id: str,
			user_id: str,
	) -> Dict[str, Any]:
		"""
		删除策略

		Args:
			strategy_id: 策略ID
			user_id: 用户ID

		Returns:
			删除结果
		"""
		try:
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权删除此策略",
					"error_code": ErrorCode.STRATEGY_NOT_FOUND
				}

			if strategy.status == StrategyLifecycleStatus.RUNNING:
				return {
					"success": False,
					"error": "策略运行中，无法删除",
					"error_code": ErrorCode.STRATEGY_NOT_RUNNING
				}

			# 删除参数（策略参数 ORM 未设 cascade，需手动逐表清理）
			await self.param_repo.delete_by_strategy_id(strategy_id)

			# 用 ORM session.delete() 触发 cascade，删除策略及关联的 versions/backtest_tasks/signals/orders/runs
			await self.session.delete(strategy)
			await self.session.flush()

			await self.session.commit()

			logger.info(f"删除策略成功: {strategy_id}")

			return {
				"success": True,
				"data": {"id": strategy_id}
			}
		except Exception as e:
			logger.error(f"删除策略失败: {e}")
			await self.session.rollback()
			return {
				"success": False,
				"error": str(e)
			}

	async def clone_strategy(
			self, strategy_id: str, user_id: str, new_name: str = None,
	) -> Dict[str, Any]:
		"""克隆策略为独立副本，用于调优而不影响原策略的实盘运行。"""
		try:
			original = await self.strategy_repo.get_by_id(strategy_id)
			if not original:
				return {"success": False, "error": f"策略 {strategy_id} 不存在"}
			if original.user_id != user_id:
				return {"success": False, "error": "无权克隆此策略"}

			params = await self.param_repo.get_by_strategy_id(strategy_id)
			param_dict = {p.name: p.value for p in params} if params else {}

			clone_data = {
				"name": new_name or f"{original.name}_副本",
				"description": f"克隆自 {original.name}",
				"code": original.code,
				"strategy_type": original.strategy_type,
				"class_name": getattr(original, "class_name", "") or "",
				"module_path": getattr(original, "module_path", "") or "",
				"user_id": user_id,
				"status": "draft",
			}
			clone = await self.strategy_repo.create(clone_data)
			await self.session.flush()

			for pname, pval in param_dict.items():
				await self.param_repo.create({
					"strategy_id": clone.id,
					"name": pname,
					"value": str(pval),
				})

			await self.session.commit()
			logger.info("策略 %s 已克隆为 %s", strategy_id, clone.id)
			return {"success": True, "data": {"id": str(clone.id), "name": clone_data["name"]}}
		except Exception as e:
			logger.error("克隆策略失败: %s", e)
			await self.session.rollback()
			return {"success": False, "error": str(e)}

	async def validate_strategy_code(
			self,
			strategy_id: str,
			user_id: str,
	) -> Dict[str, Any]:
		"""
		验证策略代码（v2.1: 不再改变状态，仅做语法检查和依赖审计）

		Args:
			strategy_id: 策略ID
			user_id: 用户ID

		Returns:
			验证结果（含 warnings/unknown_imports）
		"""
		try:
			strategy = await self.strategy_repo.get_by_id(strategy_id)
			if not strategy:
				return {
					"success": False,
					"error": f"策略 {strategy_id} 不存在"
				}

			if strategy.user_id != user_id:
				return {
					"success": False,
					"error": "无权操作此策略"
				}

			validation_result = await self._validate_strategy_code(strategy.code)
			if not validation_result["valid"]:
				return {
					"success": False,
					"error": validation_result["error"]
				}

			return {
				"success": True,
				"data": {
					"id": strategy_id,
					"status": strategy.status,
					"warnings": validation_result.get("warnings"),
					"unknown_imports": validation_result.get("unknown_imports"),
				},
			}
		except Exception as e:
			logger.error(f"验证策略代码失败: {e}")
			return {"success": False, "error": str(e)}

	# ---- 策略运行环境白名单 ----
	# 不在白名单中的 import 会在保存时给出警告，但仍允许保存
	ALLOWED_IMPORTS = {
		# Python 标准库（常用）
		"abc", "collections", "copy", "datetime", "decimal", "enum",
		"functools", "itertools", "json", "logging", "math", "operator",
		"os.path", "pathlib", "re", "statistics", "string", "time",
		"typing", "uuid", "warnings",
		# 数据处理
		"numpy", "pandas", "scipy", "scipy.stats", "scipy.optimize",
		"polars", "pandas_ta", "talib",
		# 本项目模块
		"core", "shared", "modules", "utils",
		"modules.strategy", "modules.strategy.strategies",
		"modules.strategy.strategies.base",
		"modules.strategy.strategies.base.base_strategy",
		"modules.strategy.constants", "modules.strategy.models",
		"core.engines.types.entities",
	}
	# 明确不可用的第三方 SDK（保存时直接拒绝）
	BLOCKED_IMPORTS = {
		"jqdata": "聚宽专有 SDK，不可在本地使用。请用 BaseStrategy.on_bar(bar) 替代。",
		"rqdatac": "米筐专有 SDK，不可在本地使用。",
		"xtquant": "迅投 QMT SDK，请确认环境配置。",
	}

	@staticmethod
	async def _validate_strategy_code(code: str) -> Dict[str, Any]:
		"""
		验证策略代码：语法检查 + 依赖白名单

		返回格式:
		    {"valid": True/False, "error": "...", "warnings": [...],
		     "unknown_imports": [...], "blocked_imports": [...]}
		"""
		try:
			# 1. 语法检查
			compile(code, "<string>", "exec")
		except SyntaxError as e:
			return {"valid": False, "error": f"代码语法错误: {e}"}
		except Exception as e:
			return {"valid": False, "error": f"验证失败: {e}"}

		# 2. 依赖检查（AST 提取 import 语句）
		import ast
		try:
			tree = ast.parse(code)
		except SyntaxError:
			return {"valid": True, "warnings": ["无法解析 AST，跳过依赖检查"]}

		imports = []
		for node in ast.walk(tree):
			if isinstance(node, ast.Import):
				for alias in node.names:
					imports.append(alias.name)
			elif isinstance(node, ast.ImportFrom):
				if node.module:
					imports.append(node.module)

		unknown = []
		blocked = []
		warnings = []

		for name in imports:
			# 精确匹配
			if name in StrategyService.ALLOWED_IMPORTS:
				continue
			# 前缀匹配（如 core.xxx.xxx 匹配 "core"）
			if any(name == p or name.startswith(p + ".") for p in StrategyService.ALLOWED_IMPORTS):
				continue

			# 阻塞列表
			if name in StrategyService.BLOCKED_IMPORTS:
				blocked.append(name)
			else:
				unknown.append(name)

		# 阻塞的导入 → 拒绝保存
		if blocked:
			details = "; ".join(
				f"{n}: {StrategyService.BLOCKED_IMPORTS.get(n, '不可用')}"
				for n in blocked
			)
			return {"valid": False, "error": f"代码引用了不支持的模块: {details}"}

		# 未知导入 → 警告但不阻塞
		if unknown:
			warnings.append(
				f"代码引用了未在白名单中的模块: {', '.join(unknown)}。"
				f"若回测时提示 ModuleNotFoundError，说明该模块未安装。"
			)

		result = {"valid": True}
		if warnings:
			result["warnings"] = warnings
		if unknown:
			result["unknown_imports"] = unknown
		return result

	@staticmethod
	def _extract_class_name_from_code (code: str) -> str:
		"""
		从策略代码中提取类名

		Args:
			code: 策略代码

		Returns:
			类名
		"""
		import re
		# 匹配 class Xxx: 格式
		match = re.search(r'class\s+(\w+)\s*[(:]', code)
		if match:
			return match.group(1)
		# 如果没有找到类，默认使用 Strategy
		return "Strategy"

	@staticmethod
	def _to_dict (strategy) -> Dict[str, Any]:
		"""转换为字典 — v2.0: 包含 execution_mode"""
		return {
			"id": strategy.id,
			"name": strategy.name,
			"description": strategy.description,
			"class_name": getattr(strategy, "class_name", ""),
			"strategy_type": strategy.strategy_type,
			"status": strategy.status,
			"run_mode": getattr(strategy, "run_mode", "backtest"),
			"execution_mode": getattr(strategy, "execution_mode", None),
			"account_id": getattr(strategy, "account_id", None),
			"allocated_capital": float(strategy.allocated_capital) if getattr(strategy, "allocated_capital", None) else 0,

			"created_at": strategy.created_at.isoformat() if strategy.created_at else None,
			"updated_at": strategy.updated_at.isoformat() if strategy.updated_at else None,
		}

	@staticmethod
	def _version_to_dict (version) -> Dict[str, Any]:
		"""版本转换为字典"""
		return {
			"id": version.id,
			"version": version.version_number,
			"description": version.description,
			"code_content": version.code_content,
			"is_current": version.is_current,
			"created_at": version.created_at.isoformat() if version.created_at else None,
		}