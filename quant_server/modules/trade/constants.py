# constants.py           # 交易模块常量
# 交易相关常量
from enum import Enum
# v2.4: 执行模式（原在 strategy.constants，独立定义以消除跨模块依赖）
class ExecutionMode(str, Enum):
    """实盘执行模式"""
    SEMI_AUTO = "semi_auto"   # 半自动：策略生成信号 → 人工确认
    FULL_AUTO = "full_auto"   # 全自动：策略生成信号 → 直接执行
