# -*- coding: utf-8 -*-
"""
风险监控服务（兼容包装）

v2.0: 风险评估逻辑已迁移到 modules.risk.services.risk_service.RiskService。
本文件保留向后兼容。
"""

import logging

logger = logging.getLogger(__name__)

# 重新导出
from modules.risk.services.risk_service import RiskService as RiskMonitorService  # noqa: F401, E402

logger.debug("RiskMonitorService 已从 modules.risk 重新导出（兼容包装）")
