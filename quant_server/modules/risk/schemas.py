# -*- coding: utf-8 -*-
"""
风控模块 Pydantic Schema

API 请求/响应模型。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ==================== 规则相关 ====================


class RiskRuleResponse(BaseModel):
    """风控规则响应"""
    name: str = Field(..., description="规则名称")
    description: str = Field("", description="规则描述")
    enabled: bool = Field(True, description="是否启用")
    rule_type: str = Field("", description="规则分类（position/account/blacklist/market）")
    params: Dict[str, Any] = Field(default_factory=dict, description="可配置参数")
    inputs: List[str] = Field(default_factory=list, description="所需输入字段")
    action: str = Field("alert", description="触发动作")


class RiskRuleUpdateRequest(BaseModel):
    """更新规则请求"""
    enabled: Optional[bool] = Field(None, description="是否启用")
    params: Optional[Dict[str, Any]] = Field(None, description="要更新的参数")


class RiskRulesListResponse(BaseModel):
    """规则列表响应"""
    success: bool = True
    data: List[RiskRuleResponse] = Field(default_factory=list)
    total: int = 0


# ==================== 信号检查 ====================


class SignalCheckRequest(BaseModel):
    """信号风控检查请求"""
    ts_code: Optional[str] = Field(None, description="股票代码")
    direction: Optional[str] = Field(None, description="买卖方向 buy/sell")
    quantity: Optional[int] = Field(None, description="数量")
    price: Optional[float] = Field(None, description="价格")
    trade_amount: Optional[float] = Field(None, description="交易金额")
    total_asset: Optional[float] = Field(None, description="总资产")
    available_cash: Optional[float] = Field(None, description="可用资金")
    position_value: Optional[float] = Field(None, description="持仓市值")
    initial_capital: Optional[float] = Field(None, description="初始资金")
    peak_asset: Optional[float] = Field(None, description="峰值资产")
    previous_asset: Optional[float] = Field(None, description="前日资产")
    positions: Optional[List[Dict[str, Any]]] = Field(None, description="当前持仓列表")
    market: Optional[str] = Field(None, description="市场")
    sector: Optional[str] = Field(None, description="行业")
    volume: Optional[float] = Field(None, description="成交量")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    close: Optional[float] = Field(None, description="收盘价")
    volatility: Optional[float] = Field(None, description="波动率")
    liquidity: Optional[float] = Field(None, description="流动性")
    market_status: Optional[str] = Field("normal", description="市场状态")


class SignalCheckResponse(BaseModel):
    """信号风控检查响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    # data.passed: bool
    # data.message: str
    # data.violations: List[dict]


# ==================== 风险事件 ====================


class RiskEventResponse(BaseModel):
    """风险事件响应"""
    id: Optional[int] = None
    event_type: str = ""
    rule_name: Optional[str] = None
    metric_name: Optional[str] = None
    current_value: Optional[float] = None
    threshold_value: Optional[float] = None
    level: str = "normal"
    message: str = ""
    signal_data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class RiskEventsListResponse(BaseModel):
    """风险事件分页响应"""
    success: bool = True
    data: List[RiskEventResponse] = Field(default_factory=list)
    pagination: Dict[str, int] = Field(default_factory=lambda: {
        "page": 1, "page_size": 20, "total": 0,
    })


class RiskEventsQueryRequest(BaseModel):
    """风险事件查询请求"""
    level: Optional[str] = Field(None, description="告警级别 warning/critical")
    rule_name: Optional[str] = Field(None, description="规则名称")
    start_time: Optional[str] = Field(None)
    end_time: Optional[str] = Field(None)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ==================== 风险指标 ====================


class RiskMetricsResponse(BaseModel):
    """风险指标响应"""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=lambda: {
        "drawdown": 0.0,
        "position_ratio": 0.0,
        "var": 0.0,
        "volatility": 0.0,
        "sharpe_ratio": 0.0,
        "overall_risk_level": "normal",
        "breach_count": 0,
        "breaches": [],
    })


# ==================== 告警 ====================


class RiskAlertResponse(BaseModel):
    """风险告警响应"""
    id: Optional[str] = None
    alert_type: str = ""
    level: str = "warning"
    title: str = ""
    message: str = ""
    acknowledged: bool = False
    created_at: Optional[datetime] = None


class RiskAlertsListResponse(BaseModel):
    """告警列表响应"""
    success: bool = True
    data: List[RiskAlertResponse] = Field(default_factory=list)
    pagination: Dict[str, int] = Field(default_factory=lambda: {
        "page": 1, "page_size": 20, "total": 0,
    })


# ==================== 阈值配置 ====================


class ThresholdItem(BaseModel):
    """阈值配置项"""
    metric_name: str = Field(..., description="指标名")
    warning_threshold: float = Field(..., description="预警阈值")
    critical_threshold: float = Field(..., description="严重阈值")
    description: str = Field("", description="说明")
    is_active: bool = Field(True, description="是否启用")


class ThresholdUpdateRequest(BaseModel):
    """更新阈值请求"""
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ThresholdListResponse(BaseModel):
    """阈值列表响应"""
    success: bool = True
    data: List[ThresholdItem] = Field(default_factory=list)
