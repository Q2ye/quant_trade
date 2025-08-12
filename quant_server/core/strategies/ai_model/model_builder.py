from keras import Sequential
from keras.src.layers import Dense, LSTM, Dropout
from keras.src.saving.saving_api import load_model
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from xgboost import XGBClassifier, XGBRegressor
import joblib
import logging

logger = logging.getLogger('model_builder')


class AIModelBuilder:
    """AI模型构建器"""

    def __init__(self, model_type='random_forest', task='classification'):
        self.model_type = model_type
        self.task = task
        self.model = None

    def build_model(self, input_shape=None):
        """构建模型"""
        if self.model_type == 'random_forest':
            if self.task == 'classification':
                self.model = RandomForestClassifier(
                    n_estimators=100,
                    max_depth=5,
                    random_state=42
                )
            else:
                self.model = RandomForestRegressor(
                    n_estimators=100,
                    max_depth=5,
                    random_state=42
                )
        elif self.model_type == 'xgboost':
            if self.task == 'classification':
                self.model = XGBClassifier(
                    n_estimators=100,
                    max_depth=3,
                    learning_rate=0.1,
                    random_state=42
                )
            else:
                self.model = XGBRegressor(
                    n_estimators=100,
                    max_depth=3,
                    learning_rate=0.1,
                    random_state=42
                )
        elif self.model_type == 'mlp':
            if self.task == 'classification':
                self.model = MLPClassifier(
                    hidden_layer_sizes=(64, 32),
                    activation='relu',
                    solver='adam',
                    max_iter=1000,
                    random_state=42
                )
            else:
                self.model = MLPRegressor(
                    hidden_layer_sizes=(64, 32),
                    activation='relu',
                    solver='adam',
                    max_iter=1000,
                    random_state=42
                )
        elif self.model_type == 'lstm':
            self.model = Sequential()
            self.model.add(LSTM(64, input_shape=input_shape, return_sequences=True))
            self.model.add(Dropout(0.3))
            self.model.add(LSTM(32))
            self.model.add(Dropout(0.3))
            self.model.add(Dense(16, activation='relu'))
            if self.task == 'classification':
                self.model.add(Dense(2, activation='softmax'))  # 二分类
                self.model.compile(
                    loss='categorical_crossentropy',
                    optimizer='adam',
                    metrics=['accuracy']
                )
            else:
                self.model.add(Dense(1))  # 回归
                self.model.compile(
                    loss='mse',
                    optimizer='adam'
                )
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

        logger.info(f"已构建{self.model_type}模型, 任务类型: {self.task}")
        return self.model

    def train(self, X_train, y_train):
        """训练模型"""
        if self.model_type == 'lstm':
            # 调整LSTM输入形状
            X_train = X_train.reshape(X_train.shape[0], 1, X_train.shape[1])
            self.model.fit(X_train, y_train, epochs=50, batch_size=32, verbose=0)
        else:
            self.model.fit(X_train, y_train)

    def predict(self, X):
        """预测"""
        if self.model_type == 'lstm':
            # 调整LSTM输入形状
            X = X.reshape(X.shape[0], 1, X.shape[1])
            return self.model.predict(X)
        else:
            if self.task == 'classification':
                return self.model.predict_proba(X)
            else:
                return self.model.predict(X)

    def save_model(self, model_path):
        """保存模型"""
        if self.model_type == 'lstm':
            self.model.save(model_path)
        else:
            joblib.dump(self.model, model_path)

    def load_model(self, model_path):
        """加载模型"""
        if self.model_type == 'lstm':
            self.model = load_model(model_path)
        else:
            self.model = joblib.load(model_path)