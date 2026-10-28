# -*- coding: utf-8 -*-
"""
quant_server/modules/data/__init__.py
数据模块 - 量化交易系统的数据管理模块
基于混合架构设计，提供数据同步、质量检查、因子研究等功能

数据模块 (modules/events/)
├── engines/     # 有状态引擎：管理数据同步、清洗、研究任务
├── services/    # 无状态服务：数据计算、验证、转换逻辑
└── events/      # 数据模块事件：同步完成、质量警报等

设计原则：
1. 单一职责：每个组件只负责一个明确的业务功能
2. 依赖注入：通过依赖注入获取共享基础设施
3. 事件驱动：模块间通过事件引擎通信
4. 统一异常处理：模块内错误不泄漏到外部
"""
import logging

logger = logging.getLogger(__name__)

from typing import Dict

# 导出常量
from modules.data.constants import (
	ModuleConfig,
	SyncStatus,
	SyncErrorCode,
	DataSource,
	DataType,
	MarketCode,
	StockStatus,
	QualityMetricCode,
	QualityLevelThreshold,
	FactorCategoryCode,
	StandardFactors,
	ErrorCode,
	DateTimeFormat,
	TradingTime,
	TableName,
	APIPath,
	CacheKey,
	EventType,
	Permission
)
# 导出Handlers
from modules.data.handlers import (
	get_stock_list,
	get_stock_detail,
	get_historical_quotes,
	batch_sync_data,
	quick_sync_data,
	get_sync_status,
	cancel_sync,
	get_data_quality,
	get_factor_data,
	research_factor,
	initialize_data_module,
	check_data_module_health
)
# 导出模型
from modules.data.models import (
	BaseSyncRequest,
	BatchSyncRequest,
	DataTypeInfo
)
# 导出Schema
from modules.data.schemas import (
	StockListRequest,
	StockListResponse,
	StockDetailRequest,
	StockDetailResponse,
	HistoricalQuotesRequest,
	HistoricalQuotesResponse,
	BatchSyncRequest,
	BatchSyncResponse,
	SyncStatusResponse,
	DataQualityRequest,
	DataQualityResponse,
	FactorRequest,
	FactorResponse,
	ResearchRequest,
	ResearchResponse
)
# 导出Services
from modules.data.services import (
	DataSyncService,
	DataQualityService,
	FactorResearchService,
	MarketDataService,
)


# 模块级引擎引用（由 initialize() 创建，供 handlers 等使用）
_sync_engine = None

# 模块级取消令牌注册表: task_id → asyncio.Event
import asyncio as _asyncio

logger = logging.getLogger(__name__)

_cancel_tokens: Dict[str, "_asyncio.Event"] = {}


def get_sync_engine():
	"""获取模块级数据同步引擎实例"""
	return _sync_engine


def create_cancel_token(task_id: str) -> "_asyncio.Event":
	"""为后台同步任务创建取消令牌"""
	token = _asyncio.Event()
	_cancel_tokens[task_id] = token
	return token


def signal_cancel(task_id: str) -> bool:
	"""向指定任务发送取消信号"""
	token = _cancel_tokens.get(task_id)
	if token and not token.is_set():
		token.set()
		return True
	return False


def cleanup_cancel_token(task_id: str):
	"""清理已完成的取消令牌"""
	_cancel_tokens.pop(task_id, None)


