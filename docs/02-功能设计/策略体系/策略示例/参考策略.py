# 克隆自聚宽文章：https://www.joinquant.com/post/72442
# 标题：最近网上比较火热的ETF轮动策略优缺点详细分析
# 作者：路虽远终必达（求回赞）

#在聚宽5年回测结果
# 策略收益 1822.64%
# 策略年化收益 74.24%
# 超额收益 1969.21%
# 基准收益 -7.08%
# 阿尔法 0.733
# 贝塔 0.568
# 夏普比率 2.482
# 胜率 0.525
# 盈亏比 2.200
# 最大回撤 26.45%
# 索提诺比率 4.237
# 日均超额收益0.24%
# 超额收益最大回撤 26.91%
# 超额收益夏普比率 2.641
# 日胜率 0.533
# 盈利次数 117
# 亏损次数 106
# 信息比率 2.749
# 策略波动率 0.283
# 基准波动率 0.180
# 最大回撤区间 2026/03/02,2026/04/28

import datetime
import math
import prettytable
import numpy as np
import pandas as pd
from collections import defaultdict
from jqdata import *
from jqfactor import *
from prettytable import PrettyTable
# import time  # 导入time模块
# from functools import wraps
# from nredistrade import *  # 导入实盘依赖

""" ====================== 基础配置 ====================== """


# 回测设置
def set_backtest():
	set_option('avoid_future_data', True)
	set_benchmark('000300.XSHG')
	set_option('use_real_price', True)

	set_slippage(FixedSlippage(0.002), type="stock")
	set_slippage(FixedSlippage(0.001), type="fund")
	cost_configs = [
		("stock", 0.0005, 2.5 / 10000, 5),
		("fund", 0, 2.5/ 10000, 0),
		("mmf", 0, 0, 0)
	]
	for asset_type, close_tax, commission, min_comm in cost_configs:
		set_order_cost(OrderCost(
			open_tax=0, close_tax=close_tax,
			open_commission=commission, close_commission=commission,
			close_today_commission=0, min_commission=min_comm
		), type=asset_type)


# 基础参数设置
def set_params(context):

	g.portfolio_value_proportion = [0, 0, 1, 0]  # 测试ETF轮动

	g.starting_cash = 500000 if 1 in g.portfolio_value_proportion else 200000  # 策略初始资金, 用于计算子策略收益波动曲线
	g.stock_strategy = {}  # 记录股票对应的策略, 反向映射方便检索
	g.strategy_holdings = {1: [], 2: [], 3: [], 4: []}
	# 记录策略初始的金额, 用于计算各策略收益波动曲线
	g.strategy_starting_cash = {
		1: g.starting_cash * g.portfolio_value_proportion[0],  # 小市值 初始资金
		2: g.starting_cash * g.portfolio_value_proportion[1],  # ETF反弹 初始资金
		3: g.starting_cash * g.portfolio_value_proportion[2],  # ETF轮动 初始资金
		4: g.starting_cash * g.portfolio_value_proportion[3],  # 白马攻防 初始资金
	}
	# 记录每日策略收益
	g.strategy_value_data = {}
	g.strategy_value = {
		1: g.starting_cash * g.portfolio_value_proportion[0],  # 小市值 初始资金
		2: g.starting_cash * g.portfolio_value_proportion[1],  # ETF反弹 初始资金
		3: g.starting_cash * g.portfolio_value_proportion[2],  # ETF轮动 初始资金
		4: g.starting_cash * g.portfolio_value_proportion[3],  # 白马攻防 初始资金
	}
	# 暂存一个ETF反弹的初始比例
	g.strategy_ETF_2000_proportion = g.portfolio_value_proportion[1]
	g.strategy_ETF_2000_proportion_reset = None  # 用于检测拨正
	capital_balance_2(context)  # 首次就进行一次检测

	# 顶背离检查
	g.DBL_control = True  # 小市值大盘顶背离记录（用于风险控制）
	g.ETF_DBL_control = True  # ETF独立顶背离记录
	g.dbl = []
	g.etf_dbl = defaultdict(int)
	g.check_dbl_days = 10  # 顶背离检测窗口期长度, 窗口内不仅买入

	# 止损检查
	g.run_stoploss = True  # 是否进行止损
	g.use_move_stoploss = False  # 是否使用移动止损, 不太适用, 先做保留
	g.stoploss_limit = 0.09  # 止损线
	g.stop_loss_tracking = {}  # 移动止损跟踪字典, 记录持仓最高收益价格

	# 异常处理窗口期检查
	g.check_after_no_buy = False  # 检查后不再买入时间
	g.no_buy_stocks = {}  # 检查卖出的股票
	g.no_buy_after_day = 3  # 止损后不买入的时间窗口

	# 成交额宽度检查
	g.check_defense = True  # 成交额宽度检查
	g.industries = ["组20"]  # 高位防御板块
	g.defense_signal = None
	g.cnt_defense_signal = []  # 择时次数
	g.cnt_bank_signal = []  # 组20择时次数


