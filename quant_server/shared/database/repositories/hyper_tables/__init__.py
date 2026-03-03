"""
超表管理模块 - 时序数据专用工具

提供超表（时序表）的专用管理功能：
1. 超表管理器：超表的创建、配置和管理
2. 时间分桶管理器：按时间维度分桶管理
3. 数据保留策略管理器：自动清理过期数据
4. 分片管理器：数据分片和存储优化

使用示例：
    from shared.database.repositories.hyper_tables import (
        HyperTableManager,
        TimeBucketManager,
        RetentionPolicyManager,
        ChunkManager
    )

    # 初始化管理器
    hyper_manager = HyperTableManager(session)
"""

from .hyper_table_manager import HyperTableManager
from .time_bucket_manager import TimeBucketManager
from .retention_policy_manager import RetentionPolicyManager
from .chunk_manager import ChunkManager

__all__ = [
	'HyperTableManager',
	'TimeBucketManager',
	'RetentionPolicyManager',
	'ChunkManager'
]