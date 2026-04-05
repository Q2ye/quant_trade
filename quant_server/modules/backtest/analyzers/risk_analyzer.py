# -*- coding: utf-8 -*-
"""
风险分析器

负责分析策略的风险指标
"""
import logging
from typing import Dict, List, Any
import numpy as np

logger = logging.getLogger(__name__)


class RiskAnalyzer:
    """
    风险分析器
    
    负责分析策略的风险指标
    """
    
    def __init__(self):
        """
        初始化风险分析器
        """
        pass
    
    def analyze(self, metrics: Dict[str, Any], equity_curve: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析风险指标
        
        Args:
            metrics: 基础绩效指标
            equity_curve: 净值曲线
            
        Returns:
            详细风险分析结果
        """
        try:
            logger.info("开始风险分析")
            
            # 计算基础风险指标
            risk = {
                "max_drawdown": metrics.get("max_drawdown", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0)
            }
            
            # 计算基于净值曲线的风险指标
            if equity_curve:
                risk.update(self._analyze_equity_curve(equity_curve))
            
            # 计算其他风险指标
            risk.update(self._calculate_other_risk_metrics(metrics))
            
            logger.info("风险分析完成")
            
            return risk
        except Exception as e:
            logger.error(f"风险分析失败: {str(e)}")
            return {}
    
    def _analyze_equity_curve(self, equity_curve: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析净值曲线
        
        Args:
            equity_curve: 净值曲线
            
        Returns:
            基于净值曲线的风险指标
        """
        # 提取净值数据
        equity = [item["equity"] for item in equity_curve]
        
        # 计算收益率
        returns = []
        for i in range(1, len(equity)):
            ret = (equity[i] - equity[i-1]) / equity[i-1]
            returns.append(ret)
        
        # 计算风险指标
        if returns:
            # 波动率
            volatility = np.std(returns) * np.sqrt(252)  # 年化波动率
            
            # 下行偏差
            downside_returns = [r for r in returns if r < 0]
            downside_deviation = np.std(downside_returns) * np.sqrt(252) if downside_returns else 0
            
            # 最大回撤
            max_drawdown = self._calculate_max_drawdown(equity)
            
            # 回撤持续时间
            drawdown_duration = self._calculate_drawdown_duration(equity_curve)
            
            # VaR (Value at Risk)
            var_95 = np.percentile(returns, 5) * np.sqrt(252)  # 95% VaR
            
            # CVaR (Conditional Value at Risk)
            cvar_95 = np.mean([r for r in returns if r <= var_95]) * np.sqrt(252) if returns else 0
            
            return {
                "volatility": volatility,
                "downside_deviation": downside_deviation,
                "max_drawdown": max_drawdown,
                "drawdown_duration": drawdown_duration,
                "var_95": var_95,
                "cvar_95": cvar_95
            }
        else:
            return {
                "volatility": 0,
                "downside_deviation": 0,
                "max_drawdown": 0,
                "drawdown_duration": 0,
                "var_95": 0,
                "cvar_95": 0
            }
    
    def _calculate_max_drawdown(self, equity: List[float]) -> float:
        """
        计算最大回撤
        
        Args:
            equity: 净值序列
            
        Returns:
            最大回撤
        """
        if not equity:
            return 0
        
        peak = equity[0]
        max_drawdown = 0
        
        for value in equity[1:]:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        return max_drawdown
    
    def _calculate_drawdown_duration(self, equity_curve: List[Dict[str, Any]]) -> int:
        """
        计算最大回撤持续时间
        
        Args:
            equity_curve: 净值曲线
            
        Returns:
            最大回撤持续时间（天）
        """
        if not equity_curve:
            return 0
        
        equity = [item["equity"] for item in equity_curve]
        dates = [item["date"] for item in equity_curve]
        
        peak = 0
        peak_date = dates[0]
        max_duration = 0
        current_duration = 0
        
        for i, value in enumerate(equity):
            if value > equity[peak]:
                peak = i
                peak_date = dates[i]
                current_duration = 0
            else:
                current_duration = (dates[i] - peak_date).days if hasattr(dates[i], "days") else 0
                if current_duration > max_duration:
                    max_duration = current_duration
        
        return max_duration
    
    def _calculate_other_risk_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算其他风险指标
        
        Args:
            metrics: 基础绩效指标
            
        Returns:
            其他风险指标
        """
        annualized_return = metrics.get("annualized_return", 0)
        volatility = metrics.get("volatility", 1)
        max_drawdown = metrics.get("max_drawdown", 1)
        
        # 计算风险调整收益指标
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
        sortino_ratio = annualized_return / np.sqrt(metrics.get("downside_deviation", 1)) if metrics.get("downside_deviation", 0) > 0 else 0
        calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # 计算beta值（假设基准收益率为0）
        beta = metrics.get("beta", 0)
        
        # 计算alpha值（假设基准收益率为0，无风险利率为0）
        alpha = annualized_return - beta * 0  # 基准收益率为0
        
        return {
            "sharpe_ratio": sharpe_ratio,
            "sortino_ratio": sortino_ratio,
            "calmar_ratio": calmar_ratio,
            "beta": beta,
            "alpha": alpha
        }