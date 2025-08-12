import logging
import joblib
import os
import pandas as pd
from keras.src.saving.saving_api import load_model

from quant_server.core.strategies.ai_model.model_builder import AIModelBuilder
from quant_server.core.strategies.base_strategy import BaseStrategy
from quant_server.utils.technical_indicators import TechnicalIndicators

logger = logging.getLogger('ai_model')


class AIStrategy(BaseStrategy):
    """AI选股策略（基于机器学习模型生成信号）"""

    def __init__(self, config, main_engine=None):
        super().__init__(config, main_engine)

        # AI模型配置
        self.model_type = config['params'].get('model_type', 'random_forest')
        self.features = config['params'].get('features', ['rsi', 'macd', 'boll'])
        self.target = config['params'].get('target', 'future_return')
        self.model_path = config['params'].get('model_path', 'models/ai_model.pkl')
        self.prediction_threshold = config['params'].get('prediction_threshold', 0.7)

        # 模型构建器
        self.model_builder = AIModelBuilder(model_type=self.model_type)
        self.tech = TechnicalIndicators()
        self.model = None

        # 加载或初始化模型
        self.load_model()

        logger.info(f"AI策略初始化: {self.name}, 模型类型: {self.model_type}")

    def load_model(self):
        """加载预训练模型"""
        if os.path.exists(self.model_path):
            try:
                if self.model_type == 'lstm':
                    self.model = load_model(self.model_path)
                else:
                    self.model = joblib.load(self.model_path)
                logger.info(f"已加载预训练模型: {self.model_path}")
            except Exception as e:
                logger.error(f"加载模型失败: {str(e)}")
                self.model = None
        else:
            logger.warning(f"模型文件不存在: {self.model_path}，将在preload_data中训练新模型")

    def preload_data(self, symbols=None, days=60):
        """预加载数据并训练模型"""
        # 调用基类方法加载历史K线数据
        super().preload_data(symbols, days)

        # 如果模型未加载，则训练新模型
        if self.model is None:
            self.train_model()

    def train_model(self):
        """训练AI模型"""
        logger.info(f"开始训练{self.model_type}模型...")
        try:
            # 获取训练数据
            train_data = self.get_training_data()

            if train_data is None or train_data.empty:
                logger.error("获取训练数据失败")
                return

            # 准备特征和标签
            X = train_data[self.features]
            y = train_data[self.target]

            # 二值化标签（用于分类模型）
            if self.model_type != 'lstm':
                y = (y > 0).astype(int)

            # 构建并训练模型
            input_shape = (len(self.features),) if self.model_type != 'lstm' else (1, len(self.features))
            self.model = self.model_builder.build_model(input_shape)
            self.model_builder.train(X.values, y.values)

            # 保存模型
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            self.model_builder.save_model(self.model_path)
            logger.info(f"模型训练完成并保存到: {self.model_path}")

        except Exception as e:
            logger.error(f"模型训练失败: {str(e)}", exc_info=True)

    def get_training_data(self):
        """获取训练数据"""
        symbols = self.symbols or self.data_service.get_ashare_list()[:100]
        all_data = []

        for symbol in symbols:
            try:
                # 使用数据服务获取历史数据
                df = self.get_historical_data(symbol, days=365 * 3)  # 3年数据
                if len(df) < 100:
                    continue

                # 计算技术指标
                df['rsi'] = self.tech.rsi(df['close'], 14)
                macd, _, _ = self.tech.macd(df['close'])
                df['macd'] = macd
                _, _, lower = self.tech.bollinger_bands(df['close'])
                df['boll'] = (df['close'] - lower) / (df['close'] + 1e-5)

                # 计算标签（未来5天收益率）
                df['future_return'] = df['close'].pct_change(5).shift(-5)
                df = df.dropna()

                all_data.append(df)
            except Exception as e:
                logger.warning(f"处理{symbol}数据失败: {str(e)}")

        return pd.concat(all_data) if all_data else None

    def _generate_signals_for_live(self) -> list:
        """实盘生成信号"""
        current_data = self.get_current_data()
        if current_data is None or current_data.empty:
            return []

        # 准备预测数据
        X = current_data[self.features].values

        # 使用模型预测
        predictions = self.model_builder.predict(X)

        # 生成信号
        signals = []
        for i, (symbol, row) in enumerate(current_data.iterrows()):
            if self.model_type == 'lstm':
                buy_prob = predictions[i][0]
            elif hasattr(self.model, 'predict_proba'):
                buy_prob = predictions[i][1]  # 二分类模型的买入概率
            else:
                buy_prob = predictions[i]

            if buy_prob > self.prediction_threshold:
                signals.append(self._create_signal(
                    symbol.__str__(), "BUY",
                    f"AI预测买入概率: {buy_prob:.2%}",
                    score=buy_prob,
                    price=row['close']
                ))

        return signals

    def get_current_data(self):
        """获取当前市场数据"""
        symbols = self.symbols or self.data_service.get_ashare_list()[:500]
        current_data = []

        for symbol in symbols:
            try:
                # 使用数据服务获取最近30天数据
                df = self.get_historical_data(symbol, days=30)
                if len(df) < 30:
                    continue

                # 计算技术指标
                latest = {'symbol': symbol, 'close': df['close'].iloc[-1]}
                latest['rsi'] = self.tech.rsi(df['close'], 14).iloc[-1]

                macd, _, _ = self.tech.macd(df['close'])
                latest['macd'] = macd.iloc[-1]

                _, _, lower = self.tech.bollinger_bands(df['close'])
                latest['boll'] = (df['close'].iloc[-1] - lower.iloc[-1]) / (df['close'].iloc[-1] + 1e-5)

                current_data.append(latest)
            except Exception as e:
                logger.warning(f"获取{symbol}当前数据失败: {str(e)}")

        return pd.DataFrame(current_data).dropna() if current_data else None

    def _generate_signals_for_backtest(self, daily_data: dict, current_date: str) -> list:
        """回测生成信号"""
        signals = []
        for symbol, data in daily_data.items():
            try:
                # 获取历史数据
                # df = self.get_historical_data(symbol, end_date=current_date, days=30)
                df = self.get_historical_data(symbol, days=30)
                if len(df) < 30:
                    continue

                # 计算技术指标
                features = {}
                features['rsi'] = self.tech.rsi(df['close'], 14).iloc[-1]
                macd, _, _ = self.tech.macd(df['close'])
                features['macd'] = macd.iloc[-1]
                _, _, lower = self.tech.bollinger_bands(df['close'])
                features['boll'] = (df['close'].iloc[-1] - lower.iloc[-1]) / (df['close'].iloc[-1] + 1e-5)

                # 准备特征向量
                X = pd.DataFrame([features])[self.features].values

                # 预测
                pred = self.model_builder.predict(X)[0]

                if self.model_type == 'lstm':
                    buy_prob = pred[0]
                elif hasattr(self.model, 'predict_proba'):
                    buy_prob = pred[1]
                else:
                    buy_prob = pred

                if buy_prob > self.prediction_threshold:
                    signals.append(self._create_signal(
                        symbol, "BUY",
                        f"AI预测买入概率: {buy_prob:.2%}",
                        score=buy_prob,
                        price=data['close']
                    ))
            except Exception as e:
                logger.warning(f"处理{symbol}信号失败: {str(e)}")

        return signals