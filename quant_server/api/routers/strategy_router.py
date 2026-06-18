# -*- coding: utf-8 -*-
"""
策略模块API路由
基于混合架构设计，负责将HTTP请求路由到策略模块的业务处理层
位置：quant_server/api/routers/strategy_router.py
策略模块路由
"""
import logging
from typing import Optional, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
# 导入架构依赖
from api.dependencies.database import get_db_session
# 导入策略模块的业务层处理函数
from modules.strategy.handlers import (
	get_strategy_list,
	get_strategy_detail,
	create_strategy,
	update_strategy,
	delete_strategy,
	start_strategy,
	stop_strategy,
	get_strategy_performance,
	get_strategy_status,
	compile_strategy,
	pause_strategy,
	resume_strategy,
	check_strategy_module_health,
	create_portfolio,
	get_portfolio_detail,
	get_portfolio_performance,
	update_portfolio_weights,
)
# 导入策略模块的Pydantic模型
from modules.strategy.schemas import (
	StrategyListRequest,
	StrategyListResponse,
	StrategyDetailRequest,
	StrategyDetailResponse,
	StrategyCreateRequest,
	StrategyUpdateRequest,
	StrategyResponse,
	StrategyStartRequest,
	StrategyStopRequest,
	StrategyPerformanceRequest,
	StrategyPerformanceResponse,
	StrategyStatusResponse
)
# 导入响应格式化工具
from utils.api_utils.response_formatter import success_response, error_response

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	tags=["策略中心"],
	responses={
		401: {"description": "认证失败"},
		403: {"description": "权限不足"},
		500: {"description": "服务器内部错误"}
	}
)


# ==================== 策略管理接口 ====================

