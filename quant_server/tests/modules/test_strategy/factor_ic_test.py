# factor_ic_test.py
"""
因子 IC 测试框架

用途：对 IndustryScoringService 中 8 个子因子计算横截面 Rank IC，
验证各因子对行业未来收益的预测力。

独立脚本，不依赖策略运行。只用两样东西：
  - index_sw_daily 表（行业指数日线）
  - trade_cal 表（交易日历）

用法:
  # 方式1: 直接运行
  python -m tests.modules.test_strategy.factor_ic_test

  # 方式2: 在代码中调用
  from tests.modules.test_strategy.factor_ic_test import run_ic_test
  results = await run_ic_test()  # 返回结构化结果
"""

import asyncio
import numpy as np
import pandas as pd
import logging
import warnings
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from scipy.stats import spearmanr
from scipy.stats import ConstantInputWarning

# 抑制 scipy 在常数输入时的警告（部分因子在少数期的值完全相同）
warnings.filterwarnings("ignore", category=ConstantInputWarning)

# 注意：IndustryScoringService、DataFeedEngine 等是延迟导入的（在函数内部）
# 顶层导入会触发 modules.strategy → modules.data 链，导致
# ModuleNotFoundError: pandas_ta_classic（未安装的依赖）
# 改为在 load_industry_data() 和 run_ic_test() 内部按需导入

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ========== 配置 ==========
TEST_START = "2022-01-01"
TEST_END = "2025-12-31"
FORWARD_DAYS = [5, 10, 20]          # 测试未来 5/10/20 日收益
MIN_INDUSTRIES = 15                  # 最少有效行业数
REBALANCE_INTERVAL = 5               # 每 5 天测一次（与策略频率一致）
INDUSTRY_WARMUP_DAYS = 120           # 跳过前 N 天（需要足够数据算因子）


