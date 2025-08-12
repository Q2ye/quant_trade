import importlib
import sys

import yaml
import os
import time
import logging
from typing import Dict, Optional

from .signal_manager import SignalManager
from quantCore.engineManager.engines.backtest_engine import BacktestEngine
from .event_engine import EventEngine, Event
from .stock_selector import StockSelector
from quantCore.engineManager.engines.cta_engine import CtaEngine
from quantCore.engineManager.engines.alpha_engine import AlphaEngine
from .strategy_engine import StrategyEngine
from ..database.db_connector import DbConnector
from quantCore.database.data_sources.data_source_manager import DataSourceManager
from ..utils.notification import init_notifiers_from_config
from ..strategies.base_strategy import BaseStrategy

logger = logging.getLogger('main_engine')


class MainEngine:
    """主引擎（优化统一版）"""

    def __init__(self, event_engine: EventEngine = None):

        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if project_root not in sys.path:
            sys.path.append(project_root)

        # 初始化事件引擎
        self.event_engine = event_engine or EventEngine()

        # 初始化核心组件
        self.db = None
        self.data_source_manager = None
        self.stock_selector = None
        self.signal_manager = SignalManager(self)

        # 初始化策略引擎
        self.strategies: Dict[str, BaseStrategy] = {}
        self.engines: Dict[str, StrategyEngine] = {}

        # 初始化核心引擎
        self._init_core_engines()
        # 注册事件处理
        self.event_engine.register("signal", self.process_signal)
        self.event_engine.register("logs", self.process_log)
        self.event_engine.register("error", self.process_error)

        # 启动事件引擎
        self.event_engine.start()
        logger.info("主引擎初始化完成")

    """单独提供启动事件引擎的方法"""
    def start_event_engine(self):
        self.event_engine.start()
        logger.info("事件引擎已启动")

    """初始化核心引擎并注册"""
    def _init_core_engines(self):

        # 注册内置引擎
        self.register_engine('cta', CtaEngine(self, self.event_engine))
        self.register_engine('alpha', AlphaEngine(self))
        self.register_engine('backtest', BacktestEngine(self))

        # 注册自定义引擎（示例）
        # self.register_engine('custom', CustomEngine(self))

    """注册新的策略引擎类型"""
    def register_engine(self, engine_type: str, engine: StrategyEngine):

        if engine_type in self.engines:
            logger.warning(f"引擎类型 {engine_type} 已存在，将被覆盖")
        self.engines[engine_type] = engine
        logger.info(f"策略引擎注册: {engine_type} -> {type(engine).__name__}")

    """获取指定类型的引擎"""
    def get_engine(self, engine_type: str) -> Optional[StrategyEngine]:

        return self.engines.get(engine_type)

    """加载主配置文件"""
    def load_config(self, config_file: str = "config/main.yaml"):

        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # 初始化数据库连接器
            database_config = config.get('database', {})
            self.db = DbConnector(database_config)
            if not self.db.connect():
                logger.error("数据库连接失败")
                raise RuntimeError("数据库连接失败")
            self.db.create_tables_if_not_exist()
            logger.info("数据库连接并初始化完成")

            # 初始化数据源管理器
            data_sources_config = config.get('data_sources', {})
            config_path = data_sources_config.get('config_path', 'config/data_sources.yaml')
            self.data_source_manager = DataSourceManager(
                config_path=config_path,
                db_connector=self.db
            )

            # 初始化选股器
            self.stock_selector = StockSelector(self, self.data_source_manager)

            # 加载通知渠道
            self._setup_notifiers(config.get('notifiers', {}))

            # 加载策略
            self.load_strategies(config.get('strategy_config_path', 'config/strategies'))

            logger.info("主配置加载完成")
            return config
        except Exception as e:
            logger.error(f"加载主配置失败: {str(e)}", exc_info=True)
            raise

    """设置通知渠道"""
    def _setup_notifiers(self, notifier_config: dict):

        init_notifiers_from_config(notifier_config)
        logger.info(f"已初始化通知渠道: {list(notifier_config.keys())}")

    """加载策略配置"""
    def load_strategies(self, config_path: str = "config/strategies"):

        logger.info(f"开始加载策略配置: {config_path}")

        if not os.path.exists(config_path):
            logger.error(f"策略配置路径不存在: {config_path}")
            return

        for filename in os.listdir(config_path):
            if filename.endswith((".yaml", ".yml")):
                try:
                    filepath = os.path.join(config_path, filename)
                    with open(filepath, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)

                    self.add_strategy(config)
                    logger.info(f"策略配置加载成功: {filename}")
                except Exception as e:
                    logger.error(f"加载策略配置失败 [{filename}]: {str(e)}", exc_info=True)

    """添加策略"""
    def add_strategy(self, config: dict):

        try:
            # 特殊处理 TensorFlow 依赖
            engine_type = config.get("engine", "base")
            strategy_name = config["name"]

            # 动态加载策略类
            class_path = config.get('module') or config.get('class')
            if not class_path:
                raise ValueError("策略配置缺少 'module' 或 'class' 字段")

            # 动态加载策略类
            logger.debug(f"加载策略类: {class_path}")
            module_path, class_name = class_path.rsplit('.', 1)

            try:
                module = importlib.import_module(module_path)
            except ModuleNotFoundError as e:
                # 添加详细错误信息
                logger.error(f"模块导入失败: {str(e)}")
                logger.error("当前系统路径: %s", sys.path)
                logger.error("尝试从项目根目录导入...")

                # 添加项目根目录到路径
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if project_root not in sys.path:
                    sys.path.append(project_root)
                    logger.info(f"添加项目根目录到路径: {project_root}")

                # 重试导入
                module = importlib.import_module(module_path)

            strategy_class = getattr(module, class_name)
            # 创建策略实例
            strategy = strategy_class(config, main_engine=self)

            # 获取策略引擎
            engine = self.get_engine(engine_type)

            if engine:
                # 添加到策略引擎
                engine.add_strategy(strategy)
                logger.info(f"策略 {strategy_name} 添加到 {engine_type} 引擎")
            else:
                # 添加到选股引擎（默认）
                self.stock_selector.add_strategy(strategy)
                logger.info(f"策略 {strategy_name} 添加到选股引擎")

            # 设置策略引擎引用
            strategy.set_engine(engine)

            logger.info(f"策略 {strategy_name} 加载成功")
        except Exception as e:
            logger.error(f"添加策略失败: {str(e)}", exc_info=True)

    """运行引擎"""
    def run(self, mode: str = "live"):

        logger.info(f"启动主引擎，模式: {mode}")

        if mode == "live":
            # 每日定时执行选股
            self.event_engine.register_timer(
                interval=3600,  # 每小时检查一次
                handler=self._check_and_run_selection
            )
            # 启动所有策略引擎
            self._start_all_engines()

            # 保持主线程运行
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                self.shutdown()

        elif mode == "backtest":
            # 回测模式需要单独初始化
            logger.warning("回测模式需要单独初始化，请使用init_backtest方法")

        elif mode == "alpha":
            # 启动AI策略引擎
            self.engines['alpha'].run_engine()

    """启动所有策略引擎"""
    def _start_all_engines(self):

        logger.info("启动所有策略引擎")
        for engine in self.engines.values():
            if hasattr(engine, 'start_all_strategies'):
                engine.start_all_strategies()
            if hasattr(engine, 'run_engine'):
                # 对于需要主循环的引擎（如AlphaEngine）
                engine.run_engine()

    """检查并运行选股策略"""
    def _check_and_run_selection(self):
        if self.stock_selector._is_after_market_close():
            logger.info("触发每日选股任务")
            self.stock_selector.run_selection()

    """处理信号事件"""
    def process_signal(self, event):
        self.signal_manager.process_signal(event)

    """处理日志事件"""
    def process_log(self, event):
        message = event.data
        logger.info(f"[LOG] {message}")

    """处理错误事件"""
    def process_error(self, event):
        error = event.data
        logger.error(f"[ERROR] {error}")

    def write_log(self, message: str):
        """记录日志"""
        self.event_engine.put(Event("logs", message))

    def write_error(self, error: str):
        """记录错误"""
        self.event_engine.put(Event("error", error))

    def shutdown(self):
        """关闭引擎"""
        logger.info("正在关闭主引擎...")

        # 停止所有策略引擎（使用统一接口）
        for engine in self.engines.values():
            if hasattr(engine, 'stop_all_strategies'):
                engine.stop_all_strategies()
            if hasattr(engine, 'stop_engine'):
                engine.stop_engine()

        # 停止事件引擎
        self.event_engine.stop()

            # 关闭数据库连接
        if self.db:
            self.db.close()

        logger.info("主引擎已关闭")

    """初始化回测"""
    def init_backtest(self, config: dict):
        strategy_config = config['strategy']
        # 添加策略
        self.add_strategy(strategy_config)
        # 获取策略实例
        strategy_name = strategy_config['name']
        strategy = None
        # 安全地获取策略实例
        for engine in self.engines.values():
            if hasattr(engine, 'strategies') and strategy_name in engine.strategies:
                strategy = engine.strategies[strategy_name]
                break

        if not strategy:
            # 尝试从主引擎的策略字典获取
            strategy = self.strategies.get(strategy_name)

        if not strategy:
            logger.error(f"未找到策略: {strategy_name}")
            return None

        # 设置回测引擎策略
        backtest_engine = self.engines['backtest']

        # 使用安全的方式调用回测引擎特有的方法
        if hasattr(backtest_engine, 'set_strategy'):
            backtest_engine.set_strategy(strategy)
        else:
            logger.error("回测引擎不支持 set_strategy 方法")
            return None

        # 加载数据
        symbols = config.get('symbols', [])

        if hasattr(backtest_engine, 'load_data'):
            backtest_engine.load_data(
                symbols,
                config['start_date'],
                config['end_date']
            )
        else:
            logger.error("回测引擎不支持 load_data 方法")
            return None

        # 设置初始资金
        initial_capital = config.get('initial_capital', 1000000)

        logger.info("回测引擎初始化完成")

        # 使用正确的参数调用回测
        return backtest_engine.run_backtest(strategy_name, {
            'symbols': symbols,
            'start_date': config['start_date'],
            'end_date': config['end_date'],
            'initial_capital': initial_capital
        })

    """获取所有策略实例，包括引擎和选股器中的策略"""
    def get_all_strategies(self):
        strategies = []
        # 1. 收集所有引擎中的策略
        logger.info(f"从引擎中获取策略")
        for engine in self.engines.values():
            try:
                # 使用新的get_strategies方法
                engine_strategies = engine.get_strategies()
                if isinstance(engine_strategies, list):
                    strategies.extend(engine_strategies)
            except Exception as e:
                logger.error(f"从引擎 {type(engine).__name__} 获取策略失败: {str(e)}", exc_info=True)

        # 2. 收集选股器中的策略
        logger.info(f"从收集选股器中获取策略")
        if self.stock_selector:
            try:
                # 使用选股器的get_strategies方法
                selector_strategies = self.stock_selector.get_strategies()
                if isinstance(selector_strategies, list):
                    strategies.extend(selector_strategies)
            except Exception as e:
                logger.error(f"从选股器获取策略失败: {str(e)}", exc_info=True)

        # 3. 确保所有策略都有基本属性
        for strategy in strategies:
            # 添加缺失的属性
            if not hasattr(strategy, 'status'):
                setattr(strategy, 'status', '未运行')
            if not hasattr(strategy, 'position'):
                setattr(strategy, 'position', 0)
            if not hasattr(strategy, 'pnl'):
                setattr(strategy, 'pnl', 0.0)
            if not hasattr(strategy, 'last_update'):
                setattr(strategy, 'last_update', '')

        return strategies

    def init_strategy(self, strategy_name: str):
        """初始化策略"""
        logger.info(f"初始化策略: {strategy_name}")

        # 在所有引擎中查找策略
        for engine in self.engines.values():
            strategies = engine.get_strategies()
            for strategy in strategies:
                if strategy.name == strategy_name:
                    # 调用策略的初始化方法
                    if hasattr(strategy, 'on_init') and callable(strategy.on_init):
                        strategy.on_init()
                        logger.info(f"策略 {strategy_name} 已初始化")
                    else:
                        logger.warning(f"策略 {strategy_name} 没有初始化方法")
                    return

        # 在选股器中查找策略
        if self.stock_selector:
            strategies = self.stock_selector.get_strategies()
            for strategy in strategies:
                if strategy.name == strategy_name:
                    # 选股策略通常不需要单独初始化
                    logger.info(f"选股策略 {strategy_name} 不需要显式初始化")
                    return

        logger.warning(f"未找到策略: {strategy_name}")

    def start_strategy(self, strategy_name: str):
        """启动策略"""
        logger.info(f"启动策略: {strategy_name}")

        # 在所有引擎中查找策略
        for engine in self.engines.values():
            strategies = engine.get_strategies()
            for strategy in strategies:
                if strategy.name == strategy_name:
                    # 如果引擎支持启动单个策略9
                    if hasattr(engine, 'start_strategy') and callable(engine.start_strategy):
                        engine.start_strategy(strategy_name)
                        logger.info(f"策略 {strategy_name} 已启动")
                    else:
                        # 尝试直接调用策略的启动方法
                        if hasattr(strategy, 'on_start') and callable(strategy.on_start):
                            strategy.on_start()
                            logger.info(f"策略 {strategy_name} 已启动")
                        else:
                            logger.warning(f"引擎不支持启动策略: {engine.__class__.__name__}")
                    return

        # 在选股器中查找策略
        if self.stock_selector:
            strategies = self.stock_selector.get_strategies()
            for strategy in strategies:
                if strategy.name == strategy_name:
                    # 选股策略通常不需要单独启动
                    logger.info(f"选股策略 {strategy_name} 会在计划时间自动运行")
                    return

        logger.warning(f"未找到策略: {strategy_name}")

    def stop_strategy(self, strategy_name: str):
        """停止策略"""
        logger.info(f"停止策略: {strategy_name}")

        # 在所有引擎中查找策略
        for engine in self.engines.values():
            strategies = engine.get_strategies()
            for strategy in strategies:
                if strategy.name == strategy_name:
                    # 如果引擎支持停止单个策略
                    if hasattr(engine, 'stop_strategy') and callable(engine.stop_strategy):
                        engine.stop_strategy(strategy_name)
                        logger.info(f"策略 {strategy_name} 已停止")
                    else:
                        # 尝试直接调用策略的停止方法
                        if hasattr(strategy, 'on_stop') and callable(strategy.on_stop):
                            strategy.on_stop()
                            logger.info(f"策略 {strategy_name} 已停止")
                        else:
                            logger.warning(f"引擎不支持停止策略: {engine.__class__.__name__}")
                    return

        # 在选股器中查找策略
        if self.stock_selector:
            strategies = self.stock_selector.get_strategies()
            for strategy in strategies:
                if strategy.name == strategy_name:
                    # 选股策略通常不需要单独停止
                    logger.info(f"选股策略 {strategy_name} 会在完成当前任务后停止")
                    return

        logger.warning(f"未找到策略: {strategy_name}")