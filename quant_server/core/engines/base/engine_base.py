# core/engines/base/engine_base.py - 引擎基类
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

class EngineStatus(Enum):
    """引擎状态枚举"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

@dataclass
class EngineConfig:
    """引擎配置"""
    name: str
    auto_start: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    config: Dict[str, Any] = field(default_factory=dict)

class EngineBase(ABC):
    """引擎基类 - 统一生命周期管理"""

    def __init__(self, config: EngineConfig):
        self.config = config
        self.status = EngineStatus.STOPPED
        self.start_time: Optional[datetime] = None
        self.error: Optional[str] = None
        self._dependencies: List[str] = []

    async def start(self):
        """启动引擎"""
        try:
            self.status = EngineStatus.STARTING
            self.start_time = datetime.now()

            # 检查依赖
            await self._check_dependencies()

            # 执行启动逻辑
            await self._on_start()

            self.status = EngineStatus.RUNNING
            self.error = None

            # 发送引擎启动事件
            await self._publish_event("engine_started", {
                "engine_name": self.config.name,
                "start_time": self.start_time
            })

        except Exception as e:
            self.status = EngineStatus.ERROR
            self.error = str(e)
            raise

    async def stop(self):
        """停止引擎"""
        try:
            self.status = EngineStatus.STOPPING

            # 执行停止逻辑
            await self._on_stop()

            self.status = EngineStatus.STOPPED

            # 发送引擎停止事件
            await self._publish_event("engine_stopped", {
                "engine_name": self.config.name,
                "run_duration": (datetime.now() - self.start_time).total_seconds()
            })

        except Exception as e:
            self.status = EngineStatus.ERROR
            self.error = str(e)
            raise

    @abstractmethod
    async def _on_start(self):
        """引擎启动时的具体逻辑"""

    @abstractmethod
    async def _on_stop(self):
        """引擎停止时的具体逻辑"""

    async def _check_dependencies(self):
        """检查引擎依赖"""
        pass

    async def _publish_event(self, event_type: str, data: Dict):
        """发布事件"""
        # 通过事件引擎发布事件
        pass

    def get_status_info(self) -> Dict:
        """获取引擎状态信息"""
        return {
            "name": self.config.name,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "error": self.error,
            "dependencies": self._dependencies
        }