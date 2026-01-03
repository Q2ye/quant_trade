"""
数据模块引擎包
提供数据模块的业务引擎实现

设计原则：
1. 继承核心引擎基类：所有引擎都继承自core.engines.base.EngineBase
2. 状态管理：引擎负责管理业务流程的状态和生命周期
3. 事件驱动：通过发布和订阅事件与其他组件通信
4. 服务协调：调用服务层执行业务逻辑，不包含具体业务逻辑

引擎职责清单：
1. ✅ 管理业务流程状态（进度、任务、连接等）
2. ✅ 响应事件（on_event方法）
3. ✅ 调用Service执行业务逻辑
4. ✅ 发布事件通知结果
5. ✅ 处理异常和错误恢复
6. ✅ 提供状态查询接口

使用示例：
    from quant_server.modules.data.engines import DataSyncEngine

    # 创建引擎实例
    sync_engine = DataSyncEngine(
        event_engine=event_engine,
        main_engine=main_engine,
        sync_service=sync_service
    )

    # 启动引擎
    sync_engine.start()

    # 执行任务
    await sync_engine.start_sync_task(sync_type="daily")

    # 获取状态
    status = sync_engine.get_status()

    # 停止引擎
    sync_engine.stop()
"""

from .sync_engine import DataSyncEngine
from .clean_engine import DataCleanEngine
from .quality_engine import DataQualityEngine
from .research_engine import DataResearchEngine

# 引擎类型枚举
from enum import Enum


class DataEngineType(str, Enum):
    """数据模块引擎类型枚举"""
    SYNC = "data.sync.engine"
    CLEAN = "data.clean.engine"
    QUALITY = "data.quality.engine"
    RESEARCH = "data.research.engine"


# 引擎工厂函数
def create_data_engine(
    engine_type: DataEngineType,
    event_engine,
    main_engine,
    **kwargs
):
    """
    创建数据模块引擎工厂函数

    Args:
        engine_type: 引擎类型
        event_engine: 事件引擎实例
        main_engine: 主引擎实例
        **kwargs: 引擎特定参数

    Returns:
        引擎实例

    Raises:
        ValueError: 不支持的引擎类型
    """
    engine_map = {
        DataEngineType.SYNC: DataSyncEngine,
        DataEngineType.CLEAN: DataCleanEngine,
        DataEngineType.QUALITY: DataQualityEngine,
        DataEngineType.RESEARCH: DataResearchEngine,
    }

    engine_class = engine_map.get(engine_type)
    if not engine_class:
        raise ValueError(f"不支持的引擎类型: {engine_type}")

    return engine_class(
        event_engine=event_engine,
        main_engine=main_engine,
        **kwargs
    )


# 导出所有引擎类
__all__ = [
    # 引擎类
    "DataSyncEngine",
    "DataCleanEngine",
    "DataQualityEngine",
    "DataResearchEngine",

    # 类型和工具
    "DataEngineType",
    "create_data_engine",
]

# 版本信息
__version__ = "1.0.0"
__description__ = "数据模块业务引擎 - 管理数据相关业务流程"
__author__ = "QuantServer Team"