# 策略参数设置
def set_strategy_params(context):
	""" 策略3 ETF轮动 参数 """
	# 策略3全局变量
	g.etf_pool_3 = [
		# 商品
		'501018.XSHG',  # 南方原油
		'518880.XSHG',  # 黄金ETF
		# 跨境
		'513520.XSHG',  # 日经ETF
		'513100.XSHG',  # 纳指100
		# 港股
		'513020.XSHG',  # 港股科技
		# 国内
		'510180.XSHG',  # 上证180
		'588220.XSHG',  # 科创板
		'159915.XSHE',  # 创业板
		# 债券
		'511090.XSHG',  # 30年国债ETF
	]
	g.select_etf = None  # ETF交易传递变量
	g.m_days = 25  # 动量参考天数
	g.m_score = 5  # 动量过滤分数
	g.stock_sum = 1  # 持有ETF数量
	g.buy_etf = None
	g.sell_etf = None
	# g.enable_stop_loss_by_cur_day = False  # 是否开启日内止损
	g.enable_stop_loss_by_cur_day = True  # 是否开启日内止损
	g.stoploss_limit_by_cur_day = -0.03  # 当日亏损 -3%

def initialize(context):
	set_backtest()  # 设置回测条件
	set_params(context)  # 设置基础参数
	set_strategy_params(context)  # 设置策略参数
	# setup_redis_trade(context, 'strategy1')  # 设置实盘

	# 过滤日志
	log.set_level('order', 'error')

	# 策略3 ETF轮动策略
	if g.portfolio_value_proportion[2] > 0:
		# 先计算得分，输出日志
		run_daily(strategy_3_calc, '10:30')
		run_daily(strategy_3_sell, '10:30')
		run_daily(strategy_3_buy, '10:30')

		if g.enable_stop_loss_by_cur_day:
			run_daily(etf_stop_loss_by_cur_day, '10:00')  # 日内亏损检测
		run_daily(etf_volume_check, '13:30')

	# 止损检查
	run_daily(take_profit_stop_loss, '10:35')
	# 记录各策略每日收益
	run_daily(make_record, '15:01')


""" ====================== 策略3: ETF轮动 ====================== """



def strategy_3_calc(context):
	log.info("------------------------------开盘----------------")
	# 新增：确保 g.buy_etf 被初始化
	if not hasattr(g, 'buy_etf'):
		g.buy_etf = None

	# 获取动量最高的ETF - 这部分完全不变
	g.buy_etf = get_etf_rank(context, g.etf_pool_3)

	# 检查当前持仓 - 这部分完全不变
	current_etf = None
	for asset in context.portfolio.positions:
		if asset in g.etf_pool_3:
			current_etf = asset
			break

	# 原有的买卖判断逻辑完全不变
	if (current_etf and current_etf != g.buy_etf):
		g.sell_etf = current_etf
		log.warn(f"ETF轮动调仓: 卖出：{get_stock_name(current_etf)} -> 买入：{get_stock_name(g.buy_etf)}")
	elif not current_etf and g.buy_etf:
		log.warn(f"ETF轮动建仓: ：{get_stock_name(g.buy_etf)}({g.buy_etf})")
	elif current_etf == g.buy_etf:
		g.buy_etf = None
		g.sell_etf = None
		log.warn(f"KEEP")


