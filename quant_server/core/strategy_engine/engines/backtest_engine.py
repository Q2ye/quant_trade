import pandas as pd
from typing import Dict, Any, List
import logging

from quantCore.engineManager.event_engine import EventEngine
from quantCore.backtester.analyzer import BacktestAnalyzer
from quantCore.backtester.reporter import ReportGenerator

from quantCore.database.db_connector import DbConnector
from quantCore.engineManager.strategy_engine import StrategyEngine
from quantCore.vnpyAdapters import CtaTemplate

logger = logging.getLogger(__name__)


class BacktestEngine(StrategyEngine):
    """统一回测引擎"""

    def get_strategies(self) -> List[CtaTemplate]:
        """获取引擎中的所有策略实例列表"""
        if self.strategy:
            return [self.strategy]
        return []

    @property
    def strategies(self) -> Dict[str, CtaTemplate]:
        return self.strategies


    def remove_strategy(self, strategy_name: str):
        pass

    def start_strategy(self, strategy_name: str):
        pass

    def stop_strategy(self, strategy_name: str):
        pass

    def __init__(self, main_engine: Any):
        self.main_engine = main_engine
        self.data_cache = {}
        self.strategy = None
        self.event_engine = EventEngine()

        # 初始化数据库连接器
        self.db = self._init_database_connector()

        # 注册事件处理
        self.event_engine.register("signal", self.process_signal)

        logger.info("回测引擎初始化完成")

    def _init_database_connector(self) -> DbConnector:
        """初始化数据库连接器"""
        # 检查主引擎是否已加载配置
        global database_config
        if hasattr(self.main_engine, 'config') and self.main_engine.config:
            database_config = self.main_engine.config.get('database', {})
        else:
            # 尝试从默认配置文件加载
            try:
                import yaml
                with open("config/main.yaml", 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    database_config = config.get('database', {})
            except Exception as e:
                logger.error(f"加载数据库配置失败: {str(e)}")
                database_config = {}

        # 初始化数据库连接器
        db = DbConnector(database_config)
        if not db.connect():
            logger.error("回测引擎数据库连接失败")
        return db

    def set_strategy(self, strategy: Any):
        """设置策略"""
        self.strategy = strategy
        self.strategy.event_engine = self.event_engine
        logger.info(f"策略设置: {strategy.name}")

    def add_strategy(self, strategy: Any) -> Any:
        """添加策略实例（回测引擎通常不直接添加策略）"""
        logger.warning("回测引擎不支持直接添加策略，请使用set_strategy方法")
        return strategy


    def load_data(self, symbols: list, start_date: str, end_date: str):
        """加载数据到缓存"""
        logger.info(f"开始加载历史数据: {len(symbols)}只股票 ({start_date} 至 {end_date})")

        self.start_date = start_date
        self.end_date = end_date

        # 确保数据库已连接
        if not self.db.is_connected():
            self.db.connect()

        for symbol in symbols:
            try:
                # 使用参数化查询防止SQL注入
                query = """
                        SELECT date, open, high, low, close, volume, turnover
                        FROM stock_bars
                        WHERE symbol = :symbol
                          AND date BETWEEN : \
                        start AND : \
                        end
                    ORDER BY date \
                        """
                params = {'symbol': symbol, 'start': start_date, 'end': end_date}
                df = self.db.execute_query(query, params)

                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    self.data_cache[symbol] = df
                    logger.debug(f"已加载 {symbol} 数据: {len(df)} 条")
                else:
                    logger.warning(f"未找到 {symbol} 的历史数据")
            except Exception as e:
                logger.error(f"加载 {symbol} 数据失败: {str(e)}", exc_info=True)

        logger.info("历史数据加载完成")

    def run_backtest(self, strategy_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测（统一接口）"""
        # 从配置获取参数
        symbols = config.get('symbols', [])
        start_date = config.get('start_date')
        end_date = config.get('end_date')
        initial_capital = config.get('initial_capital', 1000000)

        # 设置回测参数
        self.load_data(symbols, start_date, end_date)
        return self.execute_backtest(initial_capital)

    def execute_backtest(self, initial_capital: float = 1000000) -> Dict[str, Any]:
        """执行回测（内部方法）"""
        # 这里是从原 run_backtest 方法移动过来的代码
        # 生成交易日序列
        trading_days = self._generate_trading_days()
        logger.info(f"回测周期: {self.start_date} 至 {self.end_date}, 共 {len(trading_days)} 个交易日")

        # 初始化状态
        self.positions = {}
        self.cash = initial_capital
        self.equity_curve = []
        self.trade_history = []
        self.initial_capital = initial_capital

        # 按交易日推进
        for day in trading_days:
            self.current_date = day
            logger.debug(f"处理交易日: {day}")

            # 获取当日所有股票的行情数据
            daily_data = self._get_daily_data(day)

            if not daily_data:
                logger.debug(f"{day} 无数据，跳过")
                continue

            # 执行策略
            self.strategy.generate_signals(daily_data, day)

            # 记录当日净值
            self._record_daily_equity()

        # 生成结果
        results = self._generate_results()

        # 生成报告
        reporter = ReportGenerator(results)
        report_file = f"backtest_report_{self.strategy.name}_{self.start_date}_{self.end_date}.pdf"
        reporter.generate_pdf_report(report_file)
        logger.info(f"回测报告已生成: {report_file}")

        return results

    def process_signal(self, event):
        """处理信号事件"""
        signal = event.data
        symbol = signal['symbol']
        signal_type = signal['signal_type']
        price = signal.get('price', 0)  # 使用get防止KeyError

        if signal_type == 'BUY':
            self._buy_stock(symbol, price)
        elif signal_type == 'SELL':
            self._sell_stock(symbol, price)
        else:
            logger.warning(f"未知信号类型: {signal_type}")

    def _generate_trading_days(self):
        """生成交易日序列"""
        # 确保数据库已连接
        if not self.db.is_connected():
            self.db.connect()

        try:
            query = """
                    SELECT DISTINCT date
                    FROM stock_bars
                    WHERE date BETWEEN : \
                    start AND : \
                    end
                ORDER BY date \
                    """
            params = {'start': self.start_date, 'end': self.end_date}
            df = self.db.execute_query(query, params)

            if not df.empty:
                return pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d').tolist()
        except Exception as e:
            logger.error(f"获取交易日历失败: {str(e)}", exc_info=True)

        # 如果数据库查询失败，生成日期范围
        logger.warning("从数据库获取交易日历失败，使用连续日期替代")
        return pd.date_range(start=self.start_date, end=self.end_date, freq='B').strftime('%Y-%m-%d').tolist()

    def _get_daily_data(self, date: str) -> Dict[str, pd.Series]:
        """获取指定日期的所有股票数据"""
        daily_data = {}
        for symbol, df in self.data_cache.items():
            if date in df.index:
                daily_data[symbol] = df.loc[date]
        return daily_data

    def _record_daily_equity(self):
        """记录每日净值"""
        portfolio_value = self.cash

        # 计算持仓价值
        for symbol, pos in self.positions.items():
            if symbol in self.data_cache and self.current_date in self.data_cache[symbol].index:
                close_price = self.data_cache[symbol].loc[self.current_date]['close']
                portfolio_value += pos['quantity'] * close_price

        self.equity_curve.append({
            'date': self.current_date,
            'equity': portfolio_value,
            'cash': self.cash,
            'positions': self.positions.copy()  # 保存持仓快照
        })

    def _buy_stock(self, symbol: str, price: float):
        """买入股票"""
        # 检查价格有效性
        if price <= 0:
            logger.warning(f"无效的买入价格: {price}, 跳过买入 {symbol}")
            return

        # 计算可买数量（使用全部可用资金）
        max_shares = int(self.cash / price)
        if max_shares <= 0:
            logger.debug(f"资金不足，无法买入 {symbol}")
            return

        # 计算交易金额
        cost = max_shares * price

        # 更新现金
        self.cash -= cost

        # 更新持仓
        if symbol in self.positions:
            # 已有持仓，增加
            old_qty = self.positions[symbol]['quantity']
            old_cost = self.positions[symbol]['cost_basis'] * old_qty
            new_qty = old_qty + max_shares
            new_cost_basis = (old_cost + cost) / new_qty

            self.positions[symbol] = {
                'quantity': new_qty,
                'cost_basis': new_cost_basis
            }
        else:
            # 新建持仓
            self.positions[symbol] = {
                'quantity': max_shares,
                'cost_basis': price
            }

        # 记录交易
        self.trade_history.append({
            'date': self.current_date,
            'symbol': symbol,
            'action': 'BUY',
            'quantity': max_shares,
            'price': price,
            'commission': 0,  # 简化：不考虑交易费用
            'cash_after': self.cash
        })

        logger.debug(f"买入 {symbol}: {max_shares}股 @ {price}, 成本 {cost}, 剩余现金 {self.cash}")

    def _sell_stock(self, symbol: str, price: float):
        """卖出股票"""
        if symbol not in self.positions:
            logger.debug(f"尝试卖出未持有的股票: {symbol}")
            return

        # 检查价格有效性
        if price <= 0:
            logger.warning(f"无效的卖出价格: {price}, 跳过卖出 {symbol}")
            return

        position = self.positions[symbol]
        quantity = position['quantity']

        # 计算收益
        revenue = quantity * price

        # 更新现金
        self.cash += revenue

        # 移除持仓
        del self.positions[symbol]

        # 记录交易
        self.trade_history.append({
            'date': self.current_date,
            'symbol': symbol,
            'action': 'SELL',
            'quantity': quantity,
            'price': price,
            'commission': 0,  # 简化：不考虑交易费用
            'cash_after': self.cash
        })

        logger.debug(f"卖出 {symbol}: {quantity}股 @ {price}, 收益 {revenue}, 现金 {self.cash}")

    def _generate_results(self) -> Dict[str, Any]:
        """生成回测结果"""
        try:
            return BacktestAnalyzer.analyze(
                self.equity_curve,
                self.trade_history,
                self.initial_capital
            )
        except Exception as e:
            logger.error(f"生成回测结果失败: {str(e)}", exc_info=True)
            return {
                'error': str(e),
                'equity_curve': self.equity_curve,
                'trade_history': self.trade_history
            }


    # 添加缺失的接口方法
    def run_engine(self, interval: int = 300):
        """运行引擎主循环（回测引擎无需实时循环）"""
        logger.warning("回测引擎不支持实时运行模式")

    def stop_engine(self):
        """停止引擎"""
        logger.info("回测引擎已停止")

    def start_all_strategies(self):
        """启动所有策略（回测引擎不支持此操作）"""
        logger.warning("回测引擎不支持启动策略")

    def stop_all_strategies(self):
        """停止所有策略（回测引擎不支持此操作）"""
        logger.warning("回测引擎不支持停止策略")