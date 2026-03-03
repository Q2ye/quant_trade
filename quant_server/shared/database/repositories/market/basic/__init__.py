# -*- coding: utf-8 -*-
"""
市场基础数据Repository模块
位置：quant_server/shared/database/repositories/market/basic/__init__.py
职责：统一导出market/basic目录下的所有Repository类
"""

from .stock_repo import StockBasicRepository, RepositoryError as StockBasicError
from .company_repo import CompanyRepository, RepositoryError as CompanyError
from .st_list_repo import STListRepository, RepositoryError as STListError

# ETF和Fund相关的Repository需要另外的模型定义
# 暂时注释掉，待模型完善后再启用
from .etf_repo import ETFRepository, RepositoryError as ETFBasicError
from .index_repo import IndexBasicRepository, RepositoryError as ETFIndexError

__all__ = [
	# 股票相关
	"StockBasicRepository",
	"StockBasicError",

	# 公司相关
	"CompanyRepository",
	"CompanyError",

	# ST股票相关
	"STListRepository",
	"STListError",

	# 其他基础数据（待完善）
	"ETFRepository",
	"ETFBasicError",
	"IndexBasicRepository",
	"ETFIndexError",
]

# 类型别名
StockBasicRepo = StockBasicRepository
CompanyRepo = CompanyRepository
STListRepo = STListRepository

# 基础数据Repository映射表
BASIC_REPOSITORIES = {
	"stock_basic": StockBasicRepository,
	"company": CompanyRepository,
	"st_list": STListRepository,
}


# Repository工厂函数
def create_basic_repository (repo_type: str, session):
	"""
	创建基础数据Repository实例

	Args:
		repo_type: Repository类型（'stock_basic', 'company', 'st_list'等）
		session: 数据库会话

	Returns:
		Repository实例

	Raises:
		ValueError: 当repo_type无效时
	"""
	if repo_type not in BASIC_REPOSITORIES:
		raise ValueError(f"不支持的Repository类型: {repo_type}")

	return BASIC_REPOSITORIES[repo_type](session)