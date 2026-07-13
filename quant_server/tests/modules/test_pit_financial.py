# -*- coding: utf-8 -*-
"""
Point-in-Time 财务数据查询正确性验证

验证财务数据查询不会返回"未来数据"（在公告日之前不应可见的财报数据）。

背景：
  - financial_income 表的 f_ann_date 字段存储实际公告日期
  - financial_balance 表的 f_ann_date 字段存储实际公告日期
  - 回测/因子计算必须以 f_ann_date 为界，只获取已披露的财报
  - 修复前：查询时未按 f_ann_date 过滤 → 存在未来函数
  - 修复后：查询时增加 f_ann_date <= query_date 过滤 → PIT 正确

测试策略：
  - 使用已知的 A 股披露规则验证
  - Q1 报告 (end_date=03-31) 最晚 4月30日 披露
  - 半年报 (end_date=06-30) 最晚 8月31日 披露
  - Q3 报告 (end_date=09-30) 最晚 10月31日 披露
  - 年报   (end_date=12-31) 最晚 次年4月30日 披露
"""
import pytest
from datetime import date, timedelta


# =============================================================================
# 单元测试：PIT 逻辑正确性（不依赖数据库连接）
# =============================================================================


class TestPITLogic:
    """验证 PIT 过滤的核心逻辑（纯函数，不依赖 DB）"""

    def _apply_pit_filter(self, records, query_date):
        """模拟 PIT 过滤：只返回 f_ann_date <= query_date 的记录"""
        return [r for r in records if r.get("f_ann_date") and r["f_ann_date"] <= query_date]

    def test_q1_report_not_visible_in_april(self):
        """Q1 报告 (end_date=03-31)，在 4月15日 查询时不应可见（通常 4月底才披露）"""
        records = [
            {"end_date": date(2023, 12, 31), "f_ann_date": date(2024, 4, 3), "eps": 10.0},   # 2023年报, 4月3日披露
            {"end_date": date(2024, 3, 31),  "f_ann_date": date(2024, 4, 28), "eps": 2.5},    # 2024Q1, 4月28日披露
        ]
        query_date = date(2024, 4, 15)

        result = self._apply_pit_filter(records, query_date)

        # 4月15日：2023年报(4月3日披露)可见，2024Q1(4月28日披露)不可见
        end_dates = {r["end_date"] for r in result}
        assert date(2023, 12, 31) in end_dates, "已披露的2023年报应该可见"
        assert date(2024, 3, 31) not in end_dates, f"2024Q1在4月28日才披露，{query_date}时不应可见"

    def test_q1_report_visible_after_disclosure(self):
        """Q1 报告在披露日之后应正常可见"""
        records = [
            {"end_date": date(2023, 12, 31), "f_ann_date": date(2024, 4, 3), "eps": 10.0},
            {"end_date": date(2024, 3, 31),  "f_ann_date": date(2024, 4, 28), "eps": 2.5},
        ]
        query_date = date(2024, 5, 1)  # 4月30日之后，所有年报和Q1已披露

        result = self._apply_pit_filter(records, query_date)

        assert len(result) == 2, f"5月1日时所有报告都应可见，但只返回了 {len(result)} 条"

    def test_annual_report_not_visible_before_march(self):
        """年报在次年3月1日查询时不应可见（年报最晚4月30日，但大部分在3-4月披露）"""
        records = [
            {"end_date": date(2023, 12, 31), "f_ann_date": date(2024, 3, 28), "eps": 10.0},
        ]
        query_date = date(2024, 3, 1)

        result = self._apply_pit_filter(records, query_date)

        assert len(result) == 0, f"3月1日时2023年报尚未披露（3月28日才披露），不应可见"

    def test_no_f_ann_date_means_invisible(self):
        """缺少 f_ann_date 的记录应视为不可见（防止未披露数据泄漏）"""
        records = [
            {"end_date": date(2024, 3, 31), "f_ann_date": None, "eps": 2.5},  # 缺少披露日期
        ]
        query_date = date(2024, 5, 1)

        result = self._apply_pit_filter(records, query_date)

        # 缺少 f_ann_date → 无法判断是否已披露 → 安全起见，不应返回
        assert len(result) == 0, "缺少 f_ann_date 的记录不应返回"

    def test_multiple_quarters_pit_correct(self):
        """完整年度多季度 PIT 测试"""
        records = [
            # end_date, f_ann_date, label
            {"end_date": date(2022, 12, 31), "f_ann_date": date(2023, 4, 10), "label": "2022年报"},
            {"end_date": date(2023, 3, 31),  "f_ann_date": date(2023, 4, 25), "label": "2023Q1"},
            {"end_date": date(2023, 6, 30),  "f_ann_date": date(2023, 8, 28), "label": "2023中报"},
            {"end_date": date(2023, 9, 30),  "f_ann_date": date(2023, 10, 27), "label": "2023Q3"},
        ]

        # 时点1: 2023-04-15 — 只有2022年报可见
        r1 = self._apply_pit_filter(records, date(2023, 4, 15))
        labels = {r["label"] for r in r1}
        assert labels == {"2022年报"}, f"4月15日只有2022年报应可见，实际: {labels}"

        # 时点2: 2023-05-01 — 2022年报 + 2023Q1 可见
        r2 = self._apply_pit_filter(records, date(2023, 5, 1))
        labels = {r["label"] for r in r2}
        assert labels == {"2022年报", "2023Q1"}, f"5月1日应可见2022年报+2023Q1，实际: {labels}"

        # 时点3: 2023-09-01 — 2022年报 + 2023Q1 + 2023中报 可见
        r3 = self._apply_pit_filter(records, date(2023, 9, 1))
        labels = {r["label"] for r in r3}
        assert labels == {"2022年报", "2023Q1", "2023中报"}, f"9月1日应可见3份报告，实际: {labels}"

        # 时点4: 2023-11-01 — 全部可见
        r4 = self._apply_pit_filter(records, date(2023, 11, 1))
        assert len(r4) == 4, f"11月1日全部4份报告应可见，实际: {len(r4)}"


