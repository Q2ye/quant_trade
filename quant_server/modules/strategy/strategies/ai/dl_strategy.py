# -*- coding: utf-8 -*-
"""
深度学习策略
基于深度学习模型（如LSTM、CNN、Transformer等）的交易策略
"""

import logging
from typing import Dict, List, Optional, Any

import numpy as np

from quant_server.modules.strategy.strategies.base.base_strategy import BaseStrategy
from quant_server.modules.strategy.constants import StrategyType, SignalDirection, SignalType
from quant_server.modules.strategy.models import TradingSignal
from quant_server.core.engines.types.entities import BarData

# 导入PyTorch
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class DLStrategy(BaseStrategy):
	"""
	深度学习策略类

	基于深度学习模型进行交易决策的策略，支持多种架构：
	- LSTM (长短期记忆网络)
	- CNN (卷积神经网络)
	- Transformer (自注意力机制)
	- GRU (门控循环单元)
	"""

	def __init__ (
			self,
			name: str,
			parameters: Optional[Dict[str, Any]] = None,
	):
		"""
		初始化深度学习策略

		Args:
			name: 策略名称
			parameters: 策略参数，包含：
				- model_type: 模型类型 (lstm, cnn, transformer, gru)
				- sequence_length: 序列长度
				- hidden_units: 隐藏层单元数
				- num_layers: 网络层数
				- dropout_rate: Dropout比率
				- learning_rate: 学习率
				- batch_size: 批次大小
				- epochs: 训练轮数
		"""
		super().__init__(name, StrategyType.DL, parameters)

		# 深度学习相关属性
		self.model = None
		self.scaler = None
		self.is_model_trained = False

		# 数据缓存
		self.sequence_data = []
		self.target_data = []

		# 默认参数
		self.default_params = {
			'model_type': 'lstm',
			'sequence_length': 30,
			'hidden_units': 64,
			'num_layers': 2,
			'dropout_rate': 0.2,
			'learning_rate': 0.001,
			'batch_size': 32,
			'epochs': 50,
			'min_training_sequences': 100,
			'retrain_interval': 200,
			'confidence_threshold': 0.7,
			'prediction_horizon': 1,
		}

		# 更新参数
		self.parameters.update(self.default_params)
		if parameters:
			self.parameters.update(parameters)

	def on_init (self) -> None:
		"""策略初始化"""
		logger.info(f"初始化深度学习策略: {self.name}")

		# 初始化深度学习模型
		self._initialize_model()

	def on_bar (self, bar: BarData) -> List[TradingSignal]:
		"""
		处理K线数据，生成交易信号

		Args:
			bar: K线数据

		Returns:
			交易信号列表
		"""
		signals = []

		try:
			# 更新序列数据
			self._update_sequence_data(bar)

			# 检查是否需要重新训练模型
			if self._should_retrain():
				self._train_model()

			# 生成预测信号
			if self.is_model_trained and len(self.sequence_data) >= self.parameters['sequence_length']:
				signal = self._generate_prediction_signal(bar)
				if signal:
					signals.append(signal)

		except Exception as e:
			logger.error(f"深度学习策略 {self.name} 处理K线数据时出错: {e}")

		return signals

	def _initialize_model (self) -> None:
		"""初始化深度学习模型"""
		model_type = self.parameters['model_type']

		try:

			# 根据模型类型选择架构
			if model_type == 'lstm':
				self.model = LSTMModel(
					input_size=5,  # OHLCV
					hidden_size=self.parameters['hidden_units'],
					num_layers=self.parameters['num_layers'],
					dropout=self.parameters['dropout_rate'],
					output_size=3  # 3类：上涨、下跌、持平
				)
			elif model_type == 'cnn':
				self.model = CNNModel(
					input_channels=1,
					sequence_length=self.parameters['sequence_length'],
					output_size=3
				)
			elif model_type == 'transformer':
				self.model = TransformerModel(
					d_model=64,
					nhead=8,
					num_layers=self.parameters['num_layers'],
					output_size=3
				)
			elif model_type == 'gru':
				self.model = GRUModel(
					input_size=5,
					hidden_size=self.parameters['hidden_units'],
					num_layers=self.parameters['num_layers'],
					dropout=self.parameters['dropout_rate'],
					output_size=3
				)
			else:
				# 默认使用LSTM
				self.model = LSTMModel(
					input_size=5,
					hidden_size=self.parameters['hidden_units'],
					num_layers=self.parameters['num_layers'],
					dropout=self.parameters['dropout_rate'],
					output_size=3
				)

			# 初始化优化器
			self.optimizer = torch.optim.Adam(
				self.model.parameters(),
				lr=self.parameters['learning_rate']
			)

			# 初始化损失函数
			self.criterion = nn.CrossEntropyLoss()

			# 初始化数据标准化器
			from sklearn.preprocessing import StandardScaler
			self.scaler = StandardScaler()

			logger.info(f"初始化 {model_type} 模型成功")

		except ImportError as e:
			logger.error(f"导入深度学习库失败: {e}")
			raise

	def _update_sequence_data (self, bar: BarData) -> None:
		"""更新序列数据"""
		# 创建当前bar的特征向量
		features = [
			bar.open,
			bar.high,
			bar.low,
			bar.close,
			bar.volume
		]

		# 添加技术指标特征
		technical_features = self._calculate_technical_features(bar)
		features.extend(technical_features)

		# 更新序列数据
		self.sequence_data.append(features)

		# 限制数据长度
		max_length = self.parameters['sequence_length'] * 10  # 保留10倍序列长度的数据
		if len(self.sequence_data) > max_length:
			self.sequence_data = self.sequence_data[-max_length:]

	def _calculate_technical_features (self, bar: BarData) -> List[float]:
		"""计算技术指标特征"""
		features = []

		# 简单移动平均
		if len(self.sequence_data) >= 5:
			closes = [data[3] for data in self.sequence_data[-5:]]  # close price是第4个元素
			ma5 = sum(closes) / len(closes)
			features.append(ma5)
			features.append(bar.close / ma5 if ma5 != 0 else 1.0)

		if len(self.sequence_data) >= 10:
			closes = [data[3] for data in self.sequence_data[-10:]]
			ma10 = sum(closes) / len(closes)
			features.append(ma10)
			features.append(bar.close / ma10 if ma10 != 0 else 1.0)

		if len(self.sequence_data) >= 20:
			closes = [data[3] for data in self.sequence_data[-20:]]
			ma20 = sum(closes) / len(closes)
			features.append(ma20)
			features.append(bar.close / ma20 if ma20 != 0 else 1.0)

		# 价格波动率
		if len(self.sequence_data) >= 20:
			recent_closes = [data[3] for data in self.sequence_data[-20:]]
			returns = [(recent_closes[i] - recent_closes[i - 1]) / recent_closes[i - 1]
			           for i in range(1, len(recent_closes))]
			if returns:
				volatility = np.std(returns)
				features.append(volatility)

		return features

	def _should_retrain (self) -> bool:
		"""判断是否需要重新训练模型"""
		if not self.is_model_trained:
			return len(self.sequence_data) >= self.parameters['min_training_sequences']

		# 检查重训练间隔
		current_count = len(self.sequence_data)
		last_training_count = getattr(self, '_last_training_count', 0)

		return current_count - last_training_count >= self.parameters['retrain_interval']

	def _train_model (self) -> None:
		"""训练深度学习模型"""
		if len(self.sequence_data) < self.parameters['min_training_sequences']:
			logger.warning(f"序列数据不足，需要至少 {self.parameters['min_training_sequences']} 个序列")
			return

		try:
			from torch.utils.data import DataLoader, TensorDataset

			# 准备训练数据
			X, y = self._prepare_training_data()

			if len(X) == 0:
				logger.warning("训练数据为空")
				return

			# 数据标准化
			X_scaled = self.scaler.fit_transform(X.reshape(-1, X.shape[-1]))
			X_scaled = X_scaled.reshape(X.shape)

			# 转换为PyTorch张量
			X_tensor = torch.FloatTensor(X_scaled)
			y_tensor = torch.LongTensor(y)

			# 创建数据加载器
			dataset = TensorDataset(X_tensor, y_tensor)
			dataloader = DataLoader(
				dataset,
				batch_size=self.parameters['batch_size'],
				shuffle=True
			)

			# 训练模型
			self.model.train()

			for epoch in range(self.parameters['epochs']):
				total_loss = 0

				for batch_X, batch_y in dataloader:
					self.optimizer.zero_grad()

					# 前向传播
					outputs = self.model(batch_X)
					loss = self.criterion(outputs, batch_y)

					# 反向传播
					loss.backward()
					self.optimizer.step()

					total_loss += loss.item()

				if epoch % 10 == 0:
					avg_loss = total_loss / len(dataloader)
					logger.info(f"Epoch {epoch}, Loss: {avg_loss:.4f}")

			self.is_model_trained = True
			self._last_training_count = len(self.sequence_data)

			logger.info(f"模型训练完成，使用 {len(X)} 个序列")

		except Exception as e:
			logger.error(f"模型训练失败: {e}")

	def _prepare_training_data (self) -> tuple:
		"""准备训练数据"""
		seq_len = self.parameters['sequence_length']
		horizon = self.parameters['prediction_horizon']

		X = []
		y = []

		for i in range(seq_len, len(self.sequence_data) - horizon):
			# 获取序列窗口
			sequence_window = self.sequence_data[i - seq_len:i]

			# 计算目标变量（未来价格变化）
			current_close = self.sequence_data[i][3]  # close price
			future_close = self.sequence_data[i + horizon][3]
			price_change = (future_close - current_close) / current_close

			# 分类标签：0-下跌，1-持平，2-上涨
			if price_change < -0.001:  # 下跌超过0.1%
				target = 0
			elif price_change > 0.001:  # 上涨超过0.1%
				target = 2
			else:  # 持平
				target = 1

			X.append(sequence_window)
			y.append(target)

		return np.array(X), np.array(y)

	def _generate_prediction_signal (self, bar: BarData) -> Optional[TradingSignal]:
		"""生成预测信号"""
		try:

			# 准备当前序列
			current_sequence = self._get_current_sequence()

			if current_sequence is None:
				return None

			# 数据标准化
			current_scaled = self.scaler.transform(current_sequence.reshape(-1, current_sequence.shape[-1]))
			current_scaled = current_scaled.reshape(current_sequence.shape)

			# 转换为PyTorch张量
			sequence_tensor = torch.FloatTensor(current_scaled).unsqueeze(0)  # 添加batch维度

			# 进行预测
			self.model.eval()
			with torch.no_grad():
				outputs = self.model(sequence_tensor)
				probabilities = torch.softmax(outputs, dim=1)
				prediction = torch.argmax(outputs, dim=1).item()
				confidence = torch.max(probabilities).item()

			# 检查置信度阈值
			if confidence < self.parameters['confidence_threshold']:
				return None

			# 生成信号
			if prediction == 2:  # 预测上涨
				direction = SignalDirection.LONG
			elif prediction == 0:  # 预测下跌
				direction = SignalDirection.SHORT
			else:  # 预测持平，不交易
				return None

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

	def _get_current_sequence (self) -> Optional[np.ndarray]:
		"""获取当前序列"""
		if len(self.sequence_data) < self.parameters['sequence_length']:
			return None

		# 获取最近sequence_length个bar的序列
		recent_sequence = self.sequence_data[-self.parameters['sequence_length']:]

		return np.array(recent_sequence)

	def get_model_info (self) -> Dict[str, Any]:
		"""获取模型信息"""
		return {
			'model_type': self.parameters['model_type'],
			'is_trained': self.is_model_trained,
			'training_sequences': len(self.sequence_data),
			'sequence_length': self.parameters['sequence_length'],
			'model_architecture': type(self.model).__name__ if self.model else None
		}


