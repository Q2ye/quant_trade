"""
数据模块引擎包
基于统一引擎框架重构的数据模块引擎实现

设计原则：
1. 继承EngineBase基类，遵循统一的生命周期管理
2. 使用EngineFactory进行创建和管理
3. 通过EventEngine实现事件驱动通信
4. 支持依赖注入和配置驱动
5. 提供完整的监控、健康检查和错误处理

引擎类型：
1. DATA_CLEAN: 数据清洗引擎 - 负责数据清洗和质量提升
2. DATA_QUALITY: 数据质量检查引擎 - 负责质量检查和监控
3. RESEARCH: 因子研究引擎 - 负责因子计算和分析
4. DATA_SYNC: 数据同步引擎 - 负责数据同步和ETL（待实现）

使用示例：
    # 方式1：通过引擎工厂创建
    from quant_server.core.engines.utils.engine_factory import create_engine
    from quant_server.core.engines.types.enums import EngineType

    clean_engine = await create_engine(
        engine_type=EngineType.DATA_CLEAN,
        config={"max_concurrent_tasks": 3}
    )

    # 方式2：使用便捷函数
    from . import create_data_clean_engine

    clean_engine = await create_data_clean_engine(
        config={"max_concurrent_tasks": 3},
        instance_name="data_clean_main"
    )

    # 启动引擎
    await clean_engine.start()

    # 获取引擎状态
    status = await clean_engine.get_engine_status()

    # 停止引擎
    await clean_engine.stop()

版本信息：
- 引擎框架版本: 2.0.0
- 数据模块版本: 1.0.0
- 重构日期: 2024-01-01
"""
from typing import Dict, Any

# ==================== 导入引擎类 ====================

from .clean_engine import DataCleanEngine, CleanStep, CleanTaskStatus, CleanRule, CleanTaskConfig, CleanTaskProgress, CleanTaskResult
from .quality_engine import DataQualityEngine, QualityCheckType, QualityRuleType, QualityRule, QualityTaskConfig, QualityTaskProgress, QualityTaskResult
from .research_engine import FactorResearchEngine, ResearchTaskType

# 数据同步引擎（已实现）
try:
    from .sync_engine import (
        DataSyncEngine,
        SyncTaskStatus,
        SyncTaskConfig,
        SyncTaskProgress,
        SyncTaskResult,
        register_data_sync_engine,
        create_data_sync_engine,
        start_sync_task
    )
    DATA_SYNC_AVAILABLE = True
except ImportError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"导入数据同步引擎失败: {e}")
    
    # 定义占位符
    DataSyncEngine = None
    SyncTaskStatus = None
    SyncTaskConfig = None
    SyncTaskProgress = None
    SyncTaskResult = None
    register_data_sync_engine = None
    create_data_sync_engine = None
    start_sync_task = None
    DATA_SYNC_AVAILABLE = False

# ==================== 导入便捷函数 ====================

from .clean_engine import (
    create_data_clean_engine,
    get_data_clean_engine,
    register_data_clean_engine
)

from .quality_engine import (
    register_quality_engine,
    create_data_quality_engine,
    get_data_quality_engine
)

from .research_engine import (
    create_research_engine,
    get_research_engine,
    register_research_engine
)

# ==================== 重新导出核心引擎类型 ====================

try:
    from quant_server.core.engines.types.enums import (
        EngineType,
        EngineCategory,
        ComponentStatus,
        HealthStatus,
        EngineErrorLevel,
        PriorityLevel,
        ResourceType
    )

    from quant_server.core.engines.types.entities import (
        EngineConfig,
        Event
    )

    from quant_server.core.engines.utils.engine_factory import (
        EngineFactory
    )

except ImportError:
    # 如果核心引擎框架不可用，定义占位符
    class EngineType:
        DATA_CLEAN = "DATA_CLEAN"
        DATA_QUALITY = "DATA_QUALITY"
        DATA_SYNC = "DATA_SYNC"
        RESEARCH = "RESEARCH"
        EVENT = "EVENT"
        DATA = "DATA"

    class EngineCategory:
        DATA_PROCESSING = "DATA_PROCESSING"
        DATA = "DATA"
        RESEARCH = "RESEARCH"

    class ComponentStatus:
        UNINITIALIZED = "UNINITIALIZED"
        INITIALIZING = "INITIALIZING"
        INITIALIZED = "INITIALIZED"
        STARTING = "STARTING"
        RUNNING = "RUNNING"
        STOPPING = "STOPPING"
        STOPPED = "STOPPED"
        ERROR = "ERROR"

    class HealthStatus:
        HEALTHY = "HEALTHY"
        DEGRADED = "DEGRADED"
        UNHEALTHY = "UNHEALTHY"
        FAILED = "FAILED"

    class EngineErrorLevel:
        DEBUG = "DEBUG"
        INFO = "INFO"
        WARNING = "WARNING"
        ERROR = "ERROR"
        CRITICAL = "CRITICAL"

    class PriorityLevel:
        LOW = 1
        NORMAL = 5
        HIGH = 10
        CRITICAL = 20

    class ResourceType:
        CPU = "CPU"
        MEMORY = "MEMORY"
        DISK = "DISK"
        NETWORK = "NETWORK"


    class EngineFactory:
        pass


