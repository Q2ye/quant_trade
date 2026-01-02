"""
数据采样器 - 提供数据采样、重采样和数据集划分功能

职责：
1. 时间序列重采样（升采样、降采样）
2. 随机采样（简单随机采样、分层采样、过采样、欠采样）
3. 交叉验证数据集划分
4. 时间序列数据集划分（时间顺序敏感）
5. 滚动窗口采样（用于时间序列预测）
6. 引导法采样（Bootstrap Sampling）

设计原则：
1. 可配置：采样参数可灵活配置
2. 可重现：支持随机种子设置，确保结果可重现
3. 高性能：支持大数据集的高效采样
4. 内存友好：支持流式采样和生成器模式
5. 统计有效：确保采样方法的统计有效性
"""

import random
import warnings
from abc import ABC, abstractmethod
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple, Union, Callable, Generator

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, StratifiedKFold, TimeSeriesSplit
from sklearn.model_selection import train_test_split as sk_train_test_split


class SamplingMethod(Enum):
    """采样方法枚举"""
    RANDOM = "random"  # 简单随机采样
    SYSTEMATIC = "systematic"  # 系统采样
    STRATIFIED = "stratified"  # 分层采样
    CLUSTER = "cluster"  # 整群采样
    BOOTSTRAP = "bootstrap"  # 引导法采样
    OVERSAMPLING = "oversampling"  # 过采样
    UNDERSAMPLING = "undersampling"  # 欠采样
    SMOTE = "smote"  # SMOTE过采样
    TIME_SERIES = "time_series"  # 时间序列采样
    ROLLING_WINDOW = "rolling_window"  # 滚动窗口采样


class SamplingStrategy(Enum):
    """采样策略枚举"""
    WITH_REPLACEMENT = "with_replacement"  # 有放回采样
    WITHOUT_REPLACEMENT = "without_replacement"  # 无放回采样


@dataclass
class SamplingResult:
    """采样结果数据结构"""
    method: SamplingMethod  # 采样方法
    strategy: SamplingStrategy  # 采样策略
    sample_indices: List[int]  # 样本索引
    population_indices: List[int]  # 总体索引
    sample_size: int  # 样本大小
    population_size: int  # 总体大小
    sampling_rate: float  # 采样率
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    timestamp: datetime = field(default_factory=datetime.now)  # 采样时间

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "method": self.method.value,
            "events": self.strategy.value,
            "sample_indices": self.sample_indices,
            "population_indices": self.population_indices,
            "sample_size": self.sample_size,
            "population_size": self.population_size,
            "sampling_rate": self.sampling_rate,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }

    def get_sample_data(self, data: List[Any]) -> List[Any]:
        """根据索引获取样本数据"""
        return [data[i] for i in self.sample_indices]

    def get_population_data(self, data: List[Any]) -> List[Any]:
        """根据索引获取总体数据"""
        return [data[i] for i in self.population_indices]


@dataclass
class ResamplingResult:
    """重采样结果数据结构（时间序列）"""
    original_freq: str  # 原始频率
    target_freq: str  # 目标频率
    resampling_method: str  # 重采样方法
    original_size: int  # 原始数据大小
    resampled_size: int  # 重采样后大小
    resampled_data: pd.DataFrame  # 重采样后的数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    timestamp: datetime = field(default_factory=datetime.now)  # 重采样时间

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "original_freq": self.original_freq,
            "target_freq": self.target_freq,
            "resampling_method": self.resampling_method,
            "original_size": self.original_size,
            "resampled_size": self.resampled_size,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


class DataSampler(ABC):
    """数据采样器基类"""

    def __init__(self, method: SamplingMethod,
                 strategy: SamplingStrategy = SamplingStrategy.WITHOUT_REPLACEMENT,
                 random_seed: Optional[int] = None):
        """
        初始化数据采样器

        Args:
            method: 采样方法
            strategy: 采样策略
            random_seed: 随机种子
        """
        self.method = method
        self.strategy = strategy
        self.random_seed = random_seed

        if random_seed is not None:
            np.random.seed(random_seed)
            random.seed(random_seed)

    @abstractmethod
    def sample(self, data: List[Any], sample_size: int, **kwargs) -> SamplingResult:
        """
        执行采样

        Args:
            data: 原始数据列表
            sample_size: 样本大小
            **kwargs: 额外参数

        Returns:
            SamplingResult: 采样结果
        """
        pass

    def create_generator(self, data: List[Any], sample_size: int,
                         num_samples: int = 1, **kwargs) -> Generator[SamplingResult, None, None]:
        """
        创建采样生成器（用于多次采样）

        Args:
            data: 原始数据列表
            sample_size: 样本大小
            num_samples: 采样次数
            **kwargs: 额外参数

        Yields:
            SamplingResult: 采样结果
        """
        for i in range(num_samples):
            # 每次采样使用不同的随机种子
            if self.random_seed is not None:
                current_seed = self.random_seed + i
                np.random.seed(current_seed)
                random.seed(current_seed)

            yield self.sample(data, sample_size, **kwargs)