async def _single_day_coverage(
		session, table: str, day, bj_exclude: str = "",
		min_base: int = 1000, max_missing_ratio: float = 0.10,
):
	"""当日单日覆盖检查：返回 ``(缺失数, 基准数, 是否告警)``。

	基准 = **当日 `stock_daily` 行数**（非交易日 / 日线未同步时为 0）。
	告警条件：``基准 >= min_base`` **且** ``缺失占比 > max_missing_ratio``
	—— 基准过小（空跑/非交易日/日线没同步）时**不告警**，避免误报。

	`table` / `bj_exclude` 均为本模块内部常量（非用户输入），与同文件既有
	60 日门的 `.format()` 拼法一致。

	⚠️ 2026-10-12：`bj_exclude` 调用方现**两张表都传空串**。此前 moneyflow 传
	`NOT LIKE '%.BJ'`，依据是「Tushare 不含 920xxx.BJ」—— 该前提已实测证伪
	（`920000/920001/920002.BJ` 等对 20260930/20261008/20261012 各返回 1 行），
	而排除的后果是**掩盖真实的北交所缺口**（10-09/10-12 覆盖 26.5%）。

	⛔ 2026-10-12（`stock_moneyflow` 缺口）：本判据的存在理由是——原 60 日聚合门要求
	「缺失 ≥20 天」才告警，而当日实测只落 2378/5553（42.8%）却报「覆盖正常」，
	**单日大面积丢数要丢满约一个月才会被门发现**。单日门把它压到当天。
	"""
	from sqlalchemy import text as _text

	_r = await session.execute(
		_text(
			"SELECT count(*) FILTER (WHERE x.ts_code IS NULL), count(*) "
			"FROM stock_daily s "
			"LEFT JOIN {t} x ON x.ts_code = s.ts_code AND x.trade_date = s.trade_date "
			"WHERE s.trade_date = :d {bj}".format(t=table, bj=bj_exclude)
		),
		{"d": day},
	)
	missing, base = _r.fetchone() or (0, 0)
	alert = bool(base) and base >= min_base and missing > base * max_missing_ratio
	return missing, base, alert


