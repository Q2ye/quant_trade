"""
账户模块API处理函数
负责处理HTTP请求，调用服务层完成业务逻辑
"""
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import (
	AccountCreateRequest,
	AccountResponse,
	AccountUpdateRequest,
	AccountBalanceResponse,
	AccountPositionResponse,
	AccountSummaryResponse,
	PositionDetailResponse,
	AccountFilter
)
from .services.account_service import AccountService
from .services.position_service import PositionService

router = APIRouter()


class AccountHandler:
	"""账户API处理器"""

	def __init__ (self, db: AsyncSession):
		self.db = db
		self.account_service = AccountService(db)
		self.position_service = PositionService(db)

	async def get_accounts (self, filter_params: AccountFilter) -> List[AccountResponse]:
		"""
		获取账户列表

		Args:
			filter_params: 筛选参数

		Returns:
			账户列表
		"""
		accounts = await self.account_service.get_accounts(
			user_id=filter_params.user_id,
			account_type=filter_params.account_type,
			status=filter_params.status,
			skip=filter_params.skip,
			limit=filter_params.limit
		)
		return [AccountResponse.model_validate(account) for account in accounts]

	async def get_account_by_id (self, account_id: str) -> Optional[AccountResponse]:
		"""
		根据ID获取账户

		Args:
			account_id: 账户ID

		Returns:
			账户信息，如果不存在则返回None
		"""
		account = await self.account_service.get_account(account_id)
		if account:
			return AccountResponse.model_validate(account)
		return None

	async def create_account (self, request: AccountCreateRequest) -> AccountResponse:
		"""
		创建新账户

		Args:
			request: 账户创建请求

		Returns:
			创建的账户信息

		Raises:
			HTTPException: 创建失败时抛出
		"""
		account = await self.account_service.create_account(
			user_id=request.user_id,
			account_name=request.account_name,
			account_type=request.account_type,
			initial_balance=request.initial_balance,
			broker=request.broker,
			broker_account_id=request.broker_account_id
		)

		if not account:
			raise HTTPException(
				status_code=400,
				detail="创建账户失败，请检查输入参数"
			)

		return AccountResponse.model_validate(account)

	async def update_account (self, account_id: str, request: AccountUpdateRequest) -> Optional[AccountResponse]:
		"""
		更新账户信息

		Args:
			account_id: 账户ID
			request: 更新请求

		Returns:
			更新后的账户信息，如果账户不存在则返回None
		"""
		# 构建更新字典，过滤掉None值
		update_data = {k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None}

		if not update_data:
			raise HTTPException(
				status_code=400,
				detail="没有提供有效的更新字段"
			)

		account = await self.account_service.update_account(account_id, **update_data)
		if account:
			return AccountResponse.model_validate(account)
		return None

	async def delete_account (self, account_id: str) -> bool:
		"""
		软删除账户

		Args:
			account_id: 账户ID

		Returns:
			删除是否成功
		"""
		return await self.account_service.delete_account(account_id)

	async def get_account_balance (self, account_id: str) -> Optional[AccountBalanceResponse]:
		"""
		获取账户资金余额

		Args:
			account_id: 账户ID

		Returns:
			账户资金信息，如果账户不存在则返回None
		"""
		account = await self.account_service.get_account(account_id)
		if not account:
			return None

		return AccountBalanceResponse(
			account_id=account.id,
			account_number=account.account_number,
			total_balance=account.total_balance,
			available_balance=account.available_balance,
			frozen_balance=account.frozen_balance,
			market_value=account.market_value
		)

	async def get_account_positions (self, account_id: str, ts_code: Optional[str] = None) -> List[
		AccountPositionResponse]:
		"""
		获取账户持仓列表

		Args:
			account_id: 账户ID
			ts_code: 证券代码筛选

		Returns:
			持仓列表
		"""
		positions = await self.position_service.get_account_positions(account_id, ts_code)
		return [
			AccountPositionResponse(
				id=position.id,
				ts_code=position.ts_code,
				volume=position.volume,
				available_volume=position.available_volume,
				frozen_volume=position.frozen_volume,
				cost_price=position.cost_price,
				market_value=position.market_value,
				last_price=position.last_price,
				pnl=position.pnl,
				pnl_rate=position.pnl_rate,
				last_update=position.last_update
			)
			for position in positions
		]

	async def get_account_summary (self, account_id: str) -> Optional[AccountSummaryResponse]:
		"""
		获取账户概览信息

		Args:
			account_id: 账户ID

		Returns:
			账户概览信息，如果账户不存在则返回None
		"""
		account = await self.account_service.get_account(account_id)
		if not account:
			return None

		positions = await self.position_service.get_account_positions(account_id)

		from decimal import Decimal
		return AccountSummaryResponse(
			account=AccountResponse.model_validate(account),
			total_positions=len(positions),
			total_market_value=Decimal(str(sum(p.market_value for p in positions))),
			total_pnl=Decimal(str(sum(p.pnl for p in positions)))
		)

	async def deposit (self, account_id: str, amount: float) -> Optional[AccountBalanceResponse]:
		"""
		账户存款

		Args:
			account_id: 账户ID
			amount: 存款金额

		Returns:
			存款后的账户余额信息，如果失败则返回None
		"""
		success = await self.account_service.deposit(account_id, amount)
		if success:
			return await self.get_account_balance(account_id)
		return None

	async def withdraw (self, account_id: str, amount: float) -> Optional[AccountBalanceResponse]:
		"""
		账户取款

		Args:
			account_id: 账户ID
			amount: 取款金额

		Returns:
			取款后的账户余额信息，如果失败则返回None
		"""
		success = await self.account_service.withdraw(account_id, amount)
		if success:
			return await self.get_account_balance(account_id)
		return None

	async def get_user_accounts (self, user_id: str, include_closed: bool = False) -> List[AccountResponse]:
		"""
		获取用户的所有账户

		Args:
			user_id: 用户ID
			include_closed: 是否包含已关闭账户

		Returns:
			用户账户列表
		"""
		accounts = await self.account_service.get_user_accounts(user_id, include_closed)
		return [AccountResponse.model_validate(account) for account in accounts]

	async def get_position_detail (self, account_id: str, ts_code: str) -> Optional[PositionDetailResponse]:
		"""
		获取账户指定证券的持仓详情

		Args:
			account_id: 账户ID
			ts_code: 证券代码

		Returns:
			持仓详情，如果不存在则返回None
		"""
		position = await self.position_service.get_position_by_security(account_id, ts_code)
		if position:
			return PositionDetailResponse.model_validate(position)
		return None


