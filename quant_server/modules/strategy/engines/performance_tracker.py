# -*- coding: utf-8 -*-
"""
绩效追踪引擎（v3.3 新增）

职责：
- 订阅日终结算事件 → 自动计算所有活跃策略的每日绩效
- 遍历 RUNNING / PAUSED 策略，计算指标并写入 strategy_daily_performance 表
"""
import logging
from datetime import date

from core.engines.base.engine_base import EngineBase
from core.engines.types.enums import EngineType

logger = logging.getLogger(__name__)


class PerformanceTrackerEngine(EngineBase):
    """绩效追踪引擎"""

    engine_type = EngineType.PERFORMANCE_ENGINE

    def __init__(self, event_engine=None):
        from core.engines.base.engine_base import EngineConfigEntity
        config = EngineConfigEntity(
            name="PerformanceTracker",
            engine_type=EngineType.PERFORMANCE_ENGINE.value,
        )
        super().__init__(config=config, event_engine=event_engine)
        self.event_engine = event_engine

    async def _on_initialize(self):
        logger.info("绩效追踪引擎初始化")
        # 订阅日终结算完成事件
        if self.event_engine:
            self.event_engine.register(
                "account.settlement.completed", self._on_day_end
            )

    async def _on_start(self):
        logger.info("绩效追踪引擎已启动")

    async def _on_stop(self):
        logger.info("绩效追踪引擎已停止")

    async def _on_day_end(self, event):
        """日终结算完成 → 计算所有活跃策略的当日绩效"""
        trade_date = event.data.get("trade_date") if hasattr(event, "data") else None
        if not trade_date:
            from datetime import date as _date
            trade_date = _date.today()

        if isinstance(trade_date, str):
            from datetime import datetime as _dt
            trade_date = _dt.fromisoformat(trade_date).date()

        logger.info(f"开始计算 {trade_date} 的每日绩效")

        try:
            session_factory = getattr(self, "_session_factory", None)
            if not session_factory:
                logger.warning("绩效追踪: session_factory 未注入，跳过")
                return

            async with session_factory() as session:
                from modules.strategy.services.performance_service import (
                    PerformanceService,
                )
                svc = PerformanceService(session)
                strategies = await svc.get_active_strategies()
                if not strategies:
                    logger.info("绩效追踪: 无活跃策略需要追踪")
                    return

                written = 0
                for s in strategies:
                    sid = getattr(s, "id", None) or ""
                    if not sid:
                        continue
                    try:
                        perf = await svc.calculate_daily_performance(
                            strategy_id=sid, trade_date=trade_date
                        )
                        if perf:
                            await svc.save_daily_performance(perf)
                            written += 1
                    except Exception as e:
                        logger.warning("策略 %s 绩效追踪失败: %s", sid, e)

                await session.commit()
                logger.info(
                    f"绩效追踪完成: {trade_date}, {written}/{len(strategies)} 条已写入"
                )

        except Exception as e:
            logger.error(f"绩效追踪引擎执行失败: {e}", exc_info=True)

    async def calculate_daily(self, trade_date: date):
        """供 ScheduleManager 直接调用的入口"""
        await self._on_day_end(type("Event", (), {"data": {"trade_date": trade_date}})())
