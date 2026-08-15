# -*- coding: utf-8 -*-
"""
交易模块API路由
基于混合架构设计，负责将HTTP请求路由到交易模块的业务处理层
位置：quant_server/api/routers/trade_router.py
交易模块路由
"""
import logging
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.auth import get_current_user
# 导入架构依赖
from api.dependencies.database import get_db_session
# 导入交易模块的业务层处理函数
from modules.trade.handlers import (
	get_order_list,
	get_order_detail,
	create_order,
	cancel_order,
	get_position_list,
	get_position_detail,
	execute_signal,
	get_trade_history,
	get_account_summary,
	check_trade_module_health,
	record_trade,
	record_batch_trades,
	review_signal,
	get_signal_list,
	get_round_trips,
)
# 导入交易模块的Pydantic模型
from modules.trade.schemas import (
	OrderListRequest,
	OrderListResponse,
	OrderDetailResponse,
	OrderCreateRequest,
	OrderResponse,
	PositionListRequest,
	PositionListResponse,
	PositionDetailResponse,
	SignalExecuteRequest,
	SignalExecuteResponse,
	TradeHistoryRequest,
	TradeHistoryResponse,
	AccountSummaryResponse,
	TradeRecordRequest,
	TradeRecordResponse,
	BatchTradeRecordRequest,
	BatchTradeRecordResponse,
	SignalReviewRequest,
	SignalReviewResponse,
	SignalListRequest,
	SignalListResponse,
	RoundTripRequest,
	RoundTripResponse,
)
# 导入响应格式化工具
from utils.api_utils.response_formatter import success_response, error_response

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	tags=["交易中心"],
	responses={
		401: {"description": "认证失败"},
		403: {"description": "权限不足"},
		500: {"description": "服务器内部错误"}
	}
)


# ==================== 权限辅助 ====================


def _has_trade_permission(user: Dict) -> bool:
	"""superadmin/admin 角色默认拥有交易权限，其他角色需显式设置 can_trade"""
	role = user.get("role", user.get("user_role", ""))
	if role in ("superadmin", "admin"):
		return True
	return user.get("can_trade", False)


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
		logger.error(f"获取订单列表失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取订单列表失败: {'服务器内部错误'}"
		)