# 导出函数供router使用
async def get_account_list (session: AsyncSession, request, user_id: str):
	handler = AccountHandler(session)
	from .schemas import AccountFilter

	# 使用配置化的分页参数
	page = request.get_effective_page() if hasattr(request, 'get_effective_page') else 1
	page_size = request.get_effective_page_size() if hasattr(request, 'get_effective_page_size') else 20

	filter_params = AccountFilter(
		user_id=request.user_id if hasattr(request, 'user_id') else None,
		account_type=request.account_type if hasattr(request, 'account_type') else None,
		status=request.status if hasattr(request, 'status') else None,
		skip=(page - 1) * page_size,
		limit=page_size
	)
	accounts = await handler.get_accounts(filter_params)
	data = [a.model_dump() for a in accounts]

	# v2.6: 附加每个账户最近一次日终结算的当日盈亏/收益率（前端账户概览展示用）
	try:
		ids = [a.get("id") for a in data if a.get("id")]
		if ids:
			from sqlalchemy import text as _text
			rows = (await session.execute(
				_text(
					"SELECT DISTINCT ON (account_id) account_id, daily_pnl, daily_return, trade_date "
					"FROM account_daily_performance "
					"WHERE account_id = ANY(:ids) "
					"ORDER BY account_id, trade_date DESC"
				),
				{"ids": ids},
			)).fetchall()
			perf_map = {r.account_id: r for r in rows}
			for a in data:
				p = perf_map.get(a.get("id"))
				a["daily_pnl"] = float(p.daily_pnl) if p and p.daily_pnl is not None else 0.0
				a["daily_return"] = float(p.daily_return) if p and p.daily_return is not None else 0.0
				a["daily_pnl_date"] = p.trade_date.isoformat() if p and p.trade_date else None
	except Exception as _pe:
		logger.warning(f"附加账户日绩效失败（非致命）: {_pe}")

	return {
		"success": True,
		"data": data,
		"pagination": {"page": page, "page_size": page_size, "total": len(accounts)}
	}