def get_etf_rank(context, etf_pool):

	rank_list = []
	# 日内止损, 距离开盘暴跌的不进行买入
	current_data = get_current_data()
	for etf in etf_pool:
		if g.enable_stop_loss_by_cur_day:
			ratio = cal_cur_to_open_ratio(etf)
			if ratio <= g.stoploss_limit_by_cur_day:
				log.info(f"{etf} {get_stock_name(etf)} 进入跌幅达到 {ratio * 100:.2f}%, 已排除")
				continue
		rank_list.append(etf)

	# 过滤 动量得分, ( 0 ~ 5 )
	rank_list = filter_moment_rank(rank_list, g.m_days, 0, g.m_score)
	# 过滤异常量, 一刀切

	rank_list = filter_volume(context, rank_list)
	# 过滤 RSRS + 均值

	target_etf = filter_rsrs(rank_list)

	return target_etf

def strategy_3_sell(context):
	if not hasattr(g, 'sell_etf') or g.sell_etf is None:
		log.info("无需卖出操作")
		return

	# 检查要卖出的ETF是否停牌
	current_data = get_current_data()
	if g.sell_etf in current_data and current_data[g.sell_etf].paused:
		log.warn(f"⚠️ {get_stock_name(g.sell_etf)} ({g.sell_etf}) 今日停牌，无法卖出，跳过本次交易")
		# 重置买卖标志，避免继续尝试交易
		g.sell_etf = None
		g.buy_etf = None
		return

	if g.sell_etf:
		for current_etf in g.strategy_holdings[3]:
			close_position(context, current_etf)
		g.strategy_holdings[3] = []
		return
	g.strategy_holdings[3] = list(set(g.strategy_holdings[3]))


def strategy_3_buy(context):
	# 新增：安全检查
	if not hasattr(g, 'buy_etf') or g.buy_etf is None:
		log.info("没有要买入的ETF")
		return

	if g.buy_etf:
		strategy_cash = context.portfolio.total_value * g.portfolio_value_proportion[2]
		open_position(context, g.buy_etf, strategy_cash, 3)  # 买入新的
	g.strategy_holdings[3] = list(set(g.strategy_holdings[3]))



# 动量计算
def moment_rank(stock_pool, days, ll, hh):
	# - 对股票近days天的收盘价取对数，进行加权线性回归（近期权重高）。
	# - 计算年化收益率（指数化斜率）和R平方（趋势强度）。
	# - 动量得分 = 年化收益率×R平方。

	def mom(_stock):
		y = np.log(attribute_history(_stock, days, '1d', ['close'], df=False)['close'])
		n = len(y)
		x = np.arange(n)
		weights = np.linspace(1, 2, n)
		slope, intercept = np.polyfit(x, y, 1, w=weights)
		annualized_returns = math.pow(math.exp(slope), 250) - 1
		residuals = y - (slope * x + intercept)
		weighted_residuals = weights * residuals ** 2
		r_squared = 1 - (np.sum(weighted_residuals) / np.sum(weights * (y - np.mean(y)) ** 2))
		return annualized_returns * r_squared

	score_list = []
	for stock in stock_pool:
		score = mom(stock)
		score_list.append(score)
	df = pd.DataFrame(index=stock_pool, data={'score': score_list})
	df = df.sort_values(by='score', ascending=False)  # 降序
	df = df[(df['score'] > ll) & (df['score'] < hh)]
	rank_list = list(df.index)
	return rank_list


""" ====================== 辅助的定时执行函数 ====================== """

# 尾盘记录各个策略的收益
def make_record(context):
	positions = context.portfolio.positions
	if not positions:
		return
	current_data = get_current_data()

	# 收盘后再把ETF轮动的明日选股提前透漏下
	# if g.portfolio_value_proportion[2]:
	#     filter_moment_rank(g.etf_pool_3, g.m_days, 0, g.m_score)


# ETF轮动成交量检测
def etf_volume_check(context):
	# 检测7日均值的双倍成交量
	# print(f"ETF轮动成交量检测: 当前持仓 {g.strategy_holdings[3]}")
	holdings = set(g.strategy_holdings[3])
	filter_volume(context,
	              stock_list=holdings,
	              days=7, volume_threshold=2,
	              check_only=False,
	              check_price=True)


