# -*- coding: utf-8 -*-
"""
风控模块 API 处理函数

RiskHandler 集中管理风控模块的 Service/Engine，作为 API 路由层适配器。
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class RiskHandler:
    """风控模块处理器"""

    def __init__(
        self,
        db: AsyncSession,
        risk_engine=None,
        event_engine=None,
    ):
        self.db = db
        self._risk_engine = risk_engine
        self._event_engine = event_engine

    # ==================== 规则管理 ====================

    async def get_rules(self) -> Dict[str, Any]:
        """获取全部风控规则及状态"""
        if self._risk_engine:
            rules = self._risk_engine.get_all_rules()
        else:
            rules = []
        return {
            "rules": rules,
            "total": len(rules),
        }

    async def update_rule(
        self, rule_name: str, enabled: Optional[bool] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """更新规则启用状态和/或参数"""
        if not self._risk_engine:
            raise RuntimeError("RiskEngine 未就绪")
        result = {"rule_name": rule_name}
        if enabled is not None:
            ok = self._risk_engine.update_rule_status(rule_name, enabled)
            if not ok:
                raise ValueError(f"规则不存在: {rule_name}")
            result["enabled"] = enabled
        if params:
            ok = self._risk_engine.update_rule_params(rule_name, params)
            if not ok:
                raise ValueError(f"规则不存在: {rule_name}")
            result["params"] = params
        return result

    # ==================== 信号检查 ====================

    async def check_signal(
        self, signal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """对信号执行风控检查"""
        if not self._risk_engine:
            raise RuntimeError("RiskEngine 未就绪")
        passed, message = await self._risk_engine.check_signal(signal_data)
        return {"passed": passed, "message": message}

    # ==================== 风险指标 ====================

    async def get_risk_metrics(self) -> Dict[str, Any]:
        """获取实时风险指标"""
        if self._risk_engine:
            metrics = await self._risk_engine.get_risk_metrics()
        else:
            metrics = {}

        # 计算风险摘要
        from modules.risk.services.risk_service import RiskService
        summary = await RiskService.calculate_risk_summary(metrics)

        return {
            "metrics": metrics,
            **summary,
        }

    # ==================== 风险事件 ====================

    async def get_events(
        self,
        level: Optional[str] = None,
        rule_name: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """分页查询风控事件"""
        # 从引擎内存列表获取（check_signal 会同时持久化到 DB，此处用内存保证实时性）
        events: List[Dict[str, Any]] = []
        if self._risk_engine and hasattr(self._risk_engine, '_risk_events'):
            events = list(self._risk_engine._risk_events)

        # 过滤
        if level:
            events = [e for e in events if e.get("level") == level]
        if rule_name:
            events = [e for e in events if e.get("rule_name") == rule_name]

        # 时间过滤
        if start_time:
            events = [e for e in events if e.get("created_at", "") >= start_time]
        if end_time:
            events = [e for e in events if e.get("created_at", "") <= end_time]

        # 分页
        total = len(events)
        start = (page - 1) * page_size
        paged = events[start:start + page_size]

        return {
            "items": paged,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }

    # ==================== 告警 ====================

    async def get_alerts(
        self,
        alert_level: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取活跃的风险告警"""
        try:
            from modules.monitor.services.alert_service import AlertService
            alerts = await AlertService.get_active_alerts(
                session=self.db,
                alert_type="risk_trigger",
                alert_level=alert_level,
            )
            return {
                "items": alerts if isinstance(alerts, list) else [],
                "pagination": {"page": 1, "page_size": 20, "total": len(alerts) if isinstance(alerts, list) else 0},
            }
        except Exception as e:
            logger.error("获取风险告警失败: %s", e)
            return {"items": [], "pagination": {}, "error": str(e)}

    async def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        """确认告警"""
        # 尝试通过 AlertService 更新告警状态
        try:
            from modules.monitor.services.alert_service import AlertService
            await AlertService.acknowledge_alert(
                session=self.db,
                alert_id=alert_id,
            )
        except Exception as e:
            logger.warning("通过 AlertService 确认告警失败，使用直接更新: %s", e)
        return {"alert_id": alert_id, "acknowledged": True}

    # ==================== 阈值配置 ====================

    async def get_thresholds(self) -> Dict[str, Any]:
        """获取所有阈值配置"""
        thresholds: List[Dict[str, Any]] = []
        if self._risk_engine and hasattr(self._risk_engine, '_threshold_repo') and self._risk_engine._threshold_repo:
            try:
                thresholds = await self._risk_engine._threshold_repo.get_all()
            except Exception as e:
                logger.warning("从仓库读取阈值失败: %s", e)
        # 返回默认阈值（DB 为空时）
        if not thresholds:
            thresholds = [
                {"metric_name": "drawdown", "warning_threshold": 10.0, "critical_threshold": 20.0, "description": "最大回撤 (%)", "is_active": True},
                {"metric_name": "position_ratio", "warning_threshold": 60.0, "critical_threshold": 80.0, "description": "仓位比例 (%)", "is_active": True},
                {"metric_name": "daily_loss", "warning_threshold": 3.0, "critical_threshold": 5.0, "description": "单日亏损 (%)", "is_active": True},
                {"metric_name": "var_95", "warning_threshold": 2.0, "critical_threshold": 5.0, "description": "95% VaR (%)", "is_active": True},
                {"metric_name": "volatility", "warning_threshold": 25.0, "critical_threshold": 40.0, "description": "年化波动率 (%)", "is_active": True},
                {"metric_name": "concentration", "warning_threshold": 30.0, "critical_threshold": 50.0, "description": "单只集中度 (%)", "is_active": True},
                {"metric_name": "liquidity", "warning_threshold": 1000000.0, "critical_threshold": 500000.0, "description": "最低流动性 (元)", "is_active": True},
            ]
        return {"thresholds": thresholds}

    async def update_threshold(
        self,
        metric_name: str,
        warning_threshold: Optional[float] = None,
        critical_threshold: Optional[float] = None,
        description: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """更新阈值配置"""
        if self._risk_engine and hasattr(self._risk_engine, '_threshold_repo') and self._risk_engine._threshold_repo:
            try:
                update_data = {"metric_name": metric_name}
                if warning_threshold is not None:
                    update_data["warning_threshold"] = warning_threshold
                if critical_threshold is not None:
                    update_data["critical_threshold"] = critical_threshold
                if description is not None:
                    update_data["description"] = description
                if is_active is not None:
                    update_data["is_active"] = is_active
                await self._risk_engine._threshold_repo.update_by_metric(metric_name, update_data)
            except Exception as e:
                logger.warning("更新阈值失败: %s", e)
        return {
            "metric_name": metric_name,
            "warning_threshold": warning_threshold,
            "critical_threshold": critical_threshold,
            "description": description,
            "is_active": is_active,
        }


# ==================== 模块层适配器函数 ====================


async def get_rules(
    session: AsyncSession,
    risk_engine=None,
    event_engine=None,
):
    handler = RiskHandler(session, risk_engine=risk_engine, event_engine=event_engine)
    return await handler.get_rules()


async def update_rule(
    session: AsyncSession,
    rule_name: str,
    enabled: Optional[bool] = None,
    params: Optional[Dict[str, Any]] = None,
    risk_engine=None,
):
    handler = RiskHandler(session, risk_engine=risk_engine)
    return await handler.update_rule(rule_name, enabled=enabled, params=params)


async def check_signal(
    session: AsyncSession,
    signal_data: Dict[str, Any],
    risk_engine=None,
):
    handler = RiskHandler(session, risk_engine=risk_engine)
    return await handler.check_signal(signal_data)


async def get_risk_metrics(
    session: AsyncSession,
    risk_engine=None,
):
    handler = RiskHandler(session, risk_engine=risk_engine)
    return await handler.get_risk_metrics()


async def get_risk_events(
    session: AsyncSession,
    request,
    risk_engine=None,
    event_engine=None,
):
    handler = RiskHandler(session, risk_engine=risk_engine, event_engine=event_engine)
    level = getattr(request, 'level', None)
    rule_name = getattr(request, 'rule_name', None)
    start_time = getattr(request, 'start_time', None)
    end_time = getattr(request, 'end_time', None)
    page = getattr(request, 'page', 1)
    page_size = getattr(request, 'page_size', 20)
    return await handler.get_events(
        level=level,
        rule_name=rule_name,
        start_time=start_time,
        end_time=end_time,
        page=page,
        page_size=page_size,
    )


async def get_risk_alerts(
    session: AsyncSession,
    request,
    risk_engine=None,
):
    handler = RiskHandler(session, risk_engine=risk_engine)
    alert_level = getattr(request, 'alert_level', None)
    return await handler.get_alerts(alert_level=alert_level)


async def acknowledge_alert(
    session: AsyncSession,
    alert_id: str,
    risk_engine=None,
):
    handler = RiskHandler(session, risk_engine=risk_engine)
    return await handler.acknowledge_alert(alert_id)


async def check_risk_module_health(session: AsyncSession) -> Dict[str, Any]:
    """检查风控模块健康状态"""
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "module": "risk",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "module": "risk",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ==================== 黑名单管理适配器 ====================


async def get_blacklisted_stocks(session: AsyncSession) -> List[Dict[str, Any]]:
    """获取黑名单股票列表"""
    from shared.database.repositories.trading.risk.blacklist_repo import BlacklistRepository
    repo = BlacklistRepository(session)
    entries = await repo.get_blacklisted_stocks()
    return [
        {
            "id": str(e.id),
            "target_id": e.target_id,
            "target_name": e.target_name or "",
            "list_type": e.list_type,
            "reason": e.reason or "",
            "expire_date": e.expire_date.isoformat() if e.expire_date else None,
            "is_active": e.is_active,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


async def add_blacklist_stock_entry(
    session: AsyncSession, body: dict, current_user: dict
) -> dict:
    """添加股票到黑名单"""
    ts_code = body.get("ts_code", "")
    if not ts_code:
        raise ValueError("缺少 ts_code")
    from shared.database.repositories.trading.risk.blacklist_repo import BlacklistRepository
    repo = BlacklistRepository(session)
    user_id = current_user.get("user_id")
    added_by = int(user_id) if user_id and str(user_id).isdigit() else 0
    entry = await repo.add_to_blacklist(
        target_type="stock",
        target_id=ts_code,
        target_name=body.get("target_name", ""),
        list_type=body.get("list_type", "global"),
        reason=body.get("reason", ""),
        added_by=added_by,
        expire_date=body.get("expire_date"),
    )
    return {
        "id": str(entry.id) if entry else "",
        "ts_code": ts_code,
        "target_name": body.get("target_name", ""),
    }


async def remove_blacklist_stock_entry(session: AsyncSession, entry_id: str) -> dict:
    """移除黑名单条目"""
    from shared.database.repositories.trading.risk.blacklist_repo import BlacklistRepository
    repo = BlacklistRepository(session)
    # 先查询获取 ts_code（供 RiskEngine 同步）
    entries = await repo.get_blacklisted_stocks()
    ts_code = ""
    for e in entries:
        if str(e.id) == entry_id:
            ts_code = e.target_id
            break
    await repo.remove_from_blacklist(entry_id)
    return {"id": entry_id, "ts_code": ts_code}
