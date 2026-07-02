# -*- coding: utf-8 -*-
"""申万行业日线行情数据仓库"""
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database.models.data_models import IndexSwDaily
from shared.database.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class IndexSwDailyRepository(BaseRepository[IndexSwDaily]):
    """申万行业日线行情数据访问"""

    def __init__(self, session: AsyncSession):
        super().__init__(session, IndexSwDaily)

    # -------------------------------------------------------------------------
    # 批量查询
    # -------------------------------------------------------------------------

    async def get_batch_by_industry_codes(
        self,
        industry_codes: List[str],
        start_date: str,
        end_date: str,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        批量查询多个申万行业在日期范围内的日线数据。

        Args:
            industry_codes: 行业代码列表，如 ["801780.SI", "801150.SI"]
            start_date: 开始日期 "YYYY-MM-DD"
            end_date: 结束日期 "YYYY-MM-DD"
            columns: 需要的列（默认全部）

        Returns:
            DataFrame，列: ts_code, trade_date, name, open, high, low, close,
                        pct_change, vol, amount, pe, pb, float_mv, total_mv
            按 trade_date ASC, ts_code ASC 排序
        """
        if not industry_codes:
            return pd.DataFrame()

        start_dt = _parse_date(start_date)
        end_dt = _parse_date(end_date)

        col_str = _build_column_list(columns)

        sql = text(f"""
            SELECT {col_str}
            FROM index_sw_daily
            WHERE ts_code = ANY(:codes)
              AND trade_date >= :start_date
              AND trade_date <= :end_date
            ORDER BY trade_date ASC, ts_code ASC
        """)

        try:
            result = await self.session.execute(
                sql,
                {
                    "codes": industry_codes,
                    "start_date": start_dt,
                    "end_date": end_dt,
                },
            )
            rows = result.fetchall()
            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows, columns=result.keys())
            logger.info(
                f"index_sw_daily 批量查询: {len(industry_codes)} 个行业, "
                f"{start_date}~{end_date} → {len(df)} 行"
            )
            return df
        except Exception as e:
            logger.error(f"index_sw_daily 批量查询失败: {e}")
            return pd.DataFrame()

    async def get_latest_for_all_l1_industries(
        self,
        lookback_days: int = 1300,
    ) -> Dict[str, pd.DataFrame]:
        """
        获取所有 L1 申万行业的最近 N 天日线数据（按行业分组）。

        Args:
            lookback_days: 回溯天数（默认 1300 ≈ 5 年）

        Returns:
            {行业代码: DataFrame}，DataFrame 按 trade_date 排序
        """
        end_date = date.today().isoformat()
        start_date = (date.today() - pd.Timedelta(days=lookback_days)).isoformat()

        # 先查出所有 L1 行业的 distinct ts_code
        sql_codes = text("""
            SELECT DISTINCT ts_code
            FROM index_sw_daily
            WHERE ts_code LIKE '801%'
              AND ts_code NOT LIKE '8010%'
        """)
        result = await self.session.execute(sql_codes)
        codes = [row[0] for row in result.fetchall()]

        if not codes:
            logger.warning("未找到 L1 申万行业代码")
            return {}

        # 批量查询
        df_all = await self.get_batch_by_industry_codes(
            industry_codes=codes,
            start_date=start_date,
            end_date=end_date,
        )

        # 按 ts_code 分组
        if df_all.empty:
            return {}

        result_dict: Dict[str, pd.DataFrame] = {}
        for code in codes:
            group = df_all[df_all["ts_code"] == code].copy()
            if not group.empty:
                group = group.sort_values("trade_date").reset_index(drop=True)
                result_dict[code] = group

        logger.info(f"L1 行业日线数据加载: {len(result_dict)}/{len(codes)} 个行业")
        return result_dict


# =============================================================================
# 辅助函数
# =============================================================================


def _parse_date(d: str) -> date:
    """解析日期字符串"""
    if isinstance(d, date):
        return d
    if isinstance(d, datetime):
        return d.date()
    return date.fromisoformat(d)


def _build_column_list(columns: Optional[List[str]]) -> str:
    """构建 SELECT 列列表"""
    if columns:
        return ", ".join(c for c in columns if c not in ("*",))
    return (
        "ts_code, trade_date, name, open, high, low, close, "
        "pct_change, vol, amount, pe, pb, float_mv, total_mv"
    )
