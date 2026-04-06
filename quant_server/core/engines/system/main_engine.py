"""
主引擎
系统的协调中心，负责初始化、管理和协调所有子引擎

核心职责：
1. 系统启动和关闭的流程控制
2. 子引擎的注册和管理
3. 全局配置管理和分发
4. 系统状态监控和报告
5. 异常处理和恢复协调

主引擎是系统的"大脑"，确保所有组件协同工作。
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, cast
from datetime import datetime

# 导入统一类型定义
from ..types.entities import (
    EngineConfig as EngineConfigEntity,
    SystemConfig as SystemConfigEntity,
    Event as EventEntity
)
from ..types.enums import (
    HealthStatus,
    EngineType,
    PriorityLevel,
    EventType,
    SystemMode
)

# 导入引擎基类
from ..base.engine_base import EngineBase
from .event_engine import EventEngine
from .engine_registry import EngineRegistry
from ..utils.engine_factory import EngineFactory
from ..utils.engine_monitor import EngineMonitor

logger = logging.getLogger(__name__)


class MainEngine(EngineBase):
    """主引擎

    系统的总控制器，负责协调所有子引擎，管理系统状态，处理全局事件。
    采用单例模式确保全局只有一个主引擎实例。

    Attributes:
        _instance: 单例实例
        _system_config: 系统配置实体
        _engine_factory: 引擎工厂
        _engine_registry: 引擎注册表
        _engine_monitor: 引擎监控器
        _web_socket_manager: WebSocket管理器
        _startup_timestamp: 系统启动时间戳
        _system_status: 系统状态
        _module_engines: 模块引擎映射 {module_name: EngineBase}
        _event_handlers: 事件处理器映射
    """

    _instance: Optional['MainEngine'] = None
    _lock = asyncio.Lock()

    def __new__(cls, config: Optional[EngineConfigEntity] = None,
                event_engine: Optional[EventEngine] = None):
        """单例模式实现

        Args:
            config: 引擎配置实体
            event_engine: 事件引擎

        Returns:
            MainEngine: 主引擎实例
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[EngineConfigEntity] = None,
                 event_engine: Optional[EventEngine] = None):
        """初始化主引擎

        Args:
            config: 引擎配置实体
            event_engine: 事件引擎
        """
        # 确保只初始化一次
        if hasattr(self, '_initialized') and self._initialized:
            return

        # 默认配置
        if config is None:
            config = EngineConfigEntity(
                name="main_engine",
                engine_type=EngineType.MAIN,
                auto_start=True,
                max_retries=3,
                retry_delay=1.0,
                config={}
            )

        super().__init__(config, event_engine)

        # 设置引擎类型
        self.record.engine_type = EngineType.MAIN

        # 系统配置
        self._system_config: Optional[SystemConfigEntity] = None

        # 系统组件
        self._engine_factory: Optional[EngineFactory] = None
        self._engine_registry: Optional[EngineRegistry] = None
        self._engine_monitor: Optional[EngineMonitor] = None
        self._web_socket_manager = None  # WebSocket管理器

        # 系统状态
        self._startup_timestamp: Optional[datetime] = None
        self._system_status: Dict[str, Any] = {
            "mode": "unknown",
            "uptime": 0,
            "engine_count": 0,
            "module_count": 0,
            "last_check": None
        }

        # 模块引擎映射
        self._module_engines: Dict[str, EngineBase] = {}

        # 事件处理器
        self._event_handlers: Dict[str, List[str]] = {}

        self._initialized = True
        logger.info("主引擎初始化完成")

    async def _on_initialize(self):
        """主引擎初始化逻辑"""
        logger.info("初始化主引擎")

    async def _on_start(self) -> None:
        """主引擎启动逻辑"""
        logger.info("启动主引擎")

        # 设置启动时间戳
        self._startup_timestamp = datetime.now()

        try:
            # 初始化系统配置
            await self._initialize_system_config()

            # 初始化核心组件
            await self._initialize_core_components()

            # 注册事件处理器
            await self._register_event_handlers()

            # 启动子引擎
            await self._start_child_engines()

            # 启动监控
            if self._system_config and self._system_config.enable_monitoring:
                await self._start_monitoring()

            # 启动WebSocket
            if self._system_config and self._system_config.enable_web_socket:
                await self._start_web_socket()

            # 发布系统启动事件
            await self._publish_system_event(
                EventType.SYSTEM_STARTED,
                {
                    "system_name": self._system_config.system_name if self._system_config else "unknown",
                    "version": self._system_config.version if self._system_config else "unknown",
                    "mode": self._system_config.mode if self._system_config else "unknown",
                    "startup_time": self._startup_timestamp.isoformat()
                }
            )

            logger.info(
                f"主引擎启动完成，系统: {self._system_config.system_name if self._system_config else 'unknown'}, "
                f"版本: {self._system_config.version if self._system_config else 'unknown'}, "
                f"模式: {self._system_config.mode if self._system_config else 'unknown'}"
            )

        except Exception as e:
            logger.error(f"主引擎启动失败: {e}")
            raise

    async def _on_stop(self) -> None:
        """主引擎停止逻辑"""
        logger.info("停止主引擎")

        try:
            # 停止WebSocket
            if self._web_socket_manager:
                await self._stop_web_socket()

            # 停止监控
            if self._engine_monitor and getattr(self._engine_monitor, 'is_monitoring', False):
                await self._engine_monitor.stop_monitoring()

            # 停止子引擎
            await self._stop_child_engines()

            # 注销事件处理器
            await self._unregister_event_handlers()

            # 清理资源
            self._module_engines.clear()
            self._event_handlers.clear()

            # 计算运行时长
            uptime = 0.0
            if self._startup_timestamp:
                uptime = (datetime.now() - self._startup_timestamp).total_seconds()

            # 发布系统停止事件
            await self._publish_system_event(
                EventType.SYSTEM_STOPPED,
                {
                    "system_name": self._system_config.system_name if self._system_config else "unknown",
                    "uptime": uptime,
                    "stop_time": datetime.now().isoformat()
                }
            )

            logger.info(f"主引擎停止完成，运行时长: {uptime:.1f}秒")

        except Exception as e:
            logger.error(f"主引擎停止失败: {e}")
            raise

    async def _initialize_system_config(self) -> None:
        """初始化系统配置"""
        # 从配置文件或环境变量加载系统配置
        system_config_data = self.config.config.get("system", {})

        # 创建系统配置实体
        self._system_config = SystemConfigEntity(
            system_name=system_config_data.get("system_name", "量化交易系统"),
            version=system_config_data.get("version", "1.0.0"),
            mode=SystemMode(system_config_data.get("mode", "development")),
            auto_start_engines=system_config_data.get("auto_start_engines", True),
            enable_monitoring=system_config_data.get("enable_monitoring", True),
            enable_web_socket=system_config_data.get("enable_web_socket", True),
            max_concurrent_tasks=system_config_data.get("max_concurrent_tasks", 100),
            shutdown_timeout=system_config_data.get("shutdown_timeout", 30.0),
            engine_configs=system_config_data.get("engine_configs", {})
        )

        # 验证配置
        config_errors = self._system_config.validate()
        if config_errors:
            raise ValueError(f"系统配置验证失败: {config_errors}")

        logger.info(
            f"系统配置加载完成: {self._system_config.system_name} "
            f"v{self._system_config.version}"
        )

        # 加载模块配置（用于动态注册引擎）
        self._modules_config = self.config.config.get("modules", {})
        if isinstance(self._modules_config, dict):
            logger.info(f"加载模块配置: {list(self._modules_config.keys())}")
        else:
            logger.info(f"加载模块配置: {type(self._modules_config)} - {self._modules_config}")

    async def _initialize_core_components(self) -> None:
        """初始化核心组件"""
        # 初始化引擎工厂
        self._engine_factory = EngineFactory()

        # 初始化事件引擎（如果未提供）
        if not self.event_engine:
            # 注意：这里我们需要确保EngineFactory的create_engine返回的是EventEngine
            # 但为了类型安全，我们进行类型转换
            event_engine = await self._engine_factory.create_engine(
                EngineType.EVENT,
                config=self._system_config.engine_configs.get("event_engine", {}) if self._system_config else {},
                instance_name="event_engine"
            )
            # 进行类型转换
            self.event_engine = cast(EventEngine, event_engine)

        # 初始化引擎注册表
        self._engine_registry = EngineRegistry()

        # 初始化引擎监控器
        self._engine_monitor = EngineMonitor(
            engine_registry=self._engine_registry,
            event_engine=cast(EventEngine, self.event_engine)
        )

        # 初始化WebSocket管理器（如果启用）
        if self._system_config and self._system_config.enable_web_socket:
            await self._initialize_web_socket_manager()

        logger.info("核心组件初始化完成")

    async def _initialize_web_socket_manager(self) -> None:
        """初始化WebSocket管理器"""
        try:
            from ...api.websocket.manager import WebSocketManager
            self._web_socket_manager = WebSocketManager(self.event_engine)

            # 注册WebSocket事件处理器
            await self._web_socket_manager.initialize()

            logger.info("WebSocket管理器初始化完成")

        except ImportError:
            logger.warning("WebSocket管理器模块未找到，WebSocket功能将被禁用")
        except Exception as e:
            logger.error(f"WebSocket管理器初始化失败: {e}")

    async def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        if self.event_engine:
            # 注册系统事件处理器
            # 注意：这里我们直接调用event_engine的方法，而不是EngineBase的方法
            event_engine = cast(EventEngine, self.event_engine)
            system_health_handler = event_engine.register(
                "system_health_check",
                self._handle_system_health_check
            )
            engine_status_handler = event_engine.register(
                "engine_status_changed",
                self._handle_engine_status_changed
            )
            system_alert_handler = event_engine.register(
                "system_alert",
                self._handle_system_alert
            )

            # 保存处理器ID
            self._event_handlers["system_health_check"] = [system_health_handler]
            self._event_handlers["engine_status_changed"] = [engine_status_handler]
            self._event_handlers["system_alert"] = [system_alert_handler]

            logger.debug("主引擎事件处理器注册完成")

    async def _unregister_event_handlers(self) -> None:
        """注销事件处理器"""
        if self.event_engine:
            event_engine = cast(EventEngine, self.event_engine)
            for event_type, handler_ids in self._event_handlers.items():
                for handler_id in handler_ids:
                    event_engine.unregister(event_type, handler_id)

            self._event_handlers.clear()
            logger.debug("主引擎事件处理器注销完成")

    async def _start_child_engines(self) -> None:
        """启动子引擎"""
        if not self._system_config or not self._system_config.auto_start_engines:
            logger.info("跳过自动启动子引擎（配置为手动启动）")
            return

        # 第一步：根据 modules 配置动态注册引擎
        await self._register_module_engines()

        # 第二步：启动已注册的引擎
        await self._start_registered_engines()

    async def _register_module_engines(self) -> None:
        """根据 modules 配置动态注册引擎"""
        if not self._modules_config:
            logger.info("没有模块配置，跳过动态注册")
            return

        # 模块名称到引擎类型的映射
        module_to_engine_type = {
            "data": EngineType.DATA_SYNC,
            "strategy": EngineType.STRATEGY_MANAGER,
            "trade": EngineType.EXECUTION_ENGINE,
            "backtest": EngineType.BACKTEST_ENGINE,
            "account": EngineType.ACCOUNT_ENGINE,
            "analysis": EngineType.PERFORMANCE_ENGINE,
            "monitor": EngineType.SYSTEM_MONITOR,
            "system": EngineType.SYSTEM,
        }

        for module_name, module_config in self._modules_config.items():
            # 检查模块是否启用
            if not module_config.get("enabled", False):
                logger.info(f"模块 {module_name} 未启用，跳过注册")
                continue

            # 获取对应的引擎类型
            engine_type = module_to_engine_type.get(module_name)
            if not engine_type:
                logger.warning(f"模块 {module_name} 没有对应的引擎类型，跳过")
                continue

            # 动态注册引擎
            try:
                success = self._engine_factory.register_engine_from_module(
                    engine_type=engine_type,
                    module_name=module_name,
                    module_config=module_config
                )
                if success:
                    logger.info(f"模块 {module_name} 引擎注册成功")
            except Exception as e:
                logger.error(f"模块 {module_name} 引擎注册失败: {e}")

    async def _start_registered_engines(self) -> None:
        """启动已注册的引擎（根据配置决定是否启动）"""
        # 跳过事件引擎（已经启动）
        registered_types = self._engine_factory.list_engine_types()
        if EngineType.EVENT in registered_types:
            logger.debug("事件引擎已注册")

        # 获取所有已注册的引擎类型
        registered_types = self._engine_factory.list_engine_types()
        logger.info(f"已注册的引擎类型: {[t.value for t in registered_types]}")

        start_tasks = []
        for engine_type in registered_types:
            # 跳过事件引擎（已经启动）
            if engine_type == EngineType.EVENT:
                continue

            # 跳过主引擎（不需要自动启动）
            if engine_type == EngineType.MAIN:
                continue

            # 获取引擎配置
            engine_config = self._system_config.engine_configs.get(engine_type.value, {})

            # 检查是否启用（默认启用）
            if not engine_config.get("enabled", True):
                logger.info(f"引擎 {engine_type.value} 在配置中被禁用，跳过启动")
                continue

            start_tasks.append(self._start_child_engine(engine_type, engine_config))

        # 并行启动引擎
        if start_tasks:
            results = await asyncio.gather(*start_tasks, return_exceptions=True)

            # 统计启动结果
            success_count = sum(1 for r in results if r is True)
            error_count = sum(1 for r in results if isinstance(r, Exception))

            logger.info(f"子引擎启动完成: 成功 {success_count} 个, 失败 {error_count} 个")

    async def _start_child_engine(self,
                                 engine_type: EngineType,
                                 engine_config: Dict[str, Any]) -> bool:
        """启动子引擎

        Args:
            engine_type: 引擎类型
            engine_config: 引擎配置

        Returns:
            bool: 启动是否成功
        """
        try:
            # 创建引擎实例
            engine = await self._engine_factory.create_engine(
                engine_type,
                config=engine_config,
                lazy_init=False  # 立即启动
            )

            # 注册到引擎注册表（传递正确的category参数）
            if self._engine_registry:
                # 获取引擎描述符以获取category信息
                from quant_server.core.engines.utils.engine_factory import EngineFactory
                factory_instance = EngineFactory()
                descriptor = factory_instance.get_engine_descriptor(engine_type)
                if descriptor:
                    await self._engine_registry.register_engine(engine, descriptor.category)
                else:
                    logger.warning(f"无法获取引擎描述符: {engine_type}, 使用默认分类")
                    from quant_server.core.engines.types.enums import EngineCategory
                    await self._engine_registry.register_engine(engine, EngineCategory.SYSTEM)

            # 保存到模块映射
            module_name = engine_type.value.replace("_engine", "")
            self._module_engines[module_name] = engine

            logger.info(f"子引擎启动成功: {engine.config.name}")
            return True

        except Exception as e:
            logger.error(f"子引擎启动失败: {engine_type.value}, 错误: {e}")
            return False

    async def _stop_child_engines(self) -> None:
        """停止子引擎"""
        if not self._engine_factory:
            return

        # 按照依赖关系的逆序关闭引擎
        try:
            shutdown_results = await self._engine_factory.shutdown_all_engines(force=False)

            success_count = sum(shutdown_results.values())
            total_count = len(shutdown_results)

            logger.info(f"子引擎停止完成: 成功 {success_count}/{total_count}")

        except Exception as e:
            logger.error(f"停止子引擎失败: {e}")

    async def _start_monitoring(self) -> None:
        """启动监控"""
        if not self._engine_monitor:
            logger.warning("引擎监控器未初始化，无法启动监控")
            return

        try:
            await self._engine_monitor.start_monitoring()
            logger.info("引擎监控已启动")
        except Exception as e:
            logger.error(f"启动引擎监控失败: {e}")

    async def _stop_monitoring(self) -> None:
        """停止监控"""
        if self._engine_monitor and getattr(self._engine_monitor, 'is_monitoring', False):
            await self._engine_monitor.stop_monitoring()
            logger.info("引擎监控已停止")

    async def _start_web_socket(self) -> None:
        """启动WebSocket"""
        if not self._web_socket_manager:
            return

        try:
            # 启动WebSocket服务
            await self._web_socket_manager.start()
            logger.info("WebSocket服务已启动")
        except Exception as e:
            logger.error(f"启动WebSocket服务失败: {e}")

    async def _stop_web_socket(self) -> None:
        """停止WebSocket"""
        if self._web_socket_manager:
            await self._web_socket_manager.stop()
            logger.info("WebSocket服务已停止")

    async def _publish_system_event(self, event_type: EventType, data: Dict[str, Any]) -> None:
        """发布系统事件

        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if self.event_engine:
            try:
                event = EventEntity(
                    event_id=f"system_{event_type.value}_{datetime.now().timestamp()}",
                    event_type=event_type.value,
                    source="main_engine",
                    data=data,
                    priority=PriorityLevel.HIGH.value,
                    timestamp=datetime.now()
                )

                event_engine = cast(EventEngine, self.event_engine)
                await event_engine.put(event)

                # 通过WebSocket广播（如果启用）
                if self._web_socket_manager:
                    await self._web_socket_manager.broadcast_event(event)

            except Exception as e:
                logger.error(f"发布系统事件失败: {e}")

    async def _handle_system_health_check(self, event: EventEntity) -> None:
        """处理系统健康检查事件

        Args:
            event: 事件对象
        """
        # 更新系统状态
        await self._update_system_status()

        # 发布系统状态事件
        await self._publish_system_event(EventType.SYSTEM_STARTED, self._system_status)

    async def _handle_engine_status_changed(self, event: EventEntity) -> None:
        """处理引擎状态变化事件

        Args:
            event: 事件对象
        """
        # 更新系统状态中的引擎信息
        await self._update_system_status()

        # 通过WebSocket广播引擎状态变化
        if self._web_socket_manager:
            await self._web_socket_manager.broadcast_event(event)

    async def _handle_system_alert(self, event: EventEntity) -> None:
        """处理系统警报事件

        Args:
            event: 事件对象
        """
        alert_data = event.data

        # 记录警报
        logger.warning(f"系统警报: {alert_data.get('message', 'Unknown alert')}")

        # 通过WebSocket广播警报
        if self._web_socket_manager:
            await self._web_socket_manager.broadcast_event(event)

    async def _update_system_status(self) -> None:
        """更新系统状态"""
        if not self._engine_registry:
            return

        try:
            # 获取所有引擎
            engines = self._engine_registry.get_all_engines()

            # 统计引擎状态
            status_counts = {}
            health_counts = {}

            for engine in engines:
                status = engine.record.status.value
                health = engine.record.health.value

                status_counts[status] = status_counts.get(status, 0) + 1
                health_counts[health] = health_counts.get(health, 0) + 1

            # 计算系统健康度
            total_engines = len(engines)
            healthy_engines = health_counts.get(HealthStatus.HEALTHY.value, 0)
            system_health = (
                HealthStatus.HEALTHY.value if healthy_engines == total_engines
                else HealthStatus.DEGRADED.value
            )

            # 计算运行时长
            uptime = 0.0
            if self._startup_timestamp:
                uptime = (datetime.now() - self._startup_timestamp).total_seconds()

            # 更新系统状态
            self._system_status.update({
                "mode": self._system_config.mode if self._system_config else "unknown",
                "uptime": uptime,
                "engine_count": total_engines,
                "module_count": len(self._module_engines),
                "status_counts": status_counts,
                "health_counts": health_counts,
                "system_health": system_health,
                "last_check": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"更新系统状态失败: {e}")

    async def get_engine(self, engine_name: str) -> Optional[EngineBase]:
        """获取引擎实例

        Args:
            engine_name: 引擎名称

        Returns:
            Optional[EngineBase]: 引擎实例
        """
        # 先检查模块引擎
        if engine_name in self._module_engines:
            return self._module_engines[engine_name]

        # 检查引擎工厂
        if self._engine_factory:
            return await self._engine_factory.get_engine(engine_name)

        # 检查引擎注册表
        if self._engine_registry:
            return self._engine_registry.get_engine(engine_name)

        return None

    async def get_module_engine(self, module_name: str) -> Optional[EngineBase]:
        """获取模块引擎

        Args:
            module_name: 模块名称

        Returns:
            Optional[EngineBase]: 引擎实例
        """
        return self._module_engines.get(module_name)

    def get_all_engines(self) -> List[EngineBase]:
        """获取所有引擎实例

        Returns:
            List[EngineBase]: 引擎列表
        """
        engines = []

        # 添加模块引擎
        engines.extend(self._module_engines.values())

        # 添加工厂中的引擎
        if self._engine_factory:
            engine_names = self._engine_factory.list_engine_instances()
            for name in engine_names:
                engine = self._engine_factory.get_engine(name)
                if engine and engine not in engines:
                    engines.append(engine)

        return engines

    async def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态

        Returns:
            Dict[str, Any]: 系统状态信息
        """
        # 更新系统状态
        await self._update_system_status()

        # 获取引擎状态
        engine_status = {}
        if self._engine_factory:
            engine_status = await self._engine_factory.get_all_engine_status()

        # 获取监控状态
        monitor_status = {}
        if self._engine_monitor:
            monitor_status = self._engine_monitor.get_monitor_status()

        # 获取WebSocket状态
        web_socket_active = False
        if self._web_socket_manager and hasattr(self._web_socket_manager, 'is_active'):
            web_socket_active = self._web_socket_manager.is_active()

        return {
            "events": {
                "name": self._system_config.system_name if self._system_config else "unknown",
                "version": self._system_config.version if self._system_config else "unknown",
                "mode": self._system_config.mode if self._system_config else "unknown",
                "startup_time": self._startup_timestamp.isoformat() if self._startup_timestamp else None,
                "status": self._system_status
            },
            "engines": {
                "total": len(self.get_all_engines()),
                "status": engine_status
            },
            "monitoring": monitor_status,
            "web_socket": {
                "enabled": self._system_config.enable_web_socket if self._system_config else False,
                "active": web_socket_active
            },
            "timestamp": datetime.now().isoformat()
        }

    async def broadcast_message(self, message_type: str, data: Dict[str, Any]) -> None:
        """广播消息

        Args:
            message_type: 消息类型
            data: 消息数据
        """
        # 通过事件引擎广播
        try:
            event_type = EventType(f"broadcast_{message_type}")
            await self._publish_system_event(event_type, data)
        except ValueError:
            # 如果EventType枚举中没有该值，使用字符串
            await self._publish_system_event(EventType.SYSTEM_STARTED, {
                "message_type": message_type,
                "data": data
            })

    async def execute_command(self,
                             command: str,
                             params: Dict[str, Any]) -> Dict[str, Any]:
        """执行命令

        Args:
            command: 命令名称
            params: 命令参数

        Returns:
            Dict[str, Any]: 命令执行结果
        """
        logger.info(f"执行命令: {command}, 参数: {params}")

        try:
            if command == "system_status":
                return await self.get_system_status()

            elif command == "engine_status":
                engine_name = params.get("engine_name")
                if engine_name:
                    engine = await self.get_engine(engine_name)
                    if engine:
                        return engine.get_status_info()
                    else:
                        return {"error": f"引擎不存在: {engine_name}"}
                else:
                    if self._engine_factory:
                        return await self._engine_factory.get_all_engine_status()
                    else:
                        return {"error": "引擎工厂未初始化"}

            elif command == "start_engine":
                engine_type_str = params.get("engine_type")
                if not engine_type_str:
                    return {"error": "缺少参数: engine_type"}

                try:
                    engine_type = EngineType(engine_type_str)

                    if self._engine_factory:
                        engine_config = params.get("config", {})
                        instance_name = params.get("instance_name")

                        engine = await self._engine_factory.create_engine(
                            engine_type,
                            config=engine_config,
                            instance_name=instance_name
                        )

                        return {
                            "success": True,
                            "engine_name": engine.config.name,
                            "status": engine.record.status.value
                        }
                    else:
                        return {"error": "引擎工厂未初始化"}

                except ValueError:
                    return {"error": f"无效的引擎类型: {engine_type_str}"}

            elif command == "stop_engine":
                engine_name = params.get("engine_name")
                if not engine_name:
                    return {"error": "缺少参数: engine_name"}

                force = params.get("force", False)

                if self._engine_factory:
                    success = await self._engine_factory.destroy_engine(engine_name, force)

                    return {
                        "success": success,
                        "engine_name": engine_name
                    }
                else:
                    return {"error": "引擎工厂未初始化"}

            elif command == "restart_engine":
                engine_name = params.get("engine_name")
                if not engine_name:
                    return {"error": "缺少参数: engine_name"}

                if self._engine_factory:
                    success = await self._engine_factory.restart_engine(engine_name)

                    return {
                        "success": success,
                        "engine_name": engine_name
                    }
                else:
                    return {"error": "引擎工厂未初始化"}

            elif command == "system_health_check":
                # 触发系统健康检查
                await self._update_system_status()

                return {
                    "success": True,
                    "system_health": self._system_status.get("system_health", "unknown"),
                    "timestamp": datetime.now().isoformat()
                }

            else:
                return {"error": f"未知命令: {command}"}

        except Exception as e:
            logger.error(f"执行命令失败: {command}, 错误: {e}")
            return {"error": f"命令执行失败: {str(e)}"}

    def get_status_info(self) -> Dict[str, Any]:
        """获取状态信息（扩展基类方法）

        Returns:
            Dict[str, Any]: 状态信息
        """
        base_info = super().get_status_info()

        # 添加主引擎特定信息
        base_info.update({
            "system_name": self._system_config.system_name if self._system_config else "unknown",
            "system_version": self._system_config.version if self._system_config else "unknown",
            "system_mode": self._system_config.mode if self._system_config else "unknown",
            "module_count": len(self._module_engines),
            "startup_time": self._startup_timestamp.isoformat() if self._startup_timestamp else None,
            "web_socket_enabled": self._system_config.enable_web_socket if self._system_config else False,
            "monitoring_enabled": self._system_config.enable_monitoring if self._system_config else False
        })

        return base_info


async def get_main_engine() -> Optional['MainEngine']:
    """获取全局主引擎实例

    Returns:
        MainEngine: 主引擎实例
    """
    from ..utils.engine_factory import get_engine_factory
    factory = await get_engine_factory()
    if factory:
        engine = await factory.get_engine("main_engine")
        if isinstance(engine, MainEngine):
            return engine
    return None


async def initialize_system(config: Dict[str, Any] = None) -> MainEngine:
    """初始化系统

    Args:
        config: 系统配置

    Returns:
        MainEngine: 主引擎实例
    """
    # 创建引擎配置实体
    engine_config = EngineConfigEntity(
        name="main_engine",
        engine_type=EngineType.MAIN,
        auto_start=True,
        config=config or {}
    )

    # 获取主引擎实例
    main_engine = MainEngine(engine_config)

    # 启动主引擎
    await main_engine.start()

    return main_engine


async def shutdown_system() -> None:
    """关闭系统"""
    main_engine = await get_main_engine()
    if main_engine:
        await main_engine.stop()