async def get_account_detail (session: AsyncSession, account_id: str, _user_id: str):
	handler = AccountHandler(session)
	account = await handler.get_account_by_id(account_id)
	if not account:
		raise HTTPException(status_code=404, detail="账户不存在")
	return {"success": True, "data": account.model_dump()}


async def create_account (session: AsyncSession, request, _user_id: str):
	# 前端不传 user_id 时，由认证上下文注入
	if not getattr(request, 'user_id', None):
		request.user_id = _user_id
	handler = AccountHandler(session)
	account = await handler.create_account(request)
	return {"success": True, "data": account.model_dump()}


async def update_account (session: AsyncSession, account_id: str, request, _user_id: str):
	handler = AccountHandler(session)
	account = await handler.update_account(account_id, request)
	if not account:
		raise HTTPException(status_code=404, detail="账户不存在")
	return {"success": True, "data": account.model_dump()}


async def delete_account (session: AsyncSession, account_id: str, _user_id: str):
	handler = AccountHandler(session)
	success = await handler.delete_account(account_id)
	return success


async def get_account_balance (session: AsyncSession, account_id: str, _user_id: str):
	handler = AccountHandler(session)
	balance = await handler.get_account_balance(account_id)
	if not balance:
		raise HTTPException(status_code=404, detail="账户不存在")
	return {"success": True, "data": balance.model_dump()}


async def get_account_positions (session: AsyncSession, account_id: str, request, _user_id: str):
	handler = AccountHandler(session)

	# 使用配置化的分页参数
	page = request.get_effective_page() if hasattr(request, 'get_effective_page') else 1
	page_size = request.get_effective_page_size() if hasattr(request, 'get_effective_page_size') else 20

	# 获取所有持仓
	positions = await handler.get_account_positions(account_id)

	# 手动分页
	start_idx = (page - 1) * page_size
	end_idx = start_idx + page_size
	paginated_positions = positions[start_idx:end_idx]

	return {
		"success": True,
		"data": [p.model_dump() for p in paginated_positions],
		"pagination": {"page": page, "page_size": page_size, "total": len(positions)}
	}


async def get_account_summary (session: AsyncSession, account_id: str, _user_id: str):
	handler = AccountHandler(session)
	summary = await handler.get_account_summary(account_id)
	if not summary:
		raise HTTPException(status_code=404, detail="账户不存在")
	return {"success": True, "data": summary.model_dump()}


async def deposit_to_account (session: AsyncSession, account_id: str, request, _user_id: str):
	handler = AccountHandler(session)
	result = await handler.deposit(account_id, request.amount)
	if not result:
		raise HTTPException(status_code=400, detail="存款失败")
	return {"success": True, "data": result.model_dump()}


async def withdraw_from_account (session: AsyncSession, account_id: str, request, _user_id: str):
	handler = AccountHandler(session)
	result = await handler.withdraw(account_id, request.amount)
	if not result:
		raise HTTPException(status_code=400, detail="取款失败")
	return {"success": True, "data": result.model_dump()}


async def get_user_accounts (session: AsyncSession, user_id: str, _request, _current_user_id: str):
	handler = AccountHandler(session)
	accounts = await handler.get_user_accounts(user_id)
	return {
		"success": True,
		"data": [a.model_dump() for a in accounts],
		"pagination": {"page": 1, "page_size": 20, "total": len(accounts)}
	}


async def get_position_detail (session: AsyncSession, account_id: str, ts_code: str, _user_id: str):
	handler = AccountHandler(session)
	position = await handler.get_position_detail(account_id, ts_code)
	if not position:
		raise HTTPException(status_code=404, detail="持仓不存在")
	return {"success": True, "data": position.model_dump()}


async def check_account_module_health(_session: AsyncSession = None):
	"""检查账户模块健康状态"""
	from datetime import datetime, timezone

	if _session is not None:
		try:
			from sqlalchemy import text
			await _session.execute(text("SELECT 1"))
		except Exception as e:
			return {
				"status": "unhealthy",
				"module": "account",
				"error": str(e),
				"timestamp": datetime.now(timezone.utc).isoformat(),
			}

	return {
		"status": "healthy",
		"module": "account",
		"timestamp": datetime.now(timezone.utc).isoformat(),
	}


# 创建路由实例
account_router = router