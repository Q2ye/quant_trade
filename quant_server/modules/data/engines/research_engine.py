# -*- coding: utf-8 -*-
"""
因子研究引擎 - 基于引擎框架的重构实现

核心职责：
1. 因子计算和生成
2. 因子性能评估
3. 因子组合优化
4. 因子数据管理

重构原则：
- 继承EngineBase基类，遵循统一的生命周期管理
- 使用EngineFactory进行创建和管理
- 通过EventEngine实现事件驱动通信
- 支持依赖注入和配置驱动
- 提供完整的监控和健康检查
"""

import asyncio
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

# 导入统一类型定义
from quant_server.core.engines.types import (
    EngineConfig as EngineConfigEntity,
    Event as EventEntity
)
from quant_server.core.engines.types.enums import (
    EngineType,
    EngineCategory,
    ComponentStatus,
    HealthStatus,
    EngineErrorLevel
)

# 导入引擎基类和系统组件
from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.engines.utils.engine_factory import EngineFactory, EngineDescriptor

logger = logging.getLogger(__name__)


class ResearchTaskType(str, Enum):
    """研究任务类型枚举"""
    FACTOR_CALCULATION = "factor_calculation"  # 因子计算
    FACTOR_ANALYSIS = "factor_analysis"  # 因子分析
    FACTOR_OPTIMIZATION = "factor_optimization"  # 因子优化
    FACTOR_BACKTEST = "factor_backtest"  # 因子回测
    FACTOR_SELECTION = "factor_selection"  # 因子选择
    FACTOR_VALIDATION = "factor_validation"  # 因子验证