# ETF轮动日内止损检测
def etf_stop_loss_by_cur_day(context):
	holdings = set(g.strategy_holdings[3])
	# 检测日内亏损
	stop_loss_by_cur_day(context, holdings, ratio=g.stoploss_limit_by_cur_day)


""" ====================== 公共函数 ====================== """


# 获取股票名字
def get_stock_name(security):
	try:
		stock_info = get_security_info(security)
		return stock_info.display_name
	except Exception:
		return "无"


# 封装实盘下单函数
def my_order_target_value(context, security, value):
	o = order_target_value(security, value)
	if o:
		stock_show = f"{security} {get_stock_name(security)[:8]}: ".ljust(20)
		if o.is_buy:
			if o.price * o.amount > 0:
				log.info(f"买入操作： {stock_show}  "
				         f"买价{o.price:<7.2f}  "
				         f"买量{o.amount:<7}   "
				         f"价值{o.price * o.amount:.2f}")
				return o
		else:
			if o.price * o.amount > 0:
				log.info(f"卖出操作： {stock_show}  "
				         f"卖价{o.price:<7.2f}  "
				         f"成本{o.avg_cost:<7.2f}   "
				         f"卖量{o.amount:<7}   "
				         f"盈亏{(o.price - o.avg_cost) * o.amount:.2f}"
				         f"( {(o.price - o.avg_cost) / o.avg_cost * 100:.2f}% )")
				return o


# 开仓买入并记录策略持仓
def open_position(context, security, value, strategy_id):
	order = my_order_target_value(context, security, value)
	if order:
		security not in g.strategy_holdings[strategy_id] and g.strategy_holdings[strategy_id].append(security)
		g.stock_strategy[security] = strategy_id
	return order


# 闭仓卖出并清空策略持仓
def close_position(context, security):
	order = my_order_target_value(context, security, 0)
	if order:
		strategy_id = g.stock_strategy[security]
		# 持仓列表移除
		security in g.strategy_holdings[strategy_id] and g.strategy_holdings[strategy_id].remove(security)
		# 计算卖出的盈亏
		pnl_value = (order.price - order.avg_cost) * order.amount
		# 每日策略总价值更新盈亏
		g.strategy_value[strategy_id] += pnl_value
	return order


# 止盈止损
def take_profit_stop_loss(context):
	if not g.run_stoploss:
		return

	# 更新已经止损的票止损日到目前的时间
	no_buy_stocks = {}
	for k, v in g.no_buy_stocks.items():
		v += 1
		if v <= g.no_buy_after_day:
			no_buy_stocks[k] = v
	g.no_buy_stocks = no_buy_stocks

	# 计算移动止损
	current_data = get_current_data()
	if g.use_move_stoploss:
		for stock, position in context.portfolio.positions.items():
			if current_data[stock].paused:
				continue
			current_price = current_data[stock].last_price
			# 更新最高价
			if stock not in g.stop_loss_tracking:
				g.stop_loss_tracking[stock] = max(position.avg_cost, current_price)
			else:
				g.stop_loss_tracking[stock] = max(g.stop_loss_tracking[stock], current_price)
			# 检查是否触发移动止损
			highest_price = g.stop_loss_tracking[stock]
			if current_price <= highest_price * (1 - g.stoploss_limit):
				close_position(context, stock)
				g.no_buy_stocks[stock] = 1
				log.info(f"移动止损卖出 {stock}, 亏损:{(1 - position.price / position.avg_cost):.2%}")

	for stock, pos in context.portfolio.positions.items():
		if current_data[stock].paused:
			continue
		# 白马不进行止盈止损
		if stock in g.strategy_holdings[4]:
			continue
		# 盈利100%止盈
		if pos.price >= pos.avg_cost * 2:
			close_position(context, stock)
			g.no_buy_stocks[stock] = 1
			log.info(f"止盈卖出 {stock}, 收益率:{(pos.price / pos.avg_cost - 1):.2%}")
		# 非移动止损
		if not g.use_move_stoploss and pos.price <= pos.avg_cost * (1 - g.stoploss_limit):
			close_position(context, stock)
			g.no_buy_stocks[stock] = 1
			log.info(f"止损卖出 {stock}, 亏损:{(1 - pos.price / pos.avg_cost):.2%}")


