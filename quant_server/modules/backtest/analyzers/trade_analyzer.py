# -*- coding: utf-8 -*-
"""
交易分析器

负责分析交易记录
"""
import logging
from typing import Dict, List, Any
import numpy as np

logger = logging.getLogger(__name__)


class TradeAnalyzer:
    """
    交易分析器
    
    负责分析交易记录
    """
    
    def __init__(self):
        """
        初始化交易分析器
        """
        pass
    
    def analyze(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析交易记录
        
        Args:
            trades: 交易记录
            
        Returns:
            交易分析结果
        """
        try:
            logger.info("开始交易分析")
            
            if not trades:
                return {}
            
            # 计算交易统计指标
            analysis = {
                "total_trades": len(trades),
                "total_profit": sum(trade.get("profit", 0) for trade in trades),
                "win_trades": 0,
                "loss_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "max_win": 0.0,
                "max_loss": 0.0
            }
            
            # 计算胜率和盈亏比
            win_amounts = []
            loss_amounts = []
            
            for trade in trades:
                profit = trade.get("profit", 0)
                if profit > 0:
                    analysis["win_trades"] += 1
                    win_amounts.append(profit)
                elif profit < 0:
                    analysis["loss_trades"] += 1
                    loss_amounts.append(abs(profit))
            
            # 计算胜率
            if analysis["total_trades"] > 0:
                analysis["win_rate"] = analysis["win_trades"] / analysis["total_trades"]
            
            # 计算平均盈利和平均亏损
            if win_amounts:
                analysis["avg_win"] = float(np.mean(win_amounts))
                analysis["max_win"] = float(max(win_amounts))
            
            if loss_amounts:
                analysis["avg_loss"] = float(np.mean(loss_amounts))
                analysis["max_loss"] = float(max(loss_amounts))
            
            # 计算盈利因子
            if loss_amounts:
                analysis["profit_factor"] = sum(win_amounts) / sum(loss_amounts)
            
            # 计算交易频率
            analysis.update(self._analyze_trade_frequency(trades))
            
            # 计算持仓时间
            analysis.update(self._analyze_holding_period(trades))
            
            # 计算收益分布
            analysis.update(self._analyze_profit_distribution(trades))
            
            logger.info("交易分析完成")
            
            return analysis
        except Exception as e:
            logger.error(f"交易分析失败: {str(e)}")
            return {}
    
    @staticmethod
    def _analyze_trade_frequency(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析交易频率
        
        Args:
            trades: 交易记录
            
        Returns:
            交易频率分析结果
        """
        if not trades:
            return {}
        
        # 按日期分组
        trade_dates = [trade["datetime"].date() if hasattr(trade["datetime"], "date") else trade["datetime"] for trade in trades]
        date_counts = {}
        for date in trade_dates:
            date_counts[date] = date_counts.get(date, 0) + 1
        
        # 计算日均交易次数
        avg_daily_trades = len(trades) / len(date_counts) if date_counts else 0
        
        return {
            "avg_daily_trades": avg_daily_trades,
            "trading_days": len(date_counts)
        }
    

    @staticmethod
    def _analyze_holding_period(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析持仓时间
        
        Args:
            trades: 交易记录
            
        Returns:
            持仓时间分析结果
        """
        if not trades:
            return {}
        
        # 计算持仓时间
        holding_periods = []
        for trade in trades:
            if "entry_time" in trade and "exit_time" in trade:
                entry_time = trade["entry_time"]
                exit_time = trade["exit_time"]
                if hasattr(exit_time, "timestamp") and hasattr(entry_time, "timestamp"):
                    holding_seconds = exit_time.timestamp() - entry_time.timestamp()
                    holding_periods.append(holding_seconds / 3600)  # 转换为小时
        
        if holding_periods:
            avg_holding = float(np.mean(holding_periods))
            max_holding = float(max(holding_periods))
            min_holding = float(min(holding_periods))
        else:
            avg_holding = 0.0
            max_holding = 0.0
            min_holding = 0.0
        
        return {
            "avg_holding_period": avg_holding,
            "max_holding_period": max_holding,
            "min_holding_period": min_holding
        }
    
    @staticmethod
    def _analyze_profit_distribution(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析收益分布
        
        Args:
            trades: 交易记录
            
        Returns:
            收益分布分析结果
        """
        if not trades:
            return {}
        
        # 提取收益数据
        profits = [trade.get("profit", 0) for trade in trades]
        
        # 计算收益分布统计
        if profits:
            std_profit = float(np.std(profits))
            skewness = float(np.mean(((np.array(profits) - np.mean(profits)) / std_profit) ** 3)) if std_profit > 0 else 0.0
            kurtosis = float(np.mean(((np.array(profits) - np.mean(profits)) / std_profit) ** 4)) if std_profit > 0 else 0.0
        else:
            std_profit = 0.0
            skewness = 0.0
            kurtosis = 0.0
        
        return {
            "std_profit": std_profit,
            "skewness": skewness,
            "kurtosis": kurtosis
        }