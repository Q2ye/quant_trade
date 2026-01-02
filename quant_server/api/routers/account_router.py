"""
账户模块路由文件
负责定义账户相关的所有API端点
"""
from fastapi import APIRouter, Depends, Query, Path, HTTPException
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies.database import get_db_session
from modules.account.schemas import (
	AccountCreateRequest,
	AccountResponse,
	AccountUpdateRequest,
	AccountBalanceResponse,
	AccountPositionResponse,
	AccountSummaryResponse,
	PositionResponse,
	AccountFilter
)
from modules.account.handlers import AccountHandler

router = APIRouter(tags=["账户管理"])


@router.get("/accounts", response_model=List[AccountResponse])
async def list_accounts (
		skip: int = Query(0, ge=0, description="跳过记录数"),
		limit: int = Query(100, ge=1, le=1000, description="返回记录数"),
		user_id: Optional[int] = Query(None, description="用户ID筛选"),
		account_type: Optional[str] = Query(None, description="账户类型筛选"),
		status: Optional[str] = Query(None, description="账户状态筛选"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	获取账户列表

	- 支持分页查询
	- 支持按用户、账户类型、状态筛选
	"""
	handler = AccountHandler(db)
	filter_params = AccountFilter(
		user_id=user_id,
		account_type=account_type,
		status=status,
		skip=skip,
		limit=limit
	)
	return await handler.get_accounts(filter_params)


@router.get("/accounts/{account_id}", response_model=AccountResponse)
async def get_account (
		account_id: int = Path(..., description="账户ID"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	获取指定账户详情

	- 包括账户基本信息和当前状态
	"""
	handler = AccountHandler(db)
	account = await handler.get_account_by_id(account_id)
	if not account:
		raise HTTPException(status_code=404, detail="账户不存在")
	return account


@router.post("/accounts", response_model=AccountResponse, status_code=201)
async def create_account (
		request: AccountCreateRequest,
		db: AsyncSession = Depends(get_db_session)
):
	"""
	创建新账户

	- 支持现金账户、信用账户等类型
	- 自动生成内部账户号
	"""
	handler = AccountHandler(db)
	return await handler.create_account(request)


@router.put("/accounts/{account_id}", response_model=AccountResponse)
async def update_account (
		account_id: int = Path(..., description="账户ID"),
		request: AccountUpdateRequest = None,
		db: AsyncSession = Depends(get_db_session)
):
	"""
	更新账户信息

	- 只能更新部分字段（账户名称、状态等）
	- 不能修改账户资金信息
	"""
	handler = AccountHandler(db)
	account = await handler.update_account(account_id, request)
	if not account:
		raise HTTPException(status_code=404, detail="账户不存在")
	return account


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account (
		account_id: int = Path(..., description="账户ID"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	软删除账户

	- 实际执行软删除，标记为已删除状态
	- 需要验证账户无持仓和未完成订单
	"""
	handler = AccountHandler(db)
	success = await handler.delete_account(account_id)
	if not success:
		raise HTTPException(status_code=400, detail="无法删除账户，请检查是否有持仓或未完成订单")


@router.get("/accounts/{account_id}/balance", response_model=AccountBalanceResponse)
async def get_account_balance (
		account_id: int = Path(..., description="账户ID"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	获取账户资金余额

	- 总资产、可用资金、冻结资金、持仓市值
	"""
	handler = AccountHandler(db)
	balance = await handler.get_account_balance(account_id)
	if not balance:
		raise HTTPException(status_code=404, detail="账户不存在")
	return balance


@router.get("/accounts/{account_id}/positions", response_model=List[AccountPositionResponse])
async def get_account_positions (
		account_id: int = Path(..., description="账户ID"),
		ts_code: Optional[str] = Query(None, description="证券代码筛选"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	获取账户持仓列表

	- 包括所有持仓证券的详细信息
	- 支持按证券代码筛选
	"""
	handler = AccountHandler(db)
	return await handler.get_account_positions(account_id, ts_code)


@router.get("/accounts/{account_id}/summary", response_model=AccountSummaryResponse)
async def get_account_summary (
		account_id: int = Path(..., description="账户ID"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	获取账户概览信息

	- 综合账户信息和最近交易情况
	- 用于前端仪表板展示
	"""
	handler = AccountHandler(db)
	summary = await handler.get_account_summary(account_id)
	if not summary:
		raise HTTPException(status_code=404, detail="账户不存在")
	return summary


@router.post("/accounts/{account_id}/deposit", response_model=AccountBalanceResponse)
async def deposit_to_account (
		account_id: int = Path(..., description="账户ID"),
		amount: float = Query(..., gt=0, description="存入金额"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	账户资金存入

	- 增加账户可用资金
	- 更新总资产
	"""
	handler = AccountHandler(db)
	result = await handler.deposit(account_id, amount)
	if not result:
		raise HTTPException(status_code=400, detail="存款失败")
	return result


@router.post("/accounts/{account_id}/withdraw", response_model=AccountBalanceResponse)
async def withdraw_from_account (
		account_id: int = Path(..., description="账户ID"),
		amount: float = Query(..., gt=0, description="取出金额"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	账户资金取出

	- 减少账户可用资金
	- 验证资金是否足够
	"""
	handler = AccountHandler(db)
	result = await handler.withdraw(account_id, amount)
	if not result:
		raise HTTPException(status_code=400, detail="取款失败，资金不足")
	return result


@router.get("/users/{user_id}/accounts", response_model=List[AccountResponse])
async def get_user_accounts (
		user_id: int = Path(..., description="用户ID"),
		include_closed: bool = Query(False, description="是否包含已关闭账户"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	获取用户的所有账户

	- 按用户ID查询其所有账户
	- 可选择是否包含已关闭账户
	"""
	handler = AccountHandler(db)
	return await handler.get_user_accounts(user_id, include_closed)


@router.get("/accounts/{account_id}/positions/{ts_code}", response_model=PositionResponse)
async def get_account_position_detail (
		account_id: int = Path(..., description="账户ID"),
		ts_code: str = Path(..., description="证券代码"),
		db: AsyncSession = Depends(get_db_session)
):
	"""
	获取账户指定证券的持仓详情

	- 包含成本、盈亏等详细信息
	"""
	handler = AccountHandler(db)
	position = await handler.get_position_detail(account_id, ts_code)
	if not position:
		raise HTTPException(status_code=404, detail="持仓不存在")
	return position