# signal_engine.py      # 信号处理引擎

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from shared.utils.time_utils import beijing_now

logger = logging.getLogger(__name__)

from core.engines import EngineConfigEntity
from core.engines.base.engine_base import EngineBase
from core.engines.system import EventEngine
from core.engines.types.enums import EngineType
from modules.trade.engines.execution_engine import ExecutionEngine
from modules.trade.engines.risk_engine import RiskEngine
from modules.trade.constants import ExecutionMode  # v2.4: 消除跨模块依赖


class SignalEngine(EngineBase):
    """信号处理引擎 — 接收策略信号，经风控检查后送执行引擎"""

    def __init__(
        self,
        config: Dict[str, Any],
        execution_engine: ExecutionEngine,
        risk_engine: RiskEngine,
        event_engine: Optional[EventEngine] = None,
        session_factory=None,
    ):
        # 创建 EngineConfig 实例
        config_obj = EngineConfigEntity(
            name=config.get("name", "signal_engine"),
            engine_type="signal_engine",
            dependencies=config.get("dependencies", []),
            max_retries=config.get("max_retries", 3),
            retry_delay=config.get("retry_delay", 1.0),
            config=config
        )

        super().__init__(config=config_obj, event_engine=event_engine)
        self.execution_engine = execution_engine
        self.risk_engine = risk_engine
        self._session_factory = session_factory
        self.signals = {}
        self.processed_signals = []
    
    @property
    def engine_type(self) -> EngineType:
        """获取引擎类型"""
        return EngineType.SIGNAL_ENGINE
    
    async def _on_initialize(self) -> None:
        """引擎特定的初始化逻辑"""
        logger.info("SignalEngine 初始化完成")

    async def _on_start(self) -> None:
        """引擎特定的启动逻辑 — 订阅策略信号事件"""
        if self.event_engine:
            from modules.strategy.events.signal_events import StrategySignalEvent
            self.event_engine.subscribe(StrategySignalEvent, self._on_strategy_signal)
        logger.info("SignalEngine 启动成功")

    async def _on_strategy_signal(self, event) -> None:
        """处理策略信号事件，将信号送入风控→执行链路"""
        await self.process_signal(event.data)

    async def _on_stop(self) -> None:
        """引擎特定的停止逻辑"""
        logger.info("SignalEngine 已停止")

    async def _on_force_stop(self) -> None:
        """引擎特定的强制停止逻辑"""
        logger.warning("SignalEngine 强制停止")

    def _validate_config(self) -> None:
        """验证必要配置项"""
        required_keys = ["name"]
        for key in required_keys:
            if key not in self.config.config:
                logger.warning(f"SignalEngine 缺少配置项: {key}")

    async def _check_dependencies(self) -> None:
        """检查依赖引擎是否可用"""
        if self.execution_engine is None:
            raise RuntimeError("SignalEngine 依赖 ExecutionEngine，但未注入")
        if self.risk_engine is None:
            raise RuntimeError("SignalEngine 依赖 RiskEngine，但未注入")

    async def _start_background_tasks(self) -> None:
        """启动后台任务（信号处理统计等）"""
        pass

    async def _stop_background_tasks(self) -> None:
        """停止后台任务"""
        pass

    async def _monitoring_loop(self) -> None:
        """监控循环"""
        pass
    
    async def start(self) -> bool:
        """启动信号引擎"""
        return await super().start()
    
    async def stop(self, force: bool = False, timeout: float = 30.0) -> bool:
        """停止信号引擎"""
        return await super().stop(force=force, timeout=timeout)
    
    async def _persist_signal(self, signal_data: Dict[str, Any]) -> Optional[str]:
        """
        将信号写入 signals 超表（通过 session_factory 从连接池获取会话）
        """
        if self._session_factory is None:
            logger.warning("session_factory 未注入，跳过信号持久化")
            return None

        try:
            from shared.database.repositories.strategy.signal.signal_repo import SignalRepository

            async with self._session_factory() as session:
                async with session.begin():
                    repo = SignalRepository(session)
                    sid = signal_data.get("strategy_id") or None
                    if not sid:
                        logger.warning("信号缺少 strategy_id，跳过持久化")
                        return None
                    # 映射 signal_type: event 用 entry/exit/stop_loss/take_profit
                    # DB CHECK 约束要求 buy/sell/hold，此处做兼容映射
                    _raw_sig_type = str(signal_data.get("signal_type", signal_data.get("direction", "buy"))).lower()
                    _sig_type_map = {
                        "entry": "buy", "exit": "sell",
                        "stop_loss": "sell", "take_profit": "sell",
                        "long": "buy", "short": "sell",
                        "close_long": "sell", "close_short": "buy",
                    }
                    _db_signal_type = _sig_type_map.get(_raw_sig_type, _raw_sig_type)
                    # direction 存储原始 signal_direction (long/short)
                    _raw_dir = str(signal_data.get("direction", "")).lower()
                    _dir_map = {"long": "long", "short": "short", "buy": "buy", "sell": "sell",
                                "close_long": "sell", "close_short": "cover"}
                    _db_direction = _dir_map.get(_raw_dir, _raw_dir)

                    signal_record = await repo.create({
                        "strategy_id": sid,
                        "strategy_version_id": signal_data.get("strategy_version_id") or None,
                        "ts_code": signal_data.get("ts_code", ""),
                        "direction": _db_direction,
                        "signal_type": _db_signal_type,
                        "signal_time": beijing_now(),
                        "price": signal_data.get("price", 0.0),
                        "quantity": signal_data.get("quantity", 0),
                        "strength": float(signal_data.get("confidence", signal_data.get("strength", 1.0))),
                        "confidence": float(signal_data.get("confidence", 1.0)),
                        "reason": signal_data.get("reason", ""),
                        "price_limit_low": signal_data.get("price_limit_low"),
                        "price_limit_high": signal_data.get("price_limit_high"),
                        "max_slippage_pct": signal_data.get("max_slippage_pct", 0.02),
                        "order_type": signal_data.get("order_type", "limit_range"),
                        "parent_id": signal_data.get("parent_id"),  # v3.4: 父信号ID
                        "signal_status": "pending_manual",  # v3.3: 统一用 signal_status
                    })
                    db_id = signal_record.id
            # 返回 DB id（status 列已废弃 v3.3，统一用 signal_status）
            return db_id
        except ImportError as e:
            logger.warning(f"SignalRepository 不可用: {e}")
        except Exception as e:
            logger.error(f"信号持久化失败: {e}")
        return None

    async def process_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """处理信号"""
        # 生成信号ID
        signal_id = signal_data.get("signal_id", str(uuid.uuid4()))

        # 从事件 data 中提取所有信号字段（用于持久化和后续处理）
        sig_direction = signal_data.get("signal_direction", signal_data.get("direction", ""))
        sig_type = signal_data.get("signal_type", "")

        # 补充信号信息
        signal = {
            "signal_id": signal_id,
            "ts_code": signal_data.get("ts_code"),
            "direction": sig_direction,
            "signal_type": sig_type,
            "price": signal_data.get("price"),
            "quantity": signal_data.get("quantity"),
            "confidence": signal_data.get("confidence", 1.0),
            "reason": signal_data.get("reason", signal_data.get("message", "")),
            "price_limit_low": signal_data.get("price_limit_low"),
            "price_limit_high": signal_data.get("price_limit_high"),
            "max_slippage_pct": signal_data.get("max_slippage_pct", 0.02),
            "order_type": signal_data.get("order_type", "limit_range"),
            "parent_id": signal_data.get("parent_id"),  # v3.4: 父信号ID透传（P0 修复：此前重建 dict 缺此键导致追溯链路断裂）
            "strategy_id": signal_data.get("strategy_id", "unknown"),
            "created_at": beijing_now().isoformat(),
            "status": "received",
            "message": "信号已接收"
        }
        
        # 保存信号
        self.signals[signal_id] = signal

        # 持久化到数据库（v2.0: 含价格范围字段）
        db_signal_id = await self._persist_signal(signal)

        # v2.0: 实盘模式 → 推送交易信号通知
        run_mode = signal_data.get("run_mode", "backtest")
        execution_mode = signal_data.get("execution_mode", "semi_auto")
        if run_mode in ("live",):
            await self._send_signal_notification(signal_data, signal_id)

        # v2.0: 根据执行模式分支
        if execution_mode == "semi_auto" or execution_mode == ExecutionMode.SEMI_AUTO:
            # 半自动：信号状态设为 pending_manual，等待人工确认
            signal["status"] = "pending_manual"
            signal["message"] = "信号已生成，等待人工确认成交"
            self.processed_signals.append(signal)
            self._update_signal_status(db_signal_id, "pending_manual")
            logger.info(
                "半自动信号 pending_manual: %s %s %s @ %.2f",
                signal_id, signal.get("ts_code"), signal.get("direction"), signal.get("price", 0)
            )
            return signal

        # 全自动：走风控→执行链路
        try:
            # 发布风控检查请求事件（异步通知，不阻塞）
            if self.event_engine:
                try:
                    from modules.risk.events.risk_events import RiskCheckRequestedEvent
                    await self.event_engine.put(
                        RiskCheckRequestedEvent(signal_data=signal)
                    )
                except Exception as e:
                    logger.debug(f"发布风控检查事件失败（不影响主流程）: {e}")

            # 同步风控检查（v3.0：分层 severity）
            is_valid, message = await self.risk_engine.check_signal(signal)
            action_hint = self.risk_engine.get_last_check_action_hint()

            if not is_valid:
                # error/critical 违规 — 阻断下单
                if self.event_engine:
                    try:
                        from modules.risk.events.risk_events import RiskViolationEvent
                        await self.event_engine.put(
                            RiskViolationEvent(
                                rule_name="signal_check",
                                message=f"风控检查失败: {message}",
                                signal_data=signal,
                            )
                        )
                    except Exception:
                        pass
                signal["status"] = "rejected"
                signal["message"] = f"风控检查失败: {message}"
                self.processed_signals.append(signal)
                self._update_signal_status(db_signal_id, "rejected")
                return signal

            # v3.0: warning 级违规 — 缩减订单量但不阻断
            if action_hint == "reduce_size" and signal.get("quantity"):
                original_qty = signal["quantity"]
                signal["quantity"] = max(int(original_qty * 0.5), 100)  # 至少保留 100 股
                logger.info(
                    "风控 warning — 订单量缩减: %s -> %s (ts_code=%s)",
                    original_qty, signal["quantity"], signal.get("ts_code")
                )

            # 执行信号
            execution_result = await self.execution_engine.execute_signal(signal)

            if execution_result["success"]:
                signal["status"] = "executed"
                signal["message"] = "信号执行成功"
                signal["order_id"] = execution_result["order"].get("order_id")
                self._update_signal_status(db_signal_id, "executed", signal.get("order_id"))
            else:
                signal["status"] = "failed"
                signal["message"] = f"信号执行失败: {execution_result.get('message')}"
                self._update_signal_status(db_signal_id, "failed")

        except Exception as e:
            signal["status"] = "error"
            signal["message"] = f"信号处理异常: {str(e)}"
            self._update_signal_status(db_signal_id, "error")

        # 记录处理结果
        self.processed_signals.append(signal)
        
        # 发布信号处理完成事件
        if self.event_engine:
            # 这里可以发布信号处理完成事件
            pass
        
        return signal
    
    async def _send_signal_notification(
        self, signal_data: Dict[str, Any], signal_id: str
    ) -> None:
        """v2.0: 推送交易信号到微信/钉钉通知"""
        if not self.event_engine:
            return
        try:
            from core.events.base import BaseEvent
            event = BaseEvent(
                source="trade",
                module="trade",
                event_type="monitor.trading.signal",
                data={
                    "signal_id": signal_id,
                    "strategy_name": signal_data.get("strategy_name", ""),
                    "ts_code": signal_data.get("ts_code", ""),
                    "signal_direction": signal_data.get("signal_direction", signal_data.get("direction", "")),
                    "signal_type": signal_data.get("signal_type", ""),
                    "price": signal_data.get("price", 0),
                    "price_limit_low": signal_data.get("price_limit_low"),
                    "price_limit_high": signal_data.get("price_limit_high"),
                    "max_slippage_pct": signal_data.get("max_slippage_pct", 0.02),
                    "order_type": signal_data.get("order_type", "limit_range"),
                    "quantity": signal_data.get("quantity", 0),
                    "confidence": signal_data.get("confidence", 1.0),
                    "reason": signal_data.get("reason", ""),
                    "timestamp": signal_data.get("timestamp", signal_data.get("generation_time", "")),
                },
            )
            await self.event_engine.put(event)
            logger.info(f"交易信号通知已发布: {signal_id}")
        except Exception as e:
            logger.warning(f"发布交易信号通知失败: {e}")

    async def _update_signal_status(self, db_id: Optional[str], status: str, order_id: str = None):
        """回写信号状态到数据库"""
        if not db_id or not self._session_factory:
            return
        try:
            async with self._session_factory() as session:
                async with session.begin():
                    from shared.database.repositories.strategy.signal.signal_repo import SignalRepository
                    repo = SignalRepository(session)
                    update_data = {"signal_status": status}
                    if order_id:
                        update_data["order_id"] = order_id
                    await repo.update(db_id, update_data)
        except Exception as e:
            logger.warning(f"回写信号状态失败: {e}")

    def get_signal(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """获取信号信息"""
        return self.signals.get(signal_id)
    
    def get_signals(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取信号列表"""
        signals = list(self.signals.values())
        if status:
            signals = [signal for signal in signals if signal.get("status") == status]
        return signals
    
    def get_processed_signals(self) -> List[Dict[str, Any]]:
        """获取已处理的信号"""
        return self.processed_signals
    
    def get_signals_by_strategy(self, strategy_id: str) -> List[Dict[str, Any]]:
        """根据策略ID获取信号"""
        return [signal for signal in self.signals.values() if signal.get("strategy_id") == strategy_id]
    
    async def batch_process_signals(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量处理信号"""
        results = []
        for signal_data in signals:
            result = await self.process_signal(signal_data)
            results.append(result)
        return results