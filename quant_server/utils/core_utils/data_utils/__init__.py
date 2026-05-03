"""
数据工具包 - 提供数据处理、转换、验证和采样功能

模块包含：
1. data_validator.py - 数据验证器：验证数据质量、完整性和一致性
2. data_transformer.py - 数据转换器：转换数据格式、标准化、编码
3. data_sampler.py - 数据采样器：采样、重采样、数据集划分

设计原则：
1. 模块化：每个工具独立且功能单一
2. 可配置：通过配置对象控制行为
3. 可扩展：支持自定义验证规则、转换器和采样器
4. 高性能：支持批量处理和异步操作
5. 可重现：支持随机种子设置，确保结果可重现

使用示例：
    from core.utils.data_utils import (
        DataValidator, DataTransformer, DataSampler,
        ValidationRuleFactory, TransformationFactory, SamplerFactory
    )

    # 数据验证
    validator = ValidationRuleFactory.create_stock_validation_rules()
    report = validator.validate_batch(stock_data)

    # 数据转换
    pipeline = TransformationFactory.create_stock_transformation_pipeline()
    transformed_data = pipeline.transform_batch(stock_data)

    # 数据采样
    sampler = SamplerFactory.create_sampler('random', random_seed=42)
    sample_result = sampler.sample(events, sample_size=100)
"""

from .data_validator import (
	# 枚举和数据结构
	ValidationResultStatus,
	ValidationResult,
	ValidationReport,

	# 验证规则
	ValidationRule,
	RequiredRule,
	TypeRule,
	RangeRule,
	PatternRule,
	LengthRule,
	CustomRule,

	# 验证器
	DataValidator,
	ValidationRuleFactory,

	# 质量评分
	DataQualityScorer
)

from .data_transformer import (
	# 枚举和数据结构
	TransformationType,
	TransformationResult,
	TransformationReport,

	# 转换器
	DataTransformer,
	TypeCaster,
	Normalizer,
	StandardScaler,
	OneHotEncoder,
	MinMaxScaler,
	DataDeriver,

	# 转换管道
	DataTransformerPipeline,
	TransformationFactory
)

from .validation import (
		validate_amount,
		validate_account_data,
		validate_position_data,
)

from .data_sampler import (
	# 枚举和数据结构
	SamplingMethod,
	SamplingStrategy,
	SamplingResult,
	ResamplingResult,

	# 采样器
	DataSampler,
	RandomSampler,
	StratifiedSampler,
	TimeSeriesSampler,
	BootstrapSampler,

	# 其他采样工具
	RollingWindowSampler,
	DataResampler,
	DatasetSplitter,
	ImbalancedSampler,

	# 采样器工厂
	SamplerFactory
)

__all__ = [
	# 数据验证
	'ValidationResultStatus',
	'ValidationResult',
	'ValidationReport',
	'ValidationRule',
	'RequiredRule',
	'TypeRule',
	'RangeRule',
	'PatternRule',
	'LengthRule',
	'CustomRule',
	'DataValidator',
	'ValidationRuleFactory',
	'DataQualityScorer',

		# 业务验证
		'validate_amount',
		'validate_account_data',
		'validate_position_data',

		# 业务验证
		'validate_amount',
		'validate_account_data',
		'validate_position_data',

	# 数据转换
	'TransformationType',
	'TransformationResult',
	'TransformationReport',
	'DataTransformer',
	'TypeCaster',
	'Normalizer',
	'StandardScaler',
	'OneHotEncoder',
	'MinMaxScaler',
	'DataDeriver',
	'DataTransformerPipeline',
	'TransformationFactory',

	# 数据采样
	'SamplingMethod',
	'SamplingStrategy',
	'SamplingResult',
	'ResamplingResult',
	'DataSampler',
	'RandomSampler',
	'StratifiedSampler',
	'TimeSeriesSampler',
	'BootstrapSampler',
	'RollingWindowSampler',
	'DataResampler',
	'DatasetSplitter',
	'ImbalancedSampler',
	'SamplerFactory'
]

# 版本信息
__version__ = "1.0.0"
__author__ = "量化交易系统架构团队"
__description__ = "量化交易系统数据处理工具包"

# 配置常量
DEFAULT_VALIDATION_CONFIG = {
	"strict_mode": True,
	"allow_partial": False,
	"max_errors": 1000
}

DEFAULT_TRANSFORMATION_CONFIG = {
	"preserve_original": True,
	"error_handling": "strict",  # strict, ignore, fill
	"fill_value": None
}

DEFAULT_SAMPLING_CONFIG = {
	"random_seed": None,
	"shuffle": True,
	"stratify": False
}


