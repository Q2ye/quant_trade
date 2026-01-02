#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务异常定义

定义业务逻辑相关的异常，用于处理业务规则违反等场景。
"""

from typing import Any, Dict, Optional
from .base import BaseException
from .error_codes import ErrorCode
from .types import ErrorType, ErrorSeverity


class BusinessException(BaseException):
	"""业务异常基类"""

	def __init__ (
			self,
			message: str,
			error_code: str = ErrorCode.BUSINESS_ERROR,
			business_domain: Optional[str] = None,
			business_rule: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化业务异常

		Args:
			message: 业务错误消息
			error_code: 错误代码
			business_domain: 业务领域
			business_rule: 违反的业务规则
			details: 额外详情
			cause: 原始异常
		"""
		if business_domain or business_rule:
			details = details or {}
			if business_domain:
				details["business_domain"] = business_domain
			if business_rule:
				details["business_rule"] = business_rule

		super().__init__(
			message=message,
			error_code=error_code,
			error_type=ErrorType.BUSINESS_ERROR,
			severity=ErrorSeverity.ERROR,
			details=details,
			cause=cause
		)


class StrategyException(BusinessException):
	"""策略异常"""

	def __init__ (
			self,
			message: str,
			strategy_id: Optional[str] = None,
			strategy_name: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化策略异常

		Args:
			message: 策略错误消息
			strategy_id: 策略ID
			strategy_name: 策略名称
			details: 额外详情
			cause: 原始异常
		"""
		if strategy_id or strategy_name:
			details = details or {}
			if strategy_id:
				details["strategy_id"] = strategy_id
			if strategy_name:
				details["strategy_name"] = strategy_name

		super().__init__(
			message=message,
			error_code=ErrorCode.STRATEGY_ERROR,
			business_domain="events",
			business_rule="strategy_execution",
			details=details,
			cause=cause
		)


class AnalysisException(BusinessException):
	"""分析异常"""

	def __init__ (
			self,
			message: str,
			analysis_type: Optional[str] = None,
			analysis_id: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化分析异常

		Args:
			message: 分析错误消息
			analysis_type: 分析类型
			analysis_id: 分析ID
			details: 额外详情
			cause: 原始异常
		"""
		if analysis_type or analysis_id:
			details = details or {}
			if analysis_type:
				details["analysis_type"] = analysis_type
			if analysis_id:
				details["analysis_id"] = analysis_id

		super().__init__(
			message=message,
			error_code=ErrorCode.ANALYSIS_ERROR,
			business_domain="events",
			business_rule="analysis_calculation",
			details=details,
			cause=cause
		)


class BacktestException(BusinessException):
	"""回测异常"""

	def __init__ (
			self,
			message: str,
			backtest_id: Optional[str] = None,
			strategy_id: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化回测异常

		Args:
			message: 回测错误消息
			backtest_id: 回测ID
			strategy_id: 策略ID
			details: 额外详情
			cause: 原始异常
		"""
		if backtest_id or strategy_id:
			details = details or {}
			if backtest_id:
				details["backtest_id"] = backtest_id
			if strategy_id:
				details["strategy_id"] = strategy_id

		super().__init__(
			message=message,
			error_code=ErrorCode.BACKTEST_ERROR,
			business_domain="events",
			business_rule="backtest_simulation",
			details=details,
			cause=cause
		)


class RiskException(BusinessException):
	"""风控异常"""

	def __init__ (
			self,
			message: str,
			risk_rule: Optional[str] = None,
			risk_level: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化风控异常

		Args:
			message: 风控错误消息
			risk_rule: 风控规则
			risk_level: 风险等级
			details: 额外详情
			cause: 原始异常
		"""
		if risk_rule or risk_level:
			details = details or {}
			if risk_rule:
				details["risk_rule"] = risk_rule
			if risk_level:
				details["risk_level"] = risk_level

		super().__init__(
			message=message,
			error_code=ErrorCode.RISK_ERROR,
			business_domain="risk",
			business_rule="risk_control",
			details=details,
			cause=cause
		)


class AccountException(BusinessException):
	"""账户异常"""

	def __init__ (
			self,
			message: str,
			account_id: Optional[str] = None,
			account_number: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化账户异常

		Args:
			message: 账户错误消息
			account_id: 账户ID
			account_number: 账户号码
			details: 额外详情
			cause: 原始异常
		"""
		if account_id or account_number:
			details = details or {}
			if account_id:
				details["account_id"] = account_id
			if account_number:
				details["account_number"] = account_number

		super().__init__(
			message=message,
			error_code=ErrorCode.ACCOUNT_ERROR,
			business_domain="events",
			business_rule="account_operation",
			details=details,
			cause=cause
		)


class PortfolioException(BusinessException):
	"""投资组合异常"""

	def __init__ (
			self,
			message: str,
			portfolio_id: Optional[str] = None,
			portfolio_name: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化投资组合异常

		Args:
			message: 投资组合错误消息
			portfolio_id: 投资组合ID
			portfolio_name: 投资组合名称
			details: 额外详情
			cause: 原始异常
		"""
		if portfolio_id or portfolio_name:
			details = details or {}
			if portfolio_id:
				details["portfolio_id"] = portfolio_id
			if portfolio_name:
				details["portfolio_name"] = portfolio_name

		super().__init__(
			message=message,
			error_code=ErrorCode.PORTFOLIO_ERROR,
			business_domain="portfolio",
			business_rule="portfolio_management",
			details=details,
			cause=cause
		)


class OrderException(BusinessException):
	"""订单异常"""

	def __init__ (
			self,
			message: str,
			order_id: Optional[str] = None,
			order_type: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化订单异常

		Args:
			message: 订单错误消息
			order_id: 订单ID
			order_type: 订单类型
			details: 额外详情
			cause: 原始异常
		"""
		if order_id or order_type:
			details = details or {}
			if order_id:
				details["order_id"] = order_id
			if order_type:
				details["order_type"] = order_type

		super().__init__(
			message=message,
			error_code=ErrorCode.ORDER_ERROR,
			business_domain="order",
			business_rule="order_processing",
			details=details,
			cause=cause
		)


class PositionNotFoundException(BusinessException):
	"""持仓不存在异常"""

	def __init__ (
			self,
			message: str,
			position_id: Optional[str] = None,
			symbol: Optional[str] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化持仓不存在异常

		Args:
			message: 错误消息
			position_id: 持仓ID
			symbol: 股票代码
			details: 额外详情
			cause: 原始异常
		"""
		if position_id or symbol:
			details = details or {}
			if position_id:
				details["position_id"] = position_id
			if symbol:
				details["symbol"] = symbol

		super().__init__(
			message=message,
			error_code=ErrorCode.POSITION_NOT_FOUND,
			business_domain="position",
			business_rule="position_existence",
			details=details,
			cause=cause
		)


class InsufficientBalanceException(BusinessException):
	"""余额不足异常"""

	def __init__ (
			self,
			message: str,
			account_id: Optional[str] = None,
			required_amount: Optional[float] = None,
			available_amount: Optional[float] = None,
			details: Optional[Dict[str, Any]] = None,
			cause: Optional[Exception] = None
	):
		"""
		初始化余额不足异常

		Args:
			message: 错误消息
			account_id: 账户ID
			required_amount: 所需金额
			available_amount: 可用金额
			details: 额外详情
			cause: 原始异常
		"""
		if account_id or required_amount or available_amount:
			details = details or {}
			if account_id:
				details["account_id"] = account_id
			if required_amount:
				details["required_amount"] = required_amount
			if available_amount:
				details["available_amount"] = available_amount

		super().__init__(
			message=message,
			error_code=ErrorCode.INSUFFICIENT_BALANCE,
			business_domain="events",
			business_rule="balance_sufficiency",
			details=details,
			cause=cause
		)