# ==================== 数据模块特定类型 ====================

class DataModuleError(Exception):
    """数据模块异常基类"""
    pass

class EngineCreationError(DataModuleError):
    """引擎创建异常"""
    pass

class EngineOperationError(DataModuleError):
    """引擎操作异常"""
    pass

class DataQualityError(DataModuleError):
    """数据质量异常"""
    pass

class ResearchError(DataModuleError):
    """研究异常"""
    pass

class DataSyncError(DataModuleError):
    """数据同步异常"""
    pass

# ==================== 模块级功能函数 ====================

async def register_all_data_engines(factory: 'EngineFactory' = None) -> Dict[str, bool]:
    """
    注册所有数据模块引擎到引擎工厂

    Args:
        factory: 引擎工厂实例，如果为None则使用全局工厂

    Returns:
        Dict[str, bool]: 注册结果字典
    """
    try:
        # 如果未提供工厂，尝试获取全局工厂
        if factory is None:
            from quant_server.core.engines.utils.engine_factory import get_engine_factory
            factory = await get_engine_factory()

        if factory is None:
            raise EngineCreationError("无法获取引擎工厂实例")

        # 注册各引擎
        results = {}

        # 注册数据清洗引擎
        try:
            register_data_clean_engine(factory)
            results["DATA_CLEAN"] = True
        except (ImportError, AttributeError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"注册数据清洗引擎失败: {e}")
            results["DATA_CLEAN"] = False

        # 注册数据质量引擎
        try:
            # 注意：quality_engine中的register_quality_engine函数不接受参数
            # 需要根据实际情况调整
            register_quality_engine()
            results["DATA_QUALITY"] = True
        except (ImportError, AttributeError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"注册数据质量引擎失败: {e}")
            results["DATA_QUALITY"] = False

        # 注册研究引擎
        try:
            register_research_engine(factory)
            results["DATA_RESEARCH"] = True
        except (ImportError, AttributeError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"注册研究引擎失败: {e}")
            results["DATA_RESEARCH"] = False

        # 注册数据同步引擎
        try:
            if register_data_sync_engine:
                register_data_sync_engine(factory)
                results["DATA_SYNC"] = True
            else:
                results["DATA_SYNC"] = False
        except (ImportError, AttributeError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"注册数据同步引擎失败: {e}")
            results["DATA_SYNC"] = False

        return results

    except (ImportError, AttributeError, ValueError) as e:
        raise EngineCreationError(f"注册数据模块引擎失败: {e}")

async def create_all_data_engines(
    configs: Dict[str, Any] = None,
    event_engine: Any = None
) -> Dict[str, Any]:
    """
    创建所有数据模块引擎

    Args:
        configs: 各引擎配置字典，格式为：
            {
                "DATA_CLEAN": {...},
                "DATA_QUALITY": {...},
                "RESEARCH": {...},
                "DATA_SYNC": {...}
            }
        event_engine: 事件引擎实例

    Returns:
        dict: 创建的引擎字典
    """
    engines = {}
    configs = configs or {}

    try:
        # 创建数据清洗引擎
        clean_config = configs.get("DATA_CLEAN", {})
        data_clean_engine = await create_data_clean_engine(
            config=clean_config
        )
        engines["DATA_CLEAN"] = data_clean_engine

        # 创建数据质量引擎
        quality_config = configs.get("DATA_QUALITY", {})
        data_quality_engine = await create_data_quality_engine(
            config=quality_config
        )
        engines["DATA_QUALITY"] = data_quality_engine

        # 创建研究引擎
        research_config = configs.get("DATA_RESEARCH", {})
        data_research_engine = await create_research_engine(
            config=research_config
        )
        engines["DATA_RESEARCH"] = data_research_engine

        # 创建数据同步引擎
        sync_config = configs.get("DATA_SYNC", {})
        if create_data_sync_engine:
            data_sync_engine = await create_data_sync_engine(
                config=sync_config,
                event_engine=event_engine
            )
            engines["DATA_SYNC"] = data_sync_engine
        else:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("数据同步引擎创建函数不可用，跳过创建")

        return engines

    except (ImportError, AttributeError, ValueError) as e:
        # 清理已创建的引擎
        for engine in engines.values():
            try:
                await engine.stop()
            except Exception:
                pass
        raise EngineCreationError(f"创建数据模块引擎失败: {e}")

