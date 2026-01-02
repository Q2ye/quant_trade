"""
日志格式化器 - 提供灵活的日志格式化和渲染功能

职责：
1. 日志格式定义（支持多种输出格式）
2. 颜色渲染（终端彩色输出）
3. 字段提取和转换
4. 格式验证和优化
5. 自定义格式化器

设计原则：
1. 灵活性：支持多种格式和自定义格式
2. 可扩展：支持自定义格式化器和渲染器
3. 性能：高效格式化，避免不必要的开销
4. 一致性：确保不同处理器之间格式一致
"""

import json
import re
import time
import datetime
from typing import Dict, List, Any, Optional, Union, Callable, Pattern
from dataclasses import dataclass, field
from enum import Enum
import colorsys
from string import Template
import inspect


class ColorMode(Enum):
	"""颜色模式枚举"""
	AUTO = "auto"  # 自动检测（终端启用颜色，文件禁用）
	ALWAYS = "always"  # 总是启用颜色
	NEVER = "never"  # 从不启用颜色


class FieldType(Enum):
	"""字段类型枚举"""
	STRING = "string"
	INTEGER = "integer"
	FLOAT = "float"
	BOOLEAN = "boolean"
	DATETIME = "datetime"
	DURATION = "duration"
	JSON = "json"
	RAW = "raw"


@dataclass
class FieldSpec:
	"""字段规格定义"""
	name: str  # 字段名
	display_name: Optional[str] = None  # 显示名称
	field_type: FieldType = FieldType.STRING  # 字段类型
	format_string: Optional[str] = None  # 格式字符串
	width: Optional[int] = None  # 宽度（用于对齐）
	align: str = "left"  # 对齐方式：left, right, center
	truncate: bool = False  # 是否截断
	max_length: Optional[int] = None  # 最大长度
	default_value: Any = ""  # 默认值
	visible: bool = True  # 是否可见
	transform: Optional[Callable[[Any], Any]] = None  # 转换函数

	def format_value (self, value: Any) -> str:
		"""格式化字段值"""
		if value is None:
			value = self.default_value

		# 应用转换函数
		if self.transform:
			try:
				value = self.transform(value)
			except Exception:
				pass

		# 根据字段类型格式化
		if self.field_type == FieldType.STRING:
			formatted = str(value)
		elif self.field_type == FieldType.INTEGER:
			try:
				formatted = f"{int(value):d}"
			except (ValueError, TypeError):
				formatted = str(value)
		elif self.field_type == FieldType.FLOAT:
			try:
				if self.format_string:
					formatted = f"{float(value):{self.format_string}}"
				else:
					formatted = f"{float(value):.2f}"
			except (ValueError, TypeError):
				formatted = str(value)
		elif self.field_type == FieldType.BOOLEAN:
			formatted = "✓" if bool(value) else "✗"
		elif self.field_type == FieldType.DATETIME:
			if isinstance(value, (int, float)):
				# 时间戳
				dt = datetime.datetime.fromtimestamp(value)
			elif isinstance(value, str):
				# 尝试解析ISO格式
				try:
					dt = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
				except ValueError:
					formatted = str(value)
					return self._apply_formatting(formatted)
			else:
				dt = value

			if self.format_string:
				formatted = dt.strftime(self.format_string)
			else:
				formatted = dt.strftime('%Y-%m-%d %H:%M:%S')
		elif self.field_type == FieldType.DURATION:
			if isinstance(value, (int, float)):
				# 毫秒或秒
				if value < 1000:  # 假设是秒
					value = value * 1000

				if value < 1000:
					formatted = f"{value:.0f}ms"
				elif value < 60000:
					formatted = f"{value / 1000:.2f}s"
				elif value < 3600000:
					minutes = value // 60000
					seconds = (value % 60000) / 1000
					formatted = f"{minutes}m {seconds:.1f}s"
				else:
					hours = value // 3600000
					minutes = (value % 3600000) // 60000
					formatted = f"{hours}h {minutes}m"
			else:
				formatted = str(value)
		elif self.field_type == FieldType.JSON:
			try:
				if isinstance(value, (dict, list)):
					formatted = json.dumps(value, ensure_ascii=False)
				else:
					# 尝试解析JSON字符串
					json.loads(str(value))
					formatted = str(value)
			except (json.JSONDecodeError, TypeError):
				formatted = str(value)
		elif self.field_type == FieldType.RAW:
			formatted = str(value)
		else:
			formatted = str(value)

		return self._apply_formatting(formatted)

	def _apply_formatting (self, value: str) -> str:
		"""应用格式设置（宽度、对齐、截断）"""
		result = value

		# 截断
		if self.truncate and self.max_length and len(result) > self.max_length:
			result = result[:self.max_length - 3] + "..."

		# 宽度和对齐
		if self.width:
			if self.align == "left":
				result = result.ljust(self.width)
			elif self.align == "right":
				result = result.rjust(self.width)
			elif self.align == "center":
				result = result.center(self.width)

		return result


