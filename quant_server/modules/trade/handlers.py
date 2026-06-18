# -*- coding: utf-8 -*-
"""
交易模块API处理函数
负责处理HTTP请求，调用服务层完成业务逻辑
"""
from typing import Dict

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from modules.trade.schemas import (
	OrderListRequest, OrderListResponse, OrderDetailResponse,
	OrderCreateRequest, OrderResponse, PositionListRequest, PositionListResponse, PositionDetailResponse,
	SignalExecuteRequest, SignalExecuteResponse,
	TradeHistoryRequest, TradeHistoryResponse, AccountSummaryResponse
)
from shared.database.repositories.account.asset.account_repo import AccountRepository
from shared.database.repositories.trading.order.order_repo import OrderRepository
from shared.database.repositories.trading.order.trade_repo import TradeRepository
from shared.database.repositories.trading.position.position_repo import PositionRepository
from shared.database.repositories.operation.basket.basket_repo import BasketRepository
from shared.database.repositories.operation.basket.basket_item_repo import BasketItemRepository


class TradeHandler:
	"""交易API处理器"""

	def __init__ (self, db: AsyncSession):
		self.db = db
		self.order_repo = OrderRepository(db)
		self.account_repo = AccountRepository(db)
		self.trade_repo = TradeRepository(db)
		self.position_repo = PositionRepository(db)

	async def get_order_list (self, request: OrderListRequest, user_id: str) -> OrderListResponse:
		"""获取订单列表"""
		try:
			# 计算分页参数
			page = request.get_effective_page()
			page_size = request.get_effective_page_size()
			skip = (page - 1) * page_size
			limit = page_size

			# 查询订单
			orders = await self.order_repo.get_by_user_id(
				user_id=user_id,
				status=request.status,
				skip=skip,
				limit=limit
			)

			# 过滤订单
			filtered_orders = []
			for order in orders:
				if request.ts_code and order.ts_code != request.ts_code:
					continue
				filtered_orders.append(order)

			# 计算总数
			total_orders = len(filtered_orders)

			# 转换为响应格式
			order_data = []
			for order in filtered_orders:
				order_data.append({
					"order_id": order.order_id,
					"symbol": order.ts_code,
					"direction": order.direction,
					"price": float(order.price) if order.price else 0.0,
					"volume": order.volume,
					"status": order.status,
					"created_at": order.submitted_at.isoformat() if order.submitted_at else None,
					"filled_at": order.filled_at.isoformat() if order.filled_at else None
				})

			return OrderListResponse(
				success=True,
				data=order_data,
				pagination={
					"total": total_orders,
					"page": page,
					"page_size": page_size,
					"total_pages": (total_orders + page_size - 1) // page_size
				}
			)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取订单列表失败: {str(e)}")

	async def get_order_detail (self, order_id: str, user_id: str) -> OrderDetailResponse:
		"""获取订单详情"""
		try:
			# 查询订单详情
			order = await self.order_repo.get_by_order_id(order_id, with_trades=True)

			if not order:
				return OrderDetailResponse(success=False, data=None, message="订单不存在")

			# 检查订单是否属于该用户
			if order.user_id != user_id:
				return OrderDetailResponse(success=False, data=None, message="无权访问该订单")

			# 转换为响应格式
			order_data = {
				"order_id": order.order_id,
				"symbol": order.ts_code,
				"direction": order.direction,
				"price": float(order.price) if order.price else 0.0,
				"volume": order.volume,
				"status": order.status,
				"created_at": order.submitted_at.isoformat() if order.submitted_at else None,
				"filled_at": order.filled_at.isoformat() if order.filled_at else None,
				"cancelled_at": order.cancelled_at.isoformat() if order.cancelled_at else None,
				"filled_volume": order.filled_volume,
				"filled_amount": float(order.filled_amount) if order.filled_amount else 0.0,
				"avg_price": float(order.avg_price) if order.avg_price else 0.0
			}

			return OrderDetailResponse(success=True, data=order_data)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取订单详情失败: {str(e)}")

	async def create_order (self, request: OrderCreateRequest, user_id: str) -> OrderResponse:
		"""创建订单"""
		try:
			# 获取用户的默认账户
			accounts = await self.account_repo.get_many_by_user_id(user_id)
			if not accounts:
				return OrderResponse(success=False, data=None, message="用户没有可用账户")

			account = accounts[0]  # 假设使用第一个账户

			# 计算订单金额
			order_amount = request.price * request.quantity

			# 检查账户资金是否足够（仅买单）
			if request.direction == "buy":
				if float(account.available_balance) < order_amount:
					return OrderResponse(success=False, data=None, message="账户资金不足")

			# 创建订单
			import uuid
			order_data = {
				"order_id": str(uuid.uuid4().hex[:32]),
				"user_id": user_id,
				"account_id": account.id,
				"ts_code": request.ts_code,
				"order_type": request.order_type,
				"direction": request.direction,
				"price": request.price,
				"volume": request.quantity,
				"status": "submitted"
			}

			# 保存订单
			new_order = await self.order_repo.create(order_data)

			# 转换为响应格式
			order_response = {
				"order_id": new_order.order_id,
				"symbol": new_order.ts_code,
				"direction": new_order.direction,
				"price": float(new_order.price) if new_order.price else 0.0,
				"volume": new_order.volume,
				"status": new_order.status,
				"created_at": new_order.submitted_at.isoformat() if new_order.submitted_at else None
			}

			return OrderResponse(success=True, data=order_response)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"创建订单失败: {str(e)}")

	async def cancel_order (self, order_id: str, user_id: str) -> OrderDetailResponse:
		"""取消订单"""
		try:
			# 查询订单
			order = await self.order_repo.get_by_order_id(order_id)

			if not order:
				return OrderDetailResponse(success=False, data=None, message="订单不存在")

			# 检查订单是否属于该用户
			if order.user_id != user_id:
				return OrderDetailResponse(success=False, data=None, message="无权操作该订单")

			# 检查订单状态是否可取消
			if order.status not in ["submitted", "partial_filled"]:
				return OrderDetailResponse(success=False, data=None, message="订单状态不允许取消")

			# 更新订单状态
			from datetime import datetime
			updated_order = await self.order_repo.update(order_id, {
				"status": "cancelled",
				"cancelled_at": datetime.now()
			})

			# 转换为响应格式
			order_data = {
				"order_id": updated_order.order_id,
				"symbol": updated_order.ts_code,
				"direction": updated_order.direction,
				"price": float(updated_order.price) if updated_order.price else 0.0,
				"volume": updated_order.volume,
				"status": updated_order.status,
				"created_at": updated_order.submitted_at.isoformat() if updated_order.submitted_at else None,
				"cancelled_at": updated_order.cancelled_at.isoformat() if updated_order.cancelled_at else None
			}

			return OrderDetailResponse(success=True, data=order_data)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"取消订单失败: {str(e)}")

	async def get_position_list (self, request: PositionListRequest, user_id: str) -> PositionListResponse:
		"""获取持仓列表"""
		try:
			# 获取用户持仓
			positions = await self.position_repo.get_user_positions(
				user_id=user_id,
				include_zero=False
			)

			# 过滤持仓
			filtered_positions = []
			for position in positions:
				filtered_positions.append(position)

			# 分页处理
			total = len(filtered_positions)
			page = request.get_effective_page()
			page_size = request.get_effective_page_size()
			start = (page - 1) * page_size
			end = start + page_size
			paginated_positions = filtered_positions[start:end]

			# 转换为响应格式
			position_data = []
			for position in paginated_positions:
				position_data.append({
					"symbol": position.ts_code,
					"volume": position.volume,
					"cost_price": float(position.cost_price) if position.cost_price else 0.0,
					"current_price": float(position.last_price) if position.last_price else 0.0,
					"pnl": float(position.pnl) if position.pnl else 0.0,
					"pnl_rate": float(position.pnl_rate) if position.pnl_rate else 0.0
				})

			return PositionListResponse(
				success=True,
				data=position_data,
				pagination={
					"total": total,
					"page": page,
					"page_size": page_size,
					"total_pages": (total + page_size - 1) // page_size
				}
			)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取持仓列表失败: {str(e)}")

	async def get_position_detail (self, ts_code: str, user_id: str) -> PositionDetailResponse:
		"""获取持仓详情"""
		try:
			# 获取用户的所有账户
			accounts = await self.account_repo.get_many_by_user_id(user_id)

			if not accounts:
				return PositionDetailResponse(success=False, data=None, message="用户没有可用账户")

			# 查找持仓
			position = None
			for account in accounts:
				position = await self.position_repo.get_user_position(
					user_id=user_id,
					account_id=account.id,
					ts_code=ts_code
				)
				if position:
					break

			if not position:
				return PositionDetailResponse(success=False, data=None, message="持仓不存在")

			# 转换为响应格式
			position_data = {
				"symbol": position.ts_code,
				"volume": position.volume,
				"cost_price": float(position.cost_price) if position.cost_price else 0.0,
				"current_price": float(position.last_price) if position.last_price else 0.0,
				"pnl": float(position.pnl) if position.pnl else 0.0,
				"pnl_rate": float(position.pnl_rate) if position.pnl_rate else 0.0
			}

			return PositionDetailResponse(success=True, data=position_data)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取持仓详情失败: {str(e)}")

	async def execute_signal (self, request: SignalExecuteRequest, user_id: str) -> SignalExecuteResponse:
		"""执行交易信号"""
		try:
			# 获取用户的默认账户
			accounts = await self.account_repo.get_many_by_user_id(user_id)
			if not accounts:
				return SignalExecuteResponse(
					success=False,
					data=None,
					message="用户没有可用账户"
				)

			account = accounts[0]  # 假设使用第一个账户

			# 计算订单金额
			order_amount = request.price * request.quantity

			# 检查账户资金是否足够（仅买单）
			if request.direction == "buy":
				if float(account.available_balance) < order_amount:
					return SignalExecuteResponse(
						success=False,
						data=None,
						message="账户资金不足"
					)

			# 创建订单
			import uuid
			order_data = {
				"order_id": str(uuid.uuid4().hex[:32]),
				"user_id": user_id,
				"account_id": account.id,
				"ts_code": request.ts_code,
				"order_type": "limit",
				"direction": request.direction,
				"price": request.price,
				"volume": request.quantity,
				"status": "submitted"
			}

			# 保存订单
			new_order = await self.order_repo.create(order_data)

			# 转换为响应格式
			signal_data = {
				"signal_id": new_order.order_id,  # 使用订单ID作为信号ID
				"symbol": new_order.ts_code,
				"direction": new_order.direction,
				"price": float(new_order.price) if new_order.price else 0.0,
				"volume": new_order.volume,
				"status": "executed",
				"message": "信号执行成功"
			}

			return SignalExecuteResponse(
				success=True,
				data=signal_data,
				message="信号执行成功"
			)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"执行交易信号失败: {str(e)}")

	async def get_trade_history (self, request: TradeHistoryRequest, user_id: str) -> TradeHistoryResponse:
		"""获取交易历史"""
		try:
			# 直接使用 TradeRepository 的 get_by_user_id 方法获取交易记录
			page = request.get_effective_page()
			page_size = request.get_effective_page_size()
			trades = await self.trade_repo.get_by_user_id(
				user_id=user_id,
				skip=(page - 1) * page_size,
				limit=page_size
			)

			# 获取总记录数
			total = await self.trade_repo.count_by_user_id(user_id=user_id)

			# 转换为响应格式
			trade_data = []
			for trade in trades:
				trade_data.append({
					"trade_id": trade.trade_id,
					"order_id": trade.order_id,
					"symbol": trade.ts_code,
					"price": float(trade.price) if trade.price else 0.0,
					"volume": trade.volume,
					"trade_time": trade.trade_time.isoformat() if trade.trade_time else None,
					"commission": float(trade.commission) if trade.commission else 0.0,
					"tax": float(trade.tax) if trade.tax else 0.0
				})

			return TradeHistoryResponse(
				success=True,
				data=trade_data,
				pagination={
					"total": total,
					"page": page,
					"page_size": page_size,
					"total_pages": (total + page_size - 1) // page_size
				}
			)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取交易历史失败: {str(e)}")

	async def get_account_summary (self, user_id: str) -> AccountSummaryResponse:
		"""获取账户概览"""
		try:
			# 获取用户的所有账户
			accounts = await self.account_repo.get_many_by_user_id(user_id)

			if not accounts:
				return AccountSummaryResponse(
					success=False,
					data=None,
					message="用户没有可用账户"
				)

			# 计算总资产、现金和市值
			total_asset = 0
			total_cash = 0
			total_market_value = 0
			total_initial_balance = 0

			for account in accounts:
				total_asset += float(account.total_balance) if account.total_balance else 0
				total_cash += float(account.available_balance) if account.available_balance else 0
				total_market_value += float(account.market_value) if account.market_value else 0
				total_initial_balance += float(account.initial_balance) if account.initial_balance else 0

			# 计算总盈亏
			total_pnl = total_asset - total_initial_balance
			total_pnl_rate = (total_pnl / total_initial_balance * 100) if total_initial_balance > 0 else 0

			# 转换为响应格式
			account_data = {
				"total_asset": total_asset,
				"cash": total_cash,
				"market_value": total_market_value,
				"pnl": total_pnl,
				"pnl_rate": total_pnl_rate
			}

			return AccountSummaryResponse(success=True, data=account_data)
		except Exception as e:
			raise HTTPException(status_code=500, detail=f"获取账户概览失败: {str(e)}")

	async def check_trade_module_health (self) -> Dict:
		"""检查交易模块健康状态"""
		from datetime import datetime

		# 检查数据库连接
		health_status = {
			"status": "healthy",
			"module": "trade",
			"timestamp": datetime.now().isoformat(),
			"checks": {
				"database": "connected",
				"repositories": "available",
				"models": "valid"
			}
		}

		# 尝试查询数据库，验证连接是否正常
		try:
			# 尝试查询订单表，验证数据库连接
			await self.order_repo.count()
			health_status["checks"]["database"] = "connected"
		except Exception as e:
			health_status["status"] = "unhealthy"
			health_status["checks"]["database"] = f"error: {str(e)}"

		return health_status


