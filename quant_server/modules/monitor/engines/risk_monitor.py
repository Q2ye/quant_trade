# -*- coding: utf-8 -*-
"""
风险监控引擎（兼容包装）

v2.0: 周期巡检功能已合并到 modules.risk.engines.risk_engine.RiskEngine。
本文件保留向后兼容，实际委托给 RiskEngine。

保留此文件是为了：
1. monitor 模块内部 import 路径不变
2. 旧代码无需修改即可使用新的统一 RiskEngine
"""

import logging

logger = logging.getLogger(__name__)

# 从新位置重新导出
from modules.risk.engines.risk_engine import RiskEngine as RiskMonitorEngine  # noqa: F401, E402

logger.debug("RiskMonitorEngine 已从 modules.risk 重新导出（兼容包装）")
