# -*- coding: utf-8 -*-
"""
基金数据仓库
位置：quant_server/shared/database/repositories/market/basic/fund_repo.py
职责：管理基金基础信息、净值、持仓等数据访问
设计原则：继承BaseRepository，使用统一数据访问接口
注意：基金数据包括公募基金、私募基金等各类基金产品
"""

from datetime import date
from typing import List, Optional, Dict, Any

from sqlalchemy import select, and_, or_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from quant_server.shared.database.repositories.base.repository_base import BaseRepository, RepositoryError


# ==================== 基金仓库类 ====================

class FundRepository(BaseRepository):
    """
    基金仓库 - 继承BaseRepository
    
    注意：由于基金模型尚未完全定义，此仓库提供基础框架
    当基金模型定义完成后，需要更新模型类型注解
    """

    def __init__(self, session: AsyncSession, model_class):
        """
        初始化基金仓库

        Args:
            session: 数据库会话
            model_class: 基金模型类
        """
        super().__init__(session, model_class)

    async def search_funds (
            self,
            keyword: str,
            fund_type: Optional[str] = None,
            limit: int = 100,
            offset: int = 0
    ) -> List:
        """
        搜索基金

        Args:
            keyword: 搜索关键词（匹配代码、名称等）
            fund_type: 基金类型过滤（可选）
            limit: 返回数量限制
            offset: 跳过记录数

        Returns:
            基金列表
        """
        try:
            # 构建查询条件
            conditions = []
            
            # 检查模型是否支持搜索字段
            if hasattr(self.model, 'fund_code') and hasattr(self.model, 'fund_name'):
                conditions.append(
                    or_(
                        self.model.fund_code.like(f"%{keyword}%"),
                        self.model.fund_name.like(f"%{keyword}%")
                    )
                )
            
            # 添加基金类型过滤
            if fund_type and hasattr(self.model, 'fund_type'):
                conditions.append(self.model.fund_type == fund_type)
            
            if not conditions:
                raise RepositoryError("模型不支持基金搜索功能")

            # 构建查询
            query = select(self.model).where(and_(*conditions))

            # 排序和分页
            order_field = getattr(self.model, 'fund_code', 'id')
            query = query.order_by(order_field).offset(offset).limit(limit)

            result = await self.session.execute(query)
            return result.scalars().all()

        except Exception as e:
            raise RepositoryError(f"搜索基金失败: {str(e)}")

    async def get_by_manager (self, manager_code: str) -> List:
        """
        获取基金经理管理的基金

        Args:
            manager_code: 基金经理代码

        Returns:
            基金列表
        """
        if hasattr(self.model, 'manager_code'):
            return await self.get_many(manager_code=manager_code)
        else:
            raise RepositoryError("模型不支持manager_code字段")

    async def get_by_type (self, fund_type: str) -> List:
        """
        根据类型获取基金

        Args:
            fund_type: 基金类型

        Returns:
            基金列表
        """
        if hasattr(self.model, 'fund_type'):
            return await self.get_many(fund_type=fund_type)
        else:
            raise RepositoryError("模型不支持fund_type字段")

    async def get_latest_nav (self, fund_code: str) -> Optional:
        """
        获取最新的基金净值

        Args:
            fund_code: 基金代码

        Returns:
            最新的基金净值或None
        """
        try:
            if not all(hasattr(self.model, attr) for attr in ['fund_code', 'nav_date']):
                raise RepositoryError("模型缺少必要字段")

            query = select(self.model).where(
                self.model.fund_code == fund_code
            ).order_by(desc(self.model.nav_date)).limit(1)

            result = await self.session.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            raise RepositoryError(f"获取最新基金净值失败: {str(e)}")

    async def get_nav_by_date_range (
            self,
            fund_code: str,
            start_date: date,
            end_date: date
    ) -> List:
        """
        获取指定时间范围内的基金净值

        Args:
            fund_code: 基金代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            基金净值列表
        """
        try:
            if not all(hasattr(self.model, attr) for attr in ['fund_code', 'nav_date']):
                raise RepositoryError("模型缺少必要字段")

            query = select(self.model).where(
                and_(
                    self.model.fund_code == fund_code,
                    self.model.nav_date >= start_date,
                    self.model.nav_date <= end_date
                )
            ).order_by(self.model.nav_date)

            result = await self.session.execute(query)
            return result.scalars().all()

        except Exception as e:
            raise RepositoryError(f"获取基金净值范围失败: {str(e)}")

    async def get_fund_statistics (self, fund_code: str) -> Dict[str, Any]:
        """
        获取基金统计信息

        Args:
            fund_code: 基金代码

        Returns:
            基金统计信息字典
        """
        try:
            if not all(hasattr(self.model, attr) for attr in ['fund_code', 'nav_date', 'nav']):
                raise RepositoryError("模型缺少必要字段")

            # 查询基础统计
            stats_query = select(
                func.count(self.model.id).label('total_records'),
                func.min(self.model.nav_date).label('first_date'),
                func.max(self.model.nav_date).label('last_date'),
                func.min(self.model.nav).label('min_nav'),
                func.max(self.model.nav).label('max_nav'),
                func.avg(self.model.nav).label('avg_nav')
            ).where(self.model.fund_code == fund_code)

            result = await self.session.execute(stats_query)
            stats = result.first()

            if not stats:
                return {}

            return {
                'fund_code': fund_code,
                'total_records': stats.total_records,
                'date_range': {
                    'first': stats.first_date,
                    'last': stats.last_date
                },
                'nav_range': {
                    'min': stats.min_nav,
                    'max': stats.max_nav,
                    'avg': stats.avg_nav
                }
            }

        except Exception as e:
            raise RepositoryError(f"获取基金统计失败: {str(e)}")

    async def get_fund_returns (
            self,
            fund_code: str,
            start_date: date,
            end_date: date
    ) -> Dict[str, Any]:
        """
        计算基金收益率

        Args:
            fund_code: 基金代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            收益率信息字典
        """
        try:
            if not all(hasattr(self.model, attr) for attr in ['fund_code', 'nav_date', 'nav']):
                raise RepositoryError("模型缺少必要字段")

            # 获取开始和结束日期的净值
            start_nav_query = select(self.model.nav).where(
                and_(
                    self.model.fund_code == fund_code,
                    self.model.nav_date >= start_date
                )
            ).order_by(self.model.nav_date).limit(1)

            end_nav_query = select(self.model.nav).where(
                and_(
                    self.model.fund_code == fund_code,
                    self.model.nav_date <= end_date
                )
            ).order_by(desc(self.model.nav_date)).limit(1)

            start_result = await self.session.execute(start_nav_query)
            end_result = await self.session.execute(end_nav_query)

            start_nav = start_result.scalar()
            end_nav = end_result.scalar()

            if not start_nav or not end_nav:
                return {}

            # 计算收益率
            total_return = (end_nav - start_nav) / start_nav

            return {
                'fund_code': fund_code,
                'start_date': start_date,
                'end_date': end_date,
                'start_nav': start_nav,
                'end_nav': end_nav,
                'total_return': total_return,
                'total_return_percent': total_return * 100
            }

        except Exception as e:
            raise RepositoryError(f"计算基金收益率失败: {str(e)}")