# ==================== 深度学习模型定义 ====================

class LSTMModel(torch.nn.Module):
	"""LSTM模型"""

	def __init__ (self, input_size, hidden_size, num_layers, dropout, output_size):
		super(LSTMModel, self).__init__()
		self.hidden_size = hidden_size
		self.num_layers = num_layers

		self.lstm = torch.nn.LSTM(
			input_size, hidden_size, num_layers,
			batch_first=True, dropout=dropout
		)
		self.dropout = torch.nn.Dropout(dropout)
		self.fc = torch.nn.Linear(hidden_size, output_size)

	def forward (self, x):
		# LSTM前向传播
		lstm_out, _ = self.lstm(x)

		# 取最后一个时间步的输出
		last_output = lstm_out[:, -1, :]

		# 全连接层
		output = self.fc(self.dropout(last_output))
		return output


class CNNModel(torch.nn.Module):
	"""CNN模型"""

	def __init__ (self, input_channels, sequence_length, output_size):
		super(CNNModel, self).__init__()

		self.conv1 = torch.nn.Conv1d(input_channels, 32, kernel_size=3, padding=1)
		self.conv2 = torch.nn.Conv1d(32, 64, kernel_size=3, padding=1)
		self.pool = torch.nn.MaxPool1d(kernel_size=2)

		# 计算全连接层输入大小
		conv_output_size = sequence_length // 2 // 2  # 经过两次池化
		self.fc1 = torch.nn.Linear(64 * conv_output_size, 128)
		self.fc2 = torch.nn.Linear(128, output_size)
		self.dropout = torch.nn.Dropout(0.2)

	def forward (self, x):
		# 调整维度: (batch, channels, sequence)
		x = x.transpose(1, 2)

		# CNN前向传播
		x = torch.relu(self.conv1(x))
		x = self.pool(x)
		x = torch.relu(self.conv2(x))
		x = self.pool(x)

		# 展平
		x = x.view(x.size(0), -1)

		# 全连接层
		x = torch.relu(self.fc1(x))
		x = self.dropout(x)
		x = self.fc2(x)

		return x


