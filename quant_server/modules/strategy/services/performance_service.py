# -*- coding: utf-8 -*-
"""
策略每日绩效计算服务（v3.3 新增）

无状态纯计算服务，负责：
1. 获取活跃策略列表
2. 计算单策略每日绩效指标
3. 写入 strategy_daily_performance 表
"""
import logging
from datetime import date, datetime, time as _time
from decimal import Decimal
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import select
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

    async def get_strategy_ids_with_trades(self, trade_date: date) -> List[str]:
        """获取指定日期有成交的策略ID（含已停用但当天有清算成交的策略）。

        停用策略不再出现在 get_active_strategies 中，但其停用后的清算卖出仍产生
        已实现盈亏，必须纳入当日绩效追踪，否则停用策略的最终盈亏会丢失。
        """
        try:
            from sqlalchemy import text
            day_start = datetime.combine(trade_date, _time.min)
            day_end = datetime.combine(trade_date, _time.max)
            rows = await self.session.execute(text(
                "SELECT DISTINCT o.strategy_id FROM trades t "
                "JOIN orders o ON t.order_id = o.order_id "
                "WHERE o.strategy_id IS NOT NULL "
                "AND t.trade_time >= :s AND t.trade_time <= :e"
            ), {"s": day_start, "e": day_end})
            return [r[0] for r in rows if r[0]]
        except Exception as e:
            logger.warning("查询当日成交策略失败: %s", str(e))
            return []

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

    async def _get_latest_run_initial(self, strategy_id: str) -> Decimal:
        """获取策略最近一条 run 的初始分配资金（已停用策略无 active run 时兜底）。"""
        try:
            from sqlalchemy import text
            r = await self.session.execute(text(
                "SELECT COALESCE(allocated_capital, 0) FROM strategy_runs "
                "WHERE strategy_id = :sid AND allocated_capital > 0 "
                "ORDER BY started_at DESC LIMIT 1"
            ), {"sid": strategy_id})
            val = r.scalar()
            return Decimal(str(val)) if val else Decimal("0")
        except Exception as e:
            logger.warning("查询策略初始分配资金失败: %s", str(e))
            return Decimal("0")

    async def _get_previous_performance(self, strategy_id: str):
        """获取该策略最近一条绩效记录"""
        from shared.database.repositories.account.asset.strategy_daily_performance_repo import (
            StrategyDailyPerformanceRepository,
        )
        repo = StrategyDailyPerformanceRepository(self.session)
        # days 回看窗口加长到 30 天：跨周末/节假日结算间隔后仍能取到上一有效快照，
        # 避免 prev=None 退化回 run_initial 导致 daily_return 与 total_return 恒相等；
        # 现金台账依赖前一条的 cash，回看窗口过短会破坏台账连续性。
        records = await repo.get_latest_performance(strategy_id, days=30)
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

    async def _get_close_prices(self, symbols: List[str], trade_date: date) -> Dict[str, Decimal]:
        """批量取当日收盘价（stock_daily 覆盖 A股，etf_daily 补 ETF）。"""
        close_map: Dict[str, Decimal] = {}
        if not symbols:
            return close_map
        from shared.database.repositories.market.quote.stock_daily_repo import StockDailyRepository
        rows = await StockDailyRepository(self.session).get_batch_by_date_range(
            symbols, trade_date, trade_date
        )
        for r in rows:
            if getattr(r, "close", None) is not None:
                close_map[r.ts_code] = Decimal(str(r.close))
        try:
            from shared.database.models.data_models import EtfDaily
            _etf_rows = (await self.session.execute(
                select(EtfDaily.ts_code, EtfDaily.close).where(
                    EtfDaily.ts_code.in_(symbols),
                    EtfDaily.trade_date == trade_date,
                )
            )).all()
            for _r in _etf_rows:
                if getattr(_r, "close", None) is not None:
                    close_map[_r.ts_code] = Decimal(str(_r.close))
        except Exception as _e:
            logger.warning(f"ETF 收盘价查询失败: {_e}")
        return close_map

    async def _get_strategy_position_mv(self, strategy_id: str, trade_date: date) -> Decimal:
        """该策略当日持仓市值（volume × 当日收盘价 mark-to-market）。"""
        from shared.database.repositories.trading.position.position_repo import PositionRepository
        positions = await PositionRepository(self.session).get_by_strategy(strategy_id)
        if not positions:
            return Decimal("0")
        symbols = [p.ts_code for p in positions if getattr(p, "volume", 0) and p.volume > 0]
        if not symbols:
            return Decimal("0")
        close_map = await self._get_close_prices(symbols, trade_date)
        mv = Decimal("0")
        for p in positions:
            if not getattr(p, "volume", 0) or p.volume <= 0:
                continue
            close = close_map.get(p.ts_code)
            if close is None:
                close = Decimal(str(p.last_price)) if p.last_price else Decimal("0")
            mv += Decimal(str(p.volume)) * close
        return mv

    async def _get_strategy_trade_cash_flow(self, strategy_id: str, trade_date: date) -> Decimal:
        """该策略当日成交净现金流（卖出净额 − 买入成本含费用）。"""
        from shared.database.repositories.trading.order.trade_repo import TradeRepository
        trade_repo = TradeRepository(self.session)
        day_start = datetime.combine(trade_date, _time.min)
        day_end = datetime.combine(trade_date, _time.max)
        trades = await trade_repo.get_by_strategy_id(
            strategy_id, start_time=day_start, end_time=day_end, limit=10_000, with_order=True,
        )
        cash_flow = Decimal("0")
        for t in trades:
            amount = Decimal(str(t.price)) * int(t.volume)
            fees = Decimal(str(getattr(t, "commission", 0) or 0)) + Decimal(str(getattr(t, "tax", 0) or 0))
            direction = getattr(getattr(t, "order", None), "direction", None)
            if direction == "buy":
                cash_flow -= (amount + fees)
            elif direction == "sell":
                cash_flow += (amount - fees)
        return cash_flow

    async def calculate_daily_performance(
        self, strategy_id: str, trade_date: date, total_assets: float = None,
    ) -> Optional[Dict]:
        """
        计算单个策略的当日绩效（基于真实净值 = 持仓市值 + 现金台账）。

        v3.4 修复：此前用 allocated_capital（分配资金目标）当资产基准，收益/回撤
        反映的是「资金分配变动」而非策略自身盈亏。改为虚拟子账户：
        - 持仓市值：positions 按 strategy_id 分组，volume × 当日收盘价 mark-to-market
        - 现金台账：run 启动 allocated_capital 起，逐日 ± 成交现金流（trades join orders）
        - 净值 = 持仓市值 + 现金

        Args:
            strategy_id: 策略ID
            trade_date: 交易日期
            total_assets: 已废弃（保留参数兼容），真实净值内部计算
        """
        try:
            # 1. 当日持仓市值（mark-to-market）
            position_mv = await self._get_strategy_position_mv(strategy_id, trade_date)

            # 2. 前一条绩效记录 + 当前 run
            prev = await self._get_previous_performance(strategy_id)
            active_run = await self._get_active_run(strategy_id)
            run_initial = Decimal(str(getattr(active_run, "allocated_capital", 0) or 0))
            if run_initial <= 0:
                # 无活跃 run（已停用策略的清算日）→ 回退最近一条 run 的初始分配资金
                run_initial = await self._get_latest_run_initial(strategy_id)

            # 3. 现金台账与净值基准（首日现金 = run 初始分配资金）
            if prev is not None and getattr(prev, "cash", None) is not None:
                prev_cash = Decimal(str(prev.cash))
                prev_nav = Decimal(str(getattr(prev, "total_assets", None) or 0))
                prev_peak = Decimal(str(getattr(prev, "peak_nav", None) or prev_nav))
                prev_max_dd = Decimal(str(getattr(prev, "max_drawdown", None) or 0))
            else:
                init = run_initial if run_initial > 0 else position_mv
                prev_cash = init
                prev_nav = init
                prev_peak = init
                prev_max_dd = Decimal("0")

            # 4. 当日成交净现金流
            cash_flow = await self._get_strategy_trade_cash_flow(strategy_id, trade_date)

            # 5. 现金 + 净值
            cash_t = prev_cash + cash_flow
            nav_t = position_mv + cash_t
            if nav_t <= 0:
                logger.info("策略 %s 无有效净值，跳过绩效写入", strategy_id)
                return None

            # 6. 指标
            base = run_initial if run_initial > 0 else nav_t
            daily_return = (nav_t - prev_nav) / prev_nav if prev_nav > 0 else 0.0
            total_return = (nav_t - base) / base if base > 0 else 0.0

            # 7. 最大回撤（负值口径：运行峰值净值跟踪）
            peak_t = max(prev_peak, nav_t)
            dd = (nav_t - peak_t) / peak_t if peak_t > 0 else 0.0
            max_dd = min(prev_max_dd, dd)

            # 8. 夏普（日收益序列）
            returns = await self._get_run_daily_returns(
                strategy_id, getattr(active_run, "id", None) if active_run else None
            )
            returns = returns + [float(daily_return)]
            sharpe = None
            annual_volatility = None
            if len(returns) >= 5:
                arr = np.array(returns, dtype=float)
                std = float(np.std(arr, ddof=1))
                # ⚠️ 2026-09-19 新增：**年化波动率**。
                #    复用上面为夏普算好的 `std`（日频），乘 √252 年化。
                #    用途：① 准入标准 B5 判据 ② 实盘健康监控的波动放大告警
                #    ③ 波动损耗 = σ²/2（每年被波动吃掉的复利）。
                #    ⚠️ 单位务必区分：`std` 是**日频**，`annual_volatility` 才是年化（差 15.87 倍）。
                annual_volatility = float(std * np.sqrt(252)) if std > 0 else None
                if std > 1e-12:
                    sharpe = float(np.mean(arr)) / std * np.sqrt(252)

            return {
                "strategy_id": strategy_id,
                "trade_date": trade_date,
                # ⚠️ 2026-09-19 修复：**必须写 `strategy_run_id`** —— 原返回值缺此字段，
                #    DB 列恒为 NULL，导致 `_get_run_daily_returns` 里
                #    `[r for r in records if r.strategy_run_id == run_id]` **过滤后恒为空**
                #    → `returns` 只剩当日 1 个 → `len(returns) >= 5` 不成立
                #    → **实盘 `sharpe_ratio` 恒为 None**（实测：`跨市场…-2.0` 5 行全空；
                #    新加的 `annual_volatility` 同样被它挡住）。
                #    此处 `active_run` 本就在上文用于查 run 级收益，直接落库即可。
                "strategy_run_id": getattr(active_run, "id", None) if active_run else None,
                "daily_return": round(float(daily_return), 6),
                "total_return": round(float(total_return), 6),
                "max_drawdown": round(float(max_dd), 6),
                "sharpe_ratio": round(sharpe, 6) if sharpe is not None else None,
                # 年化波动率（= 日频 std × √252）；2026-09-19 新增，见上方注释
                "annual_volatility": (
                    round(annual_volatility, 6) if annual_volatility is not None else None
                ),
                "total_assets": round(float(nav_t), 2),
                "cash": round(float(cash_t), 2),
                "peak_nav": round(float(peak_t), 2),
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
