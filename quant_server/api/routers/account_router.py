# -*- coding: utf-8 -*-
"""
账户模块API路由
基于混合架构设计，负责将HTTP请求路由到账户模块的业务处理层
位置：quant_server/api/routers/account_router.py
账户模块路由
"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.api.dependencies.auth import get_current_user
# 导入架构依赖
from quant_server.api.dependencies.database import get_db_session
# 导入账户模块的业务层处理函数
from quant_server.modules.account.handlers import (
	get_account_list,
	get_account_detail,
	create_account,
	update_account,
	delete_account,
	get_account_balance,
	get_account_positions,
	get_account_summary,
	deposit_to_account,
	withdraw_from_account,
	get_user_accounts,
	get_position_detail,
	check_account_module_health
)
# 导入账户模块的Pydantic模型
from quant_server.modules.account.schemas import (
	AccountListRequest,
	AccountListResponse,
	AccountDetailResponse,
	AccountCreateRequest,
	AccountUpdateRequest,
	AccountResponse,
	AccountBalanceResponse,
	PositionListRequest,
	PositionListResponse,
	PositionDetailResponse,
	AccountSummaryResponse,
	DepositRequest,
	WithdrawRequest
)
# 导入响应格式化工具
from quant_server.utils.api_utils.response_formatter import success_response, error_response

# 配置日志
logger = logging.getLogger(__name__)

# 创建路由器实例
router = APIRouter(
	prefix="/accounts",
	tags=["账户管理"],
	responses={
		401: {"description": "认证失败"},
		403: {"description": "权限不足"},
		500: {"description": "服务器内部错误"}
	}
)

# ==================== 账户管理接口 ====================

from quant_server.utils.api_utils.pagination_decorator import with_pagination_config


@router.get("", response_model=AccountListResponse)
@with_pagination_config()
async def get_accounts_api (
		request: AccountListRequest = Depends(AccountListRequest),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountListResponse:
	"""
	获取账户列表

	Args:
		request: 账户列表请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountListResponse: 账户列表响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求账户列表，参数: {request.model_dump()}")

		result = await get_account_list(
			session=db_session,
			request=request,
			user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取账户列表失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取账户列表失败: {str(e)}"
		)