class ColorScheme:
	"""颜色方案"""

	def __init__ (self, name: str = "default"):
		"""
		初始化颜色方案

		Args:
			name: 方案名称（default, bright, pastel, monochrome）
		"""
		self.name = name

		if name == "default":
			self.colors = {
				"timestamp": "\033[90m",  # 灰色
				"debug": "\033[36m",  # 青色
				"info": "\033[32m",  # 绿色
				"warning": "\033[33m",  # 黄色
				"error": "\033[31m",  # 红色
				"critical": "\033[35m",  # 紫色
				"module": "\033[94m",  # 蓝色
				"function": "\033[95m",  # 洋红色
				"line": "\033[96m",  # 青色
				"message": "\033[97m",  # 白色
				"reset": "\033[0m"  # 重置
			}
		elif name == "bright":
			self.colors = {
				"timestamp": "\033[1;90m",
				"debug": "\033[1;36m",
				"info": "\033[1;32m",
				"warning": "\033[1;33m",
				"error": "\033[1;31m",
				"critical": "\033[1;35m",
				"module": "\033[1;94m",
				"function": "\033[1;95m",
				"line": "\033[1;96m",
				"message": "\033[1;97m",
				"reset": "\033[0m"
			}
		elif name == "pastel":
			self.colors = {
				"timestamp": "\033[38;5;250m",
				"debug": "\033[38;5;81m",
				"info": "\033[38;5;120m",
				"warning": "\033[38;5;221m",
				"error": "\033[38;5;210m",
				"critical": "\033[38;5;213m",
				"module": "\033[38;5;111m",
				"function": "\033[38;5;177m",
				"line": "\033[38;5;117m",
				"message": "\033[38;5;255m",
				"reset": "\033[0m"
			}
		elif name == "monochrome":
			# 单色方案（所有颜色相同）
			self.colors = {
				"timestamp": "",
				"debug": "",
				"info": "",
				"warning": "",
				"error": "",
				"critical": "",
				"module": "",
				"function": "",
				"line": "",
				"message": "",
				"reset": ""
			}
		else:
			raise ValueError(f"未知的颜色方案: {name}")

	def colorize (self, text: str, element: str) -> str:
		"""为文本添加颜色"""
		color = self.colors.get(element, "")
		reset = self.colors.get("reset", "")

		if color:
			return f"{color}{text}{reset}"
		else:
			return text

	def strip_colors (self, text: str) -> str:
		"""去除颜色代码"""
		# ANSI颜色代码正则表达式
		ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
		return ansi_escape.sub('', text)


