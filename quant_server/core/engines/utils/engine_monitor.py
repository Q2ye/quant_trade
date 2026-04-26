"""
引擎监控器
实时监控所有引擎的运行状态、性能指标和健康状况

核心功能：
1. 实时监控引擎状态和健康状况
2. 收集和分析引擎性能指标
3. 异常检测和预警
4. 生成监控报告和图表
5. 提供监控API和WebSocket推送

监控器作为系统的"眼睛"，确保所有引擎正常运行。
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque

# 导入统一类型定义
from ..types.entities import (
	Metric as MetricEntity,
	Alert as AlertEntity, EventEntity
)
from ..types.enums import (
    ComponentStatus,
    HealthStatus,
    PriorityLevel,
    AlertLevel,
    MetricType,
)

# 导入系统组件
from ..system.engine_registry import EngineRegistry
from ..system.event_engine import EventEngine
from ..utils.engine_factory import EngineFactory

logger = logging.getLogger(__name__)


@dataclass
class MonitorAlert:
    """监控警报"""

    alert_id: str  # 警报ID
    engine_name: str  # 引擎名称
    alert_level: AlertLevel  # 警报级别
    message: str  # 警报消息
    metric_name: Optional[str] = None  # 相关指标名称
    metric_value: Optional[float] = None  # 指标值
    threshold: Optional[float] = None  # 阈值
    timestamp: datetime = field(default_factory=datetime.now)  # 发生时间
    resolved: bool = False  # 是否已解决
    resolved_time: Optional[datetime] = None  # 解决时间
    acknowledged: bool = False  # 是否已确认
    acknowledged_by: Optional[str] = None  # 确认人

    def to_alert_entity(self) -> AlertEntity:
        """转换为警报实体

        Returns:
            AlertEntity: 警报实体
        """
        return AlertEntity(
            alert_id=self.alert_id,
            alert_name=f"engine_alert_{self.alert_level.value}",
            alert_type="engine_monitor",
            level=self.alert_level.value,
            message=self.message,
            source=f"engine:{self.engine_name}",
            data={
                "engine_name": self.engine_name,
                "metric_name": self.metric_name,
                "metric_value": self.metric_value,
                "threshold": self.threshold,
                "alert_id": self.alert_id
            },
            create_time=self.timestamp,
            acknowledged=self.acknowledged,
            resolved=self.resolved,
            resolved_time=self.resolved_time
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        result = {
            "alert_id": self.alert_id,
            "engine_name": self.engine_name,
            "alert_level": self.alert_level.value,
            "message": self.message,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by
        }

        if self.resolved_time:
            result["resolved_time"] = self.resolved_time.isoformat()

        return result


@dataclass
class EngineMetric:
    """引擎指标"""

    engine_name: str  # 引擎名称
    metric_name: str  # 指标名称
    value: float  # 指标值
    timestamp: datetime  # 时间戳
    tags: Dict[str, str] = field(default_factory=dict)  # 标签

    def to_metric_entity(self) -> MetricEntity:
        """转换为指标实体

        Returns:
            MetricEntity: 指标实体
        """
        return MetricEntity(
            metric_id=f"{self.engine_name}_{self.metric_name}_{self.timestamp.timestamp()}",
            metric_name=self.metric_name,
            metric_type=MetricType.GAUGE.value,
            value=self.value,
            timestamp=self.timestamp,
            tags={**self.tags, "engine": self.engine_name}
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "engine_name": self.engine_name,
            "metric_name": self.metric_name,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "tags": self.tags
        }


@dataclass
class MetricStatistic:
    """指标统计"""

    metric_name: str  # 指标名称
    count: int = 0  # 样本数量
    min_value: Optional[float] = None  # 最小值
    max_value: Optional[float] = None  # 最大值
    avg_value: Optional[float] = None  # 平均值
    median_value: Optional[float] = None  # 中位数
    std_dev: Optional[float] = None  # 标准差
    percentile_95: Optional[float] = None  # 95百分位
    last_value: Optional[float] = None  # 最新值
    trend: str = "stable"  # 趋势（上升/下降/稳定）

    def update(self, value: float) -> None:
        """更新统计

        Args:
            value: 新的指标值
        """
        if self.count == 0:
            self.min_value = value
            self.max_value = value
            self.avg_value = value
        else:
            # 确保 min_value 和 max_value 不为 None
            if self.min_value is not None:
                self.min_value = min(self.min_value, value)
            else:
                self.min_value = value

            if self.max_value is not None:
                self.max_value = max(self.max_value, value)
            else:
                self.max_value = value

            # 移动平均
            if self.avg_value is not None:
                self.avg_value = (self.avg_value * self.count + value) / (self.count + 1)
            else:
                self.avg_value = value

        self.count += 1
        self.last_value = value

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        return {
            "metric_name": self.metric_name,
            "count": self.count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "avg_value": self.avg_value,
            "median_value": self.median_value,
            "std_dev": self.std_dev,
            "percentile_95": self.percentile_95,
            "last_value": self.last_value,
            "trend": self.trend
        }


@dataclass
class AlertRule:
    """警报规则"""

    rule_id: str  # 规则ID
    engine_name: str  # 引擎名称（*表示所有引擎）
    metric_name: str  # 指标名称
    condition: str  # 条件表达式（如 ">", "<", "==", "!="）
    threshold: float  # 阈值
    alert_level: AlertLevel  # 警报级别
    message_template: str  # 消息模板
    enabled: bool = True  # 是否启用
    cooldown_seconds: int = 300  # 冷却时间（秒，避免重复警报）
    last_triggered: Optional[datetime] = None  # 上次触发时间

    def check_condition(self, value: float) -> bool:
        """检查条件

        Args:
            value: 指标值

        Returns:
            bool: 是否触发条件
        """
        if not self.enabled:
            return False

        # 检查冷却时间
        if self.last_triggered:
            elapsed = (datetime.now() - self.last_triggered).total_seconds()
            if elapsed < self.cooldown_seconds:
                return False

        # 检查条件
        if self.condition == ">":
            return value > self.threshold
        elif self.condition == ">=":
            return value >= self.threshold
        elif self.condition == "<":
            return value < self.threshold
        elif self.condition == "<=":
            return value <= self.threshold
        elif self.condition == "==":
            return abs(value - self.threshold) < 1e-6  # 浮点数比较
        elif self.condition == "!=":
            return abs(value - self.threshold) > 1e-6
        else:
            logger.warning(f"未知条件: {self.condition}")
            return False

    def create_alert(self, value: float) -> MonitorAlert:
        """创建警报

        Args:
            value: 触发警报的指标值

        Returns:
            MonitorAlert: 警报对象
        """
        # 更新触发时间
        self.last_triggered = datetime.now()

        # 生成消息
        message = self.message_template.format(
            engine_name=self.engine_name,
            metric_name=self.metric_name,
            value=value,
            threshold=self.threshold,
            timestamp=datetime.now().isoformat()
        )

        return MonitorAlert(
            alert_id=str(uuid.uuid4()),
            engine_name=self.engine_name,
            alert_level=self.alert_level,
            message=message,
            metric_name=self.metric_name,
            metric_value=value,
            threshold=self.threshold
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典

        Returns:
            Dict[str, Any]: 字典表示
        """
        result = {
            "rule_id": self.rule_id,
            "engine_name": self.engine_name,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "threshold": self.threshold,
            "alert_level": self.alert_level.value,
            "message_template": self.message_template,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
        }

        if self.last_triggered:
            result["last_triggered"] = self.last_triggered.isoformat()

        return result


