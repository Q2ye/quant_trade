# -*- coding: utf-8 -*-
"""覆盖度门「当日单日门」回归测试（源自 2026-10-12 `stock_moneyflow` 缺口）。

## 被修的漏洞

原覆盖度门（Fix7）只有**近 60 日聚合**判据：逐股比对 60 日内 `stock_daily` 与目标表
的天数，要求 `缺失 >= 20 天` 才告警。2026-10-12 实测反例：`stock_moneyflow` 当日
只落 **2378/5553（42.8%）**，门仍报「覆盖正常」—— 单日大面积丢数**要丢满约一个月
（20 个交易日）才会被门发现**。

## 本文件守住的五件事

1. 单日大面积缺失 → 告警（真实 10-12 数字：2925/5209）
2. 健康日 → 不告警（真实 09-30 数字：0/5210）
3. 阈值边界：恰好 10% 不告警（严格大于）、超过 10% 告警
4. 基准过小（非交易日 / 日线未同步）→ **不告警**（防空跑误报）
5. 北交所**不再**被排除（原「Tushare 不含 920xxx.BJ」的依据已实测证伪；
   继续排除会掩盖真实的北交所缺口 —— 2026-10-12 订正）
"""
import asyncio

import pytest

from modules.data import _single_day_coverage

DAY = "2026-10-12"


class _Res:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeSession:
    """只按预设返回 `(missing, base)`，同时记录下发的 SQL 供断言。"""

    def __init__(self, missing, base):
        self._row = (missing, base)
        self.sqls = []

    async def execute(self, clause, params=None):
        self.sqls.append(str(clause))
        return _Res(self._row)


def _check(missing, base, bj="", **kw):
    """`bj` 默认空串 —— 与调用方现状一致（2026-10-12 起不再排除北交所）。"""
    sess = _FakeSession(missing, base)
    result = asyncio.run(
        _single_day_coverage(sess, "stock_moneyflow", DAY, bj, **kw)
    )
    return result, sess


# ------------------------------------------------------------ ① 真实缺口必须被抓到
def test_real_20261012_gap_alerts():
    """10-12 实测 2925/5209 缺失（覆盖率 43.8%）→ 必须告警。"""
    (missing, base, alert), _ = _check(2925, 5209)
    assert (missing, base) == (2925, 5209), "计数未原样返回"
    assert alert is True, "单日 43.8% 覆盖率竟未告警 —— 门形同虚设"


# ------------------------------------------------------------ ② 健康日不误报
def test_healthy_day_does_not_alert():
    """09-30 实测 0/5210 → 不告警。"""
    (missing, base, alert), _ = _check(0, 5210)
    assert (missing, base) == (0, 5210)
    assert alert is False


# ------------------------------------------------------------ ③ 阈值边界
@pytest.mark.parametrize("missing,expect", [(521, False), (522, True)])
def test_threshold_is_strictly_greater_than_10pct(missing, expect):
    """基准 5210：恰 10% 不告警，超过 10% 才告警（严格大于）。"""
    (_, _, alert), _ = _check(missing, 5210)
    assert alert is expect, f"缺失 {missing}/5210 的告警判定不符（期望 {expect}）"


# ------------------------------------------------------------ ④ 小基准跳过
@pytest.mark.parametrize("missing,base", [(0, 0), (500, 500), (900, 999)])
def test_small_base_is_skipped(missing, base):
    """非交易日（基准 0）或日线未同步（基准 < 1000）→ 即使全缺也不告警。"""
    (_, _, alert), _ = _check(missing, base)
    assert alert is False, f"基准 {base} 过小仍告警 → 空跑/非交易日会误报"


# ------------------------------------------------------------ ⑤ 北交所不再被排除
def test_bj_is_no_longer_excluded():
    """⚠️ 2026-10-12 订正：北交所**不得**再被排除。

    原实现让 moneyflow 排除 `.BJ`，依据是「Tushare 资金流向接口不含 920xxx.BJ」——
    该前提已实测证伪（`920000/920001/920002.BJ` 等对 20260930/20261008/20261012
    各返回 1 行）。继续排除会**掩盖真实的北交所缺口**：实测 2026-10-09 / 10-12
    北交所 344 只基准里缺 253 只（覆盖率 26.5%），而 09-30 / 10-08 均为 100%。
    """
    _, sess = _check(100, 5210)
    assert sess.sqls, "未下发 SQL"
    assert "NOT LIKE '%.BJ'" not in sess.sqls[-1], (
        "北交所又被排除进 SQL 了 —— 会重新掩盖北交所缺口（依据已被证伪）"
    )
