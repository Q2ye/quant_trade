# quant_server/shared/database/repositories/strategy/management/__init__.py
"""
策略管理领域 - Repository 统一导出文件

职责：统一导出策略管理相关的 Repository 类，方便外部模块使用

设计原则：
1. 统一导出：简化导入路径
2. 类型安全：确保类型注解完整
3. 按需加载：避免循环导入
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .strategy_repo import StrategyRepository
    from .strategy_version_repo import StrategyVersionRepository
    from .strategy_template_repo import StrategyTemplateRepository
    from .strategy_parameter_repo import StrategyParameterRepository
    from .portfolio_strategy_repo import PortfolioStrategyRepository
    # from .strategy_dependency_repo import StrategyDependencyRepository

# 公共导出列表
__all__ = [
    'StrategyRepository',
    'StrategyVersionRepository',
    'StrategyTemplateRepository',
    'StrategyParameterRepository',
    'PortfolioStrategyRepository',
    # 'StrategyDependencyRepository',
]