class LogFormatter:
	"""日志格式化器"""

	def __init__ (self, format_template: str = None,
	              color_mode: ColorMode = ColorMode.AUTO,
	              color_scheme: str = "default",
	              field_specs: Dict[str, FieldSpec] = None):
		"""
		初始化日志格式化器

		Args:
			format_template: 格式模板
			color_mode: 颜色模式
			color_scheme: 颜色方案名称
			field_specs: 字段规格定义
		"""
		self.format_template = format_template or self._get_default_template()
		self.color_mode = color_mode
		self.color_scheme = ColorScheme(color_scheme)
		self.field_specs = field_specs or self._get_default_field_specs()

		# 编译模板
		self.template = Template(self.format_template)

	def _get_default_template (self) -> str:
		"""获取默认模板"""
		return "${timestamp} | ${level} | ${logger} | ${module}:${function}:${line} | ${message}"

	def _get_default_field_specs (self) -> Dict[str, FieldSpec]:
		"""获取默认字段规格"""
		return {
			"timestamp": FieldSpec(
				name="timestamp",
				display_name="时间戳",
				field_type=FieldType.DATETIME,
				format_string="%Y-%m-%d %H:%M:%S",
				width=23,
				align="left"
			),
			"level": FieldSpec(
				name="level",
				display_name="级别",
				field_type=FieldType.STRING,
				width=8,
				align="left"
			),
			"logger": FieldSpec(
				name="logger",
				display_name="记录器",
				field_type=FieldType.STRING,
				width=15,
				align="left",
				truncate=True,
				max_length=15
			),
			"module": FieldSpec(
				name="module",
				display_name="模块",
				field_type=FieldType.STRING,
				width=20,
				align="left",
				truncate=True,
				max_length=20
			),
			"function": FieldSpec(
				name="function",
				display_name="函数",
				field_type=FieldType.STRING,
				width=15,
				align="left",
				truncate=True,
				max_length=15
			),
			"line": FieldSpec(
				name="line",
				display_name="行号",
				field_type=FieldType.INTEGER,
				width=4,
				align="right"
			),
			"message": FieldSpec(
				name="message",
				display_name="消息",
				field_type=FieldType.STRING,
				width=0,  # 不固定宽度
				align="left"
			)
		}

	def format (self, log_record: Dict[str, Any],
	            use_color: Optional[bool] = None) -> str:
		"""
		格式化日志记录

		Args:
			log_record: 日志记录字典
			use_color: 是否使用颜色（None表示自动检测）

		Returns:
			str: 格式化后的日志字符串
		"""
		# 确定是否使用颜色
		if use_color is None:
			use_color = self._should_use_color()

		# 准备替换数据
		data = {}

		for field_name, field_spec in self.field_specs.items():
			if not field_spec.visible:
				continue

			# 获取字段值
			raw_value = log_record.get(field_name, field_spec.default_value)

			# 格式化字段值
			formatted_value = field_spec.format_value(raw_value)

			# 应用颜色
			if use_color and field_name in ["timestamp", "level", "module", "function", "line", "message"]:
				if field_name == "level":
					# 根据日志级别选择颜色元素
					level = log_record.get("level", "INFO").lower()
					if level in ["debug", "info", "warning", "error", "critical"]:
						color_element = level
					else:
						color_element = "message"
				else:
					color_element = field_name

				formatted_value = self.color_scheme.colorize(formatted_value, color_element)

			data[field_name] = formatted_value

		# 添加额外字段
		for key, value in log_record.items():
			if key not in data and key not in self.field_specs:
				# 自动为额外字段创建格式化
				if isinstance(value, (dict, list)):
					formatted = json.dumps(value, ensure_ascii=False)[:50]
					if len(formatted) > 50:
						formatted = formatted[:47] + "..."
				else:
					formatted = str(value)[:50]

				data[key] = formatted

		# 应用模板
		try:
			result = self.template.safe_substitute(data)
		except Exception:
			# 模板替换失败，使用默认格式
			result = f"{data.get('timestamp', '')} | {data.get('level', '')} | {data.get('message', '')}"

		return result

	def _should_use_color (self) -> bool:
		"""判断是否应该使用颜色"""
		if self.color_mode == ColorMode.ALWAYS:
			return True
		elif self.color_mode == ColorMode.NEVER:
			return False
		else:  # AUTO
			# 检查是否输出到终端
			try:
				import sys
				return sys.stdout.isatty()
			except:
				return False

	def to_table_format (self, log_records: List[Dict[str, Any]],
	                     fields: List[str] = None) -> str:
		"""
		将日志记录转换为表格格式

		Args:
			log_records: 日志记录列表
			fields: 要显示的字段列表

		Returns:
			str: 表格格式的日志
		"""
		if not log_records:
			return ""

		# 确定要显示的字段
		if fields is None:
			fields = ["timestamp", "level", "logger", "message"]

		# 计算每列的最大宽度
		column_widths = {}

		for field in fields:
			# 字段标题宽度
			field_spec = self.field_specs.get(field)
			if field_spec and field_spec.display_name:
				header = field_spec.display_name
			else:
				header = field

			max_width = len(header)

			# 查找数据中的最大宽度
			for record in log_records:
				value = record.get(field, "")
				if value is None:
					value = ""

				# 获取格式化后的值（不包含颜色）
				if field_spec:
					formatted = field_spec.format_value(value)
				else:
					formatted = str(value)

				# 去除颜色代码
				formatted = self.color_scheme.strip_colors(formatted)

				max_width = max(max_width, len(formatted))

			column_widths[field] = max_width + 2  # 加2作为边距

		# 构建表头
		header_parts = []
		separator_parts = []

		for field in fields:
			field_spec = self.field_specs.get(field)
			if field_spec and field_spec.display_name:
				header = field_spec.display_name
			else:
				header = field

			width = column_widths[field]
			header_parts.append(header.ljust(width))
			separator_parts.append("-" * width)

		header_line = "".join(header_parts)
		separator_line = "".join(separator_parts)

		# 构建数据行
		lines = [header_line, separator_line]

		for record in log_records:
			row_parts = []

			for field in fields:
				value = record.get(field, "")
				if value is None:
					value = ""

				# 获取格式化后的值
				field_spec = self.field_specs.get(field)
				if field_spec:
					formatted = field_spec.format_value(value)
				else:
					formatted = str(value)

				# 应用对齐
				if field_spec:
					align = field_spec.align
				else:
					align = "left"

				width = column_widths[field]
				if align == "right":
					cell = formatted.rjust(width)
				elif align == "center":
					cell = formatted.center(width)
				else:
					cell = formatted.ljust(width)

				row_parts.append(cell)

			lines.append("".join(row_parts))

		return "\n".join(lines)

	def to_json_format (self, log_record: Dict[str, Any],
	                    indent: Optional[int] = None) -> str:
		"""转换为JSON格式"""
		return json.dumps(log_record, indent=indent, ensure_ascii=False, default=str)

	def to_csv_format (self, log_records: List[Dict[str, Any]],
	                   fields: List[str] = None) -> str:
		"""转换为CSV格式"""
		if not log_records:
			return ""

		# 确定要显示的字段
		if fields is None:
			fields = ["timestamp", "level", "logger", "message"]

		# 构建CSV行
		lines = []

		# 表头
		headers = []
		for field in fields:
			field_spec = self.field_specs.get(field)
			if field_spec and field_spec.display_name:
				headers.append(field_spec.display_name)
			else:
				headers.append(field)

		lines.append(self._csv_escape_row(headers))

		# 数据行
		for record in log_records:
			row = []
			for field in fields:
				value = record.get(field, "")
				if value is None:
					value = ""

				# 获取格式化后的值（不包含颜色）
				field_spec = self.field_specs.get(field)
				if field_spec:
					formatted = field_spec.format_value(value)
				else:
					formatted = str(value)

				# 去除颜色代码
				formatted = self.color_scheme.strip_colors(formatted)

				row.append(formatted)

			lines.append(self._csv_escape_row(row))

		return "\n".join(lines)

	def _csv_escape_row (self, row: List[str]) -> str:
		"""转义CSV行"""
		escaped = []
		for item in row:
			if isinstance(item, str):
				# 转义双引号和逗号
				# if '"' in item or ',' in item or '\n' in item:
				# 	escaped.append(f'"{item.replace('"', '""')}"')
				# else:
				escaped.append(item)
			else:
				escaped.append(str(item))

		return ",".join(escaped)

	def create_custom_format (self, format_string: str) -> 'LogFormatter':
		"""创建自定义格式化器"""
		# 解析格式字符串中的字段
		field_pattern = re.compile(r'\$\{(\w+)\}')
		fields = field_pattern.findall(format_string)

		# 创建字段规格
		field_specs = {}
		for field in fields:
			if field in self.field_specs:
				field_specs[field] = self.field_specs[field]
			else:
				field_specs[field] = FieldSpec(
					name=field,
					field_type=FieldType.STRING
				)

		return LogFormatter(
			format_template=format_string,
			color_mode=self.color_mode,
			color_scheme=self.color_scheme.name,
			field_specs=field_specs
		)


