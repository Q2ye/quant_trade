# stock_basic_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime

from sqlalchemy import and_, or_,func
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.models import StockBasic


class StockBasicService(BaseService):
    """股票基础信息服务"""

    def create(self, data: Dict[str, Any]) -> StockBasic:
        """创建新股票记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(StockBasic).filter_by(ts_code=data['ts_code']).first()
            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            stock = StockBasic(**data)
            session.add(stock)
            session.flush()
            return stock

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[StockBasic]:
        """批量创建股票记录"""
        results = []
        with self.session_scope() as session:
            for data in data_list:
                # 检查是否已存在
                existing = session.query(StockBasic).filter_by(ts_code=data['ts_code']).first()
                if existing:
                    # 更新现有记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    results.append(existing)
                else:
                    # 创建新记录
                    stock = StockBasic(**data)
                    session.add(stock)
                    results.append(stock)
            session.flush()
        return results

    def get(self, ts_code: str) -> Optional[StockBasic]:
        """根据股票代码获取股票信息"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter_by(ts_code=ts_code).first()

    def update(self, ts_code: str, update_data: Dict[str, Any]) -> Optional[StockBasic]:
        """更新股票信息"""
        with self.session_scope() as session:
            stock = session.query(StockBasic).filter_by(ts_code=ts_code).first()
            if stock:
                for key, value in update_data.items():
                    setattr(stock, key, value)
                return stock
            return None

    def delete(self, ts_code: str) -> bool:
        """删除股票记录"""
        with self.session_scope() as session:
            stock = session.query(StockBasic).filter_by(ts_code=ts_code).first()
            if stock:
                session.delete(stock)
                return True
            return False

    def filter(self, **filters) -> List[StockBasic]:
        """根据条件过滤股票记录"""
        with self.session_scope() as session:
            query = session.query(StockBasic)
            for key, value in filters.items():
                query = query.filter(getattr(StockBasic, key) == value)
            return query.all()

    def get_all(self) -> List[StockBasic]:
        """获取所有股票记录"""
        with self.session_scope() as session:
            return session.query(StockBasic).all()

    def get_by_ts_code(self, ts_code: str) -> Optional[StockBasic]:
        """根据股票代码获取股票信息"""
        return self.get(ts_code)

    def get_by_symbol(self, symbol: str) -> Optional[StockBasic]:
        """根据股票符号获取股票信息"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter_by(symbol=symbol).first()

    def list_active_stocks(self) -> List[StockBasic]:
        """获取上市状态的股票列表"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter_by(list_status='L').all()

    def get_by_industry(self, industry: str) -> List[StockBasic]:
        """根据行业获取股票列表"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter_by(industry=industry).all()

    def get_by_market(self, market: str) -> List[StockBasic]:
        """根据市场类型获取股票列表"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter_by(market=market).all()

    def get_by_exchange(self, exchange: str) -> List[StockBasic]:
        """根据交易所获取股票列表"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter_by(exchange=exchange).all()

    def search_by_name(self, name: str) -> List[StockBasic]:
        """根据名称搜索股票"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter(
                or_(
                    StockBasic.name.like(f"%{name}%"),
                    StockBasic.fullname.like(f"%{name}%"),
                    StockBasic.cnspell.like(f"%{name}%")
                )
            ).all()

    def get_stocks_by_list_date_range(self, start_date: datetime, end_date: datetime) -> List[StockBasic]:
        """获取指定上市日期范围内的股票"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter(
                and_(
                    StockBasic.list_date >= start_date,
                    StockBasic.list_date <= end_date
                )
            ).all()

    def get_hs_stocks(self) -> List[StockBasic]:
        """获取沪深港通标的股票"""
        with self.session_scope() as session:
            return session.query(StockBasic).filter(
                StockBasic.is_hs.in_(['H', 'S'])
            ).all()

    def count_by_industry(self) -> Dict[str, int]:
        """统计各行业的股票数量"""
        with self.session_scope() as session:
            result = session.query(
                StockBasic.industry,
                func.count(StockBasic.ts_code)
            ).group_by(StockBasic.industry).all()
            return {industry: count for industry, count in result}

    def count_by_area(self) -> Dict[str, int]:
        """统计各地区的股票数量"""
        with self.session_scope() as session:
            result = session.query(
                StockBasic.area,
                func.count(StockBasic.ts_code)
            ).group_by(StockBasic.area).all()
            return {area: count for area, count in result}
