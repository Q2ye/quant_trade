# core/engines/cta_engine.py
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from quant_server.core.data_models import TickData, BarData, OrderData, TradeData, OrderType, Direction, Exchange, \
    OrderStatus
from quant_server.core.strategy_engine.event_engine import EventEngine, Event
from quant_server.core.strategy_engine.strategy_engine import StrategyEngine
from quant_server.db import get_db_session
from quant_server.db.data_service import DataService

logger = logging.getLogger(__name__)


class CtaTemplate:
    """CTA策略模板，策略开发者继承此类并实现逻辑"""

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting=None):
        self.cta_engine = cta_engine
        self.strategy_name = strategy_name
        self.vt_symbol = vt_symbol  # 格式: symbol.exchange (e.g., 000001.SZSE)
        self.setting = setting or {}

    def on_init(self):
        """策略初始化时调用"""
        pass

    def on_start(self):
        """策略启动时调用"""
        pass

    def on_stop(self):
        """策略停止时调用"""
        pass

    def on_tick(self, tick: TickData):
        """收到Tick数据时调用"""
        pass

    def on_bar(self, bar: BarData):
        """收到K线数据时调用"""
        pass

    def on_order(self, order: OrderData):
        """收到订单回报时调用"""
        pass

    def on_trade(self, trade: TradeData):
        """收到成交回报时调用"""
        pass

    def buy(self, price: float, volume: float, order_type: OrderType = OrderType.LIMIT):
        """发送买入订单"""
        return self.cta_engine.send_order(self, Direction.BUY, price, volume, order_type)

    def sell(self, price: float, volume: float, order_type: OrderType = OrderType.LIMIT):
        """发送卖出订单"""
        return self.cta_engine.send_order(self, Direction.SELL, price, volume, order_type)

    def cancel_order(self, orderid: str):
        """撤销订单"""
        self.cta_engine.cancel_order(self, orderid)

    def write_log(self, msg: str):
        """记录日志"""
        self.cta_engine.write_log(msg, self)