# 日内止损
def stop_loss_by_cur_day(context, stock_list, ratio=-0.03):
	for stock in stock_list:
		cur_ratio = cal_cur_to_open_ratio(stock)
		if cur_ratio < ratio:
			log.info(f"{stock} {get_stock_name(stock)} 距离开盘跌幅 {cur_ratio * 100:.2f}% 清仓处理")
			close_position(context, stock)


# 检查昨日涨停股今日表现
def check_limit_up(context):
	# 获取当前持仓
	# holdings = list(context.portfolio.positions.keys())
	holdings = g.strategy_holdings[1][:]  # 只检查策略1
	g.yesterday_HL_list = []
	# 获取昨日涨停股
	if holdings:
		# 确保所有持仓股票代码都是字符串
		valid_holdings = [s for s in holdings if isinstance(s, str) and '.' in s]
		if valid_holdings:
			df = get_price(valid_holdings, end_date=context.previous_date,
			               frequency='daily', fields=['close', 'high_limit'],
			               count=1, panel=False)
			if not df.empty:
				g.yesterday_HL_list = list(df[df['close'] >= df['high_limit'] * 0.997].index)
				if g.yesterday_HL_list:
					log.info(f"昨日涨停股: {[holdings[i] for i in g.yesterday_HL_list]}")

	# 检查涨停是否打开
	for i in sorted(g.yesterday_HL_list, reverse=True):
		stock = holdings[i]
		try:
			current_data = get_current_data()[stock]
			if current_data.last_price < current_data.high_limit * 0.99:  # 打开超过1%
				log.info(f"涨停打开卖出 {stock}")
				close_position(context, stock)
				# 记录不再购买
				g.no_buy_stocks[stock] = 1
		except Exception as e:
			log.error(f"处理股票{stock}时出错: {str(e)}")


""" ====================== 模块工具函数 ====================== """


# 计算最新价格对比开盘价格的比值
def cal_cur_to_open_ratio(security):
	current_data = get_current_data()
	last_price = current_data[security].last_price
	day_open = current_data[security].day_open
	return (last_price - day_open) / day_open


# 计算MACD指标
def mcad(close, short=12, long=26, m=9):
	"""计算 MACD 指标
	用于判断趋势强度和潜在反转点，由 DIF、DEA、MACD 柱组成

	参数:
		close: 收盘价序列
		short: 短期EMA周期（默认12）
		long: 长期EMA周期（默认26）
		m: 信号周期（默认9）

	返回:
		DIF: 短期EMA与长期EMA的差值
		DEA: DIF的M期EMA
		MACD: (DIF-DEA)*2（放大波动）
	"""

	# 计算指数移动平均线
	def ema(series, n):
		"""计算指数移动平均线（Exponential Moving Average）
		用于平滑价格波动，反映近期价格趋势，权重随时间递减

		参数:
			series: 价格序列（如收盘价）
			N: 计算周期

		返回:
			EMA序列
		"""
		return pd.Series.ewm(series, span=n, min_periods=n - 1, adjust=False).mean()

	dif = ema(close, short) - ema(close, long)
	dea = ema(dif, m)
	return dif, dea, (dif - dea) * 2


# 动量计算
def filter_moment_rank(stock_pool, days, ll, hh, show_print=True):
	scores_data = pd.DataFrame(index=stock_pool, columns=["annualized_returns", "r2", "score"])
	current_data = get_current_data()

	for code in stock_pool:
		try:
			hist_data = attribute_history(code, days, "1d", ["close", "high"])
			if hist_data.empty:
				continue

			prices = np.append(hist_data["close"].values, current_data[code].last_price)
			log_prices = np.log(prices)
			x_values = np.arange(len(log_prices))
			weights = np.linspace(1, 2, len(log_prices))

			slope, intercept = np.polyfit(x_values, log_prices, 1, w=weights)
			annualized_return = math.exp(slope * 250) - 1
			scores_data.loc[code, "annualized_returns"] = annualized_return

			ss_res = np.sum(weights * (log_prices - (slope * x_values + intercept)) ** 2)
			ss_tot = np.sum(weights * (log_prices - np.mean(log_prices)) ** 2)
			r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
			scores_data.loc[code, "r2"] = r2

			momentum_score = annualized_return * r2
			scores_data.loc[code, "score"] = momentum_score

			if min(prices[-1] / prices[-2], prices[-2] / prices[-3],
			       prices[-3] / prices[-4]) < 0.95:
				scores_data.loc[code, "score"] = -8

		except Exception as e:
			log.info(f"计算{code}动量得分失败: {e}")
			scores_data.loc[code, "score"] = -99

	sorted_scores = scores_data.sort_values("score", ascending=False)

	index_rank = [(etf, row["score"]) for etf, row in sorted_scores.iterrows()]
	score_line = " > ".join([f"{get_stock_name(etf)}:{score:.3f}" for etf, score in index_rank[:5]])
	log.info(f"ETF初始得分: {score_line}")


	valid_etfs = sorted_scores[(sorted_scores['score'] > ll) & (sorted_scores['score'] < hh)]

	return valid_etfs.index.tolist()

