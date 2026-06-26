# -*- coding: utf-8 -*-
"""
风险监控事件（兼容包装）

v2.0: 风险事件已统一到 modules.risk.events.risk_events（全部继承 BaseEvent）。
本文件保留向后兼容，重新导出新的统一事件。

注意：旧版 RiskMonitorEvent 使用 @dataclass，新版使用 BaseEvent 继承。
如需旧版接口，请直接使用 modules.risk.events 中的事件类。
"""

import logging

logger = logging.getLogger(__name__)

# 重新导出统一事件
from modules.risk.events.risk_events import (  # noqa: F401, E402
    RiskViolationEvent,
    RiskThresholdBreachedEvent,
    RiskAlertTriggeredEvent,
    RiskMetricsUpdatedEvent,
    RiskRuleStatusChangedEvent,
)

# 兼容别名
RiskMonitorEvent = RiskThresholdBreachedEvent

logger.debug("风险事件已从 modules.risk 重新导出（兼容包装）")
