# core/engines/cta_engine.py
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from quant_server.modules.data_models import TickData, BarData, OrderData, TradeData, OrderType, Direction, Exchange, \
    OrderStatus, Interval
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


def write_log(msg: str, strategy: CtaTemplate = None):
    """记录日志"""
    if strategy:
        logger.info(f"[{strategy.strategy_name}] {msg}")
    else:
        logger.info(msg)


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

        try:
            # 1. 检查订单是否存在且可取消
            # 在实际实现中，这里需要查询订单状态
            # 简化实现：假设订单存在且处于可取消状态

            # 2. 调用券商API取消订单
            # 这里使用伪代码表示实际调用过程
            # success = broker_api.cancel_order(orderid)

            # 模拟取消成功
            success = True

            if success:
                # 3. 更新订单状态为"已撤销"
                order = OrderData(
                    symbol=strategy.vt_symbol.split('.')[0],
                    exchange=Exchange(strategy.vt_symbol.split('.')[1]) if '.' in strategy.vt_symbol else Exchange.SSE,
                    orderid=orderid,
                    direction=Direction.NONE,  # 取消订单不需要方向
                    order_type=OrderType.LIMIT,
                    price=0,
                    volume=0,
                    status=OrderStatus.CANCELLED,  # 更新状态为已撤销
                    datetime=datetime.now()
                )

                # 4. 发布订单更新事件
                self.event_engine.put(Event("order", order))
                logger.info(f"订单取消成功: {orderid}")

                # 5. 通知策略订单已被取消
                strategy.on_order(order)
            else:
                logger.error(f"取消订单失败: {orderid}")
                # 可以在这里添加重试逻辑或错误处理

        except Exception as e:
            logger.error(f"取消订单时发生异常: {str(e)}")
            # 异常处理，记录详细错误信息

    def load_bar(self, vt_symbol: str, days: int, interval: str):
        """加载历史数据"""
        symbol, exchange_str = vt_symbol.split('.') if '.' in vt_symbol else (vt_symbol, 'SSE')
        logger.info(f"加载历史数据: {vt_symbol}, {days}天, {interval}周期")

        # 使用DataService获取数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        try:
            # 获取日线数据
            df = self.data_service.stock_daily.get_df_by_symbol_date_range(
                symbol, start_date, end_date
            )

            if df is None or df.empty:
                logger.warning(f"未找到 {vt_symbol} 的历史数据")
                return []

            # 转换为BarData列表
            bars = []
            for _, row in df.iterrows():
                bar = BarData(
                    symbol=symbol,
                    exchange=Exchange[exchange_str.upper()],
                    datetime=row['trade_date'],
                    interval=Interval.DAILY,
                    open_price=row['open'],
                    high_price=row['high'],
                    low_price=row['low'],
                    close_price=row['close'],
                    volume=row['volume'],
                    turnover=row.get('amount', 0)
                )
                bars.append(bar)

            logger.info(f"已加载 {vt_symbol} 数据: {len(bars)} 条")
            return bars

        except Exception as e:
            logger.error(f"加载 {vt_symbol} 数据失败: {str(e)}")
            return []

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

    def process_signal(self, event: Event):
        """处理信号事件"""
        signal = event.data
        logger.info(f"处理信号: {signal.signal_type} {signal.ts_code} @ {signal.price}")

        # 根据信号类型执行相应操作
        if signal.signal_type == 'buy':
            # 执行买入操作
            for strategy in self._strategies.values():
                if hasattr(strategy, 'vt_symbol') and strategy.vt_symbol.split('.')[0] == signal.ts_code:
                    # 这里可以调用策略的buy方法或直接发送订单
                    self.send_order(
                        strategy,
                        Direction.BUY,
                        signal.price,
                        100  # 默认数量，实际应根据信号强度或策略参数计算
                    )
        elif signal.signal_type == 'sell':
            # 执行卖出操作
            for strategy in self._strategies.values():
                if hasattr(strategy, 'vt_symbol') and strategy.vt_symbol.split('.')[0] == signal.ts_code:
                    self.send_order(
                        strategy,
                        Direction.SELL,
                        signal.price,
                        100  # 默认数量
                    )