# 模块初始化函数 - 符合主启动文件期望的接口
async def initialize (
		main_engine=None,
		event_engine=None,
		config=None
) -> bool:
	"""
	数据模块初始化函数

	Args:
		main_engine: 主引擎实例
		event_engine: 事件引擎实例
		config: 模块配置

	Returns:
		bool: 初始化是否成功
	"""

	global _sync_engine

	# 初始化变量
	success = False
	init_result = {}

	try:
		# 获取数据库会话 - 使用正确的上下文管理器方式
		if main_engine and hasattr(main_engine, 'get_async_session'):
			# 如果主引擎提供会话，使用主引擎的会话
			factory = main_engine.get_async_session()
			async with factory() as session:
				init_result = await initialize_data_module(session=session)
			success = init_result.get('status') != 'failed'
		else:
			# 使用共享层的会话管理器，通过上下文管理器正确获取
			from shared.database.session import get_session_manager

			session_manager = get_session_manager()
			async with session_manager.get_session() as session:
				# 调用原有的初始化函数
				init_result = await initialize_data_module(
					session=session
				)

				success = init_result.get('status') != 'failed'

		# 记录初始化结果
		if success:
			print(f"✅ 数据模块初始化成功: {init_result.get('message', '完成')}")
		else:
			print(f"⚠️  数据模块初始化警告: {init_result.get('message', '存在警告')}")

		# 创建并启动数据同步引擎
		if success:
			try:
				# 提取事件引擎（优先使用传入的，否则从 main_engine 获取）
				_evt_engine = event_engine
				if not _evt_engine and main_engine and hasattr(main_engine, 'event_engine'):
					_evt_engine = main_engine.event_engine

				from modules.data.engines.sync_engine import DataSyncEngine
				from core.engines.types.entities import EngineConfigEntity
				from core.engines.types.enums import EngineType

				sync_engine_config = EngineConfigEntity(
					name="data_sync_engine",
					engine_type=EngineType.DATA_SYNC,
					config={
						"max_concurrent_tasks": 3,
						"task_timeout_seconds": 3600,
						"default_data_sources": ["tushare"],
						"cleanup_interval_hours": 24,
					}
				)
				_sync_engine = DataSyncEngine(
					config=sync_engine_config,
					event_engine=_evt_engine
				)
				await _sync_engine.initialize()
				await _sync_engine.start()
				print(f"✅ 数据同步引擎已启动: {_sync_engine.config.name}")
			except Exception as engine_err:
				print(f"⚠️  数据同步引擎启动失败（不影响模块基础功能）: {engine_err}")
				_sync_engine = None

		# ===== 2026-08 C15：注册日终任务（依赖反转，替代 main_engine 内联）=====
		if main_engine and hasattr(main_engine, "register_daily_task"):
			async def _task_sync_daily(today):
				from shared.database.session import get_session_manager
				from modules.data.services.sync_service import DataSyncService
				from modules.data.constants import DataType
				sm = get_session_manager()
				sync_ok = True
				async with sm.get_session() as session:
					svc = DataSyncService(session=session)
					_daily_types = (
						DataType.DAILY_QUOTES, DataType.DAILY_BASIC, DataType.ADJ_FACTOR,
						DataType.ETF_DAILY, DataType.FUND_ADJ_FACTOR,
						DataType.INDEX_DAILY, DataType.INDEX_DAILYBASIC,
						DataType.DAILY_LIMIT, DataType.SUSPEND,
						# 2026-08 修复（Fix3）：补齐此前未纳入日终的类型。
						# moneyflow 曾停更 08-17、stock_hsgt 停更 06-25（不在日终列表 → 无自愈）。
						# moneyflow 逐股约 11min/日；hsgt/hsgt_flow/sw_daily 均为轻量全量。
						DataType.MONEYFLOW, DataType.STOCK_HSGT,
						DataType.MONEYFLOW_HSGT, DataType.INDEX_SW_DAILY,
					)
					import asyncio as _asyncio
					_sem = _asyncio.Semaphore(3)
					async def _sync_one(dt):
						async with _sem:
							try:
								# 2026-08 修复：每个同步用独立 session（gather 并发共享 session
								# 报 "concurrent operations not permitted" → etf_daily 同步失败）
								async with sm.get_session() as _sess:
									_svc = DataSyncService(session=_sess)
									result = await _svc.sync_market_data(dt, start_date=None, end_date=today)
								logger.info("日终同步 %s 完成: records=%s",
									dt.value,
									result.get("records_processed", 0) if isinstance(result, dict) else "?",
								)
								return True
							except Exception as sync_err:
								logger.error("日终同步 %s 失败: %s", dt.value, sync_err)
								return False
					_sync_results = await _asyncio.gather(
						*[_sync_one(dt) for dt in _daily_types], return_exceptions=True,
					)
					sync_ok = all(r is True for r in _sync_results)
				if not sync_ok:
					logger.warning("日终数据同步部分失败，仍尝试驱动策略")

			async def _task_coverage_validate(today):
				"""覆盖度校验（2026-08 Fix7 / 2026-10-12 加固）：以 stock_daily 为日期基准，
				对关键日频表做**两道**覆盖检查（均为纯可观测，**不阻断策略驱动**）：

				① **近 60 日聚合门**（原判据）：抓「慢性缺失」。逐股比对 60 日内
				   `stock_daily` 与目标表的天数，缺失 ≥20 天且覆盖率 <90% 才告警。
				② **当日单日门**（新增）：抓「单日大面积丢数」。原判据要求「缺失
				   ≥20 天」才响 —— 实测 `stock_moneyflow` 2026-10-12 只落
				   **2378/5553（42.8%）**，门仍报「覆盖正常」，缺口要丢满约一个月
				   才会触发。单日门按当日缺失占比 >10% 即告警。

				背景：max(trade_date) 无法发现内部空洞（两端有数据、中间缺失），
				唯有与完整日线基准对比覆盖度才能发现。此前 stock_daily_basic 4 年
				深市主板空洞即因此漏检。
				"""
				try:
					from shared.database.session import get_session_manager
					from sqlalchemy import text as _text
					from datetime import timedelta as _td
					sm = get_session_manager()
					_ws = today - _td(days=60)
					# ⚠️ 2026-10-12 订正：原注释称「Tushare 资金流向接口**不含** 920xxx.BJ
					#    （数据源限制）」→ 故 moneyflow 曾排除北交所。**该前提已被实测证伪**：
					#    920000/920001/920002/920003/920005.BJ 对 20260930 / 20261008 /
					#    20261012 **各返回 1 行**。排除的后果是**掩盖真实的北交所缺口**：
					#    实测 2026-10-09 / 10-12 北交所 344 只基准里缺 253 只（覆盖率 26.5%），
					#    而 09-30 / 10-08 均为 100% —— 缺口起始点与主板一致，同一根因。
					#    ⇒ 两张表都不再排除。
					_bj_exclude = {"stock_daily_basic": "", "stock_moneyflow": ""}
					async with sm.get_session() as _s:
						for _tbl in ("stock_daily_basic", "stock_moneyflow"):
							_r = await _s.execute(_text(
								"SELECT s.ts_code FROM stock_daily s "
								"LEFT JOIN {t} x ON x.ts_code = s.ts_code AND x.trade_date = s.trade_date "
								"WHERE s.trade_date >= :ws {bj} GROUP BY s.ts_code "
								"HAVING COUNT(DISTINCT x.trade_date) < COUNT(DISTINCT s.trade_date) * 0.9 "
								"AND COUNT(DISTINCT s.trade_date) - COUNT(DISTINCT x.trade_date) >= 20".format(
									t=_tbl, bj=_bj_exclude[_tbl])),
								{"ws": _ws})
							_n = len(_r.fetchall())
							if _n > 0:
								logger.warning(
									"覆盖度校验: %s 近60日 %d 只股票覆盖不足"
									"（建议 scripts/data/backfill_coverage_gaps.py 回填）", _tbl, _n)
							else:
								logger.info("覆盖度校验: %s 近60日覆盖正常", _tbl)

							# ② 当日单日门（2026-10-12 新增）：抓「单日大面积丢数」。
							#    原 60 日聚合门要求「缺失 >= 20 天」才告警 —— 实测
							#    stock_moneyflow 2026-10-12 只落 2378/5553（42.8%），
							#    门仍报「覆盖正常」，缺口要丢满约一个月才会响。
							_missing, _base, _alert = await _single_day_coverage(
								_s, _tbl, today, _bj_exclude[_tbl])
							if _alert:
								logger.warning(
									"覆盖度校验: %s 当日(%s)覆盖不足 —— %d/%d 只缺失"
									"（当日覆盖率 %.1f%%）；该表当日数据应视为不完整，"
									"需当日回填后再复盘/消费。回填（⚠️ 必须带 --min-missing 1，"
									"否则默认阈值 20 天会让新缺口再藏一个月）："
									"scripts/data/backfill_coverage_gaps.py --table %s "
									"--start <近端交易日> --min-missing 1",
									_tbl, today, _missing, _base,
									(_base - _missing) / _base * 100,
									{"stock_daily_basic": "daily_basic",
									 "stock_moneyflow": "moneyflow"}.get(_tbl, _tbl))
							else:
								logger.info(
									"覆盖度校验: %s 当日(%s)覆盖正常（缺失 %d/%d）",
									_tbl, today, _missing, _base)
				except Exception as _ce:
					logger.warning("覆盖度校验异常（非致命）: %s", _ce)

			async def _task_market_state(today):
				try:
					from modules.data.services.market_state_classifier import (
						classify_and_populate,
					)
					await classify_and_populate()
				except Exception as msc_err:
					logger.warning("market_state_daily 更新失败（非致命）: %s", msc_err)

			async def _task_etf_factor(today):
				try:
					from modules.data.services.etf_factor_daily import (
						compute_etf_factors_daily,
					)
					factor_result = await compute_etf_factors_daily(trade_date=today)
					logger.info("日终 ETF 因子计算完成: %s", factor_result.get("message", "?"))
				except Exception as factor_err:
					logger.warning("日终 ETF 因子计算失败（非致命）: %s", factor_err)

			await main_engine.register_daily_task("sync_daily", _task_sync_daily, phase="pre_gate", order=10)
			await main_engine.register_daily_task("coverage_validate", _task_coverage_validate, phase="pre_gate", order=15)
			await main_engine.register_daily_task("market_state_update", _task_market_state, phase="pre_gate", order=20)
			await main_engine.register_daily_task("etf_factor", _task_etf_factor, phase="pre_gate", order=30)

			# ---- 数据质量门（2026-09-19 新增）：接入 `_data_integrity_gate` ----
			async def _gate_quality_check(latest_trade_date):
				"""数据质量门 —— **仅 critical 级阻断**（2026-09-19 决策）。

				对实盘依赖的关键表跑质检，只在三种情况返回 ok=False：
				  1. 质检本身失败（**无法确认**数据可用）
				  2. 关键表记录数为 0（策略无数据可用）
				  3. 存在 `severity == 'critical'` 的 issue（如价格列 NULL）
				`high` / `medium` 只记日志、**不阻断** —— 避免新接入的门误停实盘。

				另：结果落库到 `data_quality_checks`（供前端与事后追溯）。
				"""
				# 实盘链路直接依赖的关键表（3 个策略 + regime 判定）
				_CRITICAL = ("daily_quotes", "etf_daily", "index_daily", "daily_basic")
				_crit, _warn = [], []
				from modules.data.services.quality_service import DataQualityService
				from shared.database.session import get_session_manager
				_sm = get_session_manager()
				for _dt in _CRITICAL:
					try:
						async with _sm.get_session() as _qs:
							_svc = DataQualityService(_qs)
							_rep = await _svc.check_data_quality(_dt)
							if _rep.get("skipped"):
								continue
							if not _rep.get("success"):
								_crit.append(f"{_dt}: 质检失败({_rep.get('error')})")
								await _qs.rollback()
								continue
							_m = _rep.get("result") or {}
							_issues = _m.get("issues") or []
							for _it in _issues:
								_sev = _it.get("severity")
								_desc = f"{_dt}: {_it.get('issue_type')} {_it.get('description', '')}"
								if _sev == "critical":
									_crit.append(_desc)
								else:
									_warn.append(f"[{_sev}] {_desc}")
							if not int(_m.get("total_records") or 0):
								_crit.append(f"{_dt}: 记录数为 0（无数据可用）")
							await _qs.commit()
					except Exception as _qe:
						_crit.append(f"{_dt}: 质检异常 {type(_qe).__name__}: {_qe}")
				for _w in _warn:
					logger.warning("数据质量门（不阻断）: %s", _w)
				if _crit:
					return False, "；".join(_crit[:5])
				return True, f"关键表质检通过（{len(_CRITICAL)} 类，无 critical）"

			if hasattr(main_engine, "register_gate_check"):
				main_engine.register_gate_check("data_quality_gate", _gate_quality_check)
		return success

	except Exception as e:
		print(f"❌ 数据模块初始化失败: {str(e)}")
		return False

