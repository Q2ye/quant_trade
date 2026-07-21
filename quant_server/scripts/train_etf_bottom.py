# -*- coding: utf-8 -*-
"""
LightGBM ETF 底部策略 — 离线训练脚本 (DEPRECATED)
=================================================
⚠️  此脚本已被 TrainingService 替代。
   推荐使用 API 端点: POST /api/strategy/train/lgb
   或直接调用: from modules.strategy.services.training_service import TrainingService

此脚本保留作为参考实现和独立调试用途。

执行:
  cd quant_server
  .venv/Scripts/python.exe scripts/train_etf_bottom.py
"""

import asyncio
import logging
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import asyncpg
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost", "port": 5432,
    "user": "postgres", "password": "123456",
    "database": "quant_signals_dev",
}

MODEL_DIR = Path(__file__).resolve().parent.parent / "storage" / "models"

# 核心池：流动性最好的宽基+行业ETF（必须包含，不受过滤影响）
CORE_ETFS = [
    "510050.SH", "510300.SH", "510500.SH", "159919.SZ", "510880.SH",
    "512880.SH", "512660.SH", "512690.SH", "512800.SH", "512100.SH",
    "159915.SZ", "159949.SZ", "518880.SH", "513100.SH", "513050.SH",
    "511010.SH", "511260.SH", "510310.SH", "159865.SZ", "159825.SZ",
    "159766.SZ", "159781.SZ", "512170.SH", "159806.SZ", "516510.SH",
    "159840.SZ", "512400.SH",
]

# 扩展池配置
ETF_POOL = None           # None=动态发现 + 核心池
ETF_MIN_VOL = 0.005       # 最低日波动率（过滤货币/债券ETF，<0.5%=不适合抄底）
ETF_MAX_POOL = 80         # 总ETF数上限（核心27 + 动态Top53）

FEATURE_CODES = [
    # ── oversold + volume/flow (36) — from OHLCV ──
    "drawdown_20d", "drawdown_60d", "drawdown_120d",
    "rsi_6", "rsi_14", "rsi_28", "rsi_low_days",
    "ma_disparity_20", "ma_disparity_60", "ma_disparity_120",
    "close_to_low_20d", "price_position_250d",
    "momentum_3d", "momentum_5d", "consecutive_down_days",
    "atr_14", "atr_ratio_20", "atr_ratio", "amplitude_5d", "max_dd_duration",
    "std_20d", "boll_width", "boll_pct_b",
    "volume_shrink_5d", "volume_shrink_20d", "volume_ma20_ratio",
    "vol_trend", "vol_decline_corr", "vol_spike_count",
    "amount_change_5d", "pct_chg_abs_mean_5d",
    "high_vol_days_5d",
    "volume_dry_up", "vwap_distance", "obv_divergence",
    # ── market_regime (5) — all 27 ETFs ──
    "market_regime", "breadth_ratio", "trend_strength",
    "momentum_score", "volatility_pct",
    # ── static (2) — all 27 ETFs ──
    "m_fee", "fund_age_days",
    # NOTE: etf_shares 因子 (share_change_*, fund_size_change_*)
    # 暂不加入 — date 对齐问题导致高 NaN 率。待数据管线完善后加入。
]

# 标签参数 — P1优化: 放宽回撤约束（底部抄底允许短暂破位，赔率优先）
LABEL_N = 10          # 未来 10 个交易日
LABEL_X = 0.05        # 目标涨幅 5%
LABEL_Y = -0.08       # 最大回撤容忍 -8%（放宽自-5%，与策略止损-5%脱钩：
                      #   标签只看"是否涨到位"，不要求路径完美；
                      #   实盘中止损-5%会提前截断，所以放宽标签条件）

# 训练参数 — v1.3: 降低复杂度 + 加强正则化 (防快速过拟合)
LGB_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "max_depth": 5,
    "learning_rate": 0.03,
    "n_estimators": 1000,
    "subsample": 0.8,
    "colsample_bytree": 0.7,
    "reg_alpha": 0.5,
    "reg_lambda": 1.0,
    "scale_pos_weight": 2.5,
    "random_state": 42,
    "verbosity": -1,
}