class TransformerModel(torch.nn.Module):
	"""Transformer模型"""

	def __init__ (self, d_model, nhead, num_layers, output_size):
		super(TransformerModel, self).__init__()

		self.embedding = torch.nn.Linear(5, d_model)  # OHLCV -> d_model
		self.pos_encoding = PositionalEncoding(d_model)

		encoder_layer = torch.nn.TransformerEncoderLayer(
			d_model=d_model,
			nhead=nhead,
			dim_feedforward=4 * d_model
		)
		self.transformer_encoder = torch.nn.TransformerEncoder(
			encoder_layer,
			num_layers=num_layers
		)

		self.fc = torch.nn.Linear(d_model, output_size)

	def forward (self, x):
		# 嵌入层
		x = self.embedding(x)

		# 位置编码
		x = self.pos_encoding(x)

		# Transformer编码器 (需要调整维度: seq_len, batch, features)
		x = x.transpose(0, 1)
		x = self.transformer_encoder(x)

		# 取最后一个时间步
		x = x[-1, :, :]

		# 全连接层
		x = self.fc(x)

		return x


class GRUModel(torch.nn.Module):
	"""GRU模型"""

	def __init__ (self, input_size, hidden_size, num_layers, dropout, output_size):
		super(GRUModel, self).__init__()
		self.hidden_size = hidden_size
		self.num_layers = num_layers

		self.gru = torch.nn.GRU(
			input_size, hidden_size, num_layers,
			batch_first=True, dropout=dropout
		)
		self.dropout = torch.nn.Dropout(dropout)
		self.fc = torch.nn.Linear(hidden_size, output_size)

	def forward (self, x):
		# GRU前向传播
		gru_out, _ = self.gru(x)

		# 取最后一个时间步的输出
		last_output = gru_out[:, -1, :]

		# 全连接层
		output = self.fc(self.dropout(last_output))
		return output


class PositionalEncoding(torch.nn.Module):
	"""位置编码"""

	def __init__ (self, d_model, max_len=5000):
		super(PositionalEncoding, self).__init__()

		pe = torch.zeros(max_len, d_model)
		position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
		div_term = torch.exp(torch.arange(0, d_model, 2).float() *
		                     (-torch.log(torch.tensor(10000.0)) / d_model))

		pe[:, 0::2] = torch.sin(position * div_term)
		pe[:, 1::2] = torch.cos(position * div_term)
		pe = pe.unsqueeze(0).transpose(0, 1)

		self.register_buffer('pe', pe)

	def forward (self, x):
		x = x + self.pe[:x.size(0), :]
		return x