# 成交量过滤
#装饰器：跟踪函数的运行时间（精确到毫秒）
# @track_time
def filter_volume(context, stock_list, days=7, volume_threshold=2, check_only=True, check_price=False):
	"""
	:param context:
	:param stock_list: 要检测的股票
	:param days: 检测周期天数
	:param volume_threshold: 阈值
	:param check_only: 只进行检测, 避免跟定时任务逻辑冲突, 定时任务的情况下会对异常进行卖出处理
	:param check_price: 检查最新价格与开盘价
	:return:
	"""

	def _is_price_below_open(security):
		current_data = get_current_data()
		return current_data[security].last_price < current_data[security].day_open

	def _get_volume_ratio(security):

		try:
			hist_data = attribute_history(security, days, '1d', ['volume'])
			if hist_data.empty or len(hist_data) < days:
				return
			avg_volume = hist_data['volume'].mean()
			df_vol = get_price(security, start_date=context.current_dt.date(), end_date=context.current_dt,
			                   frequency='1m', fields=['volume'], skip_paused=False, fq='pre', panel=True,
			                   fill_paused=False)
			if df_vol is None or df_vol.empty:
				return
			current_volume = df_vol['volume'].sum()
			_volume_ratio = current_volume / avg_volume
			# print(f"{security} 成交量较近{days}日均值 x{_volume_ratio:.2f}")
			# 检测到异常, 返回异常倍数
			if _volume_ratio > volume_threshold:
				return _volume_ratio
		except Exception as e:
			log.info(f"检查{security}成交量失败: {e}")
			return

	res = []
	for stock in stock_list:
		if check_only:
			ratio = _get_volume_ratio(stock)
			if not ratio:
				res.append(stock)
			else:
				log.info(f"👾👾👾👾👾 {stock} {get_stock_name(stock)} 近{days}日成交量异常, 为均值的{ratio:.4f}倍, 不纳入选择")
		else:
			position = context.portfolio.positions.get(stock)
			if position.closeable_amount == 0:
				continue
			if position.init_time.date() == context.current_dt.date():
				continue
			ratio = _get_volume_ratio(stock)
			if ratio:
				if check_price and not _is_price_below_open(stock):
					continue
				log.info(f"👽👽👽👽👽 {stock} {get_stock_name(stock)} 近{days}日成交量异常, 较均值 x{ratio}倍, 执行卖出")
				close_position(context, stock)
	return res



