# core/engines/alpha_engine.py
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import logging
import time

from quant_server.modules.data_models import BarData, Interval, Exchange
from quant_server.core.strategy_engine.event_engine import EventEngine, Event
from quant_server.core.strategy_engine.strategy_engine import StrategyEngine
from quant_server.db import get_db_session
from quant_server.db.data_service import DataService

logger = logging.getLogger(__name__)


def _is_trading_time(current_time: datetime) -> bool:
    """检查当前是否在交易时间内（简化版）"""
    # 周一至周五，上午9:30-11:30，下午13:00-15:00
    if current_time.weekday() >= 5:  # 周六日
        return False

    hour = current_time.hour
    minute = current_time.minute

    # 上午交易时段 (9:30-11:30)
    if (hour == 9 and minute >= 30) or (hour == 10) or (hour == 11 and minute < 30):
        return True

    # 下午交易时段 (13:00-15:00)
    if 13 <= hour < 15:
        return True

    return False


class AlphaEngine(StrategyEngine):
    """AI策略引擎（统一接口版）"""

    def __init__(self, main_engine, event_engine: EventEngine):
        # 调用父类初始化
        super().__init__(main_engine, event_engine)

        session = get_db_session()
        self.data_service = DataService(session)
        self.is_running = False
        self.last_run_time = None

        # 注册事件处理
        event_engine.register("tick", self.process_tick_event)
        event_engine.register("bar", self.process_bar_event)
        event_engine.register("order", self.process_order_event)
        event_engine.register("trade", self.process_trade_event)

        logger.info("AI策略引擎初始化完成")

    def add_strategy(self, strategy: Any) -> Any:
        """添加策略实例"""
        strategy_name = strategy.name

        # 检查是否已存在同名策略
        if strategy_name in self._strategies:
            logger.warning(f"AI策略 {strategy_name} 已存在，将被替换")
            self.remove_strategy(strategy_name)

        # 设置策略参数
        if hasattr(strategy, 'config') and 'params' in strategy.config:
            for key, value in strategy.config['params'].items():
                if hasattr(strategy, key):
                    setattr(strategy, key, value)

        self._strategies[strategy_name] = strategy
        logger.info(f"AI策略 {strategy_name} 添加成功")
        return strategy

    def remove_strategy(self, strategy_name: str):
        """移除策略"""
        if strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            if hasattr(strategy, 'on_stop'):
                strategy.on_stop()  # 先停止策略
            del self._strategies[strategy_name]
            logger.info(f"AI策略 {strategy_name} 移除成功")
        else:
            logger.warning(f"尝试移除不存在的AI策略: {strategy_name}")

    def start_strategy(self, strategy_name: str, engine_type: str = None):
        """启动单个策略"""
        if strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            if hasattr(strategy, 'on_start'):
                strategy.on_start()
            logger.info(f"AI策略已启动: {strategy_name}")
        else:
            logger.warning(f"尝试启动不存在的AI策略: {strategy_name}")

    def stop_strategy(self, strategy_name: str):
        """停止单个策略"""
        if strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            if hasattr(strategy, 'on_stop'):
                strategy.on_stop()
            logger.info(f"AI策略已停止: {strategy_name}")
        else:
            logger.warning(f"尝试停止不存在的AI策略: {strategy_name}")

    def run_engine(self, interval: int = 300):
        """运行AI策略引擎（实时模式）"""
        if self.is_running:
            logger.warning("AI策略引擎已在运行中，无需重复启动")
            return

        logger.info(f"启动AI策略引擎，执行间隔: {interval}秒")
        self.is_running = True

        # 预加载数据
        self._preload_data()

        try:
            while self.is_running:
                # 获取当前时间
                current_time = datetime.now()

                # 检查是否在交易时间
                if _is_trading_time(current_time):
                    # 获取实时数据
                    realtime_data = self._fetch_realtime_data()

                    if realtime_data:
                        # 处理实时数据
                        self._process_data(realtime_data)

                    # 更新最后运行时间
                    self.last_run_time = current_time

                # 等待下一次执行
                time.sleep(interval)

        except KeyboardInterrupt:
            logger.info("用户中断AI策略引擎运行")
        except Exception as e:
            logger.error(f"AI策略引擎运行异常: {str(e)}", exc_info=True)
        finally:
            self.is_running = False
            logger.info("AI策略引擎已停止")

    def stop_engine(self):
        """停止AI策略引擎"""
        if self.is_running:
            self.is_running = False
            logger.info("正在停止AI策略引擎...")

            # 停止所有策略
            for strategy_name in list(self._strategies.keys()):
                self.stop_strategy(strategy_name)
        else:
            logger.warning("AI策略引擎未在运行")

    def _preload_data(self, symbols: Optional[List[str]] = None):
        """预加载数据"""
        symbols = symbols or []

        # 收集所有策略需要的标的
        all_symbols = set(symbols)
        for strategy in self._strategies.values():
            if hasattr(strategy, 'symbols'):
                all_symbols.update(strategy.symbols)

        if not all_symbols:
            logger.warning("没有指定股票代码，跳过数据预加载")
            return

        # 计算需要加载的数据窗口
        max_window = 20  # 默认值
        for s in self._strategies.values():
            if hasattr(s, 'params') and 'window' in s.params:
                max_window = max(max_window, s.params.get('window', 20))

        start_date = pd.Timestamp.now() - pd.DateOffset(days=max_window * 3)
        end_date = pd.Timestamp.now()

        logger.info(f"预加载数据，窗口大小: {max_window}天，共 {len(all_symbols)} 只股票")

        for symbol in all_symbols:
            try:
                # 使用数据服务获取日线数据
                daily_data = self.data_service.stock_daily.get_by_symbol_date_range(
                    symbol, start_date, end_date
                )

                if not daily_data:
                    logger.warning(f"获取{symbol}数据失败或数据为空")
                    continue

                # 转换为BarData对象
                bars = []
                for data in daily_data:
                    bar = BarData(
                        symbol=symbol,
                        exchange=Exchange(data.exchange) if data.exchange else Exchange.SSE,
                        datetime=data.trade_date,
                        interval=Interval.DAILY,
                        open_price=data.open,
                        high_price=data.high,
                        low_price=data.low,
                        close_price=data.close,
                        volume=data.volume,
                        turnover=data.amount if hasattr(data, 'amount') else 0
                    )
                    bars.append(bar)

                # 分发给各个策略
                for strategy in self._strategies.values():
                    if hasattr(strategy, 'symbols') and symbol in strategy.symbols:
                        if not hasattr(strategy, 'history_data'):
                            strategy.history_data = {}
                        strategy.history_data[symbol] = bars

                logger.debug(f"已加载 {symbol} 历史数据: {len(bars)} 条")
            except Exception as e:
                logger.error(f"加载 {symbol} 数据失败: {str(e)}", exc_info=True)

        logger.info(f"数据预加载完成，共 {len(all_symbols)} 只股票")

    def _fetch_realtime_data(self) -> Dict[str, BarData]:
        """获取实时数据"""
        realtime_bars = {}
        all_symbols = set()

        # 收集所有策略需要的标的
        for strategy in self._strategies.values():
            if hasattr(strategy, 'symbols'):
                all_symbols.update(strategy.symbols)

        if not all_symbols:
            logger.debug("没有需要关注的股票，跳过实时数据获取")
            return realtime_bars

        logger.debug(f"获取实时数据，共 {len(all_symbols)} 只股票")

        # 这里简化实现，实际应该从行情API获取实时数据
        # 暂时返回空数据
        return realtime_bars

    def _process_data(self, data: Dict[str, BarData]):
        """处理实时数据"""
        for strategy in self._strategies.values():
            if hasattr(strategy, 'is_running') and not strategy.is_running:
                continue

            # 只处理该策略关注的标的
            strategy_symbols = set()
            if hasattr(strategy, 'symbols'):
                strategy_symbols = set(strategy.symbols)

            strategy_data = {sym: bar for sym, bar in data.items() if sym in strategy_symbols}

            if strategy_data:
                try:
                    # 直接传递BarData对象
                    if hasattr(strategy, 'on_bars'):
                        strategy.on_bars(strategy_data)
                except Exception as e:
                    logger.error(f"策略 {strategy.name} 处理数据失败: {str(e)}", exc_info=True)


    def process_tick_event(self, event: Event):
        """处理Tick事件"""
        tick = event.data
        for strategy in self._strategies.values():
            if hasattr(strategy, 'on_tick'):
                strategy.on_tick(tick)

    def process_bar_event(self, event: Event):
        """处理K线事件"""
        bar = event.data
        for strategy in self._strategies.values():
            if hasattr(strategy, 'on_bar'):
                strategy.on_bar(bar)

    def process_order_event(self, event: Event):
        """处理订单事件"""
        order = event.data
        for strategy in self._strategies.values():
            if hasattr(strategy, 'on_order'):
                strategy.on_order(order)

    def process_trade_event(self, event: Event):
        """处理成交事件"""
        trade = event.data
        for strategy in self._strategies.values():
            if hasattr(strategy, 'on_trade'):
                strategy.on_trade(trade)