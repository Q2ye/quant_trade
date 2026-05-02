# -*- coding: utf-8 -*-
"""
回测模块业务 DTO（数据传输对象）

纯数据类，用于 Engine → Service → Handler 之间传递领域数据。
区别于：
- schemas.py: API 层 Pydantic 请求/响应模型
- shared/database/models/: SQLAlchemy ORM 模型
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class BacktestConfig:
    """回测运行配置（解析后的领域对象）"""
    name: str
    strategy_id: str
    start_date: date
    end_date: date
    initial_capital: Decimal = Decimal("1000000.00")
    commission_rate: Decimal = Decimal("0.0003")
    slippage_rate: Decimal = Decimal("0.0001")
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestProgress:
    """回测执行进度"""
    task_id: str
    status: str  # pending / running / completed / failed / cancelled
    progress_pct: float = 0.0
    current_date: Optional[date] = None
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    message: str = ""


@dataclass
class BacktestResult:
    """回测结果（领域对象）"""
    task_id: str
    strategy_id: str
    start_date: date
    end_date: date
    # 收益指标
    total_return: Decimal = Decimal("0")
    annual_return: Decimal = Decimal("0")
    # 风险指标
    volatility: Decimal = Decimal("0")
    sharpe_ratio: Decimal = Decimal("0")
    max_drawdown: Decimal = Decimal("0")
    # 交易统计
    total_trades: int = 0
    win_rate: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")
    # 曲线数据
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    drawdown_curve: List[Dict[str, Any]] = field(default_factory=list)
    daily_returns: List[float] = field(default_factory=list)
    # 其他
    benchmark_return: Optional[Decimal] = None
    created_at: Optional[datetime] = None


@dataclass
class OptimizationConfig:
    """参数优化配置"""
    strategy_id: str
    parameter_ranges: Dict[str, Any]  # {"param_name": {"min": 1, "max": 100, "step": 1}}
    optimization_method: str = "grid"  # grid / bayesian / genetic
    objective_metric: str = "sharpe_ratio"
    max_iterations: int = 100
    population_size: int = 50  # 遗传算法用
    early_stopping_rounds: int = 10  # 贝叶斯优化用


@dataclass
class OptimizationResult:
    """参数优化结果"""
    task_id: str
    strategy_id: str
    best_parameters: Dict[str, Any] = field(default_factory=dict)
    best_score: Decimal = Decimal("0")
    optimization_method: str = "grid"
    total_combinations: int = 0
    evaluated_combinations: int = 0
    all_results: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0
