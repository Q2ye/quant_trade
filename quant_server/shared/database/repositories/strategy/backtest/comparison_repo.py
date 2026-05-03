# shared/database/repositories/strategy/backtest/comparison_repo.py
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy import select, update, desc, delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.business_models import BacktestComparison
from shared.database.repositories.base import BaseRepository


class BacktestComparisonRepository(BaseRepository[BacktestComparison]):
	"""回测对比结果数据仓库"""

	def __init__ (self, session: AsyncSession):
		super().__init__(session, BacktestComparison)

	async def get_by_comparison_id (self, comparison_id: str) -> Optional[BacktestComparison]:
		"""根据对比ID获取对比结果"""
		query = select(self.model).where(self.model.comparison_id == comparison_id)
		result = await self.session.execute(query)
		return result.scalars().first()

	async def get_user_comparisons (self, user_id: str, skip: int = 0,
	                                limit: int = 50) -> List[BacktestComparison]:
		"""获取用户创建的对比结果"""
		query = (
			select(self.model)
			.where(self.model.created_by == user_id)
			.order_by(desc(self.model.created_at))
			.offset(skip)
			.limit(limit)
		)

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_task_comparisons (self, task_id: str) -> List[BacktestComparison]:
		"""获取包含指定任务的对比结果"""
		# 需要从JSON字段中搜索包含该task_id的记录
		query = select(self.model)
		result = await self.session.execute(query)

		comparisons = []
		for comparison in result.scalars().all():
			# 检查基准任务或对比任务列表
			if (comparison.base_task_id == task_id or
					task_id in (comparison.compared_tasks or [])):
				comparisons.append(comparison)

		return comparisons

	async def create_comparison (self, comparison_data: Dict[str, Any]) -> BacktestComparison:
		"""创建对比结果"""
		now = datetime.now()

		# 确保必要字段存在
		comparison_data.setdefault("created_at", now)

		instance = self.model(**comparison_data)
		self.session.add(instance)
		await self.session.flush()

		return instance

	async def update_comparison_results (self, comparison_id: str,
	                                     comparison_results: Dict[str, Any],
	                                     comparison_metrics: Optional[Dict[str, Any]] = None) -> bool:
		"""更新对比结果数据"""
		update_data = {
			"comparison_results": comparison_results,
			"updated_at": datetime.now()
		}

		if comparison_metrics:
			update_data["comparison_metrics"] = comparison_metrics

		stmt = (
			update(self.model)
			.where(self.model.comparison_id == comparison_id)
			.values(**update_data)
		)

		result = await self.session.execute(stmt)
		return result.rowcount > 0

	async def get_comparison_summary (self, comparison_id: str) -> Dict[str, Any]:
		"""获取对比结果摘要"""
		comparison = await self.get_by_comparison_id(comparison_id)
		if not comparison:
			return {}

		# 解析对比结果
		results = comparison.comparison_results or {}
		metrics = comparison.comparison_metrics or {}

		# 提取关键指标
		summary = {
			"comparison_id": comparison.comparison_id,
			"comparison_name": comparison.comparison_name,
			"base_task_id": comparison.base_task_id,
			"compared_task_count": len(comparison.compared_tasks or []),
			"created_at": comparison.created_at,
			"metrics_summary": self._extract_key_metrics(metrics),
			"top_performers": self._identify_top_performers(results)
		}

		return summary

	@staticmethod
	def _extract_key_metrics ( metrics: Dict[str, Any]) -> Dict[str, Any]:
		"""提取关键绩效指标"""
		key_metrics = {}

		# 常见的绩效指标
		target_metrics = [
			"total_return", "annual_return", "sharpe_ratio",
			"max_drawdown", "win_rate", "profit_factor"
		]

		for metric in target_metrics:
			if metric in metrics:
				key_metrics[metric] = metrics[metric]

		return key_metrics


	@staticmethod
	def _identify_top_performers ( results: Dict[str, Any]) -> List[Dict[str, Any]]:
		"""识别表现最好的任务"""
		if not results or "task_results" not in results:
			return []

		task_results = results["task_results"]
		if not isinstance(task_results, list):
			return []

		# 按总收益率排序
		sorted_results = sorted(
			task_results,
			key=lambda x: x.get("total_return", 0),
			reverse=True
		)

		top_performers = []
		for i, result in enumerate(sorted_results[:5]):  # 取前5名
			top_performers.append({
				"rank": i + 1,
				"task_id": result.get("task_id"),
				"total_return": result.get("total_return", 0),
				"sharpe_ratio": result.get("sharpe_ratio", 0),
				"max_drawdown": result.get("max_drawdown", 0)
			})

		return top_performers

	async def delete_old_comparisons (self, days: int = 90) -> int:
		"""删除指定天数前的对比结果"""
		from datetime import timedelta

		cutoff_date = datetime.now() - timedelta(days=days)

		stmt = (
			delete(self.model)
			.where(self.model.created_at < cutoff_date)
		)

		result = await self.session.execute(stmt) # type: ignore
		return result.rowcount or 0
