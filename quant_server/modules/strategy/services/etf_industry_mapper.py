# -*- coding: utf-8 -*-
"""
行业 → ETF 映射服务

将申万行业排名转换为具体的 ETF 交易标的。

职责：
  1. 行业名 → ETF 代码映射（从配置文件读取）
  2. ETF 流动性/规模动态过滤
  3. 粘性策略：尽可能不切换正在持有的 ETF
  4. primary → secondary 降级逻辑
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Lazy import to avoid triggering the full modules.strategy chain
_INDUSTRY_ETF_MAP = None


def _get_industry_etf_map():
    """延迟加载 ETF 映射表，避免触发 modules.strategy 包链"""
    global _INDUSTRY_ETF_MAP
    if _INDUSTRY_ETF_MAP is None:
        import importlib.util
        import os
        _path = os.path.join(
            os.path.dirname(__file__), "..", "config", "industry_etf_map.py"
        )
        spec = importlib.util.spec_from_file_location(
            "industry_etf_map", os.path.abspath(_path)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _INDUSTRY_ETF_MAP = mod.INDUSTRY_ETF_MAP
    return _INDUSTRY_ETF_MAP


@dataclass
class EtfSelection:
    """某个行业被选定参与交易时，对应的 ETF 选择结果"""

    industry_name: str         # 申万行业名
    industry_code: str         # 行业指数代码
    ts_code: str               # 选定的 ETF 代码
    rank: int                  # 行业排名
    score: float               # 行业综合得分
    reason: str                # 选中理由
    is_new: bool = False       # 是否为新买入（vs 继续持有）


class EtfIndustryMapper:
    """
    行业 ETF 映射器。

    无状态。输入行业排名 + 当前 ETF 持仓 → 输出该买入的 ETF 列表。

    用法:
        mapper = EtfIndustryMapper()
        selections = mapper.resolve(ranked_industries, current_holdings, etf_data_cache)
    """

    # 流动性门槛
    MIN_DAILY_AMOUNT: float = 1e7          # 1000 万元
    MIN_DAILY_AMOUNT_FALLBACK: float = 5e6  # 500 万元（兜底）

    def __init__(self, industry_etf_map: Optional[Dict[str, Dict[str, str]]] = None):
        """
        Args:
            industry_etf_map: 行业→ETF 映射表；不传则用默认配置
        """
        self._mapping = industry_etf_map or _get_industry_etf_map()

    # -------------------------------------------------------------------------
    # 公开接口
    # -------------------------------------------------------------------------

    def resolve(
        self,
        ranked_industries: List[tuple],
        current_holdings: Set[str],
        etf_data_cache: Dict[str, pd.DataFrame],
    ) -> List[EtfSelection]:
        """
        将行业排名转换为 ETF 选择列表。

        Args:
            ranked_industries: [(行业代码, 行业名, 得分, rank), ...] 已排序
            current_holdings: 当前持有的 ETF 代码集合
            etf_data_cache: {ETF代码: DataFrame(close, volume)} 日线数据

        Returns:
            EtfSelection 列表（买了哪些 ETF）
        """
        selections: List[EtfSelection] = []

        for industry_code, industry_name, score, rank in ranked_industries:
            sel = self._select_etf(
                industry_name=industry_name,
                industry_code=industry_code,
                score=score,
                rank=rank,
                current_holdings=current_holdings,
                etf_data_cache=etf_data_cache,
            )
            if sel:
                selections.append(sel)

        return selections

    def get_industry_etf_candidates(self, industry_name: str) -> List[str]:
        """获取某个行业的 ETF 候选列表（primary, secondary）"""
        mapping = self._mapping.get(industry_name, {})
        candidates = []
        for key in ("primary", "secondary"):
            code = mapping.get(key, "")
            if code:
                candidates.append(code)
        return candidates

    def get_all_etf_codes(self) -> List[str]:
        """获取映射表中所有 ETF 代码（去重）"""
        codes: Set[str] = set()
        for mapping in self._mapping.values():
            for key in ("primary", "secondary"):
                code = mapping.get(key, "")
                if code:
                    codes.add(code)
        return sorted(codes)

    # -------------------------------------------------------------------------
    # 内部逻辑
    # -------------------------------------------------------------------------

    def _select_etf(
        self,
        industry_name: str,
        industry_code: str,
        score: float,
        rank: int,
        current_holdings: Set[str],
        etf_data_cache: Dict[str, pd.DataFrame],
    ) -> Optional[EtfSelection]:
        """
        为单个行业选择最优 ETF。

        优先级:
          1. 当前持仓的 ETF（粘性）→ 只检查流动性是否严重恶化
          2. primary ETF → 检查流动性
          3. secondary ETF → 检查流动性
          4. 无可用 ETF → 返回 None
        """
        mapping = self._mapping.get(industry_name, {})
        primary = mapping.get("primary", "")
        secondary = mapping.get("secondary", "")

        if not primary and not secondary:
            logger.debug(f"行业 {industry_name} 无 ETF 映射，跳过")
            return None

        # ---- 粘性检查：当前持仓的 ETF 在同一行业内 ----
        for held_code in current_holdings:
            if held_code in (primary, secondary):
                if self._check_liquidity(held_code, etf_data_cache,
                                         min_amount=self.MIN_DAILY_AMOUNT_FALLBACK):
                    return EtfSelection(
                        industry_name=industry_name,
                        industry_code=industry_code,
                        ts_code=held_code,
                        rank=rank,
                        score=score,
                        reason=f"继续持有(粘性) — 排名 #{rank}",
                        is_new=False,
                    )
                else:
                    logger.info(
                        f"{industry_name}: 持仓 ETF {held_code} 流动性恶化，尝试切换"
                    )

        # ---- Primary ETF ----
        if primary and self._check_liquidity(primary, etf_data_cache):
            return EtfSelection(
                industry_name=industry_name,
                industry_code=industry_code,
                ts_code=primary,
                rank=rank,
                score=score,
                reason=f"新买入 primary — 排名 #{rank}",
                is_new=True,
            )

        # ---- Secondary ETF ----
        if secondary and self._check_liquidity(secondary, etf_data_cache):
            return EtfSelection(
                industry_name=industry_name,
                industry_code=industry_code,
                ts_code=secondary,
                rank=rank,
                score=score,
                reason=f"新买入 secondary — 排名 #{rank}",
                is_new=True,
            )

        # ---- 降级尝试：只要有一点流动性就用 ----
        for code in [primary, secondary]:
            if code and self._check_liquidity(code, etf_data_cache,
                                              min_amount=1e6):  # 100 万
                return EtfSelection(
                    industry_name=industry_name,
                    industry_code=industry_code,
                    ts_code=code,
                    rank=rank,
                    score=score,
                    reason=f"低流动性买入 {code} — 排名 #{rank}",
                    is_new=True,
                )

        logger.warning(f"{industry_name}: 无可用 ETF（primary={primary}, secondary={secondary}），跳过")
        return None

    # -------------------------------------------------------------------------
    # 流动性检查
    # -------------------------------------------------------------------------

    @staticmethod
    def _check_liquidity(
        ts_code: str,
        etf_data_cache: Dict[str, pd.DataFrame],
        min_amount: float = None,
    ) -> bool:
        """
        检查 ETF 是否满足流动性要求。

        规则：近 20 日均成交额 > min_amount

        Args:
            ts_code: ETF 代码
            etf_data_cache: {ETF代码: DataFrame}
            min_amount: 最小日均成交额（默认 1000 万）

        Returns:
            是否满足流动性条件
        """
        if min_amount is None:
            min_amount = EtfIndustryMapper.MIN_DAILY_AMOUNT

        df = etf_data_cache.get(ts_code)
        if df is None or len(df) < 5:
            # 数据不足 5 天 → 保守起见，允许交易
            return True

        amount_col = "amount" if "amount" in df.columns else None
        if amount_col is None:
            # 没有成交额列 → 用 volume 估算（volume 单位通常为手 = 100 股）
            return True

        recent_amounts = df[amount_col].tail(20).astype(float)
        avg_amount = float(recent_amounts.mean()) if len(recent_amounts) > 0 else 0.0

        # 注意：index_sw_daily 的 amount 单位是万元，ETF 的 amount 单位可能是元或万元
        # 这里做保守判断：只要 > 0 就通过（避免单位不一致误杀）
        if avg_amount <= 0:
            return False

        return avg_amount >= min_amount
