import numpy as np
import logging

from keras.src.utils import to_categorical

from .model_builder import AIModelBuilder
from .data_preprocessor import DataPreprocessor
from sklearn.metrics import accuracy_score, mean_squared_error

logger = logging.getLogger('model_trainer')


class ModelTrainer:
    """AI模型训练器"""

    def __init__(self, model_type='random_forest', task='classification'):
        self.model_type = model_type
        self.task = task  # 'classification' or 'regression'
        self.model_builder = AIModelBuilder(model_type, task)
        self.preprocessor = None

    def train(self, data, features, target, test_size=0.2):
        """训练模型"""
        logger.info(f"开始训练{self.model_type}模型, 任务类型: {self.task}")

        # 数据预处理
        self.preprocessor = DataPreprocessor(features, target)
        processed = self.preprocessor.preprocess(data)

        if len(processed) == 4:
            X_train, X_test, y_train, y_test = processed
        else:
            logger.error("数据预处理失败")
            return None

        # 构建模型
        input_shape = (len(features),) if self.model_type != 'lstm' else (30, len(features))
        model = self.model_builder.build_model(input_shape)

        # 训练模型
        if self.model_type == 'lstm':
            # 调整LSTM输入形状
            X_train = X_train.reshape(X_train.shape[0], 1, X_train.shape[1])
            X_test = X_test.reshape(X_test.shape[0], 1, X_test.shape[1])

            if self.task == 'classification':
                # 分类任务需要one-hot编码
                y_train = to_categorical(y_train)
                y_test = to_categorical(y_test)

            model.fit(X_train, y_train, epochs=50, batch_size=32, validation_data=(X_test, y_test))
        else:
            model.fit(X_train, y_train)

        # 评估模型
        self.evaluate(model, X_test, y_test)

        return model

    def evaluate(self, model, X_test, y_test):
        """评估模型性能"""
        if self.model_type == 'lstm':
            y_pred = model.predict(X_test)
            if self.task == 'classification':
                y_pred = np.argmax(y_pred, axis=1)
                y_test = np.argmax(y_test, axis=1)
        else:
            if self.task == 'classification':
                y_pred = model.predict(X_test)
            else:
                y_pred = model.predict(X_test)

        if self.task == 'classification':
            accuracy = accuracy_score(y_test, y_pred)
            logger.info(f"模型准确率: {accuracy:.2%}")
        else:
            mse = mean_squared_error(y_test, y_pred)
            logger.info(f"均方误差(MSE): {mse:.4f}")