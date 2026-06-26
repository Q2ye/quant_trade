# -*- coding: utf-8 -*-
"""
风险控制引擎（兼容包装）

v2.0: 本模块已是兼容层，实际实现委托给 modules.risk.engines.risk_engine.RiskEngine。

保留此文件是为了：
1. trade 模块内部 import 路径不变（trade.engines.risk_engine.RiskEngine）
2. 旧代码无需修改即可使用新的统一 RiskEngine
"""

import logging

logger = logging.getLogger(__name__)

# 从新位置重新导出，保持向后兼容
from modules.risk.engines.risk_engine import RiskEngine  # noqa: F401, E402

logger.debug("RiskEngine 已从 modules.risk 重新导出（兼容包装）")
