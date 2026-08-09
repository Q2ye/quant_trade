# -*- coding: utf-8 -*-
"""组合实盘 — Pydantic 模型"""
from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field


# =============================================================================
# 组合分组
# =============================================================================

class StrategyCompositeConfigItem(BaseModel):
    """组合中单个策略的配置"""
    strategy_id: str = Field(..., description="策略 ID")
    allocator_id: str = Field(default="", description="分配器权重键，默认等于 strategy_id")


class CompositeGroupCreate(BaseModel):
    """创建组合分组"""
    name: str = Field(..., description="组合名称")
    account_id: Optional[str] = Field(default=None, description="关联券商账户 ID")
    strategy_configs: List[StrategyCompositeConfigItem] = Field(..., min_length=2, description="策略配置")
    allocator_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="分配器配置")


class CompositeGroupUpdate(BaseModel):
    """更新组合分组"""
    name: Optional[str] = Field(default=None, description="组合名称")
    strategy_configs: Optional[List[StrategyCompositeConfigItem]] = Field(default=None, description="策略配置")
    allocator_config: Optional[Dict[str, Any]] = Field(default=None, description="分配器配置")


class CompositeGroupResponse(BaseModel):
    """组合分组响应"""
    id: str
    name: str
    account_id: Optional[str] = None
    strategy_configs: List[Dict[str, Any]] = Field(default_factory=list)
    current_regime: int = 1
    current_allocation: Optional[Dict[str, float]] = None
    status: str = "active"
    last_rebalance_at: Optional[str] = None
    created_at: Optional[str] = None


# =============================================================================
# 组合触发
# =============================================================================

class CompositeTriggerRequest(BaseModel):
    """组合触发请求"""
    composite_group_id: str = Field(..., description="组合分组 ID")
    trade_date: str = Field(..., description="交易日期 YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="结束日期（支持日期范围）")
    symbols: Optional[List[str]] = Field(default=None, description="股票池（null=各自用各自的universe）")


class CompositeTriggerResponse(BaseModel):
    """组合触发响应"""
    success: bool = True
    composite_group_id: str
    trade_date: str
    regime: int
    allocation: Dict[str, float]
    strategies_triggered: List[str]
    skipped_strategies: List[str] = Field(default_factory=list)
    total_signals: int
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    signals: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# Capital 调整
# =============================================================================

class CapitalAdjustRequest(BaseModel):
    """手动调整 allocated_capital"""
    strategy_id: str = Field(..., description="策略 ID")
    new_capital: float = Field(..., ge=10000, description="新 allocated_capital（≥1万）")


class CompositeRebalanceRequest(BaseModel):
    """手动触发 rebalance"""
    composite_group_id: str = Field(..., description="组合分组 ID")


class CompositeRebalanceResponse(BaseModel):
    """Rebalance 响应"""
    success: bool = True
    composite_group_id: str
    regime: int
    previous_allocation: Dict[str, float]
    new_allocation: Dict[str, float]
    capital_changes: List[Dict[str, Any]]  # [{strategy_id, old_capital, new_capital}]


# =============================================================================
# v6.13: 组合成员管理 + 净值
# =============================================================================

class CompositeAddStrategyRequest(BaseModel):
    """组合添加策略"""
    strategy_id: str = Field(..., description="策略 ID")
    allocator_id: str = Field(default="", description="分配器权重键，默认等于 strategy_id")
    w0: float = Field(..., ge=0, le=1, description="熊市(0)权重")
    w1: float = Field(..., ge=0, le=1, description="震荡(1)权重")
    w2: float = Field(..., ge=0, le=1, description="牛市(2)权重")


class CompositeRemoveStrategyRequest(BaseModel):
    """组合移除策略"""
    strategy_id: str = Field(..., description="策略 ID")


class CompositeNavPoint(BaseModel):
    """组合净值点"""
    trade_date: str
    total_nav: float
    daily_return: float
    cash: float
    market_value: float
    regime: int
    allocation: Optional[Dict[str, float]] = None
    per_strategy: Optional[Dict[str, float]] = None
