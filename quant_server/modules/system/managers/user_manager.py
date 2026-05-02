# -*- coding: utf-8 -*-
"""
用户管理器
负责用户在线状态、会话管理和资源配额控制。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class UserManager:
	"""用户管理器 — 在线状态与会话管理"""

	def __init__ (self, session_factory):
		self._session_factory = session_factory
		# 在线用户: user_id -> session info
		self._online_users: Dict[str, Dict[str, Any]] = {}
		# 登录失败计数: username -> {"count": int, "last_attempt": datetime}
		self._login_failures: Dict[str, Dict[str, Any]] = {}
		# 配置
		self._max_login_attempts = 5
		self._lockout_minutes = 30
		self._session_idle_timeout_minutes = 60

	def is_user_online (self, user_id: str) -> bool:
		"""检查用户是否在线"""
		return user_id in self._online_users

	def get_online_count (self) -> int:
		"""获取在线用户数"""
		return len(self._online_users)

	def get_online_users (self) -> List[Dict[str, Any]]:
		"""获取在线用户列表"""
		return [
			{
				"user_id": uid,
				"username": info.get("username", ""),
				"login_at": info.get("login_at"),
				"last_active": info.get("last_active"),
				"ip_address": info.get("ip_address", ""),
			}
			for uid, info in self._online_users.items()
		]

	async def mark_online (self, user_id: str, username: str,
	                       ip_address: str = "") -> None:
		"""标记用户上线"""
		now = datetime.now()
		self._online_users[user_id] = {
			"username": username,
			"login_at": now,
			"last_active": now,
			"ip_address": ip_address,
		}
		# 清除登录失败记录
		self._login_failures.pop(username, None)
		logger.debug(f"用户上线: {username} ({user_id})")

	async def mark_offline (self, user_id: str) -> None:
		"""标记用户下线"""
		info = self._online_users.pop(user_id, None)
		if info:
			logger.debug(f"用户下线: {info.get('username')} ({user_id})")

	async def update_activity (self, user_id: str) -> None:
		"""更新用户最后活动时间"""
		info = self._online_users.get(user_id)
		if info:
			info["last_active"] = datetime.now()

	async def record_login_failure (self, username: str) -> Dict[str, Any]:
		"""记录登录失败，返回是否应该锁定

		Returns:
			{"locked": bool, "remaining_attempts": int, "lock_remaining_minutes": int}
		"""
		now = datetime.now()
		record = self._login_failures.get(username)

		if record:
			# 检查是否在锁定期
			lock_until = record.get("lock_until")
			if lock_until and now < lock_until:
				remaining = int((lock_until - now).total_seconds() / 60) + 1
				return {"locked": True, "remaining_attempts": 0, "lock_remaining_minutes": remaining}

			# 超时则重置
			window_start = now - timedelta(minutes=self._lockout_minutes)
			if record.get("last_attempt", datetime.min) < window_start:
				record = {"count": 0, "last_attempt": now}
				self._login_failures[username] = record

			record["count"] += 1
			record["last_attempt"] = now
		else:
			record = {"count": 1, "last_attempt": now}
			self._login_failures[username] = record

		if record["count"] >= self._max_login_attempts:
			record["lock_until"] = now + timedelta(minutes=self._lockout_minutes)
			logger.warning(
				f"用户 {username} 登录失败达到 {self._max_login_attempts} 次，已锁定 {self._lockout_minutes} 分钟")
			return {"locked": True, "remaining_attempts": 0, "lock_remaining_minutes": self._lockout_minutes}

		remaining = self._max_login_attempts - record["count"]
		return {"locked": False, "remaining_attempts": remaining, "lock_remaining_minutes": 0}

	async def cleanup_idle_sessions (self) -> int:
		"""清理空闲会话，返回清理数"""
		now = datetime.now()
		timeout = timedelta(minutes=self._session_idle_timeout_minutes)
		offline_ids = [
			uid for uid, info in self._online_users.items()
			if (now - info.get("last_active", info.get("login_at", now))) > timeout
		]
		for uid in offline_ids:
			self._online_users.pop(uid, None)
		if offline_ids:
			logger.info(f"清理了 {len(offline_ids)} 个空闲会话")
		return len(offline_ids)

	async def cleanup_expired_lockouts (self) -> int:
		"""清理过期的登录锁定记录，返回清理数"""
		now = datetime.now()
		expired = [
			username for username, record in self._login_failures.items()
			if record.get("lock_until") and now >= record["lock_until"]
		]
		for username in expired:
			self._login_failures.pop(username, None)
		return len(expired)
