# quant_server/utils/api_utils/rate_limit.py
"""
限流工具模块

提供API请求限流功能，包括：
- 基于令牌桶算法的限流
- 基于用户/IP的限流
- 滑动窗口限流
- 分布式限流支持

Author: 量化交易系统团队
Version: 1.0.0
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Dict, Any, Optional

import redis.asyncio as redis
from fastapi import Request, status
from fastapi.responses import JSONResponse


from quant_server.shared.config.config_manager import ConfigSettings as Settings
from quant_server.utils.api_utils.response_formatter import APIResponse

logger = logging.getLogger(__name__)


class RateLimitStrategy(str, Enum):
	"""限流策略枚举"""
	TOKEN_BUCKET = "token_bucket"  # 令牌桶算法
	SLIDING_WINDOW = "sliding_window"  # 滑动窗口
	FIXED_WINDOW = "fixed_window"  # 固定窗口
	LEAKY_BUCKET = "leaky_bucket"  # 漏桶算法


class RateLimitScope(str, Enum):
	"""限流范围枚举"""
	GLOBAL = "global"  # 全局限流
	USER = "user"  # 用户限流
	IP = "ip"  # IP限流
	ENDPOINT = "endpoint"  # 端点限流


@dataclass
class RateLimitConfig:
	"""限流配置"""

	requests: int = 100  # 请求数量
	period: int = 60  # 时间周期（秒）
	strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
	scope: RateLimitScope = RateLimitScope.USER
	burst: Optional[int] = None  # 突发流量允许的数量
	cost: int = 1  # 每次请求的消耗（用于加权限流）

	def __post_init__ (self):
		"""后初始化处理"""
		if self.burst is None:
			self.burst = self.requests * 2  # 默认突发流量为2倍


@dataclass
class RateLimitResult:
	"""限流结果"""

	allowed: bool  # 是否允许通过
	remaining: int  # 剩余请求数
	limit: int  # 限制数量
	reset_time: float  # 重置时间（Unix时间戳）
	retry_after: Optional[int] = None  # 重试等待时间（秒）


class RateLimiter:
	"""限流器基类"""

	def __init__ (self, config: RateLimitConfig):
		"""
		初始化限流器

		Args:
			config: 限流配置
		"""
		self.config = config
		self.key_prefix = "rate_limit"
		logger.debug(f"限流器初始化: {config}")

	async def check (
			self,
			identifier: str,
			request_cost: int = 1
	) -> RateLimitResult:
		"""
		检查是否允许请求

		Args:
			identifier: 标识符（用户ID、IP等）
			request_cost: 请求成本

		Returns:
			RateLimitResult: 限流结果
		"""
		raise NotImplementedError("子类必须实现check方法")

	def _get_key (self, identifier: str) -> str:
		"""
		获取Redis键名

		Args:
			identifier: 标识符

		Returns:
			str: Redis键名
		"""
		return f"{self.key_prefix}:{self.config.scope.value}:{identifier}"

	def _get_window_key (self, identifier: str, window: int) -> str:
		"""
		获取窗口键名

		Args:
			identifier: 标识符
			window: 窗口编号

		Returns:
			str: 窗口键名
		"""
		return f"{self._get_key(identifier)}:window:{window}"


class RedisRateLimiter(RateLimiter):
	"""Redis限流器（支持分布式限流）"""

	def __init__ (self, config: RateLimitConfig, redis_client: redis.Redis):
		"""
		初始化Redis限流器

		Args:
			config: 限流配置
			redis_client: Redis客户端
		"""
		super().__init__(config)
		self.redis = redis_client

	async def check (self, identifier: str, request_cost: int = 1) -> RateLimitResult:
		"""
		检查是否允许请求（使用Redis）

		Args:
			identifier: 标识符
			request_cost: 请求成本

		Returns:
			RateLimitResult: 限流结果
		"""
		if self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
			return await self._sliding_window_check(identifier, request_cost)
		elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
			return await self._fixed_window_check(identifier, request_cost)
		elif self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
			return await self._token_bucket_check(identifier, request_cost)
		else:
			raise ValueError(f"不支持的限流策略: {self.config.strategy}")

	async def _sliding_window_check (self, identifier: str, request_cost: int) -> RateLimitResult:
		"""滑动窗口限流检查"""
		key = self._get_key(identifier)
		current_time = time.time()
		window_size = self.config.period

		# 使用Redis事务
		async with self.redis.pipeline(transaction=True) as pipe:
			try:
				# 移除过期的时间戳
				pipe.zremrangebyscore(key, 0, current_time - window_size)

				# 获取当前窗口内的请求数
				pipe.zcard(key)

				# 添加当前请求的时间戳
				pipe.zadd(key, {str(current_time): current_time})

				# 设置过期时间
				pipe.expire(key, window_size + 1)

				results = await pipe.execute()
				current_count = results[1]

				# 检查是否超过限制
				allowed = current_count + request_cost <= self.config.requests
				remaining = max(0, self.config.requests - current_count - request_cost)

				# 计算重置时间（最早的时间戳 + 窗口大小）
				if current_count > 0:
					earliest = await self.redis.zrange(key, 0, 0, withscores=True)
					if earliest:
						reset_time = earliest[0][1] + window_size
					else:
						reset_time = current_time + window_size
				else:
					reset_time = current_time + window_size

				return RateLimitResult(
					allowed=allowed,
					remaining=remaining,
					limit=self.config.requests,
					reset_time=reset_time,
					retry_after=None if allowed else int(max(0, int(reset_time) - int(current_time)))
				)

			except Exception as e:
				logger.error(f"滑动窗口限流检查失败: {str(e)}")
				# 出错时允许通过，避免影响正常业务
				return RateLimitResult(
					allowed=True,
					remaining=self.config.requests,
					limit=self.config.requests,
					reset_time=current_time + window_size
				)

	async def _fixed_window_check (self, identifier: str, request_cost: int) -> RateLimitResult:
		"""固定窗口限流检查"""
		key = self._get_key(identifier)
		current_time = time.time()
		window_start = int(current_time // self.config.period) * self.config.period

		window_key = f"{key}:{window_start}"

		try:
			# 使用INCRBY原子操作
			current_count = await self.redis.incrby(window_key, request_cost)

			# 如果是第一次设置，设置过期时间
			if current_count == request_cost:
				await self.redis.expire(window_key, self.config.period + 1)

			# 检查是否超过限制
			allowed = current_count <= self.config.requests
			remaining = max(0, self.config.requests - current_count)

			# 计算重置时间（窗口结束时间）
			reset_time = window_start + self.config.period

			return RateLimitResult(
				allowed=allowed,
				remaining=remaining,
				limit=self.config.requests,
				reset_time=reset_time,
				retry_after=None if allowed else int(max(0, int(reset_time) - int(current_time)))
			)

		except Exception as e:
			logger.error(f"固定窗口限流检查失败: {str(e)}")
			# 出错时允许通过
			return RateLimitResult(
				allowed=True,
				remaining=self.config.requests,
				limit=self.config.requests,
				reset_time=current_time + self.config.period
			)

	async def _token_bucket_check (self, identifier: str, request_cost: int) -> RateLimitResult:
		"""令牌桶限流检查"""
		key = self._get_key(identifier)
		current_time = time.time()

		try:
			# 获取当前令牌桶状态
			bucket_data = await self.redis.hgetall(key)
			retry_after = None

			if not bucket_data:
				# 初始化令牌桶
				tokens = self.config.burst or self.config.requests * 2
				last_refill = current_time
			else:
				tokens = float(bucket_data.get(b'tokens', self.config.requests))
				last_refill = float(bucket_data.get(b'last_refill', current_time))

			# 计算需要补充的令牌
			time_passed = current_time - last_refill
			refill_amount = (time_passed * self.config.requests) / self.config.period
			new_tokens = min(self.config.burst or float('inf'), tokens + refill_amount)

			# 检查是否有足够的令牌
			if new_tokens >= request_cost:
				# 消耗令牌
				new_tokens -= request_cost
				allowed = True
				remaining_tokens = new_tokens
			else:
				# 令牌不足
				allowed = False
				remaining_tokens = new_tokens
				# 计算需要等待的时间
				deficit = request_cost - new_tokens
				refill_time = (deficit * self.config.period) / self.config.requests
				retry_after = int(refill_time)

			# 更新令牌桶
			await self.redis.hset(key, mapping={
				'tokens': remaining_tokens,
				'last_refill': current_time
			})

			# 设置过期时间（防止内存泄漏）
			await self.redis.expire(key, self.config.period * 2)

			return RateLimitResult(
				allowed=allowed,
				remaining=int(remaining_tokens),
				limit=self.config.burst or self.config.requests * 2,
				reset_time=current_time + self.config.period,
				retry_after=retry_after if not allowed else None
			)

		except Exception as e:
			logger.error(f"令牌桶限流检查失败: {str(e)}")
			# 出错时允许通过
			return RateLimitResult(
				allowed=True,
				remaining=self.config.requests,
				limit=self.config.requests,
				reset_time=current_time + self.config.period
			)


class MemoryRateLimiter(RateLimiter):
	"""内存限流器（单机限流）"""

	def __init__ (self, config: RateLimitConfig):
		"""
		初始化内存限流器

		Args:
			config: 限流配置
		"""
		super().__init__(config)
		self._store: Dict[str, Dict[str, Any]] = {}
		self._lock = asyncio.Lock()

	async def check (self, identifier: str, request_cost: int = 1) -> RateLimitResult:
		"""
		检查是否允许请求（使用内存存储）

		Args:
			identifier: 标识符
			request_cost: 请求成本

		Returns:
			RateLimitResult: 限流结果
		"""
		async with self._lock:
			current_time = time.time()
			key = self._get_key(identifier)

			if key not in self._store:
				# 初始化
				self._store[key] = {
					'count': 0,
					'window_start': current_time,
					'tokens': self.config.burst or self.config.requests * 2,
					'last_refill': current_time
				}

			data = self._store[key]

			if self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
				return await self._sliding_window_check_memory(data, request_cost, current_time)
			elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
				return await self._fixed_window_check_memory(data, request_cost, current_time)
			elif self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
				return await self._token_bucket_check_memory(data, request_cost, current_time)
			else:
				raise ValueError(f"不支持的限流策略: {self.config.strategy}")

	async def _window_check_memory (self, data: Dict[str, Any], request_cost: int,
	                               current_time: float) -> RateLimitResult:
		"""内存窗口限流检查（通用）"""
		window_start = int(current_time // self.config.period) * self.config.period

		if data['window_start'] != window_start:
			# 新窗口开始
			data['count'] = 0
			data['window_start'] = window_start

		# 检查是否超过限制
		allowed = data['count'] + request_cost <= self.config.requests

		if allowed:
			data['count'] += request_cost

		remaining = max(0, self.config.requests - data['count'])
		reset_time = window_start + self.config.period

		return RateLimitResult(
			allowed=allowed,
			remaining=remaining,
			limit=self.config.requests,
			reset_time=reset_time,
			retry_after=None if allowed else int(max(0, int(reset_time) - int(current_time)))
		)

	async def _sliding_window_check_memory (self, data: Dict[str, Any], request_cost: int,
	                                        current_time: float) -> RateLimitResult:
		"""内存滑动窗口限流检查"""
		return await self._window_check_memory(data, request_cost, current_time)

	async def _fixed_window_check_memory (self, data: Dict[str, Any], request_cost: int,
	                                      current_time: float) -> RateLimitResult:
		"""内存固定窗口限流检查"""
		return await self._window_check_memory(data, request_cost, current_time)

	async def _token_bucket_check_memory (self, data: Dict[str, Any], request_cost: int,
	                                      current_time: float) -> RateLimitResult:
		"""内存令牌桶限流检查"""
		# 计算需要补充的令牌
		time_passed = current_time - data['last_refill']
		refill_amount = (time_passed * self.config.requests) / self.config.period
		new_tokens = min(self.config.burst or float('inf'), data['tokens'] + refill_amount)
		retry_after = None

		# 检查是否有足够的令牌
		if new_tokens >= request_cost:
			# 消耗令牌
			new_tokens -= request_cost
			allowed = True
			remaining_tokens = new_tokens
		else:
			# 令牌不足
			allowed = False
			remaining_tokens = new_tokens
			# 计算需要等待的时间
			deficit = request_cost - new_tokens
			refill_time = (deficit * self.config.period) / self.config.requests
			retry_after = int(refill_time)

		# 更新数据
		data['tokens'] = remaining_tokens
		data['last_refill'] = current_time

		return RateLimitResult(
			allowed=allowed,
			remaining=int(remaining_tokens),
			limit=self.config.burst or self.config.requests * 2,
			reset_time=current_time + self.config.period,
			retry_after=retry_after if not allowed else None
		)


class RateLimitManager:
	"""限流管理器"""

	def __init__ (self, settings: Settings, redis_client: Optional[redis.Redis] = None):
		"""
		初始化限流管理器

		Args:
			settings: 应用设置
			redis_client: Redis客户端（可选）
		"""
		self.settings = settings
		self.redis_client = redis_client
		self.limiters: Dict[str, RateLimiter] = {}
		self.default_config = RateLimitConfig(
			requests=getattr(settings.API, 'MAX_REQUESTS', 100),
			period=getattr(settings.API, 'PERIOD_SECONDS', 60),
			strategy=RateLimitStrategy.SLIDING_WINDOW,
			scope=RateLimitScope.USER
		)

		logger.info("限流管理器初始化完成")

	def get_limiter (self, config: Optional[RateLimitConfig] = None) -> RateLimiter:
		"""
		获取限流器

		Args:
			config: 限流配置，不传则使用默认配置

		Returns:
			RateLimiter: 限流器实例
		"""
		config = config or self.default_config
		config_key = f"{config.strategy}:{config.scope}:{config.requests}:{config.period}"

		if config_key not in self.limiters:
			if self.redis_client and getattr(self.settings.API, 'USE_REDIS', False):
				limiter = RedisRateLimiter(config, self.redis_client)
			else:
				limiter = MemoryRateLimiter(config)

			self.limiters[config_key] = limiter

		return self.limiters[config_key]

	async def check_rate_limit (
			self,
			request: Request,
			config: Optional[RateLimitConfig] = None,
			user_id: Optional[str] = None
	) -> RateLimitResult:
		"""
		检查请求限流

		Args:
			request: FastAPI请求对象
			config: 限流配置
			user_id: 用户ID（可选）

		Returns:
			RateLimitResult: 限流结果
		"""
		config = config or self.default_config

		# 确定标识符
		identifier = self._get_identifier(request, config.scope, user_id)

		# 获取限流器
		limiter = self.get_limiter(config)

		# 检查限流
		return await limiter.check(identifier)

	@staticmethod
	def _get_identifier (
			request: Request,
			scope: RateLimitScope,
			user_id: Optional[str] = None
	) -> str:
		"""
		获取限流标识符

		Args:
			request: FastAPI请求对象
			scope: 限流范围
			user_id: 用户ID

		Returns:
			str: 标识符
		"""
		if scope == RateLimitScope.GLOBAL:
			return "global"
		elif scope == RateLimitScope.USER:
			if user_id:
				return f"user:{user_id}"
			else:
				# 如果没有用户ID，尝试从请求中获取
				# 这里需要根据实际的认证逻辑来调整
				return f"user:anonymous"
		elif scope == RateLimitScope.IP:
			client_ip = request.client.host
			return f"ip:{client_ip}"
		elif scope == RateLimitScope.ENDPOINT:
			endpoint = f"{request.method}:{request.url.path}"
			return f"endpoint:{endpoint}"

def rate_limit (
		requests: int = 100,
		period: int = 60,
		strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW,
		scope: RateLimitScope = RateLimitScope.USER,
		burst: Optional[int] = None,
		cost: int = 1,
		error_message: str = "请求过于频繁，请稍后再试"
):
	"""
	限流装饰器

	Args:
		requests: 请求数量
		period: 时间周期（秒）
		strategy: 限流策略
		scope: 限流范围
		burst: 突发流量允许的数量
		cost: 每次请求的消耗
		error_message: 错误消息

	Returns:
		装饰器函数
	"""

	def decorator (func):
		@wraps(func)
		async def wrapper (*args, **kwargs):
			# 从上下文中获取request和current_user
			request = None
			current_user = None

			for arg in args:
				if isinstance(arg, Request):
					request = arg
					break

			for key, value in kwargs.items():
				if key == 'request' and isinstance(value, Request):
					request = value
				elif key == 'current_user':
					current_user = value

			if not request:
				# 如果没有找到request，尝试从FastAPI的Depends中获取

				# 这里需要更复杂的逻辑来处理，简化处理
				logger.warning("限流装饰器中未找到request对象")
				return await func(*args, **kwargs)

			# 获取用户ID
			user_id = None
			if current_user and isinstance(current_user, dict):
				user_id = current_user.get('id')
			elif hasattr(current_user, 'id'):
				user_id = current_user.id

			# 创建限流配置
			config = RateLimitConfig(
				requests=requests,
				period=period,
				strategy=strategy,
				scope=scope,
				burst=burst,
				cost=cost
			)

			# 从应用状态获取限流管理器
			app = request.app

			if not hasattr(app.state, 'rate_limit_manager'):
				# 如果没有限流管理器，跳过限流检查
				logger.warning("应用状态中未找到限流管理器")
				return await func(*args, **kwargs)

			manager = app.state.rate_limit_manager

			# 检查限流
			result = await manager.check_rate_limit(request, config, user_id)

			if not result.allowed:
				# 构建限流响应头
				headers = {
					"X-RateLimit-Limit": str(result.limit),
					"X-RateLimit-Remaining": str(result.remaining),
					"X-RateLimit-Reset": str(int(result.reset_time)),
				}

				if result.retry_after:
					headers["Retry-After"] = str(result.retry_after)

				# 返回限流错误响应
				response = APIResponse.error(
					code="RATE_LIMIT_EXCEEDED",
					message=error_message,
					detail={
						"retry_after": result.retry_after,
						"limit": result.limit,
						"remaining": result.remaining,
						"reset_time": datetime.fromtimestamp(result.reset_time).isoformat()
					}
				).model_dump()

				return JSONResponse(
					status_code=status.HTTP_429_TOO_MANY_REQUESTS,
					content=response,
					headers=headers
				)

			# 请求允许通过，添加限流头信息
			response = await func(*args, **kwargs)

			if isinstance(response, JSONResponse):
				# 添加限流头信息
				response.headers.update({
					"X-RateLimit-Limit": str(result.limit),
					"X-RateLimit-Remaining": str(result.remaining),
					"X-RateLimit-Reset": str(int(result.reset_time)),
				})

			return response

		return wrapper

	return decorator


def create_rate_limit_middleware ():
	"""创建限流中间件工厂函数"""

	async def rate_limit_middleware (request: Request, call_next):
		"""
		限流中间件

		Args:
			request: FastAPI请求对象
			call_next: 下一个中间件或端点

		Returns:
			响应对象
		"""
		# 跳过某些路径的限流检查
		skip_paths = ["/docs", "/redoc", "/openapi.json", "/health", "/metrics"]
		if any(request.url.path.startswith(path) for path in skip_paths):
			return await call_next(request)

		# 获取限流管理器
		if not hasattr(request.app.state, 'rate_limit_manager'):
			# 如果没有限流管理器，跳过限流检查
			return await call_next(request)

		manager = request.app.state.rate_limit_manager

		# 获取用户信息（从请求头或认证信息中）
		user_id = None
		auth_header = request.headers.get("Authorization")
		if auth_header and auth_header.startswith("Bearer "):
			# 这里可以解码JWT获取用户ID
			# 简化处理：从token中提取用户ID
			# 实际应用中需要解码JWT
			# user_id = decode_jwt(auth_header.split(" ")[1]).get("sub")
			pass

		# 检查限流
		result = await manager.check_rate_limit(request, user_id=user_id)

		if not result.allowed:
			# 构建限流响应头
			headers = {
				"X-RateLimit-Limit": str(result.limit),
				"X-RateLimit-Remaining": str(result.remaining),
				"X-RateLimit-Reset": str(int(result.reset_time)),
			}

			if result.retry_after:
				headers["Retry-After"] = str(result.retry_after)

			# 返回限流错误响应
			response = APIResponse.error(
				code="RATE_LIMIT_EXCEEDED",
				message="请求过于频繁，请稍后再试",
				detail={
					"retry_after": result.retry_after,
					"limit": result.limit,
					"remaining": result.remaining,
					"reset_time": datetime.fromtimestamp(result.reset_time).isoformat()
				}
			).model_dump()

			return JSONResponse(
				status_code=status.HTTP_429_TOO_MANY_REQUESTS,
				content=response,
				headers=headers
			)

		# 请求允许通过，继续处理
		response = await call_next(request)

		# 添加限流头信息
		response.headers.update({
			"X-RateLimit-Limit": str(result.limit),
			"X-RateLimit-Remaining": str(result.remaining),
			"X-RateLimit-Reset": str(int(result.reset_time)),
		})

		return response

	return rate_limit_middleware


async def initialize_rate_limit_manager (
		settings: Settings,
		redis_client: Optional[redis.Redis] = None
) -> RateLimitManager:
	"""
	初始化限流管理器（应用启动时调用）

	Args:
		settings: 应用设置
		redis_client: Redis客户端（可选）

	Returns:
		RateLimitManager: 限流管理器实例
	"""
	manager = RateLimitManager(settings, redis_client)
	logger.info("限流管理器初始化完成")
	return manager