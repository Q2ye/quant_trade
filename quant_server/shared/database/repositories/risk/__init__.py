# quant_server/shared/database/repositories/risk/__init__.py
"""
风控领域Repository包初始化
"""
from .risk_rule_repo import RiskRuleRepository
from .risk_event_repo import RiskEventRepository
from .blacklist_repo import BlacklistRepository
from .limit_repo import LimitRepository

__all__ = [
    "RiskRuleRepository",
    "RiskEventRepository",
    "BlacklistRepository",
    "LimitRepository"
]