def filter_rsrs(stock_list):
	# 计算斜率
	def _get_slope(security, days=18):
		try:
			hist_data = attribute_history(security, days, '1d', ['high', 'low'])
			if hist_data.empty or len(hist_data) < days:
				return None
			slope = np.polyfit(hist_data['low'].values, hist_data['high'].values, 1)[0]
			return slope
		except Exception as e:
			log.info(f"计算{security} RSRS斜率失败: {e}")
			return None

	# 计算阈值
	def _get_beta(security, lookback_days=250, window=20):
		try:
			hist_data = attribute_history(security, lookback_days, '1d', ['high', 'low'])
			if hist_data.empty or len(hist_data) < lookback_days:
				return

			slope_list = []
			for i in range(len(hist_data) - window + 1):
				window_data = hist_data.iloc[i:i + window]
				low_values = window_data['low'].values
				high_values = window_data['high'].values

				if len(low_values) < window or len(high_values) < window:
					continue
				if np.any(np.isnan(low_values)) or np.any(np.isnan(high_values)):
					continue
				if np.any(np.isinf(low_values)) or np.any(np.isinf(high_values)):
					continue
				if np.std(low_values) == 0 or np.std(high_values) == 0:
					continue

				slope = np.polyfit(low_values, high_values, 1)[0]
				slope_list.append(slope)

			if len(slope_list) < 2:
				return None

			mean_slope = np.mean(slope_list)
			std_slope = np.std(slope_list)
			beta = mean_slope - 2 * std_slope
			return beta
		except Exception as e:
			log.info(f"计算{security} RSRS Beta失败: {e}")
			return None

	# 计算强度
	def _check_with_strength(security):
		_slope = _get_slope(security)
		_beta = _get_beta(security)

		if _slope is None or _beta is None:
			return None, 0
		_strength = (_slope - _beta) / abs(_beta) if _beta != 0 else 0
		return _slope > _beta, _strength

	# 计算均值
	def _check_above_ma(security, days=20):
		try:
			hist = attribute_history(security, days, "1d", ["close"])
			if len(hist) < days:
				return False
			current_price = get_current_data()[security].last_price
			return current_price >= hist["close"].mean()
		except Exception as e:
			log.info(f"计算{security} {days}日均线失败: {e}")
			return False


	for stock in stock_list:
		rsrs_pass, stock_strength = _check_with_strength(stock)
		log.info(f"{get_stock_name(stock)}, rsrs_pass:{rsrs_pass}, strength:{stock_strength:.3f}, 五日线上:{_check_above_ma(stock, 5)},十日线上:{_check_above_ma(stock, 10)}")
		if rsrs_pass:
			if stock_strength > 0.15:
				return stock
			elif stock_strength > 0.03 and _check_above_ma(stock, 5):
				return stock
			elif _check_above_ma(stock, 10):
				return stock
	return None



# 资金再平衡 (用不上, 框架已自动实现)
def capital_balance(context):
	g.now_days += 1
	if g.now_days < g.balance_cycle_days:
		return
	# 记录当前的持仓标的
	cur_holdings = {
		1: g.strategy_holdings[1][:],
		2: g.strategy_holdings[2][:],
		3: g.strategy_holdings[3][:],
		4: g.strategy_holdings[4][:],
	}
	# 检测是否可以全部清空, 不能就往后推迟, 直到能全部清空
	can_clear = True
	for stock in g.stock_strategy:
		# 检测是否可以出售
		if context.portfolio.positions[stock].closeable_amount == 0:
			can_clear = False
			break
	if can_clear:
		log.info(f"~~~~~~~~~~~~~~~~~~~~~~~~~执行资金再平衡 实际周期为: {g.now_days} ~~~~~~~~~~~~~~~~~~~~~~~~~")
		# 全部清空
		for stock in g.stock_strategy:
			close_position(context, stock)
		# 平衡后重新买入
		for strategy_id, stock_lists in cur_holdings.items():
			strategy_total_value = context.portfolio.total_value * g.portfolio_value_proportion[strategy_id]
			log.info(f"策略 {strategy_id} 资金: {strategy_total_value}, 重新买入: {stock_lists}")
			value = strategy_total_value / len(stock_lists)
			for stock in stock_lists:
				open_position(context, stock, value, strategy_id)
		g.now_days = 1
	log.info("~~~~~~~~~~~~~~~~~~~~~~~~~再平衡结束~~~~~~~~~~~~~~~~~~~~~~~~~")