# ==================== 基金聚合服务类 ====================

class FundService:
    """
    基金聚合服务类
    
    提供基金相关的聚合服务，协调多个仓库的数据访问
    遵循服务层无状态原则，不持有事件引擎引用
    """

    def __init__(self, fund_repository: FundRepository):
        """
        初始化基金服务

        Args:
            fund_repository: 基金仓库实例
        """
        self.fund_repo = fund_repository

    async def get_fund_comprehensive_info (self, fund_code: str) -> Dict[str, Any]:
        """
        获取基金综合信息

        Args:
            fund_code: 基金代码

        Returns:
            基金综合信息字典
        """
        try:
            # 获取基础信息
            basic_info = await self.fund_repo.get_by(fund_code=fund_code)
            
            # 获取统计信息
            statistics = await self.fund_repo.get_fund_statistics(fund_code)
            
            # 获取最新净值
            latest_nav = await self.fund_repo.get_latest_nav(fund_code)

            return {
                'basic_info': basic_info,
                'statistics': statistics,
                'latest_nav': latest_nav
            }

        except Exception as e:
            raise RepositoryError(f"获取基金综合信息失败: {str(e)}")

    async def search_funds_with_details (
            self,
            keyword: str,
            fund_type: Optional[str] = None,
            limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        搜索基金并返回详细信息

        Args:
            keyword: 搜索关键词
            fund_type: 基金类型过滤
            limit: 返回数量限制

        Returns:
            基金详细信息列表
        """
        try:
            # 搜索基金
            funds = await self.fund_repo.search_funds(keyword, fund_type, limit)
            
            results = []
            for fund in funds:
                fund_code = getattr(fund, 'fund_code', None)
                if fund_code:
                    # 获取每个基金的详细信息
                    fund_info = await self.get_fund_comprehensive_info(fund_code)
                    results.append(fund_info)
            
            return results

        except Exception as e:
            raise RepositoryError(f"搜索基金详细信息失败: {str(e)}")


# ==================== 导出定义 ====================

__all__ = [
    'FundRepository',
    'FundService',
    'RepositoryError'
]