# 预定义格式工厂
class FormatterFactory:
	"""格式化器工厂类"""

	@staticmethod
	def create_default_formatter () -> LogFormatter:
		"""创建默认格式化器"""
		return LogFormatter()

	@staticmethod
	def create_verbose_formatter () -> LogFormatter:
		"""创建详细格式化器"""
		template = "${timestamp} | ${level} | ${logger} | ${module}.${function}:${line} | ${message}"

		field_specs = {
			"timestamp": FieldSpec(
				name="timestamp",
				field_type=FieldType.DATETIME,
				format_string="%Y-%m-%d %H:%M:%S.%f",
				width=26,
				align="left"
			),
			"level": FieldSpec(
				name="level",
				field_type=FieldType.STRING,
				width=8,
				align="left"
			),
			"logger": FieldSpec(
				name="logger",
				field_type=FieldType.STRING,
				width=20,
				align="left",
				truncate=True,
				max_length=20
			),
			"module": FieldSpec(
				name="module",
				field_type=FieldType.STRING,
				width=25,
				align="left",
				truncate=True,
				max_length=25
			),
			"function": FieldSpec(
				name="function",
				field_type=FieldType.STRING,
				width=20,
				align="left",
				truncate=True,
				max_length=20
			),
			"line": FieldSpec(
				name="line",
				field_type=FieldType.INTEGER,
				width=4,
				align="right"
			),
			"message": FieldSpec(
				name="message",
				field_type=FieldType.STRING,
				width=0,
				align="left"
			)
		}

		return LogFormatter(
			format_template=template,
			field_specs=field_specs
		)

	@staticmethod
	def create_simple_formatter () -> LogFormatter:
		"""创建简单格式化器"""
		template = "${timestamp} | ${level} | ${message}"

		field_specs = {
			"timestamp": FieldSpec(
				name="timestamp",
				field_type=FieldType.DATETIME,
				format_string="%H:%M:%S",
				width=12,
				align="left"
			),
			"level": FieldSpec(
				name="level",
				field_type=FieldType.STRING,
				width=5,
				align="left"
			),
			"message": FieldSpec(
				name="message",
				field_type=FieldType.STRING,
				width=0,
				align="left"
			)
		}

		return LogFormatter(
			format_template=template,
			field_specs=field_specs
		)

	@staticmethod
	def create_json_formatter (indent: Optional[int] = None) -> 'JSONFormatter':
		"""创建JSON格式化器"""
		return JSONFormatter(indent=indent)

	@staticmethod
	def create_csv_formatter () -> 'CSVFormatter':
		"""创建CSV格式化器"""
		return CSVFormatter()

	@staticmethod
	def create_gelf_formatter () -> 'GELFFormatter':
		"""创建GELF格式化器"""
		return GELFFormatter()


