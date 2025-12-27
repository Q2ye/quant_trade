# data_sync/services/clean_service.py
"""
数据清洗服务 - 负责数据清洗和验证
职责分离：数据清洗作为独立模块，可以在同步过程中或同步后调用
"""
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def clean_daily_data (data: List[Dict], **kwargs) -> List[Dict]:
	"""清洗日线数据"""
	cleaned_data = []

	for item in data:
		try:
			# 1. 必填字段检查
			required_fields = ['ts_code', 'trade_date', 'open', 'high', 'low', 'close', 'vol']
			if not all(item.get(field) is not None for field in required_fields):
				logger.warning(f"日线数据缺少必填字段: {item}")
				continue

			# 2. 价格合理性检查
			open_price = float(item['open'])
			high_price = float(item['high'])
			low_price = float(item['low'])
			close_price = float(item['close'])

			# 价格必须为正数
			if any(price <= 0 for price in [open_price, high_price, low_price, close_price]):
				logger.warning(f"日线价格非正数: {item}")
				continue

			# 价格关系检查：high >= low, high >= open, high >= close, low <= open, low <= close
			if not (high_price >= low_price and
			        high_price >= open_price and
			        high_price >= close_price and
			        low_price <= open_price and
			        low_price <= close_price):
				logger.warning(f"日线价格关系不合理: {item}")
				continue

			# 3. 交易量检查
			volume = float(item['vol'])
			if volume < 0:
				logger.warning(f"交易量为负: {volume}")
				continue

			# 4. 涨跌幅限制检查（可选）
			if 'pre_close' in item:
				pre_close = float(item['pre_close'])
				if pre_close > 0:
					daily_return = (close_price - pre_close) / pre_close
					# A股涨跌幅限制通常为±10%
					if abs(daily_return) > 0.3:  # 放宽限制到30%以包含特殊情况
						logger.warning(f"涨跌幅异常: {daily_return:.2%}, 数据: {item}")
					# 可以选择记录但不移除

			# 5. 数据转换
			cleaned_item = {
				'ts_code': str(item['ts_code']),
				'trade_date': str(item['trade_date']),
				'open': open_price,
				'high': high_price,
				'low': low_price,
				'close': close_price,
				'vol': volume,
				'amount': float(item.get('amount', 0)) if item.get('amount') else 0.0,
			}

			cleaned_data.append(cleaned_item)

		except (ValueError, TypeError) as e:
			logger.warning(f"日线数据清洗失败: {e}, 数据: {item}")
			continue

	return cleaned_data