class EngineMonitor:
    """引擎监控器

    实时监控所有引擎的运行状态，收集性能指标，检测异常并触发警报。
    支持历史数据存储、趋势分析和报告生成。

    Attributes:
        _engine_registry: 引擎注册表
        _event_engine: 事件引擎
        _engine_factory: 引擎工厂
        _monitoring_interval: 监控间隔（秒）
        _metrics_history: 指标历史数据 {engine_name: {metric_name: deque}}
        _active_alerts: 活跃警报 {alert_id: MonitorAlert}
        _alert_rules: 警报规则列表
        _metric_statistics: 指标统计 {engine_name: {metric_name: MetricStatistic}}
        _monitoring_task: 监控任务
        _is_monitoring: 是否正在监控
        _alert_handlers: 警报处理器列表
    """

    def __init__(self,
                 engine_registry: Optional[EngineRegistry] = None,
                 event_engine: Optional[EventEngine] = None,
                 monitoring_interval: float = 5.0):
        """初始化引擎监控器

        Args:
            engine_registry: 引擎注册表
            event_engine: 事件引擎
            monitoring_interval: 监控间隔（秒）
        """
        self._engine_registry = engine_registry
        self._event_engine = event_engine
        self._engine_factory = None
        self._monitoring_interval = monitoring_interval

        # 数据存储
        self._metrics_history: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=1000))  # 每个指标最多保存1000个点
        )
        self._active_alerts: Dict[str, MonitorAlert] = {}
        self._alert_rules: Dict[str, AlertRule] = {}
        self._metric_statistics: Dict[str, Dict[str, MetricStatistic]] = defaultdict(dict)

        # 任务和状态
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_monitoring = False

        # 警报处理器
        self._alert_handlers: List[Callable] = []

        # 默认警报规则
        self._init_default_alert_rules()

        logger.info(f"引擎监控器初始化完成，监控间隔: {monitoring_interval}秒")

    @property
    def is_monitoring(self) -> bool:
        """获取监控状态

        Returns:
            bool: 是否正在监控
        """
        return self._is_monitoring

    async def start_monitoring(self) -> None:
        """开始监控"""
        if self._is_monitoring:
            logger.warning("监控器已经在运行")
            return

        # 获取依赖组件
        await self._init_dependencies()

        # 启动监控任务
        self._is_monitoring = True
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(),
            name="EngineMonitor"
        )

        logger.info("引擎监控器已启动")

    async def stop_monitoring(self) -> None:
        """停止监控"""
        if not self._is_monitoring:
            return

        self._is_monitoring = False

        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("引擎监控器已停止")

    async def _init_dependencies(self) -> None:
        """初始化依赖组件"""
        # 获取引擎工厂
        if not self._engine_factory:
            try:
                self._engine_factory = EngineFactory()
            except Exception as e:
                logger.warning(f"获取引擎工厂失败: {e}")

        # 获取引擎注册表
        if not self._engine_registry:
            if self._engine_factory:
                # 使用公有方法或属性访问，避免访问 protected 成员
                if hasattr(self._engine_factory, 'engine_registry'):
                    self._engine_registry = self._engine_factory.engine_registry
                elif hasattr(self._engine_factory, 'get_engine_registry'):
                    self._engine_registry = self._engine_factory.get_engine_registry()
                else:
                    logger.warning("引擎注册表未设置且无法从工厂获取")
            else:
                logger.warning("引擎注册表未设置")

        # 获取事件引擎
        if not self._event_engine:
            if self._engine_factory:
                # 使用公有方法或属性访问，避免访问 protected 成员
                if hasattr(self._engine_factory, 'event_engine'):
                    self._event_engine = self._engine_factory.event_engine
                elif hasattr(self._engine_factory, 'get_event_engine'):
                    self._event_engine = self._engine_factory.get_event_engine()
                else:
                    logger.warning("事件引擎未设置且无法从工厂获取")
            else:
                logger.warning("事件引擎未设置")

    def _init_default_alert_rules(self) -> None:
        """初始化默认警报规则"""
        # 引擎状态错误规则 - 使用状态码
        self.add_alert_rule(AlertRule(
            rule_id="engine_status_error",
            engine_name="*",
            metric_name="status",
            condition="==",
            threshold=ComponentStatus.ERROR.code,  # 使用状态码
            alert_level=AlertLevel.ERROR,
            message_template="引擎 {engine_name} 进入错误状态",
            cooldown_seconds=60
        ))

        # 引擎健康状态不健康规则 - 使用状态码
        self.add_alert_rule(AlertRule(
            rule_id="engine_health_unhealthy",
            engine_name="*",
            metric_name="health",
            condition="==",
            threshold=HealthStatus.UNHEALTHY.code,  # 使用状态码
            alert_level=AlertLevel.WARNING,
            message_template="引擎 {engine_name} 健康状态不健康",
            cooldown_seconds=300
        ))

        # 引擎健康状态失败规则 - 使用数值阈值
        # health_mapping: HEALTHY=0, DEGRADED=1, UNHEALTHY=2, FAILED=3, UNKNOWN=4
        self.add_alert_rule(AlertRule(
            rule_id="engine_health_failed",
            engine_name="*",
            metric_name="health",
            condition="==",
            threshold=3.0,  # HealthStatus.FAILED 对应的数值
            alert_level=AlertLevel.CRITICAL,
            message_template="引擎 {engine_name} 健康状态失败",
            cooldown_seconds=60
        ))

        # 内存使用过高规则（示例）
        self.add_alert_rule(AlertRule(
            rule_id="memory_usage_high",
            engine_name="*",
            metric_name="memory_usage_mb",
            condition=">",
            threshold=1024.0,  # 1GB
            alert_level=AlertLevel.WARNING,
            message_template="引擎 {engine_name} 内存使用过高: {value:.1f}MB > {threshold:.1f}MB",
            cooldown_seconds=300
        ))

        # CPU使用率过高规则（示例）
        self.add_alert_rule(AlertRule(
            rule_id="cpu_usage_high",
            engine_name="*",
            metric_name="cpu_percent",
            condition=">",
            threshold=80.0,  # 80%
            alert_level=AlertLevel.WARNING,
            message_template="引擎 {engine_name} CPU使用率过高: {value:.1f}% > {threshold:.1f}%",
            cooldown_seconds=300
        ))

        logger.info(f"初始化了 {len(self._alert_rules)} 个默认警报规则")

    async def _monitoring_loop(self) -> None:
        """监控循环"""
        logger.info("启动引擎监控循环")

        try:
            while self._is_monitoring:
                try:
                    # 收集所有引擎状态
                    await self._collect_engine_status()

                    # 检查警报规则
                    await self._check_alert_rules()

                    # 清理旧的警报
                    self._cleanup_old_alerts()

                    # 等待下次监控
                    await asyncio.sleep(self._monitoring_interval)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"监控循环异常: {e}")
                    await asyncio.sleep(self._monitoring_interval)

        except Exception as e:
            logger.error(f"监控循环意外退出: {e}")
        finally:
            logger.info("引擎监控循环已停止")

    async def _collect_engine_status(self) -> None:
        """收集引擎状态"""
        if not self._engine_registry:
            return

        try:
            # 获取所有引擎
            engines = self._engine_registry.get_all_engines()

            for engine in engines:
                try:
                    # 获取引擎状态信息
                    status_info = engine.get_status_info()

                    # 收集状态指标
                    self._collect_status_metrics(engine.config.name, status_info)

                    # 收集性能指标
                    if "metrics" in status_info:
                        self._collect_performance_metrics(engine.config.name, status_info["metrics"])

                except Exception as e:
                    logger.error(f"收集引擎状态失败: {engine.config.name}, 错误: {e}")

        except Exception as e:
            logger.error(f"收集引擎状态异常: {e}")

    def _collect_status_metrics(self, engine_name: str, status_info: Dict[str, Any]) -> None:
        """收集状态指标

        Args:
            engine_name: 引擎名称
            status_info: 状态信息
        """
        timestamp = datetime.now()

        # 状态指标（转换为数值）
        status_mapping = {
            ComponentStatus.UNINITIALIZED.value: 0,
            ComponentStatus.INITIALIZING.value: 1,
            ComponentStatus.INITIALIZED.value: 2,
            ComponentStatus.STARTING.value: 3,
            ComponentStatus.RUNNING.value: 4,
            ComponentStatus.STOPPING.value: 5,
            ComponentStatus.STOPPED.value: 6,
            ComponentStatus.ERROR.value: 7,
            ComponentStatus.DEGRADED.value: 8
        }

        status_value = status_mapping.get(status_info.get("status", ""), -1)
        self._add_metric(engine_name, "status", float(status_value), timestamp)

        # 健康指标
        health_mapping = {
            HealthStatus.HEALTHY.value: 0,
            HealthStatus.DEGRADED.value: 1,
            HealthStatus.UNHEALTHY.value: 2,
            HealthStatus.FAILED.value: 3,
            HealthStatus.UNKNOWN.value: 4
        }

        health_value = health_mapping.get(status_info.get("health", ""), -1)
        self._add_metric(engine_name, "health", float(health_value), timestamp)

        # 运行时长
        uptime = status_info.get("uptime", 0.0)
        self._add_metric(engine_name, "uptime", float(uptime), timestamp)

        # 错误计数
        has_error = 1 if status_info.get("error_message") else 0
        self._add_metric(engine_name, "has_error", float(has_error), timestamp)

        # 依赖数量
        dependency_count = len(status_info.get("dependencies", []))
        self._add_metric(engine_name, "dependency_count", float(dependency_count), timestamp)

    def _collect_performance_metrics(self, engine_name: str, metrics: Dict[str, Any]) -> None:
        """收集性能指标

        Args:
            engine_name: 引擎名称
            metrics: 性能指标
        """
        timestamp = datetime.now()

        # 收集所有数值型指标
        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                self._add_metric(engine_name, metric_name, float(value), timestamp)

    def _add_metric(self,
                   engine_name: str,
                   metric_name: str,
                   value: float,
                   timestamp: datetime) -> None:
        """添加指标

        Args:
            engine_name: 引擎名称
            metric_name: 指标名称
            value: 指标值
            timestamp: 时间戳
        """
        try:
            # 创建指标对象
            metric = EngineMetric(
                engine_name=engine_name,
                metric_name=metric_name,
                value=value,
                timestamp=timestamp
            )

            # 保存到历史
            self._metrics_history[engine_name][metric_name].append(metric)

            # 更新统计
            if metric_name not in self._metric_statistics[engine_name]:
                self._metric_statistics[engine_name][metric_name] = MetricStatistic(
                    metric_name=metric_name
                )

            self._metric_statistics[engine_name][metric_name].update(value)

            # 发布指标事件
            if self._event_engine:
                try:

                    metric_entity = metric.to_metric_entity()
                    event = EventEntity(
                        event_id=str(uuid.uuid4()),
                        event_type="engine_metric",
                        data=metric_entity.to_dict(),
                        source=f"monitor:{engine_name}",
                        priority=PriorityLevel.NORMAL.value
                    )

                    asyncio.create_task(self._event_engine.put(event))
                except Exception as e:
                    logger.debug(f"发布指标事件失败: {e}")

        except Exception as e:
            logger.error(f"添加指标失败: {engine_name}.{metric_name}, 错误: {e}")

    async def _check_alert_rules(self) -> None:
        """检查警报规则"""
        for rule_id, rule in list(self._alert_rules.items()):
            if not rule.enabled:
                continue

            # 检查所有引擎或特定引擎
            if rule.engine_name == "*":
                # 检查所有引擎
                for engine_name in self._metrics_history.keys():
                    await self._check_rule_for_engine(rule, engine_name)
            else:
                # 检查特定引擎
                await self._check_rule_for_engine(rule, rule.engine_name)

    async def _check_rule_for_engine(self, rule: AlertRule, engine_name: str) -> None:
        """为指定引擎检查规则

        Args:
            rule: 警报规则
            engine_name: 引擎名称
        """
        try:
            # 获取最新指标值
            metric_history = self._metrics_history.get(engine_name, {}).get(rule.metric_name)
            if not metric_history or len(metric_history) == 0:
                return

            # 使用索引访问 deque 的最新值
            latest_metric = metric_history[-1]

            # 检查条件
            if rule.check_condition(latest_metric.value):
                # 创建警报
                alert = rule.create_alert(latest_metric.value)

                # 保存警报
                self._active_alerts[alert.alert_id] = alert

                # 触发警报处理器
                await self._trigger_alert_handlers(alert)

                # 发布警报事件
                if self._event_engine:
                    try:

                        alert_entity = alert.to_alert_entity()
                        event = EventEntity(
                            event_id=str(uuid.uuid4()),
                            event_type="engine_alert",
                            data=alert_entity.to_dict(),
                            source="engine_monitor",
                            priority=PriorityLevel.HIGH.value
                        )

                        asyncio.create_task(self._event_engine.put(event))
                    except Exception as e:
                        logger.error(f"发布警报事件失败: {e}")

        except Exception as e:
            logger.error(f"检查警报规则失败: {rule.rule_id}, 引擎: {engine_name}, 错误: {e}")

    async def _trigger_alert_handlers(self, alert: MonitorAlert) -> None:
        """触发警报处理器

        Args:
            alert: 警报对象
        """
        for handler in self._alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"警报处理器异常: {e}")

    def _cleanup_old_alerts(self) -> None:
        """清理旧的警报"""
        cutoff_time = datetime.now() - timedelta(days=7)  # 保留7天

        alerts_to_remove = []
        for alert_id, alert in self._active_alerts.items():
            if alert.resolved and alert.resolved_time and alert.resolved_time < cutoff_time:
                alerts_to_remove.append(alert_id)

        for alert_id in alerts_to_remove:
            del self._active_alerts[alert_id]

        if alerts_to_remove:
            logger.debug(f"清理了 {len(alerts_to_remove)} 个旧的警报")

    def add_alert_rule(self, rule: AlertRule) -> None:
        """添加警报规则

        Args:
            rule: 警报规则
        """
        self._alert_rules[rule.rule_id] = rule
        logger.info(f"添加警报规则: {rule.rule_id}")

    def remove_alert_rule(self, rule_id: str) -> bool:
        """移除警报规则

        Args:
            rule_id: 规则ID

        Returns:
            bool: 是否成功移除
        """
        if rule_id in self._alert_rules:
            del self._alert_rules[rule_id]
            logger.info(f"移除警报规则: {rule_id}")
            return True
        else:
            logger.warning(f"警报规则不存在: {rule_id}")
            return False

    def update_alert_rule(self, rule_id: str, **kwargs) -> bool:
        """更新警报规则

        Args:
            rule_id: 规则ID
            **kwargs: 更新字段

        Returns:
            bool: 是否成功更新
        """
        if rule_id not in self._alert_rules:
            logger.warning(f"警报规则不存在: {rule_id}")
            return False

        rule = self._alert_rules[rule_id]

        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        logger.info(f"更新警报规则: {rule_id}")
        return True

    def add_alert_handler(self, handler: Callable) -> None:
        """添加警报处理器

        Args:
            handler: 警报处理函数
        """
        self._alert_handlers.append(handler)
        logger.debug(f"添加警报处理器: {handler.__name__ if hasattr(handler, '__name__') else 'anonymous'}")

    def remove_alert_handler(self, handler: Callable) -> bool:
        """移除警报处理器

        Args:
            handler: 警报处理函数

        Returns:
            bool: 是否成功移除
        """
        if handler in self._alert_handlers:
            self._alert_handlers.remove(handler)
            logger.debug(f"移除警报处理器: {handler.__name__ if hasattr(handler, '__name__') else 'anonymous'}")
            return True
        return False

    def get_engine_metrics(self,
                          engine_name: str,
                          metric_name: Optional[str] = None,
                          limit: int = 100) -> List[EngineMetric]:
        """获取引擎指标

        Args:
            engine_name: 引擎名称
            metric_name: 指标名称（可选，None表示获取所有）
            limit: 限制返回数量

        Returns:
            List[EngineMetric]: 指标列表
        """
        if engine_name not in self._metrics_history:
            return []

        metrics = []

        if metric_name:
            # 获取特定指标
            if metric_name in self._metrics_history[engine_name]:
                history = self._metrics_history[engine_name][metric_name]
                metrics.extend(list(history)[-limit:])
        else:
            # 获取所有指标
            for hist in self._metrics_history[engine_name].values():
                metrics.extend(list(hist)[-limit:])

        # 按时间戳排序
        metrics.sort(key=lambda m: m.timestamp)

        return metrics[-limit:] if limit else metrics

    def get_engine_statistics(self, engine_name: str) -> Dict[str, MetricStatistic]:
        """获取引擎统计信息

        Args:
            engine_name: 引擎名称

        Returns:
            Dict[str, MetricStatistic]: 指标统计字典
        """
        return self._metric_statistics.get(engine_name, {}).copy()

    def get_active_alerts(self,
                         engine_name: Optional[str] = None,
                         level: Optional[AlertLevel] = None,
                         unresolved_only: bool = True) -> List[MonitorAlert]:
        """获取活跃警报

        Args:
            engine_name: 引擎名称过滤（可选）
            level: 警报级别过滤（可选）
            unresolved_only: 是否只返回未解决的警报

        Returns:
            List[MonitorAlert]: 警报列表
        """
        filtered_alerts = []

        for alert in self._active_alerts.values():
            # 过滤引擎名称
            if engine_name and alert.engine_name != engine_name:
                continue

            # 过滤警报级别
            if level and alert.alert_level != level:
                continue

            # 过滤解决状态
            if unresolved_only and alert.resolved:
                continue

            filtered_alerts.append(alert)

        # 按时间戳排序（最新的在前）
        filtered_alerts.sort(key=lambda a: a.timestamp, reverse=True)

        return filtered_alerts

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """确认警报

        Args:
            alert_id: 警报ID
            acknowledged_by: 确认人

        Returns:
            bool: 确认是否成功
        """
        if alert_id not in self._active_alerts:
            logger.warning(f"警报不存在: {alert_id}")
            return False

        alert = self._active_alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by

        logger.info(f"警报已确认: {alert_id}, 确认人: {acknowledged_by}")
        return True

    def resolve_alert(self, alert_id: str) -> bool:
        """解决警报

        Args:
            alert_id: 警报ID

        Returns:
            bool: 解决是否成功
        """
        if alert_id not in self._active_alerts:
            logger.warning(f"警报不存在: {alert_id}")
            return False

        alert = self._active_alerts[alert_id]
        alert.resolved = True
        alert.resolved_time = datetime.now()

        logger.info(f"警报已解决: {alert_id}")
        return True

    def get_monitor_status(self) -> Dict[str, Any]:
        """获取监控器状态

        Returns:
            Dict[str, Any]: 监控器状态信息
        """
        engine_count = len(self._metrics_history)
        metric_count = sum(len(metrics) for metrics in self._metrics_history.values())

        active_alerts = self.get_active_alerts(unresolved_only=True)
        total_alerts = len(self._active_alerts)

        return {
            "is_monitoring": self._is_monitoring,
            "monitoring_interval": self._monitoring_interval,
            "engine_count": engine_count,
            "metric_count": metric_count,
            "alert_rule_count": len(self._alert_rules),
            "active_alert_count": len(active_alerts),
            "total_alert_count": total_alerts,
            "alert_handler_count": len(self._alert_handlers),
            "timestamp": datetime.now().isoformat()
        }

    async def generate_report(self,
                             report_type: str = "summary",
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """生成监控报告

        Args:
            report_type: 报告类型（summary/detailed/alert）
            start_time: 开始时间（可选）
            end_time: 结束时间（可选）

        Returns:
            Dict[str, Any]: 报告数据
        """
        if not start_time:
            start_time = datetime.now() - timedelta(hours=24)  # 默认最近24小时

        if not end_time:
            end_time = datetime.now()

        report = {
            "report_type": report_type,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "events": {}
        }

        if report_type == "summary":
            # 摘要报告
            report["events"] = {
                "engine_count": len(self._metrics_history),
                "metric_count": sum(len(metrics) for metrics in self._metrics_history.values()),
                "active_alert_count": len(self.get_active_alerts(unresolved_only=True)),
                "alert_rule_count": len(self._alert_rules),
                "monitor_status": self.get_monitor_status()
            }

        elif report_type == "detailed":
            # 详细报告
            detailed_data = {}

            for engine_name, metrics in self._metrics_history.items():
                engine_data = {
                    "metric_count": len(metrics),
                    "statistics": {}
                }

                # 统计信息
                if engine_name in self._metric_statistics:
                    engine_data["statistics"] = {
                        metric_name: stat.to_dict()
                        for metric_name, stat in self._metric_statistics[engine_name].items()
                    }

                # 活跃警报
                engine_alerts = self.get_active_alerts(engine_name=engine_name, unresolved_only=True)
                engine_data["active_alerts"] = len(engine_alerts)

                detailed_data[engine_name] = engine_data

            report["events"] = detailed_data

        elif report_type == "alert":
            # 警报报告
            alerts = self.get_active_alerts(unresolved_only=False)

            # 过滤时间范围内的警报
            filtered_alerts = [
                alert for alert in alerts
                if start_time <= alert.timestamp <= end_time
            ]

            # 初始化按引擎统计的字典
            alerts_by_engine = {}
            
            # 按引擎统计
            for alert in filtered_alerts:
                engine_name = alert.engine_name
                if engine_name not in alerts_by_engine:
                    alerts_by_engine[engine_name] = 0
                alerts_by_engine[engine_name] += 1
            
            report["events"] = {
                "total_alerts": len(filtered_alerts),
                "alerts_by_level": {
                    level.value: sum(1 for a in filtered_alerts if a.alert_level == level)
                    for level in AlertLevel
                },
                "alerts_by_engine": alerts_by_engine,
                "alert_list": [alert.to_dict() for alert in filtered_alerts]
            }

        return report


# 全局监控器实例
_monitor: Optional[EngineMonitor] = None


async def get_engine_monitor() -> EngineMonitor:
    """获取全局引擎监控器实例

    Returns:
        EngineMonitor: 引擎监控器实例
    """
    global _monitor
    if _monitor is None:
        # 获取依赖组件
        factory = EngineFactory()

        # 使用公有方法或属性访问，避免访问 protected 成员
        engine_registry = None
        event_engine = None

        if hasattr(factory, 'engine_registry'):
            engine_registry = factory.engine_registry
        elif hasattr(factory, 'get_engine_registry'):
            engine_registry = factory.get_engine_registry()

        if hasattr(factory, 'event_engine'):
            event_engine = factory.event_engine
        elif hasattr(factory, 'get_event_engine'):
            event_engine = factory.get_event_engine()

        _monitor = EngineMonitor(
            engine_registry=engine_registry,
            event_engine=event_engine
        )
    return _monitor


async def start_monitoring() -> None:
    """开始监控（便捷函数）"""
    monitor = await get_engine_monitor()
    await monitor.start_monitoring()


async def stop_monitoring() -> None:
    """停止监控（便捷函数）"""
    monitor = await get_engine_monitor()
    await monitor.stop_monitoring()