class JSONFormatter(LogFormatter):
	"""JSON格式化器"""

	def __init__ (self, indent: Optional[int] = None):
		super().__init__(format_template="", color_mode=ColorMode.NEVER)
		self.indent = indent

	def format (self, log_record: Dict[str, Any], **kwargs) -> str:
		"""格式化为JSON"""
		return json.dumps(log_record, indent=self.indent, ensure_ascii=False, default=str)


class CSVFormatter(LogFormatter):
	"""CSV格式化器"""

	def __init__ (self, delimiter: str = ","):
		super().__init__(format_template="", color_mode=ColorMode.NEVER)
		self.delimiter = delimiter

	def format (self, log_record: Dict[str, Any], **kwargs) -> str:
		"""格式化为CSV"""
		# 选择要输出的字段
		fields = ["timestamp", "level", "logger", "module", "function", "line", "message"]

		row = []
		for field in fields:
			value = log_record.get(field, "")
			if value is None:
				value = ""

			# 转义特殊字符
			value_str = str(value)
			# if self.delimiter in value_str or '"' in value_str or '\n' in value_str:
			# 	value_str = f'"{value_str.replace('"', '""')}"'

			row.append(value_str)

		return self.delimiter.join(row)


class GELFFormatter(LogFormatter):
	"""GELF（Graylog扩展日志格式）格式化器"""

	def __init__ (self):
		super().__init__(format_template="", color_mode=ColorMode.NEVER)

	def format (self, log_record: Dict[str, Any], **kwargs) -> str:
		"""格式化为GELF"""
		gelf_dict = {
			"version": "1.1",
			"host": log_record.get("host", "unknown"),
			"short_message": log_record.get("message", ""),
			"full_message": log_record.get("message", ""),
			"timestamp": time.time(),
			"level": self._convert_level_to_syslog(log_record.get("level", "INFO")),
			"_logger": log_record.get("logger", ""),
			"_module": log_record.get("module", ""),
			"_function": log_record.get("function", ""),
			"_line": log_record.get("line", 0),
		}

		# 添加额外字段（前缀为下划线）
		for key, value in log_record.items():
			if key not in gelf_dict and not key.startswith("_"):
				gelf_dict[f"_{key}"] = value

		return json.dumps(gelf_dict, ensure_ascii=False)

	def _convert_level_to_syslog (self, level: str) -> int:
		"""将日志级别转换为Syslog级别"""
		level_map = {
			"DEBUG": 7,
			"INFO": 6,
			"WARNING": 4,
			"ERROR": 3,
			"CRITICAL": 2
		}
		return level_map.get(level.upper(), 6)


