# # -*- coding: utf-8 -*-
# """
# 基金数据仓库
# 位置：quant_server/shared/database/repositories/market/basic/fund_repo.py
# 职责：管理基金基础信息、净值、持仓等数据访问
# 设计原则：继承BaseRepository，使用统一数据访问接口
# 注意：基金数据包括公募基金、私募基金等各类基金产品
# """
#
# from typing import List, Optional, Dict, Any
# from datetime import datetime, date
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy import select, and_, or_, func, desc, asc, text
# from sqlalchemy.orm import selectinload, joinedload
#
# from quant_server.shared.database.repositories.base import BaseRepository, RepositoryError
#
# # ==================== 基金模型定义（根据data_models.py中的定义）====================
#
# from quant_server.shared.database.models.data_models import (
# 	# 假设基金模型已定义，如果未定义需要先定义
# 	FundBasic, FundNav, FundPortfolio, FundManager
#
# )
#
# # 如果基金模型未在data_models.py中定义，这里需要添加
# # 由于设计文档中没有基金模型的具体定义，这里假设已存在
#
# # ==================== 基金仓库类 ====================
#
# class FundBasicRepository(BaseRepository):
# 	"""基金基础信息仓库 - 继承BaseRepository"""
#
# 	def __init__ (self, session: AsyncSession, model_class):
# 		"""初始化基金基础信息仓库"""
# 		super().__init__(session, model_class)
#
# 	async def search_by_keyword (
# 			self,
# 			keyword: str,
# 			fund_type: Optional[str] = None,
# 			limit: int = 100,
# 			skip: int = 0
# 	) -> List:
# 		"""
# 		搜索基金
#
# 		Args:
# 			keyword: 搜索关键词（匹配代码、名称等）
# 			fund_type: 基金类型过滤（可选）
# 			limit: 返回数量限制
# 			skip: 跳过记录数
#
# 		Returns:
# 			基金列表
# 		"""
# 		try:
# 			# 构建查询条件
# 			conditions = [
# 				or_(
# 					getattr(self.model, 'fund_code').like(f"%{keyword}%"),
# 					getattr(self.model, 'fund_name').like(f"%{keyword}%")
# 				)
# 			]
#
# 			# 添加基金类型过滤
# 			if fund_type and hasattr(self.model, 'fund_type'):
# 				conditions.append(getattr(self.model, 'fund_type') == fund_type)
#
# 			# 构建查询
# 			query = select(self.model).where(and_(*conditions))
#
# 			# 排序和分页
# 			order_field = getattr(self.model, 'fund_code', 'id')
# 			query = query.order_by(order_field).offset(skip).limit(limit)
#
# 			result = await self.session.execute(query)
# 			return result.scalars().all()
#
# 		except Exception as e:
# 			raise RepositoryError(f"搜索基金失败: {str(e)}")
#
# 	async def get_by_manager (self, manager_code: str) -> List:
# 		"""
# 		获取基金经理管理的基金
#
# 		Args:
# 			manager_code: 基金经理代码
#
# 		Returns:
# 			基金列表
# 		"""
# 		if hasattr(self.model, 'manager_code'):
# 			return await self.get_many(manager_code=manager_code)
# 		else:
# 			raise RepositoryError("模型不支持manager_code字段")
#
# 	async def get_by_type (self, fund_type: str) -> List:
# 		"""
# 		根据类型获取基金
#
# 		Args:
# 			fund_type: 基金类型
#
# 		Returns:
# 			基金列表
# 		"""
# 		if hasattr(self.model, 'fund_type'):
# 			return await self.get_many(fund_type=fund_type)
# 		else:
# 			raise RepositoryError("模型不支持fund_type字段")
#
#
# class FundNavRepository(BaseRepository):
# 	"""基金净值仓库 - 继承BaseRepository"""
#
# 	def __init__ (self, session: AsyncSession, model_class):
# 		"""初始化基金净值仓库"""
# 		super().__init__(session, model_class)
#
# 	async def get_by_date_range (
# 			self,
# 			fund_code: str,
# 			start_date: date,
# 			end_date: date
# 	) -> List:
# 		"""
# 		获取指定时间范围内的基金净值
#
# 		Args:
# 			fund_code: 基金代码
# 			start_date: 开始日期
# 			end_date: 结束日期
#
# 		Returns:
# 			基金净值列表
# 		"""
# 		try:
# 			# 检查模型字段
# 			if not all(hasattr(self.model, attr) for attr in ['fund_code', 'nav_date']):
# 				raise RepositoryError("模型缺少必要字段")
#
# 			query = select(self.model).where(
# 				and_(
# 					getattr(self.model, 'fund_code') == fund_code,
# 					getattr(self.model, 'nav_date') >= start_date,
# 					getattr(self.model, 'nav_date') <= end_date
# 				)
# 			).order_by(getattr(self.model, 'nav_date'))
#
# 			result = await self.session.execute(query)
# 			return result.scalars().all()
#
# 		except Exception as e:
# 			raise RepositoryError(f"获取基金净值范围失败: {str(e)}")
#
# 	async def get_latest_by_fund_code (self, fund_code: str) -> Optional:
# 		"""
# 		获取最新的基金净值
#
# 		Args:
# 			fund_code: 基金代码
#
# 		Returns:
# 			最新的基金净值或None
# 		"""
# 		try:
# 			if not all(hasattr(self.model, attr) for attr in ['fund_code', 'nav_date']):
# 				raise RepositoryError("模型缺少必要字段")
#
# 			query = select(self.model).where(
# 				getattr(self.model, 'fund_code') == fund_code
# 			).order_by(desc(getattr(self.model, 'nav_date'))).limit(1)
#
# 			result = await self.session.execute(query)
# 			return result.scalar_one_or_none()
#
# 		except Exception as e:
# 			raise RepositoryError(f"获取最新基金净值失败: {str(e)}")
#
#
# # ==================== 基金聚合仓库 ====================
#
# class FundRepository:
# 	"""基金聚合仓库 - 协调基金相关所有数据访问"""
#
# 	def __init__ (self, session: AsyncSession):
# 		"""初始化基金聚合仓库"""
# 		self.session = session
#
# 		# 根据实际模型类初始化各仓库
# 		# 这里需要根据实际模型类进行初始化
# 		try:
# 			from quant_server.shared.database.models.data_models import (
# 				FundBasic, FundNav, FundPortfolio, FundManager
# 			)
#
# 			self.fund_basic_repo = FundBasicRepository(session, FundBasic)
# 			self.fund_nav_repo = FundNavRepository(session, FundNav)
# 		# 其他仓库类似初始化
#
# 		except ImportError:
# 			# 如果模型未定义，使用默认值
# 			self.fund_basic_repo = None
# 			self.fund_nav_repo = None
#
# 	# ==================== 基础信息操作 ====================
#
# 	async def get_fund_basic (self, fund_code: str) -> Optional:
# 		"""获取基金基础信息"""
# 		if self.fund_basic_repo:
# 			return await self.fund_basic_repo.get_by(fund_code=fund_code)
# 		return None
#
# 	async def search_funds (
# 			self,
# 			keyword: str,
# 			fund_type: Optional[str] = None,
# 			limit: int = 100,
# 			skip: int = 0
# 	) -> List:
# 		"""搜索基金"""
# 		if self.fund_basic_repo:
# 			return await self.fund_basic_repo.search_by_keyword(
# 				keyword, fund_type, limit, skip
# 			)
# 		return []
#
# 	# ==================== 净值操作 ====================
#
# 	async def get_fund_nav (self, fund_code: str, nav_date: date) -> Optional:
# 		"""获取基金净值"""
# 		if self.fund_nav_repo:
# 			return await self.fund_nav_repo.get_by(
# 				fund_code=fund_code,
# 				nav_date=nav_date
# 			)
# 		return None
#
# 	async def get_fund_nav_range (
# 			self,
# 			fund_code: str,
# 			start_date: date,
# 			end_date: date
# 	) -> List:
# 		"""获取基金净值范围"""
# 		if self.fund_nav_repo:
# 			return await self.fund_nav_repo.get_by_date_range(
# 				fund_code, start_date, end_date
# 			)
# 		return []
#
# 	async def get_latest_fund_nav (self, fund_code: str) -> Optional:
# 		"""获取最新基金净值"""
# 		if self.fund_nav_repo:
# 			return await self.fund_nav_repo.get_latest_by_fund_code(fund_code)
# 		return None
#
# 	# ==================== 统计分析操作 ====================
#
# 	async def analyze_fund_performance (
# 			self,
# 			fund_code: str,
# 			start_date: date,
# 			end_date: date
# 	) -> Dict[str, Any]:
# 		"""
# 		分析基金表现
#
# 		Args:
# 			fund_code: 基金代码
# 			start_date: 开始日期
# 			end_date: 结束日期
#
# 		Returns:
# 			基金表现分析结果
# 		"""
# 		# 获取基金净值数据
# 		nav_data = await self.get_fund_nav_range(fund_code, start_date, end_date)
#
# 		if not nav_data:
# 			return {"error": "没有找到净值数据"}
#
# 		# 获取基金基础信息
# 		fund_info = await self.get_fund_basic(fund_code)
#
# 		# 计算统计指标
# 		import statistics
#
# 		# 获取净值列表
# 		nav_values = []
# 		for nav in nav_data:
# 			# 根据实际模型字段获取净值
# 			if hasattr(nav, 'unit_nav'):
# 				nav_values.append(nav.unit_nav)
# 			elif hasattr(nav, 'nav_value'):
# 				nav_values.append(nav.nav_value)
#
# 		if len(nav_values) < 2:
# 			return {"error": "数据不足"}
#
# 		# 计算收益
# 		first_nav = nav_values[0]
# 		last_nav = nav_values[-1]
# 		total_return = (last_nav - first_nav) / first_nav
#
# 		# 计算日收益
# 		daily_returns = []
# 		for i in range(1, len(nav_values)):
# 			daily_return = (nav_values[i] - nav_values[i - 1]) / nav_values[i - 1]
# 			daily_returns.append(daily_return)
#
# 		# 计算统计指标
# 		avg_return = statistics.mean(daily_returns) if daily_returns else 0
# 		volatility = statistics.stdev(daily_returns) * (252 ** 0.5) if daily_returns else 0
# 		sharpe_ratio = (avg_return * 252) / volatility if volatility != 0 else 0
#
# 		# 计算最大回撤
# 		max_drawdown = 0
# 		peak = nav_values[0]
# 		for nav in nav_values:
# 			if nav > peak:
# 				peak = nav
# 			drawdown = (peak - nav) / peak
# 			if drawdown > max_drawdown:
# 				max_drawdown = drawdown
#
# 		return {
# 			"fund_code": fund_code,
# 			"analysis_period": {
# 				"start_date": start_date,
# 				"end_date": end_date,
# 				"days": len(nav_data)
# 			},
# 			"performance_metrics": {
# 				"total_return": total_return,
# 				"annualized_return": total_return * (252 / len(nav_data)) if len(nav_data) > 0 else 0,
# 				"volatility": volatility,
# 				"sharpe_ratio": sharpe_ratio,
# 				"max_drawdown": max_drawdown,
# 				"average_daily_return": avg_return
# 			},
# 			"fund_info": fund_info if fund_info else {}
# 		}
#
# 	# ==================== 批量操作 ====================
#
# 	async def batch_create_fund_navs (self, nav_data_list: List[Dict[str, Any]]) -> List:
# 		"""批量创建基金净值记录"""
# 		if self.fund_nav_repo:
# 			return await self.fund_nav_repo.batch_create(nav_data_list)
# 		return []