"""
设计模式模块

提供量化交易系统中常用的设计模式实现。
这些模式用于解决系统架构中的常见问题，确保代码的可维护性、可扩展性和可重用性。

设计原则：
1. 单一职责：每个模式只解决一个特定问题
2. 开闭原则：对扩展开放，对修改关闭
3. 依赖倒置：依赖抽象而非具体实现
4. 接口隔离：客户端不应依赖不需要的接口
5. 里氏替换：子类可以替换父类
"""

from .singleton import Singleton, SingletonMeta
from .observer import Observer, Observable
from .factory import Factory, AbstractFactory
from .strategy_pattern import Strategy, Context
from .command import Command, CommandInvoker
from .state_machine import StateMachine, State, Transition

__all__ = [
	# 单例模式
	'Singleton',
	'SingletonMeta',

	# 观察者模式
	'Observer',
	'Observable',

	# 工厂模式
	'Factory',
	'AbstractFactory',

	# 策略模式
	'Strategy',
	'Context',

	# 命令模式
	'Command',
	'CommandInvoker',

	# 状态机模式
	'StateMachine',
	'State',
	'Transition',
]