# 资金再平衡, 2000ETF反弹策略的周期无法早于2023.10, 基于此时间进行资金平衡
def capital_balance_2(context):
	"""
	2023.10 之前 ETF反弹 的仓位纳入到 ETF轮动 中
	"""
	cur_date = str(context.current_dt.date())
	# 基于首次进行检测
	if cur_date < "2023-09-28" and g.strategy_ETF_2000_proportion_reset is None:
		g.portfolio_value_proportion[2] += g.strategy_ETF_2000_proportion
		g.portfolio_value_proportion[1] = 0
		g.strategy_ETF_2000_proportion_reset = False
	# 到达既定时间后进行拨正原始比例
	elif cur_date >= "2023-09-28" and g.strategy_ETF_2000_proportion_reset is False:
		# 计算ETF轮动所需要分配资金
		strategy_total_value = context.portfolio.total_value * g.strategy_ETF_2000_proportion
		# 检测ETF轮动是否有持仓, 如果有的话就要吐出来还给ETF反弹
		if g.strategy_holdings[2]:
			cur_etf = g.strategy_holdings[2]
			if context.portfolio.positions[cur_etf].closeable_amount > 0:
				o = order_value(context, cur_etf, -strategy_total_value)  # 卖出需要预留给ETF轮动的资金
				if o:
					stock_show = f"{cur_etf} {get_stock_name(cur_etf)[:8]}: ".ljust(20)
					log.info(f"🚛🚛🚛🚛🚛 ETF反弹预留资金转移 {stock_show}  "
					         f"卖价{o.price:<7.2f}  "
					         f"成本{o.avg_cost:<7.2f}   "
					         f"卖量{o.amount:<7}   "
					         f"盈亏{(o.price - o.avg_cost) * o.amount:.2f}"
					         f"( {(o.price - o.avg_cost) / o.avg_cost * 100:.2f}% )")
		g.portfolio_value_proportion[2] -= g.strategy_ETF_2000_proportion
		g.portfolio_value_proportion[1] = g.strategy_ETF_2000_proportion
		g.strategy_ETF_2000_proportion_reset = True  # 拨正原始比例

""" ====================== 特殊函数 ====================== """

# def track_time(func):
#     """
#     装饰器：跟踪函数的运行时间（精确到毫秒）
#     自动打印函数名、开始时间（含毫秒）、结束时间（含毫秒）、耗时（毫秒，保留3位小数）
#     """
#     @wraps(func)  # 保留原函数的元信息（如函数名）
#     def wrapper(*args, **kwargs):
#         # 记录开始时间（微秒级时间戳）
#         start_timestamp = time.time()
#         # 解析开始时间（时分秒.毫秒）
#         start_struct = time.localtime(start_timestamp)
#         start_sec = time.strftime("%H:%M:%S", start_struct)
#         start_ms = int((start_timestamp - int(start_timestamp)) * 1000)  # 提取毫秒
#         start_str = f"{start_sec}.{start_ms:03d}"

#         # 执行原函数（保留返回值）
#         result = func(*args, **kwargs)

#         # 记录结束时间
#         end_timestamp = time.time()
#         end_struct = time.localtime(end_timestamp)
#         end_sec = time.strftime("%H:%M:%S", end_struct)
#         end_ms = int((end_timestamp - int(end_timestamp)) * 1000)
#         end_str = f"{end_sec}.{end_ms:03d}"

#         # 计算耗时（毫秒）
#         cost_ms = (end_timestamp - start_timestamp) * 1000

#         # 打印跟踪信息
#         log.warn(f"------------【{func.__name__}】运行时间：{start_str} -> {end_str}，耗时：{cost_ms:.3f} ms")

#         # 返回原函数的结果（不影响原有逻辑）
#         return result
#     return wrapper

# def after_code_changed(context):
#     pass
def after_code_changed(context):
	"""代码更新后自动调用，用于调整定时任务时间，避免重启 initialize"""
	# 仅当策略3启用时才调整
	if g.portfolio_value_proportion[2] > 0:
		# 取消原有的 strategy_3_calc 任务（10:30）
		unschedule_all()

		# 重新注册全部定时任务，与 initialize 中保持一致，仅时间修改
		run_daily(strategy_3_calc, '10:32')      # 修改为 10:32 计算
		run_daily(strategy_3_sell, '10:33')
		run_daily(strategy_3_buy, '10:34')

		if g.enable_stop_loss_by_cur_day:
			run_daily(etf_stop_loss_by_cur_day, '10:00')
		run_daily(etf_volume_check, '13:30')

		# 止损检查（10:35 保持不变）
		run_daily(take_profit_stop_loss, '10:35')
		# 收盘记录
		run_daily(make_record, '15:01')

		log.info("✅ after_code_changed: 已将 strategy_3_calc 时间调整为 10:32")
