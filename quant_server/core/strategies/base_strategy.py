import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import pandas as pd

from quant_server.core.engines import Event
from quant_server.modules.data import MarketDataService
from quant_server.modules.data_models import BarData

logger = logging.getLogger(__name__)


class BaseStrategy:
	"""策略基类（统一接口版，基于数据服务）"""

	def __init__ (self, config: Dict[str, Any], main_engine=None):
		"""
		初始化策略

		参数:
			config: 策略配置字典，包含以下关键字段:
				- name: 策略名称
				- symbols: 策略关注的股票代码列表
				- params: 策略参数字典
				- engineManager: 策略所属引擎类型 (cta, alpha, events)
		"""
		self.name = config['name']
		self.symbols = config.get('symbols', [])
		self.params = config.get('params', {})
		self.engine_type = config.get('engineManager', 'base')
		self.engine = None  # 策略引擎引用
		self.is_running = False  # 策略运行状态
		self.main_engine = main_engine
		self.historical_data = {}  # 历史数据存储
		self.data_service = None  # 数据服务
		self._init_data_service()
		logger.info(f"策略初始化: {self.name} ({self.engine_type}引擎)")

	def _init_data_service (self):
		"""根据主引擎初始化数据服务"""
		if self.main_engine and hasattr(self.main_engine, 'db'):
			try:
				session = self.main_engine.db.get_session()
				self.data_service = MarketDataService(session=session)
				logger.debug(f"数据服务已初始化(数据库会话)")
			except AttributeError:
				self.data_service = MarketDataService()
				logger.warning("主引擎数据库无get_session方法")
		else:
			self.data_service = MarketDataService()
			logger.warning("数据服务独立初始化(无主引擎)")

	def set_engine (self, engine):
		"""设置策略专用引擎"""
		self.engine = engine
		if engine:
			logger.info(f"策略 {self.name} 绑定 {type(engine).__name__} 引擎")
		else:
			logger.warning(f"策略 {self.name} 引擎绑定为空")

	def on_start (self):
		"""策略启动时调用"""
		self.is_running = True
		logger.info(f"策略 {self.name} 已启动")

	def on_stop (self):
		"""策略停止时调用"""
		self.is_running = False
		logger.info(f"策略 {self.name} 已停止")

	def preload_data (self, symbols: Optional[List[str]] = None, days: int = 60):
		"""
		预加载所需历史数据（核心方法）

		参数:
			symbols: 要预加载的股票代码列表，默认为策略配置的symbols
			days: 要加载的历史天数
		"""
		symbols = symbols or self.symbols
		if not symbols:
			logger.warning(f"策略 {self.name} 未配置symbols，跳过数据预加载")
			return

		logger.info(f"策略 {self.name} 开始预加载 {len(symbols)} 只股票的 {days} 天历史数据")

		# 计算日期范围
		end_date = datetime.now()
		start_date = end_date - timedelta(days=days)

		# 为每个symbol加载历史数据
		self.historical_data = {}
		for symbol in symbols:
			try:
				# 使用数据服务加载历史K线
				df = self.data_service.load_historical_bars(
					symbol=symbol,
					start=start_date,
					end=end_date
				)

				if not df.empty:
					self.historical_data[symbol] = df
					logger.debug(f"已加载 {symbol} 数据: {len(df)} 条")
				else:
					logger.warning(f"未找到 {symbol} 的历史数据")
			except Exception as e:
				logger.error(f"加载 {symbol} 数据失败: {str(e)}")

		logger.info(f"策略 {self.name} 历史数据预加载完成")

	def get_historical_data (self, symbol: str, days: int = 30) -> pd.DataFrame:
		"""
		获取指定股票的历史数据
		优先使用已加载的数据，若不存在则从数据库加载
		"""
		# 检查是否已加载
		if symbol in self.historical_data:
			df = self.historical_data[symbol]
			if len(df) >= days:
				return df.tail(days)

		# 若未加载或数据不足，实时加载
		end_date = datetime.now()
		start_date = end_date - timedelta(days=days)

		try:
			df = self.data_service.load_historical_bars(
				symbol=symbol,
				start=start_date,
				end=end_date
			)
			return df
		except Exception as e:
			logger.error(f"获取 {symbol} 历史数据失败: {str(e)}")
			return pd.DataFrame()

	def get_fundamental_data (self, symbol: str, date: datetime = None):
		"""获取基本面数据"""
		# 添加 session 参数处理
		return self.data_service.get_fundamental(symbol, date)

	def get_financial_data (self, symbol: str, date: datetime = None):
		"""获取财务数据"""
		# 添加 session 参数处理
		return self.data_service.get_financial(symbol, date)

	# ================== 信号生成方法 ==================
	def generate_signals (self, daily_data: Optional[Dict[str, Dict[str, Any]]] = None,
	                      current_date: Optional[str] = None) -> List[Dict[str, Any]]:
		"""
		生成选股信号（核心方法）

		参数:
			daily_data: 回测时传入当日所有股票数据 {symbol: {open, high, low, close, volume}}
			current_date: 当前日期

		返回:
			信号列表，每个信号为字典格式:
			{
				'symbol': 股票代码,
				'signal_type': 'BUY'/'SELL',
				'price': 价格,
				'reason': 信号原因,
				'score': 信号分数(0-1)
			}
		"""
		if daily_data is not None and current_date is not None:
			# 回测模式
			return self._generate_signals_for_backtest(daily_data, current_date)
		else:
			# 实时模式
			return self._generate_signals_for_live()

	def _generate_signals_for_live (self) -> List[Dict[str, Any]]:
		"""实时生成信号（子类必须实现）"""
		raise NotImplementedError(f"策略 {self.name} 未实现实时信号生成方法")

	def _generate_signals_for_backtest (self, daily_data: Dict[str, Dict[str, Any]],
	                                    current_date: str) -> List[Dict[str, Any]]:
		"""回测生成信号（子类必须实现）"""
		raise NotImplementedError(f"策略 {self.name} 未实现回测信号生成方法")

	# ================== 信号处理方法 ==================
	def _create_signal (self, symbol: str, signal_type: str, reason: str,
	                    score: float, price: float) -> Dict[str, Any]:
		"""创建标准信号字典"""
		return {
			'symbol': symbol,
			'signal_type': signal_type,
			'price': price,
			'reason': reason,
			'score': score,
			'events': self.name,
			'timestamp': datetime.now().isoformat()
		}

	def send_signal (self, signal: Dict[str, Any]):
		"""发送信号到主引擎"""
		if self.main_engine:
			self.main_engine.process_signal(Event(
				event_id=f"signal_{datetime.now().isoformat()}",
				event_type="signal",
				source=self.name,
				data=signal
			))
			logger.info(f"策略 {self.name} 发送信号: {signal}")
		else:
			logger.warning(f"策略 {self.name} 无法发送信号，主引擎未设置")

	# ================== 回测相关方法 ==================
	def run_backtest (self, start_date: str, end_date: str,
	                  capital: float = 1000000) -> Dict[str, Any]:
		"""
		运行策略回测

		参数:
			start_date: 回测开始日期 (YYYY-MM-DD)
			end_date: 回测结束日期 (YYYY-MM-DD)
			capital: 初始资金

		返回:
			回测结果字典
		"""
		logger.info(f"策略 {self.name} 开始回测: {start_date} 至 {end_date}")

		# 如果策略引擎支持回测，优先使用
		if self.engine and hasattr(self.engine, 'run_backtest'):
			return self.engine.run_backtest(self.name, start_date, end_date, capital)

		# 否则使用内置的回测逻辑
		return self._run_internal_backtest(start_date, end_date, capital)

	def _run_internal_backtest (self, start_date: str, end_date: str,
	                            capital: float) -> Dict[str, Any]:
		"""内置回测逻辑（子类可重写）"""
		# 默认实现：简单打印回测信息
		logger.warning(f"策略 {self.name} 未实现回测逻辑")
		return {
			'status': 'not_implemented',
			'events': self.name,
			'start_date': start_date,
			'end_date': end_date,
			'capital': capital
		}

	def on_bars (self, bars: Dict[str, BarData]):
		"""
		处理多个标的的K线数据 (AlphaEngine 使用)
		默认实现：调用实时信号生成方法

		参数:
			bars: 股票代码到BarData对象的映射字典
		"""
		logger.debug(f"策略 {self.name} 接收 {len(bars)} 条K线数据")
		signals = self._generate_signals_for_live()
		for signal in signals:
			self.send_signal(signal)