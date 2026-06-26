# -*- coding: utf-8 -*-
"""
风险管理器（兼容包装）

v2.0: 规则管理逻辑已迁移到 modules.risk.engines.risk_engine.RiskEngine。
本文件保留向后兼容接口，实际委托给 RiskEngine。

RiskManager 继续提供：
- 规则启用/禁用状态查询
- 风险事件收集与发布
- 向后兼容的 API
"""

import logging
from typing import Any, Dict, List, Optional

from core.engines.system import EventEngine

logger = logging.getLogger(__name__)


class RiskManager:
    """风险管理器 — 兼容包装，委托给 modules.risk"""

    def __init__(
        self,
        config: Dict[str, Any],
        event_engine: Optional[EventEngine] = None,
    ):
        self.config = config
        self.event_engine = event_engine
        self.risk_events: List[Dict[str, Any]] = []

        # 规则启用状态（兼容旧配置）
        self.risk_rules = {
            "position_limit": config.get("position_limit", True),
            "loss_limit": config.get("loss_limit", True),
            "blacklist": config.get("blacklist", True),
            "market_blacklist": config.get("market_blacklist", True),
            "sector_blacklist": config.get("sector_blacklist", True),
            "liquidity": config.get("liquidity", True),
            "account_balance": config.get("account_balance", True),
            "single_position_limit": config.get("single_position_limit", True),
            "position_concentration": config.get("position_concentration", True),
            "drawdown_limit": config.get("drawdown_limit", True),
            "capital_change": config.get("capital_change", True),
            "price": config.get("price", True),
            "volatility": config.get("volatility", True),
            "market_status": config.get("market_status", True),
        }

        self._risk_engine = None  # 延迟绑定
        self._registered_rules: List = []

    def bind_risk_engine(self, risk_engine) -> None:
        """绑定到 modules.risk 的 RiskEngine 实例"""
        self._risk_engine = risk_engine

    def load_default_rules(self) -> None:
        """
        加载默认风控规则实例。

        v2.0: 委托给 RiskEngine 处理。如果 RiskEngine 未绑定，
        则回退到旧方式（从 trade/rules 导入，与迁移前的规则保持一致）。
        """
        if self._risk_engine:
            # 同步规则状态
            for rule in self._risk_engine.get_all_rules():
                name = rule["name"]
                if name in self.risk_rules:
                    self._risk_engine.update_rule_status(
                        name, self.risk_rules[name]
                    )
            return

        # 回退：直接从 trade/rules 加载（规则文件尚未迁移时）
        if self._registered_rules:
            return
        try:
            from modules.trade.rules.position_rules import (
                PositionLimitRule,
                SinglePositionLimitRule,
                PositionConcentrationRule,
            )
            from modules.trade.rules.account_rules import (
                AccountBalanceRule,
                LossLimitRule,
                DrawdownLimitRule,
                CapitalChangeRule,
            )
            from modules.trade.rules.blacklist_rules import (
                BlacklistRule,
                MarketBlacklistRule,
                SectorBlacklistRule,
            )
            from modules.trade.rules.market_rules import (
                LiquidityRule,
                PriceRule,
                VolatilityRule,
                MarketStatusRule,
            )

            self._registered_rules = [
                PositionLimitRule(),
                SinglePositionLimitRule(),
                PositionConcentrationRule(),
                AccountBalanceRule(),
                LossLimitRule(),
                DrawdownLimitRule(),
                CapitalChangeRule(),
                BlacklistRule(),
                MarketBlacklistRule(),
                SectorBlacklistRule(),
                LiquidityRule(),
                PriceRule(),
                VolatilityRule(),
                MarketStatusRule(),
            ]
        except ImportError as e:
            logger.warning("加载风控规则失败: %s", e)

    def get_enabled_rules(self) -> List:
        """获取已启用的规则实例"""
        if self._risk_engine:
            return self._risk_engine.get_enabled_rules()
        return [
            rule for rule in self._registered_rules
            if self.is_rule_enabled(rule.get_name())
        ]

    def get_risk_rules(self) -> Dict[str, bool]:
        """获取规则启用状态"""
        return dict(self.risk_rules)

    def update_risk_rule(self, rule_name: str, enabled: bool) -> bool:
        """更新规则启用状态"""
        if rule_name in self.risk_rules:
            self.risk_rules[rule_name] = enabled
            if self._risk_engine:
                self._risk_engine.update_rule_status(rule_name, enabled)
            return True
        return False

    def add_risk_event(self, event: Dict[str, Any]) -> None:
        """添加风险事件并发布"""
        self.risk_events.append(event)
        if self.event_engine:
            try:
                from modules.risk.events.risk_events import RiskAlertTriggeredEvent
                self.event_engine.put(RiskAlertTriggeredEvent(
                    risk_type=event.get("risk_type", "unknown"),
                    message=event.get("message", ""),
                    metadata=event,
                ))
            except ImportError:
                pass

    def get_risk_events(self, level: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取风险事件"""
        events = self.risk_events
        if level:
            events = [e for e in events if e.get("level") == level]
        return events

    def clear_risk_events(self) -> None:
        """清除风险事件"""
        self.risk_events.clear()

    def is_rule_enabled(self, rule_name: str) -> bool:
        """检查规则是否启用"""
        return self.risk_rules.get(rule_name, False)
