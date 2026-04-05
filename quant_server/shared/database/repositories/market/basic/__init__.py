# -*- coding: utf-8 -*-
"""
市场基础数据Repository模块
位置：quant_server/shared/database/repositories/market/basic/__init__.py
职责：统一导出market/basic目录下的所有Repository类
"""

from .stock_repo import StockBasicRepository, RepositoryError as StockBasicError
from .company_repo import CompanyRepository, RepositoryError as CompanyError
from .st_list_repo import STListRepository, RepositoryError as STListError

# ETF相关Repository
from .etf_repo import (
    EtfBasicRepository,
    EtfIndexRepository,
    EtfDailyRepository,
    EtfMinuteRepository,
    FundAdjFactorRepository,
    ETFRepository,
    RepositoryError as ETFError
)

# 指数相关Repository
from .index_repo import (
    IndexBasicRepository,
    IndexDailyRepository,
    IndexRepository,
    RepositoryError as IndexError
)

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

	# ETF相关
	"EtfBasicRepository",
	"EtfIndexRepository",
	"EtfDailyRepository",
	"EtfMinuteRepository",
	"FundAdjFactorRepository",
	"ETFRepository",
	"ETFError",

	# 指数相关
	"IndexBasicRepository",
	"IndexDailyRepository",
	"IndexRepository",
	"IndexError",
]

# 类型别名
StockBasicRepo = StockBasicRepository
CompanyRepo = CompanyRepository
STListRepo = STListRepository
EtfBasicRepo = EtfBasicRepository
EtfIndexRepo = EtfIndexRepository
EtfDailyRepo = EtfDailyRepository
EtfMinuteRepo = EtfMinuteRepository
FundAdjFactorRepo = FundAdjFactorRepository
ETFRepo = ETFRepository
IndexBasicRepo = IndexBasicRepository
IndexDailyRepo = IndexDailyRepository
IndexRepo = IndexRepository

# 基础数据Repository映射表
BASIC_REPOSITORIES = {
	"stock_basic": StockBasicRepository,
	"company": CompanyRepository,
	"st_list": STListRepository,
	"etf_basic": EtfBasicRepository,
	"etf_index": EtfIndexRepository,
	"etf_daily": EtfDailyRepository,
	"etf_minute": EtfMinuteRepository,
	"fund_adj_factor": FundAdjFactorRepository,
	"etf": ETFRepository,
	"index_basic": IndexBasicRepository,
	"index_daily": IndexDailyRepository,
	"index": IndexRepository,
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