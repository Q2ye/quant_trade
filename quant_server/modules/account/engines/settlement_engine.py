# -*- coding: utf-8 -*-
"""
结算引擎

继承 EngineBase，管理日终/周/月结算流程的生命周期。
订阅 settlement 事件，协调 SettlementTasks 执行，发布结算完成事件。

订阅事件：account.settlement.started
发布事件：account.settlement.completed
"""

import asyncio
import logging
from datetime import date
from typing import Any, Dict, Optional

from core.engines.base.engine_base import EngineBase
from core.engines.types.entities import EngineConfigEntity
from core.engines.types.enums import EngineType
from modules.account.events.settlement_events import (
    AccountSettlementStartedEvent,
    AccountSettlementCompletedEvent,
)

logger = logging.getLogger(__name__)


class SettlementEngine(EngineBase):
    """结算引擎 — 编排结算流程，消费结算开始事件，发布结算完成事件"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_engine=None,
        db_session_factory=None,
    ):
        cfg = config or {}
        config_obj = EngineConfigEntity(
            name=cfg.get("name", "settlement_engine"),
            engine_type="settlement_engine",
            dependencies=cfg.get("dependencies", []),
            max_retries=cfg.get("max_retries", 3),
            retry_delay=cfg.get("retry_delay", 1.0),
            config=cfg,
        )
        super().__init__(config=config_obj, event_engine=event_engine)

        self._db_session_factory = db_session_factory
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._process_task: Optional[asyncio.Task] = None

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CUSTOM

    async def _on_initialize(self) -> None:
        """引擎初始化：订阅结算事件"""
        if self.event_engine:
            self.event_engine.register_handler(
                AccountSettlementStartedEvent, self._handle_settlement_started
            )
        logger.info("结算引擎初始化完成")

    async def _on_start(self) -> None:
        """启动事件处理循环"""
        self._process_task = asyncio.create_task(self._process_events())
        logger.info("结算引擎已启动")

    async def _on_stop(self) -> None:
        """停止事件处理"""
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("结算引擎已停止")

    async def _process_events(self) -> None:
        """后台事件处理循环"""
        while True:
            try:
                event_data = await asyncio.wait_for(self._event_queue.get(), timeout=60.0)
                settlement_type = event_data.get("settlement_type", "daily")
                trading_day = event_data.get("settlement_date")

                if self._db_session_factory:
                    await self._run_settlement(settlement_type, trading_day)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("结算事件处理异常")

    async def _handle_settlement_started(self, event: AccountSettlementStartedEvent) -> None:
        """处理结算开始事件，放入队列异步执行"""
        await self._event_queue.put(event.data)

    async def _run_settlement(self, settlement_type: str, trading_day: Optional[date]) -> None:
        """执行结算任务并发布完成事件"""
        from modules.account.tasks.settlement_tasks import create_settlement_tasks

        session = self._db_session_factory()
        try:
            tasks = create_settlement_tasks(session, event_engine=self.event_engine)

            if settlement_type == "weekly":
                result = await tasks.weekly_settlement_task(trading_day)
            elif settlement_type == "monthly":
                result = await tasks.monthly_settlement_task(trading_day)
            else:
                result = await tasks.daily_settlement_task(trading_day)

            if self.event_engine:
                # 统计结果
                results = result.get("results", {})
                total = len(results)
                success = sum(1 for r in results.values() if r.get("status") == "success")
                failed = total - success

                await self.event_engine.put(AccountSettlementCompletedEvent(
                    settlement_date=trading_day or date.today(),
                    settlement_type=settlement_type,
                    total_accounts=total,
                    successful_accounts=success,
                    failed_accounts=failed,
                    settlement_statistics=result,
                    duration_seconds=0,
                ))
        finally:
            await session.close()