class RandomSampler(DataSampler):
    """随机采样器"""

    def __init__(self, strategy: SamplingStrategy = SamplingStrategy.WITHOUT_REPLACEMENT,
                 random_seed: Optional[int] = None):
        """
        初始化随机采样器

        Args:
            strategy: 采样策略
            random_seed: 随机种子
        """
        super().__init__(SamplingMethod.RANDOM, strategy, random_seed)

    def sample(self, data: List[Any], sample_size: int, **kwargs) -> SamplingResult:
        """
        执行随机采样

        Args:
            data: 原始数据列表
            sample_size: 样本大小
            **kwargs: 额外参数

        Returns:
            SamplingResult: 采样结果
        """
        population_size = len(data)

        if sample_size > population_size:
            raise ValueError(f"样本大小 {sample_size} 大于总体大小 {population_size}")

        if self.strategy == SamplingStrategy.WITHOUT_REPLACEMENT:
            # 无放回采样
            if sample_size == population_size:
                # 如果样本大小等于总体大小，返回所有数据
                indices = list(range(population_size))
            else:
                indices = random.sample(range(population_size), sample_size)
        else:
            # 有放回采样
            indices = [random.randint(0, population_size - 1) for _ in range(sample_size)]

        # 计算采样率
        sampling_rate = sample_size / population_size

        return SamplingResult(
            method=self.method,
            strategy=self.strategy,
            sample_indices=indices,
            population_indices=list(range(population_size)),
            sample_size=sample_size,
            population_size=population_size,
            sampling_rate=sampling_rate,
            metadata={"data_type": type(data[0]).__name__ if data else "unknown"}
        )


class StratifiedSampler(DataSampler):
    """分层采样器"""

    def __init__(self, strata_column: str = None,
                 strategy: SamplingStrategy = SamplingStrategy.WITHOUT_REPLACEMENT,
                 random_seed: Optional[int] = None):
        """
        初始化分层采样器

        Args:
            strata_column: 分层列名（对于DataFrame）
            strategy: 采样策略
            random_seed: 随机种子
        """
        super().__init__(SamplingMethod.STRATIFIED, strategy, random_seed)
        self.strata_column = strata_column

    def sample(self, data: Union[List[Any], pd.DataFrame], sample_size: int,
               **kwargs) -> SamplingResult:
        """
        执行分层采样

        Args:
            data: 原始数据（列表或DataFrame）
            sample_size: 样本大小
            **kwargs: 额外参数

        Returns:
            SamplingResult: 采样结果
        """
        # 确定分层列
        strata_column = kwargs.get('strata_column', self.strata_column)

        if isinstance(data, pd.DataFrame):
            return self._sample_dataframe(data, sample_size, strata_column)
        else:
            # 对于列表数据，需要提供标签
            labels = kwargs.get('labels')
            if labels is None:
                raise ValueError("对于列表数据，必须提供labels参数")

            return self._sample_list(data, sample_size, labels)

    def _sample_dataframe(self, df: pd.DataFrame, sample_size: int,
                          strata_column: str) -> SamplingResult:
        """从DataFrame执行分层采样"""
        population_size = len(df)

        if sample_size > population_size:
            raise ValueError(f"样本大小 {sample_size} 大于总体大小 {population_size}")

        # 获取分层列的唯一值
        strata_values = df[strata_column].unique()

        # 计算每层的样本数（按比例分配）
        strata_counts = df[strata_column].value_counts()
        strata_sample_sizes = {}

        for value in strata_values:
            strata_population = strata_counts[value]
            strata_proportion = strata_population / population_size
            strata_sample_size = int(sample_size * strata_proportion)
            strata_sample_sizes[value] = max(1, strata_sample_size)  # 每层至少一个样本

        # 调整样本数以匹配目标样本大小
        total_allocated = sum(strata_sample_sizes.values())
        if total_allocated != sample_size:
            # 调整样本数（增加或减少最大层的样本数）
            diff = sample_size - total_allocated
            if diff > 0:
                # 增加最大层的样本数
                max_stratum = max(strata_sample_sizes, key=strata_sample_sizes.get)
                strata_sample_sizes[max_stratum] += diff
            else:
                # 减少最大层的样本数
                max_stratum = max(strata_sample_sizes, key=strata_sample_sizes.get)
                strata_sample_sizes[max_stratum] = max(1, strata_sample_sizes[max_stratum] + diff)

        # 执行分层采样
        sampled_indices = []

        for value in strata_values:
            stratum_df = df[df[strata_column] == value]
            stratum_size = len(stratum_df)
            stratum_sample_size = strata_sample_sizes[value]

            if self.strategy == SamplingStrategy.WITHOUT_REPLACEMENT:
                if stratum_sample_size >= stratum_size:
                    # 如果样本大小大于等于层大小，取全部
                    stratum_indices = list(stratum_df.index)
                else:
                    # 无放回采样
                    stratum_indices = random.sample(list(stratum_df.index), stratum_sample_size)
            else:
                # 有放回采样
                stratum_indices = [
                    random.choice(list(stratum_df.index))
                    for _ in range(stratum_sample_size)
                ]

            sampled_indices.extend(stratum_indices)

        # 计算采样率
        sampling_rate = sample_size / population_size

        # 收集元数据
        metadata = {
            "strata_column": strata_column,
            "strata_values": list(strata_values),
            "strata_sample_sizes": strata_sample_sizes,
            "data_type": "DataFrame"
        }

        return SamplingResult(
            method=self.method,
            strategy=self.strategy,
            sample_indices=sampled_indices,
            population_indices=list(df.index),
            sample_size=len(sampled_indices),
            population_size=population_size,
            sampling_rate=sampling_rate,
            metadata=metadata
        )

    def _sample_list(self, data: List[Any], sample_size: int,
                     labels: List[Any]) -> SamplingResult:
        """从列表执行分层采样"""
        population_size = len(data)

        if len(labels) != population_size:
            raise ValueError("labels长度必须与data长度相同")

        if sample_size > population_size:
            raise ValueError(f"样本大小 {sample_size} 大于总体大小 {population_size}")

        # 将数据和标签组合
        combined = list(zip(data, labels, range(population_size)))

        # 按标签分组
        strata_dict = defaultdict(list)
        for item, label, idx in combined:
            strata_dict[label].append((item, idx))

        # 计算每层的样本数（按比例分配）
        strata_sample_sizes = {}
        for label, items in strata_dict.items():
            strata_population = len(items)
            strata_proportion = strata_population / population_size
            strata_sample_size = int(sample_size * strata_proportion)
            strata_sample_sizes[label] = max(1, strata_sample_size)

        # 调整样本数
        total_allocated = sum(strata_sample_sizes.values())
        if total_allocated != sample_size:
            diff = sample_size - total_allocated
            if diff > 0:
                max_label = max(strata_sample_sizes, key=strata_sample_sizes.get)
                strata_sample_sizes[max_label] += diff
            else:
                max_label = max(strata_sample_sizes, key=strata_sample_sizes.get)
                strata_sample_sizes[max_label] = max(1, strata_sample_sizes[max_label] + diff)

        # 执行分层采样
        sampled_indices = []

        for label, items in strata_dict.items():
            stratum_sample_size = strata_sample_sizes[label]

            if self.strategy == SamplingStrategy.WITHOUT_REPLACEMENT:
                if stratum_sample_size >= len(items):
                    # 取全部
                    stratum_indices = [idx for _, idx in items]
                else:
                    # 无放回采样
                    sampled_items = random.sample(items, stratum_sample_size)
                    stratum_indices = [idx for _, idx in sampled_items]
            else:
                # 有放回采样
                stratum_indices = [
                    random.choice(items)[1]
                    for _ in range(stratum_sample_size)
                ]

            sampled_indices.extend(stratum_indices)

        # 计算采样率
        sampling_rate = sample_size / population_size

        # 收集元数据
        metadata = {
            "strata_labels": list(strata_dict.keys()),
            "strata_sample_sizes": strata_sample_sizes,
            "data_type": "List"
        }

        return SamplingResult(
            method=self.method,
            strategy=self.strategy,
            sample_indices=sampled_indices,
            population_indices=list(range(population_size)),
            sample_size=len(sampled_indices),
            population_size=population_size,
            sampling_rate=sampling_rate,
            metadata=metadata
        )