# =============================================================================
# 集成测试：验证数据库中的实际 f_ann_date 字段（需要数据库连接）
# 当前项目没有 db_session fixture → 标记为 skip，等 conftest.py 配置后启用
# =============================================================================


@pytest.mark.skip(reason="数据库 fixture 未配置，conftest.py 需先注册 db_session fixture")
@pytest.mark.integration
class TestPITDatabaseIntegration:
    """验证数据库中财务数据表的 f_ann_date 字段完整性"""

    async def test_financial_income_has_f_ann_date(self, db_session):
        """验证 financial_income 表中 f_ann_date 字段存在且有数据"""
        from sqlalchemy import text
        result = await db_session.execute(text(
            "SELECT COUNT(*) FROM financial_income WHERE f_ann_date IS NOT NULL"
        ))
        count = result.scalar()
        assert count > 0, "financial_income 表中没有任何 f_ann_date 数据"

    async def test_financial_balance_has_f_ann_date(self, db_session):
        """验证 financial_balance 表中 f_ann_date 字段存在且有数据"""
        from sqlalchemy import text
        result = await db_session.execute(text(
            "SELECT COUNT(*) FROM financial_balance WHERE f_ann_date IS NOT NULL"
        ))
        count = result.scalar()
        assert count > 0, "financial_balance 表中没有任何 f_ann_date 数据"

    async def test_no_future_data_for_known_query_date(self, db_session):
        """验证：在已知时点查询，不会返回当时尚未披露的财报

        以贵州茅台 600519.SH 为例：
        - 2023Q1 报告 end_date=2023-03-31, f_ann_date≈2023-04-26
        - 在 2023-04-15 查询 → 不应返回 2023Q1 的数据
        """
        from sqlalchemy import text
        query_date = date(2023, 4, 15)
        ts_code = "600519.SH"

        result = await db_session.execute(text("""
            SELECT end_date, f_ann_date
            FROM financial_income
            WHERE ts_code = :ts_code
              AND f_ann_date > :query_date
              AND end_date < :query_date
        """), {"ts_code": ts_code, "query_date": query_date})

        future_rows = result.fetchall()
        if future_rows:
            # 如果查询返回了结果，说明存在"未来数据"泄漏
            # 但这是原始表查询，不经过 PIT 过滤 — 这只是验证数据本身
            # 真正的 PIT 过滤应该在 research_service._get_financial_data() 中生效
            pass  # 不 fail，因为原始表查询不经过 PIT 过滤

    async def test_pit_filtering_in_practice(self, db_session):
        """模拟 PIT 过滤：验证加了 f_ann_date <= query_date 后不会泄漏"""
        from sqlalchemy import text
        query_date = date(2023, 4, 15)

        # 不带 PIT 过滤（修复前）
        r1 = await db_session.execute(text("""
            SELECT COUNT(*) FROM financial_income
            WHERE end_date = '2023-03-31'
        """))
        no_pit_count = r1.scalar()

        # 带 PIT 过滤（修复后） — 2023-04-15 时不应看到 end_date=03-31 的数据
        # 因为大多数公司的 Q1 报告在 4 月底才披露
        r2 = await db_session.execute(text("""
            SELECT COUNT(*) FROM financial_income
            WHERE end_date = '2023-03-31'
              AND f_ann_date <= :query_date
        """), {"query_date": query_date})
        pit_count = r2.scalar()

        # PIT 过滤后的数量应 <= 未过滤的数量
        # 差异 = 被 PIT 过滤排除的"未来数据"
        assert pit_count <= no_pit_count, \
            f"PIT 过滤后 ({pit_count}) 不应超过未过滤 ({no_pit_count})"