async def load_industry_data(
    session_factory,
    start_date: str = TEST_START,
    end_date: str = TEST_END,
) -> Dict[str, pd.DataFrame]:
    """
    从 DB 加载行业指数日线数据，按行业代码分组。

    说明：不走 DataFeedEngine（会触发 modules.strategy → modules.data 依赖链），
    直接使用 IndexSwDailyRepository 查询 index_sw_daily 表。

    返回: {行业代码: DataFrame[trade_date, close, vol, amount, pe, pb, float_mv]}
    每个 DataFrame 按 trade_date 升序排列。
    """
    from shared.database.repositories.market.fundamental.index_sw_daily_repo import (
        IndexSwDailyRepository,
    )

    # 申万一级行业代码（31 个，直接内联避免 modules.strategy → modules.data 依赖链）
    SW_INDUSTRY_CODES = [
        "801010.SI", "801030.SI", "801040.SI", "801050.SI", "801080.SI",
        "801110.SI", "801120.SI", "801130.SI", "801140.SI", "801150.SI",
        "801160.SI", "801170.SI", "801180.SI", "801200.SI", "801210.SI",
        "801230.SI", "801710.SI", "801720.SI", "801730.SI", "801740.SI",
        "801750.SI", "801760.SI", "801770.SI", "801780.SI", "801790.SI",
        "801880.SI", "801890.SI", "801950.SI", "801970.SI", "801980.SI",
    ]

    async with session_factory() as db:
        repo = IndexSwDailyRepository(db)
        df = await repo.get_batch_by_industry_codes(
            industry_codes=SW_INDUSTRY_CODES,
            start_date=start_date,
            end_date=end_date,
        )

    if df.empty:
        logger.error(f"未加载到行业指数数据 ({start_date} ~ {end_date})")
        return {}

    # 关键修复：index_sw_daily 表 numeric 列从 PG 返回 decimal.Decimal，
    # 需转为 float64 否则 IndustryScoringService 的算数运算会报错
    numeric_cols = ["close", "vol", "amount", "pe", "pb", "float_mv", "pct_change", "open", "high", "low"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype(np.float64)

    industry_data: Dict[str, pd.DataFrame] = {}
    for ts_code in df["ts_code"].unique():
        sub = df[df["ts_code"] == ts_code].copy()
        sub = sub.sort_values("trade_date").reset_index(drop=True)
        # 确保必要字段存在
        for col in ["vol", "amount", "pe", "pb", "float_mv"]:
            if col not in sub.columns:
                sub[col] = 0.0
        industry_data[ts_code] = sub

    logger.info(
        f"行业数据加载完成: {len(industry_data)} 个行业, "
        f"{min(len(v) for v in industry_data.values())}~{max(len(v) for v in industry_data.values())} 行"
    )
    return industry_data


def _get_trade_dates(industry_data: Dict[str, pd.DataFrame]) -> List[date]:
    """取所有行业共有的交易日，返回升序列表"""
    date_sets = [set(df["trade_date"].values) for df in industry_data.values()]
    common = set.intersection(*date_sets) if date_sets else set()
    dates = sorted(common)
    logger.info(f"共有的交易日: {len(dates)} 天 (跳过前 {INDUSTRY_WARMUP_DAYS} 天用于因子计算)")
    return dates


def _rank_ic(
    factor_values: Dict[str, float],
    forward_returns: Dict[str, float],
) -> Optional[float]:
    """计算横截面 Rank IC (Spearman)"""
    common = [k for k in factor_values if k in forward_returns]
    if len(common) < 10:
        return None
    fv = np.array([factor_values[k] for k in common])
    fr = np.array([forward_returns[k] for k in common])
    with np.errstate(invalid="ignore"):
        corr, _ = spearmanr(fv, fr)
    return float(corr) if not np.isnan(corr) else None


async def run_ic_test(
    session_factory=None,
    industry_data: Optional[Dict[str, pd.DataFrame]] = None,
    verbose: bool = True,
) -> Dict[str, dict]:
    """
    执行因子 IC 测试。

    Args:
        session_factory: DB 会话工厂（industry_data 为 None 时使用）
        industry_data: 预加载的行业数据（可选，避免重复加载）
        verbose: 是否打印结果

    Returns:
        {因子名: {forward_days: [IC 值列表]}}
    """
    # 延迟导入（使用 importlib 绕过 modules.strategy/__init__.py，
    # 因为 __init__.py 会引入 engines → strategy_manager → modules.data → pandas_ta_classic）
    # IndustryScoringService 自身不依赖 modules.strategy 包，可以直加载文件。
    import importlib.util as _importlib_util
    import os as _os
    _scoring_path = _os.path.join(
        _os.path.dirname(__file__),
        "..", "..", "..",
        "modules", "strategy", "services", "industry_scoring_service.py",
    )
    _spec = _importlib_util.spec_from_file_location("industry_scoring_service", _os.path.abspath(_scoring_path))
    _mod = _importlib_util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    IndustryScoringService = _mod.IndustryScoringService
    ScoringConfig = _mod.ScoringConfig

    # ===== 1. 加载数据 =====
    if industry_data is None:
        if session_factory is None:
            # 尝试自动获取 session_factory
            from shared.database.session.connection_pool import get_connection_pool
            session_factory = get_connection_pool().get_session_factory()
        industry_data = await load_industry_data(session_factory)

    if not industry_data or len(industry_data) < 10:
        logger.error(f"行业数据不足: {len(industry_data) if industry_data else 0} 个行业")
        return {}

    # ===== 2. 构建评分服务（用策略当前参数） =====
    cfg = ScoringConfig(
        momentum_windows=[10, 30, 60],
        momentum_weights=[0.40, 0.35, 0.25],
        momentum_accel_short=10,
        momentum_accel_long=30,
        rs_window=30,
        vol_ratio_short=5,
        vol_ratio_long=60,
        vol_price_window=20,
        pe_percentile_years=5,
        pb_percentile_years=5,
    )
    service = IndustryScoringService(cfg)

    # ===== 3. 确定测试日期 =====
    all_dates = _get_trade_dates(industry_data)
    test_dates = all_dates[INDUSTRY_WARMUP_DAYS::REBALANCE_INTERVAL]
    logger.info(f"测试日期数: {len(test_dates)} (每 {REBALANCE_INTERVAL} 天一次)")

    # ===== 4. 逐期计算 IC =====
    # results[因子名][forward_days] = [ic1, ic2, ...]
    results: Dict[str, Dict[int, List[float]]] = {
        f: {n: [] for n in FORWARD_DAYS}
        for f in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]
    }

    for t_idx, t_date in enumerate(test_dates):
        if verbose and t_idx % 50 == 0:
            logger.info(f"进度: {t_idx}/{len(test_dates)} (date={t_date})")

        # 构建截至 t_date 的子数据（至少 60 天）
        sub_data: Dict[str, pd.DataFrame] = {}
        for code, df in industry_data.items():
            mask = df["trade_date"] <= t_date
            sub = df[mask].tail(250)
            if len(sub) >= 60:
                sub_data[code] = sub

        if len(sub_data) < MIN_INDUSTRIES:
            continue

        # 计算因子值
        try:
            scores = service.score_all(
                industry_data=sub_data,
                benchmark_prices=None,  # A3 不使用基准（非策略模式）
            )
        except Exception as e:
            logger.debug(f"评分异常 (t={t_date}): {e}")
            continue

        if not scores:
            continue

        # 提取各行业各子因子的原始值（归一化前）
        factor_raw: Dict[str, Dict[str, float]] = {}
        for s in scores:
            factor_raw[s.industry_code] = {
                "A1": s.factors.get("A1", 0.0),
                "A2": s.factors.get("A2", 0.0),
                "A3": s.factors.get("A3", 0.0),
                "B1": s.factors.get("B1", 0.0),
                "B2": s.factors.get("B2", 0.0),
                "B3": s.factors.get("B3", 0.0),
                "C1": s.factors.get("C1", 0.0),
                "C2": s.factors.get("C2", 0.0),
            }

        # 对未来每个窗口计算 IC
        for n in FORWARD_DAYS:
            fwd_rets: Dict[str, float] = {}
            for code, df in industry_data.items():
                if code not in sub_data:
                    continue
                mask = df["trade_date"] > t_date
                future = df[mask].head(n)
                if len(future) < max(3, n // 2):
                    continue
                close_t = sub_data[code]["close"].iloc[-1]
                if close_t <= 0:
                    continue
                ret = future["close"].iloc[-1] / close_t - 1
                fwd_rets[code] = ret

            for fname in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]:
                factor_vals = {
                    c: factor_raw[c][fname] for c in factor_raw if c in fwd_rets
                }
                if len(factor_vals) < MIN_INDUSTRIES:
                    continue
                ic = _rank_ic(factor_vals, fwd_rets)
                if ic is not None:
                    results[fname][n].append(ic)

    # ===== 5. 输出结果 =====
    _print_results(results)

    return results


