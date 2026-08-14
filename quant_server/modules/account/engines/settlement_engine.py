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
from datetime import date, datetime, timedelta
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

    # 防抖窗口：同一账户在此时间内的重复请求将被合并
    DEBOUNCE_SECONDS = 300  # 5 分钟

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

        # 防抖追踪：account_id → 最近一次结算触发时间
        self._last_settlement: Dict[str, datetime] = {}
        # 防抖定时器：account_id → 待执行的延时任务
        self._debounce_timers: Dict[str, asyncio.Task] = {}

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
                # 修复 2026-08（A4）：事件数据中 settlement_date 为字符串（如 "2026-08-14"），
                # 下游 settlement_tasks 用 datetime.combine 需要 date 对象，
                # 此前字符串在此抛 TypeError，导致成交触发结算全失败
                if isinstance(trading_day, str):
                    trading_day = date.fromisoformat(trading_day[:10])
                elif isinstance(trading_day, datetime):
                    trading_day = trading_day.date()

                if self._db_session_factory:
                    await self._run_settlement(settlement_type, trading_day)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("结算事件处理异常")

    async def _handle_settlement_started(self, event: AccountSettlementStartedEvent) -> None:
        """处理结算开始事件，带 5 分钟防抖：同一账户的重复请求合并为一次"""
        event_data = event.data
        account_ids = event_data.get("account_ids", [])

        # 全局结算（无 account_ids 过滤）直接入队，不走防抖
        if not account_ids:
            await self._event_queue.put(event_data)
            return

        now = datetime.now()
        deduped_ids: list = []
        for aid in account_ids:
            last = self._last_settlement.get(aid)
            if last and (now - last).total_seconds() < self.DEBOUNCE_SECONDS:
                # 取消已有的延时任务，更新为新的
                old_task = self._debounce_timers.pop(aid, None)
                if old_task and not old_task.done():
                    old_task.cancel()
                logger.debug(f"结算防抖: 账户 {aid} 的重复请求已合并")
            else:
                deduped_ids.append(aid)

        if not deduped_ids:
            # 所有请求均被防抖合并，延时 5 分钟后统一执行
            merged_ids = list(account_ids)
            self._debounce_timers[",".join(merged_ids)] = asyncio.create_task(
                self._delayed_settlement(event_data.get("settlement_type", "daily"),
                                         event_data.get("settlement_date"),
                                         merged_ids)
            )
            return

        # 更新防抖时间戳并正常入队
        for aid in deduped_ids:
            self._last_settlement[aid] = now

        event_data["account_ids"] = deduped_ids
        await self._event_queue.put(event_data)

    async def _delayed_settlement(
        self, settlement_type: str, settlement_date: Optional[str], account_ids: list
    ) -> None:
        """防抖延时后执行结算"""
        await asyncio.sleep(self.DEBOUNCE_SECONDS)
        event_data = {
            "settlement_type": settlement_type,
            "settlement_date": settlement_date,
            "account_ids": account_ids,
        }
        await self._event_queue.put(event_data)

    async def _run_settlement(self, settlement_type: str, trading_day: Optional[date]) -> None:
        """执行结算任务并发布完成事件"""
        from modules.account.tasks.settlement_tasks import create_settlement_tasks

        try:
            async with self._db_session_factory() as session:
                tasks = create_settlement_tasks(session, event_engine=self.event_engine)

                if settlement_type == "weekly":
                    result = await tasks.weekly_settlement_task(trading_day)
                elif settlement_type == "monthly":
                    result = await tasks.monthly_settlement_task(trading_day)
                else:
                    result = await tasks.daily_settlement_task(trading_day)

                await session.commit()

                if self.event_engine:
                    results = result.get("results", {})
                    total = len(results)
                    success_count = sum(1 for r in results.values() if r.get("status") == "success")
                    failed = total - success_count

                    await self.event_engine.put(AccountSettlementCompletedEvent(
                        settlement_date=trading_day or date.today(),
                        settlement_type=settlement_type,
                        total_accounts=total,
                        successful_accounts=success_count,
                        failed_accounts=failed,
                        settlement_statistics=result,
                        duration_seconds=0,
                    ))
        except Exception:
            logger.exception("结算执行异常，事务已回滚")
            raise
