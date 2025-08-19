# trade_calendar_service.py (completed)
from quant_server.db.base_service import BaseService
from quant_server.db.models.models import TradeCalendar


class TradeCalendarService(BaseService):
    """交易日历数据服务"""

    def create(self, data: dict) -> TradeCalendar:
        with self.session_scope() as session:
            instance = TradeCalendar(**data)
            session.add(instance)
            session.flush()
            return instance

    def get(self, keys: tuple) -> TradeCalendar:
        exchange, cal_date = keys
        with self.session_scope() as session:
            return session.query(TradeCalendar).get((exchange, cal_date))

    def update(self, keys: tuple, update_data: dict) -> TradeCalendar:
        exchange, cal_date = keys
        with self.session_scope() as session:
            instance = session.query(TradeCalendar).get((exchange, cal_date))
            if instance:
                for key, value in update_data.items():
                    setattr(instance, key, value)
            return instance

    def delete(self, keys: tuple) -> None:
        exchange, cal_date = keys
        with self.session_scope() as session:
            instance = session.query(TradeCalendar).get((exchange, cal_date))
            if instance:
                session.delete(instance)

    def filter(self, **filters) -> list[TradeCalendar]:
        with self.session_scope() as session:
            return session.query(TradeCalendar).filter_by(**filters).all()

    def get_all(self) -> list[TradeCalendar]:
        with self.session_scope() as session:
            return session.query(TradeCalendar).all()

    def get_trading_days(self, exchange: str, start_date, end_date) -> list[TradeCalendar]:
        """获取指定交易所和日期范围的交易日"""
        with self.session_scope() as session:
            return session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date >= start_date,
                TradeCalendar.cal_date <= end_date,
                TradeCalendar.is_open == True
            ).order_by(TradeCalendar.cal_date).all()

    def is_trading_day(self, exchange: str, date) -> bool:
        """判断指定日期是否为交易日"""
        with self.session_scope() as session:
            day = session.query(TradeCalendar).get((exchange, date))
            return day.is_open if day else False

    def get_next_trading_day(self, exchange: str, date):
        """获取指定日期后的下一个交易日"""
        with self.session_scope() as session:
            return session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date > date,
                TradeCalendar.is_open == True
            ).order_by(TradeCalendar.cal_date).first()

    def get_previous_trading_day(self, exchange: str, date):
        """获取指定日期前的上一个交易日"""
        with self.session_scope() as session:
            return session.query(TradeCalendar).filter(
                TradeCalendar.exchange == exchange,
                TradeCalendar.cal_date < date,
                TradeCalendar.is_open == True
            ).order_by(TradeCalendar.cal_date.desc()).first()

    def batch_create(self, data_list: list[dict]) -> list[TradeCalendar]:
        """批量创建交易日历记录"""
        with self.session_scope() as session:
            instances = []
            for data in data_list:
                # 检查是否已存在相同主键的记录
                existing = session.query(TradeCalendar).get((data['exchange'], data['cal_date']))
                if existing:
                    # 如果存在，更新记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    instances.append(existing)
                else:
                    # 如果不存在，创建新记录
                    instance = TradeCalendar(**data)
                    session.add(instance)
                    instances.append(instance)
            session.flush()
            return instances