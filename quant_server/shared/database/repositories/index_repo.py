# -*- coding: utf-8 -*-
"""
指数数据仓库
位置：quant_server/shared/database/repositories/index_repo.py
职责：管理指数基础信息、行情、成分股等数据访问
"""

from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc, text, distinct
from sqlalchemy.orm import selectinload, joinedload

from quant_server.shared.database.repositories.base import BaseRepository


# 假设的指数数据模型类
class IndexBasic:
	"""指数基础信息模型"""
	__tablename__ = 'index_basic'
	pass


class IndexDaily:
	"""指数日线行情模型"""
	__tablename__ = 'index_daily'
	pass


class IndexComponent:
	"""指数成分股模型"""
	__tablename__ = 'index_components'
	pass


class IndexRepository:
	"""指数数据仓库 - 负责指数相关数据访问"""

	def __init__ (self, session: AsyncSession):
		self.session = session
		self.index_basic_repo = BaseRepository[IndexBasic](session, IndexBasic)
		self.index_daily_repo = BaseRepository[IndexDaily](session, IndexDaily)
		self.index_component_repo = BaseRepository[IndexComponent](session, IndexComponent)

	# ==================== 指数基础信息操作 ====================

	async def get_index_basic (self, index_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取指数基础信息

		Args:
			index_code: 指数代码

		Returns:
			指数基础信息或None
		"""
		query = text("""
                     SELECT index_code,
                            index_name,
                            full_name,
                            publisher,
                            base_date,
                            base_point,
                            calculation_method,
                            weighting_method,
                            component_count,
                            category
                     FROM index_basic
                     WHERE index_code = :index_code
                     LIMIT 1
		             """)

		result = await self.session.execute(query, {"index_code": index_code})
		row = result.fetchone()

		if row:
			return dict(row)

		return None

	async def search_indices (
			self,
			keyword: str,
			category: str = None,
			limit: int = 100,
			skip: int = 0
	) -> List[Dict[str, Any]]:
		"""
		搜索指数

		Args:
			keyword: 搜索关键词（可匹配代码、名称等）
			category: 指数类别过滤（可选）
			limit: 返回数量限制
			skip: 跳过数量

		Returns:
			指数列表
		"""
		conditions = ["(index_code LIKE :keyword OR index_name LIKE :keyword OR full_name LIKE :keyword)"]
		params = {
			"keyword": f"%{keyword}%",
			"limit": limit,
			"skip": skip
		}

		if category:
			conditions.append("category = :category")
			params["category"] = category

		query_text = f"""
            SELECT 
                index_code, index_name, category,
                publisher, base_date, component_count
            FROM index_basic 
            WHERE {' AND '.join(conditions)}
            ORDER BY index_code
            LIMIT :limit OFFSET :skip
        """

		result = await self.session.execute(text(query_text), params)
		rows = result.fetchall()

		return [dict(row) for row in rows]

	async def get_indices_by_category (self, category: str) -> List[Dict[str, Any]]:
		"""
		根据类别获取指数

		Args:
			category: 指数类别

		Returns:
			指数列表
		"""
		query = text("""
                     SELECT index_code,
                            index_name,
                            full_name,
                            publisher,
                            base_date,
                            component_count
                     FROM index_basic
                     WHERE category = :category
                     ORDER BY index_code
		             """)

		result = await self.session.execute(query, {"category": category})
		rows = result.fetchall()

		return [dict(row) for row in rows]

	async def get_indices_by_publisher (self, publisher: str) -> List[Dict[str, Any]]:
		"""
		根据发布机构获取指数

		Args:
			publisher: 发布机构

		Returns:
			指数列表
		"""
		query = text("""
                     SELECT index_code,
                            index_name,
                            category,
                            base_date,
                            component_count
                     FROM index_basic
                     WHERE publisher = :publisher
                     ORDER BY base_date DESC
		             """)

		result = await self.session.execute(query, {"publisher": publisher})
		rows = result.fetchall()

		return [dict(row) for row in rows]

	async def create_index_basic (self, index_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		创建指数基础信息

		Args:
			index_data: 指数数据

		Returns:
			创建结果
		"""
		query = text("""
                     INSERT INTO index_basic
                         (index_code, index_name, full_name, publisher, base_date, base_point)
                     VALUES (:index_code, :index_name, :full_name, :publisher, :base_date, :base_point)
                     RETURNING index_code
		             """)

		result = await self.session.execute(query, index_data)
		row = result.fetchone()

		if row:
			return {"index_code": row[0], "status": "created"}

		return {"status": "failed"}

	# ==================== 指数行情操作 ====================

	async def get_index_daily (
			self,
			index_code: str,
			trade_date: date
	) -> Optional[Dict[str, Any]]:
		"""
		获取指数日线行情

		Args:
			index_code: 指数代码
			trade_date: 交易日期

		Returns:
			指数日线行情或None
		"""
		query = text("""
                     SELECT trade_date,
                            open,
                            high,
                            low,
                            close,
                            pre_close,
                            change,
                            pct_chg,
                            volume,
                            amount,
                            turnover_rate
                     FROM index_daily
                     WHERE index_code = :index_code
                       AND trade_date = :trade_date
                     LIMIT 1
		             """)

		result = await self.session.execute(
			query,
			{"index_code": index_code, "trade_date": trade_date}
		)

		row = result.fetchone()
		if row:
			return dict(row)

		return None

	async def get_index_daily_in_range (
			self,
			index_code: str,
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		获取指定时间范围内的指数日线行情

		Args:
			index_code: 指数代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			指数日线行情列表
		"""
		query = text("""
                     SELECT trade_date,
                            open,
                            high,
                            low,
                            close,
                            change,
                            pct_chg,
                            volume,
                            amount
                     FROM index_daily
                     WHERE index_code = :index_code
                       AND trade_date >= :start_date
                       AND trade_date <= :end_date
                     ORDER BY trade_date
		             """)

		result = await self.session.execute(
			query,
			{
				"index_code": index_code,
				"start_date": start_date,
				"end_date": end_date
			}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	async def get_latest_index_daily (self, index_code: str) -> Optional[Dict[str, Any]]:
		"""
		获取最新指数日线行情

		Args:
			index_code: 指数代码

		Returns:
			最新指数日线行情或None
		"""
		query = text("""
                     SELECT trade_date,
                            open,
                            high,
                            low,
                            close,
                            change,
                            pct_chg,
                            volume,
                            amount
                     FROM index_daily
                     WHERE index_code = :index_code
                     ORDER BY trade_date DESC
                     LIMIT 1
		             """)

		result = await self.session.execute(query, {"index_code": index_code})
		row = result.fetchone()

		if row:
			return dict(row)

		return None

	async def create_index_daily (self, daily_data: Dict[str, Any]) -> Dict[str, Any]:
		"""
		创建指数日线行情记录

		Args:
			daily_data: 日线行情数据

		Returns:
			创建结果
		"""
		query = text("""
                     INSERT INTO index_daily
                         (index_code, trade_date, open, high, low, close, volume, amount)
                     VALUES (:index_code, :trade_date, :open, :high, :low, :close, :volume, :amount)
                     ON CONFLICT (index_code, trade_date)
                         DO UPDATE SET open       = EXCLUDED.open,
                                       high       = EXCLUDED.high,
                                       low        = EXCLUDED.low,
                                       close      = EXCLUDED.close,
                                       volume     = EXCLUDED.volume,
                                       amount     = EXCLUDED.amount,
                                       updated_at = NOW()
                     RETURNING id
		             """)

		result = await self.session.execute(query, daily_data)
		row = result.fetchone()

		if row:
			return {"id": row[0], "index_code": daily_data["index_code"], "trade_date": daily_data["trade_date"]}

		return {"status": "failed"}

	# ==================== 指数成分股操作 ====================

	async def get_index_components (
			self,
			index_code: str,
			effective_date: date = None
	) -> List[Dict[str, Any]]:
		"""
		获取指数成分股

		Args:
			index_code: 指数代码
			effective_date: 生效日期（可选，默认最新）

		Returns:
			指数成分股列表
		"""
		if effective_date is None:
			# 获取最新的生效日期
			query = text("""
                         SELECT MAX(effective_date) as latest_date
                         FROM index_components
                         WHERE index_code = :index_code
			             """)

			result = await self.session.execute(query, {"index_code": index_code})
			row = result.fetchone()

			if not row or not row.latest_date:
				return []

			effective_date = row.latest_date

		query = text("""
                     SELECT component_code,
                            component_name,
                            industry,
                            weight,
                            shares,
                            market_value,
                            is_new,
                            change_type
                     FROM index_components
                     WHERE index_code = :index_code
                       AND effective_date = :effective_date
                     ORDER BY weight DESC
		             """)

		result = await self.session.execute(
			query,
			{"index_code": index_code, "effective_date": effective_date}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	async def get_index_history_components (
			self,
			index_code: str,
			start_date: date,
			end_date: date
	) -> Dict[date, List[Dict[str, Any]]]:
		"""
		获取指数历史成分股

		Args:
			index_code: 指数代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			按日期分组的成分股字典
		"""
		query = text("""
                     SELECT effective_date,
                            component_code,
                            component_name,
                            weight
                     FROM index_components
                     WHERE index_code = :index_code
                       AND effective_date >= :start_date
                       AND effective_date <= :end_date
                     ORDER BY effective_date DESC, weight DESC
		             """)

		result = await self.session.execute(
			query,
			{
				"index_code": index_code,
				"start_date": start_date,
				"end_date": end_date
			}
		)

		rows = result.fetchall()

		# 按日期分组
		components_by_date = {}
		for row in rows:
			date_key = row.effective_date
			if date_key not in components_by_date:
				components_by_date[date_key] = []

			components_by_date[date_key].append({
				"component_code": row.component_code,
				"component_name": row.component_name,
				"weight": row.weight
			})

		return components_by_date

	async def get_indices_by_component (
			self,
			component_code: str,
			effective_date: date = None
	) -> List[Dict[str, Any]]:
		"""
		获取包含某成分股的指数

		Args:
			component_code: 成分股代码
			effective_date: 生效日期（可选，默认最新）

		Returns:
			指数列表
		"""
		if effective_date is None:
			# 获取最新的生效日期
			query = text("""
                         SELECT MAX(effective_date) as latest_date
                         FROM index_components
                         WHERE component_code = :component_code
			             """)

			result = await self.session.execute(query, {"component_code": component_code})
			row = result.fetchone()

			if not row or not row.latest_date:
				return []

			effective_date = row.latest_date

		query = text("""
                     SELECT ic.index_code,
                            ib.index_name,
                            ib.category,
                            ic.weight,
                            ic.shares,
                            ic.market_value
                     FROM index_components ic
                              JOIN index_basic ib ON ic.index_code = ib.index_code
                     WHERE ic.component_code = :component_code
                       AND ic.effective_date = :effective_date
                     ORDER BY ic.weight DESC
		             """)

		result = await self.session.execute(
			query,
			{"component_code": component_code, "effective_date": effective_date}
		)

		rows = result.fetchall()
		return [dict(row) for row in rows]

	async def get_component_changes (
			self,
			index_code: str,
			old_date: date,
			new_date: date
	) -> Dict[str, List[Dict[str, Any]]]:
		"""
		获取成分股变动

		Args:
			index_code: 指数代码
			old_date: 旧日期
			new_date: 新日期

		Returns:
			成分股变动信息
		"""
		# 获取旧日期成分股
		old_components = await self.get_index_components(index_code, old_date)
		new_components = await self.get_index_components(index_code, new_date)

		if not old_components or not new_components:
			return {"error": "成分股数据不足"}

		# 转换为集合以便比较
		old_codes = {comp["component_code"] for comp in old_components}
		new_codes = {comp["component_code"] for comp in new_components}

		# 新增成分股
		added_codes = new_codes - old_codes
		added_components = [comp for comp in new_components if comp["component_code"] in added_codes]

		# 删除成分股
		removed_codes = old_codes - new_codes
		removed_components = [comp for comp in old_components if comp["component_code"] in removed_codes]

		# 权重变化
		weight_changes = []
		for new_comp in new_components:
			if new_comp["component_code"] in old_codes:
				old_comp = next((c for c in old_components if c["component_code"] == new_comp["component_code"]), None)
				if old_comp:
					weight_change = new_comp["weight"] - old_comp["weight"]
					if abs(weight_change) > 0.001:  # 只记录显著变化
						weight_changes.append({
							"component_code": new_comp["component_code"],
							"component_name": new_comp["component_name"],
							"old_weight": old_comp["weight"],
							"new_weight": new_comp["weight"],
							"weight_change": weight_change
						})

		return {
			"index_code": index_code,
			"old_date": old_date,
			"new_date": new_date,
			"added_components": added_components,
			"removed_components": removed_components,
			"weight_changes": weight_changes,
			"summary": {
				"old_count": len(old_components),
				"new_count": len(new_components),
				"added_count": len(added_components),
				"removed_count": len(removed_components),
				"change_ratio": (len(added_components) + len(removed_components)) / len(
					old_components) if old_components else 0
			}
		}

	# ==================== 指数分析操作 ====================

	async def analyze_index_performance (
			self,
			index_code: str,
			start_date: date,
			end_date: date
	) -> Dict[str, Any]:
		"""
		分析指数表现

		Args:
			index_code: 指数代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			指数表现分析
		"""
		# 获取指数行情数据
		daily_data = await self.get_index_daily_in_range(index_code, start_date, end_date)

		if not daily_data:
			return {"error": "没有找到行情数据"}

		# 获取指数基础信息
		index_info = await self.get_index_basic(index_code)

		# 计算收益
		first_close = daily_data[0]["close"]
		last_close = daily_data[-1]["close"]
		total_return = (last_close - first_close) / first_close

		# 计算日收益
		daily_returns = []
		for i in range(1, len(daily_data)):
			prev_close = daily_data[i - 1]["close"]
			curr_close = daily_data[i]["close"]
			daily_return = (curr_close - prev_close) / prev_close
			daily_returns.append(daily_return)

		# 计算统计指标
		import statistics
		if daily_returns:
			avg_return = statistics.mean(daily_returns)
			volatility = statistics.stdev(daily_returns) * (252 ** 0.5)  # 年化波动率
			sharpe_ratio = (avg_return * 252) / volatility if volatility != 0 else 0
		else:
			avg_return = 0
			volatility = 0
			sharpe_ratio = 0

		# 计算最大回撤
		max_drawdown = 0
		peak = first_close
		for daily in daily_data:
			current_close = daily["close"]
			if current_close > peak:
				peak = current_close
			drawdown = (peak - current_close) / peak
			if drawdown > max_drawdown:
				max_drawdown = drawdown

		# 获取最新成分股
		latest_components = await self.get_index_components(index_code)

		# 行业分布
		industry_distribution = {}
		if latest_components:
			for component in latest_components:
				industry = component.get("industry", "未知")
				weight = component.get("weight", 0)
				if industry not in industry_distribution:
					industry_distribution[industry] = 0
				industry_distribution[industry] += weight

		# 成分股集中度
		if latest_components:
			top_10_weight = sum(c["weight"] for c in latest_components[:10])
			concentration = top_10_weight / sum(c["weight"] for c in latest_components) if latest_components else 0
		else:
			concentration = 0

		return {
			"index_info": index_info,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"days": len(daily_data)
			},
			"performance_metrics": {
				"total_return": total_return,
				"annualized_return": total_return * (252 / len(daily_data)) if len(daily_data) > 0 else 0,
				"volatility": volatility,
				"sharpe_ratio": sharpe_ratio,
				"max_drawdown": max_drawdown,
				"average_daily_return": avg_return
			},
			"component_analysis": {
				"component_count": len(latest_components) if latest_components else 0,
				"industry_distribution": industry_distribution,
				"concentration_ratio": concentration,
				"top_components": latest_components[:10] if latest_components else []
			},
			"market_characteristics": {
				"average_volume": statistics.mean([d.get("volume", 0) for d in daily_data]) if daily_data else 0,
				"average_amount": statistics.mean([d.get("amount", 0) for d in daily_data]) if daily_data else 0,
				"average_turnover": statistics.mean(
					[d.get("turnover_rate", 0) for d in daily_data]) if daily_data else 0
			}
		}

	async def compare_indices_performance (
			self,
			index_codes: List[str],
			start_date: date,
			end_date: date
	) -> List[Dict[str, Any]]:
		"""
		比较多个指数的表现

		Args:
			index_codes: 指数代码列表
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			指数比较结果
		"""
		comparison_results = []

		for index_code in index_codes:
			# 获取行情数据
			daily_data = await self.get_index_daily_in_range(index_code, start_date, end_date)

			if not daily_data:
				continue

			# 计算收益
			first_close = daily_data[0]["close"]
			last_close = daily_data[-1]["close"]
			total_return = (last_close - first_close) / first_close

			# 获取指数信息
			index_info = await self.get_index_basic(index_code)

			comparison_results.append({
				"index_code": index_code,
				"index_name": index_info.get("index_name", "未知") if index_info else "未知",
				"category": index_info.get("category", "未知") if index_info else "未知",
				"publisher": index_info.get("publisher", "未知") if index_info else "未知",
				"total_return": total_return,
				"annualized_return": total_return * (252 / len(daily_data)) if len(daily_data) > 0 else 0,
				"start_close": first_close,
				"end_close": last_close,
				"data_points": len(daily_data)
			})

		# 按总收益排序
		comparison_results.sort(key=lambda x: x["total_return"], reverse=True)

		return comparison_results

	async def calculate_index_correlation (
			self,
			index_code1: str,
			index_code2: str,
			start_date: date,
			end_date: date
	) -> Optional[Dict[str, Any]]:
		"""
		计算两个指数的相关性

		Args:
			index_code1: 第一个指数代码
			index_code2: 第二个指数代码
			start_date: 开始日期
			end_date: 结束日期

		Returns:
			相关性分析结果
		"""
		# 获取两个指数的日收益
		daily1 = await self.get_index_daily_in_range(index_code1, start_date, end_date)
		daily2 = await self.get_index_daily_in_range(index_code2, start_date, end_date)

		if not daily1 or not daily2:
			return None

		# 确保日期对齐
		date_to_return1 = {
			d["trade_date"]: (d["close"] - d.get("pre_close", d["close"])) / d.get("pre_close", d["close"]) for d in
			daily1 if d.get("pre_close")}
		date_to_return2 = {
			d["trade_date"]: (d["close"] - d.get("pre_close", d["close"])) / d.get("pre_close", d["close"]) for d in
			daily2 if d.get("pre_close")}

		# 找到共同日期
		common_dates = set(date_to_return1.keys()) & set(date_to_return2.keys())

		if len(common_dates) < 10:
			return None

		# 提取共同日期的收益
		returns1 = [date_to_return1[date] for date in sorted(common_dates)]
		returns2 = [date_to_return2[date] for date in sorted(common_dates)]

		# 计算相关性
		import statistics
		try:
			correlation = statistics.correlation(returns1, returns2)
		except:
			correlation = 0

		# 计算Beta
		if statistics.stdev(returns2) != 0:
			beta = statistics.covariance(returns1, returns2) / (statistics.stdev(returns2) ** 2)
		else:
			beta = 0

		# 计算Alpha (假设无风险收益为0)
		alpha = statistics.mean(returns1) - beta * statistics.mean(returns2)

		return {
			"index1": index_code1,
			"index2": index_code2,
			"analysis_period": {
				"start_date": start_date,
				"end_date": end_date,
				"common_days": len(common_dates)
			},
			"correlation_metrics": {
				"correlation_coefficient": correlation,
				"beta": beta,
				"alpha": alpha,
				"r_squared": correlation ** 2
			},
			"return_statistics": {
				"index1_mean_return": statistics.mean(returns1),
				"index2_mean_return": statistics.mean(returns2),
				"index1_volatility": statistics.stdev(returns1) * (252 ** 0.5),
				"index2_volatility": statistics.stdev(returns2) * (252 ** 0.5)
			}
		}

	# ==================== 批量操作 ====================

	async def batch_create_index_daily (self, daily_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""
		批量创建指数日线行情记录

		Args:
			daily_data_list: 日线行情数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for daily_data in daily_data_list:
			result = await self.create_index_daily(daily_data)
			results.append(result)

		return results

	async def batch_create_index_components (
			self,
			components_data_list: List[Dict[str, Any]]
	) -> List[Dict[str, Any]]:
		"""
		批量创建指数成分股记录

		Args:
			components_data_list: 成分股数据列表

		Returns:
			创建结果列表
		"""
		results = []

		for data in components_data_list:
			query = text("""
                         INSERT INTO index_components
                             (index_code, effective_date, component_code, component_name, weight)
                         VALUES (:index_code, :effective_date, :component_code, :component_name, :weight)
                         ON CONFLICT (index_code, effective_date, component_code)
                             DO UPDATE SET weight     = EXCLUDED.weight,
                                           updated_at = NOW()
                         RETURNING id
			             """)

			result = await self.session.execute(query, data)
			row = result.fetchone()
			if row:
				results.append({
					"id": row[0],
					"index_code": data["index_code"],
					"effective_date": data["effective_date"],
					"component_code": data["component_code"]
				})

		return results

	async def batch_upsert_index_basics (self, index_data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
		"""
		批量插入或更新指数基础信息

		Args:
			index_data_list: 指数数据列表

		Returns:
			更新结果列表
		"""
		results = []

		for data in index_data_list:
			query = text("""
                         INSERT INTO index_basic
                             (index_code, index_name, publisher, base_date, base_point)
                         VALUES (:index_code, :index_name, :publisher, :base_date, :base_point)
                         ON CONFLICT (index_code)
                             DO UPDATE SET index_name = EXCLUDED.index_name,
                                           publisher  = EXCLUDED.publisher,
                                           updated_at = NOW()
                         RETURNING index_code
			             """)

			result = await self.session.execute(query, data)
			row = result.fetchone()
			if row:
				results.append({"index_code": row[0], "status": "upserted"})

		return results