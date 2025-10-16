# stock_daily_limit_service.py (completed)
from ..services.base_service import BaseService
from quant_server.db.models.data_models import StockDailyLimit
from typing import List, Dict, Any


class StockDailyLimitService(BaseService):
    """股票每日涨跌停数据服务"""

    def create(self, data: dict) -> StockDailyLimit:
        with self.session_scope() as session:
            instance = StockDailyLimit(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, stock_daily_limit_id: int) -> StockDailyLimit:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).get(stock_daily_limit_id)

    def update(self, stock_daily_limit_id: int, update_data: dict) -> StockDailyLimit:
        with self.session_scope() as session:
            instance = session.query(StockDailyLimit).get(stock_daily_limit_id)
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, stock_daily_limit_id: int) -> None:
        with self.session_scope() as session:
            instance = session.query(StockDailyLimit).get(stock_daily_limit_id)
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[StockDailyLimit]:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter_by(**filters).all()

    def get_all(self) -> list[StockDailyLimit]:
        with self.session_scope() as session:
            return session.query(StockDailyLimit).all()

    def get_by_stock_date(self, ts_code: str, trade_date):
        """获取指定股票和日期的涨跌停数据"""
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter(
                StockDailyLimit.ts_code == ts_code,
                StockDailyLimit.trade_date == trade_date
            ).first()

    def get_limit_up_stocks(self, trade_date):
        """获取指定日期涨停的股票"""
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter(
                StockDailyLimit.trade_date == trade_date,
                StockDailyLimit.up_limit == StockDailyLimit.up_limit
            ).all()

    def get_limit_down_stocks(self, trade_date):
        """获取指定日期跌停的股票"""
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter(
                StockDailyLimit.trade_date == trade_date,
                StockDailyLimit.down_limit == StockDailyLimit.down_limit
            ).all()

    def get_by_date_range(self, ts_code: str, start_date, end_date) -> list[StockDailyLimit]:
        """获取指定日期范围的涨跌停数据"""
        with self.session_scope() as session:
            return session.query(StockDailyLimit).filter(
                StockDailyLimit.ts_code == ts_code,
                StockDailyLimit.trade_date >= start_date,
                StockDailyLimit.trade_date <= end_date
            ).order_by(StockDailyLimit.trade_date).all()

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[StockDailyLimit]:
        """
        批量创建涨跌停数据记录

        Args:
            data_list: 涨跌停数据字典列表

        Returns:
            List[StockDailyLimit]: 创建的涨跌停数据对象列表
        """
        if not data_list:
            return []

        with self.session_scope() as session:
            instances = []
            for data in data_list:
                # 检查是否已存在相同股票和日期的记录
                existing = session.query(StockDailyLimit).filter(
                    StockDailyLimit.ts_code == data.get('ts_code'),
                    StockDailyLimit.trade_date == data.get('trade_date')
                ).first()

                if not existing:
                    instance = StockDailyLimit(**data)
                    session.add(instance)
                    instances.append(instance)
                else:
                    # 如果已存在，则更新记录
                    for key, value in data.items():
                        if hasattr(existing, key):
                            setattr(existing, key, value)
                    instances.append(existing)

            session.flush()
            return instances

    def batch_create_or_update(self, data_list: List[Dict[str, Any]]) -> List[StockDailyLimit]:
        """
        批量创建或更新涨跌停数据记录（使用upsert策略）

        Args:
            data_list: 涨跌停数据字典列表

        Returns:
            List[StockDailyLimit]: 创建或更新的涨跌停数据对象列表
        """
        if not data_list:
            return []

        with self.session_scope() as session:
            instances = []
            for data in data_list:
                ts_code = data.get('ts_code')
                trade_date = data.get('trade_date')

                if not ts_code or not trade_date:
                    continue

                # 查找现有记录
                existing = session.query(StockDailyLimit).filter(
                    StockDailyLimit.ts_code == ts_code,
                    StockDailyLimit.trade_date == trade_date
                ).first()

                if existing:
                    # 更新现有记录
                    for key, value in data.items():
                        if hasattr(existing, key) and key not in ['id', 'ts_code', 'trade_date']:
                            setattr(existing, key, value)
                    instances.append(existing)
                else:
                    # 创建新记录
                    instance = StockDailyLimit(**data)
                    session.add(instance)
                    instances.append(instance)

            session.flush()
            return instances

    def batch_delete(self, stock_daily_limit_ids: List[int]) -> bool:
        """
        批量删除涨跌停数据记录

        Args:
            stock_daily_limit_ids: 要删除的记录ID列表

        Returns:
            bool: 删除操作是否成功
        """
        if not stock_daily_limit_ids:
            return True

        with self.session_scope() as session:
            try:
                session.query(StockDailyLimit).filter(
                    StockDailyLimit.id.in_(stock_daily_limit_ids)
                ).delete(synchronize_session=False)
                return True
            except Exception as e:
                session.rollback()
                print(f"批量删除涨跌停数据失败: {str(e)}")
                return False

    def get_recent_limit_data(self, days: int = 30) -> List[StockDailyLimit]:
        """
        获取最近N天的涨跌停数据

        Args:
            days: 天数，默认30天

        Returns:
            List[StockDailyLimit]: 最近N天的涨跌停数据列表
        """
        with self.session_scope() as session:
            from datetime import datetime, timedelta
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')

            return session.query(StockDailyLimit).filter(
                StockDailyLimit.trade_date >= start_date
            ).order_by(StockDailyLimit.trade_date.desc()).all()

    def get_stock_limit_history(self, ts_code: str, limit_type: str = 'both') -> List[StockDailyLimit]:
        """
        获取指定股票的涨跌停历史

        Args:
            ts_code: 股票代码
            limit_type: 类型，'up'=涨停, 'down'=跌停, 'both'=两者都包括

        Returns:
            List[StockDailyLimit]: 涨跌停历史数据列表
        """
        with self.session_scope() as session:
            query = session.query(StockDailyLimit).filter(
                StockDailyLimit.ts_code == ts_code
            )

            if limit_type == 'up':
                query = query.filter(StockDailyLimit.up_limit.isnot(None))
            elif limit_type == 'down':
                query = query.filter(StockDailyLimit.down_limit.isnot(None))

            return query.order_by(StockDailyLimit.trade_date.desc()).all()