# tushare_source.py
"""
Tushare数据源实现

提供完整的A股、ETF、财务数据接口
文档: https://tushare.pro/document/2
"""
import logging
import os
from datetime import datetime
from typing import List, Dict

import pandas as pd
import tushare as ts

from .base_source import BaseDataSource

logger = logging.getLogger(__name__)


class TushareSource(BaseDataSource):
	"""Tushare数据源实现

	支持数据类型:
	- 股票: 基础列表、日线/周线/月线、分钟线、Tick、大单、复权因子、停复牌、每日指标
	- ETF: 基础信息、指数列表、实时/历史分钟、日线、复权因子、份额规模
	- 财务: 利润表、资产负债表、现金流量表、业绩预告、快报、分红、财务指标、审计意见、主营业务
	"""

	def __init__ (self, config: dict = None):
		super().__init__()
		config = config or {}
		token = config.get('token') or os.getenv('TUSHARE_TOKEN')
		if token:
			ts.set_token(token)
		self.pro = ts.pro_api()
		self._connected = True

	def __del__ (self):
		self._connected = False

	def connect (self) -> bool:
		"""建立连接"""
		self._connected = True
		return True

	def disconnect (self) -> None:
		"""断开连接"""
		self._connected = False

	# ==================== 股票基础数据 ====================

	def get_stock_basic (self, exchange: str = '', list_status: str = 'L') -> List[Dict]:
		"""获取股票基本信息（同步方法，由调用方丢线程池）

		Args:
			exchange: 交易所 (SSE/SZSE), 空表示全部
			list_status: L-上市, D-退市, P-暂停上市

		Returns:
			股票基本信息列表
		"""
		fields = ('ts_code,symbol,name,area,industry,market,exchange,'
		          'list_date,delist_date,is_hs')
		try:
			df = self.pro.stock_basic(exchange=exchange, list_status=list_status, fields=fields)
			return df.to_dict('records') if df is not None else []
		except Exception as e:
			logger.error(f"获取股票基本信息失败: {e}")
			return []

	def get_ashare_list (self) -> list:
		"""获取A股列表（排除ST/*ST）"""
		df = self.pro.stock_basic(exchange='', list_status='L',
		                          fields='ts_code,name')
		if df is None or df.empty:
			return []
		df = df[~df['name'].str.contains('ST', na=False)]
		return df['ts_code'].tolist()

	def get_daily (self, symbol: str = '', trade_date: str = '',
	               start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取日线行情

		Args:
			symbol: 股票代码 (如 000001.SZ)
			trade_date: 交易日期 (YYYYMMDD)
			start_date: 开始日期
			end_date: 结束日期
		"""
		try:
			df = self.pro.daily(ts_code=symbol, trade_date=trade_date,
			                    start_date=start_date, end_date=end_date)
			if df is not None and not df.empty:
				df['trade_date'] = pd.to_datetime(df['trade_date'])
				df = df.sort_values('trade_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取日线行情失败: {e}")
			return pd.DataFrame()

	def get_weekly (self, symbol: str = '', trade_date: str = '',
	                start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取周线行情"""
		try:
			df = self.pro.weekly(ts_code=symbol, trade_date=trade_date,
			                     start_date=start_date, end_date=end_date)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取周线行情失败: {e}")
			return pd.DataFrame()

	def get_monthly (self, symbol: str = '', trade_date: str = '',
	                 start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取月线行情"""
		try:
			df = self.pro.monthly(ts_code=symbol, trade_date=trade_date,
			                      start_date=start_date, end_date=end_date)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取月线行情失败: {e}")
			return pd.DataFrame()

	def get_minute_bar (self, symbol: str, start_date: str, end_date: str,
	                    freq: str = '5', adj: str = 'qfq') -> pd.DataFrame:
		"""
		获取分钟行情

		Args:
			symbol: 股票代码 (如 000001.SZ)
			start_date: 开始日期时间 (YYYYMMDDHHmmss 或 YYYYMMDD)
			end_date: 结束日期时间
			freq: 频率 1/5/15/30/60 分钟
			adj: 复权类型 qfq-前复权 hfq-后复权 none-不复权

		Returns:
			包含 open/high/low/close/vol/amount 的DataFrame
		"""
		try:
			# 转换日期格式
			if len(start_date) == 8:
				start_date = start_date + ' 093000'
			if len(end_date) == 8:
				end_date = end_date + ' 153000'

			df = ts.pro_bar(
				ts_code=symbol,
				adj=adj,
				start_date=start_date,
				end_date=end_date,
				freq=freq  # D日线 W周线 M月线 1/5/15/30/60分钟
			)

			if df is not None and not df.empty:
				df = df.sort_values('trade_time')
				df['trade_time'] = pd.to_datetime(df['trade_time'])
				df.rename(columns={
					'vol': 'volume',
					'amount': 'turnover'
				}, inplace=True)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取分钟行情失败: {e}")
			return pd.DataFrame()

	def get_tick_data (self, symbol: str, trade_date: str) -> pd.DataFrame:
		"""
		获取Tick级行情数据

		Args:
			symbol: 股票代码
			trade_date: 交易日期 (YYYYMMDD)

		Returns:
			包含逐笔成交的DataFrame
		"""
		try:
			# 使用 tick_data 接口 (需要会员权限)
			df = self.pro.tick_data(ts_code=symbol, trade_date=trade_date)
			if df is not None and not df.empty:
				df['trade_time'] = pd.to_datetime(
					trade_date + ' ' + df['time'].astype(str).str.zfill(6),
					format='%Y%m%d %H%M%S'
				)
				df = df.sort_values('trade_time')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.warning(f"获取Tick数据失败(可能需要会员权限): {e}")
			return pd.DataFrame()

	def get_large_order (self, symbol: str, trade_date: str,
	                     min_amount: float = 100000) -> pd.DataFrame:
		"""
		获取大单成交数据

		Args:
			symbol: 股票代码
			trade_date: 交易日期
			min_amount: 最小成交金额(元)
		"""
		try:
			# 使用 moneyflow_hsgt 或每日分钟数据
			df = self.pro.moneyflow_hsgt(trade_date=trade_date)
			if df is not None and not df.empty:
				df = df[df['amount'] >= min_amount]
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.warning(f"获取大单数据失败: {e}")
			return pd.DataFrame()

	def get_adj_factor (self, symbol: str, start_date: str = '',
	                    end_date: str = '') -> pd.DataFrame:
		"""获取复权因子

		Args:
			symbol: 股票代码
			start_date: 开始日期
			end_date: 结束日期
		"""
		try:
			df = self.pro.adj_factor(ts_code=symbol, start_date=start_date,
			                         end_date=end_date)
			if df is not None and not df.empty:
				df['trade_date'] = pd.to_datetime(df['trade_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取复权因子失败: {e}")
			return pd.DataFrame()

	def get_suspended (self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取停牌信息

		Args:
			start_date: 开始日期
			end_date: 结束日期
		"""
		try:
			df = self.pro.stock_suspended(start_date=start_date, end_date=end_date)
			if df is not None and not df.empty:
				df['trade_date'] = pd.to_datetime(df['trade_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取停牌信息失败: {e}")
			return pd.DataFrame()

	def get_resumption (self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取复牌信息"""
		try:
			df = self.pro.stock_resumed(start_date=start_date, end_date=end_date)
			if df is not None and not df.empty:
				df['trade_date'] = pd.to_datetime(df['trade_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取复牌信息失败: {e}")
			return pd.DataFrame()

	def get_daily_basic (self, symbol: str = '', trade_date: str = '',
	                     start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取每日行情指标

		包含: PE/PB/总市值/流通市值/换手率/成交量/成交额等
		"""
		try:
			df = self.pro.daily_basic(ts_code=symbol, trade_date=trade_date,
			                          start_date=start_date, end_date=end_date)
			if df is not None and not df.empty:
				df['trade_date'] = pd.to_datetime(df['trade_date'])
				df = df.sort_values('trade_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取每日指标失败: {e}")
			return pd.DataFrame()

	def get_index_constituents (self, index_code: str) -> list:
		"""获取指数成分股

		Args:
			index_code: 指数代码 (如 000300.SH 沪深300)
		"""
		try:
			trade_date = datetime.now().strftime('%Y%m%d')
			df = self.pro.index_weight(index_code=index_code, trade_date=trade_date)
			if df is not None and not df.empty:
				return df['con_code'].tolist()
			return []
		except Exception as e:
			logger.error(f"获取指数成分股失败: {e}")
			return []

	def get_stock_history (self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
		"""获取股票历史数据（前复权日线）"""
		try:
			df = ts.pro_bar(
				ts_code=symbol,
				adj='qfq',
				start_date=start_date.replace('-', ''),
				end_date=end_date.replace('-', '')
			)
			if df is not None and not df.empty:
				df = df.sort_values('trade_date')
				df['trade_date'] = pd.to_datetime(df['trade_date'])
				df.set_index('trade_date', inplace=True)
				df.rename(columns={
					'vol': 'volume',
					'amount': 'turnover'
				}, inplace=True)
				return df[['open', 'high', 'low', 'close', 'volume', 'turnover']]
			return pd.DataFrame()
		except Exception as e:
			logger.error(f"获取股票历史数据失败: {e}")
			return pd.DataFrame()

	def get_trade_cal (self, exchange: str = '',
	                    start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取交易日历（同步方法，由调用方丢线程池）"""
		try:
			df = self.pro.trade_cal(exchange=exchange, start_date=start_date,
			                        end_date=end_date)
			if df is not None and not df.empty:
				df['cal_date'] = pd.to_datetime(df['cal_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取交易日历失败: {e}")
			return pd.DataFrame()

	# ==================== ETF数据 ====================

	def get_etf_basic (self, market: str = '') -> pd.DataFrame:
		"""获取ETF基础信息（字段对齐 Tushare fund_basic，无需映射）

		Args:
			market: 市场 E-上海 S-深圳, 空表示全部
		"""
		try:
			df = self.pro.fund_basic(market=market, status='L')
			if df is None or df.empty:
				logger.warning(f"Tushare fund_basic 返回空: market='{market}', status='L'")
				return pd.DataFrame()
			# 用 name 字段过滤 ETF（排除联接基金）
			df = df[df['name'].str.contains('ETF', na=False) & ~df['name'].str.contains('联接', na=False)]
			logger.debug(f"Tushare fund_basic ETF: {len(df)} 条, 抽样: {df['name'].head(5).tolist()}")
			# 只保留模型中存在的列
			from shared.database.models.data_models import EtfBasic
			known = {c.name for c in EtfBasic.__table__.columns}
			keep = [c for c in df.columns if c in known]
			df = df[keep]
			return df
		except Exception as e:
			logger.error(f"获取ETF基础信息失败: {e}")
			return pd.DataFrame()

	def get_etf_index (self) -> pd.DataFrame:
		"""获取ETF跟踪的基准指数列表（Tushare etf_index 接口）"""
		try:
			df = self.pro.etf_index()
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取ETF基准指数失败: {e}")
			return pd.DataFrame()

	def get_etf_index_weight (self, etf_code: str) -> pd.DataFrame:
		"""获取ETF基准指数权重（Tushare fund_portfolio 接口）"""
		try:
			df = self.pro.fund_portfolio(ts_code=etf_code)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取ETF成分失败: {e}")
			return pd.DataFrame()

	def get_etf_realtime_minute (self, etf_code: str) -> pd.DataFrame:
		"""获取ETF实时分钟行情 (使用分时数据)"""
		try:
			# 使用ts.pro_bar获取当日分钟数据
			today = datetime.now().strftime('%Y%m%d')
			df = ts.pro_bar(
				ts_code=etf_code,
				adj='qfq',
				start_date=today + ' 093000',
				end_date=today + ' 153000',
				freq='5'
			)
			if df is not None and not df.empty:
				df['trade_time'] = pd.to_datetime(df['trade_time'])
				df.rename(columns={'vol': 'volume', 'amount': 'turnover'}, inplace=True)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取ETF实时分钟失败: {e}")
			return pd.DataFrame()

	def get_etf_historical_minute (self, etf_code: str, start_date: str,
	                               end_date: str, freq: str = '5') -> pd.DataFrame:
		"""获取ETF历史分钟行情"""
		return self.get_minute_bar(etf_code, start_date, end_date, freq, 'qfq')

	def get_etf_realtime_daily (self, etf_code: str) -> pd.DataFrame:
		"""获取ETF实时日线（当日行情，fund_daily 接口）"""
		try:
			today = datetime.now().strftime('%Y%m%d')
			df = self.pro.fund_daily(ts_code=etf_code, trade_date=today)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取ETF实时日线失败: {e}")
			return pd.DataFrame()

	def get_etf_daily (self, etf_code: str, start_date: str = '',
	                   end_date: str = '') -> pd.DataFrame:
		"""获取ETF日线行情（Tushare fund_daily 接口）"""
		return self.pro.fund_daily(ts_code=etf_code, start_date=start_date, end_date=end_date)

	def get_etf_adj_factor (self, etf_code: str, start_date: str = '',
	                        end_date: str = '') -> pd.DataFrame:
		"""获取ETF复权因子（Tushare fund_adj 接口）"""
		try:
			df = self.pro.fund_adj(ts_code=etf_code, start_date=start_date, end_date=end_date)
			if df is not None and not df.empty:
				df['trade_date'] = pd.to_datetime(df['trade_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取ETF复权因子失败 {etf_code}: {e}")
			return pd.DataFrame()

	def get_etf_share_scale (self, etf_code: str = '',
	                         trade_date: str = '') -> pd.DataFrame:
		"""获取ETF份额规模

		Args:
			etf_code: ETF代码，空表示全部
			trade_date: 交易日期，空表示最新
		"""
		try:
			df = self.pro.fund_share(ts_code=etf_code, trade_date=trade_date)
			if df is not None and not df.empty:
				from shared.database.models.data_models import EtfShare
				known = {c.name for c in EtfShare.__table__.columns}
				keep = [c for c in df.columns if c in known]
				df = df[keep]
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取ETF份额规模失败: {e}")
			return pd.DataFrame()

	# ==================== 财务数据 ====================

	def get_income_statement (self, symbol: str, period: str = '') -> pd.DataFrame:
		"""
		获取利润表

		Args:
			symbol: 股票代码
			period: 报告期 (YYYYMMDD), 空表示全部
		"""
		try:
			df = self.pro.income(ts_code=symbol, period=period)
			if df is not None and not df.empty:
				df['end_date'] = pd.to_datetime(df['end_date'])
				df = df.sort_values('end_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取利润表失败: {e}")
			return pd.DataFrame()

	def get_balance_sheet (self, symbol: str, period: str = '') -> pd.DataFrame:
		"""获取资产负债表"""
		try:
			df = self.pro.balancesheet(ts_code=symbol, period=period)
			if df is not None and not df.empty:
				df['end_date'] = pd.to_datetime(df['end_date'])
				df = df.sort_values('end_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取资产负债表失败: {e}")
			return pd.DataFrame()

	def get_cashflow_statement (self, symbol: str, period: str = '') -> pd.DataFrame:
		"""获取现金流量表"""
		try:
			df = self.pro.cashflow(ts_code=symbol, period=period)
			if df is not None and not df.empty:
				df['end_date'] = pd.to_datetime(df['end_date'])
				df = df.sort_values('end_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取现金流量表失败: {e}")
			return pd.DataFrame()

	def get_forecast (self, symbol: str = '', period: str = '') -> pd.DataFrame:
		"""获取业绩预告

		Args:
			symbol: 股票代码，空表示全部
			period: 报告期
		"""
		try:
			df = self.pro.forecast(ts_code=symbol, period=period)
			if df is not None and not df.empty:
				df['end_date'] = pd.to_datetime(df['end_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取业绩预告失败: {e}")
			return pd.DataFrame()

	def get_express (self, symbol: str = '', period: str = '') -> pd.DataFrame:
		"""获取业绩快报"""
		try:
			df = self.pro.express(ts_code=symbol, period=period)
			if df is not None and not df.empty:
				df['end_date'] = pd.to_datetime(df['end_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取业绩快报失败: {e}")
			return pd.DataFrame()

	def get_dividend (self, symbol: str = '', limit: int = 100) -> pd.DataFrame:
		"""获取分红送股数据

		Args:
			symbol: 股票代码，空表示全部
			limit: 返回数量限制
		"""
		try:
			df = self.pro.dividend(ts_code=symbol, limit=limit)
			if df is not None and not df.empty:
				for col in ('div_date', 'imp_date', 'record_date', 'ex_date', 'pay_date', 'ann_date'):
					if col in df.columns:
						df[col] = pd.to_datetime(df[col])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取分红送股数据失败: {e}")
			return pd.DataFrame()

	def get_fina_indicator (self, symbol: str = '', start_date: str = '',
	                        end_date: str = '') -> pd.DataFrame:
		"""获取财务指标数据

		包含: ROE/毛利率/净利率/资产负债率/周转率等
		"""
		try:
			df = self.pro.fina_indicator_vip(ts_code=symbol, start_date=start_date,
			                             end_date=end_date)
			if df is not None and not df.empty:
				df['end_date'] = pd.to_datetime(df['end_date'])
				df = df.sort_values('end_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取财务指标失败: {e}")
			return pd.DataFrame()

	def get_fina_audit (self, symbol: str = '', start_date: str = '',
	                    end_date: str = '') -> pd.DataFrame:
		"""获取财务审计意见"""
		try:
			df = self.pro.fina_audit(ts_code=symbol, start_date=start_date,
			                         end_date=end_date)
			if df is not None and not df.empty:
				df['end_date'] = pd.to_datetime(df['end_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取财务审计意见失败: {e}")
			return pd.DataFrame()

	def get_fina_mainbz (self, symbol: str = '', period: str = '', type: str = '') -> pd.DataFrame:
		"""获取主营业务构成

		Args:
			symbol: 股票代码
			period: 报告期
			type: 类型（P=产品, D=地区, I=行业）
		"""
		try:
			df = self.pro.fina_mainbz(ts_code=symbol, period=period, type=type)
			if df is not None and not df.empty:
				df['end_date'] = pd.to_datetime(df['end_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取主营业务构成失败: {e}")
			return pd.DataFrame()

	# ==================== 扩展功能 ====================

	def get_moneyflow (self, symbol: str = '', trade_date: str = '',
	                   start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取资金流向"""
		try:
			df = self.pro.moneyflow(ts_code=symbol, trade_date=trade_date,
			                        start_date=start_date, end_date=end_date)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取资金流向失败: {e}")
			return pd.DataFrame()

	def get_stock_company (self, exchange: str = '') -> pd.DataFrame:
		"""获取上市公司基本信息"""
		try:
			df = self.pro.stock_company(exchange=exchange)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取公司信息失败: {e}")
			return pd.DataFrame()

	def get_stk_managers (self, ts_code: str = '') -> pd.DataFrame:
		"""获取管理层信息"""
		try:
			df = self.pro.stk_managers(ts_code=ts_code)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取管理层信息失败: {e}")
			return pd.DataFrame()

	def get_stk_rewards (self, ts_code: str = '') -> pd.DataFrame:
		"""获取管理层薪酬持股"""
		try:
			df = self.pro.stk_rewards(ts_code=ts_code)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取管理层薪酬失败: {e}")
			return pd.DataFrame()

	def get_index_basic (self, market: str = '') -> pd.DataFrame:
		"""获取指数基本信息（沪深市场指数列表）

		Tushare接口: index_basic
		返回沪深市场全部指数的基本信息（代码、名称、基期、基点、发布日期等）
		"""
		try:
			kwargs = {}
			if market:
				kwargs['market'] = market  # SSE=上交所 SZSE=深交所
			df = self.pro.index_basic(**kwargs)
			if df is not None and not df.empty:
				if 'list_date' in df.columns:
					df['list_date'] = pd.to_datetime(df['list_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取指数基本信息失败: {e}")
			return pd.DataFrame()

	def get_index_daily (self, ts_code: str = '', start_date: str = '',
	                     end_date: str = '') -> pd.DataFrame:
		"""获取指数日线行情

		Tushare接口: index_daily
		用于同步指数日线行情到 index_daily 表
		"""
		try:
			df = self.pro.index_daily(ts_code=ts_code, start_date=start_date,
			                          end_date=end_date)
			if df is not None and not df.empty:
				df['trade_date'] = pd.to_datetime(df['trade_date'])
				df = df.sort_values('trade_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取指数日线行情失败: {e}")
			return pd.DataFrame()

	def get_namechange (self, ts_code: str = '', start_date: str = '',
	                    end_date: str = '') -> pd.DataFrame:
		"""获取股票曾用名/ST 变更历史

		Tushare接口: namechange
		包含股票名称变更记录（含 ST/*ST 特别处理），用于同步 stock_st_list 表
		过滤条件: name 包含 'ST' 的记录
		"""
		try:
			df = self.pro.namechange(ts_code=ts_code, start_date=start_date,
			                         end_date=end_date)
			if df is not None and not df.empty:
				if 'start_date' in df.columns:
					df['start_date'] = pd.to_datetime(df['start_date'])
				if 'end_date' in df.columns:
					df['end_date'] = pd.to_datetime(df['end_date'])
				df = df.sort_values('start_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取ST变更历史失败: {e}")
			return pd.DataFrame()

	# ==================== 指数相关扩展接口 ====================

	def get_index_weight (self, index_code: str, trade_date: str = '') -> pd.DataFrame:
		"""获取指数成分股权重（Tushare index_weight 接口）

		Args:
			index_code: 指数代码（如 000300.SH 沪深300）
			trade_date: 交易日期（YYYYMMDD，空=最新交易日）

		Returns:
			DataFrame: columns: index_code, con_code, weight, trade_date
		"""
		try:
			if trade_date:
				df = self.pro.index_weight(index_code=index_code, trade_date=trade_date)
			else:
				df = self.pro.index_weight(index_code=index_code)
			if df is not None and not df.empty:
				if 'trade_date' in df.columns:
					df['trade_date'] = pd.to_datetime(df['trade_date'])
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取指数成分股权重失败: {e}")
			return pd.DataFrame()

	def get_index_weekly (self, ts_code: str = '', start_date: str = '',
	                      end_date: str = '') -> pd.DataFrame:
		"""获取指数周线行情（Tushare index_weekly 接口）

		Args:
			ts_code: 指数代码（如 000001.SH 上证指数）
			start_date: 开始日期（YYYYMMDD）
			end_date: 结束日期（YYYYMMDD）

		Returns:
			DataFrame: 周线行情数据
		"""
		try:
			df = self.pro.index_weekly(ts_code=ts_code, start_date=start_date,
			                           end_date=end_date)
			if df is not None and not df.empty:
				df['trade_date'] = pd.to_datetime(df['trade_date'])
				df = df.sort_values('trade_date')
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取指数周线行情失败: {e}")
			return pd.DataFrame()

	# ==================== 宏观经济接口 ====================

	def get_cpi (self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取CPI居民消费价格指数（Tushare cn_cpi 接口）

		Args:
			start_date: 开始日期（YYYYMMDD）
			end_date: 结束日期（YYYYMMDD）

		Returns:
			DataFrame: CPI 月度数据
		"""
		try:
			df = self.pro.cn_cpi(start_date=start_date, end_date=end_date)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取CPI数据失败: {e}")
			return pd.DataFrame()

	def get_ppi (self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取PPI工业生产者出厂价格指数（Tushare cn_ppi 接口）

		Args:
			start_date: 开始日期（YYYYMMDD）
			end_date: 结束日期（YYYYMMDD）

		Returns:
			DataFrame: PPI 月度数据
		"""
		try:
			df = self.pro.cn_ppi(start_date=start_date, end_date=end_date)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取PPI数据失败: {e}")
			return pd.DataFrame()

	def get_gdp (self, start_date: str = '', end_date: str = '') -> pd.DataFrame:
		"""获取GDP国内生产总值（Tushare cn_gdp 接口）

		Args:
			start_date: 开始日期（YYYYMMDD）
			end_date: 结束日期（YYYYMMDD）

		Returns:
			DataFrame: GDP 季度数据
		"""
		try:
			df = self.pro.cn_gdp(start_date=start_date, end_date=end_date)
			return df if df is not None else pd.DataFrame()
		except Exception as e:
			logger.error(f"获取GDP数据失败: {e}")
			return pd.DataFrame()