class CtaEngine(StrategyEngine):
    """CTA策略引擎（统一接口版）"""

    def __init__(self, main_engine, event_engine: EventEngine):
        super().__init__(main_engine, event_engine)
        session = get_db_session()
        self.data_service = DataService(session)
        # 注册事件处理
        event_engine.register("tick", self.process_tick_event)
        event_engine.register("bar", self.process_bar_event)
        event_engine.register("order", self.process_order_event)
        event_engine.register("trade", self.process_trade_event)

        logger.info("CTA引擎初始化完成")

    def add_strategy(self, strategy: Any) -> Any:
        strategy_name = strategy.name
        if strategy_name in self._strategies:
            logger.warning(f"策略 {strategy_name} 已存在，将被替换")
            self.remove_strategy(strategy_name)

        # 确保策略是CtaTemplate类型
        if not isinstance(strategy, CtaTemplate):
            # 如果传入的是配置字典，尝试创建策略实例
            if isinstance(strategy, dict):
                strategy = self._create_strategy_from_config(strategy)
            else:
                logger.error(f"策略 {strategy_name} 必须是CtaTemplate类型或其配置字典")
                return None

        self._strategies[strategy_name] = strategy
        logger.info(f"CTA策略添加成功: {strategy_name}")
        return strategy

    def _create_strategy_from_config(self, config: Dict) -> CtaTemplate:
        """根据配置字典创建策略实例"""
        # 这里需要根据config中的类路径动态导入并实例化策略
        # 简化实现：返回一个基础实例
        strategy_name = config.get('name', 'UnknownStrategy')
        vt_symbol = config.get('vt_symbol', '')
        return CtaTemplate(self, strategy_name, vt_symbol, config)

    def remove_strategy(self, strategy_name: str):
        if strategy_name in self._strategies:
            self.stop_strategy(strategy_name)
            del self._strategies[strategy_name]
            logger.info(f"策略移除成功: {strategy_name}")
        else:
            logger.warning(f"尝试移除不存在的策略: {strategy_name}")

    def start_strategy(self, strategy_name: str, engine_type: str = None):
        if strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            strategy.on_start()
            logger.info(f"策略已启动: {strategy_name}")
        else:
            logger.warning(f"尝试启动不存在的策略: {strategy_name}")

    def stop_strategy(self, strategy_name: str):
        if strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            strategy.on_stop()
            logger.info(f"策略已停止: {strategy_name}")
        else:
            logger.warning(f"尝试停止不存在的策略: {strategy_name}")

    def run_engine(self, interval: int = 300):
        logger.info("CTA引擎已启动（事件驱动模式）")

    def stop_engine(self):
        logger.info("停止CTA引擎")
        self.stop_all_strategies()

    def stop_all_strategies(self):
        logger.info("停止所有CTA策略")
        for strategy_name in list(self._strategies.keys()):
            self.stop_strategy(strategy_name)

    def get_strategies(self) -> List[Any]:
        return list(self._strategies.values())

    def send_order(self, strategy: CtaTemplate, direction: Direction, price: float,
                   volume: float, order_type: OrderType = OrderType.LIMIT) -> str:
        """发送订单（模拟或对接实盘接口）"""
        # 生成订单ID
        order_id = f"ORDER_{strategy.strategy_name}_{datetime.now().timestamp()}"

        order = OrderData(
            symbol=strategy.vt_symbol.split('.')[0],  # 从vt_symbol中提取symbol
            exchange=Exchange(strategy.vt_symbol.split('.')[1]) if '.' in strategy.vt_symbol else Exchange.SSE,
            orderid=order_id,
            direction=direction,
            order_type=order_type,
            price=price,
            volume=volume,
            status=OrderStatus.SUBMITTING,
            datetime=datetime.now()
        )

        # 发布订单事件
        self.event_engine.put(Event("order", order))
        logger.info(f"策略 {strategy.strategy_name} 发送订单: {direction.value} {volume}@{price}")
        return order_id

    def cancel_order(self, strategy: CtaTemplate, orderid: str):
        """取消订单"""
        logger.info(f"策略 {strategy.strategy_name} 取消订单: {orderid}")
        # 实际实现中这里要调用券商API

    def write_log(self, msg: str, strategy: CtaTemplate = None):
        """记录日志"""
        if strategy:
            logger.info(f"[{strategy.strategy_name}] {msg}")
        else:
            logger.info(msg)

    def load_bar(self, vt_symbol: str, days: int, interval: str):
        """加载历史数据"""
        symbol, exchange_str = vt_symbol.split('.') if '.' in vt_symbol else (vt_symbol, 'SSE')
        logger.info(f"加载历史数据: {vt_symbol}, {days}天, {interval}周期")

        # 使用DataService获取数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        # ... 调用data_service获取数据并转换 ...

    def process_tick_event(self, event: Event):
        tick = event.data
        for strategy in self._strategies.values():
            if hasattr(strategy, 'vt_symbol') and strategy.vt_symbol == tick.symbol:
                strategy.on_tick(tick)

    def process_bar_event(self, event: Event):
        bar = event.data
        for strategy in self._strategies.values():
            if hasattr(strategy, 'vt_symbol') and strategy.vt_symbol == bar.symbol:
                strategy.on_bar(bar)

    def process_order_event(self, event: Event):
        order = event.data
        for strategy in self._strategies.values():
            if hasattr(strategy, 'vt_symbol') and strategy.vt_symbol == order.symbol:
                strategy.on_order(order)

    def process_trade_event(self, event: Event):
        trade = event.data
        for strategy in self._strategies.values():
            if hasattr(strategy, 'vt_symbol') and strategy.vt_symbol == trade.symbol:
                strategy.on_trade(trade)

    def run_backtest(self, strategy_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测（委托给回测引擎）"""
        backtest_engine = self.main_engine.get_engine('backtest')
        if backtest_engine is None:
            logger.error("回测引擎未加载")
            return {}
        return backtest_engine.run_backtest(strategy_name, config)