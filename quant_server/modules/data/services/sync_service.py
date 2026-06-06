# -*- coding: utf-8 -*-
"""
数据同步服务 (Data Sync Service)
===============================
基于混合架构设计，实现数据同步的核心业务逻辑。

**文件位置**：``quant_server/modules/data/services/sync_service.py``

**模块定位**：数据模块的服务层，负责所有外部数据源数据的拉取、清洗、转换和入库。
作为"无状态 Service"，不持有事件引擎引用（由调用方注入），专注纯业务逻辑。

----

## 架构设计

### 设计原则
1. **Repository 模式**：所有数据访问通过 ``shared.database.repositories`` 统一入口，
   一表一 Repository，服务层不直接操作 ORM 模型。
2. **事件驱动**：依赖 ``EventEngine`` 发布同步进度（started/progress/completed/failed），
   供前端、监控模块实时获取同步状态。
3. **同步/异步双模**：通过 ``ThreadPoolExecutor`` 将 Tushare/Baostock 的同步 IO 调用
   沉入线程池，避免阻塞 asyncio 事件循环。
4. **智能日期推断**：``_resolve_sync_date_range`` 根据数据库已有最新日期自动判断
   full（全量）、incremental（增量）、overlap（重叠）、up_to_date（已最新）四种模式。
5. **取消支持**：通过 ``asyncio.Event`` 取消令牌，在每个股票处理循环中检查，
   支持前端"取消同步"操作。
6. **类型覆盖**：支持股票、ETF、指数、财务（三表+衍生指标）、公司治理、分红等 30+ 种数据类型。

### 数据流
::

	API 请求 → DataSyncService.sync_market_data()
		│
		├─ 1. _create_sync_task()      → data_sync_tasks 表（任务记录）
		├─ 2. _publish_sync_event()     → EventEngine（started 事件）
		├─ 3. _sync_by_data_type()      → 根据 DataType 路由到具体同步方法
		│       │
		│       ├─ DataSourceFactory → Tushare/Baostock 适配器（拉取原始数据）
		│       ├─ _convert_records_datetime() → pandas Timestamp → Python datetime
		│       ├─ _clean_nan_values() → NaN → None（兼容 asyncpg）
		│       ├─ Repository.create/update → PostgreSQL（数据持久化）
		│       └─ _update_progress() → Redis/内存缓存（进度实时推送）
		│
		├─ 4. _update_sync_task()       → 更新任务状态（completed/failed/cancelled）
		├─ 5. _publish_sync_event()     → EventEngine（completed 事件）
		└─ 6. _clean_cache_after_sync() → 清理相关缓存

### 依赖方向（严格单向）
::

	modules/data/services/sync_service.py
		→ shared/database/repositories/   （数据访问）
		→ shared/sources/                 （外部数据源适配器）
		→ shared/cache/                   （Redis/内存缓存）
		→ core/engines/system/            （事件引擎，可选注入）
		→ modules/data/events/            （事件定义）
		→ modules/data/constants/         （常量枚举）

### 错误处理策略
- **单股失败不阻断全局**：每只股票独立 try/except，记录失败计数后继续下一只。
- **逐股提交**：每 N 只股票（可配置）执行 ``session.commit()``，减少事务锁竞争。
- **取消安全**：取消时记录 cancelled 状态，已处理数据不回滚。
- **NaN 安全**：pandas DataFrame 的空字符串字段转为 NaN，写入 PostgreSQL 前必须转为 None。

### 性能优化
- **逐股同步**：日行情/资金流向/复权因子等按 ts_code 逐个拉取，避免 Tushare 接口限流。
- **线程池隔离**：同步 IO 操作通过 ``ThreadPoolExecutor`` 执行，默认 8 个 worker。
- **缓存节流**：``_update_progress`` 最多每秒写一次缓存（100% 完成时立即写入）。
- **并行批量同步**：``batch_sync_data`` 使用 ``asyncio.Semaphore(3)`` 限制并行度。
"""

import asyncio
import json
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Tuple

import pandas as pd  # 新增导入，用于处理DataFrame中的Timestamp
from sqlalchemy.ext.asyncio import AsyncSession

# 导入核心基础设施
from core.engines.system.event_engine import EventEngine
# 导入数据模块常量
from modules.data.constants import (
	DataSource,
	DataType,
	CacheKey,
)
# 导入数据模块事件
from modules.data.events import (
	DataSyncStartedEvent,
	DataSyncProgressEvent,
	DataSyncCompletedEvent,
	DataSyncFailedEvent,
)
# 导入数据模块业务模型和schemas
from modules.data.schemas import (
	BatchSyncRequest,
	SyncResult,
	SyncTaskItem,
)
from modules.data.utils.timing import SyncTimingLogger
from shared.cache.memory_cache import MemoryCache
from shared.cache.redis_cache import RedisCache
from shared.database.models.data_models import (
	FinancialStatement,
	StockDividend,
	StockFinaIndicator,
	StockAuditOpinion,
	StockBusinessIncome,
)
# 从统一导出入口导入共享Repository（按领域分组）
from shared.database.repositories import (
	# 市场数据领域
	StockBasicRepository,
	StockDailyRepository,
	StockMinuteRepository,
	StockMoneyflowRepository,
	StockAdjFactorRepository,
	StockDailyBasicRepository,
	TradeCalendarRepository,
	EtfDailyRepository,
	EtfMinuteRepository,
	FundAdjFactorRepository,
	# 财务数据领域
	FinancialStatementRepository,
	# 运营领域（任务记录）
	DataSyncTaskRepository, ETFRepository,
)
from shared.database.repositories.market.basic import (
	EtfBasicRepository, IndexWeightRepository,
	CompanyRepository, STListRepository,
	IndexBasicRepository, IndexDailyRepository, EtfIndexRepository,
)
from shared.database.repositories.market.fundamental.audit_opinion_repo import StockAuditOpinionRepository
from shared.database.repositories.market.fundamental.business_income_repo import StockBusinessIncomeRepository
from shared.database.repositories.market.fundamental.dividend_repo import StockDividendRepository
from shared.database.repositories.market.fundamental.etf_share_repo import EtfShareRepository
from shared.database.repositories.market.fundamental.express_repo import StockExpressRepository
from shared.database.repositories.market.fundamental.fina_indicator_repo import StockFinaIndicatorRepository
from shared.database.repositories.market.fundamental.forecast_repo import StockForecastRepository
from shared.database.repositories.market.fundamental.suspend_info_repo import StockSuspendInfoRepository
from shared.database.repositories.market.governance.manager_repo import ManagerRepository
from shared.database.repositories.market.governance.reward_repo import RewardRepository
from shared.database.repositories.market.quote.stock_monthly_repo import StockMonthlyRepository
from shared.database.repositories.market.quote.stock_weekly_repo import StockWeeklyRepository
from shared.sources.source_factory import DataSourceFactory

# 配置日志
logger = logging.getLogger(__name__)


def _convert_pandas_datetime(record: Dict[str, Any]) -> Dict[str, Any]:
	"""
	将记录中的pandas datetime类型转换为Python datetime对象

	Args:
		record: 原始记录字典

	Returns:
		转换后的记录字典
	"""
	converted = {}
	for key, value in record.items():
		if isinstance(value, pd.Timestamp):
			# 转换为Python datetime对象
			converted[key] = value.to_pydatetime()
		elif isinstance(value, (list, tuple)):
			# 递归处理列表中的元素
			converted[key] = [
				item.to_pydatetime() if isinstance(item, pd.Timestamp) else item
				for item in value
			]
		else:
			converted[key] = value
	return converted


def _convert_to_date(value: Any) -> date:
	"""
	将各种类型的日期值转换为Python date对象

	Args:
		value: 日期值（可能是datetime、date或字符串）

	Returns:
		Python date对象
	"""
	if isinstance(value, date) and not isinstance(value, datetime):
		return value
	elif isinstance(value, datetime):
		return value.date()
	elif isinstance(value, str):
		# 尝试解析字符串格式（如 "20260318"）
		try:
			return datetime.strptime(value, '%Y%m%d').date()
		except ValueError:
			# 如果失败，尝试ISO格式
			return datetime.fromisoformat(value).date()
	else:
		raise ValueError(f"无法将类型 {type(value)} 转换为date对象: {value}")


def _convert_to_datetime(value: Any) -> datetime:
	"""
	将各种类型的日期值转换为Python datetime对象

	Args:
		value: 日期值（可能是datetime、date或字符串）

	Returns:
		Python datetime对象
	"""
	if isinstance(value, datetime):
		return value
	elif isinstance(value, date):
		return datetime.combine(value, datetime.min.time())
	elif isinstance(value, str):
		# 尝试解析字符串格式（如 "20260318"）
		try:
			return datetime.strptime(value, '%Y%m%d')
		except ValueError:
			# 如果失败，尝试ISO格式
			return datetime.fromisoformat(value)
	else:
		raise ValueError(f"无法将类型 {type(value)} 转换为datetime对象: {value}")


def _clean_nan_values(record: Dict[str, Any]) -> Dict[str, Any]:
	"""
	将记录中的 NaN/NaT 值转换为 None，避免 PostgreSQL asyncpg 驱动报错
	（pandas DataFrame.to_dict('records') 会将空字符串字段转为 NaN）

	Args:
		record: 原始记录字典

	Returns:
		清洗后的记录字典
	"""
	for key, value in record.items():
		if isinstance(value, float) and math.isnan(value):
			record[key] = None
		elif value is not None and hasattr(pd, 'isna') and pd.isna(value):
			record[key] = None
	return record


def _convert_records_datetime(records: List[Dict[Any, Any]]) -> List[Dict[str, Any]]:
	"""
	批量转换记录中的pandas datetime类型，并确保字典键为字符串类型

	Args:
		records: 原始记录列表

	Returns:
		转换后的记录列表
	"""
	converted_records = []
	for record in records:
		# 先转换日期时间
		converted_record = _convert_pandas_datetime(record)
		# 清理 NaN 值（pandas 空字段会变成 NaN，asyncpg 不接受）
		converted_record = _clean_nan_values(converted_record)
		# 确保字典键为字符串类型
		string_key_record = {}
		for k, v in converted_record.items():
			string_key_record[k] = v
		converted_records.append(string_key_record)
	return converted_records


def _estimate_total_items(data_type: str, ts_codes: Optional[List[str]] = None) -> int:
	"""
	估算同步项目总数，用于创建任务记录时填充 total_records 字段。

	估算逻辑基于 A 股市场实际规模：
	- 股票基础信息（STOCK_LIST / COMPANY / ST_LIST）：~5000 只
	- 日线行情：~5000 只 × 250 个交易日 = ~1,250,000 条
	- 周线/月线：按比例缩小（52 周 / 12 月）
	- Tick 数据量极大，限制估算范围
	- ETF 规模约为股票的 1/5（~1000 只）
	- 财务数据：~5000 只 × 20 年 = ~100,000 条
	- 公司治理（管理层/薪酬）：~5000 × 15 人
	- 指数：约 500 个指数 × 250 交易日

	Args:
		data_type: 数据类型标识符（DataType 枚举值）
		ts_codes: 股票代码列表，用于精确估算（None 时使用默认值）

	Returns:
		int: 估算的同步项目总数（用于进度百分比计算）
	"""
	estimates = {
		DataType.STOCK_LIST: 5000,
		DataType.ST_LIST: 2000,
		DataType.COMPANY: 5000,
		DataType.DAILY_QUOTES: (len(ts_codes) if ts_codes else 5000) * 250,
		DataType.WEEKLY_QUOTES: (len(ts_codes) if ts_codes else 5000) * 52,
		DataType.MONTHLY_QUOTES: (len(ts_codes) if ts_codes else 5000) * 12,
		DataType.MINUTE_QUOTES: (len(ts_codes) if ts_codes else 5000) * 240 * 20,
		DataType.TICK_QUOTES: (len(ts_codes) if ts_codes else 10) * 240 * 1,  # Tick数据量大，限制估算
		DataType.MONEYFLOW: (len(ts_codes) if ts_codes else 5000) * 250,
		DataType.ADJ_FACTOR: (len(ts_codes) if ts_codes else 5000) * 500,
		DataType.SUSPEND: (len(ts_codes) if ts_codes else 5000) * 10,  # 停牌信息相对较少
		DataType.DAILY_BASIC: (len(ts_codes) if ts_codes else 5000) * 250,
		DataType.ETF_BASIC: 1000,
		DataType.ETF_INDEX: 1000,
		DataType.ETF_DAILY: (len(ts_codes) if ts_codes else 1000) * 250,
		DataType.ETF_MINUTE: (len(ts_codes) if ts_codes else 1000) * 240 * 7,
		DataType.ETF_SHARE: (len(ts_codes) if ts_codes else 1000) * 250,  # ETF份额数据
		DataType.FUND_ADJ_FACTOR: (len(ts_codes) if ts_codes else 1000) * 500,
		DataType.MANAGERS: (len(ts_codes) if ts_codes else 5000) * 15,
		DataType.REWARDS: (len(ts_codes) if ts_codes else 5000) * 15,
		DataType.INDEX_BASIC: 500,
		DataType.INDEX_DAILY: 500 * 250,
		DataType.CALENDAR: 365 * 2,
		DataType.FINANCIAL_INCOME: (len(ts_codes) if ts_codes else 5000) * 20,
		DataType.FINANCIAL_BALANCE: (len(ts_codes) if ts_codes else 5000) * 20,
		DataType.FINANCIAL_CASHFLOW: (len(ts_codes) if ts_codes else 5000) * 20,
		DataType.FORECAST: (len(ts_codes) if ts_codes else 5000) * 5,  # 业绩预告
		DataType.EXPRESS: (len(ts_codes) if ts_codes else 5000) * 5,  # 业绩快报
		DataType.DIVIDEND: (len(ts_codes) if ts_codes else 5000) * 10,  # 分红送股
		DataType.FINANCIAL_INDICATOR: (len(ts_codes) if ts_codes else 5000) * 20,  # 财务指标
		DataType.AUDIT_OPINION: (len(ts_codes) if ts_codes else 5000) * 10,  # 审计意见
		DataType.BUSINESS_INCOME: (len(ts_codes) if ts_codes else 5000) * 15,  # 主营业务构成
	}
	return estimates.get(data_type, 100)


def _fmt_err(e: Exception, max_len: int = 200) -> str:
	"""截断过长异常信息（SQL 语句可能数千字节）"""
	s = str(e)
	return s if len(s) <= max_len else s[:max_len] + f"...({len(s)}字节截断)"

def _preprocess_records(records, date_fields=(), known_cols=None, fill_numeric=()):
	"""一趟完成：pandas类型转换 + NaN清洗 + 日期转换 + null→0填充 + 列过滤。

	Args:
		records: 记录列表（原地修改）
		date_fields: 需转换为date的字段
		known_cols: 允许保留的列集合（None=全部保留）
		fill_numeric: 需将None→0的数值字段
	"""
	_has_pd_isna = hasattr(pd, "isna")  # 提升到循环外
	for record in records:
		# 1. pandas类型 → Python原生类型
		for key, value in list(record.items()):
			if isinstance(value, pd.Timestamp):
				record[key] = value.to_pydatetime()
			elif isinstance(value, float) and math.isnan(value):
				record[key] = None
			elif value is not None and _has_pd_isna and pd.isna(value):
				record[key] = None
		# 2. 日期转换
		for field in date_fields:
			if record.get(field):
				record[field] = _convert_to_date(record[field])
		# 3. null→0填充（防止NOT NULL约束）
		for field in fill_numeric:
			if record.get(field) is None:
				record[field] = 0
		# 4. 列过滤
		if known_cols:
			extra = [k for k in record if k not in known_cols]
			for k in extra:
				del record[k]
	return records


# Tushare旧数据(2011年之前)资金流向部分列可能为null，需要填充0
_ADJ_FACTOR_NULLABLE_FIELDS = ("adj_factor",)
_MONEYFLOW_NULLABLE_FIELDS = (
    'buy_sm_vol', 'buy_sm_amount', 'sell_sm_vol', 'sell_sm_amount',
    'buy_md_vol', 'buy_md_amount', 'sell_md_vol', 'sell_md_amount',
    'buy_lg_vol', 'buy_lg_amount', 'sell_lg_vol', 'sell_lg_amount',
    'buy_elg_vol', 'buy_elg_amount', 'sell_elg_vol', 'sell_elg_amount',
    'net_mf_vol', 'net_mf_amount',
)

