# -*- coding: utf-8 -*-
"""
DataFeedEngine — 数据推送引擎

从数据库加载行情数据并逐日推送给策略引擎。
设计参照: Backtrader DataFeeds + VN.PY BarGenerator + Zipline DataPortal

职责:
- 从 stock_daily / stock_adjusted_prices / factor_data 等超表加载历史数据
- 按 trade_date 全局排序（以交易日历为时间轴）
- 逐日生成 BarData 列表，推送给 StrategyManager
- 支持增量更新（实盘模式）和批量加载（回测模式）

v1.0: 初始实现 — 回测模式全量加载
"""
import logging
from datetime import date, datetime
from typing import List, Dict, Optional, AsyncIterator, Tuple, Any

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from core.engines.base.engine_base import EngineBase, EngineConfigEntity
from core.engines.types.entities import BarData
from core.engines.types.enums import EngineType

logger = logging.getLogger(__name__)


class DataFeedEngine(EngineBase):
    """
    数据推送引擎 — 从数据库加载行情数据并逐日推送给策略引擎

    参照: Backtrader DataFeeds + VN.PY BarGenerator

    使用方式:
        engine = DataFeedEngine(db_session)
        df = await engine.load_historical_data(
            symbols=["000001.SZ", "600519.SH"],
            start_date="2024-01-01",
            end_date="2024-12-31",
        )
        async for trade_date, bars in engine.iter_bars(df):
            signals = await strategy_manager.handle_bar_batch(trade_date, bars)
    """

    def __init__(
        self,
        db: AsyncSession,
        event_engine=None,
        adj_type: str = "qfq",
    ):
        """
        初始化 DataFeedEngine

        Args:
            db: 异步数据库会话
            event_engine: 事件引擎（可选）
            adj_type: 复权类型 — "qfq"(前复权), "hfq"(后复权), "none"(不复权)
        """
        super().__init__(
            EngineConfigEntity(
                name="DataFeedEngine",
                engine_type=EngineType.DATA_FEED.value
                if hasattr(EngineType, "DATA_FEED")
                else "data_feed",
            ),
            event_engine=event_engine,
        )

        self.db = db
        self.adj_type = adj_type

        # Lazy-loaded repositories
        self._stock_repo = None
        self._daily_repo = None
        self._calendar_repo = None
        self._factor_repo = None
        self._adj_price_repo = None
        self._etf_daily_repo = None
        self._etf_repo = None
        self._sw_index_repo = None

    @staticmethod
    def _is_etf(ts_code: str) -> bool:
        """v2.4: 根据代码规则判断是否为 ETF

        A 股 ETF 代码规则:
        - 上交所 (SH):
          - 51xxxx (510050, 510300, 512880 等 — 股票/行业/跨境/商品 ETF)
          - 56xxxx (561120, 561170 等 — 行业 ETF)
          - 58xxxx (588000, 588080 等 — 科创 ETF)
        - 深交所 (SZ):
          - 159xxx (159915, 159919 等) — 各类 ETF
          - 16xxxx — LOF/ETF
        """
        code = ts_code.split(".")[0] if "." in ts_code else ts_code
        return (
            code.startswith("51")
            or code.startswith("159")
            or code.startswith("16")
            or code.startswith("56")
            or code.startswith("58")
        )

    @staticmethod
    def _is_sw_index(ts_code: str) -> bool:
        """v3.0: 判断是否为申万行业指数代码

        申万行业指数代码规则:
        - L1: 801XXX.SI (如 801780.SI = 银行)
        - L2: 801XXX.SI
        - L3: 850XXX.SI

        v2.6: .WI 后缀（如 881001.WI 万得全A）不走 SW 指数路径，
        应作为普通指数从 index_daily 加载。
        """
        return ts_code.endswith(".SI")

    @staticmethod
    def _is_general_index(ts_code: str) -> bool:
        """v2.6: 判断是否为普通指数（非 SW 行业指数，非 ETF）

        如 881001.WI (万得全A) — .WI 后缀，数据在 index_daily 表
        """
        return ts_code.endswith(".WI")

    @property
    def daily_repo(self):
        if self._daily_repo is None:
            from shared.database.repositories.market.quote.stock_daily_repo import (
                StockDailyRepository,
            )
            self._daily_repo = StockDailyRepository(self.db)
        return self._daily_repo

    @property
    def calendar_repo(self):
        if self._calendar_repo is None:
            from shared.database.repositories.market.reference.trade_calendar_repo import (
                TradeCalendarRepository,
            )
            self._calendar_repo = TradeCalendarRepository(self.db)
        return self._calendar_repo

    @property
    def factor_repo(self):
        if self._factor_repo is None:
            from shared.database.repositories.analysis.factor.factor_data_repo import (
                FactorDataRepository,
            )
            self._factor_repo = FactorDataRepository(self.db)
        return self._factor_repo

    @property
    def adj_price_repo(self):
        if self._adj_price_repo is None:
            from shared.database.repositories.market.quote.stock_adjusted_price_repo import (
                StockAdjustedPriceRepository,
            )
            self._adj_price_repo = StockAdjustedPriceRepository(self.db)
        return self._adj_price_repo

    @property
    def etf_daily_repo(self):
        if self._etf_daily_repo is None:
            from shared.database.repositories.market.quote.etf_daily_repo import (
                EtfDailyRepository,
            )
            self._etf_daily_repo = EtfDailyRepository(self.db)
        return self._etf_daily_repo

    @property
    def etf_repo(self):
        if self._etf_repo is None:
            from shared.database.repositories.market.basic.etf_repo import (
                ETFRepository,
            )
            self._etf_repo = ETFRepository(self.db)
        return self._etf_repo

    @property
    def sw_index_repo(self):
        """v3.0: 申万行业日线数据仓库"""
        if self._sw_index_repo is None:
            from shared.database.repositories.market.fundamental.index_sw_daily_repo import (
                IndexSwDailyRepository,
            )
            self._sw_index_repo = IndexSwDailyRepository(self.db)
        return self._sw_index_repo

    # ---- 核心接口 ----

    async def load_historical_data(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        fields: List[str] = None,
        include_factors: bool = False,
        factor_names: List[str] = None,
    ) -> pd.DataFrame:
        """
        从 stock_daily 超表批量加载历史数据

        参照: Backtrader PandasData — 统一 DataFrame 接口

        Args:
            symbols: 股票代码列表，如 ["000001.SZ", "600519.SH"]
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            fields: 需要的字段，默认 ['open','high','low','close','volume','amount']
            include_factors: 是否同时加载因子数据
            factor_names: 因子名称列表，如 ["momentum_20", "volume_ratio"]

        Returns:
            DataFrame，列: ts_code, trade_date, open, high, low, close, volume, amount, ...
            按 trade_date ASC, ts_code ASC 排序
        """
        if fields is None:
            fields = ["open", "high", "low", "close", "volume", "amount"]

        # 将字符串日期转为 date 对象，避免 PostgreSQL date >= varchar 类型错误
        from datetime import date as _date_class

        if isinstance(start_date, str):
            start_date = _date_class.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = _date_class.fromisoformat(end_date)

        # 拆分标的类型（v2.6: 增加 .WI 等普通指数路由）
        idx_symbols = [s for s in symbols if self._is_general_index(s)]
        stock_symbols = [s for s in symbols if not self._is_etf(s) and not self._is_sw_index(s) and not self._is_general_index(s)]
        etf_symbols = [s for s in symbols if self._is_etf(s)]
        sw_symbols = [s for s in symbols if self._is_sw_index(s)]

        logger.info(
            f"开始加载历史数据: {len(stock_symbols)} 只股票 + {len(etf_symbols)} 只 ETF"
            f" + {len(sw_symbols)} 个行业指数"
            f" + {len(idx_symbols)} 个普通指数, "
            f"{start_date} ~ {end_date}, 复权={self.adj_type}"
        )

        all_records: List[Dict[str, Any]] = []

        # ---- 股票：使用复权价格 ----
        if stock_symbols:
            if self.adj_type in ("qfq", "hfq"):
                try:
                    records = await self._load_adj_batch(
                        symbols=stock_symbols,
                        start_date=start_date,
                        end_date=end_date,
                        adj_type=self.adj_type,
                    )
                    for r in records:
                        all_records.append({
                            "ts_code": r.ts_code,
                            "trade_date": (
                                r.trade_date.date()
                                if hasattr(r.trade_date, "date")
                                else r.trade_date
                            ),
                            "open": float(r.open) if r.open else None,
                            "high": float(r.high) if r.high else None,
                            "low": float(r.low) if r.low else None,
                            "close": float(r.close) if r.close else None,
                            "volume": float(r.vol) if r.vol else 0.0,
                            "amount": float(r.amount) if r.amount else 0.0,
                        })
                except Exception as e:
                    logger.warning(f"批量加载复权价格失败: {e}")

            # 回退到不复权数据
            if not all_records or not any(
                r.get("ts_code", "").startswith(tuple(stock_symbols[:1]))
                for r in all_records[-10:] if all_records
            ):
                logger.info("stock_adjusted_prices 表为空，使用 stock_daily + stock_adj_factor 在线前复权")
                try:
                    records = await self._load_daily_batch(
                        symbols=stock_symbols,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    # 在线加载复权因子并计算复权价格（替代缺失的预计算表）
                    adj_factors: Dict[str, Dict[date, float]] = {}
                    try:
                        from shared.database.repositories.market.quote.stock_adj_factor_repo import (
                            StockAdjFactorRepository,
                        )
                        adj_repo = StockAdjFactorRepository(self.db)
                        adj_factors = await adj_repo.get_batch_by_date_range(
                            symbols=stock_symbols,
                            start_date=start_date,
                            end_date=end_date,
                        )
                        if adj_factors:
                            logger.info(f"在线复权: {len(adj_factors)}/ {len(stock_symbols)} 只股票有复权因子")
                    except Exception:
                        logger.debug("复权因子加载失败，使用原始价格")

                    for r in records:
                        price_open = float(r.open) if r.open else None
                        price_high = float(r.high) if r.high else None
                        price_low = float(r.low) if r.low else None
                        price_close = float(r.close) if r.close else None

                        # 应用复权因子（前复权：价格 × adj_factor）
                        if adj_factors and r.ts_code in adj_factors:
                            af_map = adj_factors[r.ts_code]
                            td = r.trade_date.date() if hasattr(r.trade_date, "date") else r.trade_date
                            # 用当日的复权因子
                            af = af_map.get(td)
                            # 如果当日没有，用最近的前一个日期
                            if af is None:
                                _dates = [d for d in sorted(af_map.keys()) if d <= td]
                                if _dates:
                                    af = af_map[_dates[-1]]
                            if af is not None and af > 0:
                                if price_open: price_open *= af
                                if price_high: price_high *= af
                                if price_low:  price_low  *= af
                                if price_close: price_close *= af

                        all_records.append({
                            "ts_code": r.ts_code,
                            "trade_date": (
                                r.trade_date.date()
                                if hasattr(r.trade_date, "date")
                                else r.trade_date
                            ),
                            "open": price_open,
                            "high": price_high,
                            "low": price_low,
                            "close": price_close,
                            "volume": float(r.vol) if r.vol else 0.0,
                            "amount": float(r.amount) if r.amount else 0.0,
                        })
                except Exception as e:
                    logger.warning(f"批量加载日线数据失败: {e}")

            # v2.6: stock_daily 未命中的标的 → 尝试 index_daily（如 000300.SH 沪深300）
            _stock_found = {r.get("ts_code", "") for r in all_records if r.get("ts_code", "")}
            _stock_missed = [s for s in stock_symbols if s not in _stock_found]
            if _stock_missed:
                try:
                    idx_fallback = await self._load_index_batch(
                        symbols=_stock_missed,
                        start_date=start_date,
                        end_date=end_date,
                    )
                    if idx_fallback:
                        all_records.extend(idx_fallback)
                        _fb_codes = {r["ts_code"] for r in idx_fallback}
                        logger.info(
                            f"index_daily 兜底加载: {len(idx_fallback)} 条 / "
                            f"{len(_fb_codes)} 个指数 ({', '.join(sorted(_fb_codes))})"
                        )
                except Exception as e:
                    logger.debug(f"index_daily 兜底加载失败: {e}")

        # ---- ETF：使用 etf_daily JOIN fund_adj_factor 计算复权价格 ----
        if etf_symbols:
            try:
                etf_records = await self._load_etf_batch(
                    symbols=etf_symbols,
                    start_date=start_date,
                    end_date=end_date,
                )
                all_records.extend(etf_records)
                # v2.5: 诊断日志 — 按标的统计，标记空数据
                _etf_by_code: Dict[str, int] = {}
                for r in etf_records:
                    _etf_by_code[r["ts_code"]] = _etf_by_code.get(r["ts_code"], 0) + 1
                _etf_empty = [s for s in etf_symbols if s not in _etf_by_code]
                logger.info(
                    f"ETF 数据加载: {len(etf_records)} 条 / {len(etf_symbols)} 只, "
                    f"有数据={len(_etf_by_code)} 只, 无数据={len(_etf_empty)} 只"
                )
                if _etf_empty:
                    logger.warning(
                        f"ETF 无数据 ({start_date}~{end_date}): "
                        f"{', '.join(_etf_empty[:10])}"
                        f"{' ...' if len(_etf_empty) > 10 else ''}"
                    )
            except Exception as e:
                logger.warning(f"批量加载 ETF 数据失败: {e}")

        # ---- 申万行业指数：从 index_sw_daily 加载 ----
        if sw_symbols:
            try:
                sw_records = await self._load_sw_index_batch(
                    symbols=sw_symbols,
                    start_date=start_date,
                    end_date=end_date,
                )
                all_records.extend(sw_records)
                # v2.5: 诊断日志 — 按行业统计
                _sw_by_code: Dict[str, int] = {}
                for r in sw_records:
                    _sw_by_code[r["ts_code"]] = _sw_by_code.get(r["ts_code"], 0) + 1
                _sw_empty = [s for s in sw_symbols if s not in _sw_by_code]
                logger.info(
                    f"SW 行业指数数据加载: {len(sw_records)} 条 / {len(sw_symbols)} 个行业, "
                    f"有数据={len(_sw_by_code)} 个, 无数据={len(_sw_empty)} 个"
                )
                if _sw_empty:
                    logger.warning(
                        f"SW 行业指数无数据 ({start_date}~{end_date}): "
                        f"{', '.join(_sw_empty[:10])}"
                        f"{' ...' if len(_sw_empty) > 10 else ''}"
                    )
            except Exception as e:
                logger.warning(f"批量加载申万行业指数数据失败: {e}")

        # ---- v2.6: 普通指数（如 881001.WI）从 index_daily 加载 ----
        if idx_symbols:
            try:
                idx_records = await self._load_index_batch(
                    symbols=idx_symbols,
                    start_date=start_date,
                    end_date=end_date,
                )
                all_records.extend(idx_records)
                _idx_by_code: Dict[str, int] = {}
                for r in idx_records:
                    _idx_by_code[r["ts_code"]] = _idx_by_code.get(r["ts_code"], 0) + 1
                _idx_empty = [s for s in idx_symbols if s not in _idx_by_code]
                logger.info(
                    f"普通指数数据加载: {len(idx_records)} 条 / {len(idx_symbols)} 个, "
                    f"有数据={len(_idx_by_code)} 个, 无数据={len(_idx_empty)} 个"
                )
                if _idx_empty:
                    logger.warning(
                        f"普通指数无数据 ({start_date}~{end_date}): "
                        f"{', '.join(_idx_empty)}"
                    )
            except Exception as e:
                logger.warning(f"批量加载普通指数数据失败: {e}")

        if not all_records:
            logger.warning(f"未加载到任何数据: {len(symbols)} 只股票, {start_date}~{end_date}")
            return pd.DataFrame(columns=["ts_code", "trade_date"] + fields)

        df = pd.DataFrame(all_records)

        # 过滤掉空值行
        df = df.dropna(subset=["open", "high", "low", "close"])

        # 排序
        df = df.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)

        # 可选: 注入因子数据
        if include_factors and factor_names:
            df = await self._inject_factors(df, factor_names)

        logger.info(
            f"历史数据加载完成: {len(df)} 行, "
            f"{df['ts_code'].nunique()} 只股票, "
            f"{df['trade_date'].nunique()} 个交易日"
        )

        return df

    async def iter_bars(
        self,
        df: pd.DataFrame,
    ) -> AsyncIterator[Tuple[date, List[BarData]]]:
        """
        按交易日分组迭代 BarData

        参照: Zipline DataPortal.get_spot_value() — 按时间切片

        Args:
            df: load_historical_data() 返回的 DataFrame

        Yields:
            (trade_date, [BarData_for_symbol1, BarData_for_symbol2, ...])
        """
        if df.empty:
            logger.warning("DataFrame 为空，无数据可迭代")
            return

        # 按 trade_date 分组
        grouped = df.groupby("trade_date")

        trade_dates = sorted(df["trade_date"].unique())
        total_days = len(trade_dates)

        for i, trade_date in enumerate(trade_dates):
            day_df = grouped.get_group(trade_date)

            bars = []
            for _, row in day_df.iterrows():
                try:
                    bar = BarData(
                        ts_code=str(row["ts_code"]),
                        period="daily",
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row.get("volume", 0)),
                        amount=float(row.get("amount", 0)),
                        trade_date=trade_date,
                        # v2.5: SW 行业指数扩展字段（ETF row 中这些列为 NaN → 默认值 0.0/""）
                        name=str(row.get("name", "") or ""),
                        pe=float(row.get("pe", 0) or 0),
                        pb=float(row.get("pb", 0) or 0),
                        float_mv=float(row.get("float_mv", 0) or 0),
                        pct_chg=float(row.get("pct_chg", 0) or 0),
                    )
                    bars.append(bar)
                except Exception as e:
                    logger.warning(
                        f"构造 BarData 失败: {row.get('ts_code')} @ {trade_date}: {e}"
                    )

            if bars:
                yield trade_date, bars

            # 进度日志（每 20 个交易日或最后一天）
            if (i + 1) % 20 == 0 or i == total_days - 1:
                logger.debug(
                    f"DataFeed 进度: {i + 1}/{total_days} 交易日"
                )

    async def run_backtest_feed(
        self,
        strategy_manager: "StrategyManager",
        symbols: List[str],
        start_date: str,
        end_date: str,
        include_factors: bool = False,
        factor_names: List[str] = None,
    ) -> List[Dict]:
        """
        回测模式：加载全量数据 → 逐日推送 → 收集信号

        这是 DataFeedEngine 的核心方法，驱动整个回测循环。

        Args:
            strategy_manager: StrategyManager 实例
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            include_factors: 是否注入因子数据
            factor_names: 因子名称列表

        Returns:
            所有信号的汇总列表 [{signal}, ...]
        """
        logger.info(
            f"开始回测数据推送: {len(symbols)} 只股票, "
            f"{start_date} ~ {end_date}"
        )

        # 1. 加载历史数据
        df = await self.load_historical_data(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            include_factors=include_factors,
            factor_names=factor_names,
        )

        if df.empty:
            logger.warning("回测数据为空，无法执行")
            return []

        # 2. 按交易日过滤（只推送真实交易日）
        trading_dates = set()
        try:
            cal_dates = await self.calendar_repo.get_trade_dates(
                exchange="SSE",
                start_date=start_date,
                end_date=end_date,
                only_open=True,
            )
            trading_dates = set(
                d.date() if hasattr(d, "date") else d for d in cal_dates
            )
        except Exception as e:
            logger.warning(f"获取交易日历失败，使用数据中的全部日期: {e}")
            trading_dates = set(df["trade_date"].unique())

        # 3. 逐日推送
        all_signals = []
        day_count = 0

        async for trade_date, bars in self.iter_bars(df):
            # 跳过非交易日（如果交易日历可用）
            if trading_dates and trade_date not in trading_dates:
                continue

            day_count += 1

            # 推送给策略管理器
            try:
                signals = await strategy_manager.handle_bar_batch(
                    trade_date=trade_date,
                    bars=bars,
                )
                if signals:
                    all_signals.extend(signals)
            except Exception as e:
                logger.error(f"策略处理失败 @ {trade_date}: {e}")

        logger.info(
            f"回测数据推送完成: {day_count} 个交易日, "
            f"共生成 {len(all_signals)} 个信号"
        )

        return all_signals

    async def get_available_symbols(
        self,
        start_date: str,
        end_date: str,
        min_days: int = 200,
    ) -> List[str]:
        """
        获取指定日期范围内有足够数据的股票列表

        Args:
            start_date: 开始日期
            end_date: 结束日期
            min_days: 最少需要的交易日数

        Returns:
            股票代码列表
        """
        # 使用 StockBasicRepository 获取活跃股票
        from shared.database.repositories.market.basic.stock_repo import (
            StockBasicRepository,
        )
        stock_repo = StockBasicRepository(self.db)

        try:
            active_stocks = await stock_repo.get_active_stocks()
            return [s.ts_code for s in active_stocks if s.ts_code]
        except Exception as e:
            logger.error(f"获取可用股票列表失败: {e}")
            return []

    # ---- 私有方法 ----

    async def _inject_factors(
        self,
        df: pd.DataFrame,
        factor_names: List[str],
    ) -> pd.DataFrame:
        """
        将因子数据注入到主 DataFrame 中

        Args:
            df: 主 price DataFrame
            factor_names: 因子名称列表

        Returns:
            注入因子列后的 DataFrame
        """
        for factor_name in factor_names:
            try:
                factor_col = f"factor_{factor_name}"
                df[factor_col] = None

                for ts_code in df["ts_code"].unique():
                    stock_mask = df["ts_code"] == ts_code
                    stock_dates = df.loc[stock_mask, "trade_date"]

                    if stock_dates.empty:
                        continue

                    min_date = stock_dates.min()
                    max_date = stock_dates.max()

                    factor_records = await self.factor_repo.get_stock_factor_history(
                        factor_name=factor_name,
                        ts_code=ts_code,
                        start_date=min_date,
                        end_date=max_date,
                    )

                    if factor_records:
                        factor_map = {}
                        for fr in factor_records:
                            d = fr.trade_date.date() if hasattr(fr.trade_date, "date") else fr.trade_date
                            factor_map[d] = fr.factor_value

                        df.loc[stock_mask, factor_col] = df.loc[
                            stock_mask, "trade_date"
                        ].map(factor_map)

                non_null = df[factor_col].notna().sum()
                logger.info(f"因子 {factor_name} 注入完成: {non_null}/{len(df)} 个有效值")

            except Exception as e:
                logger.warning(f"因子 {factor_name} 注入失败: {e}")

        return df

    # ---- 批量加载辅助方法（v1.3 新增） ----

    async def _load_adj_batch(
        self,
        symbols: List[str],
        start_date,
        end_date,
        adj_type: str = "qfq",
    ) -> List:
        """
        批量加载复权价格数据（一次 SQL IN 查询替代逐只循环）。

        使用 PostgreSQL WHERE ts_code = ANY(:symbols) 批量查询，
        将 N 次 DB 往返减少到 1 次。
        """
        return await self.adj_price_repo.get_batch_by_date_range(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            adj_type=adj_type,
            freq="D",
        )

    async def _load_daily_batch(
        self,
        symbols: List[str],
        start_date,
        end_date,
    ) -> List:
        """
        批量加载日线数据（fallback：不复权数据）。

        通过 StockDailyRepository 批量查询。
        """
        return await self.daily_repo.get_batch_by_date_range(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

    async def _load_etf_batch(
        self,
        symbols: List[str],
        start_date,
        end_date,
    ) -> List[Dict[str, Any]]:
        """
        批量加载 ETF 复权日线数据（etf_daily JOIN fund_adj_factor）。

        ETF 没有 stock_adjusted_prices 预计算复权表，需要通过
        ETFRepository.get_etf_adjusted_daily_batch() 在线 JOIN 计算复权价格。
        """
        return await self.etf_repo.get_etf_adjusted_daily_batch(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
        )

    async def _load_sw_index_batch(
        self,
        symbols: List[str],
        start_date,
        end_date,
    ) -> List[Dict[str, Any]]:
        """
        v3.0: 批量加载申万行业指数日线数据。

        从 index_sw_daily 表查询，返回与 stock/ETF 格式一致的记录列表。
        行业指数数据仅用于策略内部评分，不可交易。
        """
        df = await self.sw_index_repo.get_batch_by_industry_codes(
            industry_codes=symbols,
            start_date=str(start_date),
            end_date=str(end_date),
        )

        if df.empty:
            return []

        records: List[Dict[str, Any]] = []
        for _, row in df.iterrows():
            trade_date_val = row["trade_date"]
            # v2.5: 统一归一化为 date 对象，避免与其他数据源（ETF/stock）
            # 返回的 date 类型不一致导致 sorted() 报 TypeError
            if isinstance(trade_date_val, datetime):
                trade_date_val = trade_date_val.date()
            elif isinstance(trade_date_val, date):
                pass  # 已是 date，不变
            elif isinstance(trade_date_val, str):
                trade_date_val = date.fromisoformat(trade_date_val[:10])
            # 兜底：尝试转换
            try:
                if not isinstance(trade_date_val, date):
                    trade_date_val = date.fromisoformat(str(trade_date_val)[:10])
            except (ValueError, TypeError):
                pass

            records.append({
                "ts_code": str(row["ts_code"]),
                "trade_date": trade_date_val,
                "open": float(row.get("open") or 0),
                "high": float(row.get("high") or 0),
                "low": float(row.get("low") or 0),
                "close": float(row.get("close") or 0),
                "volume": float(row.get("vol") or 0),
                "amount": float(row.get("amount") or 0),
                "name": str(row.get("name") or ""),
                "pe": float(row.get("pe") or 0),
                "pb": float(row.get("pb") or 0),
                "float_mv": float(row.get("float_mv") or 0),
                "pct_chg": float(row.get("pct_change") or 0),
            })

        return records

    # ---- v2.6: 普通指数数据加载 ----

    async def _load_index_batch(
        self,
        symbols: List[str],
        start_date,
        end_date,
    ) -> List[Dict[str, Any]]:
        """
        v2.6: 从 index_daily 表加载普通指数日线数据。

        适用于 881001.WI (万得全A) 等非 SW 行业指数的普通指数。
        """
        from sqlalchemy import text

        records: List[Dict[str, Any]] = []
        for code in symbols:
            try:
                result = await self.db.execute(
                    text(
                        "SELECT ts_code, trade_date, open, high, low, close, vol, amount "
                        "FROM index_daily "
                        "WHERE ts_code = :code AND trade_date BETWEEN :start AND :end "
                        "ORDER BY trade_date ASC"
                    ),
                    {"code": code, "start": start_date, "end": end_date},
                )
                rows = result.fetchall()
                for row in rows:
                    records.append({
                        "ts_code": str(row.ts_code),
                        "trade_date": (
                            row.trade_date.date()
                            if hasattr(row.trade_date, "date")
                            else row.trade_date
                        ),
                        "open": float(row.open) if row.open else 0.0,
                        "high": float(row.high) if row.high else 0.0,
                        "low": float(row.low) if row.low else 0.0,
                        "close": float(row.close) if row.close else 0.0,
                        "volume": float(row.vol) if row.vol else 0.0,
                        "amount": float(row.amount) if row.amount else 0.0,
                    })
            except Exception as e:
                logger.warning(f"加载指数 {code} 数据失败: {e}")

        return records

    # ---- EngineBase 生命周期 ----

    async def _on_initialize(self) -> None:
        """初始化：验证数据库连接 + 预加载交易日历"""
        try:
            from sqlalchemy import text
            await self.db.execute(text("SELECT 1"))
            # 预热交易日历（最近 3 年）
            from datetime import date as _date_class
            today = _date_class.today()
            cal = await self.calendar_repo.get_trade_dates(
                exchange="SSE",
                start_date=_date_class(today.year - 2, 1, 1),
                end_date=today,
                only_open=True,
            )
            self._trading_cal_cache = set(
                d.date() if hasattr(d, "date") else d for d in cal
            )
            logger.info(
                f"DataFeedEngine 初始化完成：交易日历缓存 {len(self._trading_cal_cache)} 天"
            )
        except Exception as e:
            logger.warning(f"DataFeedEngine 初始化部分失败（不影响核心功能）: {e}")
            self._trading_cal_cache = set()

    async def _on_start(self) -> None:
        """启动：注册事件订阅"""
        if self._event_engine:
            self._event_engine.subscribe(
                "data.sync.completed", self._on_data_sync_completed
            )
            logger.info("DataFeedEngine 已启动，订阅 data.sync.completed 事件")

    async def _on_stop(self) -> None:
        """停止：清理缓存"""
        self._trading_cal_cache.clear()
        self._stock_repo = None
        self._daily_repo = None
        self._calendar_repo = None
        self._factor_repo = None
        self._adj_price_repo = None
        self._etf_daily_repo = None
        self._etf_repo = None
        self._sw_index_repo = None
        logger.info("DataFeedEngine 已停止，缓存已清理")

    async def _on_data_sync_completed(self, event) -> None:
        """数据同步完成时刷新交易日历缓存"""
        logger.info("数据同步完成，刷新交易日历缓存")
        self._trading_cal_cache = set()  # 下次访问时重新加载