class DataCleanService:
	"""数据清洗服务"""

	def __init__ (self, config: Optional[Dict[str, Any]] = None):
		"""初始化清洗服务"""
		self.config = config or {}
		self._clean_rules = self._init_clean_rules()

	def _init_clean_rules (self) -> Dict[str, Callable]:
		"""初始化清洗规则"""
		return {
			"stock_basic": self.clean_stock_basic,
			"daily": clean_daily_data,
			"weekly": self.clean_weekly_data,
			"monthly": self.clean_monthly_data,
			"adj_factor": self.clean_adj_factor,
			"daily_basic": self.clean_daily_basic,
			"moneyflow": self.clean_moneyflow,
			"daily_limit": self.clean_daily_limit,
			"fund_basic": self.clean_fund_basic,
			"fund_daily": self.clean_fund_daily,
			"index_weight": self.clean_index_weight,
		}

	def clean_data (self, data_type: str, data: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
		"""
		通用数据清洗入口

		Args:
			data_type: 数据类型
			data: 原始数据列表
			**kwargs: 清洗参数

		Returns:
			清洗后的数据列表
		"""
		if not data:
			logger.warning(f"{data_type}数据为空，跳过清洗")
			return []

		logger.info(f"开始清洗{data_type}数据，原始数据量: {len(data)}")

		# 获取清洗函数
		clean_func = self._clean_rules.get(data_type)
		if not clean_func:
			logger.warning(f"未找到{data_type}的清洗规则，使用默认清洗")
			return self._default_clean(data, data_type, **kwargs)

		try:
			# 执行清洗
			cleaned_data = clean_func(data, **kwargs)

			# 记录清洗统计
			original_count = len(data)
			cleaned_count = len(cleaned_data)
			removed_count = original_count - cleaned_count

			if removed_count > 0:
				logger.info(f"{data_type}数据清洗完成: 移除{removed_count}条无效记录，保留{cleaned_count}条")
			else:
				logger.info(f"{data_type}数据清洗完成: 全部{cleaned_count}条记录有效")

			return cleaned_data

		except Exception as e:
			logger.error(f"{data_type}数据清洗失败: {str(e)}")
			# 清洗失败时返回原始数据
			return data

	def _default_clean (self, data: List[Dict], data_type: str, **kwargs) -> List[Dict]:
		"""默认清洗规则"""
		cleaned_data = []

		for item in data:
			try:
				# 1. 移除空记录
				if not item:
					continue

				# 2. 移除所有值都为None的记录
				if all(v is None for v in item.values()):
					continue

				# 3. 基本类型转换
				cleaned_item = {}
				for key, value in item.items():
					# 处理空值
					if value is None:
						cleaned_item[key] = None
						continue

					# 数值类型转换
					if isinstance(value, (int, float, np.integer, np.floating)):
						cleaned_item[key] = float(value)
					else:
						cleaned_item[key] = str(value).strip() if isinstance(value, str) else value

				cleaned_data.append(cleaned_item)

			except Exception as e:
				logger.warning(f"数据项清洗失败: {e}, 数据: {item}")
				continue

		return cleaned_data

	def clean_stock_basic (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗股票基本信息"""
		cleaned_data = []

		for item in data:
			try:
				# 1. 必填字段检查
				required_fields = ['ts_code', 'symbol', 'name']
				if not all(item.get(field) for field in required_fields):
					logger.warning(f"股票基本信息缺少必填字段: {item}")
					continue

				# 2. 代码格式验证
				ts_code = str(item['ts_code'])
				if not (ts_code.endswith('.SZ') or ts_code.endswith('.SH')):
					logger.warning(f"股票代码格式错误: {ts_code}")
					continue

				# 3. 上市日期验证
				list_date = item.get('list_date')
				if list_date:
					try:
						# 检查日期格式是否为YYYYMMDD
						if len(list_date) != 8:
							logger.warning(f"上市日期格式错误: {list_date}")
							continue

						# 检查日期是否合理（不超过当前日期）
						list_datetime = datetime.strptime(list_date, '%Y%m%d')
						if list_datetime > datetime.now():
							logger.warning(f"上市日期在未来: {list_date}")
							continue
					except ValueError:
						logger.warning(f"上市日期解析失败: {list_date}")
						continue

				# 4. 数据类型转换
				cleaned_item = {
					'ts_code': ts_code,
					'symbol': str(item['symbol']),
					'name': str(item['name']).strip(),
					'area': str(item.get('area', '')).strip() if item.get('area') else None,
					'industry': str(item.get('industry', '')).strip() if item.get('industry') else None,
					'list_date': list_date,
					'market': str(item.get('market', '')).strip() if item.get('market') else None,
				}

				cleaned_data.append(cleaned_item)

			except Exception as e:
				logger.warning(f"股票基本信息清洗失败: {e}, 数据: {item}")
				continue

		return cleaned_data

	def clean_weekly_data (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗周线数据"""
		return self._clean_period_data(data, 'weekly')

	def clean_monthly_data (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗月线数据"""
		return self._clean_period_data(data, 'monthly')

	def _clean_period_data (self, data: List[Dict], period: str) -> List[Dict]:
		"""清洗周期数据（周线、月线）"""
		cleaned_data = []

		for item in data:
			try:
				# 必填字段检查
				required_fields = ['ts_code', 'trade_date', 'close']
				if not all(item.get(field) is not None for field in required_fields):
					logger.warning(f"{period}数据缺少必填字段: {item}")
					continue

				# 价格检查
				close_price = float(item['close'])
				if close_price <= 0:
					logger.warning(f"{period}收盘价非正数: {close_price}")
					continue

				# 数据转换
				cleaned_item = {
					'ts_code': str(item['ts_code']),
					'trade_date': str(item['trade_date']),
					'open': float(item.get('open', close_price)) if item.get('open') else close_price,
					'high': float(item.get('high', close_price)) if item.get('high') else close_price,
					'low': float(item.get('low', close_price)) if item.get('low') else close_price,
					'close': close_price,
					'vol': float(item.get('vol', 0)) if item.get('vol') else 0.0,
					'amount': float(item.get('amount', 0)) if item.get('amount') else 0.0,
				}

				cleaned_data.append(cleaned_item)

			except (ValueError, TypeError) as e:
				logger.warning(f"{period}数据清洗失败: {e}, 数据: {item}")
				continue

		return cleaned_data

	def clean_adj_factor (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗复权因子数据"""
		cleaned_data = []

		for item in data:
			try:
				# 必填字段检查
				if not all(item.get(field) for field in ['ts_code', 'trade_date', 'adj_factor']):
					logger.warning(f"复权因子数据缺少必填字段: {item}")
					continue

				# 复权因子检查（通常为正数）
				adj_factor = float(item['adj_factor'])
				if adj_factor <= 0:
					logger.warning(f"复权因子非正数: {adj_factor}")
					continue

				cleaned_item = {
					'ts_code': str(item['ts_code']),
					'trade_date': str(item['trade_date']),
					'adj_factor': adj_factor,
				}

				cleaned_data.append(cleaned_item)

			except (ValueError, TypeError) as e:
				logger.warning(f"复权因子数据清洗失败: {e}, 数据: {item}")
				continue

		return cleaned_data

	def clean_daily_basic (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗每日指标数据"""
		cleaned_data = []

		for item in data:
			try:
				# 必填字段检查
				if not all(item.get(field) for field in ['ts_code', 'trade_date']):
					logger.warning(f"每日指标数据缺少必填字段: {item}")
					continue

				cleaned_item = {
					'ts_code': str(item['ts_code']),
					'trade_date': str(item['trade_date']),
				}

				# 处理可选数值字段
				numeric_fields = ['pe', 'pb', 'ps', 'total_share', 'float_share', 'total_mv', 'circ_mv']
				for field in numeric_fields:
					if field in item and item[field] is not None:
						try:
							cleaned_item[field] = float(item[field])
						except (ValueError, TypeError):
							cleaned_item[field] = None

				cleaned_data.append(cleaned_item)

			except Exception as e:
				logger.warning(f"每日指标数据清洗失败: {e}, 数据: {item}")
				continue

		return cleaned_data

	def clean_moneyflow (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗资金流向数据"""
		cleaned_data = []

		for item in data:
			try:
				# 必填字段检查
				if not all(item.get(field) for field in ['ts_code', 'trade_date']):
					logger.warning(f"资金流向数据缺少必填字段: {item}")
					continue

				cleaned_item = {
					'ts_code': str(item['ts_code']),
					'trade_date': str(item['trade_date']),
				}

				# 处理资金流向字段
				flow_fields = ['buy_sm_vol', 'sell_sm_vol', 'buy_md_vol', 'sell_md_vol',
				               'buy_lg_vol', 'sell_lg_vol', 'buy_elg_vol', 'sell_elg_vol',
				               'net_mf_vol', 'net_mf_amount']

				for field in flow_fields:
					if field in item and item[field] is not None:
						try:
							value = float(item[field])
							# 资金流向通常为非负数
							if field.startswith('buy_') or field.startswith('sell_'):
								if value < 0:
									logger.warning(f"资金流向字段{field}为负数: {value}")
									value = abs(value)
							cleaned_item[field] = value
						except (ValueError, TypeError):
							cleaned_item[field] = 0.0

				cleaned_data.append(cleaned_item)

			except Exception as e:
				logger.warning(f"资金流向数据清洗失败: {e}, 数据: {item}")
				continue

		return cleaned_data

	def clean_daily_limit (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗涨跌停价格数据"""
		cleaned_data = []

		for item in data:
			try:
				# 必填字段检查
				required_fields = ['ts_code', 'trade_date', 'pre_close', 'up_limit', 'down_limit']
				if not all(item.get(field) is not None for field in required_fields):
					logger.warning(f"涨跌停价格数据缺少必填字段: {item}")
					continue

				# 价格检查
				pre_close = float(item['pre_close'])
				up_limit = float(item['up_limit'])
				down_limit = float(item['down_limit'])

				if pre_close <= 0 or up_limit <= 0 or down_limit <= 0:
					logger.warning(f"涨跌停价格非正数: pre_close={pre_close}, up={up_limit}, down={down_limit}")
					continue

				# 涨跌停价格合理性检查
				if up_limit <= down_limit:
					logger.warning(f"涨停价不大于跌停价: up={up_limit}, down={down_limit}")
					continue

				# 涨跌停价格与前收盘价关系检查
				if not (down_limit <= pre_close <= up_limit):
					logger.warning(f"前收盘价不在涨跌停范围内: pre_close={pre_close}, up={up_limit}, down={down_limit}")
					continue

				cleaned_item = {
					'ts_code': str(item['ts_code']),
					'trade_date': str(item['trade_date']),
					'pre_close': pre_close,
					'up_limit': up_limit,
					'down_limit': down_limit,
				}

				cleaned_data.append(cleaned_item)

			except (ValueError, TypeError) as e:
				logger.warning(f"涨跌停价格数据清洗失败: {e}, 数据: {item}")
				continue

		return cleaned_data

	def clean_fund_basic (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗基金基本信息"""
		return self.clean_stock_basic(data)  # 复用股票基本信息清洗

	def clean_fund_daily (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗基金日线数据"""
		return clean_daily_data(data)  # 复用日线数据清洗

	def clean_index_weight (self, data: List[Dict], **kwargs) -> List[Dict]:
		"""清洗指数成分股数据"""
		cleaned_data = []

		for item in data:
			try:
				# 必填字段检查
				required_fields = ['index_code', 'con_code', 'trade_date', 'weight']
				if not all(item.get(field) is not None for field in required_fields):
					logger.warning(f"指数成分股数据缺少必填字段: {item}")
					continue

				# 权重检查（0-100之间）
				weight = float(item['weight'])
				if not (0 <= weight <= 100):
					logger.warning(f"指数权重超出范围: {weight}")
					continue

				cleaned_item = {
					'index_code': str(item['index_code']),
					'con_code': str(item['con_code']),
					'trade_date': str(item['trade_date']),
					'weight': weight,
				}

				cleaned_data.append(cleaned_item)

			except (ValueError, TypeError) as e:
				logger.warning(f"指数成分股数据清洗失败: {e}, 数据: {item}")
				continue

		return cleaned_data

	def deduplicate_data (self, data: List[Dict], key_fields: List[str]) -> List[Dict]:
		"""
		数据去重

		Args:
			data: 数据列表
			key_fields: 用于去重的关键字段

		Returns:
			去重后的数据
		"""
		if not data or not key_fields:
			return data

		seen = set()
		deduplicated_data = []

		for item in data:
			# 生成去重键
			try:
				key = tuple(str(item.get(field, '')) for field in key_fields)
			except Exception:
				continue

			if key not in seen:
				seen.add(key)
				deduplicated_data.append(item)

		logger.info(f"数据去重完成: 原始{len(data)}条 -> 去重后{len(deduplicated_data)}条")
		return deduplicated_data