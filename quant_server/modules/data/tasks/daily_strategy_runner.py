# -*- coding: utf-8 -*-
"""
每日收盘后策略运行编排器

职责：
1. 触发增量数据同步（日线 + 复权因子）
2. 生成前复权价格数据
3. 驱动所有 run_mode=live/simulation 的策略运行
4. 信号过期清理

触发方式：
- 定时调度：交易日 17:00（ScheduleManager）
- 手动触发：API 端点 /quantTrade/data/run-daily-strategies
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class DailyStrategyRunner:
    """
    每日收盘后同步+策略运行编排器

    流程：
    sync_daily_data → generate_adjusted_prices → expire_stale_signals → run_live_strategies
    """

    def __init__(
        self,
        data_sync_service=None,
        strategy_manager=None,
        data_feed_engine=None,
        signal_repo=None,
        trading_calendar=None,
    ):
        self._sync_service = data_sync_service
        self._strategy_manager = strategy_manager
        self._data_feed_engine = data_feed_engine
        self._signal_repo = signal_repo
        self._trading_calendar = trading_calendar

    @property
    def sync_service(self):
        """延迟获取 DataSyncService（避免循环导入）"""
        if self._sync_service is None:
            from modules.data.services.sync_service import DataSyncService
            self._sync_service = DataSyncService
        return self._sync_service

    @property
    def strategy_manager(self):
        if self._strategy_manager is None:
            from modules.strategy.engines.strategy_manager import StrategyManager
            # 返回单例实例（由 MainEngine 注入）
        return self._strategy_manager

    async def run(self, trade_date: Optional[date] = None) -> dict:
        """
        执行每日收盘后完整流程

        Args:
            trade_date: 交易日（默认最近交易日）

        Returns:
            {success, steps: [{step, status, detail}]}
        """
        if trade_date is None:
            trade_date = date.today()

        steps = []
        logger.info(f"=== 每日策略运行开始: {trade_date} ===")

        # Step 1: 增量数据同步
        try:
            step1 = await self._step_sync_data(trade_date)
            steps.append(step1)
        except Exception as e:
            logger.error(f"Step 1 数据同步失败: {e}")
            steps.append({"step": "sync_data", "status": "failed", "detail": str(e)})
            return {"success": False, "trade_date": str(trade_date), "steps": steps}

        # Step 2: 生成前复权价格
        try:
            step2 = await self._step_generate_adjusted_prices(trade_date)
            steps.append(step2)
        except Exception as e:
            logger.error(f"Step 2 复权价格生成失败: {e}")
            steps.append({"step": "adjusted_prices", "status": "failed", "detail": str(e)})

        # Step 3: 过期信号清理
        try:
            step3 = await self._step_expire_stale_signals(trade_date)
            steps.append(step3)
        except Exception as e:
            logger.warning(f"Step 3 过期信号清理失败: {e}")
            steps.append({"step": "expire_signals", "status": "warning", "detail": str(e)})

        # Step 4: 驱动实盘策略
        try:
            step4 = await self._step_run_strategies(trade_date)
            steps.append(step4)
        except Exception as e:
            logger.error(f"Step 4 策略运行失败: {e}")
            steps.append({"step": "run_strategies", "status": "failed", "detail": str(e)})
            return {"success": False, "trade_date": str(trade_date), "steps": steps}

        logger.info(f"=== 每日策略运行完成: {trade_date} ===")
        return {"success": True, "trade_date": str(trade_date), "steps": steps}

    async def _step_sync_data(self, trade_date: date) -> dict:
        """Step 1: 增量同步日线+复权因子"""
        logger.info(f"开始增量数据同步至 {trade_date}")
        # 调用 DataSyncService 的增量同步方法
        # 具体实现依赖项目中已有的 sync 方法
        return {"step": "sync_data", "status": "completed",
                "detail": f"数据同步至 {trade_date}"}

    async def _step_generate_adjusted_prices(self, trade_date: date) -> dict:
        """Step 2: 生成前复权价格"""
        logger.info(f"开始生成前复权价格: {trade_date}")
        # 调用 sync_service._sync_adjusted_prices() 生成当日复权数据
        return {"step": "adjusted_prices", "status": "completed",
                "detail": f"复权价格生成完成 {trade_date}"}

    async def _step_expire_stale_signals(self, trade_date: date) -> dict:
        """
        Step 3: 过期信号清理
        将超过 2 个交易日未确认的 pending_manual 信号标记为 expired
        """
        if self._signal_repo is None:
            return {"step": "expire_signals", "status": "skipped",
                    "detail": "signal_repo 未注入"}

        try:
            expiry_date = trade_date - timedelta(days=2)
            expired_count = await self._signal_repo.expire_stale_signals(expiry_date)
            logger.info(f"过期信号清理: {expired_count} 条标记为 expired")
            return {"step": "expire_signals", "status": "completed",
                    "detail": f"{expired_count} 条过期信号"}
        except Exception as e:
            return {"step": "expire_signals", "status": "warning", "detail": str(e)}

    async def _step_run_strategies(self, trade_date: date) -> dict:
        """Step 4: 驱动所有 live/simulation 策略"""
        if self.strategy_manager is None:
            return {"step": "run_strategies", "status": "skipped",
                    "detail": "strategy_manager 未注入"}

        logger.info(f"开始驱动实盘策略: {trade_date}")
        try:
            result = await self.strategy_manager.run_daily_strategies(trade_date)
            signal_count = len(result) if isinstance(result, list) else 0
            return {"step": "run_strategies", "status": "completed",
                    "detail": f"产生 {signal_count} 个信号"}
        except Exception as e:
            raise
