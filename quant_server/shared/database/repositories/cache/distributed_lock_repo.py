# quant_server/shared/database/repositories/cache/distributed_lock_repo.py
"""
分布式锁Repository
"""
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import redis
import hashlib
import json

from quant_server.shared.database.repositories.base import BaseRepository


class DistributedLockRepository(BaseRepository):
	"""
	分布式锁仓库
	用于管理分布式系统中的资源锁，防止并发冲突
	"""

	def __init__ (self, session: Session, redis_client: Optional[redis.Redis] = None):
		"""
		初始化分布式锁仓库

		Args:
			session: SQLAlchemy会话
			redis_client: Redis客户端（用于分布式锁实现）
		"""
		super().__init__(session)
		self.redis_client = redis_client

	def acquire_lock (
			self,
			lock_key: str,
			timeout: int = 30,
			expire: int = 60
	) -> Optional[str]:
		"""
		获取分布式锁

		Args:
			lock_key: 锁的键名
			timeout: 获取锁的超时时间（秒）
			expire: 锁的过期时间（秒）

		Returns:
			str: 锁的唯一标识符，如果获取失败返回None
		"""
		if not self.redis_client:
			# 如果没有配置Redis，返回一个简单的本地锁标识
			return f"local_lock_{lock_key}"

		lock_identifier = hashlib.md5(f"{lock_key}_{datetime.now().timestamp()}".encode()).hexdigest()

		# 使用Redis SETNX命令实现分布式锁
		for _ in range(timeout):
			if self.redis_client.setnx(lock_key, lock_identifier):
				self.redis_client.expire(lock_key, expire)
				return lock_identifier

		return None

	def release_lock (self, lock_key: str, lock_identifier: str) -> bool:
		"""
		释放分布式锁

		Args:
			lock_key: 锁的键名
			lock_identifier: 锁的唯一标识符

		Returns:
			bool: 是否成功释放
		"""
		if not self.redis_client:
			return True

		# 使用Lua脚本确保原子性操作
		lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """

		result = self.redis_client.eval(lua_script, 1, lock_key, lock_identifier)
		return result == 1

	def renew_lock (self, lock_key: str, lock_identifier: str, expire: int = 60) -> bool:
		"""
		续期分布式锁

		Args:
			lock_key: 锁的键名
			lock_identifier: 锁的唯一标识符
			expire: 新的过期时间（秒）

		Returns:
			bool: 是否成功续期
		"""
		if not self.redis_client:
			return True

		# 使用Lua脚本确保原子性操作
		lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """

		result = self.redis_client.eval(lua_script, 1, lock_key, lock_identifier, expire)
		return result == 1

	def is_locked (self, lock_key: str) -> bool:
		"""
		检查锁是否被占用

		Args:
			lock_key: 锁的键名

		Returns:
			bool: 是否被锁定
		"""
		if not self.redis_client:
			return False

		return self.redis_client.exists(lock_key) > 0

	def get_lock_info (self, lock_key: str) -> Optional[Dict[str, Any]]:
		"""
		获取锁的详细信息

		Args:
			lock_key: 锁的键名

		Returns:
			Dict: 锁的详细信息，包括持有者、创建时间、剩余时间等
		"""
		if not self.redis_client:
			return None

		lock_value = self.redis_client.get(lock_key)
		if not lock_value:
			return None

		ttl = self.redis_client.ttl(lock_key)
		return {
			"key": lock_key,
			"identifier": lock_value.decode(),
			"ttl": ttl,
			"is_expiring": ttl < 10,  # 剩余时间小于10秒视为即将过期
			"created_at": datetime.now() - timedelta(seconds=self.redis_client.object("idletime", lock_key))
		}

	def clear_expired_locks (self, pattern: str = "*_lock_*") -> int:
		"""
		清理过期的锁

		Args:
			pattern: 锁键的模式

		Returns:
			int: 清理的锁数量
		"""
		if not self.redis_client:
			return 0

		keys = self.redis_client.keys(pattern)
		expired_count = 0

		for key in keys:
			if self.redis_client.ttl(key) == -1:  # 没有设置过期时间
				self.redis_client.delete(key)
				expired_count += 1
			elif self.redis_client.ttl(key) == -2:  # 已过期
				expired_count += 1

		return expired_count