class TimeSeriesSampler(DataSampler):
    """时间序列采样器"""

    def __init__(self, date_column: str = None,
                 random_seed: Optional[int] = None):
        """
        初始化时间序列采样器

        Args:
            date_column: 日期列名（对于DataFrame）
            random_seed: 随机种子
        """
        super().__init__(SamplingMethod.TIME_SERIES,
                         SamplingStrategy.WITHOUT_REPLACEMENT,
                         random_seed)
        self.date_column = date_column

    def sample(self, data: Union[List[Any], pd.DataFrame], sample_size: int,
               **kwargs) -> SamplingResult:
        """
        执行时间序列采样（按时间顺序采样）

        Args:
            data: 原始数据
            sample_size: 样本大小
            **kwargs: 额外参数

        Returns:
            SamplingResult: 采样结果
        """
        date_column = kwargs.get('date_column', self.date_column)

        if isinstance(data, pd.DataFrame):
            return self._sample_dataframe(data, sample_size, date_column)
        else:
            # 对于列表数据，需要提供日期
            dates = kwargs.get('dates')
            if dates is None:
                raise ValueError("对于列表数据，必须提供dates参数")

            return self._sample_list(data, sample_size, dates)

    def _sample_dataframe(self, df: pd.DataFrame, sample_size: int,
                          date_column: str) -> SamplingResult:
        """从DataFrame执行时间序列采样"""
        population_size = len(df)

        if sample_size > population_size:
            raise ValueError(f"样本大小 {sample_size} 大于总体大小 {population_size}")

        # 确保数据按时间排序
        if date_column:
            df_sorted = df.sort_values(date_column)
        else:
            df_sorted = df

        # 时间序列采样通常取最近的数据
        sampled_indices = list(df_sorted.index)[-sample_size:]

        # 计算采样率
        sampling_rate = sample_size / population_size

        # 收集元数据
        metadata = {
            "date_column": date_column,
            "sampling_type": "most_recent",
            "data_type": "DataFrame"
        }

        return SamplingResult(
            method=self.method,
            strategy=self.strategy,
            sample_indices=sampled_indices,
            population_indices=list(df.index),
            sample_size=sample_size,
            population_size=population_size,
            sampling_rate=sampling_rate,
            metadata=metadata
        )

    def _sample_list(self, data: List[Any], sample_size: int,
                     dates: List[datetime]) -> SamplingResult:
        """从列表执行时间序列采样"""
        population_size = len(data)

        if len(dates) != population_size:
            raise ValueError("dates长度必须与data长度相同")

        if sample_size > population_size:
            raise ValueError(f"样本大小 {sample_size} 大于总体大小 {population_size}")

        # 将数据、日期和索引组合并排序
        combined = list(zip(data, dates, range(population_size)))
        combined_sorted = sorted(combined, key=lambda x: x[1])  # 按日期排序

        # 取最近的数据
        sampled_combined = combined_sorted[-sample_size:]
        sampled_indices = [idx for _, _, idx in sampled_combined]

        # 计算采样率
        sampling_rate = sample_size / population_size

        # 收集元数据
        metadata = {
            "sampling_type": "most_recent",
            "data_type": "List",
            "date_range": {
                "start": min(dates).isoformat(),
                "end": max(dates).isoformat()
            }
        }

        return SamplingResult(
            method=self.method,
            strategy=self.strategy,
            sample_indices=sampled_indices,
            population_indices=list(range(population_size)),
            sample_size=sample_size,
            population_size=population_size,
            sampling_rate=sampling_rate,
            metadata=metadata
        )