# 工具函数
def get_data_utils_info () -> dict:
	"""获取数据工具包信息"""
	return {
		"version": __version__,
		"author": __author__,
		"description": __description__,
		"modules": ["data_validator", "data_transformer", "data_sampler", "validation"],
		"default_configs": {
			"validation": DEFAULT_VALIDATION_CONFIG,
			"transformation": DEFAULT_TRANSFORMATION_CONFIG,
			"sampling": DEFAULT_SAMPLING_CONFIG
		}
	}


def create_default_validator () -> DataValidator:
	"""创建默认验证器"""
	return DataValidator()


def create_default_transformer () -> DataTransformerPipeline:
	"""创建默认转换器管道"""
	return DataTransformerPipeline()


def create_default_sampler () -> RandomSampler:
	"""创建默认采样器"""
	return RandomSampler()


# 数据质量评估工具
def assess_data_quality (data, validator: DataValidator = None) -> dict:
	"""
	评估数据质量

	Args:
		data: 要评估的数据
		validator: 验证器实例（如果为None，则使用默认验证器）

	Returns:
		dict: 质量评估报告
	"""
	if validator is None:
		validator = create_default_validator()

	if isinstance(data, list):
		report = validator.validate_batch(data)
	elif isinstance(data, dict):
		report = validator.validate_record(data)
	else:
		raise ValueError(f"不支持的数据类型: {type(data)}")

	# 计算质量得分
	scorer = DataQualityScorer()
	quality_score = scorer.calculate_score(report)

	return {
		"validation_report": report.to_dict(),
		"quality_score": quality_score,
		"summary": {
			"total_records": report.total_records,
			"valid_records": report.valid_records,
			"invalid_records": report.invalid_records,
			"warning_records": report.warning_records,
			"overall_quality": quality_score["overall_score"],
			"quality_grade": quality_score["grade"]
		}
	}


# 批量数据处理工具
def batch_process_data (data, processors: list, config: dict = None) -> dict:
	"""
	批量处理数据

	Args:
		data: 原始数据
		processors: 处理器列表，每个处理器为 (processor_type, config) 元组
		config: 全局配置

	Returns:
		dict: 处理结果
	"""
	config = config or {}
	results = {
		"original_data": data,
		"processed_data": data,
		"processing_steps": [],
		"errors": []
	}

	current_data = data

	for i, (processor_type, processor_config) in enumerate(processors):
		step_result = {
			"step": i + 1,
			"processor_type": processor_type,
			"config": processor_config,
			"success": False
		}

		try:
			if processor_type == "validate":
				validator = DataValidator(**processor_config)
				report = validator.validate_batch(current_data)
				step_result.update({
					"success": True,
					"result": report.to_dict(),
					"valid_records": report.valid_records,
					"invalid_records": report.invalid_records
				})

			elif processor_type == "transform":
				pipeline = DataTransformerPipeline()
				# 根据配置添加转换器
				for transform_config in processor_config.get("transformers", []):
					# 这里需要根据配置创建转换器
					pass
				transformed_data = pipeline.transform_batch(current_data)
				step_result.update({
					"success": True,
					"result": pipeline.report.to_dict(),
					"transformed_data": transformed_data
				})
				current_data = transformed_data

			elif processor_type == "sample":
				sampler = SamplerFactory.create_sampler(
					processor_config.get("method", "random"),
					**processor_config
				)
				sample_result = sampler.sample(
					current_data,
					processor_config.get("sample_size", len(current_data) // 2)
				)
				step_result.update({
					"success": True,
					"result": sample_result.to_dict(),
					"sampled_data": sample_result.get_sample_data(current_data)
				})
				current_data = sample_result.get_sample_data(current_data)

			else:
				raise ValueError(f"不支持的处理器类型: {processor_type}")

		except Exception as e:
			step_result.update({
				"error": str(e),
				"error_type": type(e).__name__
			})
			results["errors"].append(step_result)

			if config.get("stop_on_error", True):
				break

		results["processing_steps"].append(step_result)

	results["processed_data"] = current_data
	results["success"] = len(results["errors"]) == 0

	return results


# 导出工具函数
__all__.extend([
	'get_data_utils_info',
	'create_default_validator',
	'create_default_transformer',
	'create_default_sampler',
	'assess_data_quality',
	'batch_process_data',
	'DEFAULT_VALIDATION_CONFIG',
	'DEFAULT_TRANSFORMATION_CONFIG',
	'DEFAULT_SAMPLING_CONFIG'
])

print(f"数据工具包 {__version__} 加载完成")
print(f"包含 {len(__all__)} 个导出项")