async def _discover_etf_pool(conn: asyncpg.Connection, min_days: int = 250) -> List[str]:
    """动态发现符合条件的 ETF 池：核心池 + 高流动性高波动 ETF。

    策略：
    1. 核心池（CORE_ETFS）始终包含
    2. 按日均成交额排序，取前 N 只高流动性 ETF
    3. 过滤日波动率 < ETF_MIN_VOL 的品种（货币/债券类无法抄底）
    4. 最终池 = 核心池 ∪ (Top流动性 ∩ 高波动)，上限 ETF_MAX_POOL
    """
    # 1. 动态发现：高流动性 + 高波动 ETF
    #    (分两层查询：先算日收益，再聚合波动率，避免窗口函数与聚合函数混用)
    rows = await conn.fetch(f"""
        WITH daily_ret AS (
            SELECT ts_code, trade_date, vol,
                   close / LAG(close) OVER (PARTITION BY ts_code ORDER BY trade_date) - 1 AS ret
            FROM etf_daily
            WHERE trade_date >= '2024-01-01'
        ),
        etf_vol AS (
            SELECT ts_code,
                   AVG(vol) AS avg_vol,
                   STDDEV(ret) AS daily_vol,
                   COUNT(*) AS n_days
            FROM daily_ret
            WHERE ret IS NOT NULL
            GROUP BY ts_code
            HAVING COUNT(*) >= 200
        ),
        etf_with_factors AS (
            SELECT f.ts_code
            FROM factor_data f
            WHERE f.factor_code = ANY(ARRAY['drawdown_20d','rsi_14','atr_14']::varchar[])
              AND f.trade_date >= '2020-01-01'
            GROUP BY f.ts_code
            HAVING COUNT(DISTINCT f.trade_date) >= {min_days}
        )
        SELECT v.ts_code, v.daily_vol, v.avg_vol, v.n_days
        FROM etf_vol v
        JOIN etf_with_factors ef ON v.ts_code = ef.ts_code
        WHERE v.daily_vol >= {ETF_MIN_VOL}
        ORDER BY v.avg_vol DESC
        LIMIT {ETF_MAX_POOL}
    """)
    dynamic_pool = [r["ts_code"] for r in rows]

    # 2. 合并核心池（去重，核心池优先）
    core_set = set(CORE_ETFS)
    pool = list(dict.fromkeys(CORE_ETFS + [e for e in dynamic_pool if e not in core_set]))

    # 3. 上限截断
    pool = pool[:ETF_MAX_POOL]

    n_core_found = len([e for e in pool if e in core_set])
    n_dynamic = len(pool) - n_core_found
    logger.info(
        "  动态发现 %d 只 ETF (核心%d + 扩展%d, 日波动>=%.1f%%, 按成交额排序)",
        len(pool), n_core_found, n_dynamic, ETF_MIN_VOL * 100
    )
    return pool


async def load_factor_matrix(conn: asyncpg.Connection) -> pd.DataFrame:
    """从 factor_data 加载全量特征矩阵 (ETF × trade_date × features)"""
    logger.info("加载因子数据...")
    factor_list = "','".join(FEATURE_CODES)

    # 动态发现 ETF 池
    etf_pool = ETF_POOL or await _discover_etf_pool(conn)

    etf_list = "','".join(etf_pool)
    rows = await conn.fetch(f"""
        SELECT ts_code, trade_date, factor_code, factor_value
        FROM factor_data
        WHERE ts_code = ANY(ARRAY['{etf_list}']::varchar[])
          AND factor_code = ANY(ARRAY['{factor_list}']::varchar[])
          AND trade_date >= '2020-01-01' AND trade_date <= '2025-12-31'
        ORDER BY ts_code, trade_date, factor_code
    """)

    # 转换为宽表 DataFrame
    data = {}
    for r in rows:
        key = (r["ts_code"], r["trade_date"])
        if key not in data:
            data[key] = {}
        data[key][r["factor_code"]] = float(r["factor_value"]) if r["factor_value"] is not None else np.nan

    df = pd.DataFrame.from_dict(data, orient="index")
    df.index = pd.MultiIndex.from_tuples(df.index, names=["ts_code", "trade_date"])
    df = df.reindex(columns=FEATURE_CODES)  # ensure column order
    logger.info("  特征矩阵: %d 行 × %d 列 (NaN ratio: %.1f%%)",
                len(df), len(FEATURE_CODES), df.isna().mean().mean() * 100)
    return df, etf_pool


