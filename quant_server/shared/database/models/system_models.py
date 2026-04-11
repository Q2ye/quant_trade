"""
system_models.py
系统相关表模型定义（配置、任务、日志等）
位置：shared/database/models/system_models.py
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, DateTime, Integer, Numeric, Boolean, Text, ForeignKey, JSON, Index, \
	CheckConstraint, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .base import Base


# ==================== 系统配置 ====================

class SystemConfig(Base):
	"""系统配置表"""
	__tablename__ = 'system_configs'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='配置ID')
	config_key = Column(String(100), nullable=False, unique=True, index=True, comment='配置键')
	config_value = Column(Text, nullable=False, comment='配置值')
	config_type = Column(String(50), default='string', comment='配置类型：string, int, float, bool, json')
	description = Column(Text, comment='配置描述')
	is_public = Column(Boolean, default=False, comment='是否公开配置')
	created_by = Column(String(36), ForeignKey('sys_users.id'), comment='创建人ID')
	updated_by = Column(String(36), ForeignKey('sys_users.id'), comment='更新人ID')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	creator = relationship("SysUser", foreign_keys=created_by)
	updater = relationship("SysUser", foreign_keys=updated_by)


# ==================== 任务调度 ====================

class ScheduledTask(Base):
	"""定时任务调度表"""
	__tablename__ = 'sys_scheduled_tasks'

	# 主键和基础字段
	id = Column(String(50), primary_key=True, comment='任务唯一标识')
	task_name = Column(String(100), nullable=False, comment='任务名称')
	task_type = Column(String(50), nullable=False, comment='任务调度类型（cron表达式、时间间隔、指定时间、手动）')
	task_module = Column(String(50), nullable=False, comment='任务所属模块')

	# 配置字段
	schedule_config = Column(JSONB, nullable=False, comment='调度配置（JSON格式，如cron表达式）')
	task_config = Column(JSONB, default={}, server_default='{}', comment='任务配置（JSON格式）')

	# 运行状态字段
	last_run_at = Column(DateTime(timezone=True), comment='最后运行时间')
	last_run_result = Column(String(20), comment='上次运行结果（success, failed, skipped）')
	last_run_duration = Column(Integer, comment='上次运行时长（秒）')
	next_run_at = Column(DateTime(timezone=True), comment='下次运行时间')

	# 统计字段
	total_runs = Column(Integer, default=0, server_default='0', comment='总运行次数')
	success_runs = Column(Integer, default=0, server_default='0', comment='成功运行次数')
	failed_runs = Column(Integer, default=0, server_default='0', comment='失败运行次数')

	# 控制字段
	is_active = Column(Boolean, default=True, server_default='true', comment='是否激活')
	max_retries = Column(Integer, default=3, server_default='3', comment='最大重试次数')
	retry_delay = Column(Integer, default=60, server_default='60', comment='重试延迟（秒）')
	timeout_seconds = Column(Integer, default=300, server_default='300', comment='超时时间（秒）')

	# 审计字段
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    server_default='CURRENT_TIMESTAMP', comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc),
	                    server_default='CURRENT_TIMESTAMP', comment='更新时间')

	# 添加软删除字段
	is_deleted = Column(Boolean, default=False, server_default='false', comment='是否删除')

	# 检查约束
	__table_args__ = (
		CheckConstraint(
			"task_type IN ('cron', 'interval', 'date', 'manual')",
			name='ck_scheduled_tasks_task_type'
		),
		CheckConstraint(
			"last_run_result IN ('success', 'failed', 'skipped')",
			name='ck_scheduled_tasks_last_run_result'
		),
		Index('idx_sys_scheduled_tasks_active', 'is_active'),
		Index('idx_sys_scheduled_tasks_next_run', 'next_run_at'),
		Index('idx_sys_scheduled_tasks_module', 'task_module'),
		Index('idx_sys_scheduled_tasks_created_at', 'created_at'),
		Index('idx_sys_scheduled_tasks_updated_at', 'updated_at'),
	)

	def __repr__ (self):
		return f"<ScheduledTask(id={self.id}, name={self.task_name}, module={self.task_module}, active={self.is_active})>"

	@property
	def success_rate (self) -> float:
		"""计算任务成功率"""
		if self.total_runs == 0:
			return 0.0
		return (self.success_runs / self.total_runs) * 100

	@property
	def is_due (self) -> bool:
		"""检查任务是否到期需要执行"""
		if not self.is_active or not self.next_run_at:
			return False
		from datetime import datetime
		return self.next_run_at <= datetime.now(timezone.utc)

	@property
	def average_duration (self) -> float:
		"""计算平均运行时长"""
		if self.total_runs == 0 or not self.last_run_duration:
			return 0.0
		return self.last_run_duration

	def get_schedule_config (self, key: str, default=None):
		"""获取调度配置中的值"""
		if self.schedule_config and isinstance(self.schedule_config, dict):
			return self.schedule_config.get(key, default)
		return default

	def get_task_config (self, key: str, default=None):
		"""获取任务配置中的值"""
		if self.task_config and isinstance(self.task_config, dict):
			return self.task_config.get(key, default)
		return default

	def to_dict (self) -> dict:
		"""转换为字典格式"""
		return {
			'id': self.id,
			'task_name': self.task_name,
			'task_type': self.task_type,
			'task_module': self.task_module,
			'schedule_config': self.schedule_config,
			'task_config': self.task_config,
			'last_run_at': self.last_run_at.isoformat() if self.last_run_at else None,
			'last_run_result': self.last_run_result,
			'last_run_duration': self.last_run_duration,
			'next_run_at': self.next_run_at.isoformat() if self.next_run_at else None,
			'total_runs': self.total_runs,
			'success_runs': self.success_runs,
			'failed_runs': self.failed_runs,
			'is_active': self.is_active,
			'max_retries': self.max_retries,
			'retry_delay': self.retry_delay,
			'timeout_seconds': self.timeout_seconds,
			'success_rate': round(self.success_rate, 2),
			'is_due': self.is_due,
			'average_duration': self.average_duration,
			'created_at': self.created_at.isoformat() if self.created_at else None,
			'updated_at': self.updated_at.isoformat() if self.updated_at else None,
			'is_deleted': self.is_deleted
		}


# ==================== 系统日志 ====================

class SystemLog(Base):
	"""系统操作日志表"""
	__tablename__ = 'system_logs'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='日志ID')
	log_level = Column(String(20), nullable=False, index=True, comment='日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL')
	module = Column(String(50), nullable=False, index=True, comment='模块名称')
	user_id = Column(String(36), ForeignKey('sys_users.id'), index=True, comment='用户ID')
	action = Column(String(100), nullable=False, comment='操作动作')
	details = Column(Text, comment='详细信息（JSON格式）')
	ip_address = Column(String(50), comment='IP地址')
	user_agent = Column(Text, comment='用户代理')
	execution_time = Column(Integer, comment='执行时间（毫秒）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True,
	                    comment='创建时间')

	# 关联关系
	user = relationship("SysUser", back_populates="system_logs")

	# 索引
	__table_args__ = (
		Index('idx_system_logs_module_action', 'module', 'action'),
		Index('idx_system_logs_created_at', 'created_at'),
	)


# ==================== 审计日志 ====================

class AuditLog(Base):
	"""审计日志表"""
	__tablename__ = 'audit_logs'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='审计日志ID')
	user_id = Column(String(36), ForeignKey('sys_users.id'), index=True, comment='用户ID')
	username = Column(String(100), comment='用户名')
	action_type = Column(String(50), nullable=False, comment='操作类型：CREATE, UPDATE, DELETE, LOGIN, LOGOUT')
	resource_type = Column(String(100), nullable=False, comment='资源类型')
	resource_id = Column(String(100), comment='资源ID')
	resource_name = Column(String(255), comment='资源名称')
	old_values = Column(JSONB, comment='旧值（JSON格式）')
	new_values = Column(JSONB, comment='新值（JSON格式）')
	changed_fields = Column(JSONB, comment='变更字段列表')
	ip_address = Column(String(50), comment='IP地址')
	user_agent = Column(Text, comment='用户代理')
	status = Column(String(20), default='success', comment='操作状态：success, failed')
	error_message = Column(Text, comment='错误信息')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    index=True, comment='创建时间')

	# 关联关系
	user = relationship("SysUser")

	# 索引
	__table_args__ = (
		Index('idx_audit_logs_action_type', 'action_type'),
		Index('idx_audit_logs_resource_type', 'resource_type'),
		Index('idx_audit_logs_created_at_user', 'created_at', 'user_id'),
	)


# ==================== 系统通知 ====================

class SystemNotification(Base):
	"""系统通知表"""
	__tablename__ = 'system_notifications'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='通知ID')
	notification_type = Column(String(50), nullable=False, comment='通知类型：SYSTEM, ALERT, TASK, TRADE')
	title = Column(String(200), nullable=False, comment='通知标题')
	content = Column(Text, nullable=False, comment='通知内容')
	priority = Column(String(20), default='normal', comment='优先级：low, normal, high, urgent')
	recipient_id = Column(String(36), ForeignKey('sys_users.id'), comment='接收用户ID')
	recipient_type = Column(String(50), default='USER', comment='接收者类型：USER, ROLE, ALL')
	is_read = Column(Boolean, default=False, comment='是否已读')
	read_at = Column(DateTime(timezone=True), comment='阅读时间')
	expiry_at = Column(DateTime(timezone=True), comment='过期时间')
	action_url = Column(String(500), comment='操作链接')
	metainfo = Column(JSONB, comment='元数据（JSON格式）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    index=True, comment='创建时间')

	# 关联关系
	recipient = relationship("SysUser", foreign_keys=recipient_id)

	# 索引
	__table_args__ = (
		Index('idx_notifications_recipient_read', 'recipient_id', 'is_read'),
		Index('idx_notifications_created_at', 'created_at'),
		Index('idx_notifications_type_priority', 'notification_type', 'priority'),
	)


# ==================== 用户偏好设置 ====================

class UserPreference(Base):
	"""用户偏好设置表"""
	__tablename__ = 'user_preferences'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='偏好设置ID')
	user_id = Column(String(36), ForeignKey('sys_users.id'), nullable=False, unique=True, comment='用户ID')
	preferences = Column(JSONB, default={}, server_default='{}', comment='用户偏好设置（JSON格式）')
	theme = Column(String(50), default='light', comment='主题：light, dark')
	language = Column(String(10), default='zh-CN', comment='语言')
	timezone = Column(String(50), default='Asia/Shanghai', comment='时区')
	date_format = Column(String(50), default='YYYY-MM-DD', comment='日期格式')
	time_format = Column(String(50), default='24h', comment='时间格式：12h, 24h')
	notifications_enabled = Column(Boolean, default=True, comment='是否启用通知')
	email_notifications = Column(Boolean, default=True, comment='是否启用邮件通知')
	push_notifications = Column(Boolean, default=True, comment='是否启用推送通知')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	user = relationship("SysUser", back_populates="user_preferences")

	# 索引
	__table_args__ = (
		Index('idx_user_preferences_user_id', 'user_id'),
	)


# ==================== API使用日志 ====================

class ApiUsageLog(Base):
	"""API使用日志表"""
	__tablename__ = 'api_usage_logs'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='日志ID')
	user_id = Column(String(36), ForeignKey('sys_users.id'), index=True, comment='用户ID')
	api_endpoint = Column(String(500), nullable=False, comment='API端点')
	http_method = Column(String(10), nullable=False, comment='HTTP方法：GET, POST, PUT, DELETE')
	request_headers = Column(JSONB, comment='请求头（JSON格式）')
	request_body = Column(Text, comment='请求体')
	query_params = Column(JSONB, comment='查询参数（JSON格式）')
	response_status = Column(Integer, nullable=False, comment='响应状态码')
	response_body = Column(Text, comment='响应体')
	response_time = Column(Integer, comment='响应时间（毫秒）')
	request_size = Column(Integer, comment='请求大小（字节）')
	response_size = Column(Integer, comment='响应大小（字节）')
	ip_address = Column(String(50), comment='客户端IP地址')
	user_agent = Column(Text, comment='用户代理')
	referer = Column(String(500), comment='来源URL')
	error_message = Column(Text, comment='错误信息')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    index=True, comment='创建时间')

	# 关联关系
	user = relationship("SysUser", back_populates="api_usage_logs")

	# 索引
	__table_args__ = (
		Index('idx_api_logs_endpoint_method', 'api_endpoint', 'http_method'),
		Index('idx_api_logs_response_status', 'response_status'),
		Index('idx_api_logs_created_at_user', 'created_at', 'user_id'),
		Index('idx_api_logs_response_time', 'response_time'),
	)


# ==================== 系统健康指标 ====================

class SystemHealthMetric(Base):
	"""系统健康指标表"""
	__tablename__ = 'system_health_metrics'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='指标ID')
	metric_name = Column(String(100), nullable=False, comment='指标名称')
	metric_value = Column(Numeric(10, 2), nullable=False, comment='指标值')
	metric_unit = Column(String(50), comment='指标单位')
	component = Column(String(100), nullable=False, comment='组件名称')
	severity = Column(String(20), default='info', comment='严重程度：info, warning, error, critical')
	threshold_min = Column(Numeric(10, 2), comment='阈值最小值')
	threshold_max = Column(Numeric(10, 2), comment='阈值最大值')
	is_healthy = Column(Boolean, default=True, comment='是否健康')
	details = Column(JSONB, comment='详细信息（JSON格式）')
	collected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                      index=True, comment='采集时间')

	# 索引
	__table_args__ = (
		Index('idx_health_metrics_name_component', 'metric_name', 'component'),
		Index('idx_health_metrics_collected_at', 'collected_at'),
		Index('idx_health_metrics_severity', 'severity'),
		Index('idx_health_metrics_is_healthy', 'is_healthy'),
	)


# ==================== 许可证密钥 ====================

class LicenseKey(Base):
	"""许可证密钥表"""
	__tablename__ = 'license_keys'

	id = Column(String(100), primary_key=True, comment='许可证ID')
	license_key = Column(String(500), nullable=False, unique=True, comment='许可证密钥')
	license_type = Column(String(50), nullable=False, comment='许可证类型：TRIAL, STANDARD, ENTERPRISE')
	owner = Column(String(200), comment='所有者')
	email = Column(String(200), comment='邮箱')
	max_users = Column(Integer, default=1, comment='最大用户数')
	max_strategies = Column(Integer, default=10, comment='最大策略数')
	max_api_calls = Column(Integer, default=10000, comment='最大API调用数')
	features = Column(JSONB, default={}, server_default='{}', comment='功能列表（JSON格式）')
	valid_from = Column(DateTime(timezone=True), nullable=False, comment='有效期开始时间')
	valid_to = Column(DateTime(timezone=True), nullable=False, comment='有效期结束时间')
	is_active = Column(Boolean, default=True, comment='是否激活')
	activation_date = Column(DateTime(timezone=True), comment='激活日期')
	deactivation_date = Column(DateTime(timezone=True), comment='停用日期')
	last_validation = Column(DateTime(timezone=True), comment='最后验证时间')
	validation_result = Column(String(20), comment='验证结果：valid, expired, invalid')
	metainfo = Column(JSONB, comment='元数据（JSON格式）')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 索引
	__table_args__ = (
		Index('idx_license_keys_valid_to', 'valid_to'),
		Index('idx_license_keys_is_active', 'is_active'),
		Index('idx_license_keys_license_type', 'license_type'),
		Index('idx_license_keys_validation_result', 'validation_result'),
	)


class HyperTableMetadata(Base):
	"""超表元数据表"""
	__tablename__ = 'hyper_table_metadata'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='元数据ID')
	table_name = Column(String(100), nullable=False, unique=True, index=True, comment='表名')
	time_column = Column(String(50), nullable=False, default='timestamp', comment='时间列名')
	tags = Column(JSON, default=lambda: [], comment='标签列列表')
	chunk_time_interval = Column(String(20), default='1 day', comment='数据块时间间隔')
	compression_enabled = Column(Boolean, default=True, comment='是否启用压缩')
	compression_settings = Column(JSON, default=lambda: {}, comment='压缩设置')
	status = Column(String(20), default='active', comment='状态：active, disabled, error')
	disabled_reason = Column(Text, comment='禁用原因')
	disabled_at = Column(DateTime(timezone=True), comment='禁用时间')
	enabled_at = Column(DateTime(timezone=True), comment='启用时间')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	time_buckets = relationship("TimeBucketConfig", back_populates="hyper_table", cascade="all, delete-orphan")
	retention_policies = relationship("RetentionPolicy", back_populates="hyper_table", cascade="all, delete-orphan")
	chunks = relationship("ChunkMetadata", back_populates="hyper_table", cascade="all, delete-orphan")


class TimeBucketConfig(Base):
	"""时间分桶配置表"""
	__tablename__ = 'time_bucket_configs'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='配置ID')
	table_name = Column(String(100), ForeignKey('hyper_table_metadata.table_name'), nullable=False, comment='表名')
	bucket_interval = Column(String(10), nullable=False, comment='分桶间隔：1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1M')
	aggregate_functions = Column(JSON, default=lambda: [], comment='聚合函数列表')
	retention_days = Column(Integer, default=365, comment='数据保留天数')
	is_active = Column(Boolean, default=True, comment='是否激活')
	materialized_view = Column(String(100), comment='物化视图名')
	last_bucket_time = Column(DateTime(timezone=True), comment='最后分桶时间')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	hyper_table = relationship("HyperTableMetadata", back_populates="time_buckets")

	# 索引
	__table_args__ = (
		Index('idx_time_bucket_configs_table', 'table_name'),
		Index('idx_time_bucket_configs_interval', 'bucket_interval'),
	)


class RetentionPolicy(Base):
	"""数据保留策略表"""
	__tablename__ = 'retention_policies'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='策略ID')
	table_name = Column(String(100), ForeignKey('hyper_table_metadata.table_name'), nullable=False, comment='表名')
	retention_period = Column(String(50), nullable=False, comment='保留周期：30 days, 1 year, 1000 rows')
	cleanup_strategy = Column(String(50), nullable=False, default='drop', comment='清理策略：drop, archive, compress')
	schedule_interval = Column(String(20), default='1 day', comment='调度间隔')
	is_active = Column(Boolean, default=True, comment='是否激活')
	conditions = Column(JSON, default=lambda: {}, comment='额外条件')
	last_executed = Column(DateTime(timezone=True), comment='最后执行时间')
	next_execution = Column(DateTime(timezone=True), comment='下次执行时间')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	hyper_table = relationship("HyperTableMetadata", back_populates="retention_policies")
	execution_logs = relationship("RetentionPolicyLog", back_populates="policy", cascade="all, delete-orphan")

	# 索引
	__table_args__ = (
		Index('idx_retention_policies_table', 'table_name'),
		Index('idx_retention_policies_active', 'is_active'),
		Index('idx_retention_policies_next_execution', 'next_execution'),
	)


class RetentionPolicyLog(Base):
	"""保留策略执行日志表"""
	__tablename__ = 'retention_policy_logs'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='日志ID')
	policy_id = Column(String(36), ForeignKey('retention_policies.id'), nullable=False, comment='策略ID')
	execution_time = Column(DateTime(timezone=True), nullable=False, comment='执行时间')
	dry_run = Column(Boolean, default=False, comment='是否试运行')
	rows_affected = Column(Integer, default=0, comment='影响行数')
	space_reclaimed = Column(String(50), comment='回收空间')
	execution_status = Column(String(20), nullable=False, comment='执行状态：success, failed')
	error_message = Column(Text, comment='错误信息')
	execution_details = Column(JSON, default=lambda: {}, comment='执行详情')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')

	# 关联关系
	policy = relationship("RetentionPolicy", back_populates="execution_logs")

	# 索引
	__table_args__ = (
		Index('idx_retention_policy_logs_policy', 'policy_id'),
		Index('idx_retention_policy_logs_time', 'execution_time'),
	)


class ChunkMetadata(Base):
	"""数据分片元数据表"""
	__tablename__ = 'chunk_metadata'

	id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), comment='分片ID')
	table_name = Column(String(100), ForeignKey('hyper_table_metadata.table_name'), nullable=False, comment='表名')
	chunk_name = Column(String(100), nullable=False, unique=True, comment='分片名')
	start_time = Column(DateTime(timezone=True), nullable=False, comment='开始时间')
	end_time = Column(DateTime(timezone=True), nullable=False, comment='结束时间')
	storage_type = Column(String(10), default='hot', comment='存储类型：hot, warm, cold')
	storage_location = Column(Text, comment='存储位置')
	max_size_mb = Column(Integer, default=1024, comment='最大大小（MB）')
	current_size_mb = Column(Float, default=0, comment='当前大小（MB）')
	row_count = Column(Integer, default=0, comment='行数')
	compression_enabled = Column(Boolean, default=False, comment='是否启用压缩')
	compression_ratio = Column(Float, default=1.0, comment='压缩比')
	status = Column(String(20), default='active', comment='状态：active, merged, split, archived')
	merged_into = Column(String(36), comment='合并到哪个分片')
	split_into = Column(String(100), comment='分裂成哪些分片')
	last_storage_move = Column(DateTime(timezone=True), comment='最后存储移动时间')
	created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), comment='创建时间')
	updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
	                    onupdate=lambda: datetime.now(timezone.utc), comment='更新时间')

	# 关联关系
	hyper_table = relationship("HyperTableMetadata", back_populates="chunks")

	# 索引
	__table_args__ = (
		Index('idx_chunk_metadata_table', 'table_name'),
		Index('idx_chunk_metadata_time_range', 'start_time', 'end_time'),
		Index('idx_chunk_metadata_storage', 'storage_type'),
		Index('idx_chunk_metadata_status', 'status'),
	)


# ==================== 模型导出 ====================

__all__ = [
	'SystemConfig',
	'ScheduledTask',
	'SystemLog',
	'AuditLog',
	'SystemNotification',
	'UserPreference',
	'ApiUsageLog',
	'SystemHealthMetric',
	'LicenseKey',
	'HyperTableMetadata',
	'TimeBucketConfig',
	'RetentionPolicy',
	'RetentionPolicyLog',
	'ChunkMetadata',
]
