import logging

from sqlalchemy.orm import Session
from typing import List, Optional, Any
from datetime import datetime

from quant_server.shared.database.models.data_models import TradeCalendar
from quant_server.db.services.base_service import BaseService

logger = logging.getLogger(__name__)


class TradeCalendarService(BaseService):
    """交易日历服务类"""

    def __init__(self, session: Session):
        super().__init__(session)

    def create(self, data: dict) -> TradeCalendar:
        """创建交易日历记录"""
        with self.session_scope() as session:
            trade_calendar = TradeCalendar(**data)
            session.add(trade_calendar)
            return trade_calendar

    def get(self, pk: Any) -> Optional[TradeCalendar]:
        """
        根据主键获取记录
        对于TradeCalendar，主键是(exchange, cal_date)元组
        """
        if not isinstance(pk, tuple) or len(pk) != 2:
            raise ValueError("TradeCalendar的主键应该是(exchange, cal_date)元组")

        exchange, cal_date = pk
        return self.get_by_exchange_and_date(exchange, cal_date)

    def update(self, pk: Any, update_data: dict) -> Optional[TradeCalendar]:
        """
        更新记录
        对于TradeCalendar，主键是(exchange, cal_date)元组
        """
        if not isinstance(pk, tuple) or len(pk) != 2:
            raise ValueError("TradeCalendar的主键应该是(exchange, cal_date)元组")

        exchange, cal_date = pk
        return self.update_by_exchange_and_date(exchange, cal_date, update_data)

    def delete(self, pk: Any) -> bool:
        """
        删除记录
        对于TradeCalendar，主键是(exchange, cal_date)元组
        """
        if not isinstance(pk, tuple) or len(pk) != 2:
            raise ValueError("TradeCalendar的主键应该是(exchange, cal_date)元组")

        exchange, cal_date = pk
        return self.delete_by_exchange_and_date(exchange, cal_date)

    def filter(self, **filters) -> List[TradeCalendar]:
        """根据条件过滤交易日历记录"""
        with self.session_scope() as session:
            query = session.query(TradeCalendar)
            for attr, value in filters.items():
                if hasattr(TradeCalendar, attr):
                    query = query.filter(getattr(TradeCalendar, attr) == value)
            return query.all()

    def get_all(self) -> List[TradeCalendar]:
        """获取所有交易日历记录"""
        with self.session_scope() as session:
            return session.query(TradeCalendar).all()

    def get_by_exchange_and_date(self, exchange: str, cal_date: datetime) -> Optional[TradeCalendar]:
        """根据交易所和日期获取交易日历记录"""
        with self.session_scope() as session:
            return session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date == cal_date
            ).first()

    def update_by_exchange_and_date(self, exchange: str, cal_date: datetime, update_data: dict) -> Optional[
        TradeCalendar]:
        """根据交易所和日期更新记录"""
        with self.session_scope() as session:
            trade_calendar = session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date == cal_date
            ).first()

            if trade_calendar:
                for key, value in update_data.items():
                    setattr(trade_calendar, key, value)

            return trade_calendar

    def delete_by_exchange_and_date(self, exchange: str, cal_date: datetime) -> bool:
        """根据交易所和日期删除记录"""
        with self.session_scope() as session:
            trade_calendar = session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date == cal_date
            ).first()

            if trade_calendar:
                session.delete(trade_calendar)
                return True
            return False

    def get_trading_days(self, exchange: str, start_date: datetime, end_date: datetime) -> List[TradeCalendar]:
        """获取指定交易所和时间范围内的交易日"""
        with self.session_scope() as session:
            return session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date >= start_date,
                TradeCalendar.cal_date <= end_date,
                TradeCalendar.is_open == True
            ).order_by(TradeCalendar.cal_date).all()

    def is_trading_day(self, exchange: str, date: datetime) -> bool:
        """检查指定日期是否为交易日"""
        with self.session_scope() as session:
            day = session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date == date
            ).first()
            return day.is_open if day else False

    def get_previous_trading_day(self, exchange: str, date: datetime) -> Optional[TradeCalendar]:
        """获取指定日期的前一个交易日"""
        with self.session_scope() as session:
            return session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date < date,
                TradeCalendar.is_open == True
            ).order_by(TradeCalendar.cal_date.desc()).first()