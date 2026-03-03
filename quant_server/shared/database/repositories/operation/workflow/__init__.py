# quant_server/shared/database/repositories/operation/workflow/__init__.py
"""
工作流管理领域 - Repository 统一导出文件

职责：统一导出工作流管理相关的 Repository 类，方便外部模块使用

设计原则：
1. 统一导出：简化导入路径
2. 类型安全：确保类型注解完整
3. 按需加载：避免循环导入
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .workflow_task_repo import WorkflowTaskRepository
    from .workflow_log_repo import WorkflowLogRepository
    # 注：WorkflowTemplate 表在 business_models.py 中不存在
    # 设计文档中有 workflow_template_repo.py，但对应表模型未定义
    # 暂时注释掉，等表模型定义后再启用
    # from .workflow_template_repo import WorkflowTemplateRepository

# 公共导出列表
__all__ = [
    'WorkflowTaskRepository',
    'WorkflowLogRepository',
    # 'WorkflowTemplateRepository',  # 待表模型定义后启用
]