class DataSyncService:
	"""
	数据同步服务（无状态 Service）。

	**职责边界**：
	- 负责数据同步的完整生命周期：拉取 → 清洗 → 转换 → 入库 → 缓存清理
	- 通过注入的 ``EventEngine`` 发布同步进度和结果
	- 通过注入的 ``cancel_token`` 支持前端取消同步
	- **不负责**：数据源协议细节（由 DataSourceFactory 代理）、
	  数据库连接管理（由 session 管理）、模块间通信（由 EventEngine 代理）

	**典型调用方式**::

		async with session_manager.get_session() as session:
			svc = DataSyncService(session, event_engine)
			result = await svc.sync_market_data(
				data_type=DataType.DAILY_QUOTES,
				start_date=date(2026, 1, 1),
				end_date=date(2026, 6, 1),
				ts_codes=["000001.SZ", "600000.SH"],
			)

	**生命周期管理**：
	- 每次 API 调用创建新实例（通过依赖注入获得 session）
	- 批量同步 ``batch_sync_data`` 为每种数据类型创建独立 session（隔离事务）
	- 实例内部的 ``ThreadPoolExecutor`` 在垃圾回收时自动关闭

	**待实现（stub）方法**：cancel_sync / retry_failed_sync / _update_sync_task /
	cleanup_old_tasks / get_recent_sync_tasks
	"""

	def __init__(
			self,
			session: AsyncSession,
			event_engine: Optional[EventEngine] = None,
			cancel_token=None,  # asyncio.Event
			task_id: Optional[str] = None,
			executor=None,  # 可选：共享线程池（batch_sync_data 场景复用）
	):
		"""
		初始化数据同步服务。

		每次调用创建新实例，完成以下初始化：
		1. 注入数据库会话和事件引擎引用
		2. 为每张数据表创建对应的 Repository 实例（一表一 Repository）
		3. 创建线程池用于同步 IO 隔离
		4. 初始化数据源工厂
		5. 建立 DataType → sync_method 映射表

		Args:
			session: SQLAlchemy 异步数据库会话（必需）。所有数据访问通过此会话。
			event_engine: 事件引擎实例（可选）。为 None 时不发布事件，
				用于纯数据同步场景（如命令行脚本）。
			cancel_token: ``asyncio.Event`` 取消令牌（可选）。设置后各同步方法在
				循环中检查并中止当前任务。用于前端"取消同步"功能。
			task_id: 任务 ID（可选）。用于双重取消检查——token 失效时回退到 DB 查询。

		Note:
			- Repository 数量 = 数据表数量（~30+），按业务域分组初始化便于维护。
			- ThreadPoolExecutor 的 worker 数量默认 8，可通过配置文件
			  ``settings.ENGINES.max_workers`` 调整。
			- ``_sync_method_map`` 是 DataType → method 的映射，新增同步类型时
			  只需在此映射中添加条目并实现对应方法。
		"""
		self.session = session
		self.event_engine = event_engine
		self.cancel_token = cancel_token  # asyncio.Event or None
		self._task_id = task_id  # 用于 DB 回退检查

		# ========== 初始化 Repository 实例（一表一 Repository） ==========
		# 原则：每个 Repository 对应一张数据库表，服务层通过 Repository 访问数据，
		# 不直接操作 ORM 模型。Repository 实例在 __init__ 时创建，随服务实例生命周期。

		# --- 股票行情相关 ---
		self.stock_basic_repo = StockBasicRepository(session)  # stock_basic（基础信息）
		self.stock_daily_repo = StockDailyRepository(session)  # stock_daily（日线，超表）
		self.stock_minute_repo = StockMinuteRepository(session)  # stock_minute（分钟，超表）
		self.stock_moneyflow_repo = StockMoneyflowRepository(session)  # stock_moneyflow（资金流向）
		self.stock_adj_factor_repo = StockAdjFactorRepository(session)  # stock_adj_factor（复权因子）
		self.stock_daily_basic_repo = StockDailyBasicRepository(session)  # stock_daily_basic（每日指标）
		self.trade_calendar_repo = TradeCalendarRepository(session)  # trade_calendar（交易日历）

		# --- ETF 相关 ---
		self.etf_basic_repo = EtfBasicRepository(session)  # etf_basic（ETF 基础信息）
		self.etf_daily_repo = EtfDailyRepository(session)  # etf_daily（ETF 日线）
		self.etf_minute_repo = EtfMinuteRepository(session)  # etf_minute（ETF 分钟）
		self.fund_adj_factor_repo = FundAdjFactorRepository(session)  # fund_adj_factor（基金复权因子）

		# --- 财务数据 ---
		self.financial_statement_repo = FinancialStatementRepository(session)  # financial_statements

		# --- 任务记录 ---
		self.sync_task_repo = DataSyncTaskRepository(session)  # data_sync_tasks

		# --- 公司治理 ---
		self.company_repo = CompanyRepository(session)  # stock_company（公司基本信息）
		self.manager_repo = ManagerRepository(session)  # stk_managers（管理层）
		self.reward_repo = RewardRepository(session)  # stk_rewards（薪酬持股）

		# --- 行情衍生（周/月线） ---
		self.stock_weekly_repo = StockWeeklyRepository(session)  # stock_weekly
		self.stock_monthly_repo = StockMonthlyRepository(session)  # stock_monthly

		# --- 指数 ---
		self.index_basic_repo = IndexBasicRepository(session)  # index_basic
		self.index_daily_repo = IndexDailyRepository(session)  # index_daily

		# --- ST 列表 ---
		self.st_list_repo = STListRepository(session)  # st_list（ST 变更历史）

		# --- 财务衍生数据 ---
		self.suspend_info_repo = StockSuspendInfoRepository(session)  # suspend_info（停复牌）
		self.etf_share_repo = EtfShareRepository(session)  # etf_share（ETF 份额规模）
		self.forecast_repo = StockForecastRepository(session)  # forecast（业绩预告）
		self.express_repo = StockExpressRepository(session)  # express（业绩快报）
		self.dividend_repo = StockDividendRepository(session)  # dividend（分红送股）
		self.fina_indicator_repo = StockFinaIndicatorRepository(session)  # fina_indicator（财务指标）
		self.audit_opinion_repo = StockAuditOpinionRepository(session)  # audit_opinion（审计意见）
		self.business_income_repo = StockBusinessIncomeRepository(session)  # business_income（主营业务构成）
		self.etf_index_repo = EtfIndexRepository(session)  # etf_index（ETF 跟踪指数）

		# ========== 线程池（避免 Tushare 同步调用阻塞事件循环） ==========
		# Tushare/Baostock 的 HTTP 请求是同步阻塞的，必须在独立线程中执行。
		# worker 数量从配置文件 settings.ENGINES.max_workers 读取，默认 8。
		from shared.config.config_manager import get_config
		cfg = get_config()
		if executor:
			self._executor = executor
			self._own_executor = False  # 共享线程池，不由本实例关闭
		else:
			self._max_workers = getattr(getattr(cfg, 'settings', None), 'ENGINES', None)
			self._max_workers = getattr(self._max_workers, 'max_workers', None) if self._max_workers else None
			self._max_workers = self._max_workers or 16  # I/O密集型，默认16
			self._executor = ThreadPoolExecutor(
				max_workers=self._max_workers,
				thread_name_prefix="sync_"  # 便于调试时识别线程来源
			)
			self._own_executor = True

		# ========== 缓存和数据源工厂 ==========
		self.source_factory = DataSourceFactory()  # 统一数据源适配器工厂
		self._cache = None  # 懒加载（首次访问 cache property 时初始化）

		# ========== DataType → 同步方法 映射表 ==========
		# 通过字典映射避免冗长的 if-elif 链，新增数据类型只需在此添加条目即可。
		self._sync_method_map = {
			# 股票基础
			DataType.STOCK_LIST: self._sync_stock_list,
			DataType.ST_LIST: self._sync_st_list,
			DataType.COMPANY: self._sync_stock_company,
			DataType.DAILY_QUOTES: self._sync_daily_quotes,
			DataType.WEEKLY_QUOTES: self._sync_weekly_quotes,
			DataType.MONTHLY_QUOTES: self._sync_monthly_quotes,
			DataType.MINUTE_QUOTES: self._sync_minute_quotes,
			DataType.TICK_QUOTES: self._sync_tick_quotes,  # TODO (tick数据量大，延后)
			DataType.MONEYFLOW: self._sync_moneyflow,
			DataType.ADJ_FACTOR: self._sync_adj_factor,
			DataType.SUSPEND: self._sync_suspend_info,
			DataType.DAILY_BASIC: self._sync_daily_basic,
			# ETF数据
			DataType.ETF_BASIC: self._sync_etf_basic,
			DataType.ETF_INDEX: self._sync_etf_index,
			DataType.ETF_MINUTE: self._sync_etf_minute,
			DataType.ETF_DAILY: self._sync_etf_daily,
			DataType.FUND_ADJ_FACTOR: self._sync_fund_adj_factor,
			DataType.ETF_SHARE: self._sync_etf_share,
			# 指数数据
			DataType.INDEX_BASIC: self._sync_index_basic,
			DataType.INDEX_DAILY: self._sync_index_daily,
			# 公司治理
			DataType.MANAGERS: self._sync_stk_managers,
			DataType.REWARDS: self._sync_stk_rewards,
			# 财务数据
			DataType.FINANCIAL_DATA: self._sync_financial_data,  # 三 表合并同步
			DataType.FINANCIAL_INCOME: self._sync_financial_income,
			DataType.FINANCIAL_BALANCE: self._sync_financial_balance,
			DataType.FINANCIAL_CASHFLOW: self._sync_financial_cashflow,
			DataType.FORECAST: self._sync_forecast,
			DataType.EXPRESS: self._sync_express,
			DataType.DIVIDEND: self._sync_dividend,
			DataType.FINANCIAL_INDICATOR: self._sync_financial_indicator,
			DataType.AUDIT_OPINION: self._sync_audit_opinion,
			DataType.BUSINESS_INCOME: self._sync_business_income,
			# 通用
			DataType.CALENDAR: self._sync_trade_calendar,
			# 宏观经济
			DataType.CPI: self._sync_cpi,
			DataType.PPI: self._sync_ppi,
			DataType.GDP: self._sync_gdp,
			# 指数扩展
			DataType.INDEX_WEIGHT: self._sync_index_weight,
			DataType.INDEX_WEEKLY: self._sync_index_weekly,
		}

	@property
	def cache(self):
		"""
		获取缓存实例（懒加载）。

		根据配置自动选择：
		- ``settings.REDIS.ENABLED = True`` → ``RedisCache``（生产环境，支持持久化、模式删除）
		- ``settings.REDIS.ENABLED = False`` → ``MemoryCache``（开发环境，无需 Redis 依赖）

		用途：
		- ``_create_sync_task``：缓存同步任务初始状态（TTL 24h）
		- ``_update_progress``：缓存同步进度（TTL 1h）
		- ``_clean_cache_after_sync``：同步完成后清理对应缓存

		Returns:
			``RedisCache`` 或 ``MemoryCache`` 实例
		"""
		if self._cache is None:
			from shared.config.config_manager import get_config
			settings = get_config().settings
			if settings.REDIS.ENABLED:
				self._cache = RedisCache(
					host=settings.REDIS.HOST,
					port=settings.REDIS.PORT,
					db=settings.REDIS.DB,
					password=settings.REDIS.PASSWORD
				)
			else:
				self._cache = MemoryCache(namespace="data_sync")
		return self._cache

	# ==================== 公共API ====================

	async def sync_market_data(
			self,
			data_type: DataType,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_codes: Optional[List[str]] = None,
			user_id: Optional[str] = None,
			task_id: Optional[str] = None,
			update_task_status: bool = True,
			**kwargs
	) -> Dict[str, Any]:
		"""
		同步市场数据（单类型），是数据同步的主入口。

		完整生命周期（6 步）：
		1. 创建任务记录（``_create_sync_task``）
		2. 发布 started 事件（``_publish_sync_event``）
		3. 路由到具体同步方法（``_sync_by_data_type``），拉取→清洗→入库
		4. 更新任务状态为 completed（``_update_sync_task``）
		5. 发布 completed 事件
		6. 清理相关缓存（``_clean_cache_after_sync``）

		异常处理：
		- 取消令牌已设置 → status=cancelled, error_message="用户手动取消"
		- 其他异常 → status=failed, 记录完整 traceback
		- 返回的 dict 中 ``success`` 字段区分成败

		Args:
			data_type: 数据类型枚举（如 ``DataType.DAILY_QUOTES``）。
				参见 ``modules/data/constants.py`` 中 ``DataType`` 枚举定义。
			start_date: 同步起始日期（含）。为 None 时由各同步方法智能推断。
			end_date: 同步结束日期（含）。为 None 时默认为当天。
			ts_codes: 股票代码列表（如 ``["000001.SZ", "600000.SH"]``）。
				为 None 时从 ``stock_basic`` 表获取全部活跃股票。
			user_id: 用户标识，用于事件发布和权限校验。
			task_id: 任务 ID。为 None 时自动生成（格式: ``sync_{data_type}_{timestamp}``）。
				非 None 时表示由外部（如批量同步）统一管理任务 ID。
			**kwargs: 透传给具体同步方法的额外参数（如 ``freq="1min"``）。

		Returns:
			Dict::
				{
					"success": bool,       # 是否成功
					"task_id": str,        # 任务 ID（用于状态查询）
					"result": {            # 详细结果（仅 success=True 时有意义）
						"records_added": int,
						"records_updated": int,
						"records_failed": int,
						"total_items": int,
						"message": str,
					},
					"error": str,          # 错误信息（仅 success=False 时有意义）
					"message": str,        # 人类可读的状态描述
				}
		"""
		logger.debug(f"开始同步市场数据，类型: {data_type}, 用户ID: {user_id}")

		try:
			# 步骤 1：创建同步任务记录（如已从外部传入 task_id 则跳过，避免重复创建）
			if task_id is None:
				task_id = await self._create_sync_task(
					data_type=data_type,
					start_date=start_date,
					end_date=end_date,
					ts_codes=ts_codes,
					user_id=user_id,
					params=kwargs
				)

			# 步骤 2：发布 started 事件，前端可据此显示加载状态
			await self._publish_sync_event(
				event_type="started",
				task_id=task_id,
				data_type=data_type,
				user_id=user_id
			)

			# 步骤 3：路由到具体同步方法（通过 _sync_method_map）
			sync_result = await self._sync_by_data_type(
				data_type=data_type,
				start_date=start_date,
				end_date=end_date,
				ts_codes=ts_codes,
				task_id=task_id,
				user_id=user_id,
				**kwargs
			)

			# 步骤 4：根据实际结果判断任务状态
			# 优先检查取消 → 全部失败 → 部分成功/成功
			added = sync_result.get("records_added", 0)
			updated = sync_result.get("records_updated", 0)
			failed = sync_result.get("records_failed", 0)
			total = added + updated + failed
			if sync_result.get("cancelled"):
				final_status = "cancelled"
				err_msg = "用户手动取消"
				
			elif total > 0 and added + updated == 0:
				# 所有记录都失败了（如字段名不匹配、接口报错等）
				final_status = "failed"
				err_msg = f"全部 {failed} 条记录同步失败，无成功记录"
				sync_result["message"] = err_msg
			else:
				final_status = "completed"
				err_msg = None

			if update_task_status:
				await self._update_sync_task(
					task_id=task_id,
					status=final_status,
					result=sync_result,
					error_message=err_msg
				)
				
				await self.session.commit()
				
	
				# 步骤 5：发布同步完成/失败/取消事件
				event_type = "cancelled" if final_status == "cancelled" else ("completed" if final_status == "completed" else "failed")
				await self._publish_sync_event(
					event_type=event_type,
					task_id=task_id,
					data_type=data_type,
					result=sync_result,
					error=err_msg,
					user_id=user_id
			)

			# 步骤 6：清理相关缓存（仅成功时清理）
			if final_status == "completed":
				await self._clean_cache_after_sync(data_type, ts_codes)

			_status_label = "已取消" if final_status == "cancelled" else ("完成" if final_status == "completed" else "失败")
			logger.info(f"[{data_type.value}] 同步{_status_label}，"
			            f"新增={added}, 更新={updated}, 失败={failed}")

			return {
				"success": final_status == "completed",
				"task_id": task_id,
				"result": sync_result,
				"message": "数据同步完成" if final_status == "completed" else err_msg
			}

		except Exception as e:
			logger.error(f"[{data_type.value if hasattr(data_type, chr(39)+chr(118)+chr(97)+chr(108)+chr(117)+chr(101)+chr(39)) else data_type}] 市场数据同步失败: {str(e)}", exc_info=True)

			if task_id:
				# 区分取消（cancel_token 已设置）和真实失败
				final_status = "cancelled" if (await self._is_cancelled()) else "failed"
				err_msg = "用户手动取消" if final_status == "cancelled" else str(e)
				await self._update_sync_task(
					task_id=task_id,
					status=final_status,
					result=None,
					error_message=err_msg
				)
				await self.session.commit()
				await self._publish_sync_event(
					event_type="cancelled" if final_status == "cancelled" else "failed",
					task_id=task_id,
					data_type=data_type,
					error=str(e),
					user_id=user_id
				)

			return {
				"success": False,
				"task_id": task_id,
				"error": str(e),
				"message": "数据同步失败"
			}

	async def batch_sync_data(
			self,
			tasks: List[SyncTaskItem],
			priority: Optional[Any] = None,
			user_id: Optional[str] = None,
			task_id: Optional[str] = None,
	) -> Dict[str, Any]:
		"""
		批量同步数据（**串行**执行，一个任务完成后再执行下一个）。

		与 ``batch_sync_data``（并行版）的区别：
		- 此方法按顺序执行，共享同一个 session，适合少量、有依赖关系的同步。
		- ``batch_sync_data`` 为每种类型创建独立 session 并行执行，适合大量、独立的数据类型。

		执行流程：
		1. 生成 batch_task_id
		2. 发布 batch_started 事件
		3. 按顺序遍历 tasks，每个任务调用 ``sync_market_data``
		4. 每个任务独立记录 SyncResult（失败不影响后续任务）
		5. 发布 batch_completed 或 batch_failed 事件

		Args:
			request: ``BatchSyncRequest`` 实例，包含 ``tasks: List[SyncTaskItem]``，
				每个 ``SyncTaskItem`` 指定 data_type、start_date、end_date 等。
			user_id: 用户标识（可选）

		Returns:
			Dict::
				{
					"success": bool,
					"task_id": str,
					"results": List[dict],      # 每个 SyncTaskItem 的执行结果
					"total_tasks": int,
					"completed_tasks": int,
					"message": str,
				}
		"""
		logger.info(f"开始批量同步，数据类型: {[task.data_type for task in tasks]}, 用户ID: {user_id}")

		batch_task_id = f"batch_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
			
			# 并发参数从配置文件读取，默认值兜底
		# settings.ENGINES.sync_type_concurrency -> 跨类型并发数（默认 5）
		# settings.ENGINES.max_workers           -> 共享线程池大小（默认 16）
		from shared.config.config_manager import get_config as _get_cfg
		_cfg = _get_cfg()
		_ec = getattr(getattr(_cfg, "settings", None), "ENGINES", None)
		_type_cc = getattr(_ec, "sync_type_concurrency", None) if _ec else None
		_type_cc = _type_cc or 3
		_pool_size = getattr(_ec, "max_workers", None) if _ec else None
		_pool_size = _pool_size or 16
		sem = asyncio.Semaphore(_type_cc)
		import concurrent.futures as _cf
		shared_executor = _cf.ThreadPoolExecutor(max_workers=_pool_size, thread_name_prefix="batch_sync_")

		async def _sync_one(task, idx):
			logger.info(f"[批量同步 #{idx + 1}] {task.data_type} 排队等待...")
			async with sem:
				from shared.database.session import get_session_manager
				logger.info(f"[批量同步 #{idx + 1}] {task.data_type} 开始执行")
				sm = get_session_manager()
				async with sm.get_session() as session:
					svc = DataSyncService(session, self.event_engine, self.cancel_token, task_id=self._task_id,
					                      executor=shared_executor)
					try:
						dt = DataType(task.data_type.value) if hasattr(task.data_type, 'value') else DataType(
							task.data_type)
						result = await svc.sync_market_data(
							data_type=dt, start_date=task.start_date, end_date=task.end_date,
							user_id=user_id, task_id=task_id or batch_task_id,
							force_update=getattr(task, 'force_update', False),
							update_task_status=False,
						)
						ra = result.get("result", {}).get("records_added", 0)
						ru = result.get("result", {}).get("records_updated", 0)
						rf = result.get("result", {}).get("records_failed", 0)
						sr = SyncResult(data_type=task.data_type, success=result.get("success", False),
						                records_added=ra, records_updated=ru, records_failed=rf,
						                start_time=datetime.now(), end_time=datetime.now(),
						                error_message=result.get("error"))
						logger.info(f"[批量同步 #{idx + 1}] {task.data_type}: 新增={ra} 更新={ru} 失败={rf}")
						return sr.model_dump()
					except Exception:
						logger.error(f"[批量同步 #{idx + 1}] {task.data_type} 失败: {e}", exc_info=True)
						return SyncResult(data_type=task.data_type, success=False,
						                  start_time=datetime.now(), end_time=datetime.now(),
						                  error_message=str(e)).model_dump()

		try:
			coros = [_sync_one(task, i) for i, task in enumerate(tasks)]
			results = await asyncio.gather(*coros)
			shared_executor.shutdown(wait=False)  # 不等待未完成任务，它们已经 gather 完成

			total_records = sum(
				r.get("records_added", 0) + r.get("records_updated", 0) + r.get("records_failed", 0) for r in results)
			succeeded_records = sum(r.get("records_added", 0) + r.get("records_updated", 0) for r in results)
			failed_records = sum(r.get("records_failed", 0) for r in results)
				# 检查取消
			cancelled = self.cancel_token and self.cancel_token.is_set()
			all_success = all(r.get("success", True) for r in results) and not cancelled

			# 批量完成后统一更新任务状态
			effective_task_id = task_id or batch_task_id
			if effective_task_id:
				final_status = "cancelled" if cancelled else ("completed" if all_success else "failed")
				await self._update_sync_task(effective_task_id, final_status,
				                             error_message="用户手动取消" if cancelled else None)
				await self.session.commit()

			logger.info(f"[批量同步] 完成: {len(results)} 种类型, 处理={total_records}, 成功={succeeded_records}")
			return {
				"success": all_success, "task_id": batch_task_id, "results": results,
				"records_processed": total_records, "records_succeeded": succeeded_records,
				"records_failed": failed_records, "total_tasks": len(tasks),
				"completed_tasks": len(results),
				"cancelled": cancelled,
				"message": "批量同步已取消" if cancelled else ("批量同步完成" if all_success else f"批量同步部分完成（{sum(1 for r in results if not r.get('success', True))}/{len(results)} 失败）")
			}
		except Exception as e:
			logger.error(f"[批量同步] 并行执行失败: {e}", exc_info=True)
			return {"success": False, "task_id": batch_task_id, "results": [],
			        "records_processed": 0, "records_succeeded": 0, "records_failed": 0,
			        "total_tasks": len(tasks), "error": str(e), "message": "批量同步异常"}

	async def get_sync_status(
			self,
			task_id: str,
			user_id: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		获取同步任务的执行状态。

		数据来源优先级：
		1. 缓存（Redis/MemoryCache）→ 实时进度数据
		2. 数据库（data_sync_tasks 表）→ 持久化任务记录（fallback：按 processed/total 计算百分比）

		包含权限校验：指定 user_id 时，仅返回该用户的任务（否则抛出 ValueError）。

		Args:
			task_id: 任务 ID
			user_id: 用户标识（可选，用于权限校验）

		Returns:
			Dict::
				{
					"task_id": str,
					"status": str,             # "pending" / "running" / "completed" / "failed" / "cancelled"
					"progress": {              # 实时进度（来自缓存）
						"progress": float,
						"current_task": str,
						"estimated_time_remaining": float | None,
					},
					"start_time": str,         # ISO 8601 格式
					"end_time": str | None,
					"data_type": str,
					"total_items": int,
					"completed_items": int,
					"error_message": str | None,
					"results": None,
				}

		Raises:
			ValueError: 任务不存在或无权查看
		"""
		try:
			task_result = await self.sync_task_repo.get_by_task_id(task_id)
			if not task_result or not task_result.data:
				raise ValueError(f"任务 {task_id} 不存在")
			task = task_result.data
			if user_id and task.user_id != user_id:
				raise ValueError("无权查看此任务")

			progress_key = CacheKey.SYNC_PROGRESS.format(task_id=task_id)
			cached_progress_raw = await self.cache.get(progress_key)
			if cached_progress_raw:
				try:
					progress_data = json.loads(cached_progress_raw)
				except (json.JSONDecodeError, TypeError):
					progress_data = {}
			else:
				progress_data = {
					"progress": (
							task.processed_records / task.total_records * 100) if task and task.total_records > 0 else 0,
					"current_task": None,
					"estimated_time_remaining": None
				}

			return {
				"task_id": task.task_id if task else None,
				"status": task.status if task else None,
				"progress": progress_data,
				"start_time": task.start_time.isoformat() if task and task.start_time else None,
				"end_time": task.completed_at.isoformat() if task and task.completed_at else None,
				"data_type": task.task_type if task else None,
				"total_items": task.total_records if task else 0,
				"completed_items": task.processed_records if task else 0,
				"error_message": task.error_message if task else None,
				"results": None
			}

		except Exception as e:
			logger.error(f"获取同步状态失败: {str(e)}", exc_info=True)
			raise

	async def cancel_sync(self, task_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
		"""取消同步任务。

		设置 cancel_token（asyncio.Event）通知正在运行的同步循环停止，
		同时更新 DB 中的任务状态为 cancelled。

		Args:
			task_id: 任务 ID
			user_id: 用户标识（可选）

		Returns:
			Dict: {task_id, status, message}
		"""
		try:
			# 1. 设置取消令牌，通知 _is_cancelled() 和 _cancellable_run_in_executor 停止
			if self.cancel_token:
				self.cancel_token.set()
				logger.info(f"[取消同步] cancel_token 已设置, task={task_id}")

			# 2. 更新 DB 中的任务状态
			await self._update_sync_task(task_id, "cancelled", error_message="用户手动取消")

			return {
				"task_id": task_id,
				"status": "cancelled",
				"message": "取消信号已发送，正在终止同步任务",
			}
		except Exception as e:
			logger.error(f"[取消同步] 取消失败 task={task_id}: {e}", exc_info=True)
			return {
				"task_id": task_id,
				"status": "error",
				"message": f"取消失败: {str(e)}",
			}

	async def retry_failed_sync(self, task_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
		"""重试失败的同步任务（与原实现相同）"""
		pass

	# ==================== 私有辅助方法 ====================
	# 以下方法为服务内部使用，不对外暴露。

	async def _run_in_executor(self, fn, *args, **kwargs):
		"""
		将同步阻塞调用（Tushare HTTP 请求）沉入线程池执行，避免阻塞 asyncio 事件循环。

		这是本服务最核心的异步适配方法。Tushare/Baostock 的所有数据获取方法都是
		同步阻塞的 HTTP 请求（基于 requests 库）。如果直接在 async 协程中调用，
		会阻塞整个事件循环，导致其他协程无法执行。

		解决方案：通过 ``loop.run_in_executor`` 将同步调用交由 ThreadPoolExecutor
		在独立线程中执行，当前协程 await 其结果。

		Args:
			fn: 同步函数（如 ``source.get_daily``）
			*args: 位置参数（如 ``symbol="000001.SZ"``）
			**kwargs: 关键字参数（如 ``start_date="20260101"``）

		Returns:
			fn 的返回值（通常为 pandas DataFrame）
		"""
		import functools
		loop = asyncio.get_event_loop()
		return await loop.run_in_executor(
			self._executor,
			functools.partial(fn, *args, **kwargs)  # partial 避免 lambda 闭包陷阱
		)

	async def _cancellable_run_in_executor(self, fn, *args, poll_interval: float = 1.0, **kwargs):
		"""
		可取消的线程池执行器——在阻塞任务执行期间定期检查取消令牌。

		与 ``_run_in_executor`` 的区别：本方法通过 ``asyncio.wait_for`` 配合
		短超时轮询，每隔 ``poll_interval`` 秒检查一次取消状态，在用户请求取消时
		能快速响应（最坏延迟 = ``poll_interval``）。

		**实现原理**：:
			1. 将同步函数 fn 提交到 ThreadPoolExecutor（与 _run_in_executor 相同）
			2. 通过 ``asyncio.shield(future)`` 防止 timeout 取消内部 future
			3. 每隔 poll_interval 秒检查一次 ``_is_cancelled()``
			4. 取消时抛出 ``asyncio.CancelledError``（外层循环捕获并 break）

		**限制**：无法真正 kill OS 线程（Python GIL 限制），但 asyncio 层立即抛异常，
		外层 loop 正常 break。已在 OS 线程中运行的 HTTP 请求会自然完成但结果被丢弃。

		Args:
			fn: 同步函数（如 ``source.get_daily``）
			*args: 位置参数
			poll_interval: 取消检查间隔（秒，默认 3.0）
			**kwargs: 关键字参数

		Returns:
			fn 的返回值

		Raises:
			asyncio.CancelledError: 任务被用户取消
		"""
		import functools

		loop = asyncio.get_event_loop()
		future = loop.run_in_executor(
			self._executor,
			functools.partial(fn, *args, **kwargs),
		)

		while not future.done():
			try:
				# shield 防止 wait_for 超时取消内部的 future
				return await asyncio.wait_for(asyncio.shield(future), timeout=poll_interval)
			except asyncio.TimeoutError:
				if await self._is_cancelled():
					# 尽力取消 asyncio 层包装（OS 线程会继续运行直到 finish，但结果被丢弃）
					future.cancel()
					return pd.DataFrame()  # 返回空DataFrame让caller自然跳过
			except asyncio.CancelledError:
				# 传递取消信号
				future.cancel()
				return pd.DataFrame()

		# future 已经完成，直接取结果（不阻塞）
		return future.result()

	async def _is_cancelled(self) -> bool:
		"""
		双重取消检查：先查 token（asyncio.Event），失败则回退到 DB 查询。

		**性能优化**：DB 回退结果缓存到 ``_cancelled_cached``，在 token
		未变化时避免重复查 DB。token 变化时（用户点击取消）刷新缓存。

		Returns:
			bool: 任务是否已被取消
		"""
		# 第一层：token 检查（最快，O(1) 内存读取）
		if self.cancel_token and self.cancel_token.is_set():
			self._cancelled_cached = True  # token 已设置，刷新缓存
			return True
		# 如果已有缓存结论（未取消），直接返回
		if getattr(self, '_cancelled_cached', False):
			return True
		# 第二层：DB 回退检查（绕过 SQLAlchemy 缓存，直接查 DB）
		if self._task_id and not hasattr(self, '_cancelled_checked'):
			self._cancelled_checked = True
			try:
				from sqlalchemy import text
				result = await self.session.execute(
					text("SELECT status FROM data_sync_tasks WHERE task_id = :tid"),
					{"tid": self._task_id}
				)
				row = result.fetchone()
				if row and row[0] == 'cancelled':
					self._cancelled_cached = True
					return True
			except Exception:
				pass  # DB 查询失败时不阻断同步
		return False

	async def _resolve_sync_date_range(
			self, ts_code: str, start_date: Optional[date], end_date: Optional[date], repo,
			latest_dates_map: Optional[Dict[str, Optional[date]]] = None,
			stock_list_date_map: Optional[Dict[str, Optional[date]]] = None,
	) -> Tuple[Optional[date], Optional[date], str]:
		"""
		智能确定同步日期范围，返回 (start_date, end_date, mode)。

		四种模式判断逻辑：
		1. **full**（全量同步）：数据库中无该股票任何记录 → 从上市日期开始全量拉取
		2. **incremental**（增量同步）：数据库有记录、未指定 start_date → 从最后交易日+1天开始
		3. **up_to_date**（无需同步）：最后交易日 ≥ end_date → 跳过，返回 0 条记录
		4. **overlap**（重叠同步）：用户指定了 start_date → 按用户指定的范围拉取（可能覆盖已有数据）

		Args:
			ts_code: 股票代码（如 "000001.SZ"）
			start_date: 用户指定的起始日期（None 表示自动推断）
			end_date: 用户指定的结束日期（None 默认为今天）
			repo: Repository 实例，需有 ``get_latest_trade_date(ts_code)`` 方法

		Returns:
			Tuple: ``(start_date, end_date, mode)``，mode 为 "full"|"incremental"|"up_to_date"|"overlap"

		Note:
			- 全量同步起始日期优先使用股票的 ``list_date``（上市日期），
			  如果无法获取则回退到 1990-12-19（A 股最早交易日）。
			- **up_to_date 模式下 start_date > end_date**（start_date = 最后交易日+1，
			  end_date = 用户指定），调用方应检查 mode 并跳过。
		"""
		if not end_date:
			end_date = datetime.now().date()
		# 查询数据库中该股票的最新交易日期
		if latest_dates_map is not None:
			latest_date = latest_dates_map.get(ts_code)
		else:
			latest_date = await repo.get_latest_trade_date(ts_code)
		if latest_date is None:
			# 数据库中无记录 → 全量同步
			if not start_date:
				stock = await self.stock_basic_repo.get_by_ts_code(ts_code)
				start_date = stock.list_date if stock and stock.list_date else date(1990, 12, 19)
			mode = "full"
		elif start_date is None:
			# 用户未指定起始日期 → 增量同步（从最后日期+1天开始）
			start_date = latest_date + timedelta(days=1)
			if start_date > end_date:
				return start_date, end_date, "up_to_date"
			mode = "incremental"
		else:
			# 用户指定了起始日期 → 重叠同步
			mode = "overlap"
		return start_date, end_date, mode

	async def _get_date_range_and_stocks(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]]
	) -> Tuple[date, date, List[str]]:
		"""
		获取日期范围和股票代码列表，提供合理的默认值。

		Args:
			start_date: 起始日期（None → 30 天前）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）

		Returns:
			Tuple: ``(start_date, end_date, ts_codes)``，所有字段保证非 None。
		"""
		if not end_date:
			end_date = datetime.now().date()
		if not start_date:
			start_date = end_date - timedelta(days=30)
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [stock.ts_code for stock in stocks]
		return start_date, end_date, ts_codes

	async def _get_date_range_and_etfs(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]]
	) -> Tuple[date, date, List[str]]:
		"""
		获取日期范围和 ETF 代码列表。

		与 ``_get_date_range_and_stocks`` 的 ETF 版本，从 etf 表获取活跃 ETF。

		Args:
			start_date: 起始日期（None → 30 天前）
			end_date: 结束日期（None → 今天）
			ts_codes: ETF 代码列表（None → 全部 ETF）

		Returns:
			Tuple: ``(start_date, end_date, ts_codes)``
		"""
		if not end_date:
			end_date = datetime.now().date()
		if not start_date:
			start_date = end_date - timedelta(days=30)
		if not ts_codes:
			etf_repo = ETFRepository(self.session)
			etfs = await etf_repo.get_all_etfs()
			ts_codes = [etf.ts_code for etf in etfs]
		return start_date, end_date, ts_codes

	# ==================== 并行处理通用框架 ====================

	async def _parallel_for_each(
			self, ts_codes, label, task_id, user_id,
			process_one, max_concurrency=8, mode_stats=True,
			rate_key: str = "",
	) -> Dict[str, Any]:
		"""
		通用逐股并行处理框架。

		将 N 只股票分配到 M 个并发 worker（Semaphore 控制），每个 worker 持有
		独立 DB session，处理完成后每只股票独立 commit，异常隔离不影响其他 worker。

		调用方只需提供一个 ``process_one(session, ts_code)`` 协程，返回处理结果
		dict（含 added/updated/skipped/failed/mode 等字段）。

		Args:
			ts_codes: 股票代码列表
			label: 日志标签（如 "日行情"、"资金流向"）
			task_id: 任务 ID
			user_id: 用户 ID
			process_one: async (session, ts_code) -> dict, 单股处理逻辑
			max_concurrency: 最大并发数（默认 8）
			mode_stats: 是否统计 mode_summary（full/incremental/overlap/up_to_date）

		Returns:
			{records_added, records_updated, records_skipped, records_failed,
			 total_items, mode_summary, message}
		"""
		# 读取per-type限流配置（Tushare VIP接口有限频，未配置则不限）

		_rate_limit = 0
		if rate_key:
			import yaml, os
			try:
				_cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config.yaml")
				with open(_cfg_path, "r", encoding="utf-8") as _f:
					_cfg_yaml = yaml.safe_load(_f)
				_limits = _cfg_yaml.get("ENGINES", {}).get("sync_rate_limits", {})
				_rate_limit = _limits.get(rate_key, 0)
			except Exception:
				pass  # 配置文件不存在或格式错误时降级为不限流

			
		limiter = asyncio.Semaphore(_rate_limit) if _rate_limit > 0 else None
		
		sem = asyncio.Semaphore(max_concurrency)
		lock = asyncio.Lock()
		done = 0; total = len(ts_codes)
		records_added = 0; records_updated = 0; records_skipped = 0; records_failed = 0
		mode_summary = {"full": 0, "incremental": 0, "overlap": 0, "up_to_date": 0}

		async def _worker(ts_code):
			"""单个 worker：获取独立 session，调用 process_one，commit 后累加统计。"""
			nonlocal records_added, records_updated, records_skipped, records_failed
			nonlocal mode_summary, done
			if await self._is_cancelled():
				return

			if limiter:
				async with limiter:
					async with sem:
						if await self._is_cancelled():
							return
						from shared.database.session import get_session_manager
						sm = get_session_manager()
						async with sm.get_session() as s:
							result = await process_one(s, ts_code)
							await s.commit()
			else:
				async with sem:
					if await self._is_cancelled():
						return
					from shared.database.session import get_session_manager
					sm = get_session_manager()
					async with sm.get_session() as s:
						result = await process_one(s, ts_code)
						await s.commit()
			async with lock:
				records_added += result.get("added", 0)
				records_updated += result.get("updated", 0)
				records_skipped += result.get("skipped", 0)
				if result.get("failed"): records_failed += 1
				if mode_stats and "mode" in result:
					m = result["mode"]
					mode_summary[m] = mode_summary.get(m, 0) + 1
				done += 1; cur = done
			if cur % 500 == 0 and not await self._is_cancelled():
				pct = cur / total * 100
				await self._update_progress(task_id, progress=min(100, int(pct)),
				                            current_item=f"{label}: {cur}/{total}", user_id=user_id)
				logger.info(f"[{label}] {cur}/{total} ({pct:.0f}%) "
				            f"新增={records_added} 更新={records_updated} "
				            f"跳过={records_skipped} 失败={records_failed}")

		coros = [_worker(c) for c in ts_codes]
		await asyncio.gather(*coros)

		cancelled = await self._is_cancelled()
		_cancel_word = "已取消" if cancelled else "完成"
		if cancelled:
			logger.info(f"[{label}] 取消成功: 已处理={done}/{total} "
			            f"新增={records_added} 失败={records_failed}")
		else:
			await self._update_progress(task_id, progress=100,
			                            current_item=f"{label}: {total}/{total}", user_id=user_id)
			logger.info(f"[{label}] 完成: 新增={records_added} 跳过={records_skipped} "
			            f"失败={records_failed} 模式={mode_summary}")
		return {
			"records_added": records_added, "records_updated": records_updated,
			"records_skipped": records_skipped, "records_failed": records_failed,
			"total_items": records_added + records_updated + records_skipped + records_failed,
			"mode_summary": mode_summary if mode_stats else {},
			"cancelled": cancelled,
			"message": f"{label}数据同步{_cancel_word}（已处理{done}/{total}）"
		}

	async def _process_trade_date_data(
			self,
			repo,
			data: List[Dict],
			ts_code: str,
	) -> Tuple[int, int]:
		"""批量 upsert trade_date 数据。注意：PG ON CONFLICT DO UPDATE 将 INSERT+UPDATE 都计入 rowcount，因此返回值不分 added/updated，第二项固定为 0。"""
		_preprocess_records(data, date_fields=['trade_date'])  # 批量转换，替代逐条遍历
		count = await repo.bulk_upsert(data)
		return count, 0

	async def _create_sync_task(
			self,
			data_type: str,
			start_date: Optional[date] = None,
			end_date: Optional[date] = None,
			ts_codes: Optional[List[str]] = None,
			user_id: Optional[str] = None,
			params: Optional[Dict] = None
	) -> str:
		"""
		创建同步任务记录（写入 data_sync_tasks 表 + 缓存）。

		生成唯一的 task_id（格式: ``sync_{data_type}_{YYYYMMDD_HHMMSS}``），
		估算 total_records 并写入数据库和缓存（TTL 24 小时）。

		Args:
			data_type: 数据类型标识符
			start_date: 起始日期（仅用于记录）
			end_date: 结束日期（仅用于记录）
			ts_codes: 股票代码列表（用于估算 total_records）
			user_id: 用户标识
			params: 额外参数

		Returns:
			str: 生成的 task_id，供后续状态查询和事件发布使用。

		Note:
			``data_sync_tasks.id`` 是自增主键（数据库生成），``task_id`` 是业务唯一标识。
		"""
		task_id = f"sync_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
		task_data = {
			"task_id": task_id,
			"task_type": data_type,
			"status": "pending",
			"user_id": user_id,
			"parameters": params or {},
			"total_records": _estimate_total_items(data_type, ts_codes),
			"created_at": datetime.now()
		}
		# 写入持久化存储（PostgreSQL）
		await self.sync_task_repo.create(task_data)
		# 同时写入缓存，供前端实时查询（24 小时 TTL）
		await self.cache.set(
			CacheKey.SYNC_STATUS.format(task_id=task_id),
			json.dumps(task_data, default=str),
			ttl=86400
		)
		return task_id

	async def _update_sync_task(
			self,
			task_id: str,
			status: str,
			result: Optional[Dict] = None,
			error_message: Optional[str] = None
	):
		"""
		更新同步任务状态到 data_sync_tasks 表。

		Args:
			task_id: 任务 ID
			status: 新状态（"completed" / "failed" / "cancelled"）
			result: 同步结果详情（可选）
			error_message: 错误信息（失败/取消时填充）

		Note:
			将任务状态写入 data_sync_tasks 表。
		"""
		if not task_id:
			
			return
		try:
			task = await self.sync_task_repo.get_by_task_id(task_id)
			if not task or not task.data:
				
				return
			current = task.data.status
			
			# 已是终态的不覆盖（防止 completed 覆盖 handler 的 cancelled）
			if current in ("completed", "cancelled") and status not in ("cancelled",):
				
				return
			update_data = {"status": status, "updated_at": datetime.now()}
			if error_message:
				update_data["error_message"] = error_message
			
			await self.sync_task_repo.update(task.data.id, update_data)
			
		except Exception as e:
			logger.warning(f"[_update_sync_task] 失败 task={task_id}: {e}")

	async def _sync_by_data_type(
			self,
			data_type: str,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**kwargs
	) -> Dict[str, Any]:
		"""
		根据 DataType 路由到对应的同步方法（策略模式）。

		通过 ``_sync_method_map``（DataType → method）实现类型路由，
		避免冗长的 if-elif 链。新增同步类型只需在 map 中添加条目。

		Args:
			data_type: 数据类型字符串（如 "daily_quotes"）
			start_date: 起始日期
			end_date: 结束日期
			ts_codes: 股票代码列表
			task_id: 任务 ID
			user_id: 用户标识
			**kwargs: 透传给具体同步方法

		Returns:
			Dict: 同步方法的返回值

		Raises:
			ValueError: 当 data_type 不合法或未注册时
		"""
		# 1. 字符串 → DataType 枚举
		try:
			data_type_enum = DataType(data_type)
		except ValueError:
			raise ValueError(f"不支持的数据类型: {data_type}")

		# 2. 查找注册的同步方法
		method = self._sync_method_map.get(data_type_enum)
		if not method:
			raise ValueError(f"未注册的同步方法: {data_type}")

		# 3. 调用具体方法
		return await method(
			start_date=start_date,
			end_date=end_date,
			ts_codes=ts_codes,
			task_id=task_id,
			user_id=user_id,
			**kwargs
		)

	# =====================================================================
	# 具体同步方法
	# =====================================================================
	# 每个方法对应一种 DataType，通过 _sync_method_map 路由调用。
	# 通用模式：
	#   1. 获取数据源（source_factory.get_source）
	#   2. 确定日期范围和股票列表（_get_date_range_and_stocks / _resolve_sync_date_range）
	#   3. 逐股拉取数据（_run_in_executor → source.get_xxx）
	#   4. 数据转换（_convert_records_datetime / _clean_nan_values / _convert_to_date）
	#   5. 逐条 upsert（_process_trade_date_data 或直接 repo.create/update）
	#   6. 定时提交（每 N 只 commit 一次，减少事务锁竞争）
	#   7. 进度更新（_update_progress → 缓存）
	#   8. 取消检查（cancel_token.is_set）在每个循环中
	# =====================================================================

	# --- 股票基础信息 ---

	async def _sync_stock_list(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""
		同步股票基础信息列表（stock_basic 表）。

		调用 Tushare ``stock_basic`` 接口，全量拉取所有 A 股（沪深两市）基础信息：
		ts_code、name、area、industry、list_date 等。首次同步或手动触发。

		处理流程：
		1. 全量拉取 → 遍历每条记录
		2. 清洗 NaN → 转换 list_date/delist_date
		3. 逐条 upsert（按 ts_code 查重）
		4. 一次性 commit

		Args:
			start_date: 未使用（股票列表无日期过滤）
			end_date: 未使用
			ts_codes: 未使用（固定全量拉取）
			task_id: 任务 ID（进度追踪）
			user_id: 用户标识

		Returns:
			Dict: ``{records_added, records_updated, records_failed, total_items, message}``
		"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		logger.info("开始同步股票列表...")
		stock_list = await source.get_stock_basic()
		total = len(stock_list)
		# 批量预处理 + bulk upsert（替代逐行 SELECT+INSERT/UPDATE）
		if hasattr(self.stock_basic_repo, 'bulk_upsert'):
			_preprocess_records(stock_list, date_fields=['list_date', 'delist_date'])
			records_added = await self.stock_basic_repo.bulk_upsert(stock_list)
			records_updated = 0  # PG ON CONFLICT DO UPDATE 将 upsert 全部计入 rowcount
		else:
			records_added = 0
			records_updated = 0
			for stock_data in stock_list:
				stock_data = _clean_nan_values(stock_data)
				if 'list_date' in stock_data and stock_data['list_date']:
					stock_data['list_date'] = _convert_to_date(stock_data['list_date'])
				if 'delist_date' in stock_data and stock_data['delist_date']:
					stock_data['delist_date'] = _convert_to_date(stock_data['delist_date'])
				existing = await self.stock_basic_repo.get_by_ts_code(stock_data["ts_code"])
				if existing:
					await self.stock_basic_repo.update_by({"ts_code": existing.ts_code}, stock_data)
					records_updated += 1
				else:
					await self.stock_basic_repo.create(stock_data)
					records_added += 1
			# 实时更新进度到缓存
			await self._update_progress(task_id, progress=min(100, int((idx + 1) / total * 100)),
			                            current_item=f"股票: {stock_data['ts_code']}", user_id=user_id)
		# 全部完成后一次性提交事务
		await self.session.commit()
		return {
			"records_added": records_added,
			"records_updated": records_updated,
			"records_failed": 0,
			"total_items": len(stock_list),
			"message": "股票列表同步完成"
		}

	# --- 日/周/月/分钟行情 ---

	async def _sync_daily_quotes(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""
		同步日线行情数据（stock_daily 表，TimescaleDB 超表）— 并行版本。

		采用 **多股并行 + 独立 session** 架构，N 只股票同时拉取 HTTP 数据并写入 DB，
		将 Tushare HTTP 等待时间从串行叠加变为并行重叠，大幅缩短总耗时。

		==== 架构设计 ====

		                      ┌─[session 1]── http fetch → upsert → commit
		Semaphore(N=8) ────────├─[session 2]── http fetch → upsert → commit
		                      ├─[session 3]── http fetch → upsert → commit
		                      └─[session N]── http fetch → upsert → commit
		                             ↑                ↑            ↑
		                        独立 session     每股独立 commit  互不干扰

		==== 关键设计决策 ====

		1. **独立 session 隔离**
		   每个 worker 通过 ``get_session_manager().get_session()`` 获取独立数据库会话，
		   避免并发写入时的会话冲突和事务互相干扰。

		2. **每只股票独立 commit**
		   并行模式下无法使用"每 10 股批量 commit"，因为各 worker 的 session 独立。
		   改为每只股票处理后立即 commit，单股 ~250 行数据，commit 开销 ~5ms，可接受。

		3. **Semaphore 控制并发**
		   默认 ``max_concurrency=8``，防止 Tushare 免费版限流（每分钟 200 次），
		   同时避免 DB 连接池耗尽。可通过 ``settings.ENGINES.sync_concurrency`` 配置。

		4. **共享只读预加载数据**
		   ``stock_list_date_map`` 和 ``latest_dates_map`` 在主线程预加载后共享给所有 worker，
		   避免 N 次重复 DB 查询。

		5. **asyncio.Lock 保护共享统计**
		   ``records_added/updated/skipped/failed`` 和 ``mode_summary`` 多 worker 并发累加，
		   通过 ``asyncio.Lock`` 保证原子性。

		6. **取消令牌共享**
		   主线程的 ``cancel_token`` 传递给每个 worker，任何 worker 检测到取消后立即退出。

		==== 性能 ====

		- 串行 5000 股 ≈ 25 分钟（HTTP 占 87% = 22min）
		- 并行 8 并发 ≈ 3-5 分钟（HTTP 重叠，DB 并行写入）
		- 加速比 ≈ 5-8x

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
			       records_failed, total_items, mode_summary, message}
		"""
		# ===== 步骤 1：获取股票列表 =====
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		else:
			stocks = await self.stock_basic_repo.get_active_stocks()

		# ===== 步骤 2：批量预加载所有股票的最新日期 =====
		# 一次 SQL 查询获取 {ts_code → latest_trade_date}，避免每个 worker 逐股查询
		stock_list_date_map = {s.ts_code: s.list_date for s in stocks}
		latest_dates_map = await self.stock_daily_repo.get_latest_trade_dates_batch(ts_codes)

		# ===== 步骤 3：配置并发参数 =====
		# 默认 8 并发，可通过配置文件 settings.ENGINES.sync_concurrency 调整
		from shared.config.config_manager import get_config
		cfg = get_config()
		engine_cfg = getattr(getattr(cfg, 'settings', None), 'ENGINES', None)
		max_concurrency = getattr(engine_cfg, 'sync_concurrency', None) if engine_cfg else None
		max_concurrency = max_concurrency or 8

		sem = asyncio.Semaphore(max_concurrency)  # 控制并发数
		stats_lock = asyncio.Lock()                # 保护统计变量
		done_count = 0                             # 已完成数量（用于进度日志）

		# 共享统计（多 worker 通过 lock 保护写入）
		records_added = 0
		records_updated = 0
		records_skipped = 0
		records_failed = 0
		mode_summary = {"full": 0, "incremental": 0, "overlap": 0, "up_to_date": 0}

		total = len(ts_codes)

		async with SyncTimingLogger(logger, "daily_quotes", slow_threshold=30.0) as timer:
			logger.info(
				f"[日行情] 并行同步 {total} 只, 并发={max_concurrency}, "
				f"预估 ~{total * 0.3 / 60 / max_concurrency:.1f}min"
			)

			# ===== 步骤 4：定义单股处理协程 =====
			async def _process_one(ts_code: str) -> None:
				"""
				处理单只股票的完整流程：日期推断 → HTTP 拉取 → 转换 → upsert → commit。

				**异常隔离**：任何异常只影响当前股票，通过 except 捕获后累加 failed 计数，
				不影响其他 worker 的处理。

				**取消支持**：处理前检查 cancel_token，已取消时立即返回。
				"""
				nonlocal records_added, records_updated, records_skipped, records_failed
				nonlocal mode_summary, done_count

				# --- 取消检查 ---
				if await self._is_cancelled():
					return

				# --- 获取独立数据库会话 ---
				from shared.database.session import get_session_manager
				sm = get_session_manager()
				async with sm.get_session() as worker_session:
					# 为当前 worker 创建独立的 Repository 实例
					repo = StockDailyRepository(worker_session)
					# 为当前 worker 创建独立的 Tushare 连接
					source = self.source_factory.get_source(DataSource.TUSHARE)

					try:
						# --- 步骤 4a：智能日期推断（O(1) 查预加载 dict） ---
						# 使用主线程预加载的 latest_dates_map 和 stock_list_date_map，
						# 不逐股查 DB，N 只股票从 N 次查询降为 1 次
						s_date, e_date, mode = await self._resolve_sync_date_range(
							ts_code, start_date, end_date, repo,
							latest_dates_map=latest_dates_map,
							stock_list_date_map=stock_list_date_map,
						)

						# 累加 mode 统计（需要 lock 保护，因为多 worker 并发写入）
						async with stats_lock:
							mode_summary[mode] = mode_summary.get(mode, 0) + 1

						if mode == "up_to_date":
							async with stats_lock:
								records_skipped += 1
							return

						# --- 步骤 4b：HTTP 拉取日线数据 ---
						if mode == 'full':
							s_str = '';
							e_str = ''
						else:
							s_str = s_date.strftime('%Y%m%d') if s_date else ''
							e_str = e_date.strftime('%Y%m%d') if e_date else ''

						daily_df = await self._cancellable_run_in_executor(
							source.get_daily, symbol=ts_code,
							start_date=s_str, end_date=e_str,
						)

						if daily_df is None or daily_df.empty:
							return  # 无数据，正常跳过

						# --- 步骤 4c：数据转换 + DB 写入 ---
						daily_data = _convert_records_datetime(
							daily_df.to_dict("records")
						)
						added, updated = await self._process_trade_date_data(
							repo, daily_data, ts_code
						)

						# --- 步骤 4d：独立 commit + 累加统计 ---
						await worker_session.commit()

						async with stats_lock:
							records_added += added
							records_updated += updated

					except Exception as e:
						# 单股失败隔离：记录错误 + 累加失败计数，不影响其他 worker
						logger.error(f"[日行情] {ts_code} 同步失败: {e}")
						async with stats_lock:
							records_failed += 1
						try:
							await worker_session.rollback()
						except Exception:
							pass
					finally:
						# --- 进度更新（节流） ---
						async with stats_lock:
							done_count += 1
							current_done = done_count
						# 每 10 只输出一次进度，避免锁竞争过频
						if current_done % 500 == 0:
							await self._update_progress(
								task_id,
								progress=min(100, int(current_done / total * 100)),
								current_item=f"日行情: {current_done}/{total}",
								user_id=user_id,
							)
							async with stats_lock:
								logger.info(
									f"[日行情] {current_done}/{total} "
									f"({current_done / total * 100:.0f}%) "
									f"新增={records_added} 跳过={records_skipped} 失败={records_failed}"
								)

			# ===== 步骤 5：并行执行所有股票 =====
			# 使用 asyncio.gather 并发调度，Semaphore 自动限流
			coros = [_process_one(ts_code) for ts_code in ts_codes]
			await asyncio.gather(*coros)

			# ===== 步骤 6：最终进度更新（100%） =====
			await self._update_progress(
				task_id, progress=100,
				current_item=f"日行情: {total}/{total}", user_id=user_id,
			)

			logger.info(
				f"[日行情] 完成: 新增={records_added} 跳过={records_skipped} "
				f"失败={records_failed} 模式={mode_summary}"
			)
			return {
				"records_added": records_added, "records_updated": records_updated,
				"records_skipped": records_skipped, "records_failed": records_failed,
				"total_items": records_added + records_updated + records_skipped + records_failed,
				"mode_summary": mode_summary,
				"message": f"日行情数据同步完成（并行{max_concurrency}并发）"
			}

	async def _sync_minute_quotes(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			freq: str = "1min",
			**_kwargs
	) -> Dict[str, Any]:
		"""同步分钟行情数据（stock_minute 超表，批量插入不更新）。

		与日行情不同，分钟数据量大，仅批量插入不去重更新。
		默认只同步最近 7 天、最多 100 只活跃股票。

		Args:
			start_date: 起始日期（None → 7 天前）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 前 100 只活跃股票，分钟数据量大限制数量）
			task_id: 任务 ID
			user_id: 用户标识
			freq: K 线频率（"1min" / "5min" / "15min" / "30min" / "60min"）

		Returns:
			Dict: {records_added, records_updated(0), records_failed, total_items, message}"""
		if not end_date:
			end_date = datetime.now().date()
		if not start_date:
			start_date = end_date - timedelta(days=7)
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks(limit=100)  # 分钟数据量大，限制数量
			ts_codes = [stock.ts_code for stock in stocks]

		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0
		records_updated = 0
		records_failed = 0

		start_date_str = start_date.strftime('%Y%m%d') if start_date else ''
		end_date_str = end_date.strftime('%Y%m%d') if end_date else ''

		async with SyncTimingLogger(logger, "minute_quotes", slow_threshold=30.0):
			logger.info(f"[分钟行情] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
			for idx, ts_code in enumerate(ts_codes):
				if await self._is_cancelled(): break
				try:
					minute_df = await self._cancellable_run_in_executor(source.get_minute_bar, symbol=ts_code,
					                                                    start_date=start_date_str,
					                                                    end_date=end_date_str,
					                                                    freq=freq)

					if not minute_df.empty:
						minute_data = _convert_records_datetime(minute_df.to_dict('records'))
						# 分钟表通常使用批量插入，不进行更新
						inserted = await self.stock_minute_repo.batch_insert(minute_data)
						records_added += inserted
				except Exception as e:
					logger.error(f"同步 {ts_code} 分钟数据失败: {e}")
					records_failed += 1

				await self._update_progress(
					task_id,
					current_item=f"处理 {ts_code}",
					user_id=user_id
				)

				# 每处理5只股票提交一次
				if (idx + 1) % 5 == 0:
					logger.info(
						f"[分钟行情] {idx + 1}/{len(ts_codes)} ({(idx + 1) / len(ts_codes) * 100:.0f}%) 新增={records_added} 更新={records_updated} 失败={records_failed}")
					await self.session.commit()

			await self.session.commit()

			return {
				"records_added": records_added,
				"records_updated": 0,
				"records_failed": records_failed,
				"total_items": records_added + records_failed,
				"message": f"{freq}分钟行情数据同步完成"
			}

	async def _sync_moneyflow(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步资金流向数据（stock_moneyflow 表，逐股同步+智能日期推断）。

		资金流向反映主力资金进出情况，与日行情采用相同的逐股同步模式。
		通过 _resolve_sync_date_range 自动推断增量/全量模式。

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
				   records_failed, total_items, mode_summary, message}"""

		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0
		records_updated = 0
		records_skipped = 0
		records_failed = 0
		mode_summary = {"full": 0, "incremental": 0, "overlap": 0, "up_to_date": 0}

		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		else:
			stocks = await self.stock_basic_repo.get_active_stocks()

		# 批量预加载：一次 SQL 获取所有股票的最新日期（替代逐股查询）
		stock_list_date_map = {s.ts_code: s.list_date for s in stocks}
		latest_dates_map = await self.stock_moneyflow_repo.get_latest_trade_dates_batch(ts_codes)

		logger.info(f"[资金流向] 逐股同步 {len(ts_codes)} 只, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async with SyncTimingLogger(logger, "moneyflow", slow_threshold=10.0) as timer:

			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = StockMoneyflowRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo, latest_dates_map=latest_dates_map, stock_list_date_map=stock_list_date_map
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					df = await self._cancellable_run_in_executor(source.get_moneyflow, symbol=ts_code, start_date=s_str, end_date=e_str)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					data = _convert_records_datetime(df.to_dict("records"))
					added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[资金流向] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}
			logger.info(f"[资金流向] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
			result = await self._parallel_for_each(ts_codes, "资金流向", task_id, user_id, _process_one)
			if not result.get("cancelled"):
				result["message"] = "资金流向数据同步完成"
			return result


	async def _sync_adj_factor(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步复权因子数据（stock_adj_factor 表，逐股同步+智能日期推断）。

		复权因子用于前复权/后复权价格计算，每个交易日一条记录。
		采用与 _sync_daily_quotes 相同的逐股同步模式。

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
				   records_failed, total_items, mode_summary, message}"""
		# 步骤 1：获取股票列表
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		else:
			stocks = await self.stock_basic_repo.get_active_stocks()

		# 步骤 2：批量预加载所有股票的最新日期（一次 SQL 替代 N 次逐股查询）
		stock_list_date_map = {s.ts_code: s.list_date for s in stocks}
		latest_dates_map = await self.stock_adj_factor_repo.get_latest_trade_dates_batch(ts_codes)

		async with SyncTimingLogger(logger, "adj_factor", slow_threshold=10.0) as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = StockAdjFactorRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo,
						latest_dates_map=latest_dates_map,
						stock_list_date_map=stock_list_date_map,
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					async with timer.node(SyncTimingLogger.NODE_HTTP_FETCH, ts_code):
						df = await self._cancellable_run_in_executor(
							source.get_adj_factor, symbol=ts_code,
							start_date=s_str, end_date=e_str,
						)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					async with timer.node(SyncTimingLogger.NODE_CONVERT, ts_code):
						data = _convert_records_datetime(df.to_dict("records"))
					async with timer.node(SyncTimingLogger.NODE_DB_UPSERT, ts_code):
						added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[复权因子] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}

			logger.info(f"[复权因子] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
			result = await self._parallel_for_each(ts_codes, "复权因子", task_id, user_id, _process_one)
			if not result.get("cancelled"):
				result["message"] = "复权因子数据同步完成"
			return result

	async def _sync_daily_basic(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步每日指标数据（stock_daily_basic 表，逐股同步+智能日期推断）。

		每日指标包含市盈率、市净率、换手率等，与日行情一一对应。

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
				   records_failed, total_items, mode_summary, message}"""
		# 步骤 1：获取股票列表
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		else:
			stocks = await self.stock_basic_repo.get_active_stocks()

		# 步骤 2：批量预加载所有股票的最新日期（一次 SQL 替代 N 次逐股查询）
		stock_list_date_map = {s.ts_code: s.list_date for s in stocks}
		latest_dates_map = await self.stock_daily_basic_repo.get_latest_trade_dates_batch(ts_codes)

		async with SyncTimingLogger(logger, "daily_basic", slow_threshold=10.0) as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = StockDailyBasicRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo,
						latest_dates_map=latest_dates_map,
						stock_list_date_map=stock_list_date_map,
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					async with timer.node(SyncTimingLogger.NODE_HTTP_FETCH, ts_code):
						df = await self._cancellable_run_in_executor(
							source.get_daily_basic, symbol=ts_code,
							start_date=s_str, end_date=e_str,
						)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					async with timer.node(SyncTimingLogger.NODE_CONVERT, ts_code):
						data = _convert_records_datetime(df.to_dict("records"))
					async with timer.node(SyncTimingLogger.NODE_DB_UPSERT, ts_code):
						added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[每日指标] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}

			logger.info(f"[每日指标] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
			result = await self._parallel_for_each(ts_codes, "每日指标", task_id, user_id, _process_one)
			if not result.get("cancelled"):
				result["message"] = "每日指标数据同步完成"
			return result
	async def _sync_etf_basic(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步 ETF 基础信息（etf_basic 表，全量拉取）。

		调用 Tushare fund_basic 接口，拉取所有 ETF 基金的基础信息
		（基金代码、名称、管理人等）。全量 upsert，不区分日期。

		Args:
			start_date: 未使用（全量拉取）
			end_date: 未使用（全量拉取）
			ts_codes: 未使用（固定全量）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		etf_df = await self._cancellable_run_in_executor(source.get_etf_basic, )
		# 将DataFrame转换为字典列表并确保键为字符串类型
		etf_list = _convert_records_datetime(etf_df.to_dict('records')) if not etf_df.empty else []
		records_added = 0
		records_updated = 0
		# 批量预处理 + bulk upsert
		if etf_list and hasattr(self.etf_basic_repo, 'bulk_upsert'):
			_preprocess_records(etf_list, date_fields=['setup_date', 'list_date'])
			records_added = await self.etf_basic_repo.bulk_upsert(etf_list)
			records_updated = 0
		else:
			for etf in etf_list:
				if 'setup_date' in etf and etf['setup_date']:
					etf['setup_date'] = _convert_to_date(etf['setup_date'])
				if 'list_date' in etf and etf['list_date']:
					etf['list_date'] = _convert_to_date(etf['list_date'])
				existing = await self.etf_basic_repo.get_by(ts_code=etf["ts_code"])
				if existing:
					await self.etf_basic_repo.update_by({"ts_code": existing.ts_code}, etf)
					records_updated += 1
				else:
					await self.etf_basic_repo.create(etf)
					records_added += 1
			await self._update_progress(task_id, current_item=f"ETF: {etf['ts_code']}", user_id=user_id)
		await self.session.commit()
		return {
			"records_added": records_added,
			"records_updated": records_updated,
			"records_failed": 0,
			"total_items": len(etf_list),
			"message": "ETF基础信息同步完成"
		}

	async def _sync_etf_index(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步 ETF 基准指数列表（etf_index 表，全量拉取）。

		获取各 ETF 跟踪的基准指数及发行日期等信息。全量写入，重复记录 catch 后 update。

		Args:
			start_date: 未使用
			end_date: 未使用
			ts_codes: 未使用
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added, records_updated, records_failed = 0, 0, 0
		try:
			df = await self._cancellable_run_in_executor(source.get_etf_index, )
			if df is not None and not df.empty:
				data = _convert_records_datetime(df.to_dict('records'))
				if hasattr(self.etf_index_repo, "batch_upsert"):
					records_added += await self.etf_index_repo.bulk_upsert(data)
				else:
					_preprocess_records(data, date_fields=('pub_date',))
					for item in data:
						try:
							await self.etf_index_repo.create(item)
							records_added += 1
						except Exception as _e:
							if "unique" in str(_e).lower() or "duplicate" in str(_e).lower():
								try:
									await self.etf_index_repo.update_by(
										{"ts_code": item.get("ts_code", ""), "pub_date": item.get("pub_date", None)},
										item)
									records_updated += 1
								except Exception as _ue:
									logger.warning(f'记录唯一键冲突但更新失败: {_ue}')
									records_failed += 1
							else:
								logger.warning(f"[ETF指?数] 写入失败: {_e}")
								records_failed += 1

			await self.session.commit()
			return {"records_added": records_added, "records_updated": 0, "records_failed": records_failed,
			        "total_items": records_added + records_failed, "message": "ETF基准指数同步完成"}
		except Exception as e:
			logger.error(f"ETF基准指数同步失败: {e}")
			return {"records_added": 0, "records_updated": 0, "records_failed": 1, "total_items": 0,
			        "message": f"ETF基准指数同步失败: {str(e)}"}

	async def _sync_etf_daily(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步 ETF 日线行情（etf_daily 表，逐 ETF 同步+智能日期推断）。

		与股票日行情结构完全一致，不同之处在于股票代码来源为 etf_basic 表。

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: ETF 代码列表（None → 全部 ETF）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
				   records_failed, total_items, mode_summary, message}"""
		# 步骤 1：获取 ETF 列表
		if not ts_codes:
			etfs = await self.etf_basic_repo.get_all()
			ts_codes = [etf.ts_code for etf in etfs]
		else:
			etfs = await self.etf_basic_repo.get_all()

		# 步骤 2：批量预加载所有 ETF 的最新日期（一次 SQL 替代 N 次逐 ETF 查询）
		stock_list_date_map = {etf.ts_code: etf.list_date for etf in etfs if getattr(etf, 'list_date', None)}
		latest_dates_map = await self.etf_daily_repo.get_latest_trade_dates_batch(ts_codes)

		async with SyncTimingLogger(logger, "etf_daily", slow_threshold=10.0) as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = EtfDailyRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo,
						latest_dates_map=latest_dates_map,
						stock_list_date_map=stock_list_date_map,
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					async with timer.node(SyncTimingLogger.NODE_HTTP_FETCH, ts_code):
						df = await self._cancellable_run_in_executor(
							source.get_etf_daily, etf_code=ts_code,
							start_date=s_str, end_date=e_str,
						)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					async with timer.node(SyncTimingLogger.NODE_CONVERT, ts_code):
						data = _convert_records_datetime(df.to_dict("records"))
					async with timer.node(SyncTimingLogger.NODE_DB_UPSERT, ts_code):
						added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[ETF日线] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}

			logger.info(f"[ETF日线] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
			result = await self._parallel_for_each(ts_codes, "ETF日线", task_id, user_id, _process_one)
			if not result.get("cancelled"):
				result["message"] = "ETF日线数据同步完成"
			return result
	async def _sync_index_data_with_weight(
			self,
			start_date: str,
			end_date: str,
			index_codes=None
	) -> Dict[str, Any]:
		result = await self.sync_index_data(start_date, end_date, index_codes)
		try:
			await self.sync_index_weight()
		except Exception as e:
			logger.warning(f"指数成分股权重同步失败（行情数据已同步）: {e}")
		return result

	async def sync_index_weight(
			self,
			index_code: str = None,
			trade_date: str = None
	) -> Dict[str, Any]:
		"""同步指数成分股权重数据

		从 Tushare / Baostock 等数据源拉取指数成分股及权重，
		批量写入 index_weight 表（已存在记录会更新）。

		数据源选择策略：
		- 优先使用 Tushare pro.index_weight() 接口（支持沪深300、中证500）
		- 回退到 Baostock query_hs300_stocks() / query_zz500_stocks()

		调用时机：
		- 在 sync_index_data() 末尾自动调用
		- 也可独立调用，按月同步权重（指数成分股通常每月调整）

		Args:
			index_code: 指定指数代码，为 None 时同步沪深300 + 中证500
			trade_date: 指定权重日期，为 None 时使用当前日期

		Returns:
			Dict 含 records_added, records_updated, records_failed, message
		"""
		from datetime import date as date_type

		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0
		records_updated = 0
		records_failed = 0

		# 默认同步沪深300 和 中证500
		if index_code is None:
			target_indices = ['000300.SH', '000905.SH']
		else:
			target_indices = [index_code]

		# 默认使用当前日期
		if trade_date is None:
			trade_date_obj = date_type.today()
		else:
			trade_date_obj = _convert_to_date(trade_date)

		weight_repo = IndexWeightRepository(self.session)

		for idx_code in target_indices:
			try:
				constituent_data = []

				if hasattr(source, 'get_index_weight'):
					# Tushare 路径：使用 index_weight 接口获取真实权重
					weight_df = await self._cancellable_run_in_executor(source.get_index_weight, index_code=idx_code,
					                                                    trade_date=trade_date_obj.strftime('%Y%m%d')
					                                                    )
					if not weight_df.empty:
						for _, row in weight_df.iterrows():
							constituent_data.append({
								'index_code': idx_code,
								'ts_code': row.get('con_code', ''),
								'weight': float(row.get('weight', 0)) / 100.0 if row.get('weight', 0) > 1 else float(
									row.get('weight', 0)),
								'trade_date': trade_date_obj,
							})
				elif hasattr(source, 'get_index_constituents'):
					# Baostock 路径：获取成分股列表（等权）
					stocks = await self._cancellable_run_in_executor(source.get_index_constituents, index_code=idx_code)
					if stocks:
						n = len(stocks)
						w = 1.0 / n
						for ts_code in stocks:
							constituent_data.append({
								'index_code': idx_code,
								'ts_code': ts_code,
								'weight': w,
								'trade_date': trade_date_obj,
							})
				else:
					logger.warning(f"数据源不支持指数成分股权重获取: {idx_code}")
					records_failed += 1
					continue

				if constituent_data:
					await weight_repo.batch_upsert(
						match_fields=["index_code", "ts_code", "trade_date"],
						data_list=constituent_data
					)
					records_added += len(constituent_data)
					logger.info(
						f"指数 {idx_code} 成分股权重同步完成，"
						f"共 {len(constituent_data)} 条记录"
					)
				else:
					logger.warning(f"指数 {idx_code} 未获取到成分股数据")
					records_failed += 1

			except Exception as e:
				logger.error(f"同步指数 {idx_code} 成分股权重失败: {e}")
				records_failed += 1

		return {
			"records_added": records_added,
			"records_updated": records_updated,
			"records_failed": records_failed,
			"total_items": records_added + records_failed,
			"message": (
				f"指数成分股权重同步完成，"
				f"共处理 {len(target_indices)} 个指数，"
				f"新增 {records_added} 条记录"
			)
		}

	async def sync_macro_data(
			self,
			macro_type: str,
			start_date: str,
			end_date: str
	) -> Dict[str, Any]:
		"""同步宏观经济数据"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0
		records_failed = 0

		try:
			# 根据宏观经济数据类型选择同步策略
			if macro_type == 'cpi':
				# 同步CPI数据
				if hasattr(source, 'get_cpi'):
					cpi_df = await self._cancellable_run_in_executor(source.get_cpi, start_date=start_date,
					                                                 end_date=end_date)
					if not cpi_df.empty:
						from shared.database.repositories.market.macro import MacroCpiRepository
						cpi_repo = MacroCpiRepository(self.session)
						cpi_data = _convert_records_datetime(cpi_df.to_dict('records'))
						written = await cpi_repo.bulk_upsert(cpi_data)
						records_added += written
						logger.info(f"CPI数据同步完成，共 {written} 条记录")
				else:
					logger.warning(f"数据源不支持CPI数据同步")
					records_failed += 1
			elif macro_type == 'ppi':
				# 同步PPI数据
				if hasattr(source, 'get_ppi'):
					ppi_df = await self._cancellable_run_in_executor(source.get_ppi, start_date=start_date,
					                                                 end_date=end_date)
					if not ppi_df.empty:
						from shared.database.repositories.market.macro import MacroPpiRepository
						ppi_repo = MacroPpiRepository(self.session)
						ppi_data = _convert_records_datetime(ppi_df.to_dict('records'))
						written = await ppi_repo.bulk_upsert(ppi_data)
						records_added += written
						logger.info(f"PPI数据同步完成，共 {written} 条记录")
				else:
					logger.warning(f"数据源不支持PPI数据同步")
					records_failed += 1
			elif macro_type == 'gdp':
				# 同步GDP数据
				if hasattr(source, 'get_gdp'):
					gdp_df = await self._cancellable_run_in_executor(source.get_gdp, start_date=start_date,
					                                                 end_date=end_date)
					if not gdp_df.empty:
						from shared.database.repositories.market.macro import MacroGdpRepository
						gdp_repo = MacroGdpRepository(self.session)
						gdp_data = _convert_records_datetime(gdp_df.to_dict('records'))
						written = await gdp_repo.bulk_upsert(gdp_data)
						records_added += written
						logger.info(f"GDP数据同步完成，共 {written} 条记录")
				else:
					logger.warning(f"数据源不支持GDP数据同步")
					records_failed += 1
			else:
				logger.warning(f"不支持的宏观经济数据类型: {macro_type}")
				records_failed += 1
		except Exception as e:
			logger.error(f"宏观经济数据 {macro_type} 同步失败: {e}")
			records_failed += 1

		return {
			"records_added": records_added,
			"records_updated": 0,
			"records_failed": records_failed,
			"total_items": records_added + records_failed,
			"message": f"宏观经济数据 {macro_type} 同步完成"
		}

	# ==================== 宏观数据 wrapper ====================

	async def _sync_cpi(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步 CPI 居民消费价格指数。"""
		start_str = start_date.strftime('%Y%m%d') if start_date else datetime.now().strftime('%Y%m%d')
		end_str = end_date.strftime('%Y%m%d') if end_date else datetime.now().strftime('%Y%m%d')
		return await self.sync_macro_data('cpi', start_str, end_str)

	async def _sync_ppi(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步 PPI 工业生产者出厂价格指数。"""
		start_str = start_date.strftime('%Y%m%d') if start_date else datetime.now().strftime('%Y%m%d')
		end_str = end_date.strftime('%Y%m%d') if end_date else datetime.now().strftime('%Y%m%d')
		return await self.sync_macro_data('ppi', start_str, end_str)

	async def _sync_gdp(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步 GDP 国内生产总值。"""
		start_str = start_date.strftime('%Y%m%d') if start_date else datetime.now().strftime('%Y%m%d')
		end_str = end_date.strftime('%Y%m%d') if end_date else datetime.now().strftime('%Y%m%d')
		return await self.sync_macro_data('gdp', start_str, end_str)

	# ==================== 指数扩展 sync 方法 ====================

	async def _sync_index_weight(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步指数成分股权重。"""
		trade_date_str = end_date.strftime('%Y%m%d') if end_date else datetime.now().strftime('%Y%m%d')
		return await self.sync_index_weight(trade_date=trade_date_str)

	async def _sync_index_weekly(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步指数周线行情（Tushare index_weekly 接口）。"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0;
		records_failed = 0
		default_indices = ['000001.SH', '399001.SZ', '000300.SH', '000905.SH', '399006.SZ']
		indices = ts_codes if ts_codes else default_indices
		start_str = start_date.strftime('%Y%m%d') if start_date else datetime.now().strftime('%Y%m%d')
		end_str = end_date.strftime('%Y%m%d') if end_date else datetime.now().strftime('%Y%m%d')
		for idx_code in indices:
			try:
				if hasattr(source, 'get_index_weekly'):
					df = await self._cancellable_run_in_executor(source.get_index_weekly, ts_code=idx_code,
					                                             start_date=start_str, end_date=end_str)
					if not df.empty:
						records_added += len(df)
				else:
					records_failed += 1
			except Exception as e:
				logger.error(f"指数周线 {idx_code} 同步失败: {e}")
				records_failed += 1
		return {"records_added": records_added, "records_updated": 0,
		        "records_failed": records_failed,
		        "total_items": records_added + records_failed,
		        "message": f"指数周线行情同步完成: 新增={records_added}"}

	# [DEAD] async def async_sync_stock_quotes(
	# [DEAD] self,
	# [DEAD] stock_codes: List[str],
	# [DEAD] start_date: str,
	# [DEAD] end_date: str,
	# [DEAD] sync_type: str = 'daily'
	# [DEAD] ) -> Dict[str, Any]:
	# [DEAD] """异步同步股票行情数据"""
	# [DEAD] return await self.sync_stock_quote(
	# [DEAD] stock_codes=stock_codes,
	# [DEAD] start_date=start_date,
	# [DEAD] end_date=end_date,
	# [DEAD] _sync_type=sync_type,
	# [DEAD] force_update=False
	# [DEAD] )

	# [DEAD] # ==================== 具体同步方法 ====================

	async def _sync_etf_minute(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			freq: str = "1min",
			**_kwargs
	) -> Dict[str, Any]:
		"""同步 ETF 分钟行情（etf_minute 表，批量插入）。

		默认最近 7 天、最多 50 只 ETF。分钟数据量大，仅批量插入不去重。

		Args:
			start_date: 起始日期（None → 7 天前）
			end_date: 结束日期（None → 今天）
			ts_codes: ETF 代码列表（None → 前 50 只 ETF）
			task_id: 任务 ID
			user_id: 用户标识
			freq: K 线频率（默认 "1min"）

		Returns:
			Dict: {records_added, records_updated(0), records_failed, total_items, message}"""
		if not end_date:
			end_date = datetime.now().date()
		if not start_date:
			start_date = end_date - timedelta(days=7)
		if not ts_codes:
			# 使用 ETFRepository 获取所有 ETF
			etf_repo = ETFRepository(self.session)
			etfs = await etf_repo.get_all_etfs(limit=50)
			ts_codes = [etf.ts_code for etf in etfs]

		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0
		records_failed = 0

		async with SyncTimingLogger(logger, "etf_minute", slow_threshold=30.0):
			logger.info(f"[ETF分钟] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
			for idx, ts_code in enumerate(ts_codes):
				if await self._is_cancelled():
					logger.warning("检测到取消信号，中止ETF分钟同步")
					break
				try:
					start_date_str = start_date.strftime('%Y%m%d') if start_date else ''
					end_date_str = end_date.strftime('%Y%m%d') if end_date else ''

					minute_df = await self._cancellable_run_in_executor(source.get_etf_historical_minute, etf_code=ts_code,
					                                                    start_date=start_date_str,
					                                                    end_date=end_date_str,
					                                                    freq=freq)
					if not minute_df.empty:
						minute_data = _convert_records_datetime(minute_df.to_dict('records'))
						inserted = await self.etf_minute_repo.batch_insert(minute_data)
						records_added += inserted
				except Exception as e:
					logger.error(f"同步 {ts_code} ETF分钟数据失败: {e}")
					records_failed += 1

				await self._update_progress(task_id, current_item=f"处理 {ts_code}", user_id=user_id)

				# 每处理5只ETF提交一次
				if (idx + 1) % 5 == 0:
					logger.info(
						f"[ETF分钟] {idx + 1}/{len(ts_codes)} ({(idx + 1) / len(ts_codes) * 100:.0f}%) 新增={records_added} 更新={records_updated} 失败={records_failed}")
					await self.session.commit()

			await self.session.commit()
			return {
				"records_added": records_added,
				"records_updated": 0,
				"records_failed": records_failed,
				"total_items": records_added + records_failed,
				"message": f"ETF {freq}分钟行情同步完成"
			}

	async def _sync_fund_adj_factor(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步基金复权因子（fund_adj_factor 表，逐 ETF 同步+智能日期推断）。

		与股票复权因子结构一致，用于 ETF 的复权价格计算。

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: ETF 代码列表（None → 全部 ETF）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
				   records_failed, total_items, mode_summary, message}"""
		# 步骤 1：获取 ETF 列表
		if not ts_codes:
			etfs = await self.etf_basic_repo.get_all()
			ts_codes = [etf.ts_code for etf in etfs]
		else:
			etfs = await self.etf_basic_repo.get_all()

		# 步骤 2：批量预加载所有 ETF 的最新日期（一次 SQL 替代 N 次逐 ETF 查询）
		stock_list_date_map = {etf.ts_code: etf.list_date for etf in etfs if getattr(etf, 'list_date', None)}
		latest_dates_map = await self.fund_adj_factor_repo.get_latest_trade_dates_batch(ts_codes)

		async with SyncTimingLogger(logger, "fund_adj_factor", slow_threshold=10.0) as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = FundAdjFactorRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo,
						latest_dates_map=latest_dates_map,
						stock_list_date_map=stock_list_date_map,
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					async with timer.node(SyncTimingLogger.NODE_HTTP_FETCH, ts_code):
						df = await self._cancellable_run_in_executor(
							source.get_etf_adj_factor, etf_code=ts_code,
							start_date=s_str, end_date=e_str,
						)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					async with timer.node(SyncTimingLogger.NODE_CONVERT, ts_code):
						data = _convert_records_datetime(df.to_dict("records"))
					async with timer.node(SyncTimingLogger.NODE_DB_UPSERT, ts_code):
						added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[基金复权因子] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}

			logger.info(f"[基金复权因子] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
			result = await self._parallel_for_each(ts_codes, "基金复权因子", task_id, user_id, _process_one)
			if not result.get("cancelled"):
				result["message"] = "基金复权因子数据同步完成"
			return result
	async def _sync_financial_data(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步财务报表（三 表合并：利润表+资产负债表+现金流量表）

		每表独立同步，任一个被取消后跳过后续表。
		"""
		results = {}
		total_added = 0
		total_updated = 0
		total_failed = 0
		for name, method in [
			("income", self._sync_financial_income),
			("balance", self._sync_financial_balance),
			("cashflow", self._sync_financial_cashflow),
		]:
			# 取消时不再继续后续报表
			if await self._is_cancelled():
				results[name] = {"skipped": True, "reason": "cancelled"}
				break
			try:
				r = await method(start_date=start_date, end_date=end_date,
				                 ts_codes=ts_codes, task_id=task_id, user_id=user_id)
				results[name] = r
				total_added += r.get("records_added", 0)
				total_updated += r.get("records_updated", 0)
				total_failed += r.get("records_failed", 0)
			except Exception as e:
				logger.error(f"财务报表 {name} 同步失败: {e}")
				results[name] = {"error": str(e)}
				total_failed += 1
		cancelled = await self._is_cancelled()
		return {
			"records_added": total_added, "records_updated": total_updated,
			"records_failed": total_failed,
			"total_items": total_added + total_updated + total_failed,
			"cancelled": cancelled,
			"sub_results": results,
			"message": f"财务报表同步{'已取消' if cancelled else '完成'}（三表: 新增{total_added}, 更新{total_updated}, 失败{total_failed}）"
		}

	async def _sync_financial_income(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**kwargs
	) -> Dict[str, Any]:
		"""同步利润表数据，委托给 ``_sync_financial_statement(report_type="income")``。

		Args:
			start_date: 起始日期
			end_date: 结束日期
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		return await self._sync_financial_statement(
			start_date=start_date,
			end_date=end_date,
			ts_codes=ts_codes,
			task_id=task_id,
			user_id=user_id,
			report_type="income",
			**kwargs
		)

	async def _sync_financial_balance(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**kwargs
	) -> Dict[str, Any]:
		"""同步资产负债表，委托给 ``_sync_financial_statement(report_type="balance")``。

		Args:
			start_date: 起始日期
			end_date: 结束日期
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		return await self._sync_financial_statement(
			start_date=start_date,
			end_date=end_date,
			ts_codes=ts_codes,
			task_id=task_id,
			user_id=user_id,
			report_type="balance",
			**kwargs
		)

	async def _sync_financial_cashflow(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**kwargs
	) -> Dict[str, Any]:
		"""同步现金流量表，委托给 ``_sync_financial_statement(report_type="cashflow")``。

		Args:
			start_date: 起始日期
			end_date: 结束日期
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		return await self._sync_financial_statement(
			start_date=start_date,
			end_date=end_date,
			ts_codes=ts_codes,
			task_id=task_id,
			user_id=user_id,
			report_type="cashflow",
			**kwargs
		)

	# --- 财务报表通用同步（三类报表共用） ---

	async def _sync_financial_statement(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			report_type: str = "income",
			**_kwargs
	) -> Dict[str, Any]:
		"""通用财务报表同步方法（利润表/资产负债表/现金流量表共用）。

		根据 ``report_type`` 参数调用不同的 Tushare 接口：
		- ``"income"`` → ``get_income_statement``（利润表）
		- ``"balance"`` → ``get_balance_sheet``（资产负债表）
		- ``"cashflow"`` → ``get_cashflow_statement``（现金流量表）

		关键处理逻辑：
		1. 从 ORM 模型 ``FinancialStatement`` 获取已知列名，过滤 Tushare 多余字段
		2. 每条记录设置 ``report_type`` 标签，三表存入同一张 financial_statements 表
		3. 按 ``(ts_code, ann_date, report_type)`` 三元组查重去重
		4. 每只股票处理完即 commit（财务报表接口返回数据量大，减少事务持有时间）

		Args:
			start_date: 未使用（财务报表按报告期拉取，不按日期过滤）
			end_date: 未使用
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识
			report_type: 报表类型（"income" / "balance" / "cashflow"）

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [stock.ts_code for stock in stocks]

		# 获取 FinancialStatement 模型的已知列名，用于过滤 Tushare 多余字段
		known_cols = {c.name for c in FinancialStatement.__table__.columns}

		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0
		records_updated = 0
		records_failed = 0

		logger.info(f"[财务报表] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async with SyncTimingLogger(logger, f"financial_{report_type}") as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：HTTP拉取 > 日期转换 > upsert。"""
				repo = FinancialStatementRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					df = await self._cancellable_run_in_executor(source.get_income_statement, symbol=ts_code, period='')
					if df is None or df.empty:
						return {"added": 0, "updated": 0}
					data = _convert_records_datetime(df.to_dict("records"))
					_preprocess_records(data, date_fields=('ann_date', 'end_date'))
					added = await repo.bulk_upsert(data)
					return {"added": added, "updated": 0}
				except Exception as e:
					logger.error(f"[财务报表] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}
			logger.info(f"[财务报表] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "财务报表", task_id, user_id, _process_one, rate_key="financial_statement")
			if not result.get("cancelled"):
				result["message"] = "财务报表数据同步完成"
			return result


	async def _sync_trade_calendar(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步交易日历（trade_calendar 表，按交易所/日期 upsert）。

		获取 SSE（上交所）和 SZSE（深交所）的交易日历，标记每个日期是否为交易日。

		Args:
			start_date: 起始日期
			end_date: 结束日期
			ts_codes: 未使用
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		start_date_str = start_date.strftime('%Y%m%d') if start_date else ''
		end_date_str = end_date.strftime('%Y%m%d') if end_date else ''

		# get_trade_cal is async, direct await (no executor)
		calendar_df = await source.get_trade_cal(
			start_date=start_date_str,
			end_date=end_date_str
		)
		records_added = 0
		records_updated = 0

		if calendar_df is not None and not calendar_df.empty:
			calendar_data = _convert_records_datetime(calendar_df.to_dict('records'))
			# 批量预处理 + bulk upsert（替代逐行 SELECT+INSERT/UPDATE）
			if hasattr(self.trade_calendar_repo, 'bulk_upsert'):
				_preprocess_records(calendar_data, date_fields=['cal_date', 'pretrade_date'])
				records_added = await self.trade_calendar_repo.bulk_upsert(calendar_data)
				records_updated = 0
			else:
				for cal in calendar_data:
					if await self._is_cancelled():
						break
					cal['cal_date'] = _convert_to_date(cal.get('cal_date'))
					if 'pretrade_date' in cal and cal['pretrade_date']:
						cal['pretrade_date'] = _convert_to_date(cal.get('pretrade_date'))
					existing_list = await self.trade_calendar_repo.get_by_date(
						exchange=cal["exchange"], cal_date=cal['cal_date'])
					existing = existing_list[0] if existing_list else None
					if existing:
						await self.trade_calendar_repo.update_by(
							{"exchange": existing.exchange, "cal_date": existing.cal_date}, cal)
						records_updated += 1
					else:
						await self.trade_calendar_repo.create(cal)
						records_added += 1
		await self.session.commit()
		return {
			"records_added": records_added,
			"records_updated": records_updated,
			"records_failed": 0,
			"total_items": len(calendar_data),
			"message": "交易日历同步完成"
		}

	# --- 公司基本信息与治理 ---

	async def _sync_stock_company(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步上市公司基本信息（stock_company 表，全量拉取后逐条 upsert）。

		包含公司注册地址、注册资本、员工人数、主营业务等基本面信息。

		Args:
			start_date: 未使用（全量拉取）
			end_date: 未使用
			ts_codes: 未使用（固定全量）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0;
		records_updated = 0
		try:
			df = await self._cancellable_run_in_executor(source.get_stock_company, )
			if df.empty:
				return {"records_added": 0, "records_updated": 0, "records_failed": 0, "total_items": 0,
				        "message": "公司信息同步完成（无数据）"}
			data = _convert_records_datetime(df.to_dict('records'))
			# 兜底：com_name 为空时用 ts_code 填充（NOT NULL 约束）
			_empty_name_count = 0
			for d in data:
				if not d.get("com_name"):
					d["com_name"] = d.get("ts_code", "")
					_empty_name_count += 1
			if _empty_name_count:
				logger.warning(f"[公司信息] {_empty_name_count} 条 com_name 为空，已用 ts_code 兜底")
			if hasattr(self.company_repo, "batch_upsert"):
				_preprocess_records(data, date_fields=["setup_date", "list_date"])
				for item in data:
					if item.get("com_id") is None:
						item["com_id"] = ""
				records_added += await self.company_repo.bulk_upsert(data)
			else:
				_preprocess_records(data, date_fields=('setup_date',))
				for item in data:
					existing = await self.company_repo.get_by(ts_code=item["ts_code"])
					if existing:
						await self.company_repo.update(existing.id, item);
						records_updated += 1
					else:
						await self.company_repo.create(item);
						records_added += 1
			await self.session.commit()
			return {"records_added": records_added, "records_updated": records_updated, "records_failed": 0,
			        "total_items": records_added + records_updated, "message": "公司基本信息同步完成"}
		except Exception as e:
			logger.error(f"公司信息同步失败: {_fmt_err(e)}")
			return {"records_added": 0, "records_updated": 0, "records_failed": 1, "total_items": 0,
			        "message": f"公司信息同步失败: {str(e)}"}

	# --- ST 股票变更历史 ---

	async def _sync_st_list(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步 ST 股票变更历史（st_list 表，全市场日期范围拉取）。

		通过 Tushare namechange 接口获取 ST/*ST 变更记录，
		仅保留 name 包含 "ST" 的记录写入 st_list 表。

		Args:
			start_date: 起始日期（None → 1990-12-19，A 股最早交易日）
			end_date: 结束日期（None → 今天）
			ts_codes: 未使用（全市场拉取）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated(0), records_failed, total_items, message}"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		if not start_date: start_date = date(1990, 12, 19)
		if not end_date: end_date = datetime.now().date()
		start_date_str = start_date.strftime('%Y%m%d');
		end_date_str = end_date.strftime('%Y%m%d')
		records_added = 0;
		records_failed = 0
		try:
			df = await self._cancellable_run_in_executor(source.get_namechange, start_date=start_date_str,
			                                             end_date=end_date_str)
			if df.empty: return {"records_added": 0, "records_updated": 0, "records_failed": 0, "total_items": 0,
			                     "message": "ST列表同步完成（无数据）"}
			data = _convert_records_datetime(df.to_dict('records'))
			if hasattr(self.st_list_repo, "batch_upsert"):
				records_added += await self.st_list_repo.bulk_upsert(data)
			else:
				_preprocess_records(data, date_fields=('start_date',))
				for item in data:
					if item.get('start_date'): item['trade_date'] = item['start_date']
					name = item.get('name', '')
					if 'ST' in str(name).upper():
						item['st_type'] = '*ST' if '*ST' in str(name) else 'ST'
						item['st_type_name'] = name
						try:
							await self.st_list_repo.create(item);
							records_added += 1
						except Exception:
							try:
								await self.st_list_repo.update_by(
									{"ts_code": item["ts_code"], "trade_date": item["trade_date"]}, item)
							except Exception as _ue:
								logger.warning(f'记录唯一键冲突但更新失败: {_ue}')
								records_failed += 1
			await self.session.commit()
			return {"records_added": records_added, "records_updated": 0, "records_failed": records_failed,
			        "total_items": records_added + records_failed, "message": "ST股票列表同步完成"}
		except Exception as e:
			logger.error(f"ST列表同步失败: {e}")
			return {"records_added": 0, "records_updated": 0, "records_failed": 1, "total_items": 0,
			        "message": f"ST列表同步失败: {str(e)}"}

	async def _sync_stk_managers(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步管理层信息（stk_managers 表，逐股先删后插保证数据一致性）。

		每位高管可能发生职位变更，采用"删除全部旧记录→插入新记录"策略
		而非 upsert，确保数据与数据源完全一致。

		Args:
			start_date: 未使用
			end_date: 未使用
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		if not ts_codes: stocks = await self.stock_basic_repo.get_active_stocks(); ts_codes = [s.ts_code for s in
		                                                                                       stocks]
		records_added = 0;
		records_updated = 0;
		records_failed = 0
		logger.info(f"[管理层] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async def _process_one(session, ts_code):
			"""处理单只标的：先删后插。"""
			repo = ManagerRepository(session)
			source = self.source_factory.get_source(DataSource.TUSHARE)
			try:
				await repo.delete_by_ts_code(ts_code)
				df = await self._cancellable_run_in_executor(source.get_stk_managers, ts_code=ts_code)
				if df is None or df.empty:
					return {"added": 0, "updated": 0}
				data = _convert_records_datetime(df.to_dict("records"))
				added = await repo.bulk_upsert(data)
				return {"added": added, "updated": 0}
			except Exception as e:
				logger.error(f"[管理层信息] {ts_code} 同步失败: {e}")
				return {"added": 0, "updated": 0, "failed": True}
		async with SyncTimingLogger(logger, "stk_managers", slow_threshold=30.0):
			logger.info(f"[管理层信息] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "管理层信息", task_id, user_id, _process_one, rate_key="managers")
			if not result.get("cancelled"):
				result["message"] = "管理层信息数据同步完成"
			return result
	async def _sync_stk_rewards(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步管理层薪酬持股（stk_rewards 表，逐股先删后插保证数据一致性）。

		与 _sync_stk_managers 相同的策略："删除全部旧记录→插入新记录"。
		薪酬持股数据常有变动，不允许 upsert 导致旧数据残留。

		Args:
			start_date: 未使用
			end_date: 未使用
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		source = self.source_factory.get_source(DataSource.TUSHARE)
		if not ts_codes: stocks = await self.stock_basic_repo.get_active_stocks(); ts_codes = [s.ts_code for s in
		                                                                                       stocks]
		records_added = 0;
		records_updated = 0;
		records_failed = 0
		logger.info(f"[薪酬] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async def _process_one(session, ts_code):
			"""处理单只标的：先删后插。"""
			repo = RewardRepository(session)
			source = self.source_factory.get_source(DataSource.TUSHARE)
			try:
				await repo.delete_by_ts_code(ts_code)
				df = await self._cancellable_run_in_executor(source.get_stk_rewards, ts_code=ts_code)
				if df is None or df.empty:
					return {"added": 0, "updated": 0}
				data = _convert_records_datetime(df.to_dict("records"))
				_preprocess_records(data, fill_numeric=("reward", "hold_vol"))
				added = await repo.bulk_upsert(data)
				return {"added": added, "updated": 0}
			except Exception as e:
				logger.error(f"[管理层薪酬] {ts_code} 同步失败: {e}")
				return {"added": 0, "updated": 0, "failed": True}
		async with SyncTimingLogger(logger, "stk_rewards", slow_threshold=30.0):
			logger.info(f"[管理层薪酬] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "管理层薪酬", task_id, user_id, _process_one, rate_key="rewards")
			if not result.get("cancelled"):
				result["message"] = "管理层薪酬数据同步完成"
			return result
	async def _sync_weekly_quotes(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步周线行情（stock_weekly 表，逐股同步+智能日期推断）。

		与 _sync_daily_quotes 结构一致，由 Tushare 接口直接返回周线数据。

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
				   records_failed, total_items, message}"""
		# 步骤 1：获取股票列表
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [stock.ts_code for stock in stocks]
		else:
			stocks = await self.stock_basic_repo.get_active_stocks()

		# 步骤 2：批量预加载所有股票的最新日期（一次 SQL 替代 N 次逐股查询）
		stock_list_date_map = {s.ts_code: s.list_date for s in stocks}
		latest_dates_map = await self.stock_weekly_repo.get_latest_trade_dates_batch(ts_codes)

		async with SyncTimingLogger(logger, "weekly_quotes", slow_threshold=10.0) as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = StockWeeklyRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo,
						latest_dates_map=latest_dates_map,
						stock_list_date_map=stock_list_date_map,
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					async with timer.node(SyncTimingLogger.NODE_HTTP_FETCH, ts_code):
						df = await self._cancellable_run_in_executor(
							source.get_weekly, symbol=ts_code,
							start_date=s_str, end_date=e_str,
						)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					async with timer.node(SyncTimingLogger.NODE_CONVERT, ts_code):
						data = _convert_records_datetime(df.to_dict("records"))
					async with timer.node(SyncTimingLogger.NODE_DB_UPSERT, ts_code):
						added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[周线行情] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}

			logger.info(f"[周线行情] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
			result = await self._parallel_for_each(ts_codes, "周线行情", task_id, user_id, _process_one)
			if not result.get("cancelled"):
				result["message"] = "周线行情数据同步完成"
			return result
	async def _sync_monthly_quotes(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步月线行情（stock_monthly 表，逐股同步+智能日期推断）。

		与 _sync_daily_quotes 结构一致，由 Tushare 接口直接返回月线数据。

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
				   records_failed, total_items, message}"""
		# 步骤 1：获取股票列表
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [stock.ts_code for stock in stocks]
		else:
			stocks = await self.stock_basic_repo.get_active_stocks()

		# 步骤 2：批量预加载所有股票的最新日期（一次 SQL 替代 N 次逐股查询）
		stock_list_date_map = {s.ts_code: s.list_date for s in stocks}
		latest_dates_map = await self.stock_monthly_repo.get_latest_trade_dates_batch(ts_codes)

		async with SyncTimingLogger(logger, "monthly_quotes", slow_threshold=10.0) as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = StockMonthlyRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo,
						latest_dates_map=latest_dates_map,
						stock_list_date_map=stock_list_date_map,
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					async with timer.node(SyncTimingLogger.NODE_HTTP_FETCH, ts_code):
						df = await self._cancellable_run_in_executor(
							source.get_monthly, symbol=ts_code,
							start_date=s_str, end_date=e_str,
						)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					async with timer.node(SyncTimingLogger.NODE_CONVERT, ts_code):
						data = _convert_records_datetime(df.to_dict("records"))
					async with timer.node(SyncTimingLogger.NODE_DB_UPSERT, ts_code):
						added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[月线行情] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}

			logger.info(f"[月线行情] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
			result = await self._parallel_for_each(ts_codes, "月线行情", task_id, user_id, _process_one)
		if not result.get("cancelled"):
			result["message"] = "月线行情数据同步完成"
		return result
	async def _sync_index_basic(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步指数基本信息（index_basic 表，分 SSE/SZSE 两个市场拉取）。

		获取沪深两市所有指数的基本信息（指数代码、名称、发布日等）。

		Args:
			start_date: 未使用
			end_date: 未使用
			ts_codes: 未使用（全量拉取）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""

		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0;
		records_updated = 0;
		records_failed = 0
		for market in ['SSE', 'SZSE']:
			try:
				df = await self._cancellable_run_in_executor(source.get_index_basic, market=market)
				if df.empty: continue
				data = _convert_records_datetime(df.to_dict('records'))

				_preprocess_records(data, date_fields=('list_date', 'base_date', 'exp_date'))
				if hasattr(self.index_basic_repo, "batch_upsert"):
					records_added += await self.index_basic_repo.bulk_upsert(data)
				else:
					for item in data:
						existing = await self.index_basic_repo.get_by(ts_code=item["ts_code"])
						if existing:
							await self.index_basic_repo.update(existing.id, item);
							records_updated += 1
						else:
							await self.index_basic_repo.create(item);
							records_added += 1
			except Exception as e:
				logger.error(f"指数基本信息 {market} 同步失败: {e}")
				records_failed += 1
		await self.session.commit()
		return {"records_added": records_added, "records_updated": records_updated, "records_failed": records_failed,
		        "total_items": records_added + records_updated + records_failed, "message": "指数基本信息同步完成"}

	async def _sync_index_daily(
			self, start_date: Optional[date], end_date: Optional[date],
			ts_codes: Optional[List[str]], task_id: str,
			user_id: Optional[str] = None, **_kwargs
	) -> Dict[str, Any]:
		"""同步指数日线行情（index_daily 表，逐指数同步+智能日期推断）。

		结构与 _sync_daily_quotes 一致。无 ts_codes 时默认同步 5 大指数
		（上证指数、深证成指、沪深300、中证500、创业板指）。

		Args:
			start_date: 起始日期（None → 自动推断）
			end_date: 结束日期（None → 今天）
			ts_codes: 指数代码列表（None → 5 大指数或全部指数）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_skipped,
				   records_failed, total_items, message}"""

		# 步骤 1：获取指数列表
		if not ts_codes:
			all_indices = await self.index_basic_repo.get_all()
			ts_codes = [idx.ts_code for idx in all_indices] if all_indices else ['000001.SH', '399001.SZ', '000300.SH',
			                                                                     '000905.SH', '399006.SZ']

		# 步骤 2：批量预加载所有指数的最新日期（一次 SQL 替代 N 次逐指数查询）
		latest_dates_map = await self.index_daily_repo.get_latest_trade_dates_batch(ts_codes)

		async with SyncTimingLogger(logger, "index_daily", slow_threshold=10.0) as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = IndexDailyRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo,
						latest_dates_map=latest_dates_map,
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					async with timer.node(SyncTimingLogger.NODE_HTTP_FETCH, ts_code):
						df = await self._cancellable_run_in_executor(
							source.get_index_daily, ts_code=ts_code,
							start_date=s_str, end_date=e_str,
						)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					async with timer.node(SyncTimingLogger.NODE_CONVERT, ts_code):
						data = _convert_records_datetime(df.to_dict("records"))
					async with timer.node(SyncTimingLogger.NODE_DB_UPSERT, ts_code):
						added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[指数日线] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}
				logger.info(f"[指数日线] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
				result = await self._parallel_for_each(ts_codes, "指数日线", task_id, user_id, _process_one)
				if not result.get("cancelled"):
					result["message"] = "指数日线数据同步完成"
				return result
	async def _sync_tick_quotes(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步 Tick 级行情数据（逐股按日拉取，数据量极大，仅同步活跃股票中少量）。

		**注意**：Tick 数据量极大（单只股票一天可有数万条），默认只同步 1 天、
		最多 10 只股票。此方法仅用于特殊分析场景，不参与常规同步流程。

		Args:
			start_date: 起始日期（None → 昨天）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 前 10 只活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated(0), records_failed, total_items, message}"""
		if not end_date:
			end_date = datetime.now().date()
		if not start_date:
			start_date = end_date - timedelta(days=1)  # Tick数据量大，默认只同步一天
		if not ts_codes:
			# Tick数据量大，限制同步股票数量
			stocks = await self.stock_basic_repo.get_active_stocks(limit=10)
			ts_codes = [stock.ts_code for stock in stocks]

		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added = 0
		records_failed = 0

		logger.info(f"[逐笔行情] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		for idx, ts_code in enumerate(ts_codes):
			if await self._is_cancelled(): break
			try:
				# Tick数据通常需要按天获取
				current_date = start_date
				while current_date <= end_date:
					try:
						tick_df = await self._cancellable_run_in_executor(source.get_tick_data, symbol=ts_code,
						                                                  trade_date=current_date.strftime('%Y%m%d')
						                                                  )
						if not tick_df.empty:
							# Tick数据通常使用批量插入到专门的分区表或超表
							# 这里需要根据实际的Tick数据存储方式进行调整
							tick_data = _convert_records_datetime(tick_df.to_dict('records'))
							records_added += len(tick_data)
					except Exception as e:
						logger.warning(f"获取 {ts_code} {current_date} Tick数据失败: {e}")
						records_failed += 1

					current_date += timedelta(days=1)
			except Exception as e:
				logger.error(f"同步 {ts_code} Tick数据失败: {e}")
				records_failed += 1

			await self._update_progress(
				task_id,
				progress=min(100, int((idx + 1) / len(ts_codes) * 100)),
				current_item=f"处理 {ts_code} Tick数据",
				user_id=user_id
			)

			# 每处理一只股票提交一次
			if (idx + 1) % 1 == 0:
				logger.info(
					f"[Tick] {idx + 1}/{len(ts_codes)} ({(idx + 1) / len(ts_codes) * 100:.0f}%) 新增={records_added} 更新={records_updated} 失败={records_failed}")
				await self.session.commit()

		await self.session.commit()
		return {
			"records_added": records_added,
			"records_updated": 0,  # Tick数据通常只插入不更新
			"records_failed": records_failed,
			"total_items": records_added + records_failed,
			"message": "Tick级行情数据同步完成"
		}

	# --- 财务衍生数据（停复牌 / ETF 份额 / 业绩预告 / 快报 / 分红 / 财务指标 / 审计意见 / 主营业务） ---

	async def _sync_suspend_info(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步停复牌信息（suspend_info 表，全市场日期范围拉取）。

		通过 Tushare suspend_d 接口获取停复牌公告信息，
		默认拉取最近 30 天。重复记录 catch 后 update。

		Args:
			start_date: 起始日期（None → 30 天前）
			end_date: 结束日期（None → 今天）
			ts_codes: 未使用（全市场拉取）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		if not end_date: end_date = datetime.now().date()
		if not start_date: start_date = end_date - timedelta(days=30)
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added, records_updated, records_failed = 0, 0, 0
		start_date_str = start_date.strftime('%Y%m%d') if start_date else ''
		end_date_str = end_date.strftime('%Y%m%d') if end_date else ''
		try:
			df = await self._cancellable_run_in_executor(source.get_suspended, start_date=start_date_str,
			                                             end_date=end_date_str)
			if df is not None and not df.empty:
				data = _convert_records_datetime(df.to_dict('records'))
				if hasattr(self.suspend_info_repo, "batch_upsert"):
					records_added += await self.suspend_info_repo.bulk_upsert(data)
				else:
					_preprocess_records(data, date_fields=('trade_date',))
					for item in data:
						try:
							await self.suspend_info_repo.create(item)
							records_added += 1
						except Exception as _e:
							if "unique" in str(_e).lower() or "duplicate" in str(_e).lower():
								try:
									await self.suspend_info_repo.update_by({"ts_code": item.get("ts_code", ""),
									                                        "suspend_type": item.get("suspend_type",
									                                                                 None)},
									                                       item)
									records_updated += 1
								except Exception as _ue:
									logger.warning(f'记录唯一键冲突但更新失败: {_ue}')
									records_failed += 1
							else:
								logger.warning(f"[停复牌] 写入失败: {_e}")
								records_failed += 1

			await self.session.commit()
			return {"records_added": records_added, "records_updated": 0, "records_failed": records_failed,
			        "total_items": records_added + records_failed, "message": "停复牌信息同步完成"}
		except Exception as e:
			logger.error(f"停复牌信息同步失败: {e}")
			await self.session.commit()
			return {"records_added": 0, "records_updated": 0, "records_failed": 1, "total_items": 0,
			        "not_implemented": True, "message": f"停复牌信息同步失败: {str(e)}"}

	async def _sync_etf_share(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步 ETF 份额规模（etf_share 表，逐 ETF 拉取）。

		ETF 份额和规模每日变化，反映资金净流入/流出情况。
		逐 ETF 拉取全历史数据，按 (ts_code, trade_date) 去重。

		Args:
			start_date: 未使用（全历史拉取）
			end_date: 未使用
			ts_codes: ETF 代码列表（None → 全部 ETF）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		# 步骤 1：获取 ETF 列表
		if not ts_codes:
			etfs = await self.etf_basic_repo.get_all()
			ts_codes = [etf.ts_code for etf in etfs]
		else:
			etfs = await self.etf_basic_repo.get_all()

		# 步骤 2：批量预加载所有 ETF 的最新日期（一次 SQL 替代 N 次逐 ETF 查询）
		stock_list_date_map = {etf.ts_code: etf.list_date for etf in etfs if getattr(etf, 'list_date', None)}
		latest_dates_map = await self.etf_share_repo.get_latest_trade_dates_batch(ts_codes)

		async with SyncTimingLogger(logger, "etf_share", slow_threshold=10.0) as timer:
			async def _process_one(session, ts_code):
				"""处理单只标的：日期推断 > HTTP拉取 > 转换 > upsert。"""
				repo = EtfShareRepository(session)
				source = self.source_factory.get_source(DataSource.TUSHARE)
				try:
					s_date, e_date, mode = await self._resolve_sync_date_range(
						ts_code, start_date, end_date, repo,
						latest_dates_map=latest_dates_map,
						stock_list_date_map=stock_list_date_map,
					)
					if mode == "up_to_date":
						return {"added": 0, "updated": 0, "skipped": 1, "mode": mode}
					s_str = "" if mode == "full" else (s_date.strftime("%Y%m%d") if s_date else "")
					e_str = "" if mode == "full" else (e_date.strftime("%Y%m%d") if e_date else "")
					async with timer.node(SyncTimingLogger.NODE_HTTP_FETCH, ts_code):
						df = await self._cancellable_run_in_executor(
							source.get_etf_share_scale, etf_code=ts_code, trade_date='',
						)
					if df is None or df.empty:
						return {"added": 0, "updated": 0, "mode": mode}
					async with timer.node(SyncTimingLogger.NODE_CONVERT, ts_code):
						data = _convert_records_datetime(df.to_dict("records"))
					async with timer.node(SyncTimingLogger.NODE_DB_UPSERT, ts_code):
						added, _ = await self._process_trade_date_data(repo, data, ts_code)
					return {"added": added, "updated": 0, "mode": mode}
				except Exception as e:
					logger.error(f"[ETF份额] {ts_code} 同步失败: {e}")
					return {"added": 0, "updated": 0, "failed": True}

			logger.info(f"[ETF份额] 并行同步 {len(ts_codes)} 只, 并发=8, 预估 ~{len(ts_codes) * 0.3 / 60 / 8:.1f}min")
			result = await self._parallel_for_each(ts_codes, "ETF份额", task_id, user_id, _process_one)
			if not result.get("cancelled"):
				result["message"] = "ETF份额数据同步完成"
			return result
	async def _sync_forecast(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步业绩预告（forecast 表，逐股拉取全历史）。

		业绩预告是上市公司在正式财报发布前的预估数据，
		按 (ts_code, ann_date) 去重。

		Args:
			start_date: 未使用（全历史拉取）
			end_date: 未使用
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added, records_updated, records_failed = 0, 0, 0
		logger.info(f"[业绩预告] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async def _process_one(session, ts_code):
			"""处理单只标的：HTTP拉取 > 日期转换 > upsert。"""
			repo = StockForecastRepository(session)
			source = self.source_factory.get_source(DataSource.TUSHARE)
			try:
				df = await self._cancellable_run_in_executor(source.get_forecast, symbol=ts_code, period='')
				if df is None or df.empty:
					return {"added": 0, "updated": 0}
				data = _convert_records_datetime(df.to_dict("records"))
				_preprocess_records(data, date_fields=('ann_date', 'end_date'))
				data.sort(key=lambda d: d.get('ann_date') or date.min, reverse=True)
				# 批次内按唯一键去重（Tushare 偶发返回重复行，PG ON CONFLICT 无法处理）
				data = list({(d.get('ts_code'), d.get('ann_date')): d for d in data}.values())
				added = await repo.bulk_upsert(data)
				return {"added": added, "updated": 0}
			except Exception as e:
				logger.error(f"[业绩预告] {ts_code} 同步失败: {e}")
				return {"added": 0, "updated": 0, "failed": True}
		async with SyncTimingLogger(logger, "forecast", slow_threshold=30.0):
			logger.info(f"[业绩预告] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "业绩预告", task_id, user_id, _process_one, rate_key="forecast")
			if not result.get("cancelled"):
				result["message"] = "业绩预告数据同步完成"
			return result
	async def _sync_express(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步业绩快报（express 表，逐股拉取全历史）。

		业绩快报介于预告和正式财报之间，数据比预告更准确。
		按 (ts_code, ann_date) 去重。

		Args:
			start_date: 未使用（全历史拉取）
			end_date: 未使用
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added, records_updated, records_failed = 0, 0, 0
		logger.info(f"[业绩快报] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async def _process_one(session, ts_code):
			"""处理单只标的：HTTP拉取 > 日期转换 > upsert。"""
			repo = StockExpressRepository(session)
			source = self.source_factory.get_source(DataSource.TUSHARE)
			try:
				df = await self._cancellable_run_in_executor(source.get_express, symbol=ts_code, period='')
				if df is None or df.empty:
					return {"added": 0, "updated": 0}
				data = _convert_records_datetime(df.to_dict("records"))
				_preprocess_records(data, date_fields=('ann_date', 'end_date'))
				data.sort(key=lambda d: d.get('ann_date') or date.min, reverse=True)
				# 批次内按唯一键去重（Tushare 偶发返回重复行，PG ON CONFLICT 无法处理）
				data = list({(d.get('ts_code'), d.get('ann_date')): d for d in data}.values())
				added = await repo.bulk_upsert(data)
				return {"added": added, "updated": 0}
			except Exception as e:
				logger.error(f"[业绩快报] {ts_code} 同步失败: {e}")
				return {"added": 0, "updated": 0, "failed": True}
		async with SyncTimingLogger(logger, "express", slow_threshold=30.0):
			logger.info(f"[业绩快报] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "业绩快报", task_id, user_id, _process_one, rate_key="express")
			if not result.get("cancelled"):
				result["message"] = "业绩快报数据同步完成"
			return result
	async def _sync_dividend(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步分红送股（dividend 表，逐股拉取，limit=100 条/股）。

		分红送股是上市公司回馈股东的重要信息。按 (ts_code, ann_date) 去重。

		Args:
			start_date: 未使用
			end_date: 未使用
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added, records_updated, records_failed = 0, 0, 0
		logger.info(f"[分红送股] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async def _process_one(session, ts_code):
			"""处理单只标的：HTTP拉取 > 日期转换 > upsert。"""
			repo = StockDividendRepository(session)
			source = self.source_factory.get_source(DataSource.TUSHARE)
			try:
				df = await self._cancellable_run_in_executor(source.get_dividend, symbol=ts_code, limit=100)
				if df is None or df.empty:
					return {"added": 0, "updated": 0}
				data = _convert_records_datetime(df.to_dict("records"))
				_known = {c.name for c in StockDividend.__table__.columns}
				_preprocess_records(data, date_fields=(
					"ann_date", "end_date", "record_date", "ex_date",
					"pay_date", "div_listdate", "imp_ann_date",
				), known_cols=_known)
				# 批次内按唯一键去重（Tushare 偶发返回重复行）
				data.sort(key=lambda d: d.get("ann_date") or date.min, reverse=True)
				data = list({(d.get("ts_code"), d.get("ann_date")): d for d in data}.values())
				added = await repo.bulk_upsert(data)
				return {"added": added, "updated": 0}
			except Exception as e:
				logger.error(f"[分红送股] {ts_code} 同步失败: {e}")
				return {"added": 0, "updated": 0, "failed": True}
		async with SyncTimingLogger(logger, "dividend", slow_threshold=30.0):
			logger.info(f"[分红送股] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "分红送股", task_id, user_id, _process_one, rate_key="dividend")
			if not result.get("cancelled"):
				result["message"] = "分红送股数据同步完成"
			return result
	async def _sync_financial_indicator(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步财务指标（fina_indicator 表，逐股拉取，默认近 365 天）。

		财务指标包含 ROE、ROA、毛利率、净利率等关键量化指标，
		按 (ts_code, end_date) 去重。

		Args:
			start_date: 起始日期（None → 365 天前）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		if not end_date: end_date = datetime.now().date()
		if not start_date: start_date = end_date - timedelta(days=365)
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added, records_updated, records_failed = 0, 0, 0
		# 获取 ORM 模型的已知列名，过滤 Tushare 返回的多余字段（如 dt_eps → eps 不匹配）
		known_cols = {c.name for c in StockFinaIndicator.__table__.columns}
		start_date_str = start_date.strftime('%Y%m%d') if start_date else ''
		end_date_str = end_date.strftime('%Y%m%d') if end_date else ''
		logger.info(f"[财务指标] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async def _process_one(session, ts_code):
			"""处理单只标的：HTTP拉取 > 日期转换 > upsert。"""
			repo = StockFinaIndicatorRepository(session)
			source = self.source_factory.get_source(DataSource.TUSHARE)
			try:
				df = await self._cancellable_run_in_executor(source.get_fina_indicator, symbol=ts_code, start_date=start_date_str, end_date=end_date_str)
				if df is None or df.empty:
					return {"added": 0, "updated": 0}
				data = _convert_records_datetime(df.to_dict("records"))
				_preprocess_records(data, date_fields=('ann_date', 'end_date'), known_cols=known_cols)
				seen = set()
				deduped = []
				for item in reversed(data):
					key = (item.get("ts_code"), item.get("end_date"))
					if key not in seen:
						seen.add(key)
						deduped.append(item)
				data = deduped
				added = await repo.bulk_upsert(data)
				return {"added": added, "updated": 0}
			except Exception as e:
				logger.error(f"[财务指标] {ts_code} 同步失败: {e}")
				return {"added": 0, "updated": 0, "failed": True}
		async with SyncTimingLogger(logger, "financial_indicator", slow_threshold=30.0):
			logger.info(f"[财务指标] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "财务指标", task_id, user_id, _process_one, rate_key="financial_indicator")
			if not result.get("cancelled"):
				result["message"] = "财务指标数据同步完成"
			return result
	async def _sync_audit_opinion(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步审计意见（audit_opinion 表，逐股拉取，默认近 5 年）。

		审计意见反映财报可信度（标准无保留/保留/否定/无法表示意见等），
		按 (ts_code, end_date) 去重。

		Args:
			start_date: 起始日期（None → 5 年前）
			end_date: 结束日期（None → 今天）
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		if not end_date: end_date = datetime.now().date()
		if not start_date: start_date = end_date - timedelta(days=365 * 5)
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added, records_updated, records_failed = 0, 0, 0
		# 获取 ORM 模型的已知列名，过滤 Tushare 返回的多余字段
		known_cols = {c.name for c in StockAuditOpinion.__table__.columns}
		start_date_str = start_date.strftime('%Y%m%d') if start_date else ''
		end_date_str = end_date.strftime('%Y%m%d') if end_date else ''
		logger.info(f"[审计意见] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async def _process_one(session, ts_code):
			"""处理单只标的：HTTP拉取 > 日期转换 > upsert。"""
			repo = StockAuditOpinionRepository(session)
			source = self.source_factory.get_source(DataSource.TUSHARE)
			try:
				df = await self._cancellable_run_in_executor(source.get_fina_audit, symbol=ts_code, start_date=start_date_str, end_date=end_date_str)
				if df is None or df.empty:
					return {"added": 0, "updated": 0}
				data = _convert_records_datetime(df.to_dict("records"))
				_preprocess_records(data, date_fields=('ann_date', 'end_date'))
				data.sort(key=lambda d: d.get('ann_date') or date.min, reverse=True)
				# 批次内按唯一键去重（Tushare 偶发返回重复行，PG ON CONFLICT 无法处理）
				data = list({(d.get('ts_code'), d.get('end_date')): d for d in data}.values())
				added = await repo.bulk_upsert(data)
				return {"added": added, "updated": 0}
			except Exception as e:
				logger.error(f"[审计意见] {ts_code} 同步失败: {e}")
				return {"added": 0, "updated": 0, "failed": True}
		async with SyncTimingLogger(logger, "audit_opinion", slow_threshold=30.0):
			logger.info(f"[审计意见] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "审计意见", task_id, user_id, _process_one, rate_key="audit_opinion")
			if not result.get("cancelled"):
				result["message"] = "审计意见数据同步完成"
			return result
	async def _sync_business_income(
			self,
			start_date: Optional[date],
			end_date: Optional[date],
			ts_codes: Optional[List[str]],
			task_id: str,
			user_id: Optional[str] = None,
			**_kwargs
	) -> Dict[str, Any]:
		"""同步主营业务构成（business_income 表，逐股拉取，按产品和地区两种维度）。

		对每只股票拉取两种维度：
		- ``P``（Product/产品）：按产品类别划分的营收构成
		- ``D``（District/地区）：按地理区域划分的营收构成
		按 (ts_code, end_date) 去重。

		Args:
			start_date: 未使用（全历史拉取）
			end_date: 未使用
			ts_codes: 股票代码列表（None → 全部活跃股票）
			task_id: 任务 ID
			user_id: 用户标识

		Returns:
			Dict: {records_added, records_updated, records_failed, total_items, message}"""
		if not ts_codes:
			stocks = await self.stock_basic_repo.get_active_stocks()
			ts_codes = [s.ts_code for s in stocks]
		source = self.source_factory.get_source(DataSource.TUSHARE)
		records_added, records_updated, records_failed = 0, 0, 0
		# 获取 ORM 模型的已知列名，过滤 Tushare 返回的多余字段
		known_cols = {c.name for c in StockBusinessIncome.__table__.columns}
		logger.info(f"[主营业务收入] 开始 {len(ts_codes)} 只标的, 预估 ~{len(ts_codes) * 0.3 / 60:.1f}min")
		async def _process_one(session, ts_code):
			"""处理单只标的：HTTP拉取 > 日期转换 > upsert。"""
			repo = StockBusinessIncomeRepository(session)
			source = self.source_factory.get_source(DataSource.TUSHARE)
			try:
				df = await self._cancellable_run_in_executor(source.get_fina_mainbz, symbol=ts_code, period="")
				if df is None or df.empty:
					return {"added": 0, "updated": 0}
				data = _convert_records_datetime(df.to_dict("records"))
				_preprocess_records(data, date_fields=('end_date',))
				added = await repo.bulk_upsert(data)
				return {"added": added, "updated": 0}
			except Exception as e:
				logger.error(f"[主营业务收入] {ts_code} 同步失败: {e}")
				return {"added": 0, "updated": 0, "failed": True}
		async with SyncTimingLogger(logger, "business_income", slow_threshold=30.0):
			logger.info(f"[主营业务收入] 并行同步 {len(ts_codes)} 只, 并发=8")
			result = await self._parallel_for_each(ts_codes, "主营业务收入", task_id, user_id, _process_one, rate_key="business_income")
			if not result.get("cancelled"):
				result["message"] = "主营业务收入数据同步完成"
			return result
	async def _update_progress(
			self,
			task_id: str,
			progress: Optional[float] = None,
			current_item: Optional[str] = None,
			user_id: Optional[str] = None
	):
		"""
		更新同步进度到缓存（Redis 或内存缓存）。

		**节流机制**：此方法在逐股同步的循环中被频繁调用（每只股票一次），
		为避免频繁写入缓存造成性能浪费，采用"最多每秒写入一次"的节流策略。
		例外：进度达到 100% 时**总是写入**，确保完成状态立即可见。

		缓存结构::

			{
				"progress": 45.2,          # 进度百分比（0-100）
				"current_task": "日行情: 2267/5000",
				"estimated_time_remaining": null,
				"_last_cache_write": 1717500000.123  # 上次写入时间戳（节流用）
			}

		Args:
			task_id: 任务 ID
			progress: 进度百分比（0-100），None 时不更新
			current_item: 当前处理项描述（如 "日行情: 2267/5000"）
			user_id: 用户标识（预留，用于权限控制）
		"""
		import time as _t

		progress_key = CacheKey.SYNC_PROGRESS.format(task_id=task_id)

		# ===== 节流：实例变量替代缓存读取，避免每次调用读缓存 =====
		now = _t.time()
		last_write = getattr(self, '_last_progress_write', 0.0)
		is_complete = (progress is not None and progress >= 100)
		if not is_complete and (now - last_write) < 1.0:
			return  # 1秒内不重复写，直接跳过（省一次 cache GET + JSON parse）
		self._last_progress_write = now

		# ===== 仅在需要写入时读取缓存 =====
		current_progress_raw = await self.cache.get(progress_key)
		if current_progress_raw:
			try:
				current_progress = json.loads(current_progress_raw)
			except (json.JSONDecodeError, TypeError):
				current_progress = {}
		else:
			current_progress = {}

		current_progress.setdefault("progress", 0)
		current_progress.setdefault("current_task", "")
		current_progress.setdefault("estimated_time_remaining", None)

		if progress is not None:
			current_progress["progress"] = progress
		if current_item:
			current_progress["current_task"] = current_item

		# 总是写入（已通过节流到达此处）
		await self.cache.set(progress_key, json.dumps(current_progress, default=str), ttl=3600)

	async def _publish_sync_event(
			self,
			event_type: str,
			task_id: str,
			data_type: Optional[str] = None,
			data_types: Optional[List[str]] = None,
			progress: Optional[float] = None,
			current_task: Optional[str] = None,
			result: Optional[Dict] = None,
			error: Optional[str] = None,
			user_id: Optional[str] = None
	):
		"""
		通过 EventEngine 发布同步事件，供前端实时展示和监控模块监听。

		支持的事件类型：
		- **started / batch_started**：同步开始 → 创建 ``DataSyncStartedEvent``
		- **progress**：进度更新 → 创建 ``DataSyncProgressEvent``
		- **completed / batch_completed**：同步完成 → 创建 ``DataSyncCompletedEvent``
		- **failed / batch_failed / cancelled**：失败/取消 → 创建 ``DataSyncFailedEvent``

		如果 ``event_engine`` 为 None（如命令行脚本场景），则静默跳过。

		Args:
			event_type: 事件类型（"started" / "progress" / "completed" / "failed" / "cancelled" 及其 batch 变体）
			task_id: 任务 ID
			data_type: 单个数据类型（单次同步场景）
			data_types: 多个数据类型（批量同步场景）
			progress: 进度百分比
			current_task: 当前任务描述
			result: 同步结果详情
			error: 错误信息
			user_id: 用户标识

		Note:
			``DataSyncStartedEvent`` 的 ``source`` 字段固定为 "tushare"，
			不再使用 ``event_kwargs`` 中的 "source"（"data_module"），避免参数冲突。
		"""
		if not self.event_engine:
			return

		# 基础事件参数（所有事件类型共享）
		event_kwargs = {
			"task_id": task_id,
			"user_id": user_id,
			"timestamp": datetime.now(),
			"source": "data_module"
		}

		if event_type in ("started", "batch_started"):
			sync_type = "batch" if event_type == "batch_started" else (data_type or "unknown")
			# 从 event_kwargs 中移除 source，避免与 DataSyncStartedEvent 的 source 参数冲突
			event_kwargs_copy = {k: v for k, v in event_kwargs.items() if k != "source"}
			event = DataSyncStartedEvent(
				sync_type=sync_type,
				source="tushare",
				params={
					"data_types": data_types,
					"data_type": data_type,
					**event_kwargs_copy
				}
			)
		elif event_type == "progress":
			event = DataSyncProgressEvent(
				sync_type=data_type or "unknown",
				progress=progress or 0,
				current_item=current_task or "",
				total_items=0,
				processed_items=0,
				**event_kwargs
			)
		elif event_type in ("completed", "batch_completed"):
			sync_type = "batch" if event_type == "batch_completed" else (data_type or "unknown")
			summary = result if result else {}
			if data_types:
				summary["data_types"] = data_types
			event = DataSyncCompletedEvent(
				sync_type=sync_type,
				record_count=result.get("total_items", 0) if result else 0,
				duration_seconds=0,
				success=True,
				summary=summary,
				**event_kwargs
			)
		elif event_type in ("failed", "batch_failed", "cancelled"):
			sync_type = "batch" if event_type == "batch_failed" else (data_type or "unknown")
			error_message = error or "未知错误"
			if event_type == "cancelled":
				error_message = "任务被用户取消"
			event = DataSyncFailedEvent(
				sync_type=sync_type,
				error_message=error_message,
				error_details=None,
				retry_count=0,
				**event_kwargs
			)
		else:
			logger.warning(f"未知的事件类型: {event_type}")
			return

		# 发布事件到事件引擎（异步，不阻塞当前流程）
		await self.event_engine.put(event)

	async def _clean_cache_after_sync(
			self,
			data_type: str,
			ts_codes: Optional[List[str]] = None
	):
		"""
		同步完成后清理相关缓存，确保下次查询获取最新数据。

		清理策略按数据类型分类：
		- **STOCK_LIST**：清理股票列表缓存（通配符匹配）
		- **行情类**（DAILY_QUOTES / MINUTE_QUOTES / ETF_DAILY / ETF_MINUTE）：
		  清理历史行情缓存，优先按具体 ts_code 清理（精确匹配），
		  无 ts_codes 时使用通配符全量清理。

		Args:
			data_type: 已同步的数据类型
			ts_codes: 涉及股票代码列表（用于精确缓存失效）
		"""
		cache_keys = []
		if data_type == DataType.STOCK_LIST:
			cache_keys.append(CacheKey.STOCK_LIST.format(hash="*"))
		elif data_type in (DataType.DAILY_QUOTES, DataType.MINUTE_QUOTES, DataType.ETF_DAILY, DataType.ETF_MINUTE):
			if ts_codes:
				for ts_code in ts_codes:
					cache_keys.append(CacheKey.HISTORICAL_QUOTES.format(
						ts_code=ts_code, start="*", end="*", freq="*", adj="*"
					))
			else:
				cache_keys.append(CacheKey.HISTORICAL_QUOTES.format(
					ts_code="*", start="*", end="*", freq="*", adj="*"
				))
		# 其他数据类型可根据需要添加缓存清理逻辑

		for pattern in cache_keys:
			await self.cache.delete_pattern(pattern)

	async def cleanup_old_tasks(self, days: int = 30) -> int:
		"""
		清理超过指定天数的旧同步任务记录。

		Args:
			days: 保留天数（默认 30 天）

		Returns:
			int: 清理的任务记录数

		Note:
			当前为 stub 实现（pass），实际清理逻辑由引擎层处理。
		"""
		# TODO: 实现旧任务清理逻辑
		pass

	async def get_recent_sync_tasks(
			self,
			user_id: Optional[str] = None,
			limit: int = 20
	) -> List[Dict[str, Any]]:
		"""
		获取最近的同步任务列表，按创建时间倒序。

		Args:
			user_id: 用户标识（None 返回全部用户的记录）
			limit: 返回的最大数量（默认 20）

		Returns:
			List[Dict]: 同步任务记录列表

		Note:
			当前为 stub 实现（pass），实际查询逻辑由引擎层处理。
		"""
		# TODO: 实现最近任务查询逻辑
		pass
