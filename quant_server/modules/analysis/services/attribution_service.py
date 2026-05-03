#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归因分析服务

负责计算收益归因，将投资组合的超额收益分解为不同来源的贡献。

支持的归因模型：
--------------
1. **Brinson 归因** — 将主动收益分解为配置效应、选择效应和交互效应
   - 行业 Brinson：按行业板块进行归因，分析行业配置和行业内选股贡献
   - 个股 Brinson：按个股进行归因，逐股票计算配置和选择贡献
   - 参考：Brinson, Hood & Beebower (1986); Brinson & Fachler (1985)

2. **因子归因** — 基于多因子模型（Fama-French/Carhart）的收益分解
   - Fama-French 三因子：市场(MKT)、规模(SMB)、价值(HML)
   - Carhart 四因子：MKT + SMB + HML + 动量(UMD)
   - 通过 OLS 回归估计因子暴露度，计算各因子的收益贡献
   - 参考：Fama & French (1993); Carhart (1997)

核心算法说明：
--------------
- Brinson 分解：Active Return = Allocation + Selection + Interaction
  - Allocation = Σ (w_pi - w_bi) × r_bi
  - Selection  = Σ w_bi × (r_pi - r_bi)
  - Interaction = Active Return - Allocation - Selection
- 因子归因：通过 LinearRegression 估计 β，贡献 = β_i × mean(factor_return_i)
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Tuple, Any

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from modules.analysis.analyzers.attribution.factor_attribution import FactorAttribution
from modules.analysis.models import AttributionAnalysis
from shared.database.repositories import AccountRepository
from shared.database.repositories import PositionRepository
from shared.database.repositories import StockBasicRepository
from shared.database.repositories import StrategyRepository
from shared.database.repositories.market.quote import StockDailyRepository
from shared.database.repositories.market.basic import IndexWeightRepository

logger = logging.getLogger(__name__)