@router.get("/users/{user_id}", response_model=AccountListResponse)
async def get_user_accounts_api (
		user_id: str,
		request: AccountListRequest = Depends(),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountListResponse:
	"""
	获取用户的所有账户

	Args:
		user_id: 用户ID
		request: 账户列表请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountListResponse: 用户账户列表响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求用户 {user_id} 的账户列表")

		result = await get_user_accounts(
			session=db_session,
			user_id=user_id,
			_request=request,
			_current_user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"获取用户账户列表失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取用户账户列表失败: {str(e)}"
		)


@router.get("/{account_id}", response_model=AccountDetailResponse)
async def get_account_detail_api (
		account_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountDetailResponse:
	"""
	获取账户详情

	Args:
		account_id: 账户ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountDetailResponse: 账户详情响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求账户详情，账户ID: {account_id}")

		result = await get_account_detail(
			session=db_session,
			account_id=account_id,
			_user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"账户不存在: {account_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"账户 {account_id} 不存在"
		)
	except Exception as e:
		logger.error(f"获取账户详情失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取账户详情失败: {str(e)}"
		)


@router.post("", response_model=AccountResponse, status_code=201)
async def create_account_api (
		request: AccountCreateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountResponse:
	"""
	创建新账户

	Args:
		request: 账户创建请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountResponse: 创建的账户响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 创建账户，参数: {request.model_dump()}")

		result = await create_account(
			session=db_session,
			request=request,
			_user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"创建账户失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"创建账户失败: {str(e)}"
		)


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account_api (
		account_id: str,
		request: AccountUpdateRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountResponse:
	"""
	更新账户信息

	Args:
		account_id: 账户ID
		request: 账户更新请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountResponse: 更新后的账户响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 更新账户 {account_id}，参数: {request.model_dump()}")

		result = await update_account(
			session=db_session,
			account_id=account_id,
			request=request,
			_user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"账户不存在: {account_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"账户 {account_id} 不存在"
		)
	except Exception as e:
		logger.error(f"更新账户失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"更新账户失败: {str(e)}"
		)


@router.delete("/{account_id}", status_code=204)
async def delete_account_api (
		account_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
):
	"""
	删除账户

	Args:
		account_id: 账户ID
		current_user: 当前登录用户
		db_session: 数据库会话
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 删除账户 {account_id}")

		await delete_account(
			session=db_session,
			account_id=account_id,
			_user_id=current_user.get("id")
		)

		return success_response(
			message="账户删除成功",
			data={"account_id": account_id}
		)

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"账户不存在或无法删除: {account_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"删除账户失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"删除账户失败: {str(e)}"
		)


# ==================== 账户资金接口 ====================

@router.get("/{account_id}/balance", response_model=AccountBalanceResponse)
async def get_account_balance_api (
		account_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountBalanceResponse:
	"""
	获取账户资金余额

	Args:
		account_id: 账户ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountBalanceResponse: 账户资金余额响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求账户 {account_id} 资金余额")

		result = await get_account_balance(
			session=db_session,
			account_id=account_id,
			_user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"账户不存在: {account_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"账户 {account_id} 不存在"
		)
	except Exception as e:
		logger.error(f"获取账户资金余额失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取账户资金余额失败: {str(e)}"
		)


@router.post("/{account_id}/deposit", response_model=AccountBalanceResponse)
async def deposit_api (
		account_id: str,
		request: DepositRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountBalanceResponse:
	"""
	账户资金存入

	Args:
		account_id: 账户ID
		request: 存款请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountBalanceResponse: 存款后的账户资金余额
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 向账户 {account_id} 存入资金 {request.amount}")

		result = await deposit_to_account(
			session=db_session,
			account_id=account_id,
			request=request,
			_user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"存款失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"存款失败: {str(e)}"
		)


@router.post("/{account_id}/withdraw", response_model=AccountBalanceResponse)
async def withdraw_api (
		account_id: str,
		request: WithdrawRequest,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountBalanceResponse:
	"""
	账户资金取出

	Args:
		account_id: 账户ID
		request: 取款请求
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountBalanceResponse: 取款后的账户资金余额
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 从账户 {account_id} 取出资金 {request.amount}")

		result = await withdraw_from_account(
			session=db_session,
			account_id=account_id,
			request=request,
			_user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"取款失败: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=str(e)
		)
	except Exception as e:
		logger.error(f"取款失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"取款失败: {str(e)}"
		)


# ==================== 持仓管理接口 ====================
@router.get("/{account_id}/positions", response_model=PositionListResponse)
@with_pagination_config()
async def get_account_positions_api (
		account_id: str = Path(..., description="账户ID"),
		request: PositionListRequest = Depends(PositionListRequest),
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> PositionListResponse:
	"""
	获取账户持仓列表

	Args:
		account_id: 账户ID
		request: 持仓列表请求参数
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		PositionListResponse: 持仓列表响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求账户 {account_id} 持仓列表")

		result = await get_account_positions(
			session=db_session,
			account_id=account_id,
			request=request,
			_user_id=current_user.get("id")
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


@router.get("/{account_id}/positions/{ts_code}", response_model=PositionDetailResponse)
async def get_position_detail_api (
		account_id: str,
		ts_code: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> PositionDetailResponse:
	"""
	获取账户指定证券的持仓详情

	Args:
		account_id: 账户ID
		ts_code: 证券代码
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		PositionDetailResponse: 持仓详情响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求账户 {account_id} 持仓详情，证券代码: {ts_code}")

		result = await get_position_detail(
			session=db_session,
			account_id=account_id,
			ts_code=ts_code,
			_user_id=current_user.get("id")
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


# ==================== 账户概览接口 ====================

@router.get("/{account_id}/summary", response_model=AccountSummaryResponse)
async def get_account_summary_api (
		account_id: str,
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
) -> AccountSummaryResponse:
	"""
	获取账户概览信息

	Args:
		account_id: 账户ID
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		AccountSummaryResponse: 账户概览响应
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求账户 {account_id} 概览")

		result = await get_account_summary(
			session=db_session,
			account_id=account_id,
			_user_id=current_user.get("id")
		)

		return result

	except HTTPException:
		raise
	except ValueError as e:
		logger.warning(f"账户不存在: {account_id}, 错误: {str(e)}")
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"账户 {account_id} 不存在"
		)
	except Exception as e:
		logger.error(f"获取账户概览失败: {str(e)}", exc_info=True)
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail=f"获取账户概览失败: {str(e)}"
		)


# ==================== 模块管理接口 ====================

@router.get("/health")
async def account_module_health_check (
		current_user: Dict = Depends(get_current_user),
		db_session: AsyncSession = Depends(get_db_session)
):
	"""
	账户模块健康检查

	Args:
		current_user: 当前登录用户
		db_session: 数据库会话

	Returns:
		JSONResponse: 健康状态
	"""
	try:
		logger.info(f"用户 {current_user.get('username')} 请求账户模块健康检查")

		health_status = await check_account_module_health(
			_session=db_session,
		)

		return success_response(
			data=health_status,
			message="账户模块健康检查完成"
		)

	except Exception as e:
		logger.error(f"账户模块健康检查失败: {str(e)}", exc_info=True)
		return error_response(
			message="账户模块健康检查失败",
			data={
				"status": "unhealthy",
				"error": str(e)
			},
			status_code=500
		)