@router.get("/orders/{order_id}", response_model=OrderDetailResponse)
async def get_order_detail_api (
		order_id: str,
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
		logger.warning(f"订单不存在: {order_id}, 错误: {'服务器内部错误'}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"订单 {order_id} 不存在"
		)
	except Exception as e:
		logger.error(f"获取订单详情失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取订单详情失败: {'服务器内部错误'}"
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
		if not _has_trade_permission(current_user):
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
		logger.error(f"创建订单失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"创建订单失败: {'服务器内部错误'}"
		)


@router.post("/orders/{order_id}/cancel", response_model=OrderDetailResponse)
async def cancel_order_api (
		order_id: str,
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

		if not _has_trade_permission(current_user):
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户没有交易权限")

		result = await cancel_order(
			session=db_session,
			order_id=order_id,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"订单不存在或无法撤销: {order_id}, 错误: {'服务器内部错误'}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"撤销订单失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"撤销订单失败: {'服务器内部错误'}"
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
		logger.error(f"获取持仓列表失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取持仓列表失败: {'服务器内部错误'}"
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
		logger.warning(f"持仓不存在: {ts_code}, 错误: {'服务器内部错误'}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"持仓 {ts_code} 不存在"
		)
	except Exception as e:
		logger.error(f"获取持仓详情失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取持仓详情失败: {'服务器内部错误'}"
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
		if not _has_trade_permission(current_user):
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
		logger.error(f"执行交易信号失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"执行交易信号失败: {'服务器内部错误'}"
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
		logger.error(f"获取交易历史失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取交易历史失败: {'服务器内部错误'}"
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
		logger.error(f"获取账户概览失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取账户概览失败: {'服务器内部错误'}"
		)


# ==================== 手动成交录入接口 ====================

@router.post("/trades/record", response_model=TradeRecordResponse, status_code=201)
async def record_trade_api (
		request: TradeRecordRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> TradeRecordResponse:
	"""
	录入一笔已成交的交易（手动记账）

	用户在券商端手动完成交易后，回到系统记录成交信息。
	系统会在一个事务内自动完成：创建订单→创建成交→创建费用→更新持仓→更新账户。
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 录入成交: {request.ts_code} {request.direction}")

		if not _has_trade_permission(current_user):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有交易权限"
			)

		result = await record_trade(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"成交录入失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"成交录入失败: {'服务器内部错误'}"
		)


@router.post("/trades/record/batch", response_model=BatchTradeRecordResponse, status_code=201)
async def record_batch_trades_api (
		request: BatchTradeRecordRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> BatchTradeRecordResponse:
	"""
	批量录入成交

	一次提交多笔成交记录。每笔独立处理，单笔失败不阻塞其他。
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 批量录入成交，共 {len(request.trades)} 笔")

		if not _has_trade_permission(current_user):
			raise HTTPException(
				status_code=status.HTTP_403_FORBIDDEN,
				detail="用户没有交易权限"
			)

		result = await record_batch_trades(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"批量成交录入失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"批量成交录入失败: {'服务器内部错误'}"
		)


# ==================== 信号管理接口 ====================

@router.get("/signals", response_model=SignalListResponse)
async def get_signals_api (
		request: SignalListRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> SignalListResponse:
	"""
	获取信号列表

	支持按状态（pending/approved/rejected/executed）和信号类型（buy/sell）筛选。
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求信号列表")

		result = await get_signal_list(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取信号列表失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取信号列表失败: {'服务器内部错误'}"
		)


@router.put("/signals/{signal_id}/review", response_model=SignalReviewResponse)
async def review_signal_api (
		signal_id: str,
		request: SignalReviewRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> SignalReviewResponse:
	"""
	审核信号

	对策略产生的交易信号进行采纳或拒绝。
	action: approved（采纳）或 rejected（拒绝）
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 审核信号 {signal_id}: {request.action}")

		if not _has_trade_permission(current_user):
			raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="用户没有交易权限")

		result = await review_signal(
			session=db_session,
			signal_id=signal_id,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"信号审核参数错误: {'服务器内部错误'}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"信号审核失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"信号审核失败: {'服务器内部错误'}"
		)


# ==================== 买卖配对追溯接口 ====================

@router.get("/round-trips", response_model=RoundTripResponse)
async def get_round_trips_api (
		account_id: str = Query(..., description="账户ID"),
		ts_code: Optional[str] = Query(default=None, description="证券代码（可选）"),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> RoundTripResponse:
	"""
	获取买卖配对追溯（FIFO）

	返回每笔卖出吃掉哪些买入、已实现盈亏，以及当前持仓由哪些买入构成。
	实时计算，不落库。
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求买卖配对追溯: account={account_id}, ts_code={ts_code}")

		result = await get_round_trips(
			session=db_session,
			account_id=account_id,
			ts_code=ts_code,
		)
		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"买卖配对追溯失败: {'服务器内部错误'}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"买卖配对追溯失败: {'服务器内部错误'}"
		)


# ==================== 交易统计接口 ====================


@router.get("/statistics")
async def get_trade_statistics_api(
    start_date: Optional[str] = Query(default=None, description="开始日期"),
    end_date: Optional[str] = Query(default=None, description="结束日期"),
    strategy_id: Optional[str] = Query(default=None, description="策略ID"),
    current_user: Dict = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
):
    """获取交易统计数据（总笔数、成功笔数、成交量、成交额）"""
    try:
        from sqlalchemy import text
        params = {"user_id": current_user.get("id", "")}
        conditions = []
        if start_date:
            conditions.append("t.created_at >= :start_date")
            params["start_date"] = start_date
        if end_date:
            conditions.append("t.created_at <= :end_date")
            params["end_date"] = end_date
        if strategy_id:
            conditions.append("o.strategy_id = :strategy_id")
            params["strategy_id"] = strategy_id
        where = " AND ".join(conditions) if conditions else "1=1"

        # 修复 2026-08（A28）：原 SQL 查不存在的 trade_records 表且无 user_id 过滤；
        # trades 表无 user_id/status 列，需 JOIN orders 过滤归属与成交状态
        query = text(
            f"SELECT COUNT(*) as total_trades, "
            "COALESCE(SUM(CASE WHEN o.status = 'filled' THEN 1 ELSE 0 END), 0) as successful_trades, "
            "COALESCE(SUM(t.volume), 0) as total_volume, "
            "COALESCE(SUM(t.price * t.volume), 0) as total_amount "
            "FROM trades t JOIN orders o ON t.order_id = o.order_id "
            "WHERE o.user_id = :user_id AND {where}"
        )
        result = await db_session.execute(query, params)
        row = result.fetchone()

        total = int(row.total_trades) if row and row.total_trades else 0
        success = int(row.successful_trades) if row and row.successful_trades else 0

        return {
            "success": True,
            "data": {
                "total_trades": total,
                "successful_trades": success,
                "total_volume": int(row.total_volume) if row and row.total_volume else 0,
                "total_amount": float(row.total_amount) if row and row.total_amount else 0.0,
                "avg_trade_size": float(row.total_amount) / total if row and total > 0 and row.total_amount else 0.0,
            },
        }
    except Exception as e:
        logger.error(f"获取交易统计失败: {'服务器内部错误'}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取交易统计失败: {'服务器内部错误'}",
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
		logger.debug(f"用户 {current_user.get('username')} 请求交易模块健康检查")

		health_status = await check_trade_module_health(
			session=db_session,
		)

		return success_response(
			data=health_status,
			message="交易模块健康检查完成"
		)

	except Exception as e:
		logger.error(f"交易模块健康检查失败: {'服务器内部错误'}", exc_info=True)
		return error_response(
			message="交易模块健康检查失败",
			data={
				"status": "unhealthy",
				"error": str(e)
			},
			status_code=500
		)