# 格式渲染器
class LogRenderer:
	"""日志渲染器（高级格式化）"""

	def __init__ (self, formatter: LogFormatter = None):
		self.formatter = formatter or FormatterFactory.create_default_formatter()

	def render (self, log_record: Dict[str, Any],
	            output_format: str = "text") -> str:
		"""
		渲染日志记录

		Args:
			log_record: 日志记录
			output_format: 输出格式（text, json, csv, html）

		Returns:
			str: 渲染后的日志
		"""
		if output_format == "text":
			return self.formatter.format(log_record)
		elif output_format == "json":
			return self.formatter.to_json_format(log_record)
		elif output_format == "csv":
			records = [log_record]
			return self.formatter.to_csv_format(records)
		elif output_format == "html":
			return self._render_html(log_record)
		else:
			raise ValueError(f"不支持的输出格式: {output_format}")

	def _render_html (self, log_record: Dict[str, Any]) -> str:
		"""渲染为HTML格式"""
		level = log_record.get("level", "INFO").lower()

		# 根据级别选择CSS类
		level_class = {
			"debug": "log-debug",
			"info": "log-info",
			"warning": "log-warning",
			"error": "log-error",
			"critical": "log-critical"
		}.get(level, "log-info")

		html = f"""
        <div class="log-entry {level_class}">
            <span class="log-timestamp">{log_record.get('timestamp', '')}</span>
            <span class="log-level">{log_record.get('level', '')}</span>
            <span class="log-logger">{log_record.get('logger', '')}</span>
            <span class="log-module">{log_record.get('module', '')}.{log_record.get('function', '')}:{log_record.get('line', 0)}</span>
            <span class="log-message">{log_record.get('message', '')}</span>
        </div>
        """

		return html.strip()

	def render_batch (self, log_records: List[Dict[str, Any]],
	                  output_format: str = "text") -> str:
		"""批量渲染日志记录"""
		if output_format == "text":
			lines = []
			for record in log_records:
				lines.append(self.formatter.format(record))
			return "\n".join(lines)
		elif output_format == "json":
			return json.dumps(log_records, indent=2, ensure_ascii=False, default=str)
		elif output_format == "csv":
			return self.formatter.to_csv_format(log_records)
		elif output_format == "table":
			return self.formatter.to_table_format(log_records)
		else:
			raise ValueError(f"不支持的输出格式: {output_format}")


# 使用示例
if __name__ == "__main__":
	print("=== 日志格式化器示例 ===")

	# 创建测试日志记录
	test_record = {
		"timestamp": "2023-12-01T10:30:45.123456Z",
		"level": "INFO",
		"logger": "app.module",
		"module": "quant_server.core",
		"function": "process_data",
		"line": 123,
		"message": "数据处理完成",
		"extra": {"records": 100, "duration": 1.234},
		"request_id": "req_123456",
		"user_id": "user_789"
	}

	# 1. 默认格式化器
	print("\n1. 默认格式化器:")
	formatter = FormatterFactory.create_default_formatter()
	formatted = formatter.format(test_record)
	print(formatted)

	# 2. 详细格式化器
	print("\n2. 详细格式化器:")
	verbose_formatter = FormatterFactory.create_verbose_formatter()
	formatted = verbose_formatter.format(test_record)
	print(formatted)

	# 3. 简单格式化器
	print("\n3. 简单格式化器:")
	simple_formatter = FormatterFactory.create_simple_formatter()
	formatted = simple_formatter.format(test_record)
	print(formatted)

	# 4. JSON格式化器
	print("\n4. JSON格式化器:")
	json_formatter = FormatterFactory.create_json_formatter(indent=2)
	formatted = json_formatter.format(test_record)
	print(formatted)

	# 5. CSV格式化器
	print("\n5. CSV格式化器:")
	csv_formatter = FormatterFactory.create_csv_formatter()
	formatted = csv_formatter.format(test_record)
	print(formatted)

	# 6. 表格格式
	print("\n6. 表格格式:")
	records = [test_record, test_record, test_record]
	table = formatter.to_table_format(records)
	print(table)

	# 7. 自定义格式
	print("\n7. 自定义格式:")
	custom_formatter = formatter.create_custom_format("${level}: ${message} [${request_id}]")
	formatted = custom_formatter.format(test_record)
	print(formatted)

	# 8. 渲染器
	print("\n8. 渲染器:")
	renderer = LogRenderer(formatter)

	# 文本渲染
	text_output = renderer.render(test_record, "text")
	print("文本输出:", text_output[:100] + "...")

	# JSON渲染
	json_output = renderer.render(test_record, "json")
	print("JSON输出:", json_output[:100] + "...")

	print("\n示例完成")