# core/engines/strategy_manager_engine.py
import asyncio
import importlib
import logging
from typing import Dict, Any, List

from quant_server.db import get_db_session
from quant_server.db.data_service import DataService
from ..event_engine import EventEngine, Event
from ..strategy_engine import StrategyEngine

logger = logging.getLogger(__name__)


class StrategyManagerEngine(StrategyEngine):
    """策略管理引擎 - 负责策略的加载、添加和管理"""

    def __init__(self, main_engine, event_engine: EventEngine):
        super().__init__(main_engine, event_engine)
        self.main_engine = main_engine
        self.event_engine = event_engine

        # 数据库会话和数据服务
        session = get_db_session()
        self.data_service = DataService(session)

        # 策略存储
        # self.strategy_engine_map: Dict[str, str] = {}

        # 注册事件处理
        event_engine.register("strategy_load", self.handle_strategy_load)
        event_engine.register("strategy_add", self.handle_strategy_add)
        event_engine.register("strategy_remove", self.handle_strategy_remove)

        logger.info("策略管理引擎初始化完成")

    async def initialize(self):
        """初始化策略管理引擎"""
        logger.info("初始化策略管理引擎")

        # 从数据库加载策略配置
        await self._load_strategies_from_db()

        logger.info("策略管理引擎初始化完成")

    async def _load_strategies_from_db(self):
        """从数据库加载策略配置"""
        try:
            # 使用data_service获取所有策略
            strategies: List = self.data_service.strategy.get_all()
            for strategy in strategies:
                try:
                    # 将SQLAlchemy对象转换为字典
                    strategy_config = {
                        'id': strategy.id,
                        'name': strategy.name,
                        'user_id': strategy.user_id,
                        'description': strategy.description,
                        'class_name': strategy.class_name,
                        'module_path': strategy.module_path,
                        'status': strategy.status,
                        'parameters': strategy.parameters,
                    }
                    await self.add_strategy(strategy_config)
                except Exception as e:
                    logger.error(f"加载策略失败 {strategy.name}: {str(e)}")
        except Exception as e:
            logger.error(f"从数据库加载策略失败: {str(e)}")

    async def add_strategy(self, config: Dict[str, Any]) -> Any:
        """添加策略"""
        strategy_name = config["name"]

        if strategy_name in self.strategies:
            logger.warning(f"策略已存在: {strategy_name}")
            return self.strategies[strategy_name]

        # 动态加载策略类
        try:
            module_path, class_name = config["class_name"].rsplit(".", 1)
            module = importlib.import_module(module_path)
            strategy_class = getattr(module, class_name)
        except Exception as e:
            logger.error(f"加载策略类失败 {config['class_name']}: {str(e)}")
            return None

        # 创建策略实例
        strategy = strategy_class(config, main_engine=self.main_engine)

        # 添加到策略字典
        self.strategies[strategy_name] = strategy
        logger.info(f"策略加载成功: {strategy_name}")

        # 发送策略添加事件
        self.event_engine.put(Event(
            "strategy_added",
            {"strategy_name": strategy_name, "config": config},
            "strategy_manager"
        ))

        return strategy

    def remove_strategy(self, strategy_name: str):
        """移除策略"""
        if strategy_name in self.strategies:
            strategy = self.strategies[strategy_name]

            # 如果策略正在运行，先停止
            if hasattr(strategy, 'is_running') and strategy.is_running:
                strategy.on_stop()

            del self.strategies[strategy_name]
            logger.info(f"策略移除成功: {strategy_name}")

            # 发送策略移除事件
            self.event_engine.put(Event(
                "strategy_removed",
                {"strategy_name": strategy_name},
                "strategy_manager"
            ))
        else:
            logger.warning(f"尝试移除不存在的策略: {strategy_name}")

    def get_strategy(self, strategy_name: str) -> Any:
        """获取策略实例"""
        return self.strategies.get(strategy_name)


    def get_all_strategies(self) -> Dict[str, Any]:
        """获取所有策略"""
        return self.strategies.copy()

    def handle_strategy_load(self, event):
        """处理策略加载事件"""
        config = event.data
        asyncio.create_task(self.add_strategy(config))

    def handle_strategy_add(self, event):
        """处理策略添加事件"""
        config = event.data
        asyncio.create_task(self.add_strategy(config))

    def handle_strategy_remove(self, event):
        """处理策略移除事件"""
        strategy_name = event.data
        self.remove_strategy(strategy_name)


    async def start_strategy(self, strategy_name: str, engine_type: str):
        """启动策略"""
        if strategy_name not in self.strategies:
            raise ValueError(f"策略不存在: {strategy_name}")

        if engine_type not in self.main_engine.engines:
            raise ValueError(f"引擎不存在: {engine_type}")

        strategy = self.strategies[strategy_name]
        target_engine = self.main_engine.engines[engine_type]

        # 如果策略已经在其他引擎中运行，先停止
        current_engine_type = self.main_engine.get_strategy_engine(strategy_name)
        if current_engine_type and current_engine_type != engine_type:
            await self.stop_strategy(strategy_name)

        # 添加到目标引擎
        target_engine.add_strategy(strategy)

        # 记录策略与引擎的映射关系
        self.main_engine.strategy_engine_map[strategy_name] = engine_type

        # 启动策略
        target_engine.start_strategy(strategy_name)
        logger.info(f"策略 {strategy_name} 已在 {engine_type} 引擎中启动")

        # 更新策略状态为运行中
        strategy.status = "running"

        # 发送策略启动事件
        self.event_engine.put(Event(
            "strategy_started",
            {"strategy_name": strategy_name, "engine_type": engine_type},
            "strategy_manager"
        ))

    async def stop_strategy(self, strategy_name: str):
        """停止策略"""
        if strategy_name not in self.main_engine.strategy_engine_map:
            logger.warning(f"策略 {strategy_name} 未在任何引擎中运行")
            return

        engine_type = self.main_engine.strategy_engine_map[strategy_name]

        if engine_type in self.main_engine.engines:
            target_engine = self.main_engine.engines[engine_type]

            # 停止策略
            target_engine.stop_strategy(strategy_name)

            # 从引擎中移除策略
            target_engine.remove_strategy(strategy_name)

            # 移除映射关系
            del self.main_engine.strategy_engine_map[strategy_name]

            # 更新策略状态为已停止
            if strategy_name in self.strategies:
                self.strategies[strategy_name].status = "stopped"

            logger.info(f"策略 {strategy_name} 已从 {engine_type} 引擎中停止")

            # 发送策略停止事件
            self.event_engine.put(Event(
                "strategy_stopped",
                {"strategy_name": strategy_name},
                "strategy_manager"
            ))
        else:
            logger.warning(f"引擎不存在: {engine_type}")
