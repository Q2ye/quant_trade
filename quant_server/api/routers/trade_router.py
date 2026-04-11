# -*- coding: utf-8 -*-
"""
交易模块API路由
基于混合架构设计，负责将HTTP请求路由到交易模块的业务处理层
位置：quant_server/api/routers/trade_router.py
交易模块路由
"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.api.dependencies.auth import get_current_user
# 导入架构依赖
from quant_server.api.dependencies.database import get_db_session
from quant_server.api.dependencies.event_engine import get_event_engine
# 导入交易模块的业务层处理函数
from quant_server.modules.trade.handlers import (
	get_order_list,
	get_order_detail,
	create_order,
	cancel_order,
	get_position_list,
	get_position_detail,
	execute_signal,
	get_trade_history,
	get_account_summary,
	check_trade_module_health
)
# 导入交易模块的Pydantic模型
from quant_server.modules.trade.schemas import (
	OrderListRequest,
	OrderListResponse,
	OrderDetailResponse,
	OrderCreateRequest,
	OrderResponse,
	OrderCancelRequest,
	PositionListRequest,
	PositionListResponse,
	PositionDetailResponse,
	SignalExecuteRequest,
	SignalExecuteResponse,
	TradeHistoryRequest,
	TradeHistoryResponse,
	AccountSummaryResponse
)
# 导入响应格式化工具
from quant_server.utils.api_utils.response_formatter import success_response, error_response

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	prefix="/trade",
	tags=["交易中心"],
	responses={
		401: {"description": "认证失败"},
		403: {"description": "权限不足"},
		500: {"description": "服务器内部错误"}
	}
)


# ==================== 订单管理接口 ====================

@router.get("/orders", response_model=OrderListResponse)
async def get_orders_api (
		request: OrderListRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> OrderListResponse:
	"""
	获取订单列表

	Args:
		request: 订单列表请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		OrderListResponse: 订单列表响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求订单列表，参数: {request.model_dump()}")

		result = await get_order_list(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取订单列表失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取订单列表失败: {str(e)}"
		)


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order_detail_api (
		order_id: int,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> OrderDetailResponse:
	"""
	获取订单详情

	Args:
		order_id: 订单ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		OrderDetailResponse: 订单详情响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求订单详情，订单ID: {order_id}")

		result = await get_order_detail(
			session=db_session,
			order_id=order_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"订单不存在: {order_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"订单 {order_id} 不存在"
		)
	except Exception as e:
		logger.error(f"获取订单详情失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取订单详情失败: {str(e)}"
		)


@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order_api (
		request: OrderCreateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> OrderResponse:
	"""
	创建新订单

	Args:
		request: 订单创建请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		OrderResponse: 创建的订单响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 创建订单，参数: {request.model_dump()}")

		# 检查用户权限
		if not current_user.get("can_trade", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有交易权限"
			)

		result = await create_order(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"创建订单失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"创建订单失败: {str(e)}"
		)


@router.post("/orders/{order_id}/cancel", response_model=OrderDetailResponse)
async def cancel_order_api (
		order_id: int,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> OrderDetailResponse:
	"""
	撤销订单

	Args:
		order_id: 订单ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		OrderDetailResponse: 撤销后的订单详情
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 撤销订单 {order_id}")

		result = await cancel_order(
			session=db_session,
			order_id=order_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"订单不存在或无法撤销: {order_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"撤销订单失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"撤销订单失败: {str(e)}"
		)


# ==================== 持仓管理接口 ====================

@router.get("/positions", response_model=PositionListResponse)
async def get_positions_api (
		request: PositionListRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> PositionListResponse:
	"""
	获取持仓列表

	Args:
		request: 持仓列表请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		PositionListResponse: 持仓列表响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求持仓列表")

		result = await get_position_list(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取持仓列表失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取持仓列表失败: {str(e)}"
		)


@router.get("/positions/{ts_code}", response_model=PositionDetailResponse)
async def get_position_detail_api (
		ts_code: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> PositionDetailResponse:
	"""
	获取持仓详情

	Args:
		ts_code: 证券代码
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		PositionDetailResponse: 持仓详情响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求持仓详情，证券代码: {ts_code}")

		result = await get_position_detail(
			session=db_session,
			ts_code=ts_code,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"持仓不存在: {ts_code}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"持仓 {ts_code} 不存在"
		)
	except Exception as e:
		logger.error(f"获取持仓详情失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取持仓详情失败: {str(e)}"
		)


# ==================== 交易执行接口 ====================

@router.post("/signals/execute", response_model=SignalExecuteResponse)
async def execute_signal_api (
		request: SignalExecuteRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> SignalExecuteResponse:
	"""
	执行交易信号

	Args:
		request: 信号执行请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		SignalExecuteResponse: 信号执行响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 执行交易信号，参数: {request.model_dump()}")

		# 检查用户权限
		if not current_user.get("can_trade", False):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有交易权限"
			)

		result = await execute_signal(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"执行交易信号失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"执行交易信号失败: {str(e)}"
		)


# ==================== 交易记录接口 ====================

@router.get("/trades", response_model=TradeHistoryResponse)
async def get_trade_history_api (
		request: TradeHistoryRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> TradeHistoryResponse:
	"""
	获取交易历史

	Args:
		request: 交易历史请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		TradeHistoryResponse: 交易历史响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求交易历史")

		result = await get_trade_history(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取交易历史失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取交易历史失败: {str(e)}"
		)


# ==================== 账户概览接口 ====================

@router.get("/account", response_model=AccountSummaryResponse)
async def get_account_summary_api (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountSummaryResponse:
	"""
	获取账户概览

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountSummaryResponse: 账户概览响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求账户概览")

		result = await get_account_summary(
			session=db_session,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取账户概览失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取账户概览失败: {str(e)}"
		)


# ==================== 模块管理接口 ====================

@router.get("/health")
async def trade_module_health_check (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
):
	"""
	交易模块健康检查

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		JSONResponse: 健康状态
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求交易模块健康检查")

		health_status = await check_trade_module_health(
			session=db_session,
		)

		return success_response(
			data=health_status,
			message="交易模块健康检查完成"
		)

	except Exception as e:
		logger.error(f"交易模块健康检查失败: {str(e)}", exc_info=True)
		return error_response(
			message="交易模块健康检查失败",
			data={
				"status": "unhealthy",
				"error": str(e)
			},
			status_code=500
		)