# -*- coding: utf-8 -*-
"""
策略训练服务 (v1.0)
===================
将 LightGBM ETF 底部策略的离线训练逻辑从脚本迁移为可调用的服务。
支持通过 API 提交训练任务 → 后台执行 → 保存模型 artifact。

API 端点: POST /api/strategy/train/lgb
"""

import asyncio
import logging
import math
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import asyncpg
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "models"

# ── 数据库配置（从系统配置读取，这里给默认值）──
DB_CONFIG = {
    "host": "localhost", "port": 5432,
    "user": "postgres", "password": "123456",
    "database": "quant_signals_dev",
}

# ── 默认 ETF 池 ──
DEFAULT_ETF_POOL = [
    "510050.SH", "510300.SH", "510500.SH", "159919.SZ", "510880.SH",
    "512880.SH", "512660.SH", "512690.SH", "512800.SH", "512100.SH",
    "159915.SZ", "159949.SZ", "518880.SH", "513100.SH", "513050.SH",
    "511010.SH", "511260.SH", "510310.SH", "159865.SZ", "159825.SZ",
    "159766.SZ", "159781.SZ", "512170.SH", "159806.SZ", "516510.SH",
    "159840.SZ", "512400.SH",
]


class TrainingService:
    """LightGBM 策略离线训练服务"""

    def __init__(self, db_config: dict = None):
        self.db_config = db_config or DB_CONFIG
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

    async def load_features(
        self, conn: asyncpg.Connection,
        feature_codes: List[str], etf_pool: List[str],
        start: date, end: date,
    ) -> pd.DataFrame:
        """从 factor_data 加载特征矩阵"""
        etf_list = "','".join(etf_pool)
        factor_list = "','".join(feature_codes)

        rows = await conn.fetch(f"""
            SELECT ts_code, trade_date, factor_code, factor_value
            FROM factor_data
            WHERE ts_code = ANY(ARRAY['{etf_list}']::varchar[])
              AND factor_code = ANY(ARRAY['{factor_list}']::varchar[])
              AND trade_date >= $1 AND trade_date <= $2
            ORDER BY ts_code, trade_date
        """, start, end)

        data = {}
        for r in rows:
            key = (r["ts_code"], r["trade_date"])
            if key not in data:
                data[key] = {}
            v = r["factor_value"]
            data[key][r["factor_code"]] = float(v) if v is not None else np.nan

        df = pd.DataFrame.from_dict(data, orient="index")
        df.index = pd.MultiIndex.from_tuples(df.index, names=["ts_code", "trade_date"])
        df = df.reindex(columns=feature_codes)
        return df

    async def load_labels(
        self, conn: asyncpg.Connection,
        etf_pool: List[str], N: int, X: float, Y: float,
        start: date, end: date,
    ) -> pd.DataFrame:
        """从 etf_daily 构造标签"""
        etf_list = "','".join(etf_pool)
        rows = await conn.fetch(f"""
            SELECT ts_code, trade_date, high, low, close
            FROM etf_daily
            WHERE ts_code = ANY(ARRAY['{etf_list}']::varchar[])
              AND trade_date >= $1 AND trade_date <= $2
            ORDER BY ts_code, trade_date
        """, start, end)

        df = pd.DataFrame([dict(r) for r in rows])
        for c in ["high", "low", "close"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        labels = []
        for ts_code, grp in df.groupby("ts_code"):
            grp = grp.sort_values("trade_date").reset_index(drop=True)
            closes = grp["close"].values
            highs = grp["high"].values
            lows = grp["low"].values
            n = len(grp)
            for i in range(n - N):
                fh = np.max(highs[i + 1 : i + 1 + N])
                fl = np.min(lows[i + 1 : i + 1 + N])
                cur = closes[i]
                mx = (fh - cur) / cur
                mn = (fl - cur) / cur
                target = 1 if (mx >= X and mn >= Y) else 0
                labels.append({
                    "ts_code": ts_code,
                    "trade_date": grp["trade_date"].iloc[i],
                    "target": target,
                })

        return pd.DataFrame(labels)

    async def run(
        self,
        feature_set_ids: List[str] = None,
        feature_codes: List[str] = None,
        etf_pool: List[str] = None,
        label_N: int = 10,
        label_X: float = 0.03,
        label_Y: float = -0.05,
        lgb_params: dict = None,
        train_end: date = date(2022, 12, 31),
        val_end: date = date(2023, 12, 31),
        data_start: date = date(2020, 1, 1),
        data_end: date = date(2025, 6, 30),
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        执行完整训练流程，返回结果摘要。

        Args:
            feature_set_ids: 特征集ID列表（从 feature_sets 表加载 feature_codes）
            feature_codes: 直接指定特征代码（与 feature_set_ids 二选一）
            etf_pool: ETF 列表
            label_N/label_X/label_Y: 标签参数
            lgb_params: LightGBM 参数（None=使用默认值）
            train_end/val_end: 训练/验证集截止日期
            data_start/data_end: 数据日期范围
            progress_callback: callable(step, pct)

        Returns:
            Dict: {model_path, auc_val, auc_test, threshold, features_n, ...}
        """
        # 默认 LightGBM 参数
        default_lgb = {
            "objective": "binary", "metric": "auc",
            "boosting_type": "gbdt", "num_leaves": 31, "max_depth": 5,
            "learning_rate": 0.05, "n_estimators": 500,
            "subsample": 0.8, "colsample_bytree": 0.7,
            "reg_alpha": 0.5, "reg_lambda": 1.0,
            "random_state": 42, "verbosity": -1,
        }
        lgb_params = lgb_params or default_lgb
        etf_pool = etf_pool or DEFAULT_ETF_POOL

        # 解析特征代码
        if feature_codes is None and feature_set_ids:
            feature_codes = await self._load_feature_codes(feature_set_ids)
        if not feature_codes:
            raise ValueError("必须指定 feature_set_ids 或 feature_codes")

        conn = await asyncpg.connect(**self.db_config)
        try:
            # 1. 加载特征
            if progress_callback:
                progress_callback("loading_features", 0.1)
            logger.info("加载特征: %d codes × %d ETFs", len(feature_codes), len(etf_pool))
            features = await self.load_features(conn, feature_codes, etf_pool, data_start, data_end)

            # 2. 构造标签
            if progress_callback:
                progress_callback("building_labels", 0.3)
            logger.info("构造标签: N=%d, X=%.0f%%, Y=%.0f%%", label_N, label_X * 100, label_Y * 100)
            labels = await self.load_labels(conn, etf_pool, label_N, label_X, label_Y, data_start, data_end)

            # 3. 合并
            feats = features.reset_index()
            feats["trade_date"] = pd.to_datetime(feats["trade_date"])
            labels["trade_date"] = pd.to_datetime(labels["trade_date"])
            merged = feats.merge(labels, on=["ts_code", "trade_date"], how="inner")
            logger.info("合并样本: %d (正样本率 %.1f%%)", len(merged), merged["target"].mean() * 100)

            # 缺失值
            X = merged[feature_codes].copy()
            for col in feature_codes:
                X[col] = merged.groupby("ts_code")[col].transform(lambda x: x.ffill().bfill())
            X = X.fillna(X.median())
            y = merged["target"].values.astype(int)
            date_arr = pd.to_datetime(merged["trade_date"])

            # 4. 数据划分
            if progress_callback:
                progress_callback("splitting_data", 0.5)
            train_mask = date_arr.dt.date <= train_end
            val_mask = (date_arr.dt.date > train_end) & (date_arr.dt.date <= val_end)
            test_mask = date_arr.dt.date > val_end

            X_tr, y_tr = X[train_mask].values, y[train_mask]
            X_va, y_va = X[val_mask].values, y[val_mask]
            X_te, y_te = X[test_mask].values, y[test_mask]

            # 5. 标准化 + 训练
            if progress_callback:
                progress_callback("training", 0.6)
            scaler = StandardScaler()
            X_tr_s = scaler.fit_transform(X_tr)
            X_va_s = scaler.transform(X_va)

            model = lgb.LGBMClassifier(**lgb_params)
            model.fit(X_tr_s, y_tr,
                      eval_set=[(X_va_s, y_va)],
                      eval_metric="auc",
                      callbacks=[lgb.early_stopping(50)])

            # 6. 阈值优化
            proba = model.predict_proba(X_va_s)[:, 1]
            baseline = y_va.mean()
            best_t, best_score = 0.50, -np.inf
            for t in np.arange(0.30, 0.90, 0.02):
                pred = (proba >= t).astype(int)
                n = pred.sum()
                if n > 0:
                    wr = (y_va[pred == 1] == 1).mean()
                    score = (wr - baseline) * math.log(n + 1)
                    if score > best_score:
                        best_score, best_t = score, t

            # 7. 测试集评估
            if progress_callback:
                progress_callback("evaluating", 0.9)
            X_te_s = scaler.transform(X_te)
            proba_te = model.predict_proba(X_te_s)[:, 1]
            pred_te = (proba_te >= best_t).astype(int)
            n_te = pred_te.sum()
            wr_te = (y_te[pred_te == 1] == 1).mean() if n_te > 0 else 0
            auc_te = roc_auc_score(y_te, proba_te)
            logger.info("测试集: AUC=%.4f, signals=%d, win_rate=%.1f%%", auc_te, n_te, wr_te * 100)

            # 8. 保存
            today = date.today().strftime("%Y%m%d")
            model_path = MODEL_DIR / f"etf_bottom_v2_{today}.joblib"
            artifact = {
                "model": model,
                "feature_names": feature_codes,
                "scaler_params": {"mu": scaler.mean_.tolist(), "sigma": scaler.scale_.tolist()},
                "threshold": float(best_t),
                "metadata": {
                    "train_end": str(train_end), "val_end": str(val_end),
                    "auc_val": float(model.best_score_["valid_0"]["auc"]) if model.best_score_ else 0,
                    "auc_test": float(auc_te),
                    "features_n": len(feature_codes), "n_train": len(X_tr),
                    "label_N": label_N, "label_X": label_X, "label_Y": label_Y,
                },
            }
            joblib.dump(artifact, model_path)
            if progress_callback:
                progress_callback("done", 1.0)

            return {
                "model_path": str(model_path),
                "auc_val": artifact["metadata"]["auc_val"],
                "auc_test": float(auc_te),
                "threshold": float(best_t),
                "features_n": len(feature_codes),
                "n_samples": len(merged),
                "test_signals": int(n_te),
                "test_win_rate": float(wr_te),
                "feature_importance": dict(zip(
                    feature_codes,
                    model.feature_importances_.tolist() if hasattr(model, "feature_importances_") else [],
                )),
            }
        finally:
            await conn.close()

    async def _load_feature_codes(self, feature_set_ids: List[str]) -> List[str]:
        """从 feature_sets 表加载特征代码"""
        conn = await asyncpg.connect(**self.db_config)
        try:
            rows = await conn.fetch(
                "SELECT feature_columns FROM feature_sets WHERE id::text = ANY($1::text[])",
                feature_set_ids,
            )
            codes = []
            for r in rows:
                cols = r["feature_columns"]
                if isinstance(cols, list):
                    codes.extend(cols)
            return list(dict.fromkeys(codes))  # dedup, preserve order
        finally:
            await conn.close()