class BasketHandler:
    """篮子管理处理器 — API 路由与 Repository 之间的适配层"""

    def __init__(self, db: AsyncSession):
        self.basket_repo = BasketRepository(db)
        self.basket_item_repo = BasketItemRepository(db)

    # ==================== 篮子 CRUD ====================

    async def get_baskets(self, page: int, page_size: int, keyword: str = None) -> dict:
        """篮子列表（分页 + 搜索）"""
        try:
            from shared.database.repositories.types import PaginationParams
            pagination = PaginationParams(page=page, page_size=page_size)

            if keyword:
                result = await self.basket_repo.search_baskets(keyword, pagination)
            else:
                result = await self.basket_repo.get_user_baskets(pagination=pagination)

            items = [await self._basket_to_dict(b) for b in result.items]
            return {
                "success": True,
                "message": "篮子列表获取成功",
                "data": {
                    "items": items,
                    "total": result.total,
                    "page": result.page,
                    "page_size": result.page_size,
                },
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取篮子列表失败: {str(e)}")

    async def get_basket(self, basket_id: str) -> dict:
        """篮子详情（含成分股）"""
        try:
            basket = await self.basket_repo.get_basket_with_items(basket_id)
            if not basket:
                raise HTTPException(status_code=404, detail="篮子不存在")
            return {
                "success": True,
                "message": "篮子详情获取成功",
                "data": await self._basket_to_dict(basket),
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取篮子详情失败: {str(e)}")

    async def create_basket(self, name: str, description: str, items: list = None) -> dict:
        """创建篮子（含初始成分股）"""
        try:
            basket_data = {"name": name, "description": description or ""}
            items_data = (
                [{"ts_code": it["ts_code"], "weight": it["weight"]} for it in items]
                if items else []
            )
            basket = await self.basket_repo.create_basket_with_items(basket_data, items_data)
            return {
                "success": True,
                "message": "篮子创建成功",
                "data": await self._basket_to_dict(basket),
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"创建篮子失败: {str(e)}")

    async def update_basket(self, basket_id: str, name: str = None,
                            description: str = None, items: list = None) -> dict:
        """更新篮子"""
        try:
            existing = await self.basket_repo.get(basket_id)
            if not existing:
                raise HTTPException(status_code=404, detail="篮子不存在")

            basket_data = {}
            if name is not None:
                basket_data["name"] = name
            if description is not None:
                basket_data["description"] = description

            items_data = None
            if items is not None:
                items_data = [{"ts_code": it["ts_code"], "weight": it["weight"]} for it in items]

            basket = await self.basket_repo.update_basket_with_items(
                basket_id, basket_data, items_data
            )
            return {
                "success": True,
                "message": "篮子更新成功",
                "data": await self._basket_to_dict(basket),
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"更新篮子失败: {str(e)}")

    async def delete_basket(self, basket_id: str) -> dict:
        """删除篮子及其成分股"""
        try:
            existing = await self.basket_repo.get(basket_id)
            if not existing:
                raise HTTPException(status_code=404, detail="篮子不存在")
            await self.basket_repo.delete_basket_with_items(basket_id)
            return {"success": True, "message": "篮子删除成功", "data": None}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"删除篮子失败: {str(e)}")

    # ==================== 成分股管理 ====================

    async def add_item(self, basket_id: str, ts_code: str, weight: float) -> dict:
        """添加成分股"""
        try:
            basket = await self.basket_repo.get(basket_id)
            if not basket:
                raise HTTPException(status_code=404, detail="篮子不存在")
            await self.basket_item_repo.create({
                "basket_id": basket_id, "ts_code": ts_code, "weight": weight,
            })
            basket = await self.basket_repo.get_basket_with_items(basket_id)
            return {
                "success": True,
                "message": "成分股添加成功",
                "data": await self._basket_to_dict(basket),
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"添加成分股失败: {str(e)}")

    async def adjust_weight(self, basket_id: str, ts_code: str, weight: float) -> dict:
        """调整成分股权重"""
        try:
            await self.basket_item_repo.update_item_weight(basket_id, ts_code, weight)
            basket = await self.basket_repo.get_basket_with_items(basket_id)
            return {
                "success": True,
                "message": "权重调整成功",
                "data": await self._basket_to_dict(basket),
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"调整权重失败: {str(e)}")

    async def remove_item(self, basket_id: str, ts_code: str) -> dict:
        """移除成分股"""
        try:
            await self.basket_item_repo.delete_by(basket_id=basket_id, ts_code=ts_code)
            return {"success": True, "message": "成分股移除成功", "data": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"移除成分股失败: {str(e)}")

    # ==================== 绩效分析 ====================

    async def get_performance(self, basket_id: str, start_date: str, end_date: str,
                              benchmark: str = None) -> dict:
        """篮子绩效（行情数据源接入中，暂返回占位数据）"""
        try:
            basket = await self.basket_repo.get_basket_with_items(basket_id)
            if not basket:
                raise HTTPException(status_code=404, detail="篮子不存在")

            items = [{"ts_code": it.ts_code, "weight": it.weight} for it in basket.items]
            return {
                "success": True,
                "message": "篮子绩效分析（行情数据源接入中，暂返回占位数据）",
                "data": {
                    "basket_id": basket_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "total_return": 0,
                    "annual_return": 0,
                    "max_drawdown": 0,
                    "sharpe_ratio": 0,
                    "items": items,
                },
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"获取绩效失败: {str(e)}")

    # ==================== 辅助方法 ====================

    async def _basket_to_dict(self, basket) -> dict:
        """将 Basket ORM 对象转为字典（含成分股）"""
        items = []
        if basket.items:
            items = [
                {"id": it.id, "ts_code": it.ts_code, "weight": it.weight}
                for it in basket.items
            ]
        return {
            "id": basket.id,
            "name": basket.name,
            "description": getattr(basket, "description", ""),
            "items": items,
            "item_count": len(items),
            "created_at": basket.created_at.isoformat() if basket.created_at else None,
            "updated_at": basket.updated_at.isoformat() if basket.updated_at else None,
        }


# 导出函数供router使用
async def get_order_list (session: AsyncSession, request: OrderListRequest, user_id: str) -> OrderListResponse:
	handler = TradeHandler(session)
	return await handler.get_order_list(request, user_id)


async def get_order_detail (session: AsyncSession, order_id: str, user_id: str) -> OrderDetailResponse:
	handler = TradeHandler(session)
	return await handler.get_order_detail(order_id, user_id)


async def create_order (session: AsyncSession, request: OrderCreateRequest, user_id: str) -> OrderResponse:
	handler = TradeHandler(session)
	return await handler.create_order(request, user_id)


async def cancel_order (session: AsyncSession, order_id: str, user_id: str) -> OrderDetailResponse:
	handler = TradeHandler(session)
	return await handler.cancel_order(order_id, user_id)


async def get_position_list (session: AsyncSession, request: PositionListRequest, user_id: str) -> PositionListResponse:
	handler = TradeHandler(session)
	return await handler.get_position_list(request, user_id)


async def get_position_detail (session: AsyncSession, ts_code: str, user_id: str) -> PositionDetailResponse:
	handler = TradeHandler(session)
	return await handler.get_position_detail(ts_code, user_id)


async def execute_signal (session: AsyncSession, request: SignalExecuteRequest, user_id: str) -> SignalExecuteResponse:
	handler = TradeHandler(session)
	return await handler.execute_signal(request, user_id)


async def get_trade_history (session: AsyncSession, request: TradeHistoryRequest, user_id: str) -> TradeHistoryResponse:
	handler = TradeHandler(session)
	return await handler.get_trade_history(request, user_id)


async def get_account_summary (session: AsyncSession, user_id: str) -> AccountSummaryResponse:
	handler = TradeHandler(session)
	return await handler.get_account_summary(user_id)


async def check_trade_module_health (session: AsyncSession) -> Dict:
	handler = TradeHandler(session)
	return await handler.check_trade_module_health()


# ==================== BasketHandler 包装函数 ====================

async def get_basket_list(session: AsyncSession, page: int, page_size: int,
                          keyword: str = None) -> dict:
	handler = BasketHandler(session)
	return await handler.get_baskets(page, page_size, keyword)


async def get_basket_detail(session: AsyncSession, basket_id: str) -> dict:
	handler = BasketHandler(session)
	return await handler.get_basket(basket_id)


async def create_basket_item(session: AsyncSession, name: str, description: str,
                             items: list = None) -> dict:
	handler = BasketHandler(session)
	return await handler.create_basket(name, description, items)


async def update_basket_item(session: AsyncSession, basket_id: str, name: str = None,
                             description: str = None, items: list = None) -> dict:
	handler = BasketHandler(session)
	return await handler.update_basket(basket_id, name, description, items)


async def delete_basket_item(session: AsyncSession, basket_id: str) -> dict:
	handler = BasketHandler(session)
	return await handler.delete_basket(basket_id)


async def add_basket_item(session: AsyncSession, basket_id: str,
                          ts_code: str, weight: float) -> dict:
	handler = BasketHandler(session)
	return await handler.add_item(basket_id, ts_code, weight)


async def adjust_basket_weight(session: AsyncSession, basket_id: str,
                               ts_code: str, weight: float) -> dict:
	handler = BasketHandler(session)
	return await handler.adjust_weight(basket_id, ts_code, weight)


async def remove_basket_item(session: AsyncSession, basket_id: str,
                             ts_code: str) -> dict:
	handler = BasketHandler(session)
	return await handler.remove_item(basket_id, ts_code)


async def get_basket_performance(session: AsyncSession, basket_id: str,
                                 start_date: str, end_date: str,
                                 benchmark: str = None) -> dict:
	handler = BasketHandler(session)
	return await handler.get_performance(basket_id, start_date, end_date, benchmark)
