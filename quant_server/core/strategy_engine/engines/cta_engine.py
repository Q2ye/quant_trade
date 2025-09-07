import logging
from datetime import datetime
from typing import Dict, Any, List

from quantCore.engineManager.event_engine import Event, EventEngine
from quantCore.engineManager.strategy_engine import StrategyEngine
from quantCore.vnpyAdapters import CtaTemplate, OrderData, Exchange, Status

logger = logging.getLogger(__name__)


class CtaEngine(StrategyEngine):
    """CTA策略引擎（统一接口版）"""

    def get_strategies(self) -> List[CtaTemplate]:
        """获取引擎中的所有策略实例列表"""
        return list(self._strategies.values())

    @property
    def strategies(self) -> Dict[str, CtaTemplate]:
        return self._strategies

    def __init__(self, main_engine: Any, event_engine: EventEngine):
        self.main_engine = main_engine
        self.event_engine = event_engine
        self._strategies: Dict[str, CtaTemplate] = {}

        # 注册事件处理
        event_engine.register("tick", self.process_tick_event)
        event_engine.register("bar", self.process_bar_event)
        event_engine.register("order", self.process_order_event)
        event_engine.register("trade", self.process_trade_event)

        logger.info("CTA引擎初始化完成")

    def add_strategy(self, strategy: Any) -> Any:
        """添加策略实例"""
        strategy_name = strategy.name

        # 检查是否已存在同名策略
        if strategy_name in self._strategies:
            logger.warning(f"策略 {strategy_name} 已存在，将被替换")
            self.remove_strategy(strategy_name)

        # 转换策略类型（如果需要）
        if not isinstance(strategy, CtaTemplate):
            strategy = self._convert_to_cta_strategy(strategy)

        # 设置策略参数
        if 'params' in strategy.config:
            strategy.set_parameters(strategy.config['params'])

        self._strategies[strategy_name] = strategy
        logger.info(f"CTA策略添加成功: {strategy_name}")
        return strategy

    def _convert_to_cta_strategy(self, base_strategy):
        """将基础策略转换为CTA策略"""
        class CtaAdapter(CtaTemplate):
            def __init__(self, cta_engine, name, vt_symbol, base_strategy):
                # 关键修复：传递 setting 参数（使用策略配置）
                super().__init__(
                    cta_engine=cta_engine,
                    strategy_name=name,
                    vt_symbol=vt_symbol,
                    setting=base_strategy.config  # 使用策略配置作为 setting
                )
                self.base_strategy = base_strategy

            def on_tick(self, tick):
                # 转换为统一数据格式
                data = {
                    'symbol': tick.symbol,
                    'price': tick.last_price,
                    'volume': tick.volume,
                    # ... 其他字段 ...
                }
                self.base_strategy.on_tick(data)

            def on_bar(self, bar):
                # 处理K线数据
                self.base_strategy.on_bar(bar)

            def on_order(self, order):
                # 处理订单事件
                self.base_strategy.on_order(order)

            def on_trade(self, trade):
                # 处理成交事件
                self.base_strategy.on_trade(trade)

        # 从配置获取vt_symbol
        vt_symbol = base_strategy.config.get('vt_symbol', '')
        if not vt_symbol:
            logger.error(f"CTA策略 {base_strategy.name} 缺少 vt_symbol 配置")
            return base_strategy

        return CtaAdapter(self, base_strategy.name, vt_symbol, base_strategy)

    def run_backtest(self, strategy_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测"""
        if strategy_name not in self._strategies:
            logger.error(f"策略不存在: {strategy_name}")
            return {}

        strategy = self._strategies[strategy_name]

        # 转换配置参数
        backtest_config = {
            'start_date': config.get('start_date'),
            'end_date': config.get('end_date'),
            'capital': config.get('initial_capital', 1000000),
            'symbols': [strategy.vt_symbol]
        }

        # 使用主引擎的回测功能
        return self.main_engine.init_backtest(backtest_config)

    def remove_strategy(self, strategy_name: str):
        """移除策略"""
        if strategy_name in self._strategies:
            self.stop_strategy(strategy_name)
            del self._strategies[strategy_name]
            logger.info(f"策略移除成功: {strategy_name}")
        else:
            logger.warning(f"尝试移除不存在的策略: {strategy_name}")

    def start_strategy(self, strategy_name: str):
        """启动单个策略"""
        if strategy_name in self._strategies:
            self._strategies[strategy_name].on_start()
            logger.info(f"策略已启动: {strategy_name}")
        else:
            logger.warning(f"尝试启动不存在的策略: {strategy_name}")

    def stop_strategy(self, strategy_name: str):
        """停止单个策略"""
        if strategy_name in self._strategies:
            self._strategies[strategy_name].on_stop()
            logger.info(f"策略已停止: {strategy_name}")
        else:
            logger.warning(f"尝试停止不存在的策略: {strategy_name}")

    def start_all_strategies(self):
        """启动所有策略"""
        logger.info("启动所有CTA策略")
        for strategy_name in self._strategies:
            self.start_strategy(strategy_name)

    def stop_all_strategies(self):
        """停止所有策略"""
        logger.info("停止所有CTA策略")
        for strategy_name in self._strategies:
            self.stop_strategy(strategy_name)

    def send_order(self, strategy: CtaTemplate, direction, price, volume, stop=False, lock=False) -> str:
        """发送订单（模拟实现）"""
        # 生成订单ID
        order_id = f"ORDER_{strategy.strategy_name}_{datetime.now().timestamp()}"

        # 创建订单对象
        order = OrderData(
            symbol=strategy.vt_symbol,
            exchange=Exchange.SSE,
            orderid=order_id,
            direction=direction,
            price=price,
            volume=volume,
            traded=0,
            status=Status.SUBMITTING,
            datetime=datetime.now()
        )

        # 发送订单事件
        self.event_engine.put(Event("order", order))

        logger.info(f"策略 {strategy.strategy_name} 发送订单: {direction} {volume}@{price}")
        return order_id

    def cancel_order(self, strategy: CtaTemplate, orderid: str):
        """取消订单"""
        # 在实际实现中，这里应该与经纪商API交互
        logger.info(f"策略 {strategy.strategy_name} 取消订单: {orderid}")

    def write_log(self, msg: str, strategy: CtaTemplate = None):
        """记录日志"""
        if strategy:
            logger.info(f"[{strategy.strategy_name}] {msg}")
        else:
            logger.info(msg)

    def put_strategy_event(self, strategy: CtaTemplate):
        """推送策略事件"""
        # 在实际实现中，这里应该更新策略状态
        logger.debug(f"更新策略状态: {strategy.strategy_name}")

    def load_bar(self, vt_symbol: str, days: int, interval: str):
        """加载历史数据"""
        # 在实际实现中，这里应该从数据库加载历史数据
        logger.info(f"加载历史数据: {vt_symbol}, {days}天, {interval}周期")

    def process_tick_event(self, event: Event):
        """处理Tick事件"""
        tick = event.data
        for strategy in self._strategies.values():
            if strategy.vt_symbol == tick.symbol:
                strategy.on_tick(tick)

    def process_bar_event(self, event: Event):
        """处理K线事件"""
        bar = event.data
        for strategy in self._strategies.values():
            if strategy.vt_symbol == bar.symbol:
                strategy.on_bar(bar)

    def process_order_event(self, event: Event):
        """处理订单事件"""
        order = event.data
        for strategy in self._strategies.values():
            if strategy.vt_symbol == order.symbol:
                strategy.on_order(order)

    def process_trade_event(self, event: Event):
        """处理成交事件"""
        trade = event.data
        for strategy in self._strategies.values():
            if strategy.vt_symbol == trade.symbol:
                strategy.on_trade(trade)

    def run_engine(self, interval: int = 300):
        """运行引擎主循环（CTA引擎由事件驱动，无需单独循环）"""
        logger.info("CTA引擎已启动（事件驱动模式）")

    def stop_engine(self):
        """停止引擎"""
        logger.info("停止CTA引擎")
        self.stop_all_strategies()