def _print_results(results: Dict[str, Dict[int, List[float]]]) -> None:
    """打印结构化结果"""
    print(f"\n{'='*85}")
    print(f"  因子 IC 测试结果")
    print(f"  测试区间: {TEST_START} ~ {TEST_END}  |  每 {REBALANCE_INTERVAL} 天测试一次")
    print(f"  评分配置: 动量窗口=[10,30,60]  RS窗口=30  量价窗口=[5,60,20]")
    print(f"{'='*85}")
    print(f"{'因子':>6} {'窗口':>4} {'Mean IC':>9} {'Std IC':>9} {'IC_IR':>9} {'Win%':>7} {'T值':>8} {'样本':>6}")
    print(f"{'-'*85}")

    factor_labels = {
        "A1": "动量", "A2": "加速度", "A3": "相对强弱",
        "B1": "量比", "B2": "价量配合", "B3": "换手",
        "C1": "PE分位", "C2": "PB分位",
    }

    # 调试：打印各因子原始 IC 样本数
    for fname in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]:
        for n in FORWARD_DAYS:
            cnt = len(results.get(fname, {}).get(n, []))
            if cnt > 0:
                logger.info(f"  IC 样本: {fname} N={n}d -> {cnt} 个")

    for fname in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]:
        label = factor_labels.get(fname, fname)
        for n in FORWARD_DAYS:
            arr = np.array(results[fname][n])
            if len(arr) < 5:
                print(f"  {label:>6s} {n:>4}d  {'-- 数据不足':<20s}")
                continue
            mean_ic = float(np.mean(arr))
            std_ic = float(np.std(arr, ddof=1))
            ic_ir = mean_ic / std_ic if std_ic > 0 else 0.0
            win = float(np.mean(arr > 0))

            # 单样本 t 检验：IC 是否显著不为 0
            se = std_ic / np.sqrt(len(arr))
            t_stat = mean_ic / se if se > 0 else 0.0

            # 星级标记
            star = ""
            if mean_ic > 0.06 and ic_ir > 0.6:
                star = " ★"
            elif mean_ic > 0.03 and ic_ir > 0.3:
                star = " ☆"

            print(
                f"  {label:>6s} {n:>4}d "
                f"{mean_ic:>9.4f} {std_ic:>9.4f} {ic_ir:>9.3f} "
                f"{win:>6.1%} {t_stat:>8.2f} {len(arr):>6}"
                f"{star}"
            )

    print(f"{'='*85}")
    print(f"  图例:  # 强因子(IC>0.06 & IC_IR>0.6)  ^ 有效因子(IC>0.03 & IC_IR>0.3)")
    print(f"         C类(估值)预期较弱，验证是否可安全移除")
    print(f"{'='*85}\n")


