# -*- coding: utf-8 -*-
"""
策略执行服务
负责策略的启动、停止、暂停、恢复等运行控制

v2.0: 接入 EventEngine，通过事件通知 StrategyManager 引擎执行实际策略生命周期。
      ExecutionService 负责 DB 操作 + 事件发布，StrategyManager 负责策略加载和运行。
"""
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from modules.strategy.constants import (
    StrategyLifecycleStatus,
    RunMode,
    ExecutionMode,
    ErrorCode,
)
from modules.strategy.models import StrategyState
from shared.database.repositories.strategy.management import (
    StrategyRepository,
    StrategyRunRepository,
)
from shared.database.repositories import TradeRepository

logger = logging.getLogger(__name__)


class ExecutionService:
    """
    策略执行服务

    负责：
    - 策略启动/停止（DB 操作 + 事件发布）
    - 策略暂停/恢复
    - 运行状态管理
    - 持仓和资金管理

    注意：实际策略加载/初始化/运行由 StrategyManager 引擎负责。
    ExecutionService 通过 EventEngine 发布事件通知引擎执行。
    """

    def __init__(
        self,
        session: AsyncSession,
        event_engine=None,
    ):
        """
        初始化服务

        Args:
            session: 数据库会话
            event_engine: 事件引擎（可选，用于通知 StrategyManager）
        """
        self.session = session
        self.event_engine = event_engine
        self.strategy_repo = StrategyRepository(session)
        self.strategy_run_repo = StrategyRunRepository(session)
        self.trade_repo = TradeRepository(session)

    async def start_strategy(
            self,
            strategy_id: str,
            user_id: str,
            capital: Optional[float] = None,
            parameters: Optional[Dict[str, Any]] = None,
            run_mode: RunMode = RunMode.LIVE,
            execution_mode: ExecutionMode = ExecutionMode.SEMI_AUTO,
            account_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        启动策略

        1. 校验策略状态、权限、账户资金
        2. 更新 DB: status=RUNNING, run_mode, execution_mode, account_id, allocated_capital
        3. 创建 strategy_runs 记录（含 account_id）
        4. 发布 StrategyStartedEvent → StrategyManager 响应并真正加载执行

        Args:
            strategy_id: 策略ID
            user_id: 用户ID
            capital: 初始资金/分配额度
            parameters: 运行参数
            run_mode: 运行模式
            execution_mode: 执行模式（半自动/全自动）
            account_id: 绑定的交易账户ID（实盘必选）

        Returns:
            启动结果
        """
        try:
            # 获取策略
            strategy = await self.strategy_repo.get_by_id(strategy_id)
            if not strategy:
                return {
                    "success": False,
                    "error": f"策略 {strategy_id} 不存在",
                    "error_code": ErrorCode.STRATEGY_NOT_FOUND,
                }

            if strategy.user_id != user_id:
                return {
                    "success": False,
                    "error": "无权操作此策略",
                    "error_code": ErrorCode.STRATEGY_NOT_FOUND,
                }

            # 检查状态：仅阻止重复启动
            if strategy.status == StrategyLifecycleStatus.RUNNING:
                logger.warning(f"策略 {strategy_id} 已在运行中，跳过启动")
                return {
                    "success": False,
                    "error": "策略已在运行中",
                    "error_code": ErrorCode.STRATEGY_ALREADY_RUNNING,
                }

            # v2.1: 使用状态转换矩阵校验
            if StrategyLifecycleStatus.RUNNING not in StrategyLifecycleStatus.allowed_transitions(
                StrategyLifecycleStatus(strategy.status)
            ):
                return {
                    "success": False,
                    "error": f"当前状态 {strategy.status} 不允许启动",
                    "error_code": ErrorCode.STRATEGY_INVALID_PARAMETER,
                }

            # 获取或设置初始资金
            if capital is None:
                capital = 1000000.0

            if capital <= 0:
                return {
                    "success": False,
                    "error": "初始资金必须大于0",
                    "error_code": ErrorCode.STRATEGY_INSUFFICIENT_CAPITAL,
                }

            # 创建策略运行记录
            run_data = {
                "strategy_id": strategy_id,
                "run_mode": run_mode.value,
                "execution_mode": execution_mode.value,
                "account_id": account_id,
                "allocated_capital": capital,
                "status": "running",
                "started_at": datetime.now(),
            }
            run_record = await self.strategy_run_repo.create(run_data)

            # 更新策略状态 + 绑定账户 + 记录分配资金
            strategy.status = StrategyLifecycleStatus.RUNNING.value
            strategy.run_mode = run_mode.value
            strategy.execution_mode = execution_mode.value
            strategy.account_id = account_id if account_id else None
            strategy.allocated_capital = capital
            strategy.updated_at = datetime.now()

            await self.session.commit()
            await self.session.refresh(strategy)

            logger.info(
                f"策略启动成功(DB): {strategy_id}, status={strategy.status}, "
                f"run_mode={strategy.run_mode}, execution_mode={getattr(strategy, 'execution_mode', 'N/A')}, "
                f"资金: {capital}, account_id={account_id}"
            )

            # v2.0: 发布事件通知 StrategyManager 引擎加载并执行策略
            if self.event_engine:
                try:
                    from modules.strategy.events.lifecycle_events import StrategyStartedEvent
                    event = StrategyStartedEvent(
                        strategy_id=strategy_id,
                        user_id=user_id,
                        initial_capital=capital,
                        parameters=parameters or {},
                        run_mode=run_mode.value,
                        execution_mode=execution_mode.value,
                        account_id=account_id or "",
                    )
                    await self.event_engine.put(event)
                    logger.info(f"已发布 StrategyStartedEvent: {strategy_id}")
                except Exception as e:
                    logger.error(f"发布 StrategyStartedEvent 失败: {e}")
                    # 事件发布失败不阻塞 HTTP 响应

            return {
                "success": True,
                "data": {
                    "strategy_id": strategy_id,
                    "run_id": run_record.id if run_record else None,
                    "status": "running",
                    "run_mode": run_mode.value,
                    "execution_mode": execution_mode.value,
                    "account_id": account_id,
                    "capital": capital,
                    "started_at": datetime.now().isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"启动策略失败: {e}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    async def stop_strategy(
            self,
            strategy_id: str,
            user_id: str,
            force: bool = False,
    ) -> Dict[str, Any]:
        """
        停止策略

        Args:
            strategy_id: 策略ID
            user_id: 用户ID
            force: 是否强制停止

        Returns:
            停止结果
        """
        try:
            # 获取策略
            strategy = await self.strategy_repo.get_by_id(strategy_id)
            if not strategy:
                return {
                    "success": False,
                    "error": f"策略 {strategy_id} 不存在",
                    "error_code": ErrorCode.STRATEGY_NOT_FOUND,
                }

            if strategy.user_id != user_id:
                return {
                    "success": False,
                    "error": "无权操作此策略",
                    "error_code": ErrorCode.STRATEGY_NOT_FOUND,
                }

            # 检查状态：允许 RUNNING、PAUSED、ERROR 状态下停止
            if strategy.status not in (
                StrategyLifecycleStatus.RUNNING.value,
                StrategyLifecycleStatus.PAUSED.value,
                StrategyLifecycleStatus.ERROR.value,
            ):
                return {
                    "success": False,
                    "error": f"策略状态为 {strategy.status}，无法停止",
                    "error_code": ErrorCode.STRATEGY_NOT_RUNNING,
                }

            # 获取运行记录
            runs = await self.strategy_run_repo.get_by_strategy_id(strategy_id)
            active_run = None
            for run in runs:
                if run.status == "running":
                    active_run = run
                    break

            # 更新运行记录
            if active_run:
                await self.strategy_run_repo.update(active_run.id, {
                    "status": "stopped",
                    "stopped_at": datetime.now(),
                })

            # 计算绩效
            performance = await self._calculate_performance(strategy_id)

            # 直接修改 ORM 对象
            strategy.status = StrategyLifecycleStatus.STOPPED.value
            strategy.updated_at = datetime.now()

            await self.session.commit()
            await self.session.refresh(strategy)

            # v2.0: 发布事件通知 StrategyManager 停止策略
            if self.event_engine:
                try:
                    from modules.strategy.events.lifecycle_events import StrategyStoppedEvent
                    event = StrategyStoppedEvent(
                        strategy_id=strategy_id,
                        user_id=user_id,
                        reason="manual" if not force else "force",
                        performance_summary=performance,
                    )
                    await self.event_engine.put(event)
                    logger.info(f"已发布 StrategyStoppedEvent: {strategy_id}")
                except Exception as e:
                    logger.error(f"发布 StrategyStoppedEvent 失败: {e}")

            logger.info(f"策略停止成功: {strategy_id}")

            return {
                "success": True,
                "data": {
                    "strategy_id": strategy_id,
                    "status": "stopped",
                    "performance": performance,
                    "stopped_at": datetime.now().isoformat(),
                },
            }
        except Exception as e:
            logger.error(f"停止策略失败: {e}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    async def pause_strategy(
            self,
            strategy_id: str,
            user_id: str,
    ) -> Dict[str, Any]:
        """
        暂停策略

        Args:
            strategy_id: 策略ID
            user_id: 用户ID

        Returns:
            暂停结果
        """
        try:
            strategy = await self.strategy_repo.get_by_id(strategy_id)
            if not strategy:
                return {
                    "success": False,
                    "error": f"策略 {strategy_id} 不存在",
                }

            if strategy.user_id != user_id:
                return {
                    "success": False,
                    "error": "无权操作此策略",
                }

            # v2.1: 检查转换合法性
            from_status = StrategyLifecycleStatus(strategy.status)
            if StrategyLifecycleStatus.PAUSED not in StrategyLifecycleStatus.allowed_transitions(from_status):
                return {
                    "success": False,
                    "error": f"当前状态 {strategy.status} 不允许暂停",
                }

            # 直接修改 ORM 对象
            strategy.status = StrategyLifecycleStatus.PAUSED.value
            strategy.updated_at = datetime.now()

            await self.session.commit()
            await self.session.refresh(strategy)

            # v2.0: 发布暂停事件
            if self.event_engine:
                try:
                    from modules.strategy.events.lifecycle_events import StrategyPausedEvent
                    event = StrategyPausedEvent(
                        strategy_id=strategy_id,
                        user_id=user_id,
                        reason="manual",
                    )
                    await self.event_engine.put(event)
                except Exception as e:
                    logger.error(f"发布 StrategyPausedEvent 失败: {e}")

            return {
                "success": True,
                "data": {
                    "strategy_id": strategy_id,
                    "status": "paused",
                },
            }
        except Exception as e:
            logger.error(f"暂停策略失败: {e}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    async def resume_strategy(
            self,
            strategy_id: str,
            user_id: str,
    ) -> Dict[str, Any]:
        """
        恢复策略

        Args:
            strategy_id: 策略ID
            user_id: 用户ID

        Returns:
            恢复结果
        """
        try:
            strategy = await self.strategy_repo.get_by_id(strategy_id)
            if not strategy:
                return {
                    "success": False,
                    "error": f"策略 {strategy_id} 不存在",
                }

            if strategy.user_id != user_id:
                return {
                    "success": False,
                    "error": "无权操作此策略",
                }

            # v2.1: 检查转换合法性
            from_status = StrategyLifecycleStatus(strategy.status)
            if StrategyLifecycleStatus.RUNNING not in StrategyLifecycleStatus.allowed_transitions(from_status):
                return {
                    "success": False,
                    "error": f"当前状态 {strategy.status} 不允许恢复",
                }

            # 直接修改 ORM 对象
            strategy.status = StrategyLifecycleStatus.RUNNING.value
            strategy.updated_at = datetime.now()

            await self.session.commit()
            await self.session.refresh(strategy)

            # v2.0: 发布恢复事件
            if self.event_engine:
                try:
                    from modules.strategy.events.lifecycle_events import StrategyResumedEvent
                    event = StrategyResumedEvent(
                        strategy_id=strategy_id,
                        user_id=user_id,
                    )
                    await self.event_engine.put(event)
                except Exception as e:
                    logger.error(f"发布 StrategyResumedEvent 失败: {e}")

            return {
                "success": True,
                "data": {
                    "strategy_id": strategy_id,
                    "status": "running",
                },
            }
        except Exception as e:
            logger.error(f"恢复策略失败: {e}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    async def get_strategy_status(
            self,
            strategy_id: str,
            user_id: str,
    ) -> Dict[str, Any]:
        """
        获取策略状态

        Args:
            strategy_id: 策略ID
            user_id: 用户ID

        Returns:
            策略状态
        """
        try:
            strategy = await self.strategy_repo.get_by_id(strategy_id)
            if not strategy:
                return {
                    "success": False,
                    "error": f"策略 {strategy_id} 不存在",
                }

            if strategy.user_id != user_id:
                return {
                    "success": False,
                    "error": "无权访问此策略",
                }

            # 获取运行信息
            runs = await self.strategy_run_repo.get_by_strategy_id(strategy_id)
            active_run = None
            for run in runs:
                if run.status == "running":
                    active_run = run
                    break

            return {
                "success": True,
                "data": {
                    "strategy_id": strategy_id,
                    "name": strategy.name,
                    "status": strategy.status,
                    "run_mode": getattr(strategy, "run_mode", None),
                    "execution_mode": getattr(strategy, "execution_mode", None),
                    "is_running": strategy.status == StrategyLifecycleStatus.RUNNING,
                    "run_id": active_run.id if active_run else None,
                    "started_at": (
                        active_run.started_at.isoformat()
                        if active_run and active_run.started_at
                        else None
                    ),
                },
            }
        except Exception as e:
            logger.error(f"获取策略状态失败: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def _calculate_performance(self, strategy_id: str) -> Dict[str, Any]:
        """
        计算策略绩效

        Args:
            strategy_id: 策略ID

        Returns:
            绩效数据
        """
        # 获取运行记录
        runs = await self.strategy_run_repo.get_by_strategy_id(strategy_id)
        if not runs:
            return {}

        # 从成交记录计算实际绩效
        trades = await self.trade_repo.get_by_strategy_id(
            strategy_id, limit=100000,
        )

        total_trades = len(trades)
        winning_trades = 0
        losing_trades = 0
        total_pnl = 0.0

        for trade in trades:
            pnl = float(trade.pnl) if hasattr(trade, 'pnl') else 0.0
            total_pnl += pnl
            if pnl > 0:
                winning_trades += 1
            elif pnl < 0:
                losing_trades += 1

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "total_pnl": round(total_pnl, 4),
        }
