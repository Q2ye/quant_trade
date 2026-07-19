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

ETF_POOL = [
    "510050.SH", "510300.SH", "510500.SH", "159919.SZ", "510880.SH",
    "512880.SH", "512660.SH", "512690.SH", "512800.SH", "512100.SH",
    "159915.SZ", "159949.SZ", "518880.SH", "513100.SH", "513050.SH",
    "511010.SH", "511260.SH", "510310.SH", "159865.SZ", "159825.SZ",
    "159766.SZ", "159781.SZ", "512170.SH", "159806.SZ", "516510.SH",
    "159840.SZ", "512400.SH",
]

FEATURE_CODES = [
    # oversold (22)
    "drawdown_20d", "drawdown_60d", "drawdown_120d",
    "rsi_28", "rsi_low_days",
    "ma_disparity_20", "ma_disparity_60", "ma_disparity_120",
    "close_to_low_20d", "price_position_250d",
    "momentum_5d", "consecutive_down_days",
    "atr_ratio_20", "amplitude_5d", "max_dd_duration",
    "volume_shrink_5d", "volume_shrink_20d",
    "vol_decline_corr", "vol_spike_count",
    "amount_change_5d", "pct_chg_abs_mean_5d",
    "high_vol_days_5d", "boll_pct_b",
    # valuation (16)
    "pe_ttm", "pb", "pe_percentile_5y", "pb_percentile_5y",
    "pe_percentile_1y", "pb_percentile_1y",
    "erp", "total_mv_log", "turnover_rate_idx",
    "pe_region", "pb_region",
    "m_fee", "fund_age_days",
    # market_regime (5)
    "market_regime", "breadth_ratio", "trend_strength",
    "momentum_score", "volatility_pct",
]

# 标签参数 — 方案A: 年化25%
LABEL_N = 20          # 未来 20 个交易日
LABEL_X = 0.08        # 目标涨幅 8%
LABEL_Y = -0.05       # 最大回撤容忍 -5%

# 训练参数
LGB_PARAMS = {
    "objective": "binary",
    "metric": "auc",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "max_depth": 5,
    "learning_rate": 0.05,
    "n_estimators": 500,
    "subsample": 0.8,
    "colsample_bytree": 0.7,
    "reg_alpha": 0.5,
    "reg_lambda": 1.0,
    "random_state": 42,
    "verbosity": -1,
}


async def load_factor_matrix(conn: asyncpg.Connection) -> pd.DataFrame:
    """从 factor_data 加载全量特征矩阵 (ETF × trade_date × features)"""
    logger.info("加载因子数据...")
    factor_list = "','".join(FEATURE_CODES)
    etf_list = "','".join(ETF_POOL)

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
    return df


async def load_etf_future_returns(conn: asyncpg.Connection) -> pd.DataFrame:
    """加载 ETF 未来 N 日最高/最低，用于标签构造"""
    logger.info("加载未来收益数据...")
    etf_list = "','".join(ETF_POOL)

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
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(50)],
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
    logger.info("LightGBM ETF 底部策略 — 离线训练")
    logger.info("特征: %d, ETF: %d, 标签: N=%d X=%.0f%% Y=%.0f%%",
                len(FEATURE_CODES), len(ETF_POOL), LABEL_N, LABEL_X * 100, LABEL_Y * 100)

    conn = await asyncpg.connect(**DB_CONFIG)
    try:
        # 1. 加载数据
        features = await load_factor_matrix(conn)
        labels = await load_etf_future_returns(conn)

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