async def main():
    """入口函数"""
    logger.info("因子 IC 测试开始...")
    t0 = datetime.now()

    # 初始化数据库连接（支持独立运行 + 系统运行两种模式）
    from shared.database.session.connection_pool import get_connection_pool

    pool = get_connection_pool()
    try:
        # 模式1: 系统已在运行，连接池已就绪
        sf = pool.get_session_factory()
    except RuntimeError:
        # 模式2: 独立运行，手动初始化连接池
        logger.info("连接池未初始化，执行手动初始化...")
        ok = await pool.initialize()
        if not ok:
            logger.error("数据库连接池初始化失败")
            return
        sf = pool.get_session_factory()
        logger.info("数据库连接池初始化成功（独立模式）")

    results = await run_ic_test(session_factory=sf)

    elapsed = (datetime.now() - t0).total_seconds()
    logger.info(f"因子 IC 测试完成, 耗时 {elapsed:.1f}s")

    # 简要汇总
    print("\n>>> 结论速览 <<<")
    for fname in ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2"]:
        best_n = max(
            FORWARD_DAYS,
            key=lambda n: np.mean(results[fname][n]) if len(results[fname][n]) >= 5 else -999,
            default=10,
        )
        arr = results[fname][best_n]
        if len(arr) >= 5:
            mean_ic = float(np.mean(arr))
            if mean_ic > 0.05:
                print(f"  [+] {fname}: Mean IC={mean_ic:.4f} (N={best_n}d) -- 有效因子")
            elif mean_ic > 0.02:
                print(f"  [?] {fname}: Mean IC={mean_ic:.4f} (N={best_n}d) -- 弱因子")
            else:
                print(f"  [x] {fname}: Mean IC={mean_ic:.4f} (N={best_n}d) -- 无效因子")
        else:
            print(f"  [x] {fname}: 数据不足")


if __name__ == "__main__":
    asyncio.run(main())
