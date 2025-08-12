import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


class DataPreprocessor:
    """AI策略数据预处理器"""

    def __init__(self, features, target_column='label'):
        self.features = features
        self.target_column = target_column
        self.scaler = StandardScaler()

    def preprocess(self, data):
        """
        数据预处理流程
        1. 清洗数据
        2. 特征工程
        3. 标准化
        4. 划分训练集和测试集
        """
        # 清洗数据
        cleaned = self.clean_data(data)

        # 特征工程
        engineered = self.feature_engineering(cleaned)

        # 分离特征和标签
        X = engineered[self.features]
        y = engineered[self.target_column] if self.target_column in engineered else None

        # 标准化特征
        X_scaled = self.scale_features(X)

        # 划分数据集
        if y is not None:
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y, test_size=0.2, random_state=42
            )
            return X_train, X_test, y_train, y_test
        else:
            return X_scaled

    def clean_data(self, data):
        """数据清洗"""
        # 处理缺失值
        data = data.fillna(data.mean())

        # 去除重复值
        data = data.drop_duplicates()

        # 去除极端值
        for col in data.select_dtypes(include=[np.number]).columns:
            q1 = data[col].quantile(0.25)
            q3 = data[col].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            data = data[(data[col] >= lower_bound) & (data[col] <= upper_bound)]

        return data

    def feature_engineering(self, data):
        """特征工程"""
        # 示例：添加技术指标
        # 实际应用中应根据需要添加更多特征

        # 计算简单移动平均
        if 'close' in data.columns:
            data['sma_10'] = data['close'].rolling(window=10).mean()
            data['sma_30'] = data['close'].rolling(window=30).mean()

            # 计算收益率
            data['return_5'] = data['close'].pct_change(5)

        return data

    def scale_features(self, X):
        """特征标准化"""
        return self.scaler.fit_transform(X)