class RollingWindowSampler:
    """滚动窗口采样器（用于时间序列预测）"""

    def __init__(self, window_size: int, forecast_horizon: int = 1,
                 step_size: int = 1):
        """
        初始化滚动窗口采样器

        Args:
            window_size: 窗口大小（历史数据点数）
            forecast_horizon: 预测步长
            step_size: 步长（窗口移动的步长）
        """
        self.window_size = window_size
        self.forecast_horizon = forecast_horizon
        self.step_size = step_size

    def create_windows(self, data: List[Any]) -> List[Tuple[List[Any], Any]]:
        """
        创建滚动窗口

        Args:
            data: 时间序列数据

        Returns:
            List[Tuple[List[Any], Any]]: 窗口列表，每个窗口包含（历史数据，目标值）
        """
        n = len(data)
        windows = []

        for i in range(0, n - self.window_size - self.forecast_horizon + 1, self.step_size):
            window_start = i
            window_end = i + self.window_size
            target_index = window_end + self.forecast_horizon - 1

            if target_index < n:
                X = data[window_start:window_end]
                y = data[target_index]
                windows.append((X, y))

        return windows

    def create_multi_output_windows(self, data: List[Any]) -> List[Tuple[List[Any], List[Any]]]:
        """
        创建多输出滚动窗口

        Args:
            data: 时间序列数据

        Returns:
            List[Tuple[List[Any], List[Any]]]: 窗口列表，每个窗口包含（历史数据，目标序列）
        """
        n = len(data)
        windows = []

        for i in range(0, n - self.window_size - self.forecast_horizon + 1, self.step_size):
            window_start = i
            window_end = i + self.window_size
            target_start = window_end
            target_end = window_end + self.forecast_horizon

            if target_end <= n:
                X = data[window_start:window_end]
                y = data[target_start:target_end]
                windows.append((X, y))

        return windows

    def create_windows_with_features(self, df: pd.DataFrame,
                                     feature_columns: List[str],
                                     target_column: str,
                                     date_column: str = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        从DataFrame创建特征窗口

        Args:
            df: 包含特征的DataFrame
            feature_columns: 特征列名列表
            target_column: 目标列名
            date_column: 日期列名（用于排序）

        Returns:
            Tuple[np.ndarray, np.ndarray]: 特征数组和目标数组
        """
        # 确保数据按时间排序
        if date_column and date_column in df.columns:
            df_sorted = df.sort_values(date_column)
        else:
            df_sorted = df

        n = len(df_sorted)
        X_list = []
        y_list = []

        for i in range(0, n - self.window_size - self.forecast_horizon + 1, self.step_size):
            window_start = i
            window_end = i + self.window_size
            target_index = window_end + self.forecast_horizon - 1

            if target_index < n:
                # 特征窗口（多行特征）
                X_window = df_sorted.iloc[window_start:window_end][feature_columns].values
                # 目标值
                y_value = df_sorted.iloc[target_index][target_column]

                X_list.append(X_window)
                y_list.append(y_value)

        return np.array(X_list), np.array(y_list)


class BootstrapSampler(DataSampler):
    """引导法采样器"""

    def __init__(self, num_bootstrap_samples: int = 1000,
                 random_seed: Optional[int] = None):
        """
        初始化引导法采样器

        Args:
            num_bootstrap_samples: 引导样本数量
            random_seed: 随机种子
        """
        super().__init__(SamplingMethod.BOOTSTRAP,
                         SamplingStrategy.WITH_REPLACEMENT,
                         random_seed)
        self.num_bootstrap_samples = num_bootstrap_samples

    def sample(self, data: List[Any], sample_size: int = None,
               **kwargs) -> List[SamplingResult]:
        """
        执行引导法采样（生成多个引导样本）

        Args:
            data: 原始数据列表
            sample_size: 样本大小（如果为None，则与总体大小相同）
            **kwargs: 额外参数

        Returns:
            List[SamplingResult]: 引导样本结果列表
        """
        population_size = len(data)
        sample_size = sample_size or population_size

        bootstrap_results = []

        for i in range(self.num_bootstrap_samples):
            # 有放回采样，样本大小与总体相同
            indices = [random.randint(0, population_size - 1)
                       for _ in range(sample_size)]

            result = SamplingResult(
                method=self.method,
                strategy=self.strategy,
                sample_indices=indices,
                population_indices=list(range(population_size)),
                sample_size=sample_size,
                population_size=population_size,
                sampling_rate=sample_size / population_size,
                metadata={
                    "bootstrap_sample_index": i,
                    "data_type": type(data[0]).__name__ if data else "unknown"
                }
            )

            bootstrap_results.append(result)

        return bootstrap_results

    def calculate_bootstrap_statistics(self, data: List[float],
                                       statistic_func: Callable[[List[float]], float],
                                       **kwargs) -> Dict[str, Any]:
        """
        计算引导法统计量

        Args:
            data: 原始数据（数值列表）
            statistic_func: 统计量函数
            **kwargs: 额外参数

        Returns:
            Dict[str, Any]: 统计量结果
        """
        # 生成引导样本
        bootstrap_results = self.sample(data, **kwargs)

        # 计算每个引导样本的统计量
        bootstrap_statistics = []

        for result in bootstrap_results:
            sample_data = result.get_sample_data(data)
            try:
                stat = statistic_func(sample_data)
                bootstrap_statistics.append(stat)
            except Exception as e:
                warnings.warn(f"计算统计量失败: {str(e)}")
                continue

        if not bootstrap_statistics:
            raise ValueError("无法计算任何引导统计量")

        # 计算置信区间
        alpha = kwargs.get('alpha', 0.05)
        lower_percentile = 100 * alpha / 2
        upper_percentile = 100 * (1 - alpha / 2)

        lower_bound = np.percentile(bootstrap_statistics, lower_percentile)
        upper_bound = np.percentile(bootstrap_statistics, upper_percentile)

        # 计算原始统计量
        original_statistic = statistic_func(data)

        return {
            "original_statistic": original_statistic,
            "bootstrap_mean": np.mean(bootstrap_statistics),
            "bootstrap_std": np.std(bootstrap_statistics),
            "confidence_interval": (float(lower_bound), float(upper_bound)),
            "confidence_level": 1 - alpha,
            "num_bootstrap_samples": len(bootstrap_statistics),
            "bootstrap_statistics": bootstrap_statistics
        }


class DatasetSplitter:
    """数据集划分器"""

    def __init__(self, test_size: float = 0.2, val_size: float = 0.1,
                 random_seed: Optional[int] = None,
                 shuffle: bool = True):
        """
        初始化数据集划分器

        Args:
            test_size: 测试集比例（0-1之间）
            val_size: 验证集比例（0-1之间）
            random_seed: 随机种子
            shuffle: 是否打乱数据
        """
        self.test_size = test_size
        self.val_size = val_size
        self.random_seed = random_seed
        self.shuffle = shuffle

    def train_test_split(self, X: List[Any], y: List[Any] = None,
                         **kwargs) -> Tuple[List[Any], List[Any], Optional[List[Any]], Optional[List[Any]]]:
        """
        划分训练集和测试集

        Args:
            X: 特征数据
            y: 标签数据（可选）

        Returns:
            Tuple: (X_train, X_test, y_train, y_test) 或 (X_train, X_test)
        """
        if y is None:
            # 只有X的情况
            X_train, X_test = sk_train_test_split(
                X, test_size=self.test_size, random_state=self.random_seed,
                shuffle=self.shuffle
            )
            return X_train, X_test, None, None
        else:
            # 有X和y的情况
            X_train, X_test, y_train, y_test = sk_train_test_split(
                X, y, test_size=self.test_size, random_state=self.random_seed,
                shuffle=self.shuffle
            )
            return X_train, X_test, y_train, y_test

    def train_val_test_split(self, X: List[Any], y: List[Any] = None
                             ) -> Tuple[List[Any], List[Any], List[Any],
                                        Optional[List[Any]], Optional[List[Any]], Optional[List[Any]]]:
        """
        划分训练集、验证集和测试集

        Args:
            X: 特征数据
            y: 标签数据（可选）

        Returns:
            Tuple: (X_train, X_val, X_test, y_train, y_val, y_test) 或 (X_train, X_val, X_test)
        """
        # 先划分训练+验证集和测试集
        X_train_val, X_test, y_train_val, y_test = self.train_test_split(X, y)

        # 计算验证集相对于训练+验证集的比例
        val_ratio = self.val_size / (1 - self.test_size)

        # 再划分训练集和验证集
        if y is None:
            X_train, X_val, _, _ = sk_train_test_split(
                X_train_val, [0] * len(X_train_val),  # 虚拟标签
                test_size=val_ratio, random_state=self.random_seed,
                shuffle=self.shuffle
            )
            return X_train, X_val, X_test, None, None, None
        else:
            X_train, X_val, y_train, y_val = sk_train_test_split(
                X_train_val, y_train_val,
                test_size=val_ratio, random_state=self.random_seed,
                shuffle=self.shuffle
            )
            return X_train, X_val, X_test, y_train, y_val, y_test

    def time_series_split(self, data: List[Any], n_splits: int = 5,
                          test_size: int = None) -> List[Tuple[List[int], List[int]]]:
        """
        时间序列交叉验证划分

        Args:
            data: 时间序列数据
            n_splits: 划分次数
            test_size: 每次测试集大小

        Returns:
            List[Tuple[List[int], List[int]]]: 训练索引和测试索引列表
        """
        tscv = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)
        splits = []

        for train_idx, test_idx in tscv.split(data):
            splits.append((list(train_idx), list(test_idx)))

        return splits

    def kfold_split(self, data: List[Any], n_splits: int = 5,
                    shuffle: bool = True) -> List[Tuple[List[int], List[int]]]:
        """
        K折交叉验证划分

        Args:
            data: 数据
            n_splits: K值
            shuffle: 是否打乱

        Returns:
            List[Tuple[List[int], List[int]]]: 训练索引和测试索引列表
        """
        kf = KFold(n_splits=n_splits, shuffle=shuffle,
                   random_state=self.random_seed)
        splits = []

        for train_idx, test_idx in kf.split(data):
            splits.append((list(train_idx), list(test_idx)))

        return splits

    def stratified_kfold_split(self, data: List[Any], labels: List[Any],
                               n_splits: int = 5, shuffle: bool = True
                               ) -> List[Tuple[List[int], List[int]]]:
        """
        分层K折交叉验证划分

        Args:
            data: 数据
            labels: 标签
            n_splits: K值
            shuffle: 是否打乱

        Returns:
            List[Tuple[List[int], List[int]]]: 训练索引和测试索引列表
        """
        skf = StratifiedKFold(n_splits=n_splits, shuffle=shuffle,
                              random_state=self.random_seed)
        splits = []

        for train_idx, test_idx in skf.split(data, labels):
            splits.append((list(train_idx), list(test_idx)))

        return splits


class ImbalancedSampler:
    """不平衡数据采样器（过采样和欠采样）"""

    def __init__(self, strategy: str = 'auto', random_seed: Optional[int] = None):
        """
        初始化不平衡数据采样器

        Args:
            strategy: 采样策略 ('over', 'under', 'auto')
            random_seed: 随机种子
        """
        self.strategy = strategy
        self.random_seed = random_seed

        if random_seed is not None:
            np.random.seed(random_seed)
            random.seed(random_seed)

    def resample(self, X: List[Any], y: List[Any]) -> Tuple[List[Any], List[Any]]:
        """
        重新采样不平衡数据

        Args:
            X: 特征数据
            y: 标签数据

        Returns:
            Tuple[List[Any], List[Any]]: 重采样后的特征和标签
        """
        if len(X) != len(y):
            raise ValueError("X和y的长度必须相同")

        # 统计各类别的样本数
        class_counts = Counter(y)

        if len(class_counts) < 2:
            raise ValueError("至少需要两个类别")

        # 确定多数类和少数类
        majority_class = max(class_counts, key=class_counts.get)
        minority_class = min(class_counts, key=class_counts.get)

        majority_count = class_counts[majority_class]
        minority_count = class_counts[minority_class]

        # 计算不平衡比例
        imbalance_ratio = minority_count / majority_count

        # 自动选择策略
        if self.strategy == 'auto':
            if imbalance_ratio < 0.5:
                # 严重不平衡，使用过采样
                return self._oversample(X, y)
            else:
                # 轻度不平衡，使用欠采样
                return self._undersample(X, y)
        elif self.strategy == 'over':
            return self._oversample(X, y)
        elif self.strategy == 'under':
            return self._undersample(X, y)
        else:
            raise ValueError(f"不支持的策略: {self.strategy}")

    def _oversample(self, X: List[Any], y: List[Any]) -> Tuple[List[Any], List[Any]]:
        """过采样少数类"""
        # 统计各类别的样本数
        class_counts = Counter(y)
        max_count = max(class_counts.values())

        X_resampled = []
        y_resampled = []

        # 对每个类别进行过采样
        for class_label, count in class_counts.items():
            # 获取该类别的所有样本
            class_indices = [i for i, label in enumerate(y) if label == class_label]
            class_X = [X[i] for i in class_indices]

            # 计算需要复制的次数
            if count < max_count:
                # 需要过采样
                repeat_times = max_count // count
                remainder = max_count % count

                # 复制样本
                for i in range(repeat_times):
                    X_resampled.extend(class_X)
                    y_resampled.extend([class_label] * count)

                # 添加剩余样本（随机选择）
                if remainder > 0:
                    random_indices = random.sample(class_indices, remainder)
                    X_resampled.extend([X[i] for i in random_indices])
                    y_resampled.extend([class_label] * remainder)
            else:
                # 多数类，直接添加
                X_resampled.extend(class_X)
                y_resampled.extend([class_label] * count)

        # 打乱数据
        combined = list(zip(X_resampled, y_resampled))
        random.shuffle(combined)
        X_resampled, y_resampled = zip(*combined)

        return list(X_resampled), list(y_resampled)

    def _undersample(self, X: List[Any], y: List[Any]) -> Tuple[List[Any], List[Any]]:
        """欠采样多数类"""
        # 统计各类别的样本数
        class_counts = Counter(y)
        min_count = min(class_counts.values())

        X_resampled = []
        y_resampled = []

        # 对每个类别进行欠采样
        for class_label, count in class_counts.items():
            # 获取该类别的所有样本
            class_indices = [i for i, label in enumerate(y) if label == class_label]

            # 随机选择min_count个样本
            sampled_indices = random.sample(class_indices, min_count)

            X_resampled.extend([X[i] for i in sampled_indices])
            y_resampled.extend([class_label] * min_count)

        # 打乱数据
        combined = list(zip(X_resampled, y_resampled))
        random.shuffle(combined)
        X_resampled, y_resampled = zip(*combined)

        return list(X_resampled), list(y_resampled)


class DataResampler:
    """数据重采样器（时间序列频率转换）"""

    def __init__(self, date_column: str = 'date'):
        """
        初始化数据重采样器

        Args:
            date_column: 日期列名
        """
        self.date_column = date_column

    def resample(self, df: pd.DataFrame, freq: str,
                 method: str = 'mean') -> ResamplingResult:
        """
        重采样时间序列数据

        Args:
            df: 原始DataFrame
            freq: 目标频率（如 'D', 'W', 'M', 'Q', 'Y'）
            method: 重采样方法

        Returns:
            ResamplingResult: 重采样结果
        """
        if self.date_column not in df.columns:
            raise ValueError(f"DataFrame必须包含日期列: {self.date_column}")

        # 确保日期列为datetime类型
        df_copy = df.copy()
        df_copy[self.date_column] = pd.to_datetime(df_copy[self.date_column])

        # 设置日期索引
        df_indexed = df_copy.set_index(self.date_column)

        # 确定原始频率
        original_freq = self._infer_frequency(df_indexed)

        # 执行重采样
        if method == 'mean':
            resampled = df_indexed.resample(freq).mean()
        elif method == 'sum':
            resampled = df_indexed.resample(freq).sum()
        elif method == 'last':
            resampled = df_indexed.resample(freq).last()
        elif method == 'first':
            resampled = df_indexed.resample(freq).first()
        elif method == 'ohlc':
            # OHLC重采样（用于金融数据）
            resampled = df_indexed.resample(freq).agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
        else:
            raise ValueError(f"不支持的resample方法: {method}")

        # 重置索引，将日期列还原为普通列
        resampled_reset = resampled.reset_index()

        # 创建结果对象
        return ResamplingResult(
            original_freq=original_freq,
            target_freq=freq,
            resampling_method=method,
            original_size=len(df),
            resampled_size=len(resampled_reset),
            resampled_data=resampled_reset,
            metadata={
                "date_column": self.date_column,
                "method": method,
                "columns": list(df.columns)
            }
        )

    def _infer_frequency(self, df_indexed: pd.DatetimeIndex) -> str:
        """推断时间序列频率"""
        if len(df_indexed) < 2:
            return "unknown"

        # 计算时间间隔
        diffs = df_indexed.index.to_series().diff().dropna()

        # 最常见的间隔作为频率
        mode_diff = diffs.mode()
        if len(mode_diff) > 0:
            diff = mode_diff[0]

            # 将时间间隔转换为频率字符串
            if diff >= pd.Timedelta(days=365):
                return 'Y'
            elif diff >= pd.Timedelta(days=90):
                return 'Q'
            elif diff >= pd.Timedelta(days=28):
                return 'M'
            elif diff >= pd.Timedelta(days=7):
                return 'W'
            elif diff >= pd.Timedelta(days=1):
                return 'D'
            elif diff >= pd.Timedelta(hours=1):
                return 'H'
            elif diff >= pd.Timedelta(minutes=1):
                return 'T'
            else:
                return 'S'

        return "unknown"

    def resample_ohlc(self, df: pd.DataFrame, freq: str,
                      open_col: str = 'open', high_col: str = 'high',
                      low_col: str = 'low', close_col: str = 'close',
                      volume_col: str = 'vol') -> pd.DataFrame:
        """
        重采样为OHLC数据（金融数据专用）

        Args:
            df: 原始DataFrame（需要包含日期和OHLCV列）
            freq: 目标频率（如 '5T', '15T', '1H', '1D'）
            open_col: 开盘价列名
            high_col: 最高价列名
            low_col: 最低价列名
            close_col: 收盘价列名
            volume_col: 成交量列名

        Returns:
            pd.DataFrame: 重采样后的OHLC数据
        """
        if self.date_column not in df.columns:
            raise ValueError(f"DataFrame必须包含日期列: {self.date_column}")

        # 确保日期列为datetime类型
        df_copy = df.copy()
        df_copy[self.date_column] = pd.to_datetime(df_copy[self.date_column])

        # 设置日期索引
        df_indexed = df_copy.set_index(self.date_column)

        # 执行OHLC重采样
        ohlc_dict = {
            open_col: 'first',
            high_col: 'max',
            low_col: 'min',
            close_col: 'last',
            volume_col: 'sum'
        }

        # 只重采样存在的列
        existing_cols = {}
        for col, agg_func in ohlc_dict.items():
            if col in df_indexed.columns:
                existing_cols[col] = agg_func

        if not existing_cols:
            raise ValueError("DataFrame中没有找到OHLCV列")

        resampled = df_indexed.resample(freq).agg(existing_cols)

        # 重置索引
        return resampled.reset_index()


class SamplerFactory:
    """采样器工厂类"""

    @staticmethod
    def create_sampler(method: Union[str, SamplingMethod], **kwargs) -> DataSampler:
        """
        创建采样器

        Args:
            method: 采样方法（字符串或枚举）
            **kwargs: 采样器参数

        Returns:
            DataSampler: 采样器实例
        """
        if isinstance(method, str):
            method = SamplingMethod(method.lower())

        if method == SamplingMethod.RANDOM:
            return RandomSampler(**kwargs)
        elif method == SamplingMethod.STRATIFIED:
            return StratifiedSampler(**kwargs)
        elif method == SamplingMethod.TIME_SERIES:
            return TimeSeriesSampler(**kwargs)
        elif method == SamplingMethod.BOOTSTRAP:
            return BootstrapSampler(**kwargs)
        else:
            raise ValueError(f"不支持的采样方法: {method}")

    @staticmethod
    def create_rolling_window_sampler(window_size: int, **kwargs) -> RollingWindowSampler:
        """创建滚动窗口采样器"""
        return RollingWindowSampler(window_size=window_size, **kwargs)

    @staticmethod
    def create_dataset_splitter(**kwargs) -> DatasetSplitter:
        """创建数据集划分器"""
        return DatasetSplitter(**kwargs)

    @staticmethod
    def create_imbalanced_sampler(**kwargs) -> ImbalancedSampler:
        """创建不平衡数据采样器"""
        return ImbalancedSampler(**kwargs)


# 使用示例
if __name__ == "__main__":
    print("=== 数据采样器示例 ===")

    # 1. 随机采样示例
    print("\n1. 随机采样示例:")
    data = list(range(100))
    sampler = RandomSampler(random_seed=42)
    result = sampler.sample(data, sample_size=10)

    print(f"总体大小: {result.population_size}")
    print(f"样本大小: {result.sample_size}")
    print(f"采样率: {result.sampling_rate:.2%}")
    print(f"样本索引: {result.sample_indices}")
    print(f"样本数据: {result.get_sample_data(data)}")

    # 2. 分层采样示例
    print("\n2. 分层采样示例:")
    df = pd.DataFrame({
        'feature': np.random.randn(100),
        'label': np.random.choice(['A', 'B', 'C'], size=100, p=[0.5, 0.3, 0.2])
    })

    stratified_sampler = StratifiedSampler(strata_column='label', random_seed=42)
    stratified_result = stratified_sampler.sample(df, sample_size=20)

    print(f"分层采样结果:")
    print(f"样本大小: {stratified_result.sample_size}")
    print(f"各层样本数: {stratified_result.metadata['strata_sample_sizes']}")

    # 3. 时间序列采样示例
    print("\n3. 时间序列采样示例:")
    dates = pd.date_range('2023-01-01', periods=100, freq='D')
    ts_data = pd.DataFrame({
        'date': dates,
        'value': np.random.randn(100).cumsum()
    })

    ts_sampler = TimeSeriesSampler(date_column='date', random_seed=42)
    ts_result = ts_sampler.sample(ts_data, sample_size=20)

    print(f"时间序列采样结果:")
    print(f"样本大小: {ts_result.sample_size}")
    print(f"采样类型: {ts_result.metadata['sampling_type']}")

    # 4. 滚动窗口采样示例
    print("\n4. 滚动窗口采样示例:")
    time_series = np.sin(np.linspace(0, 4 * np.pi, 50))
    window_sampler = RollingWindowSampler(window_size=10, forecast_horizon=2, step_size=2)
    windows = window_sampler.create_windows(time_series)

    print(f"时间序列长度: {len(time_series)}")
    print(f"创建的窗口数: {len(windows)}")
    print(f"第一个窗口: X={windows[0][0]}, y={windows[0][1]}")

    # 5. 引导法采样示例
    print("\n5. 引导法采样示例:")
    bootstrap_sampler = BootstrapSampler(num_bootstrap_samples=100, random_seed=42)
    bootstrap_results = bootstrap_sampler.sample(data, sample_size=50)

    print(f"引导样本数量: {len(bootstrap_results)}")
    print(f"第一个引导样本大小: {bootstrap_results[0].sample_size}")

    # 计算引导法统计量
    def mean_statistic(x):
        return np.mean(x)

    stats = bootstrap_sampler.calculate_bootstrap_statistics(
        list(np.random.randn(100)), mean_statistic, alpha=0.05
    )

    print(f"原始统计量: {stats['original_statistic']:.4f}")
    print(f"引导法均值: {stats['bootstrap_mean']:.4f}")
    print(f"95%置信区间: {stats['confidence_interval']}")

    # 6. 数据集划分示例
    print("\n6. 数据集划分示例:")
    splitter = DatasetSplitter(test_size=0.2, val_size=0.1, random_seed=42)

    X = list(range(100))
    y = [i % 3 for i in range(100)]  # 3个类别

    X_train, X_val, X_test, y_train, y_val, y_test = splitter.train_val_test_split(X, y)

    print(f"训练集大小: {len(X_train)}")
    print(f"验证集大小: {len(X_val)}")
    print(f"测试集大小: {len(X_test)}")

    # 7. 不平衡数据采样示例
    print("\n7. 不平衡数据采样示例:")
    # 创建不平衡数据
    X_imbalanced = list(range(100))
    y_imbalanced = [0] * 90 + [1] * 10  # 90个类别0，10个类别1

    print(f"原始数据类别分布: {Counter(y_imbalanced)}")

    imbalanced_sampler = ImbalancedSampler(strategy='over', random_seed=42)
    X_resampled, y_resampled = imbalanced_sampler.resample(X_imbalanced, y_imbalanced)

    print(f"过采样后类别分布: {Counter(y_resampled)}")
    print(f"过采样后数据大小: {len(X_resampled)}")

    # 8. 重采样示例
    print("\n8. 重采样示例:")
    # 创建分钟级数据
    minute_data = pd.DataFrame({
        'date': pd.date_range('2023-01-01 09:30', periods=240, freq='1min'),
        'price': 100 + np.random.randn(240).cumsum() * 0.1,
        'volume': np.random.randint(100, 1000, 240)
    })

    resampler = DataResampler(date_column='date')
    resampled_result = resampler.resample(minute_data, freq='5T', method='ohlc')

    print(f"原始数据大小: {resampled_result.original_size}")
    print(f"重采样后大小: {resampled_result.resampled_size}")
    print(f"原始频率: {resampled_result.original_freq}")
    print(f"目标频率: {resampled_result.target_freq}")