async def load_etf_future_returns(conn: asyncpg.Connection, etf_pool: List[str]) -> pd.DataFrame:
    """加载 ETF 未来 N 日最高/最低，用于标签构造"""
    logger.info("加载未来收益数据...")
    etf_list = "','".join(etf_pool)

    rows = await conn.fetch(f"""
        SELECT ts_code, trade_date, high, low, close
        FROM etf_daily
        WHERE ts_code = ANY(ARRAY['{etf_list}']::varchar[])
          AND trade_date >= '2020-01-01' AND trade_date <= '2025-12-31'
        ORDER BY ts_code, trade_date
    """)

    df = pd.DataFrame([dict(r) for r in rows])
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    for c in ["high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # 计算未来 N 日最大收益/最大回撤
    labels = []
    for ts_code, grp in df.groupby("ts_code"):
        grp = grp.sort_values("trade_date").reset_index(drop=True)
        closes = grp["close"].values
        highs = grp["high"].values
        lows = grp["low"].values
        n = len(grp)
        for i in range(n - LABEL_N):
            future_high = np.max(highs[i + 1 : i + 1 + LABEL_N])
            future_low = np.min(lows[i + 1 : i + 1 + LABEL_N])
            cur_close = closes[i]
            max_ret = (future_high - cur_close) / cur_close
            max_dd = (future_low - cur_close) / cur_close
            target = 1 if (max_ret >= LABEL_X and max_dd >= LABEL_Y) else 0
            labels.append({
                "ts_code": ts_code,
                "trade_date": grp["trade_date"].iloc[i],
                "target": target,
                "max_ret": max_ret,
                "max_dd": max_dd,
            })

    label_df = pd.DataFrame(labels)
    label_df["trade_date"] = pd.to_datetime(label_df["trade_date"])
    pos_rate = label_df["target"].mean()
    logger.info("  标签: %d 条, 正样本率: %.1f%%", len(label_df), pos_rate * 100)
    return label_df


def prepare_train_data(features: pd.DataFrame, labels: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray, List[date]]:
    """合并特征 + 标签，处理缺失值"""
    logger.info("合并特征与标签...")
    # Reset multi-index to columns for merge
    feats = features.reset_index()
    # Align types: features trade_date from DB is date, labels from etf_daily is datetime
    feats["trade_date"] = pd.to_datetime(feats["trade_date"])
    labels["trade_date"] = pd.to_datetime(labels["trade_date"])
    merged = feats.merge(labels, on=["ts_code", "trade_date"], how="inner")
    logger.info("  合并后: %d 样本", len(merged))

    # 按时间排序
    merged = merged.sort_values("trade_date")

    # 缺失值填充
    X = merged[FEATURE_CODES].copy()
    # ffill per ts_code
    for col in FEATURE_CODES:
        X[col] = merged.groupby("ts_code")[col].transform(lambda x: x.ffill().bfill())
    # 全局中位数填充剩余 NaN
    X = X.fillna(X.median())

    y = merged["target"].values.astype(int)
    dates = merged["trade_date"].dt.date.tolist()

    logger.info("  特征: %s, 正样本: %d (%.1f%%)", X.shape, y.sum(), y.mean() * 100)
    return X.values, y, dates


def train_model(X_train, y_train, X_val, y_val):
    """训练 LightGBM 模型"""
    logger.info("Training LightGBM...")
    model = lgb.LGBMClassifier(**LGB_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="auc",
        callbacks=[lgb.early_stopping(100), lgb.log_evaluation(50)],
    )
    return model


def optimize_threshold(model, X_val, y_val):
    """扫描阈值，找最佳胜率/频率平衡点"""
    logger.info("阈值优化...")
    proba = model.predict_proba(X_val)[:, 1]
    baseline_rate = y_val.mean()
    logger.info("  验证集 baseline 正样本率: %.1f%%", baseline_rate * 100)
    logger.info("  预测概率分布: min=%.3f p25=%.3f p50=%.3f p75=%.3f max=%.3f",
                proba.min(), np.percentile(proba, 25), np.median(proba),
                np.percentile(proba, 75), proba.max())

    best_t, best_score = 0.50, -np.inf
    results = []
    for t in np.arange(0.30, 0.90, 0.02):
        pred = (proba >= t).astype(int)
        n_signals = pred.sum()
        if n_signals == 0:
            results.append((t, 0, 0, -np.inf))
            continue
        wr = (y_val[pred == 1] == 1).mean()
        # score = improvement over baseline × log signal count
        improvement = wr - baseline_rate
        score = improvement * math.log(n_signals + 1)
        results.append((t, n_signals, wr, score))
        if score > best_score:
            best_score = score
            best_t = t

    logger.info("  最佳阈值: %.3f (score=%.3f)", best_t, best_score)
    # Show key thresholds
    for r in [r for r in results if r[0] in np.arange(0.40, 0.80, 0.10)]:
        logger.info("    T=%.2f  signals=%4d  win_rate=%.1f%%",
                    r[0], r[1], r[2] * 100)
    return best_t


async def main():
    logger.info("=" * 56)
    logger.info("LightGBM ETF 底部策略 — 离线训练（动态 ETF 池）")
    logger.info("特征: %d, 标签: N=%d X=%.0f%% Y=%.0f%%",
                len(FEATURE_CODES), LABEL_N, LABEL_X * 100, LABEL_Y * 100)

    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        # 1. 加载数据（动态发现 ETF 池）
        features, etf_pool = await load_factor_matrix(conn)
        logger.info("ETF 池: %d 只", len(etf_pool))
        labels = await load_etf_future_returns(conn, etf_pool)

        # 2. 准备训练数据
        X, y, dates = prepare_train_data(features, labels)

        # 3. TimeSeriesSplit: train(2020-2022), val(2023), test(2024-2025H1)
        date_arr = np.array(dates)
        train_mask = date_arr <= date(2022, 12, 31)
        val_mask = (date_arr > date(2022, 12, 31)) & (date_arr <= date(2023, 12, 31))
        test_mask = date_arr > date(2023, 12, 31)

        X_train, y_train = X[train_mask], y[train_mask]
        X_val, y_val = X[val_mask], y[val_mask]
        X_test, y_test = X[test_mask], y[test_mask]

        logger.info("数据划分: train=%d val=%d test=%d",
                    len(X_train), len(X_val), len(X_test))

        # 4. 标准化
        scaler = StandardScaler()
        X_train_s = scaler.fit_transform(X_train)
        X_val_s = scaler.transform(X_val)
        X_test_s = scaler.transform(X_test)

        # 5. 训练
        model = train_model(X_train_s, y_train, X_val_s, y_val)

        # 6. 阈值优化
        best_threshold = optimize_threshold(model, X_val_s, y_val)

        # 7. 测试集评估
        proba_test = model.predict_proba(X_test_s)[:, 1]
        pred_test = (proba_test >= best_threshold).astype(int)
        n_test_signals = pred_test.sum()
        test_wr = (y_test[pred_test == 1] == 1).mean() if n_test_signals > 0 else 0
        from sklearn.metrics import roc_auc_score
        test_auc = roc_auc_score(y_test, proba_test)
        logger.info("测试集: AUC=%.4f, 信号=%d, 胜率=%.1f%%", test_auc, n_test_signals, test_wr * 100)

        # 8. 保存模型 artifact
        artifact = {
            "model": model,
            "feature_names": FEATURE_CODES,
            "scaler_params": {"mu": scaler.mean_.tolist(), "sigma": scaler.scale_.tolist()},
            "threshold": float(best_threshold),
            "metadata": {
                "train_end": "2022-12-31",
                "val_end": "2023-12-31",
                "test_end": "2025-06-30",
                "auc_val": float(model.best_score_["valid_0"]["auc"]) if model.best_score_ else 0,
                "auc_test": float(test_auc),
                "features_n": len(FEATURE_CODES),
                "n_train": len(X_train),
                "n_val": len(X_val),
            },
        }

        today_str = date.today().strftime("%Y%m%d")
        model_path = MODEL_DIR / f"etf_bottom_v1_{today_str}.joblib"
        joblib.dump(artifact, model_path)
        logger.info("✅ 模型已保存: %s", model_path)

        # 特征重要性
        importances = pd.DataFrame({
            "feature": FEATURE_CODES,
            "importance": model.feature_importances_,
        }).sort_values("importance", ascending=False)
        logger.info("Top 10 特征:")
        for _, row in importances.head(10).iterrows():
            logger.info("  %-25s %.4f", row["feature"], row["importance"])

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
