# quant_server/shared/database/models/base.py

from sqlalchemy.ext.declarative import declarative_base

# 创建声明性基类
Base = declarative_base()

# 如果需要全局的 mixin 类，可以在这里定义
class BaseMixin:
    """基础混合类，用于所有模型共享的字段和方法"""
    pass