@router.get("", response_model=StrategyListResponse)
async def get_strategies_api (
		request: StrategyListRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyListResponse:
	"""
	获取策略列表

	Args:
		request: 策略列表请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyListResponse: 策略列表响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求策略列表，参数: {request.model_dump()}")

		result = await get_strategy_list(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取策略列表失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取策略列表失败: {str(e)}"
		)


@router.get("/{strategy_id}", response_model=StrategyDetailResponse)
async def get_strategy_detail_api (
		strategy_id: str,
		request: StrategyDetailRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyDetailResponse:
	"""
	获取策略详细信息

	Args:
		strategy_id: 策略ID
		request: 策略详情请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyDetailResponse: 策略详情响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求策略详情，策略ID: {strategy_id}")

		result = await get_strategy_detail(
			session=db_session,
			strategy_id=strategy_id,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"策略不存在: {strategy_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"策略 {strategy_id} 不存在"
		)
	except Exception as e:
		logger.error(f"获取策略详情失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取策略详情失败: {str(e)}"
		)


@router.post("", response_model=StrategyResponse, status_code=201)
async def create_strategy_api (
		request: StrategyCreateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyResponse:
	"""
	创建新策略

	Args:
		request: 策略创建请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyResponse: 创建的策略响应
	"""
	try:
		create_summary = {k: v for k, v in request.model_dump().items() if k not in ("code",)}
		logger.info(f"用户 {current_user.get('username')} 创建策略，参数: {create_summary}")

		result = await create_strategy(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"创建策略失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"创建策略失败: {str(e)}"
		)


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy_api (
		strategy_id: str,
		request: StrategyUpdateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyResponse:
	"""
	更新策略信息

	Args:
		strategy_id: 策略ID
		request: 策略更新请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyResponse: 更新后的策略响应
	"""
	try:
		update_summary = {k: v for k, v in request.model_dump().items() if k not in ("code",)}
		logger.info(f"用户 {current_user.get('username')} 更新策略 {strategy_id}，参数: {update_summary}")

		result = await update_strategy(
			session=db_session,
			strategy_id=strategy_id,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"策略不存在: {strategy_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"策略 {strategy_id} 不存在"
		)
	except Exception as e:
		logger.error(f"更新策略失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"更新策略失败: {str(e)}"
		)


@router.delete("/{strategy_id}", status_code=204)
async def delete_strategy_api (
		strategy_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
):
	"""
	删除策略

	Args:
		strategy_id: 策略ID
		current_user: 当前登录用户
		db_session: 数据库会话
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 删除策略 {strategy_id}")

		await delete_strategy(
			session=db_session,
			strategy_id=strategy_id,
			user_id=current_user.get("id")
		)

		return success_response(
			message="策略删除成功",
			data={"strategy_id": strategy_id}
		)

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"策略不存在: {strategy_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"策略 {strategy_id} 不存在"
		)
	except Exception as e:
		logger.error(f"删除策略失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"删除策略失败: {str(e)}"
		)


# ==================== 策略执行接口 ====================

@router.post("/{strategy_id}/start", response_model=StrategyStatusResponse)
async def start_strategy_api (
		strategy_id: str,
		capital: Optional[float] = None,
		request: StrategyStartRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyStatusResponse:
	"""
	启动策略

	Args:
		strategy_id: 策略ID
		capital: 初始资金（可选，支持query参数或body参数）
		request: 策略启动请求参数（body）
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyStatusResponse: 策略状态响应
	"""
	try:
		# 优先使用 query 参数，其次使用 body 参数
		if capital is None and request.capital is not None:
			capital = request.capital
		logger.info(f"用户 {current_user.get('username')} 启动策略 {strategy_id}，资金: {capital}")

		result = await start_strategy(
			session=db_session,
			strategy_id=strategy_id,
			request=request,
			user_id=current_user.get("id"),
			capital=capital
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"策略不存在或无法启动: {strategy_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"启动策略失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"启动策略失败: {str(e)}"
		)


@router.post("/{strategy_id}/stop", response_model=StrategyStatusResponse)
async def stop_strategy_api (
		strategy_id: str,
		force: Optional[bool] = None,
		request: StrategyStopRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyStatusResponse:
	"""
	停止策略

	Args:
		strategy_id: 策略ID
		force: 是否强制停止（可选，支持query参数或body参数）
		request: 策略停止请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyStatusResponse: 策略状态响应
	"""
	try:
		# 优先使用 query 参数，其次使用 body 参数
		if force is None:
			force = request.force if hasattr(request, 'force') else False

		logger.info(f"用户 {current_user.get('username')} 停止策略 {strategy_id}，强制: {force}")

		result = await stop_strategy(
			session=db_session,
			strategy_id=strategy_id,
			request=request,
			user_id=current_user.get("id"),
			force=force
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"策略不存在或无法停止: {strategy_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"停止策略失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"停止策略失败: {str(e)}"
		)


# ==================== 策略分析接口 ====================

@router.get("/{strategy_id}/performance", response_model=StrategyPerformanceResponse)
async def get_strategy_performance_api (
		strategy_id: str,
		request: StrategyPerformanceRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyPerformanceResponse:
	"""
	获取策略绩效

	Args:
		strategy_id: 策略ID
		request: 策略绩效请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyPerformanceResponse: 策略绩效响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求策略 {strategy_id} 绩效")

		result = await get_strategy_performance(
			session=db_session,
			strategy_id=strategy_id,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取策略绩效失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取策略绩效失败: {str(e)}"
		)


@router.get("/{strategy_id}/status", response_model=StrategyStatusResponse)
async def get_strategy_status_api (
		strategy_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyStatusResponse:
	"""
	获取策略运行状态

	Args:
		strategy_id: 策略ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyStatusResponse: 策略状态响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求策略 {strategy_id} 状态")

		result = await get_strategy_status(
			session=db_session,
			strategy_id=strategy_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取策略状态失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取策略状态失败: {str(e)}"
		)




# ==================== 策略组合接口 ====================

@router.post("/portfolio", response_model=StrategyResponse, status_code=201)
async def create_portfolio_api(
		request: StrategyCreateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyResponse:
	"""创建策略组合"""
	try:
		result = await create_portfolio(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)
		return result
	except Exception as e:
		logger.error(f"创建组合失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/{portfolio_id}", response_model=StrategyResponse)
async def get_portfolio_detail_api(
		portfolio_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyResponse:
	"""获取策略组合详情"""
	try:
		result = await get_portfolio_detail(session=db_session, portfolio_id=portfolio_id)
		return result
	except Exception as e:
		logger.error(f"获取组合详情失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/{portfolio_id}/performance", response_model=StrategyPerformanceResponse)
async def get_portfolio_performance_api(
		portfolio_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyPerformanceResponse:
	"""获取策略组合绩效"""
	try:
		result = await get_portfolio_performance(session=db_session, portfolio_id=portfolio_id)
		return result
	except Exception as e:
		logger.error(f"获取组合绩效失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


@router.put("/portfolio/{portfolio_id}/weights", response_model=StrategyResponse)
async def update_portfolio_weights_api(
		portfolio_id: str,
		request: StrategyUpdateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyResponse:
	"""更新策略组合权重"""
	try:
		result = await update_portfolio_weights(
			session=db_session,
			portfolio_id=portfolio_id,
			request=request,
		)
		return result
	except Exception as e:
		logger.error(f"更新权重失败: {str(e)}", exc_info=True)
		raise HTTPException(status_code=500, detail=str(e))


# ==================== 策略生命周期扩展接口 ====================

@router.post("/{strategy_id}/compile", response_model=StrategyResponse)
async def compile_strategy_api (
		strategy_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyResponse:
	"""
	编译策略

	Args:
		strategy_id: 策略ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyResponse: 编译结果
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 编译策略 {strategy_id}")

		result = await compile_strategy(
			session=db_session,
			strategy_id=strategy_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"策略不存在: {strategy_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"策略 {strategy_id} 不存在"
		)
	except Exception as e:
		logger.error(f"编译策略失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"编译策略失败: {str(e)}"
		)


@router.post("/{strategy_id}/pause", response_model=StrategyStatusResponse)
async def pause_strategy_api (
		strategy_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyStatusResponse:
	"""
	暂停策略

	Args:
		strategy_id: 策略ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyStatusResponse: 策略状态响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 暂停策略 {strategy_id}")

		result = await pause_strategy(
			session=db_session,
			strategy_id=strategy_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"策略不存在或无法暂停: {strategy_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"暂停策略失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"暂停策略失败: {str(e)}"
		)


@router.post("/{strategy_id}/resume", response_model=StrategyStatusResponse)
async def resume_strategy_api (
		strategy_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> StrategyStatusResponse:
	"""
	恢复策略

	Args:
		strategy_id: 策略ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		StrategyStatusResponse: 策略状态响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 恢复策略 {strategy_id}")

		result = await resume_strategy(
			session=db_session,
			strategy_id=strategy_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"策略不存在或无法恢复: {strategy_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"恢复策略失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"恢复策略失败: {str(e)}"
		)


# ==================== 模块管理接口 ====================

@router.get("/health")
async def strategy_module_health_check (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
):
	"""
	策略模块健康检查

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		JSONResponse: 健康状态
	"""
	try:
		logger.debug(f"用户 {current_user.get('username')} 请求策略模块健康检查")

		health_status = await check_strategy_module_health(
			session=db_session,
		)

		return success_response(
			data=health_status,
			message="策略模块健康检查完成"
		)

	except Exception as e:
		logger.error(f"策略模块健康检查失败: {str(e)}", exc_info=True)
		return error_response(
			message="策略模块健康检查失败",
			data={
				"status": "unhealthy",
				"error": str(e)
			},
			status_code=500
		)