async def create_engine_by_type(
    engine_type: EngineType,
    config: dict = None,
    instance_name: str = None,
    event_engine = None,
    **kwargs
):
    """
    根据引擎类型创建引擎（通用函数）

    Args:
        engine_type: 引擎类型
        config: 引擎配置
        instance_name: 实例名称
        event_engine: 事件引擎实例
        **kwargs: 其他参数

    Returns:
        EngineBase: 创建的引擎实例

    Raises:
        EngineCreationError: 引擎创建失败
    """
    try:
        if engine_type == EngineType.DATA_CLEAN:
            return await create_data_clean_engine(
                config=config,
                instance_name=instance_name,
                **kwargs
            )
        elif engine_type == EngineType.DATA_QUALITY:
            return await create_data_quality_engine(
                config=config,
                instance_name=instance_name,
            )
        elif engine_type == EngineType.DATA_RESEARCH:
            return await create_research_engine(
                config=config,
                instance_name=instance_name,
            )
        elif engine_type == EngineType.DATA_SYNC:
            if create_data_sync_engine:
                return await create_data_sync_engine(
                    config=config,
                    instance_name=instance_name,
                    event_engine=event_engine,
                    **kwargs
                )
            else:
                raise EngineCreationError("数据同步引擎创建函数不可用")
        else:
            raise EngineCreationError(f"不支持的引擎类型: {engine_type}")

    except Exception as e:
        raise EngineCreationError(f"创建引擎失败 ({engine_type}): {e}")

def get_all_engine_types() -> dict:
    """
    获取所有数据模块引擎类型信息

    Returns:
        dict: 引擎类型信息字典
    """
    return {
        "DATA_CLEAN": {
            "type": EngineType.DATA_CLEAN,
            "category": EngineCategory.DATA_PROCESSING,
            "class": DataCleanEngine,
            "description": "数据清洗引擎，负责管理数据清洗和质量提升的完整流程",
            "dependencies": [EngineType.EVENT]
        },
        "DATA_QUALITY": {
            "type": EngineType.DATA_QUALITY,
            "category": EngineCategory.DATA,
            "class": DataQualityEngine,
            "description": "数据质量检查引擎，负责管理和执行数据质量检查任务",
            "dependencies": [EngineType.EVENT]
        },
        "DATA_RESEARCH": {
            "type": EngineType.DATA_RESEARCH,
            "category": EngineCategory.DATA,
            "class": FactorResearchEngine,
            "description": "因子研究引擎，负责因子计算、分析和优化",
            "dependencies": [EngineType.EVENT]
        },
        "DATA_SYNC": {
            "type": EngineType.DATA_SYNC,
            "category": EngineCategory.DATA_PROCESSING,
            "class": DataSyncEngine if DataSyncEngine else None,
            "description": "数据同步引擎，负责数据同步和ETL处理",
            "dependencies": [EngineType.EVENT],
            "available": DataSyncEngine is not None
        }
    }

# ==================== 导出列表 ====================

__all__ = [
    # 引擎类
    "DataCleanEngine",
    "DataQualityEngine",
    "FactorResearchEngine",
    "DataSyncEngine",

    # 数据同步引擎特定类型
    "SyncTaskStatus",
    "SyncTaskConfig",
    "SyncTaskProgress",
    "SyncTaskResult",

    # 数据清洗引擎特定类型
    "CleanStep",
    "CleanTaskStatus",
    "CleanRule",
    "CleanTaskConfig",
    "CleanTaskProgress",
    "CleanTaskResult",

    # 数据质量引擎特定类型
    "QualityCheckType",
    "QualityRuleType",
    "QualityRule",
    "QualityTaskConfig",
    "QualityTaskProgress",
    "QualityTaskResult",

    # 研究引擎特定类型
    "ResearchTaskType",

    # 核心引擎类型（重新导出）
    "EngineType",
    "EngineCategory",
    "ComponentStatus",
    "HealthStatus",
    "EngineErrorLevel",
    "PriorityLevel",
    "ResourceType",
    "EngineFactory",

    # 异常类
    "DataModuleError",
    "EngineCreationError",
    "EngineOperationError",
    "DataQualityError",
    "ResearchError",
    "DataSyncError",

    # 便捷函数
    "create_data_clean_engine",
    "get_data_clean_engine",
    "create_data_quality_engine",
    "get_data_quality_engine",
    "create_research_engine",
    "get_research_engine",
    "create_data_sync_engine",
    "start_sync_task",

    # 注册函数
    "register_data_clean_engine",
    "register_quality_engine",
    "register_research_engine",
    "register_data_sync_engine",

    # 模块级功能
    "register_all_data_engines",
    "create_all_data_engines",
    "create_engine_by_type",
    "get_all_engine_types",
]

# ==================== 版本信息 ====================

__version__ = "2.0.0"
__description__ = "数据模块引擎 - 基于统一引擎框架重构"
__author__ = "QuantServer Team"
__license__ = "MIT"
__copyright__ = "Copyright 2024 QuantServer Team"

# ==================== 模块初始化检查 ====================

def _check_module_dependencies():
    """
    检查模块依赖
    """
    required_modules = [
        "quant_server.core.engines",
        "quant_server.core.engines.types",
        "quant_server.core.engines.base",
        "quant_server.core.engines.utils",
    ]

    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    if missing_modules:
        print(f"警告: 缺少以下核心模块依赖: {missing_modules}")
        print("部分功能可能受限")

# 执行依赖检查
_check_module_dependencies()