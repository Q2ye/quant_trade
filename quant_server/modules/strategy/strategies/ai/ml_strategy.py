# -*- coding: utf-8 -*-
"""
机器学习策略
基于传统机器学习算法（如随机森林、SVM、XGBoost等）的交易策略
"""

import logging
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

from quant_server.modules.strategy.strategies.base.base_strategy import BaseStrategy
from quant_server.modules.strategy.constants import StrategyType, SignalDirection, SignalType
from quant_server.modules.strategy.models import TradingSignal
from quant_server.core.engines.types.entities import BarData

logger = logging.getLogger(__name__)


class MLStrategy(BaseStrategy):
    """
    机器学习策略类
    
    基于机器学习模型进行交易决策的策略，支持多种算法：
    - 随机森林 (Random Forest)
    - 支持向量机 (SVM)
    - XGBoost
    - 逻辑回归 (Logistic Regression)
    """

    def __init__(
        self,
        name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化机器学习策略

        Args:
            name: 策略名称
            parameters: 策略参数，包含：
                - algorithm: 使用的算法类型
                - feature_columns: 特征列名列表
                - target_column: 目标列名
                - lookback_period: 回看周期
                - prediction_horizon: 预测周期
                - confidence_threshold: 置信度阈值
        """
        super().__init__(name, StrategyType.ML, parameters)
        
        # 机器学习相关属性
        self.model = None
        self.feature_scaler = None
        self.is_model_trained = False
        
        # 数据缓存
        self.feature_data = pd.DataFrame()
        self.target_data = pd.Series()
        
        # 默认参数
        self.default_params = {
            'algorithm': 'random_forest',
            'feature_columns': ['open', 'high', 'low', 'close', 'volume'],
            'target_column': 'future_return',
            'lookback_period': 20,
            'prediction_horizon': 1,
            'confidence_threshold': 0.7,
            'min_training_samples': 100,
            'retrain_interval': 100,
        }
        
        # 更新参数
        self.parameters.update(self.default_params)
        if parameters:
            self.parameters.update(parameters)

    def on_init(self) -> None:
        """策略初始化"""
        logger.info(f"初始化机器学习策略: {self.name}")
        
        # 初始化机器学习模型
        self._initialize_model()

    def on_bar(self, bar: BarData) -> List[TradingSignal]:
        """
        处理K线数据，生成交易信号

        Args:
            bar: K线数据

        Returns:
            交易信号列表
        """
        signals = []
        
        try:
            # 更新特征数据
            self._update_feature_data(bar)
            
            # 检查是否需要重新训练模型
            if self._should_retrain():
                self._train_model()
            
            # 生成预测信号
            if self.is_model_trained and len(self.feature_data) >= self.parameters['lookback_period']:
                signal = self._generate_prediction_signal(bar)
                if signal:
                    signals.append(signal)
                    
        except Exception as e:
            logger.error(f"机器学习策略 {self.name} 处理K线数据时出错: {e}")
        
        return signals

    def _initialize_model(self) -> None:
        """初始化机器学习模型"""
        algorithm = self.parameters['algorithm']
        
        try:
            # 根据算法类型选择模型
            if algorithm == 'random_forest':
                from sklearn.ensemble import RandomForestClassifier
                self.model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=10,
                    random_state=42
                )
            elif algorithm == 'svm':
                from sklearn.svm import SVC
                self.model = SVC(probability=True, random_state=42)
            elif algorithm == 'xgboost':
                from xgboost import XGBClassifier
                self.model = XGBClassifier(random_state=42)
            elif algorithm == 'logistic_regression':
                from sklearn.linear_model import LogisticRegression
                self.model = LogisticRegression(random_state=42)
            else:
                # 默认使用随机森林
                from sklearn.ensemble import RandomForestClassifier
                self.model = RandomForestClassifier(random_state=42)
                
            # 初始化特征标准化器
            from sklearn.preprocessing import StandardScaler
            self.feature_scaler = StandardScaler()
            
            logger.info(f"初始化 {algorithm} 模型成功")
            
        except ImportError as e:
            logger.error(f"导入机器学习库失败: {e}")
            raise

    def _update_feature_data(self, bar: BarData) -> None:
        """更新特征数据"""
        # 创建当前bar的特征向量
        features = {
            'timestamp': bar.trade_time,
            'open': bar.open,
            'high': bar.high,
            'low': bar.low,
            'close': bar.close,
            'volume': bar.volume,
            'symbol': bar.ts_code
        }
        
        # 添加技术指标特征
        features.update(self._calculate_technical_features(bar))
        
        # 更新特征数据
        new_row = pd.DataFrame([features])
        self.feature_data = pd.concat([self.feature_data, new_row], ignore_index=True)
        
        # 限制数据长度
        max_length = self.parameters['lookback_period'] * 10  # 保留10倍回看周期的数据
        if len(self.feature_data) > max_length:
            self.feature_data = self.feature_data.iloc[-max_length:]

    def _calculate_technical_features(self, bar: BarData) -> Dict[str, float]:
        """计算技术指标特征"""
        features = {}
        
        # 简单移动平均
        if len(self.feature_data) >= 5:
            closes = self.feature_data['close'].tail(5)
            features['ma5'] = closes.mean()
            features['ma5_ratio'] = bar.close / features['ma5'] if features['ma5'] != 0 else 1.0
            
        if len(self.feature_data) >= 10:
            closes = self.feature_data['close'].tail(10)
            features['ma10'] = closes.mean()
            features['ma10_ratio'] = bar.close / features['ma10'] if features['ma10'] != 0 else 1.0
            
        if len(self.feature_data) >= 20:
            closes = self.feature_data['close'].tail(20)
            features['ma20'] = closes.mean()
            features['ma20_ratio'] = bar.close / features['ma20'] if features['ma20'] != 0 else 1.0
        
        # 价格波动率（基于最近20个bar）
        if len(self.feature_data) >= 20:
            recent_closes = self.feature_data['close'].tail(20)
            features['volatility'] = recent_closes.pct_change().std()
        
        # 成交量特征
        if len(self.feature_data) >= 10:
            recent_volumes = self.feature_data['volume'].tail(10)
            features['volume_ma10'] = recent_volumes.mean()
            features['volume_ratio'] = bar.volume / features['volume_ma10'] if features['volume_ma10'] != 0 else 1.0
        
        return features

    def _should_retrain(self) -> bool:
        """判断是否需要重新训练模型"""
        if not self.is_model_trained:
            return len(self.feature_data) >= self.parameters['min_training_samples']
        
        # 检查重训练间隔
        current_count = len(self.feature_data)
        last_training_count = getattr(self, '_last_training_count', 0)
        
        return current_count - last_training_count >= self.parameters['retrain_interval']

    def _train_model(self) -> None:
        """训练机器学习模型"""
        if len(self.feature_data) < self.parameters['min_training_samples']:
            logger.warning(f"数据量不足，需要至少 {self.parameters['min_training_samples']} 个样本")
            return
        
        try:
            # 准备训练数据
            X, y = self._prepare_training_data()
            
            if len(X) == 0:
                logger.warning("训练数据为空")
                return
            
            # 特征标准化
            X_scaled = self.feature_scaler.fit_transform(X)
            
            # 训练模型
            self.model.fit(X_scaled, y)
            self.is_model_trained = True
            self._last_training_count = len(self.feature_data)
            
            logger.info(f"模型训练完成，使用 {len(X)} 个样本")
            
        except Exception as e:
            logger.error(f"模型训练失败: {e}")

    def _prepare_training_data(self) -> tuple:
        """准备训练数据"""
        # 选择特征列
        feature_cols = [col for col in self.parameters['feature_columns'] 
                       if col in self.feature_data.columns]
        
        if not feature_cols:
            logger.warning("没有可用的特征列")
            return [], []
        
        # 准备特征矩阵
        X = []
        y = []
        
        lookback = self.parameters['lookback_period']
        horizon = self.parameters['prediction_horizon']
        
        for i in range(lookback, len(self.feature_data) - horizon):
            # 获取特征窗口
            features_window = self.feature_data.iloc[i-lookback:i][feature_cols].values
            
            # 展平特征窗口
            flattened_features = features_window.flatten().tolist()
            
            # 计算目标变量（未来收益率）
            current_close = self.feature_data.iloc[i]['close']
            future_close = self.feature_data.iloc[int(i + horizon)]['close']
            future_return = (future_close - current_close) / current_close
            
            # 分类标签：1表示上涨，0表示下跌
            target = 1 if future_return > 0 else 0
            
            X.append(flattened_features)
            y.append(target)
        
        return np.array(X), np.array(y)

    def _generate_prediction_signal(self, bar: BarData) -> Optional[TradingSignal]:
        """生成预测信号"""
        try:
            # 准备当前特征
            current_features = self._get_current_features()
            
            if current_features is None:
                return None
            
            # 特征标准化
            current_features_scaled = self.feature_scaler.transform([current_features])
            
            # 进行预测
            prediction = self.model.predict(current_features_scaled)[0]
            probability = self.model.predict_proba(current_features_scaled)[0]
            
            confidence = max(probability)
            
            # 检查置信度阈值
            if confidence < self.parameters['confidence_threshold']:
                return None
            
            # 生成信号
            if prediction == 1:  # 预测上涨
                direction = SignalDirection.LONG
            else:  # 预测下跌
                direction = SignalDirection.SHORT
            
            import uuid
            signal = TradingSignal(
                id=str(uuid.uuid4()),
                strategy_id=self.name,
                strategy_name=self.name,
                ts_code=bar.ts_code,
                signal_type=SignalType.ENTRY,
                direction=direction,
                price=bar.close,
                confidence=confidence,
                timestamp=bar.trade_time
            )
            
            return signal
            
        except Exception as e:
            logger.error(f"生成预测信号失败: {e}")
            return None

    def _get_current_features(self) -> Optional[np.ndarray]:
        """获取当前特征向量"""
        if len(self.feature_data) < self.parameters['lookback_period']:
            return None
        
        # 选择特征列
        feature_cols = [col for col in self.parameters['feature_columns'] 
                       if col in self.feature_data.columns]
        
        if not feature_cols:
            return None
        
        # 获取最近lookback_period个bar的特征
        recent_features = self.feature_data[feature_cols].tail(self.parameters['lookback_period']).values
        
        # 展平特征窗口
        return recent_features.flatten()

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            'algorithm': self.parameters['algorithm'],
            'is_trained': self.is_model_trained,
            'training_samples': len(self.feature_data),
            'feature_columns': self.parameters['feature_columns'],
            'model_type': type(self.model).__name__ if self.model else None
        }