async def shutdown(main_engine=None) -> None:
	"""数据模块关闭函数"""
	import logging
	logging.getLogger(__name__).info("数据模块已关闭")


# 模块元数据
__version__ = "1.0.0"
__author__ = "量化交易系统团队"
__description__ = "量化交易系统数据管理模块"
__all__ = [
	# 常量
	"ModuleConfig", "SyncStatus", "SyncErrorCode", "DataSource", "DataType",
	"MarketCode", "StockStatus", "QualityMetricCode", "QualityLevelThreshold",
	"FactorCategoryCode", "StandardFactors", "ErrorCode", "DateTimeFormat",
	"TradingTime", "TableName", "APIPath", "CacheKey", "EventType", "Permission",

	# 模型
	"BaseSyncRequest", "BatchSyncRequest", "DataTypeInfo",

	# Schema
	"StockListRequest", "StockListResponse", "StockDetailRequest", "StockDetailResponse",
	"HistoricalQuotesRequest", "HistoricalQuotesResponse", "BatchSyncRequest", "BatchSyncResponse",
	"SyncStatusResponse", "DataQualityRequest", "DataQualityResponse", "FactorRequest",
	"FactorResponse", "ResearchRequest", "ResearchResponse",

	# Handlers
	"get_stock_list", "get_stock_detail", "get_historical_quotes",
	"batch_sync_data", "quick_sync_data", "get_sync_status", "cancel_sync",
	"get_data_quality", "get_factor_data", "research_factor", "initialize_data_module",
	"check_data_module_health",

	# Services
"DataSyncService", "DataQualityService", "FactorResearchService", "MarketDataService",

	# 引擎访问器
	"get_sync_engine",

	# 取消令牌管理
	"create_cancel_token",
	"signal_cancel",
	"cleanup_cancel_token",

	# 模块初始化函数
	"initialize",
	"shutdown"
]