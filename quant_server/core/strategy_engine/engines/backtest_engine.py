# core/engines/backtest_engine.py
import pandas as pd
from typing import Dict, Any, List
import logging

from quant_server.core.data_models import BarData, Exchange, Interval
from quant_server.core.strategy_engine.event_engine import EventEngine, Event
from quant_server.core.strategy_engine.strategy_engine import StrategyEngine
from quant_server.db import get_db_session
from quant_server.db.data_service import DataService

logger = logging.getLogger(__name__)


def process_signal(event: Event):
    """处理信号事件"""
    signal = event.data
    # ... 根据信号执行买卖操作 ...


class BacktestEngine(StrategyEngine):
    """统一回测引擎"""

    def __init__(self, main_engine, event_engine: EventEngine):
        super().__init__(main_engine, event_engine)

        self.strategy = None
        session = get_db_session()
        self.data_service = DataService(session)

        self.data_cache = {}  # 缓存历史数据 {symbol: List[BarData]}
        self.current_date = None
        self.current_strategy = None

        # 回测状态变量
        self.initial_capital = 1000000
        self.cash = self.initial_capital
        self.positions = {}  # {symbol: {'quantity': int, 'cost_basis': float}}
        self.equity_curve = []  # 记录每日净值
        self.trade_history = []  # 记录所有交易
        self.start_date = None
        self.end_date = None

        event_engine.register("signal", process_signal)
        logger.info("回测引擎初始化完成")

    def add_strategy(self, strategy: Any) -> Any:
        strategy_name = strategy.name
        if strategy_name in self._strategies:
            logger.warning(f"策略 {strategy_name} 已存在，将被替换")
            self.remove_strategy(strategy_name)
        self._strategies[strategy_name] = strategy
        self.current_strategy = strategy
        logger.info(f"策略设置: {strategy_name}")
        return strategy

    def remove_strategy(self, strategy_name: str):
        if strategy_name in self._strategies:
            if self.current_strategy and self.current_strategy.name == strategy_name:
                self.current_strategy = None
            del self._strategies[strategy_name]
            logger.info(f"策略移除成功: {strategy_name}")
        else:
            logger.warning(f"尝试移除不存在的策略: {strategy_name}")

    def start_strategy(self, strategy_name: str, engine_type: str = None):
        logger.warning("回测引擎不支持实时启动策略，请使用run_backtest方法")

    def stop_strategy(self, strategy_name: str):
        logger.warning("回测引擎不支持实时停止策略")


    def stop_engine(self):
        """停止引擎"""
        logger.info("回测引擎已停止")
        self.data_cache.clear()
        self.positions.clear()
        self.equity_curve.clear()
        self.trade_history.clear()

    def get_strategies(self) -> List[Any]:
        return list(self._strategies.values())

    @property
    def strategies(self) -> Dict[str, Any]:
        return self._strategies

    def set_strategy(self, strategy: Any):
        """设置当前要回测的策略"""
        self.strategy = strategy
        logger.info(f"策略设置: {strategy.name}")

    def load_data(self, symbols: list, start_date: str, end_date: str):
        """从DataService加载数据到缓存，并转换为List[BarData]"""
        logger.info(f"开始加载历史数据: {len(symbols)}只股票 ({start_date} 至 {end_date})")
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)

        for symbol in symbols:
            try:
                # 1. 使用DataService获取原始数据
                df = self.data_service.stock_daily.get_df_by_symbol_date_range(
                    symbol, self.start_date, self.end_date
                )
                if df is None or df.empty:
                    logger.warning(f"未找到 {symbol} 的历史数据")
                    continue

                # 2. 将DataFrame转换为List[BarData] (内存模型)
                bars = []
                for _, row in df.iterrows():
                    bar = BarData(
                        symbol=symbol,
                        exchange=Exchange.SSE,  # 简化处理，实际需从数据库获取
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

                self.data_cache[symbol] = bars
                logger.debug(f"已加载 {symbol} 数据: {len(bars)} 条")

            except Exception as e:
                logger.error(f"加载 {symbol} 数据失败: {str(e)}")

        logger.info("历史数据加载完成")

    def run_backtest(self, strategy_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测（统一接口）"""
        if strategy_name not in self._strategies:
            logger.error(f"策略不存在: {strategy_name}")
            return {}

        symbols = config.get('symbols', [])
        start_date = config.get('start_date')
        end_date = config.get('end_date')
        self.initial_capital = config.get('initial_capital', 1000000)
        self.cash = self.initial_capital

        # 1. 加载数据
        self.load_data(symbols, start_date, end_date)
        # 2. 设置策略
        self.strategy = self._strategies[strategy_name]
        # 3. 执行回测
        return self.execute_backtest()

    def execute_backtest(self) -> Dict[str, Any]:
        """执行回测核心逻辑"""
        if not self.strategy:
            logger.error("未设置策略，无法执行回测")
            return {}

        # 生成回测日期序列
        all_dates = sorted(set(bar.datetime for bars in self.data_cache.values() for bar in bars))
        logger.info(f"回测周期: {all_dates[0]} 至 {all_dates[-1]}, 共 {len(all_dates)} 个交易日")

        # 按日期循环
        for current_date in all_dates:
            self.current_date = current_date
            daily_bars = {}

            # 获取当日所有标的的BarData
            for symbol, bars in self.data_cache.items():
                for bar in bars:
                    if bar.datetime == current_date:
                        daily_bars[symbol] = bar
                        break

            if not daily_bars:
                continue

            # 调用策略的on_bars方法
            try:
                if hasattr(self.strategy, 'on_bars'):
                    self.strategy.on_bars(daily_bars)
            except Exception as e:
                logger.error(f"策略执行出错: {str(e)}")
                break

            # 记录当日净值
            self._record_daily_equity(daily_bars)

        # 生成回测结果
        results = self._generate_results()
        logger.info(f"回测完成，最终净值: {results.get('total_value', 0):.2f}")
        return results

    def _record_daily_equity(self, daily_bars: Dict[str, BarData]):
        """记录每日净值"""
        total_value = self.cash
        for symbol, position_info in self.positions.items():
            if symbol in daily_bars:
                bar = daily_bars[symbol]
                market_value = position_info['quantity'] * bar.close_price
                total_value += market_value

        self.equity_curve.append({
            'date': self.current_date,
            'equity': total_value,
            'cash': self.cash,
            'positions': self.positions.copy()
        })

    def _generate_results(self) -> Dict[str, Any]:
        """生成回测结果报告"""
        # 这里实现计算收益率、夏普比率、最大回撤等逻辑
        if not self.equity_curve:
            return {}

        initial_value = self.initial_capital
        final_value = self.equity_curve[-1]['equity']
        total_return = (final_value - initial_value) / initial_value

        return {
            'initial_capital': initial_value,
            'final_value': final_value,
            'total_return': total_return,
            'equity_curve': self.equity_curve,
            'trade_history': self.trade_history,
            # ... 其他指标 ...
        }