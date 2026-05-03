# quant_server/shared/database/repositories/system/__init__.py
"""
系统管理领域Repository包初始化
"""

from shared.database.repositories.system.auth.permission_repo import PermissionRepository
from shared.database.repositories.system.auth.role_repo import RoleRepository
from shared.database.repositories.system.auth.user_repo import UserRepository
from shared.database.repositories.system.config.api_usage_log_repo import ApiUsageLogRepository
from shared.database.repositories.system.config.audit_repo import AuditRepository
from shared.database.repositories.system.config.config_repo import ConfigRepository
from shared.database.repositories.system.config.notification_repo import NotificationRepository
from shared.database.repositories.system.config.operation_log_repo import OperationLogRepository

# backward-compatible alias
LogRepository = OperationLogRepository
from shared.database.repositories.system.config.user_preference_repo import UserPreferenceRepository
from shared.database.repositories.system.ops.license_key_repo import LicenseKeyRepository
from shared.database.repositories.system.ops.retention_policy_log_repo import RetentionPolicyLogRepository
from shared.database.repositories.system.ops.scheduled_task_repo import (
	ScheduledTaskRepository,
	TaskType,
	TaskStatus,
	TaskModule
)
from shared.database.repositories.system.ops.system_health_metric_repo import SystemHealthMetricRepository

__all__ = [
	# 认证授权Repository
	"UserRepository",
	"RoleRepository",
	"PermissionRepository",

	# 配置管理Repository
	"ConfigRepository",
	"AuditRepository",
	"NotificationRepository",
	"OperationLogRepository",
	"LogRepository",
	"UserPreferenceRepository",
	"ApiUsageLogRepository",

	# 系统运维Repository
	"SystemHealthMetricRepository",
	"LicenseKeyRepository",
	"RetentionPolicyLogRepository",
	"ScheduledTaskRepository",

	# 定时任务相关枚举
	"TaskType",
	"TaskStatus",
	"TaskModule"
]