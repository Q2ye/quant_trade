"""分析模块引擎"""

from typing import Dict, Any, Optional
from datetime import date
import logging

from quant_server.core.engines.base.engine_base import EngineBase
from quant_server.core.engines.system.event_engine import EventEngine
from quant_server.core.engines.types.entities import EngineConfigEntity
from quant_server.modules.analysis.services.attribution_service import AttributionService
from quant_server.modules.analysis.services.integration_service import AnalysisIntegrationService
from quant_server.modules.analysis.handlers.event_handler import AnalysisEventHandler

logger = logging.getLogger(__name__)


class AnalysisEngine(EngineBase):
    """分析模块引擎"""

    def __init__(
        self,
        event_engine: EventEngine,
        db_session_factory,
        config: Optional[EngineConfigEntity] = None,
    ):
        """初始化分析引擎

        Args:
            event_engine: 事件引擎实例
            db_session_factory: 数据库会话工厂（callable）
            config: 引擎配置实体（可选，自动生成默认配置）
        """
        if config is None:
            config = EngineConfigEntity(
                name="analysis",
                engine_type="analysis",
                dependencies=[],
            )
        super().__init__(config=config, event_engine=event_engine)
        self.db_session_factory = db_session_factory

    async def _on_initialize(self):
        """初始化分析引擎组件"""
        session = self.db_session_factory()
        try:
            self.attribution_service = AttributionService(session)
            self.integration_service = AnalysisIntegrationService(
                event_engine=self.event_engine,
                attribution_service=self.attribution_service
            )
            self.event_handler = AnalysisEventHandler(self.event_engine)
            self._subscribe_events()
        finally:
            await self._safe_close_session(session)

    async def _on_start(self):
        """启动引擎"""
        logger.info("分析引擎启动成功")

    async def _on_stop(self):
        """停止引擎"""
        logger.info("分析引擎停止成功")

    def _subscribe_events(self):
        """订阅外部模块事件"""
        try:
            self.event_engine.register(
                "strategy.executed", self.handle_strategy_executed
            )
        except ImportError:
            logger.warning("策略模块事件未找到，跳过订阅")

        try:
            self.event_engine.register(
                "backtest.task.completed", self.handle_backtest_completed
            )
        except ImportError:
            logger.warning("回测模块事件未找到，跳过订阅")

        try:
            self.event_engine.register(
                "trade.order.completed", self.handle_trade_completed
            )
        except ImportError:
            logger.warning("交易模块事件未找到，跳过订阅")

    async def handle_strategy_executed(self, event):
        """处理策略执行事件"""
        try:
            strategy_id = event.data.get("strategy_id")
            execution_result = event.data.get("result", {})

            if strategy_id:
                await self.integration_service.handle_strategy_executed(
                    strategy_id=strategy_id,
                    execution_result=execution_result
                )
        except Exception as e:
            logger.error(f"处理策略执行事件失败: {str(e)}")

    async def handle_backtest_completed(self, event):
        """处理回测完成事件"""
        try:
            strategy_id = event.data.get("strategy_id")
            backtest_result = event.data.get("result", {})

            if strategy_id:
                await self.integration_service.handle_backtest_completed(
                    strategy_id=strategy_id,
                    backtest_result=backtest_result
                )
        except Exception as e:
            logger.error(f"处理回测完成事件失败: {str(e)}")

    async def handle_trade_completed(self, event):
        """处理交易完成事件"""
        try:
            trade_data = event.data
            await self.integration_service.handle_trade_completed(trade_data)
        except Exception as e:
            logger.error(f"处理交易完成事件失败: {str(e)}")

    async def analyze_strategy(
        self,
        strategy_id: str,
        start_date: date,
        end_date: date,
        analysis_type: str = "performance"
    ) -> Dict[str, Any]:
        """分析策略

        Args:
            strategy_id: 策略ID
            start_date: 开始日期
            end_date: 结束日期
            analysis_type: 分析类型 (performance, risk, attribution)

        Returns:
            分析结果
        """
        session = self.db_session_factory()
        try:
            if analysis_type == "performance":
                return await self.integration_service.analyze_strategy_performance(
                    strategy_id=strategy_id,
                    start_date=start_date,
                    end_date=end_date,
                    session=session
                )
            elif analysis_type == "risk":
                return await self.integration_service.analyze_strategy_risk(
                    strategy_id=strategy_id,
                    start_date=start_date,
                    end_date=end_date,
                    session=session
                )
            elif analysis_type == "attribution":
                return await self.integration_service.analyze_portfolio_attribution(
                    portfolio_id=strategy_id,
                    start_date=start_date,
                    end_date=end_date,
                    attribution_model="Fama-French",
                    session=session
                )
            else:
                raise ValueError(f"不支持的分析类型: {analysis_type}")
        finally:
            await self._safe_close_session(session)

    async def analyze_portfolio(
        self,
        portfolio_id: str,
        start_date: date,
        end_date: date,
        analysis_type: str = "attribution"
    ) -> Dict[str, Any]:
        """分析投资组合

        Args:
            portfolio_id: 投资组合ID
            start_date: 开始日期
            end_date: 结束日期
            analysis_type: 分析类型

        Returns:
            分析结果
        """
        session = self.db_session_factory()
        try:
            if analysis_type == "attribution":
                return await self.integration_service.analyze_portfolio_attribution(
                    portfolio_id=portfolio_id,
                    start_date=start_date,
                    end_date=end_date,
                    attribution_model="Fama-French",
                    session=session
                )
            else:
                raise ValueError(f"不支持的分析类型: {analysis_type}")
        finally:
            await self._safe_close_session(session)

    def get_status(self) -> Dict[str, Any]:
        """获取引擎状态

        Returns:
            引擎状态
        """
        status = super().get_status_info()
        status.update({
            "components": {
                "attribution_service": "initialized",
                "integration_service": "initialized",
                "event_handler": "initialized"
            }
        })
        return status

    @staticmethod
    async def _safe_close_session(session):
        """安全关闭数据库会话"""
        try:
            if hasattr(session, "close") and callable(session.close):
                result = session.close()
                if hasattr(result, "__await__"):
                    await result  # type: ignore
        except (RuntimeError, AttributeError):
            pass