class FactorResearchEngine(EngineBase):
    """
    因子研究引擎

    基于引擎框架重构的实现，提供完整的因子研究功能：
    1. 继承EngineBase基类，遵循统一的生命周期管理
    2. 使用事件驱动架构进行模块间通信
    3. 支持依赖注入和配置驱动
    4. 提供完整的监控、健康检查和错误处理

    设计模式：
    - 观察者模式：通过事件引擎实现解耦通信
    - 策略模式：支持不同的因子计算和分析策略
    - 模板方法模式：定义研究任务的执行流程
    - 工厂模式：支持研究任务的创建和管理
    """

    # 引擎类型定义
    ENGINE_TYPE = EngineType.RESEARCH

    def __init__(
        self,
        config: EngineConfigEntity,
        event_engine: Optional[EventEngine] = None,
        resource_pool: Optional[Any] = None
    ):
        """
        初始化因子研究引擎

        Args:
            config: 引擎配置实体
            event_engine: 事件引擎实例
            resource_pool: 资源池管理器
        """
        # 调用父类初始化
        super().__init__(config, event_engine, resource_pool)

        # 设置引擎类型
        self.record.engine_type = self.ENGINE_TYPE

        # 研究服务依赖（通过依赖注入）
        self._research_service = None
        self._cache_manager = None
        self._data_service = None

        # 研究任务管理
        self._active_tasks: Dict[str, Dict[str, Any]] = {}
        self._task_history: List[Dict[str, Any]] = []
        self._max_history_size = 1000

        # 因子缓存
        self._factor_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 3600  # 缓存过期时间（秒）

        # 默认因子配置
        self._default_factors: Dict[str, Dict[str, Any]] = {}

        # 性能统计
        self._performance_stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "factors_calculated": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_processing_time": 0.0
        }

        # 研究任务队列
        self._task_queue = asyncio.Queue()
        self._task_workers: List[asyncio.Task] = []
        self._max_workers = 5  # 最大并发任务数

        logger.info(f"因子研究引擎初始化完成: {self.config.name}")

    @property
    def engine_type(self) -> EngineType:
        """获取引擎类型"""
        return self.ENGINE_TYPE

    @property
    def research_service(self):
        """获取研究服务（懒加载）"""
        if self._research_service is None:
            # 动态导入以避免循环依赖
            try:
                from quant_server.modules.data.services.research_service import FactorResearchService
                self._research_service = FactorResearchService()
            except ImportError:
                logger.warning("研究服务不可用，部分功能可能受限")
                self._research_service = None
        return self._research_service

    @property
    def cache_manager(self):
        """获取缓存管理器（懒加载）"""
        if self._cache_manager is None:
            try:
                from ....shared.cache.cache_manager import CacheManager
                self._cache_manager = CacheManager()
            except ImportError:
                logger.warning("缓存管理器不可用，部分功能可能受限")
                self._cache_manager = None
        return self._cache_manager

    @property
    def data_service(self):
        """获取数据服务（懒加载）"""
        if self._data_service is None:
            try:
                from ...services.data_service import DataService
                self._data_service = DataService()
            except ImportError:
                logger.warning("数据服务不可用，部分功能可能受限")
                self._data_service = None
        return self._data_service

    # ==================== 引擎生命周期方法 ====================

    async def _on_initialize(self):
        """
        引擎初始化时的具体逻辑

        执行因子研究引擎的初始化，包括：
        1. 加载默认因子配置
        2. 初始化研究服务
        3. 注册事件处理器
        """
        logger.info(f"开始初始化因子研究引擎: {self.config.name}")

        try:
            # 加载默认因子配置
            await self._load_default_factors()

            # 初始化研究服务
            if self.research_service:
                await self.research_service.initialize()

            # 初始化缓存管理器
            if self.cache_manager:
                await self.cache_manager.initialize()

            # 注册事件处理器
            await self._register_event_handlers()

            # 更新状态
            self.record.update_health(
                HealthStatus.HEALTHY,
                "引擎初始化成功"
            )

            logger.info(f"因子研究引擎初始化成功: {self.config.name}")

        except Exception as e:
            logger.error(f"因子研究引擎初始化失败: {e}")
            self.record.update_health(
                HealthStatus.FAILED,
                f"初始化失败: {str(e)}"
            )
            raise

    async def _on_start(self):
        """
        引擎启动时的具体逻辑

        启动因子研究引擎，包括：
        1. 启动任务工作线程
        2. 恢复缓存数据
        3. 发布启动事件
        """
        logger.info(f"启动因子研究引擎: {self.config.name}")

        try:
            # 启动任务工作线程
            await self._start_task_workers()

            # 恢复缓存数据
            await self._restore_cache_data()

            # 发布启动事件
            await self._publish_event("research_engine_started", {
                "engine_id": self.engine_id,
                "engine_name": self.config.name,
                "timestamp": datetime.now().isoformat(),
                "config": self.config.to_dict()
            })

            logger.info(f"因子研究引擎启动成功: {self.config.name}")

        except Exception as e:
            logger.error(f"因子研究引擎启动失败: {e}")
            raise

    async def _on_stop(self):
        """
        引擎停止时的具体逻辑

        优雅停止因子研究引擎，包括：
        1. 停止所有任务工作线程
        2. 保存缓存数据
        3. 清理资源
        """
        logger.info(f"停止因子研究引擎: {self.config.name}")

        try:
            # 停止所有任务工作线程
            await self._stop_task_workers()

            # 取消所有进行中的任务
            await self._cancel_active_tasks()

            # 保存缓存数据
            await self._save_cache_data()

            # 清理资源
            self._active_tasks.clear()
            self._task_history.clear()

            logger.info(f"因子研究引擎停止成功: {self.config.name}")

        except Exception as e:
            logger.error(f"因子研究引擎停止异常: {e}")
            # 继续执行停止流程，不重新抛出异常

    async def _on_pause(self):
        """引擎暂停时的具体逻辑"""
        logger.info(f"暂停因子研究引擎: {self.config.name}")

        # 暂停所有任务工作线程
        for worker in self._task_workers:
            if not worker.done():
                worker.cancel()

        # 发布暂停事件
        await self._publish_event("research_engine_paused", {
            "engine_id": self.engine_id,
            "engine_name": self.config.name,
            "timestamp": datetime.now().isoformat()
        })

    async def _on_resume(self):
        """引擎恢复时的具体逻辑"""
        logger.info(f"恢复因子研究引擎: {self.config.name}")

        # 重新启动任务工作线程
        await self._start_task_workers()

        # 发布恢复事件
        await self._publish_event("research_engine_resumed", {
            "engine_id": self.engine_id,
            "engine_name": self.config.name,
            "timestamp": datetime.now().isoformat()
        })

    async def _on_health_check(self) -> Dict[str, Any]:
        """
        引擎特定的健康检查逻辑

        Returns:
            Dict[str, Any]: 引擎特定的健康检查信息
        """
        health_info = {
            "engine_type": self.ENGINE_TYPE.value,
            "active_tasks": len(self._active_tasks),
            "task_history_size": len(self._task_history),
            "factor_cache_size": len(self._factor_cache),
            "task_queue_size": self._task_queue.qsize(),
            "active_workers": len([w for w in self._task_workers if not w.done()]),
            "performance_stats": self._performance_stats,
            "default_factors": len(self._default_factors),
            "service_status": {
                "research_service": self.research_service is not None,
                "cache_manager": self.cache_manager is not None,
                "data_service": self.data_service is not None
            }
        }

        # 检查服务可用性
        if not self.research_service:
            self.record.update_health(
                HealthStatus.DEGRADED,
                "研究服务不可用"
            )

        # 检查缓存状态
        if len(self._factor_cache) > 10000:
            self.record.update_health(
                HealthStatus.DEGRADED,
                "因子缓存过大，可能需要清理"
            )

        return health_info

    async def _on_collect_metrics(self):
        """引擎特定的指标收集逻辑"""
        # 收集任务相关指标
        self.record.update_performance_metrics({
            "active_tasks": len(self._active_tasks),
            "completed_tasks": self._performance_stats["tasks_completed"],
            "failed_tasks": self._performance_stats["tasks_failed"],
            "factors_calculated": self._performance_stats["factors_calculated"],
            "cache_hit_rate": (
                self._performance_stats["cache_hits"] /
                (self._performance_stats["cache_hits"] + self._performance_stats["cache_misses"] + 1e-6)
            ),
            "avg_processing_time": (
                self._performance_stats["total_processing_time"] /
                (self._performance_stats["tasks_completed"] + 1e-6)
            ),
            "queue_size": self._task_queue.qsize(),
            "active_workers": len([w for w in self._task_workers if not w.done()])
        })

    async def _on_handle_event(self, event: EventEntity):
        """
        引擎特定的事件处理逻辑

        Args:
            event: 事件实体
        """
        try:
            if event.event_type == "research_task_request":
                await self._handle_research_task_request(event.data)
            elif event.event_type == "factor_calculation_request":
                await self._handle_factor_calculation_request(event.data)
            elif event.event_type == "factor_analysis_request":
                await self._handle_factor_analysis_request(event.data)
            elif event.event_type == "cancel_research_task":
                await self._handle_cancel_task_request(event.data)
            elif event.event_type == "get_research_status":
                await self._handle_status_request(event.data)

        except Exception as e:
            logger.error(f"处理研究事件失败: {event.event_type}, 错误: {e}")
            await self.handle_error(e, EngineErrorLevel.ERROR, {
                "event_type": event.event_type,
                "event_data": event.data
            })

    async def _on_auto_recover(self, error: Exception, context: Dict[str, Any]) -> bool:
        """
        引擎特定的自动恢复逻辑

        Args:
            error: 发生的异常
            context: 错误上下文

        Returns:
            bool: 恢复是否成功
        """
        logger.info(f"尝试自动恢复因子研究引擎: {self.config.name}")

        try:
            # 清理失败的任务
            failed_tasks = [
                task_id for task_id, task_info in self._active_tasks.items()
                if task_info.get("status") == "error"
            ]

            for task_id in failed_tasks:
                await self._cleanup_task(task_id)

            # 重启任务工作线程
            await self._stop_task_workers()
            await self._start_task_workers()

            logger.info(f"因子研究引擎自动恢复成功: {self.config.name}")
            return True

        except Exception as recover_error:
            logger.error(f"因子研究引擎自动恢复失败: {recover_error}")
            return False

    # ==================== 研究任务管理 ====================

    async def submit_research_task(
        self,
        task_type: ResearchTaskType,
        params: Dict[str, Any],
        priority: int = 1
    ) -> str:
        """
        提交研究任务

        Args:
            task_type: 任务类型
            params: 任务参数
            priority: 任务优先级（1-10，数字越大优先级越高）

        Returns:
            str: 任务ID
        """
        task_id = str(uuid.uuid4())

        task_info = {
            "task_id": task_id,
            "task_type": task_type,
            "params": params,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now(),
            "progress": 0,
            "result": None,
            "error": None
        }

        # 添加到活跃任务
        self._active_tasks[task_id] = task_info

        # 添加到任务队列
        await self._task_queue.put((priority, task_id))

        # 发布任务创建事件
        await self._publish_event("research_task_created", {
            "task_id": task_id,
            "task_type": task_type.value,
            "params": params,
            "priority": priority,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"研究任务已提交: {task_id} ({task_type.value})")

        return task_id

    async def _process_research_task(self, task_id: str):
        """
        处理研究任务

        Args:
            task_id: 任务ID
        """
        if task_id not in self._active_tasks:
            logger.warning(f"任务不存在: {task_id}")
            return

        task_info = self._active_tasks[task_id]
        task_type = task_info["task_type"]
        params = task_info["params"]

        try:
            # 更新任务状态
            task_info["status"] = "running"
            task_info["started_at"] = datetime.now()

            logger.info(f"开始处理研究任务: {task_id} ({task_type.value})")

            # 根据任务类型执行相应处理
            start_time = datetime.now()

            if task_type == ResearchTaskType.FACTOR_CALCULATION:
                result = await self._execute_factor_calculation(params)
            elif task_type == ResearchTaskType.FACTOR_ANALYSIS:
                result = await self._execute_factor_analysis(params)
            elif task_type == ResearchTaskType.FACTOR_OPTIMIZATION:
                result = await self._execute_factor_optimization(params)
            elif task_type == ResearchTaskType.FACTOR_BACKTEST:
                result = await self._execute_factor_backtest(params)
            elif task_type == ResearchTaskType.FACTOR_SELECTION:
                result = await self._execute_factor_selection(params)
            elif task_type == ResearchTaskType.FACTOR_VALIDATION:
                result = await self._execute_factor_validation(params)
            else:
                raise ValueError(f"未知的任务类型: {task_type}")

            # 计算处理时间
            processing_time = (datetime.now() - start_time).total_seconds()

            # 更新任务状态
            task_info["status"] = "completed"
            task_info["completed_at"] = datetime.now()
            task_info["result"] = result
            task_info["processing_time"] = processing_time

            # 更新性能统计
            self._performance_stats["tasks_completed"] += 1
            self._performance_stats["total_processing_time"] += processing_time

            # 添加到历史记录
            self._task_history.append(task_info.copy())
            if len(self._task_history) > self._max_history_size:
                self._task_history.pop(0)

            # 发布任务完成事件
            await self._publish_event("research_task_completed", {
                "task_id": task_id,
                "task_type": task_type.value,
                "result": result,
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"研究任务完成: {task_id} ({task_type.value}), 耗时: {processing_time:.2f}秒")

        except Exception as e:
            # 更新任务状态
            task_info["status"] = "error"
            task_info["error"] = str(e)
            task_info["completed_at"] = datetime.now()

            # 更新性能统计
            self._performance_stats["tasks_failed"] += 1

            # 发布任务失败事件
            await self._publish_event("research_task_failed", {
                "task_id": task_id,
                "task_type": task_type.value,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })

            logger.error(f"研究任务失败: {task_id} ({task_type.value}), 错误: {e}")

            # 记录错误
            await self.handle_error(e, EngineErrorLevel.ERROR, {
                "task_id": task_id,
                "task_type": task_type.value,
                "params": params
            })

    async def _execute_factor_calculation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行因子计算任务

        Args:
            params: 计算参数

        Returns:
            Dict[str, Any]: 计算结果
        """
        # 提取参数
        factor_name = params.get("factor_name")
        stock_codes = params.get("stock_codes", [])
        start_date = params.get("start_date")
        end_date = params.get("end_date")
        calculation_params = params.get("params", {})

        # 检查缓存
        cache_key = self._generate_cache_key(factor_name, stock_codes, start_date, end_date)
        if self.cache_manager:
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                self._performance_stats["cache_hits"] += 1
                logger.info(f"从缓存获取因子数据: {factor_name}")
                return {
                    "cached": True,
                    "factor_data": cached_result.get("factor_data"),
                    "metadata": cached_result.get("metadata")
                }

        self._performance_stats["cache_misses"] += 1

        # 执行因子计算
        if self.research_service:
            result = await self.research_service.calculate_factor(
                factor_name=factor_name,
                stock_codes=stock_codes,
                start_date=start_date,
                end_date=end_date,
                params=calculation_params
            )
        else:
            # 模拟计算（实际应用中应使用真正的服务）
            result = self._simulate_factor_calculation(
                factor_name, stock_codes, start_date, end_date, calculation_params
            )

        # 缓存结果
        if self.cache_manager and result:
            await self.cache_manager.set(
                cache_key,
                {
                    "factor_data": result.get("factor_data"),
                    "metadata": result.get("metadata")
                },
                ttl=self._cache_ttl
            )

        # 更新统计
        self._performance_stats["factors_calculated"] += 1

        return {
            "cached": False,
            "factor_data": result.get("factor_data") if result else None,
            "metadata": result.get("metadata") if result else None
        }

    async def _execute_factor_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行因子分析任务

        Args:
            params: 分析参数

        Returns:
            Dict[str, Any]: 分析结果
        """
        # 提取参数
        factor_names = params.get("factor_names", [])
        analysis_type = params.get("analysis_type", "performance")
        analysis_params = params.get("params", {})

        # 执行因子分析
        if self.research_service:
            result = await self.research_service.analyze_factors(
                factor_names=factor_names,
                analysis_type=analysis_type,
                params=analysis_params
            )
        else:
            # 模拟分析
            result = self._simulate_factor_analysis(factor_names, analysis_type, analysis_params)

        return result

    async def _execute_factor_optimization(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行因子优化任务

        Args:
            params: 优化参数

        Returns:
            Dict[str, Any]: 优化结果
        """
        # 提取参数
        factor_names = params.get("factor_names", [])
        optimization_method = params.get("method", "genetic")
        objective_function = params.get("objective", "sharpe_ratio")
        constraints = params.get("constraints", {})

        # 执行因子优化
        if self.research_service:
            result = await self.research_service.optimize_factors(
                factor_names=factor_names,
                method=optimization_method,
                objective=objective_function,
                constraints=constraints
            )
        else:
            # 模拟优化
            result = self._simulate_factor_optimization(
                factor_names, optimization_method, objective_function, constraints
            )

        return result

    async def _execute_factor_backtest(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行因子回测任务

        Args:
            params: 回测参数

        Returns:
            Dict[str, Any]: 回测结果
        """
        # 提取参数
        factor_name = params.get("factor_name")
        backtest_params = params.get("params", {})

        # 执行因子回测
        if self.research_service:
            result = await self.research_service.backtest_factor(
                factor_name=factor_name,
                params=backtest_params
            )
        else:
            # 模拟回测
            result = self._simulate_factor_backtest(factor_name, backtest_params)

        return result

    async def _execute_factor_selection(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行因子选择任务

        Args:
            params: 选择参数

        Returns:
            Dict[str, Any]: 选择结果
        """
        # 提取参数
        candidate_factors = params.get("candidate_factors", [])
        selection_method = params.get("method", "correlation")
        selection_criteria = params.get("criteria", {})

        # 执行因子选择
        if self.research_service:
            result = await self.research_service.select_factors(
                candidate_factors=candidate_factors,
                method=selection_method,
                criteria=selection_criteria
            )
        else:
            # 模拟选择
            result = self._simulate_factor_selection(
                candidate_factors, selection_method, selection_criteria
            )

        return result

    async def _execute_factor_validation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行因子验证任务

        Args:
            params: 验证参数

        Returns:
            Dict[str, Any]: 验证结果
        """
        # 提取参数
        factor_name = params.get("factor_name")
        validation_method = params.get("method", "statistical")
        validation_params = params.get("params", {})

        # 执行因子验证
        if self.research_service:
            result = await self.research_service.validate_factor(
                factor_name=factor_name,
                method=validation_method,
                params=validation_params
            )
        else:
            # 模拟验证
            result = self._simulate_factor_validation(factor_name, validation_method, validation_params)

        return result

    # ==================== 任务管理方法 ====================

    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            bool: 取消是否成功
        """
        if task_id not in self._active_tasks:
            logger.warning(f"任务不存在，无法取消: {task_id}")
            return False

        task_info = self._active_tasks[task_id]

        if task_info["status"] in ["completed", "error", "cancelled"]:
            logger.warning(f"任务状态为{task_info['status']}，无法取消: {task_id}")
            return False

        # 更新任务状态
        task_info["status"] = "cancelled"
        task_info["cancelled_at"] = datetime.now()

        # 发布任务取消事件
        await self._publish_event("research_task_cancelled", {
            "task_id": task_id,
            "task_type": task_info["task_type"].value,
            "timestamp": datetime.now().isoformat()
        })

        logger.info(f"研究任务已取消: {task_id}")

        return True

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            Optional[Dict[str, Any]]: 任务状态信息
        """
        if task_id in self._active_tasks:
            return self._active_tasks[task_id]

        # 在历史记录中查找
        for task in self._task_history:
            if task.get("task_id") == task_id:
                return task

        return None

    async def get_all_tasks(
        self,
        status_filter: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        获取所有任务

        Args:
            status_filter: 状态过滤条件
            limit: 返回数量限制

        Returns:
            List[Dict[str, Any]]: 任务列表
        """
        all_tasks = []

        # 添加活跃任务
        all_tasks.extend(self._active_tasks.values())

        # 添加历史任务
        all_tasks.extend(self._task_history)

        # 状态过滤
        if status_filter:
            all_tasks = [task for task in all_tasks if task.get("status") == status_filter]

        # 按创建时间排序（最新的在前）
        all_tasks.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)

        return all_tasks[:limit]

    async def _cleanup_task(self, task_id: str):
        """
        清理任务

        Args:
            task_id: 任务ID
        """
        if task_id in self._active_tasks:
            # 从活跃任务中移除
            task_info = self._active_tasks.pop(task_id)

            # 添加到历史记录
            self._task_history.append(task_info)
            if len(self._task_history) > self._max_history_size:
                self._task_history.pop(0)

            logger.debug(f"任务已清理: {task_id}")

    # ==================== 因子管理方法 ====================

    async def calculate_factor_on_demand(
        self,
        factor_name: str,
        stock_codes: List[str],
        start_date: str,
        end_date: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        按需计算因子（同步接口）

        Args:
            factor_name: 因子名称
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            params: 计算参数

        Returns:
            Dict[str, Any]: 因子计算结果
        """
        try:
            # 提交计算任务
            task_id = await self.submit_research_task(
                task_type=ResearchTaskType.FACTOR_CALCULATION,
                params={
                    "factor_name": factor_name,
                    "stock_codes": stock_codes,
                    "start_date": start_date,
                    "end_date": end_date,
                    "params": params or {}
                },
                priority=10  # 高优先级
            )

            # 等待任务完成（轮询）
            max_wait_time = 300  # 最大等待时间（秒）
            poll_interval = 0.5  # 轮询间隔（秒）

            start_time = datetime.now()
            while (datetime.now() - start_time).total_seconds() < max_wait_time:
                task_status = await self.get_task_status(task_id)

                if not task_status:
                    raise RuntimeError(f"任务不存在: {task_id}")

                status = task_status.get("status")

                if status == "completed":
                    return task_status.get("result", {})
                elif status == "error":
                    raise RuntimeError(f"因子计算失败: {task_status.get('error')}")
                elif status == "cancelled":
                    raise RuntimeError(f"因子计算被取消: {task_id}")

                await asyncio.sleep(poll_interval)

            raise TimeoutError(f"因子计算超时: {task_id}")

        except Exception as e:
            logger.error(f"按需计算因子失败: {e}")
            raise

    async def get_factor_definition(self, factor_name: str) -> Optional[Dict[str, Any]]:
        """
        获取因子定义

        Args:
            factor_name: 因子名称

        Returns:
            Optional[Dict[str, Any]]: 因子定义
        """
        if factor_name in self._default_factors:
            return self._default_factors[factor_name]

        # 尝试从缓存获取
        if self.cache_manager:
            cache_key = f"factor_definition:{factor_name}"
            definition = await self.cache_manager.get(cache_key)
            if definition:
                return definition

        return None

    async def register_factor_definition(
        self,
        factor_name: str,
        definition: Dict[str, Any]
    ) -> bool:
        """
        注册因子定义

        Args:
            factor_name: 因子名称
            definition: 因子定义

        Returns:
            bool: 注册是否成功
        """
        try:
            # 验证因子定义
            if not self._validate_factor_definition(definition):
                raise ValueError("无效的因子定义")

            # 保存到默认因子
            self._default_factors[factor_name] = definition

            # 保存到缓存
            if self.cache_manager:
                cache_key = f"factor_definition:{factor_name}"
                await self.cache_manager.set(cache_key, definition, ttl=86400)

            # 发布因子注册事件
            await self._publish_event("factor_definition_registered", {
                "factor_name": factor_name,
                "definition": definition,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"因子定义已注册: {factor_name}")
            return True

        except Exception as e:
            logger.error(f"注册因子定义失败: {factor_name}, 错误: {e}")
            return False

    # ==================== 内部辅助方法 ====================

    async def _load_default_factors(self):
        """加载默认因子配置"""
        try:
            logger.info("开始加载默认因子配置")

            # 默认因子定义
            default_factors = {
                "price_momentum": {
                    "name": "price_momentum",
                    "description": "价格动量因子",
                    "calculation_method": "technical",
                    "parameters": {"lookback_period": 20},
                    "category": "momentum",
                    "version": "1.0.0"
                },
                "volume_ratio": {
                    "name": "volume_ratio",
                    "description": "量比因子",
                    "calculation_method": "volume",
                    "parameters": {"window": 5},
                    "category": "volume",
                    "version": "1.0.0"
                },
                "volatility": {
                    "name": "volatility",
                    "description": "波动率因子",
                    "calculation_method": "statistical",
                    "parameters": {"window": 20, "annualized": True},
                    "category": "risk",
                    "version": "1.0.0"
                }
            }

            # 加载到内存
            self._default_factors = default_factors

            # 保存到缓存
            if self.cache_manager:
                for factor_name, definition in default_factors.items():
                    cache_key = f"factor_definition:{factor_name}"
                    await self.cache_manager.set(cache_key, definition, ttl=86400)

            logger.info(f"默认因子配置加载完成，共加载{len(default_factors)}个因子")

        except Exception as e:
            logger.warning(f"加载默认因子配置失败: {e}")

    async def _register_event_handlers(self):
        """注册事件处理器"""
        if not self.event_engine:
            logger.warning("事件引擎不可用，无法注册事件处理器")
            return

        try:
            # 注册研究任务请求处理器
            self.event_engine.register_handler(
                "research_task_request",
                self._handle_research_task_request
            )

            # 注册因子计算请求处理器
            self.event_engine.register_handler(
                "factor_calculation_request",
                self._handle_factor_calculation_request
            )

            # 注册因子分析请求处理器
            self.event_engine.register_handler(
                "factor_analysis_request",
                self._handle_factor_analysis_request
            )

            # 注册任务取消请求处理器
            self.event_engine.register_handler(
                "cancel_research_task",
                self._handle_cancel_task_request
            )

            # 注册状态请求处理器
            self.event_engine.register_handler(
                "get_research_status",
                self._handle_status_request
            )

            logger.info("研究引擎事件处理器注册完成")

        except Exception as e:
            logger.error(f"注册事件处理器失败: {e}")

    async def _start_task_workers(self):
        """启动任务工作线程"""
        # 停止现有工作线程
        await self._stop_task_workers()

        # 创建新的工作线程
        self._task_workers = []
        for i in range(self._max_workers):
            worker = asyncio.create_task(
                self._task_worker_loop(i),
                name=f"research_task_worker_{i}"
            )
            self._task_workers.append(worker)

        logger.info(f"启动了 {self._max_workers} 个任务工作线程")

    async def _stop_task_workers(self):
        """停止任务工作线程"""
        if not self._task_workers:
            return

        # 取消所有工作线程
        for worker in self._task_workers:
            if not worker.done():
                worker.cancel()

        # 等待工作线程停止
        try:
            await asyncio.gather(*self._task_workers, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        self._task_workers.clear()
        logger.info("任务工作线程已停止")

    async def _task_worker_loop(self, worker_id: int):
        """
        任务工作线程循环

        Args:
            worker_id: 工作线程ID
        """
        logger.info(f"任务工作线程启动: {worker_id}")

        try:
            while self.record.status == ComponentStatus.RUNNING:
                try:
                    # 等待暂停事件
                    await self.pause_event.wait()

                    # 检查关闭事件
                    if self.shutdown_event.is_set():
                        break

                    # 从队列获取任务
                    try:
                        priority, task_id = await asyncio.wait_for(
                            self._task_queue.get(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue

                    # 处理任务
                    await self._process_research_task(task_id)

                    # 标记任务完成
                    self._task_queue.task_done()

                except asyncio.CancelledError:
                    # 工作线程被取消，正常退出
                    break
                except Exception as e:
                    logger.error(f"任务工作线程异常: {worker_id}, 错误: {e}")
                    await asyncio.sleep(1.0)

        except Exception as e:
            logger.error(f"任务工作线程意外退出: {worker_id}, 错误: {e}")
        finally:
            logger.info(f"任务工作线程停止: {worker_id}")

    async def _cancel_active_tasks(self):
        """取消所有活跃任务"""
        cancelled_count = 0

        for task_id, task_info in list(self._active_tasks.items()):
            if task_info["status"] in ["pending", "running"]:
                task_info["status"] = "cancelled"
                task_info["cancelled_at"] = datetime.now()
                cancelled_count += 1

        if cancelled_count > 0:
            logger.info(f"已取消 {cancelled_count} 个活跃任务")

    async def _save_cache_data(self):
        """保存缓存数据"""
        try:
            if self._factor_cache and self.cache_manager:
                for cache_key, cache_data in self._factor_cache.items():
                    await self.cache_manager.set(cache_key, cache_data, ttl=self._cache_ttl)

                logger.info(f"因子缓存数据已保存，共{len(self._factor_cache)}条记录")
        except Exception as e:
            logger.error(f"保存缓存数据失败: {e}")

    async def _restore_cache_data(self):
        """恢复缓存数据"""
        # 此方法可根据需要实现缓存数据的恢复
        pass

    def _generate_cache_key(
        self,
        factor_name: str,
        stock_codes: List[str],
        start_date: str,
        end_date: str
    ) -> str:
        """
        生成缓存键

        Args:
            factor_name: 因子名称
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            str: 缓存键
        """
        sorted_codes = sorted(stock_codes)
        codes_hash = hash(tuple(sorted_codes)) % 10000

        return f"factor:{factor_name}:{start_date}:{end_date}:{codes_hash}"

    def _validate_factor_definition(self, definition: Dict[str, Any]) -> bool:
        """
        验证因子定义

        Args:
            definition: 因子定义

        Returns:
            bool: 验证是否通过
        """
        required_fields = ["name", "calculation_method", "parameters"]

        for field in required_fields:
            if field not in definition:
                logger.error(f"因子定义缺少必要字段: {field}")
                return False

        return True

    # ==================== 事件处理方法 ====================

    async def _handle_research_task_request(self, data: Dict[str, Any]):
        """
        处理研究任务请求事件

        Args:
            data: 事件数据
        """
        try:
            task_type_str = data.get("task_type")
            params = data.get("params", {})
            priority = data.get("priority", 1)

            # 转换任务类型
            try:
                task_type = ResearchTaskType(task_type_str)
            except ValueError:
                raise ValueError(f"无效的任务类型: {task_type_str}")

            # 提交任务
            task_id = await self.submit_research_task(task_type, params, priority)

            # 返回任务ID
            await self._publish_event("research_task_submitted", {
                "task_id": task_id,
                "task_type": task_type_str,
                "priority": priority,
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"处理研究任务请求失败: {e}")
            await self.handle_error(e, EngineErrorLevel.ERROR, {
                "event_type": "research_task_request",
                "event_data": data
            })

    async def _handle_factor_calculation_request(self, data: Dict[str, Any]):
        """
        处理因子计算请求事件

        Args:
            data: 事件数据
        """
        try:
            factor_name = data.get("factor_name")
            stock_codes = data.get("stock_codes", [])
            start_date = data.get("start_date")
            end_date = data.get("end_date")
            params = data.get("params", {})

            # 提交因子计算任务
            task_id = await self.submit_research_task(
                task_type=ResearchTaskType.FACTOR_CALCULATION,
                params={
                    "factor_name": factor_name,
                    "stock_codes": stock_codes,
                    "start_date": start_date,
                    "end_date": end_date,
                    "params": params
                },
                priority=5
            )

            logger.info(f"因子计算任务已提交: {task_id} ({factor_name})")

        except Exception as e:
            logger.error(f"处理因子计算请求失败: {e}")

    async def _handle_factor_analysis_request(self, data: Dict[str, Any]):
        """
        处理因子分析请求事件

        Args:
            data: 事件数据
        """
        try:
            factor_names = data.get("factor_names", [])
            analysis_type = data.get("analysis_type", "performance")
            params = data.get("params", {})

            # 提交因子分析任务
            task_id = await self.submit_research_task(
                task_type=ResearchTaskType.FACTOR_ANALYSIS,
                params={
                    "factor_names": factor_names,
                    "analysis_type": analysis_type,
                    "params": params
                },
                priority=3
            )

            logger.info(f"因子分析任务已提交: {task_id}")

        except Exception as e:
            logger.error(f"处理因子分析请求失败: {e}")

    async def _handle_cancel_task_request(self, data: Dict[str, Any]):
        """
        处理任务取消请求事件

        Args:
            data: 事件数据
        """
        try:
            task_id = data.get("task_id")

            if not task_id:
                raise ValueError("任务ID不能为空")

            # 取消任务
            success = await self.cancel_task(task_id)

            if success:
                logger.info(f"任务取消成功: {task_id}")
            else:
                logger.warning(f"任务取消失败: {task_id}")

        except Exception as e:
            logger.error(f"处理任务取消请求失败: {e}")

    async def _handle_status_request(self, data: Dict[str, Any]):
        """
        处理状态请求事件

        Args:
            data: 事件数据
        """
        try:
            request_type = data.get("type", "engine_status")

            if request_type == "engine_status":
                # 返回引擎状态
                status_info = self.get_status_info()

                await self._publish_event("research_engine_status", {
                    "engine_id": self.engine_id,
                    "engine_name": self.config.name,
                    "status": status_info,
                    "timestamp": datetime.now().isoformat()
                })

            elif request_type == "task_status":
                # 返回任务状态
                task_id = data.get("task_id")

                if task_id:
                    task_status = await self.get_task_status(task_id)

                    await self._publish_event("research_task_status", {
                        "task_id": task_id,
                        "status": task_status,
                        "timestamp": datetime.now().isoformat()
                    })
                else:
                    # 返回所有任务状态
                    tasks = await self.get_all_tasks(limit=50)

                    await self._publish_event("research_all_tasks_status", {
                        "total_tasks": len(tasks),
                        "tasks": tasks,
                        "timestamp": datetime.now().isoformat()
                    })

            elif request_type == "performance_stats":
                # 返回性能统计
                await self._publish_event("research_performance_stats", {
                    "engine_id": self.engine_id,
                    "engine_name": self.config.name,
                    "performance_stats": self._performance_stats,
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            logger.error(f"处理状态请求失败: {e}")

    # ==================== 模拟方法（用于演示和测试） ====================

    def _simulate_factor_calculation(
        self,
        factor_name: str,
        stock_codes: List[str],
        start_date: str,
        end_date: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模拟因子计算"""
        # 模拟计算逻辑
        import random

        factor_data = []
        for code in stock_codes:
            for i in range(10):  # 模拟10天的数据
                date = f"2024-01-{i+1:02d}"
                value = random.uniform(-2.0, 2.0)

                factor_data.append({
                    "date": date,
                    "stock_code": code,
                    "factor_name": factor_name,
                    "value": value
                })

        return {
            "factor_data": factor_data,
            "metadata": {
                "factor_name": factor_name,
                "stock_count": len(stock_codes),
                "data_points": len(factor_data),
                "date_range": f"{start_date} - {end_date}",
                "calculation_method": "simulated"
            }
        }

    def _simulate_factor_analysis(
        self,
        factor_names: List[str],
        analysis_type: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模拟因子分析"""
        import random

        analysis_results = {}
        for factor_name in factor_names:
            analysis_results[factor_name] = {
                "ic_mean": random.uniform(-0.1, 0.3),
                "ic_std": random.uniform(0.05, 0.15),
                "ic_ir": random.uniform(0.5, 2.0),
                "turnover": random.uniform(0.1, 0.5),
                "win_rate": random.uniform(0.4, 0.7),
                "sharpe_ratio": random.uniform(0.5, 1.5)
            }

        return {
            "analysis_type": analysis_type,
            "factor_count": len(factor_names),
            "analysis_results": analysis_results,
            "summary": {
                "best_factor": max(analysis_results.items(), key=lambda x: x[1]["ic_ir"])[0],
                "worst_factor": min(analysis_results.items(), key=lambda x: x[1]["ic_ir"])[0],
                "avg_ic_ir": sum(r["ic_ir"] for r in analysis_results.values()) / len(analysis_results)
            }
        }

    def _simulate_factor_optimization(
        self,
        factor_names: List[str],
        method: str,
        objective: str,
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模拟因子优化"""
        import random

        weights = {}
        total_weight = 0.0

        for factor_name in factor_names:
            weight = random.uniform(0.0, 1.0)
            weights[factor_name] = weight
            total_weight += weight

        # 归一化权重
        for factor_name in weights:
            weights[factor_name] /= total_weight

        return {
            "optimized_factors": factor_names,
            "weights": weights,
            "objective_value": random.uniform(0.5, 2.0),
            "iterations": random.randint(10, 100),
            "method": method,
            "objective": objective,
            "constraints": constraints
        }

    def _simulate_factor_backtest(
        self,
        factor_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模拟因子回测"""
        import random

        return {
            "factor_name": factor_name,
            "period": params.get("period", "2024-01-01 to 2024-01-31"),
            "performance": {
                "total_return": random.uniform(-0.1, 0.3),
                "annual_return": random.uniform(-0.2, 0.6),
                "sharpe_ratio": random.uniform(0.5, 2.0),
                "max_drawdown": random.uniform(-0.15, -0.05),
                "win_rate": random.uniform(0.4, 0.7)
            },
            "transaction_count": random.randint(10, 100),
            "turnover": random.uniform(0.1, 0.5)
        }

    def _simulate_factor_selection(
        self,
        candidate_factors: List[str],
        method: str,
        criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模拟因子选择"""
        import random

        # 模拟选择结果
        selected_count = min(len(candidate_factors), random.randint(1, 5))
        selected_factors = random.sample(candidate_factors, selected_count)

        return {
            "candidate_count": len(candidate_factors),
            "selected_count": selected_count,
            "selected_factors": selected_factors,
            "selection_method": method,
            "criteria": criteria,
            "selection_scores": {
                factor: random.uniform(0.5, 1.0) for factor in selected_factors
            }
        }

    def _simulate_factor_validation(
        self,
        factor_name: str,
        method: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """模拟因子验证"""
        import random

        return {
            "factor_name": factor_name,
            "validation_method": method,
            "scores": {
                "statistical_significance": random.uniform(0.6, 0.95),
                "economic_significance": random.uniform(0.5, 0.9),
                "robustness": random.uniform(0.7, 0.95),
                "stability": random.uniform(0.6, 0.9)
            },
            "overall_score": random.uniform(0.6, 0.9),
            "recommendation": random.choice(["strong_buy", "buy", "hold", "sell", "strong_sell"]),
            "confidence_level": random.uniform(0.7, 0.95)
        }

    # ==================== 公共接口方法 ====================

    def get_engine_stats(self) -> Dict[str, Any]:
        """
        获取引擎统计信息

        Returns:
            Dict[str, Any]: 引擎统计信息
        """
        return {
            "engine_id": self.engine_id,
            "engine_name": self.config.name,
            "engine_type": self.ENGINE_TYPE.value,
            "status": self.record.status.value,
            "health": self.record.health.value,
            "uptime": self.record.get_uptime(),
            "active_tasks": len(self._active_tasks),
            "task_history_size": len(self._task_history),
            "factor_cache_size": len(self._factor_cache),
            "default_factors": len(self._default_factors),
            "task_queue_size": self._task_queue.qsize(),
            "active_workers": len([w for w in self._task_workers if not w.done()]),
            "performance_stats": self._performance_stats,
            "config": self.config.to_dict()
        }

    async def clear_cache(self, cache_type: str = "all") -> Dict[str, Any]:
        """
        清理缓存

        Args:
            cache_type: 缓存类型（all, factor, task, definition）

        Returns:
            Dict[str, Any]: 清理结果
        """
        cleared_counts = {}

        try:
            if cache_type in ["all", "factor"]:
                # 清理因子缓存
                factor_count = len(self._factor_cache)
                self._factor_cache.clear()
                cleared_counts["factor_cache"] = factor_count

            if cache_type in ["all", "task"]:
                # 清理任务历史（保留最近100条）
                if len(self._task_history) > 100:
                    removed_count = len(self._task_history) - 100
                    self._task_history = self._task_history[-100:]
                    cleared_counts["task_history"] = removed_count

            if cache_type in ["all", "definition"]:
                # 清理默认因子定义（保留系统默认）
                user_defined = {
                    k: v for k, v in self._default_factors.items()
                    if k not in ["price_momentum", "volume_ratio", "volatility"]
                }
                cleared_counts["factor_definitions"] = len(user_defined)
                for key in user_defined:
                    del self._default_factors[key]

            # 发布缓存清理事件
            await self._publish_event("research_cache_cleared", {
                "engine_id": self.engine_id,
                "engine_name": self.config.name,
                "cache_type": cache_type,
                "cleared_counts": cleared_counts,
                "timestamp": datetime.now().isoformat()
            })

            logger.info(f"研究缓存已清理: {cache_type}, 清理结果: {cleared_counts}")

            return {
                "success": True,
                "cleared_counts": cleared_counts,
                "cache_type": cache_type
            }

        except Exception as e:
            logger.error(f"清理缓存失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "cache_type": cache_type
            }


# ==================== 引擎工厂注册 ====================

def register_research_engine(factory: EngineFactory):
    """
    注册因子研究引擎到引擎工厂

    Args:
        factory: 引擎工厂实例
    """
    # 创建引擎描述符
    descriptor = EngineDescriptor(
        engine_type=EngineType.RESEARCH,
        engine_class=FactorResearchEngine,
        name="factor_research_engine",
        description="因子研究引擎，负责因子计算、分析和优化",
        version="1.0.0",
        category=EngineCategory.RESEARCH,
        dependencies=[
            EngineType.EVENT,  # 依赖事件引擎
            EngineType.DATA    # 依赖数据引擎
        ],
        config_schema={
            "required": ["name"],
            "default": {
                "name": "factor_research_engine",
                "description": "因子研究引擎",
                "version": "1.0.0",
                "auto_start": True,
                "max_retries": 3,
                "retry_delay": 1.0,
                "backoff_factor": 2.0,
                "max_delay": 30.0,
                "health_check_interval": 30.0,
                "graceful_shutdown_timeout": 30.0,
                "max_workers": 5,
                "max_history_size": 1000,
                "cache_ttl": 3600
            }
        },
        tags=["research", "factor", "calculation", "analysis"]
    )

    # 注册引擎
    try:
        factory.register_engine(descriptor)
        logger.info("因子研究引擎已注册到引擎工厂")
    except ValueError as e:
        logger.warning(f"因子研究引擎注册失败: {e}")


# ==================== 便捷函数 ====================

async def create_research_engine(
    config: Optional[Dict[str, Any]] = None,
    instance_name: Optional[str] = None,
    lazy_init: bool = False
) -> FactorResearchEngine:
    """
    创建因子研究引擎（便捷函数）

    Args:
        config: 引擎配置
        instance_name: 实例名称
        lazy_init: 是否延迟初始化

    Returns:
        FactorResearchEngine: 创建的因子研究引擎实例
    """
    from quant_server.core.engines.utils.engine_factory import create_engine
    from quant_server.core.engines.types.enums import EngineType

    engine = await create_engine(
        engine_type=EngineType.RESEARCH,
        config=config,
        instance_name=instance_name,
        lazy_init=lazy_init
    )

    return engine


async def get_research_engine(
    instance_name: str = "factor_research_engine"
) -> Optional[FactorResearchEngine]:
    """
    获取因子研究引擎（便捷函数）

    Args:
        instance_name: 引擎实例名称

    Returns:
        Optional[FactorResearchEngine]: 因子研究引擎实例
    """
    from quant_server.core.engines.utils.engine_factory import get_engine
    from quant_server.core.engines.types.enums import EngineType

    engine = await get_engine(instance_name)

    if engine and isinstance(engine, FactorResearchEngine):
        return engine

    return None