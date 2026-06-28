# -*- coding: utf-8 -*-
"""
告警引擎

继承 EngineBase，管理告警的创建、分发和生命周期。
订阅系统/风险/业务引擎的告警事件，统一路由到通知渠道。

订阅事件：monitor.risk.alert.triggered, monitor.system.health.changed, monitor.trading.signal
发布事件：monitor.alert.created, monitor.alert.notification.sent/failed
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from core.engines.base.engine_base import EngineBase
from core.engines.types.entities import EngineConfigEntity
from core.engines.types.enums import EngineType
from modules.monitor.constants import ModuleConfig, AlertLevel, AlertType
from modules.monitor.events.alert_events import AlertMonitorEvent
from modules.monitor.managers.alert_manager import AlertManager

logger = logging.getLogger(__name__)


class AlertEngine(EngineBase):
    """告警引擎 — 统一告警生命周期管理"""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        event_engine=None,
        db_session_factory=None,
    ):
        cfg = config or {}
        config_obj = EngineConfigEntity(
            name=cfg.get("name", "alert_engine"),
            engine_type="alert_engine",
            dependencies=cfg.get("dependencies", []),
            max_retries=cfg.get("max_retries", 3),
            retry_delay=cfg.get("retry_delay", 1.0),
            config=cfg,
        )
        super().__init__(config=config_obj, event_engine=event_engine)

        self._alert_manager = AlertManager(cfg)
        self._db_session_factory = db_session_factory
        self._event_queue: asyncio.Queue = asyncio.Queue(maxsize=ModuleConfig.ENGINE_QUEUE_SIZE)
        self._process_task: Optional[asyncio.Task] = None

    @property
    def engine_type(self) -> EngineType:
        return EngineType.CUSTOM

    @property
    def alert_manager(self) -> AlertManager:
        return self._alert_manager

    async def _on_initialize(self) -> None:
        logger.info("告警引擎初始化")

    async def _on_start(self) -> None:
        logger.info("告警引擎启动")
        self._process_task = asyncio.create_task(
            self._process_loop(),
            name="alert_engine_process",
        )

        # 注册通知渠道（微信/钉钉/邮件）
        self._register_alerters()

        # 注册事件处理器
        if self.event_engine:
            self.event_engine.register(
                "monitor.risk.alert.triggered",
                self._handle_risk_alert,
            )
            self.event_engine.register(
                "monitor.system.health.changed",
                self._handle_system_alert,
            )
            self.event_engine.register(
                "monitor.trading.signal",
                self._handle_trading_signal,
            )

    def _register_alerters(self) -> None:
        """注册通知渠道。开关读 config.yaml，敏感 URL 读 .env"""
        import os

        cfg = self.config.config if hasattr(self.config, 'config') else {}
        monitor_cfg = cfg.get("monitor", {}).get("config", {})

        # 微信：开关在 config.yaml，webhook_url 在 .env
        if monitor_cfg.get("wechat_enabled"):
            webhook_url = os.getenv("WECHAT_WEBHOOK_URL", "")
            if webhook_url:
                try:
                    from modules.monitor.alerters.wechat_alerter import WechatAlerter
                    alerter = WechatAlerter({"webhook_url": webhook_url})
                    self._alert_manager.register_alerter("wechat", alerter)
                    logger.info("WechatAlerter 已注册")
                except ImportError as e:
                    logger.warning(f"WechatAlerter 导入失败: {e}")
            else:
                logger.warning("wechat_enabled=true 但 .env 中 WECHAT_WEBHOOK_URL 为空，跳过")

        # 钉钉：开关在 config.yaml，webhook_url 在 .env
        if monitor_cfg.get("dingtalk_enabled"):
            webhook_url = os.getenv("DINGTALK_WEBHOOK_URL", "")
            if webhook_url:
                try:
                    from modules.monitor.alerters.dingtalk_alerter import DingtalkAlerter
                    alerter = DingtalkAlerter({
                        "webhook_url": webhook_url,
                        "secret": os.getenv("DINGTALK_SECRET", ""),
                    })
                    self._alert_manager.register_alerter("dingtalk", alerter)
                    logger.info("DingtalkAlerter 已注册")
                except ImportError as e:
                    logger.warning(f"DingtalkAlerter 导入失败: {e}")
            else:
                logger.warning("dingtalk_enabled=true 但 .env 中 DINGTALK_WEBHOOK_URL 为空，跳过")

    async def _on_stop(self) -> None:
        logger.info("告警引擎停止")
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
            self._process_task = None

    async def _process_loop(self) -> None:
        """处理告警事件队列"""
        while self.record.status.value == "running":
            try:
                alert_data = await asyncio.wait_for(
                    self._event_queue.get(), timeout=5.0
                )
                await self._process_alert(alert_data)
                self._event_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"告警处理异常: {e}")

    async def _process_alert(self, alert_data: Dict[str, Any]) -> None:
        """处理单个告警"""
        session = None
        if self._db_session_factory:
            try:
                session = await self._db_session_factory()
            except Exception as e:
                logger.error(f"获取会话失败: {e}")
                return

        if not session:
            logger.warning("无数据库会话，告警无法持久化")
            return

        try:
            result = await self._alert_manager.create_and_dispatch(
                session=session,
                alert_type=alert_data.get("alert_type", "system_error"),
                alert_level=alert_data.get("alert_level", AlertLevel.WARNING.value),
                title=alert_data.get("title", "未知告警"),
                message=alert_data.get("message", ""),
                source_module=alert_data.get("source_module", "monitor"),
                channels=alert_data.get("channels"),
                metadata=alert_data.get("metadata"),
            )

            alert_id = result.get("alert_id")
            if alert_id:
                created_event = AlertMonitorEvent.alert_created(
                    alert_id=alert_id,
                    alert_type=AlertType(alert_data.get("alert_type", "system_error")),
                    alert_level=AlertLevel(alert_data.get("alert_level", AlertLevel.WARNING.value)),
                    title=alert_data.get("title", ""),
                    message=alert_data.get("message", ""),
                )
                await self._publish_event(
                    created_event.event_type, created_event.data
                )

                for ch, status in result.get("dispatch", {}).get("results", {}).items():
                    if status == "sent":
                        sent_event = AlertMonitorEvent.notification_sent(alert_id, [ch])
                        await self._publish_event(sent_event.event_type, sent_event.data)
                    elif status == "failed":
                        failed_event = AlertMonitorEvent.notification_failed(
                            alert_id, ch, "发送失败"
                        )
                        await self._publish_event(failed_event.event_type, failed_event.data)

        except Exception as e:
            logger.error(f"告警处理失败: {e}")
        finally:
            pass  # session 生命周期由 factory 管理

    async def trigger_alert(
        self,
        alert_type: str,
        alert_level: str,
        title: str,
        message: str,
        source_module: str = "monitor",
        channels: Optional[list] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        外部触发告警（由 handlers 调用）

        Returns:
            alert_id 或 None（若去重导致跳过）
        """
        session = None
        if self._db_session_factory:
            try:
                session = await self._db_session_factory()
            except (OSError, asyncio.TimeoutError):
                return None

        if not session:
            return None

        try:
            result = await self._alert_manager.create_and_dispatch(
                session=session,
                alert_type=alert_type,
                alert_level=alert_level,
                title=title,
                message=message,
                source_module=source_module,
                channels=channels,
                metadata=metadata,
            )
            return result.get("alert_id")
        except Exception as e:
            logger.error(f"手动触发告警失败: {e}")
            return None

    async def _handle_risk_alert(self, event) -> None:
        """处理风险告警事件"""
        data = event.data if hasattr(event, 'data') else event.get('data', {})
        await self._event_queue.put({
            "alert_type": "risk_trigger",
            "alert_level": data.get("level", AlertLevel.WARNING.value),
            "title": f"[{data.get('level', 'warning')}] 风险预警 - {data.get('risk_type', 'unknown')}",
            "message": data.get("message", ""),
            "source_module": "monitor.risk_monitor",
            "metadata": data,
        })

    async def _handle_system_alert(self, event) -> None:
        """处理系统健康变化事件"""
        data = event.data if hasattr(event, 'data') else event.get('data', {})
        alert_level = data.get("new_status", AlertLevel.WARNING.value)
        if alert_level not in ("warning", "critical"):
            return

        await self._event_queue.put({
            "alert_type": "system_error",
            "alert_level": alert_level,
            "title": f"[{alert_level}] 系统健康变化 - {data.get('component', 'unknown')}",
            "message": data.get("message", ""),
            "source_module": "monitor.system_monitor",
            "metadata": data,
        })

    async def _handle_trading_signal(self, event) -> None:
        """处理交易信号事件 → 推送微信/钉钉通知"""
        data = event.data if hasattr(event, 'data') else event.get('data', {})

        # 从信号数据构建通知内容
        strategy_name = data.get("strategy_name", "未知策略")
        ts_code = data.get("ts_code", "")
        direction = data.get("direction", data.get("signal_direction", ""))
        signal_type = data.get("signal_type", "")
        price = data.get("price", 0)
        price_low = data.get("price_limit_low", price)
        price_high = data.get("price_limit_high", price)
        quantity = data.get("quantity", 0)
        confidence = data.get("confidence", 1.0)
        reason = data.get("reason", "")
        slippage = data.get("max_slippage_pct", 0.02)
        signal_id = data.get("signal_id", "")
        timestamp = data.get("timestamp", data.get("generation_time", ""))

        # 构建确认 URL
        confirm_url = f"/signals/{signal_id}" if signal_id else ""

        title = f"[info] 交易信号 - {strategy_name}"
        message = (
            f"策略: {strategy_name}\n"
            f"股票: {ts_code}\n"
            f"方向: {direction}\n"
            f"信号类型: {signal_type}\n"
            f"参考价格: {price}\n"
            f"价格区间: {price_low} ~ {price_high}\n"
            f"最大滑点: {slippage * 100:.1f}%\n"
            f"建议数量: {quantity}股\n"
            f"置信度: {confidence}\n"
            f"原因: {reason}\n"
            f"时间: {timestamp}\n"
            f"---\n"
            f"请在交易时段操作后标记: {confirm_url}"
        )

        await self._event_queue.put({
            "alert_type": AlertType.TRADING_SIGNAL.value,
            "alert_level": AlertLevel.INFO.value,
            "title": title,
            "message": message,
            "source_module": "trade.signal_engine",
            "channels": ["wechat"],  # 交易信号默认推送微信
            "metadata": data,
        })
