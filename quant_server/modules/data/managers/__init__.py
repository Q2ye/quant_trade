"""
数据模块管理器包

提供数据模块的管理器实现，负责协调多个引擎或服务的复杂业务逻辑

设计原则：
1. 协调者角色：管理多个引擎或服务的协作
2. 业务流程：实现完整的业务工作流
3. 状态管理：管理跨引擎的状态一致性
4. 异常处理：提供统一的错误处理和恢复机制

管理器职责清单：
1. ✅ 协调多个引擎的协作
2. ✅ 实现复杂业务流程
3. ✅ 管理跨组件的状态
4. ✅ 提供统一的事务管理
5. ✅ 实现业务规则的验证
6. ✅ 处理异常和重试逻辑
"""

from .data_manager import DataManager
from .research_manager import ResearchManager
from .status_manager import SyncStatusManager

__all__ = [
    "DataManager",
    "ResearchManager",
    "SyncStatusManager"
]