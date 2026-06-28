# -*- coding: utf-8 -*-
"""
MarketEngine — 市场数据引擎

负责:
- 交易日历加载与缓存
- 市场状态管理（开盘/收盘/午休）
- 数据同步完成后刷新仪表盘缓存
"""
import logging
from datetime import date, datetime
from typing import Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from core.engines.base.engine_base import EngineBase, EngineConfigEntity
from core.engines.types.enums import EngineType

logger = logging.getLogger(__name__)


class MarketEngine(EngineBase):
    """市场数据引擎"""

    def __init__(self, db: AsyncSession, event_engine=None):
        super().__init__(
            EngineConfigEntity(
                name="MarketEngine",
                engine_type="market",
            ),
            event_engine=event_engine,
        )
        self.db = db
        self._trading_days: Set[date] = set()
        self._today_status: str = "unknown"

    async def _on_initialize(self) -> None:
        """加载交易日历（最近 1 年）"""
        try:
            from shared.database.repositories.market.reference.trade_calendar_repo import (
                TradeCalendarRepository,
            )
            repo = TradeCalendarRepository(self.db)
            today = date.today()
            cal = await repo.get_trade_dates(
                exchange="SSE",
                start_date=date(today.year - 1, 1, 1),
                end_date=today,
                only_open=True,
            )
            self._trading_days = set(
                d.date() if hasattr(d, "date") else d for d in cal
            )
            logger.info(
                "MarketEngine 初始化完成，交易日历缓存 %d 天",
                len(self._trading_days),
            )
        except Exception as e:
            logger.warning(f"MarketEngine 交易日历加载失败: {e}")

    async def _on_start(self) -> None:
        """订阅数据同步完成事件"""
        if self._event_engine:
            self._event_engine.subscribe(
                "data.sync.completed", self._on_sync_completed
            )
            logger.info("MarketEngine 已启动")

    async def _on_stop(self) -> None:
        """清理缓存"""
        self._trading_days.clear()
        logger.info("MarketEngine 已停止")

    async def _on_sync_completed(self, event) -> None:
        """数据同步完成时刷新缓存"""
        logger.info("数据同步完成，MarketEngine 缓存已过期（下次访问时刷新）")
        self._trading_days.clear()

    def is_trading_day(self, d: date) -> bool:
        """检查是否为交易日"""
        return d in self._trading_days

    @property
    def today_status(self) -> str:
        return self._today_status
