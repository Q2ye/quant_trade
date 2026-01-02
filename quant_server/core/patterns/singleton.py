"""
单例模式实现

确保一个类只有一个实例，并提供一个全局访问点。
在量化交易系统中用于管理全局资源，如配置、日志、缓存等。

典型应用场景：
1. 系统配置管理器
2. 全局日志管理器
3. 数据库连接池
4. Redis缓存客户端
5. 事件引擎（全局唯一）
"""

from threading import Lock
from typing import Any, Type, TypeVar

T = TypeVar('T', bound='Singleton')


class SingletonMeta(type):
	"""
	单例元类

	使用元类实现单例模式，确保线程安全。
	"""

	_instances = {}
	_lock: Lock = Lock()

	def __call__ (cls: Type[T], *args: Any, **kwargs: Any) -> T:
		"""确保类只有一个实例"""
		if cls not in cls._instances:
			with cls._lock:
				if cls not in cls._instances:
					instance = super().__call__(*args, **kwargs)
					cls._instances[cls] = instance
		return cls._instances[cls]

	def clear (cls):
		"""清除单例实例（主要用于测试）"""
		if cls in cls._instances:
			del cls._instances[cls]


class Singleton(metaclass=SingletonMeta):
	"""
	单例基类

	继承此类即可获得单例功能。

	示例：
	```python
	class ConfigManager(Singleton):
		def __init__(self):
			self.config = {}

	# 两次获取的是同一个实例
	config1 = ConfigManager()
	config2 = ConfigManager()
	assert config1 is config2  # True
	```
	"""

	def __init__ (self):
		"""初始化单例实例"""
		# 防止通过__init__重新初始化
		if not hasattr(self, '_initialized'):
			self._initialized = True
			self._setup()

	def _setup (self):
		"""子类可以重写此方法进行初始化"""
		pass

	@classmethod
	def get_instance (cls) -> 'Singleton':
		"""获取单例实例（替代直接实例化）"""
		return cls()

	@classmethod
	def destroy (cls):
		"""销毁单例实例（主要用于测试或重启）"""
		cls.clear()