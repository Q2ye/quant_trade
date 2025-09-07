# stock_daily_service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import desc
from quant_server.data_services.base_service import BaseService
from quant_server.db.models.models import StockDaily


class StockDailyService(BaseService):
    """股票日线行情服务"""

    def create(self, data: Dict[str, Any]) -> StockDaily:
        """创建新日线记录"""
        with self.session_scope() as session:
            # 检查是否已存在
            existing = session.query(StockDaily).filter_by(
                ts_code=data['ts_code'],
                trade_date=data['trade_date']
            ).first()

            if existing:
                # 更新现有记录
                for key, value in data.items():
                    setattr(existing, key, value)
                return existing

            # 创建新记录
            daily = StockDaily(**data)
            session.add(daily)
            session.flush()
            return daily

    def batch_create(self, data_list: List[Dict[str, Any]]) -> List[StockDaily]:
        """批量创建日线记录"""
        results = []
        with self.session_scope() as session:
            for data in data_list:
                # 检查是否已存在
                existing = session.query(StockDaily).filter_by(
                    ts_code=data['ts_code'],
                    trade_date=data['trade_date']
                ).first()

                if existing:
                    # 更新现有记录
                    for key, value in data.items():
                        setattr(existing, key, value)
                    results.append(existing)
                else:
                    # 创建新记录
                    daily = StockDaily(**data)
                    session.add(daily)
                    results.append(daily)
            session.flush()
        return results

    def get(self, stock_daily_id: int) -> Optional[StockDaily]:
        """根据ID获取日线记录"""
        with self.session_scope() as session:
            return session.query(StockDaily).get(stock_daily_id)

    def update(self, stock_daily_id: int, update_data: Dict[str, Any]) -> Optional[StockDaily]:
        """更新日线记录"""
        with self.session_scope() as session:
            daily = session.query(StockDaily).get(stock_daily_id)
            if daily:
                for key, value in update_data.items():
                    setattr(daily, key, value)
                return daily
            return None

    def delete(self, stock_daily_id: int) -> bool:
        """删除日线记录"""
        with self.session_scope() as session:
            daily = session.query(StockDaily).get(stock_daily_id)
            if daily:
                session.delete(daily)
                return True
            return False

    def filter(self, **filters) -> List[StockDaily]:
        """根据条件过滤日线记录"""
        with self.session_scope() as session:
            query = session.query(StockDaily)
            for key, value in filters.items():
                query = query.filter(getattr(StockDaily, key) == value)
            return query.all()

    def get_all(self) -> List[StockDaily]:
        """获取所有日线记录"""
        with self.session_scope() as session:
            return session.query(StockDaily).all()

    def get_by_date_range(self, ts_code: str, start_date: datetime, end_date: datetime) -> List[StockDaily]:
        """获取指定日期范围内的行情数据"""
        with self.session_scope() as session:
            return session.query(StockDaily).filter(
                StockDaily.ts_code == ts_code,
                StockDaily.trade_date >= start_date,
                StockDaily.trade_date <= end_date
            ).order_by(StockDaily.trade_date).all()

    def get_latest_by_ts_code(self, ts_code: str) -> Optional[StockDaily]:
        """获取指定股票的最新行情"""
        with self.session_scope() as session:
            return session.query(StockDaily).filter(
                StockDaily.ts_code == ts_code
            ).order_by(desc(StockDaily.trade_date)).first()

    def get_by_code_and_date(self, ts_code: str, trade_date: datetime) -> Optional[StockDaily]:
        """根据股票代码和日期获取日线记录"""
        with self.session_scope() as session:
            return session.query(StockDaily).filter_by(
                ts_code=ts_code,
                trade_date=trade_date
            ).first()

    def get_price_history(self, ts_code: str, start_date: datetime, end_date: datetime) -> List[StockDaily]:
        """获取指定时间范围内的价格历史"""
        return self.get_by_date_range(ts_code, start_date, end_date)

    def get_last_trading_day_data(self, ts_code: str) -> Optional[StockDaily]:
        """获取最近交易日的行情数据"""
        return self.get_latest_by_ts_code(ts_code)

    def get_price_change_stats(self, ts_code: str, days: int = 30) -> Dict[str, Any]:
        """获取价格变动统计"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        with self.session_scope() as session:
            data = session.query(StockDaily).filter(
                StockDaily.ts_code == ts_code,
                StockDaily.trade_date >= start_date,
                StockDaily.trade_date <= end_date
            ).order_by(StockDaily.trade_date).all()

            if not data:
                return {}

            prices = [d.close for d in data]
            max_price = max(prices)
            min_price = min(prices)
            current_price = prices[-1]

            return {
                'start_price': prices[0],
                'end_price': current_price,
                'max_price': max_price,
                'min_price': min_price,
                'price_change': current_price - prices[0],
                'price_change_pct': (current_price - prices[0]) / prices[0] * 100 if prices[0] else 0,
                'volatility': (max_price - min_price) / prices[0] * 100 if prices[0] else 0
            }

    def get_volume_stats(self, ts_code: str, days: int = 30) -> Dict[str, Any]:
        """获取成交量统计"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        with self.session_scope() as session:
            data = session.query(StockDaily).filter(
                StockDaily.ts_code == ts_code,
                StockDaily.trade_date >= start_date,
                StockDaily.trade_date <= end_date
            ).order_by(StockDaily.trade_date).all()

            if not data:
                return {}

            volumes = [d.vol for d in data]
            avg_volume = sum(volumes) / len(volumes)
            max_volume = max(volumes)
            min_volume = min(volumes)

            return {
                'avg_volume': avg_volume,
                'max_volume': max_volume,
                'min_volume': min_volume,
                'volume_ratio': volumes[-1] / avg_volume if avg_volume else 0
            }

    def get_top_gainers(self, trade_date: datetime, limit: int = 10) -> List[StockDaily]:
        """获取当日涨幅最大的股票"""
        with self.session_scope() as session:
            return session.query(StockDaily).filter(
                StockDaily.trade_date == trade_date
            ).order_by(desc(StockDaily.pct_chg)).limit(limit).all()

    def get_top_losers(self, trade_date: datetime, limit: int = 10) -> List[StockDaily]:
        """获取当日跌幅最大的股票"""
        with self.session_scope() as session:
            return session.query(StockDaily).filter(
                StockDaily.trade_date == trade_date
            ).order_by(StockDaily.pct_chg).limit(limit).all()

    def get_highest_volume(self, trade_date: datetime, limit: int = 10) -> List[StockDaily]:
        """获取当日成交量最大的股票"""
        with self.session_scope() as session:
            return session.query(StockDaily).filter(
                StockDaily.trade_date == trade_date
            ).order_by(desc(StockDaily.vol)).limit(limit).all()

    def get_price_moving_average(self, ts_code: str, window: int = 20) -> List[Dict[str, Any]]:
        """计算移动平均线"""
        with self.session_scope() as session:
            # 获取最近的数据
            data = session.query(StockDaily).filter(
                StockDaily.ts_code == ts_code
            ).order_by(desc(StockDaily.trade_date)).limit(window * 2).all()

            if not data:
                return []

            # 按时间顺序排序
            data.sort(key=lambda x: x.trade_date)

            result = []
            prices = [d.close for d in data]

            for i in range(window, len(prices)):
                ma = sum(prices[i - window:i]) / window
                result.append({
                    'trade_date': data[i].trade_date,
                    'close': prices[i],
                    f'ma{window}': ma
                })

            return result

    def detect_price_breakout(self, ts_code: str, window: int = 20, threshold: float = 0.02) -> List[Dict[str, Any]]:
        """检测价格突破"""
        ma_data = self.get_price_moving_average(ts_code, window)

        breakouts = []
        for i in range(1, len(ma_data)):
            prev_close = ma_data[i - 1]['close']
            prev_ma = ma_data[i - 1][f'ma{window}']
            curr_close = ma_data[i]['close']
            curr_ma = ma_data[i][f'ma{window}']

            # 检测向上突破
            if prev_close <= prev_ma and curr_close > curr_ma * (1 + threshold):
                breakouts.append({
                    'trade_date': ma_data[i]['trade_date'],
                    'type': 'up',
                    'close': curr_close,
                    'ma': curr_ma
                })

            # 检测向下突破
            elif prev_close >= prev_ma and curr_close < curr_ma * (1 - threshold):
                breakouts.append({
                    'trade_date': ma_data[i]['trade_date'],
                    'type': 'down',
                    'close': curr_close,
                    'ma': curr_ma
                })

        return breakouts