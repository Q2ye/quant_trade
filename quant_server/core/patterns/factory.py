"""
工厂模式实现

提供一个创建对象的接口，但让子类决定实例化哪个类。
工厂方法让类的实例化延迟到子类。

在量化交易系统中的典型应用：
1. 策略工厂：根据策略类型创建不同的策略实例
2. 数据源工厂：根据配置创建不同的数据源
3. 引擎工厂：创建不同类型的交易引擎
4. 适配器工厂：创建券商适配器
"""

from abc import ABC, abstractmethod
from typing import Type, Dict, Any, Optional, TypeVar, Generic
from enum import Enum

T = TypeVar('T')  # 产品类型
C = TypeVar('C')  # 创建器类型


class Factory(ABC, Generic[T]):
	"""
	工厂基类

	定义创建对象的接口。
	"""

	@abstractmethod
	def create (self, *args, **kwargs) -> T:
		"""创建产品实例"""
		pass

	@abstractmethod
	def get_product_type (self) -> Type[T]:
		"""获取产品类型"""
		pass


class AbstractFactory(ABC):
	"""
	抽象工厂

	创建一系列相关或依赖对象的接口，而不需要指定它们的具体类。
	"""

	@abstractmethod
	def create_product_a (self) -> Any:
		"""创建产品A"""
		pass

	@abstractmethod
	def create_product_b (self) -> Any:
		"""创建产品B"""
		pass


class SimpleFactory:
	"""
	简单工厂

	根据输入参数创建不同的产品。
	"""

	def __init__ (self, product_map: Dict[str, Type[T]]):
		"""
		初始化简单工厂

		Args:
			product_map: 产品类型映射 {产品标识: 产品类}
		"""
		self._product_map = product_map

	def create (self, product_type: str, *args, **kwargs) -> T:
		"""
		创建产品

		Args:
			product_type: 产品类型标识
			*args, **kwargs: 传递给产品构造函数的参数

		Returns:
			T: 产品实例

		Raises:
			ValueError: 如果产品类型不存在
		"""
		if product_type not in self._product_map:
			raise ValueError(f"未知的产品类型: {product_type}")

		product_class = self._product_map[product_type]
		return product_class(*args, **kwargs)

	def register_product (self, product_type: str, product_class: Type[T]) -> None:
		"""注册新产品类型"""
		self._product_map[product_type] = product_class

	def unregister_product (self, product_type: str) -> None:
		"""注销产品类型"""
		if product_type in self._product_map:
			del self._product_map[product_type]


class FactoryMethod:
	"""
	工厂方法模式

	定义一个创建对象的接口，但让子类决定实例化哪个类。
	"""

	@abstractmethod
	def factory_method (self) -> T:
		"""工厂方法：子类必须实现此方法来创建产品"""
		pass

	def create (self) -> T:
		"""使用工厂方法创建产品"""
		product = self.factory_method()
		# 可以进行一些公共的初始化操作
		self._post_create(product)
		return product

	def _post_create (self, product: T) -> None:
		"""创建后的公共处理（可选）"""
		pass


class ProductRegistry:
	"""
	产品注册器

	用于管理工厂和产品注册。
	"""

	def __init__ (self):
		self._factories: Dict[str, Factory] = {}
		self._products: Dict[str, Type] = {}

	def register_factory (self, factory_name: str, factory: Factory) -> None:
		"""注册工厂"""
		self._factories[factory_name] = factory

	def register_product (self, product_name: str, product_class: Type) -> None:
		"""注册产品"""
		self._products[product_name] = product_class

	def get_factory (self, factory_name: str) -> Optional[Factory]:
		"""获取工厂"""
		return self._factories.get(factory_name)

	def get_product_class (self, product_name: str) -> Optional[Type]:
		"""获取产品类"""
		return self._products.get(product_name)

	def create_product (self, factory_name: str, *args, **kwargs) -> Any:
		"""使用工厂创建产品"""
		factory = self.get_factory(factory_name)
		if not factory:
			raise ValueError(f"工厂不存在: {factory_name}")
		return factory.create(*args, **kwargs)