from datetime import datetime
from typing import Dict, List, Any, Optional

from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.object import BarData

from quantCore.engineManager.strategy_engine import StrategyEngine
from quantCore.strategies.base_strategy import BaseStrategy
import pandas as pd
import logging
import time

logger = logging.getLogger(__name__)


class AlphaEngine(StrategyEngine):
    """AI策略引擎（统一接口版）"""

    def get_strategies(self) -> List[BaseStrategy]:
        """获取引擎中的所有策略实例列表"""
        return list(self._strategies.values())

    @property
    def strategies(self) -> Dict[str, BaseStrategy]:
        return self._strategies

    def __init__(self, main_engine: Any):
        self.main_engine = main_engine
        self._strategies: Dict[str, BaseStrategy] = {}
        self.data_fetcher = DataFetcher()
        self.is_running = False
        self.last_run_time = None

        logger.info("AI策略引擎初始化完成")

    def add_strategy(self, strategy: Any) -> Any:
        """添加策略实例"""
        strategy_name = strategy.name

        # 检查是否已存在同名策略
        if strategy_name in self._strategies:
            logger.warning(f"AI策略 {strategy_name} 已存在，将被替换")
            self.remove_strategy(strategy_name)

        # 设置策略参数
        if 'params' in strategy.config:
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
            strategy.on_stop()  # 先停止策略
            del self._strategies[strategy_name]
            logger.info(f"AI策略 {strategy_name} 移除成功")
        else:
            logger.warning(f"尝试移除不存在的AI策略: {strategy_name}")

    def start_strategy(self, strategy_name: str):
        """启动单个策略"""
        if strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            strategy.on_start()
            logger.info(f"AI策略已启动: {strategy_name}")
        else:
            logger.warning(f"尝试启动不存在的AI策略: {strategy_name}")

    def stop_strategy(self, strategy_name: str):
        """停止单个策略"""
        if strategy_name in self._strategies:
            strategy = self._strategies[strategy_name]
            strategy.on_stop()
            logger.info(f"AI策略已停止: {strategy_name}")
        else:
            logger.warning(f"尝试停止不存在的AI策略: {strategy_name}")

    def start_all_strategies(self):
        """启动所有策略"""
        logger.info("启动所有AI策略")
        for strategy_name in self._strategies:
            self.start_strategy(strategy_name)

    def stop_all_strategies(self):
        """停止所有策略"""
        logger.info("停止所有AI策略")
        for strategy_name in self._strategies:
            self.stop_strategy(strategy_name)

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
                if self._is_trading_time(current_time):
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
        else:
            logger.warning("AI策略引擎未在运行")

    def _preload_data(self, symbols: Optional[List[str]] = None):
        """预加载数据"""
        symbols = symbols or []

        # 收集所有策略需要的标的
        all_symbols = set(symbols)
        for strategy in self._strategies.values():
            all_symbols.update(strategy.symbols)

        if not all_symbols:
            logger.warning("没有指定股票代码，跳过数据预加载")
            return

        # 计算需要加载的数据窗口
        max_window = max(
            (s.params.get('window', 20) for s in self._strategies.values()),
            default=20
        )
        start_date = pd.Timestamp.now() - pd.DateOffset(days=max_window * 3)
        end_date = pd.Timestamp.now()

        logger.info(f"预加载数据，窗口大小: {max_window}天，共 {len(all_symbols)} 只股票")

        for symbol in all_symbols:
            try:
                df = self.data_fetcher.get_daily_data(
                    symbol,
                    start_date.strftime('%Y-%m-%d'),
                    end_date.strftime('%Y-%m-%d'),
                    adj='none'  # 不复权
                )
                # 转换为BarData对象
                bars = [self._df_to_bar(row, symbol) for _, row in df.iterrows()]

                # 分发给各个策略
                for strategy in self._strategies.values():
                    if symbol in strategy.symbols:
                        if not hasattr(strategy, 'history_data'):
                            strategy.history_data = {}
                        strategy.history_data[symbol] = bars

                logger.debug(f"已加载 {symbol} 历史数据: {len(bars)} 条")
            except Exception as e:
                logger.error(f"加载 {symbol} 数据失败: {str(e)}", exc_info=True)

        logger.info(f"数据预加载完成，共 {len(all_symbols)} 只股票")

    @staticmethod
    def _df_to_bar(row, symbol) -> BarData:
        """将DataFrame行转换为BarData对象"""
        return BarData(
            symbol=symbol,
            exchange=Exchange.SSE,
            datetime=row.name.to_pydatetime(),
            interval=Interval.DAILY,
            open_price=row['open'],
            high_price=row['high'],
            low_price=row['low'],
            close_price=row['close'],
            volume=row['volume'],
            turnover=row.get('turnover', 0),
            gateway_name="DB"
        )

    def _is_trading_time(self, current_time: datetime) -> bool:
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

    def _fetch_realtime_data(self) -> Dict[str, BarData]:
        """获取实时数据"""
        realtime_bars = {}
        all_symbols = set()

        # 收集所有策略需要的标的
        for strategy in self._strategies.values():
            all_symbols.update(strategy.symbols)

        if not all_symbols:
            logger.debug("没有需要关注的股票，跳过实时数据获取")
            return realtime_bars

        logger.debug(f"获取实时数据，共 {len(all_symbols)} 只股票")

        for symbol in all_symbols:
            try:
                # 获取最新的分钟K线
                latest_bar = self.data_fetcher.get_latest_bar(symbol, interval='1min')

                if latest_bar is None:
                    continue

                # 转换为BarData对象
                bar = BarData(
                    symbol=symbol,
                    exchange=Exchange.SSE,
                    datetime=latest_bar['datetime'],
                    interval=Interval.MINUTE,
                    open_price=latest_bar['open'],
                    high_price=latest_bar['high'],
                    low_price=latest_bar['low'],
                    close_price=latest_bar['close'],
                    volume=latest_bar['volume'],
                    turnover=latest_bar.get('turnover', 0),
                    gateway_name="RT"
                )
                realtime_bars[symbol] = bar

            except Exception as e:
                logger.error(f"获取{symbol}实时数据失败: {str(e)}", exc_info=True)

        logger.debug(f"获取到{len(realtime_bars)}个标的的实时数据")
        return realtime_bars

    def _process_data(self, data: Dict[str, BarData]):
        """处理实时数据"""
        for strategy in self._strategies.values():
            if not strategy.is_running:
                continue

            # 只处理该策略关注的标的
            strategy_symbols = set(strategy.symbols)
            strategy_data = {sym: bar for sym, bar in data.items() if sym in strategy_symbols}

            if strategy_data:
                try:
                    # 直接传递BarData对象，不需要转换为字典
                    strategy.on_bars(strategy_data)
                except Exception as e:
                    logger.error(f"策略 {strategy.name} 处理数据失败: {str(e)}", exc_info=True)

    def run_backtest(self, strategy_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测（委托给主引擎的回测引擎）"""
        if strategy_name not in self._strategies:
            logger.error(f"策略不存在: {strategy_name}")
            return {}

        # 通过主引擎获取回测引擎
        backtest_engine = self.main_engine.get_engine('backtest')
        if backtest_engine is None:
            logger.error("回测引擎未加载")
            return {}

        # 准备回测配置
        backtest_config = {
            'strategy': {
                'name': strategy_name,
                'class': f"{self._strategies[strategy_name].__class__.__module__}.{self._strategies[strategy_name].__class__.__name__}"
            },
            'start_date': config.get('start_date'),
            'end_date': config.get('end_date'),
            'initial_capital': config.get('initial_capital', 1000000),
            'symbols': self._strategies[strategy_name].symbols
        }

        # 调用回测引擎
        return backtest_engine.run_backtest(strategy_name, backtest_config)