class AttributionService:
    """归因分析服务

    提供 Brinson 归因和因子归因两大类分析方法。
    通过 Repository 层读取持仓、行情数据，委托 FactorAttribution 执行因子分解。

    使用方式：
        service = AttributionService(session)
        result = await service.perform_brinson_attribution(
            portfolio_id="strategy_001", start_date=..., end_date=..., benchmark="000300.SH"
        )
    """

    def __init__(
            self,
            session: AsyncSession,
            strategy_repo: StrategyRepository = None,
            account_repo: AccountRepository = None,
            position_repo: PositionRepository = None,
            quote_repo: StockDailyRepository = None,
            stock_repo: StockBasicRepository = None,
            index_weight_repo: IndexWeightRepository = None
    ):
        """
        初始化归因服务

        Args:
            session: 异步数据库会话，用于 Repository 数据访问
            strategy_repo: 策略 Repository（可选，默认根据 session 创建）
            account_repo: 账户 Repository（可选）
            position_repo: 持仓 Repository（可选）
            quote_repo: 日线行情 Repository（可选）
            stock_repo: 股票基础信息 Repository（可选）
            index_weight_repo: 指数成分股权重 Repository（可选，用于获取真实成分股和权重）
        """
        self.session = session
        self.strategy_repo = strategy_repo or StrategyRepository(session)
        self.account_repo = account_repo or AccountRepository(session)
        self.position_repo = position_repo or PositionRepository(session)
        self.quote_repo = quote_repo or StockDailyRepository(session)
        self.stock_repo = stock_repo or StockBasicRepository(session)
        self.index_weight_repo = index_weight_repo or IndexWeightRepository(session)
        self.factor_attributor = FactorAttribution()

    async def perform_brinson_attribution(
            self,
            portfolio_id: str,
            start_date: datetime,
            end_date: datetime,
            benchmark: str,
            sectors: List[str] = None
    ) -> AttributionAnalysis:
        """执行 Brinson 归因分析

        根据是否提供 sectors 参数，自动选择行业级别或个股级别的 Brinson 分解。
        行业 Brinson 适用于分析行业配置能力，个股 Brinson 适用于逐股票归因。

        计算流程：
        1. 获取组合持仓和基准持仓数据
        2. 计算组合收益率和基准收益率，得到主动收益
        3. 执行 Brinson 分解（行业或个股级别）
        4. 构建 AttributionAnalysis 结果对象

        Args:
            portfolio_id: 组合 ID（策略 ID 以 "strategy_" 开头，否则视为账户 ID）
            start_date: 分析区间起始日期
            end_date: 分析区间结束日期
            benchmark: 基准指数代码（如 "000300.SH" 沪深300、"000905.SH" 中证500）
            sectors: 行业分类列表，非空时按行业归因，为空时按个股归因

        Returns:
            AttributionAnalysis: 包含配置/选择/交互效应及行业/个股明细的归因结果

        Raises:
            ValueError: 持仓数据不足或计算失败时抛出
        """
        try:
            # 1. 获取组合与基准的持仓数据
            portfolio_positions = await self._get_portfolio_positions(
                portfolio_id, start_date, end_date
            )

            benchmark_positions = await self._get_benchmark_positions(
                benchmark, start_date, end_date
            )

            if not portfolio_positions or not benchmark_positions:
                raise ValueError("持仓数据不足")

            # 2. 计算组合与基准 区间 收益率
            portfolio_return = await self._calculate_portfolio_return(
                portfolio_positions, start_date, end_date
            )

            benchmark_return = await self._calculate_benchmark_return(
                benchmark_positions, start_date, end_date
            )

            active_return = portfolio_return - benchmark_return

            # 3. 执行 Brinson 分解
            if sectors:
                # 行业级别 Brinson 归因
                attribution_results = await self._perform_sector_brinson(
                    portfolio_positions, benchmark_positions,
                    sectors, start_date, end_date
                )

                allocation_effect = attribution_results.get('allocation_effect', Decimal("0.0"))
                selection_effect = attribution_results.get('selection_effect', Decimal("0.0"))
                interaction_effect = attribution_results.get('interaction_effect', Decimal("0.0"))

                sector_attributions = attribution_results.get('sector_attributions', {})
                sector_allocations = attribution_results.get('sector_allocations', {})

                attribution = AttributionAnalysis(
                    attribution_id=f"attr_{portfolio_id}_{start_date}_{end_date}",
                    portfolio_id=portfolio_id,
                    analysis_period=f"{start_date} 至 {end_date}",
                    attribution_model="Brinson Sector Attribution",
                    benchmark=benchmark,
                    total_return=Decimal(str(portfolio_return)),
                    benchmark_return=Decimal(str(benchmark_return)),
                    active_return=Decimal(str(active_return)),
                    allocation_effect=Decimal(str(allocation_effect)),
                    selection_effect=Decimal(str(selection_effect)),
                    interaction_effect=Decimal(str(interaction_effect)),
                    sector_attributions=sector_attributions,
                    sector_allocations=sector_allocations
                )
            else:
                # 个股级别 Brinson 归因
                attribution_results = await self._perform_stock_brinson(
                    portfolio_positions, benchmark_positions,
                    start_date, end_date
                )

                allocation_effect = attribution_results.get('allocation_effect', Decimal("0.0"))
                selection_effect = attribution_results.get('selection_effect', Decimal("0.0"))
                interaction_effect = attribution_results.get('interaction_effect', Decimal("0.0"))

                stock_attributions = attribution_results.get('stock_attributions', {})
                stock_contributions = attribution_results.get('stock_contributions', {})

                attribution = AttributionAnalysis(
                    attribution_id=f"attr_{portfolio_id}_{start_date}_{end_date}",
                    portfolio_id=portfolio_id,
                    analysis_period=f"{start_date} 至 {end_date}",
                    attribution_model="Brinson Stock Attribution",
                    benchmark=benchmark,
                    total_return=Decimal(str(portfolio_return)),
                    benchmark_return=Decimal(str(benchmark_return)),
                    active_return=Decimal(str(active_return)),
                    allocation_effect=Decimal(str(allocation_effect)),
                    selection_effect=Decimal(str(selection_effect)),
                    interaction_effect=Decimal(str(interaction_effect)),
                    stock_attributions=stock_attributions,
                    stock_contributions=stock_contributions
                )

            return attribution

        except Exception as e:
            raise ValueError(f"Brinson归因分析失败: {str(e)}")

    async def perform_factor_attribution(
            self,
            portfolio_id: str,
            start_date: datetime,
            end_date: datetime,
            factor_model: str = "Fama-French"
    ) -> AttributionAnalysis:
        """执行因子归因分析

        基于多因子模型将组合收益分解为各因子贡献。
        通过 OLS 回归估计因子暴露度（β），然后计算每个因子的收益贡献。

        计算流程：
        1. 获取组合的日收益率序列
        2. 获取因子日收益率（优先从行情数据计算，回退到模拟数据）
        3. 委托 FactorAttribution 执行因子回归和分解
        4. 构建 AttributionAnalysis 结果对象

        Args:
            portfolio_id: 组合 ID
            start_date: 分析区间起始日期
            end_date: 分析区间结束日期
            factor_model: 因子模型名称，可选 "Fama-French"（三因子）或 "Carhart"（四因子）

        Returns:
            AttributionAnalysis: 包含因子归因贡献和因子暴露度的结果

        Raises:
            ValueError: 收益数据不足（<10 条）或因子数据获取失败时抛出
        """
        try:
            # 获取组合日收益率序列
            portfolio_returns = await self._get_portfolio_returns(
                portfolio_id, start_date, end_date
            )

            if len(portfolio_returns) < 10:
                raise ValueError("收益数据不足（至少需要 10 个交易日）")

            # 获取因子收益率
            factor_returns = await self._get_factor_returns(
                factor_model, start_date, end_date
            )

            if factor_returns.empty:
                raise ValueError(f"无法获取因子收益率: {factor_model}")

            # 委托 FactorAttribution 执行回归分解
            attribution_result = self.factor_attributor.perform_factor_attribution(
                portfolio_returns=portfolio_returns,
                factor_returns=factor_returns,
                factor_model=factor_model
            )

            # 计算组合区间总收益
            total_return = np.prod(1 + portfolio_returns.values) - 1

            # 构建归因结果对象
            attribution = AttributionAnalysis(
                attribution_id=f"factor_{portfolio_id}_{start_date}_{end_date}",
                portfolio_id=portfolio_id,
                analysis_period=f"{start_date} 至 {end_date}",
                attribution_model=f"Factor Attribution ({factor_model})",
                benchmark="",  # 因子归因不需要显式基准
                total_return=Decimal(str(total_return)),
                factor_attributions={
                    factor: Decimal(str(attr))
                    for factor, attr in attribution_result['factor_contributions'].items()
                },
                factor_exposures={
                    factor: Decimal(str(exposure))
                    for factor, exposure in attribution_result['factor_exposures'].items()
                }
            )

            return attribution

        except Exception as e:
            raise ValueError(f"因子归因分析失败: {str(e)}")

    async def compare_attribution_models(
            self,
            portfolio_id: str,
            start_date: datetime,
            end_date: datetime,
            benchmark: str = None
    ) -> Dict[str, AttributionAnalysis]:
        """比较不同归因模型的结果

        同时运行 Brinson 归因和多种因子归因，便于横向对比不同模型的归因结论。
        单个模型失败不影响其他模型继续执行。

        Args:
            portfolio_id: 组合 ID
            start_date: 分析区间起始日期
            end_date: 分析区间结束日期
            benchmark: 基准指数代码（为 None 时跳过 Brinson 归因）

        Returns:
            Dict[str, AttributionAnalysis]: key 为模型名称（"brinson"/"fama-french"/"carhart"），
            value 为对应归因结果。失败模型不包含在结果中。
        """
        results = {}

        # Brinson 归因（需要基准）
        if benchmark:
            try:
                brinson_result = await self.perform_brinson_attribution(
                    portfolio_id, start_date, end_date, benchmark
                )
                results['brinson'] = brinson_result
            except Exception as e:
                logger.warning(f"Brinson归因失败: {str(e)}")

        # 因子归因 — 依次尝试 Fama-French 和 Carhart
        for factor_model in ['Fama-French', 'Carhart']:
            try:
                factor_result = await self.perform_factor_attribution(
                    portfolio_id, start_date, end_date, factor_model
                )
                results[factor_model.lower()] = factor_result
            except Exception as e:
                logger.warning(f"{factor_model}因子归因失败: {str(e)}")

        return results

    # =========================================================================
    # 私有方法 — 数据获取
    # =========================================================================

    async def _get_portfolio_positions(
        self,
        portfolio_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get portfolio positions, resolving account_id from portfolio_id."""
        account_id = None
        if portfolio_id.startswith('strategy_'):
            strategy = await self.strategy_repo.get_by_id(portfolio_id)
            if strategy and hasattr(strategy, "account_id") and strategy.account_id:
                account_id = str(strategy.account_id)
            if not account_id:
                logger.warning(f'Strategy {portfolio_id} has no account, using id as account_id')
                account_id = portfolio_id
        else:
            account_id = portfolio_id

        raw = await self.position_repo.get_account_positions(str(account_id), include_zero=False)
        if not raw:
            return []

        total_value = sum(float(getattr(p, "market_value", 0) or 0) for p in raw)
        if total_value <= 0:
            return []

        positions = []
        for p in raw:
            mv = float(getattr(p, "market_value", 0) or 0)
            positions.append({
                "ts_code": getattr(p, 'ts_code', ''),
                "weight": mv / total_value if total_value > 0 else 0.0,
                "sector": getattr(p, 'sector', getattr(p, 'industry', '')),
            })

        return positions
    async def _get_benchmark_positions(
            self,
            benchmark: str,
            start_date: date,
            end_date: date
    ) -> List[Dict[str, Any]]:
        """获取基准指数的成分股及权重

        优先从 index_weight 表查询真实成分股和权重；
        若表中无数据（如尚未同步），回退到取 stock_repo 前 N 只等权的旧逻辑。

        支持的基准：
        - "000300.SH"：沪深300
        - "000905.SH"：中证500
        - 其他代码：返回空列表（调用方需处理）

        Args:
            benchmark: 基准指数代码
            start_date: 起始日期
            end_date: 结束日期（用于查询该区间生效的权重）

        Returns:
            基准持仓列表，每项包含 ts_code, weight, sector
        """
        del end_date  # 当前按 start_date 查询最近的权重数据
        index_map = {
            '000300.SH': (300, '沪深300'),
            '000905.SH': (500, '中证500'),
        }
        if benchmark in index_map:
            return await self._get_index_constituents(
                index_code=benchmark,
                target_date=start_date,
                fallback_count=index_map[benchmark][0]
            )
        return []

    async def _get_index_constituents(
            self,
            index_code: str,
            target_date: date,
            fallback_count: int
    ) -> list:
        """获取指数成分股及权重（统一入口）

        优先从 index_weight 表读取真实成分股和权重数据；
        若表中无数据则回退到旧逻辑 — 从 stock_basic 取前 N 只股票等权配置。

        回退逻辑保留了向后兼容性：在 index_weight 表尚未同步时，
        归因分析仍可正常执行（使用近似等权基准）。

        Args:
            index_code: 指数代码（如 '000300.SH'）
            target_date: 目标日期，查询该日期生效的权重
            fallback_count: 回退时取前 N 只股票等权

        Returns:
            成分股列表，每项含 ts_code, weight, sector
        """
        try:
            # 优先：从 index_weight 表获取真实成分股和权重
            if self.index_weight_repo:
                constituents = await self.index_weight_repo.get_constituents(
                    index_code=index_code,
                    trade_date=target_date
                )
                if not constituents:
                    # 若指定日期无数据，尝试获取最新日期的成分股
                    constituents = await self.index_weight_repo.get_latest_constituents(
                        index_code=index_code
                    )

                if constituents:
                    return [
                        {
                            'ts_code': c.ts_code,
                            'weight': float(c.weight) if c.weight else 1.0 / len(constituents),
                            'sector': getattr(c.stock, 'industry', '其他') if c.stock else '其他',
                        }
                        for c in constituents
                    ]
        except Exception as e:
            logger.warning(
                f"从 index_weight 表查询 {index_code} 成分股失败，回退到等权方案: {e}"
            )

        # 回退：取 stock_repo 前 N 只股票等权配置（旧逻辑）
        logger.info(f"index_weight 表无 {index_code} 数据，使用等权回退方案（前 {fallback_count} 只）")
        try:
            stocks = await self.stock_repo.get_all()
            if stocks:
                n = min(len(stocks), fallback_count)
                w = 1.0 / n
                return [
                    {
                        'ts_code': s.ts_code,
                        'weight': w,
                        'sector': getattr(s, 'industry', '其他'),
                    }
                    for s in stocks[:n]
                ]
            return []
        except (ValueError, RuntimeError):
            logger.warning(f"获取 {index_code} 成分股失败")
            return []

    # =========================================================================
    # 私有方法 — 收益计算
    # =========================================================================

    async def _calculate_portfolio_return(
            self,
            positions: List[Dict[str, Any]],
            start_date: datetime,
            end_date: datetime
    ) -> float:
        """计算组合的加权区间 收益率

        对每只持仓股票计算区间 收益，按权重加权求和。
        权重归一化：总权重 > 0 时做归一化处理。

        Args:
            positions: 持仓数据列表
            start_date: 区间起始日期
            end_date: 区间结束日期

        Returns:
            float: 组合加权收益率（小数形式，如 0.05 表示 5%）
        """
        if not positions:
            return 0.0

        total_return = 0.0
        total_weight = 0.0

        for position in positions:
            ts_code = position.get('ts_code')
            weight = position.get('weight', 0.0)

            if ts_code and weight > 0:
                stock_return = await self._get_stock_return(
                    ts_code, start_date, end_date
                )
                total_return += stock_return * weight
                total_weight += weight

        if total_weight > 0:
            return total_return / total_weight
        else:
            return 0.0

    async def _calculate_benchmark_return(
            self,
            positions,
            start_date: datetime,
            end_date: datetime
    ) -> float:
        """计算基准的加权区间收益率

        与 _calculate_portfolio_return 逻辑一致，用于基准持仓的加权收益计算。

        Args:
            positions: 基准持仓数据列表
            start_date: 区间起始日期
            end_date: 区间结束日期

        Returns:
            float: 基准加权收益率
        """
        if not positions:
            return 0.0
        total_ret = 0.0
        total_w = 0.0
        for p in positions:
            code = p.get('ts_code', '') if isinstance(p, dict) else getattr(p, 'ts_code', '')
            w = float(p.get('weight', 0) if isinstance(p, dict) else getattr(p, 'weight', 0))
            if code and w > 0:
                sr = await self._get_stock_return(code, start_date, end_date)
                total_ret += sr * w
                total_w += w
        return total_ret / total_w if total_w > 0 else 0.0

    async def _get_stock_return(
            self,
            ts_code: str,
            start_date: datetime,
            end_date: datetime
    ) -> float:
        """计算单只股票在指定区间的收益率

        通过日线行情数据，取区间首日开盘价 → 区间末日收盘价计算简单收益率。
        公式：return = (last_close - first_close) / first_close

        Args:
            ts_code: 股票代码（如 "000001.SZ"）
            start_date: 区间起始日期
            end_date: 区间结束日期

        Returns:
            float: 区间收益率（小数形式），数据不足或异常时返回 0.0
        """
        try:
            quotes = await self.quote_repo.get_by_code_and_date_range(ts_code, start_date, end_date)
            if quotes and len(quotes) >= 2:
                first = float(quotes[0].close)
                last = float(quotes[-1].close)
                return (last / first - 1.0) if first != 0 else 0.0
            return 0.0
        except (ValueError, TypeError):
            logger.warning(f"获取股票 {ts_code} 收益率失败")
            return 0.0

    async def _get_portfolio_returns(
            self,
            portfolio_id: str,
            start_date: datetime,
            end_date: datetime
    ) -> 'pd.Series':
        """获取组合的日收益率序列

        通过持仓股票的价格变化和权重，逐日计算组合的加权日收益率。
        用于因子归因分析中作为因变量进行回归。

        计算逻辑：
        1. 获取组合持仓
        2. 对每只持仓股票获取日线行情，计算日收益率
        3. 按权重加权求和得到组合每日收益率

        Args:
            portfolio_id: 组合 ID
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            pd.Series: index 为日期，values 为日收益率
        """
        positions = await self._get_portfolio_positions(portfolio_id, start_date, end_date)
        if not positions:
            dates = pd.date_range(start_date, end_date, freq='B')
            return pd.Series(np.zeros(len(dates)), index=dates)

        daily_returns = {}
        for p in positions:
            code = p.get('ts_code', '') if isinstance(p, dict) else getattr(p, 'ts_code', '')
            w = float(p.get('weight', 0) if isinstance(p, dict) else getattr(p, 'weight', 0))
            if not code or w <= 0:
                continue
            quotes = await self.quote_repo.get_by_code_and_date_range(code, start_date, end_date)
            if quotes and len(quotes) >= 2:
                df = pd.DataFrame([{'d': q.trade_date, 'c': float(q.close)} for q in quotes])
                df['d'] = pd.to_datetime(df['d'])
                df = df.set_index('d').sort_index()
                rets = df['c'].pct_change().fillna(0)
                for dt, val in rets.items():
                    daily_returns[dt] = daily_returns.get(dt, 0.0) + val * w
        if not daily_returns:
            dates = pd.date_range(start_date, end_date, freq='B')
            return pd.Series(np.zeros(len(dates)), index=dates)
        return pd.Series(daily_returns).sort_index()

    # =========================================================================
    # 私有方法 — Brinson 归因核心算法
    # =========================================================================

    async def _perform_sector_brinson(
            self,
            portfolio_positions,
            benchmark_positions,
            sectors,
            start_date: datetime,
            end_date: datetime
    ) -> dict:
        """按行业执行 Brinson 归因计算

        算法步骤：
        1. 汇总组合和基准在各行业上的权重
        2. 计算各行业的组合收益率（行业内持仓等权平均）
        3. 计算各行业的基准收益率（当前为近似值，TODO: 应从基准成分股计算）
        4. 按 Brinson 公式分解为配置效应、选择效应和交互效应

        公式：
        - 配置效应 = Σ (w_p_s - w_b_s) × r_b_s
        - 选择效应 = Σ w_b_s × (r_p_s - r_b_s)
        - 交互效应 = -配置效应 - 选择效应（近似，精确公式不同）

        Args:
            portfolio_positions: 组合持仓列表
            benchmark_positions: 基准持仓列表
            sectors: 行业分类列表
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            dict: 包含 allocation_effect, selection_effect, interaction_effect,
                  sector_attributions（行业超额收益）, sector_allocations（行业超配/低配）
        """
        # 初始化行业权重和收益
        pf_s = {s: {'w': 0.0, 'r': 0.0} for s in sectors}
        bm_s = {s: {'w': 0.0, 'r': 0.0} for s in sectors}

        # 汇总组合各行业权重
        for p in portfolio_positions:
            sec = p.get('sector', '') if isinstance(p, dict) else getattr(p, 'sector', '')
            if sec in sectors:
                w = float(p.get('weight', 0) if isinstance(p, dict) else getattr(p, 'weight', 0))
                pf_s[sec]['w'] += w

        # 汇总基准各行业权重
        for p in benchmark_positions:
            sec = p.get('sector', '') if isinstance(p, dict) else getattr(p, 'sector', '')
            if sec in sectors:
                w = float(p.get('weight', 0) if isinstance(p, dict) else getattr(p, 'weight', 0))
                bm_s[sec]['w'] += w

        # 计算各行业的组合收益率（行业内股票等权平均）
        for s in sectors:
            s_returns = []
            for p in portfolio_positions:
                sec = p.get('sector', '') if isinstance(p, dict) else getattr(p, 'sector', '')
                if sec == s:
                    code = p.get('ts_code', '') if isinstance(p, dict) else getattr(p, 'ts_code', '')
                    if code:
                        sr = await self._get_stock_return(code, start_date, end_date)
                        s_returns.append(sr)
            pf_s[s]['r'] = sum(s_returns) / len(s_returns) if s_returns else 0.0

            # Compute benchmark sector returns from actual benchmark constituents
            bm_s_returns = []
            for p in benchmark_positions:
                sec = p.get("sector", "") if isinstance(p, dict) else getattr(p, "sector", "")
                if sec == s:
                    code = p.get("ts_code", "") if isinstance(p, dict) else getattr(p, "ts_code", "")
                    if code:
                        br = await self._get_stock_return(code, start_date, end_date)
                        bm_s_returns.append(br)
            bm_s[s]['r'] = sum(bm_s_returns) / len(bm_s_returns) if bm_s_returns else 0.0

        # Brinson 分解
        alloc = sum((pf_s[s]['w'] - bm_s[s]['w']) * bm_s[s]['r'] for s in sectors)
        selec = sum(bm_s[s]['w'] * (pf_s[s]['r'] - bm_s[s]['r']) for s in sectors)
        inter = -alloc - selec

        return {
            'allocation_effect': alloc,
            'selection_effect': selec,
            'interaction_effect': inter,
            'sector_attributions': {s: pf_s[s]['r'] - bm_s[s]['r'] for s in sectors},
            'sector_allocations': {s: pf_s[s]['w'] - bm_s[s]['w'] for s in sectors},
        }

    async def _perform_stock_brinson(
            self,
            portfolio_positions,
            benchmark_positions,
            start_date: datetime,
            end_date: datetime
    ) -> dict:
        """按个股执行 Brinson 归因计算

        对组合和基准中每只股票计算配置效应和选择效应。

        算法步骤：
        1. 遍历组合持仓，构建 {code: (weight, return)} 字典
        2. 遍历基准持仓，构建 {code: (weight, return)} 字典
        3. 对组合和基准的股票并集，逐股票计算：
           - 配置效应 = (w_p_norm - w_b_norm) × r_b
           - 选择效应 = w_b_norm × (r_p - r_b)
           - 股票贡献 = r_p × w_p_norm

        Brinson 公式（Fachler 变体）：
        - 配置效应 = Σ (w_pi - w_bi) × (r_bi - R_b)
        - 选择效应 = Σ w_bi × (r_pi - r_bi)

        当前使用 Brinson（非 Fachler），不减去基准总收益。

        Args:
            portfolio_positions: 组合持仓列表
            benchmark_positions: 基准持仓列表
            start_date: 区间起始日期
            end_date: 区间结束日期

        Returns:
            dict: 包含 allocation_effect, selection_effect, interaction_effect,
                  stock_attributions（{code: {allocation, selection}}）,
                  stock_contributions（{code: contribution}）
        """
        # 第一步：构建组合持仓字典 {code: (weight, return)}
        pf_data: Dict[str, tuple] = {}
        pf_w_sum = 0.0

        for p in portfolio_positions:
            code = p.get('ts_code', '') if isinstance(p, dict) else getattr(p, 'ts_code', '')
            if not code:
                continue
            pw = float(p.get('weight', 0) if isinstance(p, dict) else getattr(p, 'weight', 0))
            pf_w_sum += pw
            sr = await self._get_stock_return(code, start_date, end_date)
            pf_data[code] = (pw, sr)

        if pf_w_sum <= 0:
            return {
                'allocation_effect': 0.0, 'selection_effect': 0.0,
                'interaction_effect': 0.0,
                'stock_attributions': {}, 'stock_contributions': {},
            }

        # 第二步：构建基准持仓字典 {code: (weight, return)}
        bm_data: Dict[str, tuple] = {}
        bm_w_sum = 0.0

        for p in benchmark_positions:
            code = p.get('ts_code', '') if isinstance(p, dict) else getattr(p, 'ts_code', '')
            if not code:
                continue
            bw = float(p.get('weight', 0) if isinstance(p, dict) else getattr(p, 'weight', 0))
            bm_w_sum += bw
            br = await self._get_stock_return(code, start_date, end_date)
            bm_data[code] = (bw, br)

        if bm_w_sum <= 0:
            return {
                'allocation_effect': 0.0, 'selection_effect': 0.0,
                'interaction_effect': 0.0,
                'stock_attributions': {}, 'stock_contributions': {},
            }

        # 第三步：对组合和基准的股票并集，逐股票计算 Brinson 归因
        stock_attr: Dict[str, dict] = {}
        stock_contrib: Dict[str, float] = {}
        allocation_effect = 0.0
        selection_effect = 0.0
        all_codes = set(pf_data.keys()) | set(bm_data.keys())

        for code in all_codes:
            pf_w, pf_r = pf_data.get(code, (0.0, 0.0))
            bm_w, bm_r = bm_data.get(code, (0.0, 0.0))

            pf_w_norm = pf_w / pf_w_sum
            bm_w_norm = bm_w / bm_w_sum

            # 配置效应：组合权重 vs 基准权重的偏差 × 基准收益
            alloc = (pf_w_norm - bm_w_norm) * bm_r
            # 选择效应：基准权重 × 组合股票超额收益
            sel = bm_w_norm * (pf_r - bm_r)

            allocation_effect += alloc
            selection_effect += sel

            stock_attr[code] = {'allocation': alloc, 'selection': sel}
            stock_contrib[code] = pf_r * pf_w_norm

        interaction_effect = -allocation_effect - selection_effect

        return {
            'allocation_effect': allocation_effect,
            'selection_effect': selection_effect,
            'interaction_effect': interaction_effect,
            'stock_attributions': stock_attr,
            'stock_contributions': stock_contrib,
        }

    # =========================================================================
    # 私有方法 — 因子归因辅助
    # =========================================================================

    async def _get_factor_returns(
            self,
            factor_model: str,
            start_date: datetime,
            end_date: datetime
    ) -> 'pd.DataFrame':
        """获取因子日收益率序列

        优先从基准行情数据计算 MKT 因子（市场超额收益），其他因子回退到模拟数据。
        无法获取任何数据时使用随机数生成器产生占位数据。

        因子定义：
        - Fama-French: MKT（市场）、SMB（规模）、HML（价值）
        - Carhart: 上述三项 + UMD（动量）

        Args:
            factor_model: "Fama-French" 或 "Carhart"
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            pd.DataFrame: index=交易日（B频），columns=因子名，values=日收益率

        TODO: 对接真实因子数据源（如 Fama-French 中国版因子、Barra CNE5 因子）
        """
        dates = pd.date_range(start_date, end_date, freq='B')
        if factor_model == 'Fama-French':
            factors = ['MKT', 'SMB', 'HML']
        elif factor_model == 'Carhart':
            factors = ['MKT', 'SMB', 'HML', 'UMD']
        else:
            factors = ['Factor1', 'Factor2', 'Factor3']

        # 尝试从基准行情数据计算 MKT 因子
        try:
            bm = await self.quote_repo.get_by_code_and_date_range('000300.SH', start_date, end_date)
            if bm and len(bm) > 0:
                df = pd.DataFrame([{'d': x.trade_date, 'c': float(x.close)} for x in bm])
                df['d'] = pd.to_datetime(df['d'])
                df = df.set_index('d').sort_index()
                df['MKT'] = df['c'].pct_change()
                data = {}
                for i, f in enumerate(factors):
                    if f == 'MKT':
                        data[f] = df['MKT'].reindex(dates).fillna(0).values[:len(dates)]
                    else:
                        # TODO: 应从真实数据源获取 SMB/HML/UMD 因子
                        rng = np.random.RandomState(42 + i)
                        data[f] = rng.randn(len(dates)) * 0.003
                return pd.DataFrame(data, index=dates)
            raise ValueError('无基准数据')
        except (ValueError, RuntimeError, TypeError):
            # 完全回退：随机模拟因子收益率
            logger.warning(
                f"无法获取 {factor_model} 因子收益率，使用随机模拟数据。"
                f"请确认行情数据源配置正确。"
            )
            rng = np.random.RandomState(42)
            return pd.DataFrame(
                {f: rng.randn(len(dates)) * 0.005 for f in factors},
                index=dates
            )

    @staticmethod
    async def _perform_factor_regression(
        portfolio_returns: np.ndarray,
        factor_returns: np.ndarray,
        factor_names: List[str]
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """Estimate factor exposures and attribution via OLS (np.linalg.lstsq)."""
        if len(portfolio_returns) != len(factor_returns):
            raise ValueError(
                f"return series length mismatch: portfolio {len(portfolio_returns)}, factors {len(factor_returns)}"
            )

        # OLS: X = [1 | factor_returns], solve via lstsq
        X = np.column_stack([np.ones(len(factor_returns)), factor_returns])
        coef, residuals, rank, sv = np.linalg.lstsq(X, portfolio_returns, rcond=None)

        # Factor exposures (skip intercept at index 0)
        exposures = {}
        for i, factor in enumerate(factor_names):
            exposures[factor] = float(coef[i + 1])

        # Factor contribution = beta_i * mean(factor_return_i)
        attributions = {}
        for i, factor in enumerate(factor_names):
            contrib = float(coef[i + 1]) * float(np.mean(factor_returns[:, i]))
            attributions[factor] = contrib

        return exposures, attributions
