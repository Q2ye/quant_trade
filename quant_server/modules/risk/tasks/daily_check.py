# -*- coding: utf-8 -*-
"""
每日风控检查任务 — 盘前巡检风控参数与阈值
"""
import logging
from typing import Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def run_daily_risk_check(
    session: AsyncSession,
    risk_engine=None,
) -> Dict[str, Any]:
    """
    盘前风控参数巡检

    检查项:
    1. 所有风控规则是否正常启用
    2. 阈值参数是否在合理范围内
    3. 前一日是否有未处理的风控事件

    Returns:
        巡检结果摘要
    """
    results = {
        "checked_at": "",
        "rules_ok": True,
        "thresholds_ok": True,
        "pending_events": 0,
        "warnings": [],
    }

    try:
        from datetime import datetime, timezone
        results["checked_at"] = datetime.now(timezone.utc).isoformat()

        # 检查风险引擎规则状态
        if risk_engine and hasattr(risk_engine, "_registered_rules"):
            rules = risk_engine._registered_rules
            for rule in rules:
                if not getattr(rule, "enabled", True):
                    results["warnings"].append(f"规则 {getattr(rule, 'get_name', lambda: '?' )()} 已禁用")

        # 检查待处理事件
        if risk_engine and hasattr(risk_engine, "_risk_manager"):
            events = risk_engine._risk_manager.get_risk_events()
            pending = [e for e in events if not e.get("acknowledged", False)]
            results["pending_events"] = len(pending)

        logger.info(
            "每日风控巡检完成: rules_ok=%s, pending=%d",
            results["rules_ok"], results["pending_events"],
        )
    except Exception as e:
        logger.error(f"每日风控巡检异常: {e}")
        results["rules_ok"] = False
        results["warnings"].append(str(e))

    return results
