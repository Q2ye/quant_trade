"""
数据工具包 - 提供数据处理、转换、验证和采样功能

模块包含：
1. data_validator.py - 数据验证器：验证数据质量、完整性和一致性
2. data_transformer.py - 数据转换器：转换数据格式、标准化、编码

设计原则：
1. 模块化：每个工具独立且功能单一
2. 可配置：通过配置对象控制行为
3. 可扩展：支持自定义验证规则、转换器和采样器
4. 高性能：支持批量处理和异步操作
5. 可重现：支持随机种子设置，确保结果可重现

使用示例：
    from core.utils.data_utils import (
        ValidationRuleFactory, TransformationFactory, SamplerFactory
    )

    # 数据验证
    validator = ValidationRuleFactory.create_stock_validation_rules()
    report = validator.validate_batch(stock_data)

    # 数据转换
    pipeline = TransformationFactory.create_stock_transformation_pipeline()
    transformed_data = pipeline.transform_batch(stock_data)

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



# 工具函数
def get_data_utils_info () -> dict:
	"""获取数据工具包信息"""
	return {
		"version": __version__,
		"author": __author__,
		"description": __description__,
		"modules": ["data_validator", "data_transformer", "validation"],
		"default_configs": {
			"validation": DEFAULT_VALIDATION_CONFIG,
			"transformation": DEFAULT_TRANSFORMATION_CONFIG,
		}
	}


def create_default_validator () -> DataValidator:
	"""创建默认验证器"""
	return DataValidator()


def create_default_transformer () -> DataTransformerPipeline:
	"""创建默认转换器管道"""
	return DataTransformerPipeline()




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


# 导出工具函数
__all__.extend([
	'get_data_utils_info',
	'create_default_validator',
	'create_default_transformer',
	'assess_data_quality',
	'DEFAULT_VALIDATION_CONFIG',
	'DEFAULT_TRANSFORMATION_CONFIG',
])

print(f"数据工具包 {__version__} 加载完成")
print(f"包含 {len(__all__)} 个导出项")
