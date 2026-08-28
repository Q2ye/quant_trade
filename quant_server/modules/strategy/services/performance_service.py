# -*- coding: utf-8 -*-
"""
策略每日绩效计算服务（v3.3 新增）

无状态纯计算服务，负责：
1. 获取活跃策略列表
2. 计算单策略每日绩效指标
3. 写入 strategy_daily_performance 表
"""
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class PerformanceService:
    """策略每日绩效计算服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_strategies(self) -> list:
        """获取所有运行中/暂停中的策略"""
        from shared.database.repositories.strategy.management.strategy_repo import (
            StrategyRepository,
        )
        repo = StrategyRepository(self.session)
        running = await repo.get_by_status("running")
        paused = await repo.get_by_status("paused")
        return (running or []) + (paused or [])

    async def _get_strategy_assets(self, strategy_id: str) -> float:
        """策略当日资产基准 = 分配资金（strategies.allocated_capital）。

        修复 2026-08（Bug2）：此前用全账户 SUM(total_balance) 当作每个策略的
        total_assets，导致所有策略收益趋同。共享账户 + CapitalAllocator 架构下，
        策略资产以其分配资金为基准（rebalance 每日同步 allocated_capital =
        账户总资产 × 权重），而非全局账户合计。

        注意：allocated_capital 仅在 rebalance 触发时更新（阈值 1000 元），存在
        步进式滞后；精确的 per-strategy 每日盈亏需后续补 per-strategy 净值追踪。
        """
        try:
            from sqlalchemy import text
            r = await self.session.execute(text(
                "SELECT COALESCE(allocated_capital, 0) FROM strategies WHERE id = :sid"
            ), {"sid": strategy_id})
            val = r.scalar()
            return float(val) if val else 0.0
        except Exception as e:
            logger.warning("查询策略分配资金失败: %s", str(e))
            return 0.0

    async def _get_active_run(self, strategy_id: str):
        """获取策略当前的 active run"""
        from shared.database.repositories.strategy.management.strategy_run_repo import (
            StrategyRunRepository,
        )
        repo = StrategyRunRepository(self.session)
        runs = await repo.get_active_runs()
        for r in (runs or []):
            if getattr(r, "strategy_id", "") == strategy_id:
                return r
        return None

    async def _get_previous_performance(self, strategy_id: str):
        """获取该策略最近一条绩效记录"""
        from shared.database.repositories.account.asset.strategy_daily_performance_repo import (
            StrategyDailyPerformanceRepository,
        )
        repo = StrategyDailyPerformanceRepository(self.session)
        # days 回看窗口加长到 10 天：跨周末/节假日结算间隔后仍能取到上一有效快照，
        # 避免 prev=None 退化回 run_initial 导致 daily_return 与 total_return 恒相等
        records = await repo.get_latest_performance(strategy_id, days=10)
        return records[0] if records else None

    async def _get_run_daily_returns(self, strategy_id: str, run_id: Optional[str]) -> List[float]:
        """获取指定 run 的历史日收益序列"""
        from shared.database.repositories.account.asset.strategy_daily_performance_repo import (
            StrategyDailyPerformanceRepository,
        )
        repo = StrategyDailyPerformanceRepository(self.session)
        records = await repo.get_latest_performance(strategy_id, days=365)
        if run_id:
            records = [r for r in records if getattr(r, "strategy_run_id", "") == run_id]
        return [float(r.daily_return) for r in records if getattr(r, "daily_return", None) is not None]

    async def calculate_daily_performance(
        self, strategy_id: str, trade_date: date, total_assets: float = None,
    ) -> Optional[Dict]:
        """
        计算单个策略的当日绩效。

        Args:
            strategy_id: 策略ID
            trade_date: 交易日期
            total_assets: 当日总资产（外部传入，省略时默认为0）

        Returns:
            绩效记录 dict or None
        """
        try:
            # 修复 2026-08（A30 + Bug2）：total_assets 未传时取该策略分配资金，
            # 而非全账户总资产合计（Bug2：后者致所有策略收益趋同）
            if total_assets is None:
                total_assets = await self._get_strategy_assets(strategy_id)
            if total_assets <= 0:
                logger.info("策略 %s 无有效资产数据，跳过绩效写入", strategy_id)
                return None

            prev = await self._get_previous_performance(strategy_id)
            active_run = await self._get_active_run(strategy_id)

            if prev and getattr(prev, "total_assets", None):
                prev_assets = float(prev.total_assets)
                daily_returns = await self._get_run_daily_returns(
                    strategy_id, getattr(active_run, "id", None) if active_run else None
                )
                run_initial = float(
                    getattr(active_run, "allocated_capital", prev_assets) or prev_assets
                )
            else:
                prev_assets = float(
                    getattr(active_run, "allocated_capital", total_assets)
                    if active_run else total_assets
                )
                run_initial = prev_assets if prev_assets > 0 else total_assets
                daily_returns = []

            # 计算指标
            daily_return = (
                (total_assets - prev_assets) / prev_assets if prev_assets > 0 else 0.0
            )
            total_return = (
                (total_assets - run_initial) / run_initial if run_initial > 0 else 0.0
            )

            # 最大回撤（修复 2026-08（C4）：统一负值口径，与 exposure_calculator 一致）
            peak = max(
                float(getattr(prev, "total_assets", total_assets) or total_assets),
                total_assets,
            )
            dd = (total_assets - peak) / peak if peak > 0 else 0.0
            max_dd = max(
                float(getattr(prev, "max_drawdown", 0) or 0),
                dd,
            )

            # 夏普比率
            returns = daily_returns + [daily_return]
            sharpe = None
            if len(returns) >= 5:
                arr = np.array(returns, dtype=float)
                std = float(np.std(arr, ddof=1))  # 修复 2026-08（C4）：ddof=1
                if std > 1e-12:
                    sharpe = float(np.mean(arr)) / std * np.sqrt(252)

            return {
                "strategy_id": strategy_id,
                "trade_date": trade_date,
                "daily_return": round(daily_return, 6),
                "total_return": round(total_return, 6),
                "max_drawdown": round(max_dd, 6),
                "sharpe_ratio": round(sharpe, 6) if sharpe is not None else None,
                # 2026-08 修复（A30 补完）：total_assets 必须落库——
                # 此前 perf dict 不带该字段导致 total_assets 列恒 NULL，
                # 次日绩效 prev.total_assets 恒缺 → daily_return 每次相对 run_initial 重算
                # （与 total_return 恒相等），日收益曲线失真。
                "total_assets": round(total_assets, 2),
                "created_at": datetime.now(),
            }
        except Exception as e:
            logger.warning(f"策略 {strategy_id} 绩效计算失败: {e}")
            return None

    async def save_daily_performance(self, perf: Dict) -> bool:
        """保存一条每日绩效记录"""
        try:
            from shared.database.repositories.account.asset.strategy_daily_performance_repo import (
                StrategyDailyPerformanceRepository,
            )
            repo = StrategyDailyPerformanceRepository(self.session)
            # 幂等 upsert（按 strategy_id + trade_date）：重结算不产生重复行，避免首尾差被污染
            await repo.upsert_performance(perf["strategy_id"], perf["trade_date"], perf)
            return True
        except Exception as e:
            logger.warning(f"绩效记录保存失败: {e}")
            return False

    async def batch_save(self, records: List[Dict]) -> int:
        """批量保存绩效记录（回测用）"""
        try:
            from shared.database.repositories.account.asset.strategy_daily_performance_repo import (
                StrategyDailyPerformanceRepository,
            )
            repo = StrategyDailyPerformanceRepository(self.session)
            written = 0
            for rec in records:
                try:
                    await repo.create(rec)
                    written += 1
                except Exception as _e:
                    # 第一个失败时记录详细信息，后续同类错误仅计数
                    if written == 0:
                        logger.warning(f"绩效记录写入失败(首条): {_e}")
            if written < len(records):
                logger.warning(f"绩效记录写入: {written}/{len(records)} 成功")
            return written
        except Exception as e:
            logger.warning(f"批量绩效保存失败: {e}")
            return 0
