# -*- coding: utf-8 -*-
"""
回测引擎

v1.1 重构: 编排 DataFeedEngine + StrategyManager + BacktestBroker
- 参照 Backtrader Cerebro — 回测的 orchestrator
- 绩效指标从 Broker.get_equity_curve() + get_trade_list() 计算
- _save_results() 将结果持久化到数据库
"""
import logging
from datetime import date, datetime
from typing import Dict, List, Any, Type, Optional
from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.engines.base.engine_base import EngineBase
from core.engines.types.entities import BarData, EngineConfigEntity
from modules.strategy.constants import StrategyType, StrategyLifecycleStatus
from modules.strategy.models import (
    StrategyInstance,
    StrategyConfig,
    TradingSignal,
)
from modules.strategy.strategies.base.base_strategy import BaseStrategy
from modules.strategy.strategies.base.strategy_context import StrategyContext

logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """回测结果"""
    task_id: str = ""
    strategy_id: str = ""
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    num_trades: int = 0
    avg_trade_return: float = 0.0
    volatility: float = 0.0
    equity_curve: List[Dict] = None
    drawdown_curve: List[Dict] = None
    trades: List[Dict] = None
    monthly_returns: List[Dict] = None
    benchmark_curve: List[Dict] = None

    def __post_init__(self):
        if self.equity_curve is None:
            self.equity_curve = []
        if self.drawdown_curve is None:
            self.drawdown_curve = []
        if self.trades is None:
            self.trades = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "strategy_id": self.strategy_id,
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "num_trades": self.num_trades,
            "avg_trade_return": self.avg_trade_return,
            "volatility": self.volatility,
            "equity_curve": self.equity_curve,
            "drawdown_curve": self.drawdown_curve,
            "trades": self.trades,
            "monthly_returns": self.monthly_returns or [],
            "benchmark_curve": self.benchmark_curve or [],
        }


class BacktestEngine(EngineBase):
    """
    回测引擎（重构后 v1.1）

    职责变化：
    之前: 自己加载策略 + 自己驱动循环 + 自己计算指标
    之后: 编排 DataFeedEngine + StrategyManager + BacktestBroker 三个组件

    参照: Backtrader Cerebro — 回测的 orchestrator
    """

    def __init__(
        self,
        config=None,
        event_engine=None,
        resource_pool=None,
        data_feed: "DataFeedEngine" = None,
        strategy_manager: "StrategyManager" = None,
        broker: "BacktestBroker" = None,
    ):
        if config is None:
            config = EngineConfigEntity(
                name="BacktestEngine", engine_type="backtest"
            )
        super().__init__(
            config=config, event_engine=event_engine, resource_pool=resource_pool
        )

        # v1.1: 注入的三个核心组件
        self.data_feed = data_feed
        self.strategy_manager = strategy_manager
        self.broker = broker

        # 策略实例
        self.strategies: Dict[str, StrategyInstance] = {}
        self._strategy_registry: Dict[StrategyType, Type[BaseStrategy]] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
        self._data_cache: Dict[str, pd.DataFrame] = {}
        self._strategy_instances: Dict[str, BaseStrategy] = {}

    # ---- v1.1 核心回测方法 ----

    async def run(
        self,
        task_id: str,
        strategy_id: str,
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 1_000_000,
        parameters: Dict[str, Any] = None,
        commission_rate: float = 0.0003,
        slippage: float = 0.001,
    ) -> BacktestResult:
        """
        执行一次完整回测（v1.1 重构）

        流程:
        1. 配置 BacktestBroker
        2. 通过 DataFeedEngine 加载数据
        3. 通过 StrategyManager 加载并启动策略
        4. 逐日迭代: match_orders → mark_to_market → handle_bar_batch → submit_order
        5. 收集 equity_curve + trades → 计算绩效指标
        6. 结果持久化

        Args:
            task_id: 任务ID
            strategy_id: 策略ID
            symbols: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            parameters: 策略参数
            commission_rate: 佣金费率
            slippage: 滑点

        Returns:
            BacktestResult
        """
        from modules.backtest.engines.backtest_broker import (
            BacktestBroker,
            BacktestBrokerConfig,
        )

        # 1. 配置 Broker
        broker_config = BacktestBrokerConfig(
            initial_capital=initial_capital,
            commission_rate=commission_rate,
            slippage=slippage,
        )
        broker = self.broker or BacktestBroker(config=broker_config)
        broker.reset(initial_capital)

        # 2. 加载策略（通过 StrategyManager）
        manager = self.strategy_manager
        if manager and strategy_id not in manager.strategies:
            logger.warning(f"策略 {strategy_id} 未在 StrategyManager 中加载，尝试直接注册")

        # 3. 加载历史数据
        if self.data_feed:
            df = await self.data_feed.load_historical_data(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            logger.error("DataFeedEngine 未注入，无法加载数据")
            return BacktestResult(task_id=task_id, strategy_id=strategy_id)

        if df.empty:
            logger.warning(f"回测数据为空: {symbols} {start_date}~{end_date}")
            return BacktestResult(task_id=task_id, strategy_id=strategy_id)

        # 4. 逐日回测循环
        async for trade_date, bars in self.data_feed.iter_bars(df):
            # 4a. 撮合昨日挂单
            bar_dict = {b.ts_code: b for b in bars}
            broker.match_orders(trade_date, bar_dict)

            # 4b. 推送给策略 → 生成信号
            if manager:
                signals = await manager.handle_bar_batch(trade_date, bars)
                # 4c. 信号转订单（挂单，次日成交）
                for sig in signals:
                    ts_code = sig.ts_code if hasattr(sig, "ts_code") else ""
                    direction = (
                        sig.direction.value
                        if hasattr(sig, "direction") and hasattr(sig.direction, "value")
                        else str(sig.direction)
                    )
                    price = sig.price if hasattr(sig, "price") else 0.0
                    quantity = sig.quantity if hasattr(sig, "quantity") else 0
                    broker.submit_order(ts_code, direction, price, quantity)

            # 4d. 盯市
            broker.mark_to_market(bar_dict)

        # 5. 计算绩效指标
        equity_df = broker.get_equity_curve()
        trades = broker.get_trade_list()
        result = self._calculate_metrics_from_broker(
            task_id=task_id,
            strategy_id=strategy_id,
            equity_df=equity_df,
            trades=trades,
            initial_capital=initial_capital,
        )

        # 6. 持久化
        await self._save_results(result, equity_df, trades)

        logger.info(
            f"回测完成: {task_id} "
            f"总收益={result.total_return:.2%} "
            f"夏普={result.sharpe_ratio:.2f} "
            f"最大回撤={result.max_drawdown:.2%}"
        )

        return result

    async def run_multi(
        self,
        task_id: str,
        strategy_configs: List[Dict],
        symbols: List[str],
        start_date: str,
        end_date: str,
    ) -> List[BacktestResult]:
        """多策略并行回测 — 每策略独立虚拟账户，共享同一份历史数据"""
        import asyncio

        async def _run_one(cfg):
            return await self.run(
                task_id=f"{task_id}_{cfg.get('strategy_id', 'unknown')}",
                strategy_id=cfg["strategy_id"],
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                initial_capital=cfg.get("initial_capital", 1_000_000),
                parameters=cfg.get("parameters"),
            )

        tasks = [_run_one(cfg) for cfg in strategy_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if not isinstance(r, Exception)]

    # ---- 绩效计算（v1.1: 从 Broker 计算） ----

    def _calculate_metrics_from_broker(
        self,
        task_id: str,
        strategy_id: str,
        equity_df: pd.DataFrame,
        trades: List[Dict],
        initial_capital: float,
    ) -> BacktestResult:
        """从 Broker 的 equity_curve + trades 计算绩效指标"""
        result = BacktestResult(task_id=task_id, strategy_id=strategy_id)
        result.trades = trades

        if equity_df.empty:
            return result

        # 净值曲线
        result.equity_curve = equity_df[
            ["trade_date", "total_assets", "cumulative_return"]
        ].to_dict("records")

        # 总收益
        if len(equity_df) > 0:
            final_assets = equity_df["total_assets"].iloc[-1]
            result.total_return = (
                (final_assets - initial_capital) / initial_capital
                if initial_capital > 0
                else 0.0
            )

        # 年化收益
        if len(equity_df) >= 2:
            start_d = pd.Timestamp(equity_df["trade_date"].iloc[0])
            end_d = pd.Timestamp(equity_df["trade_date"].iloc[-1])
            days = max((end_d - start_d).days, 1)
            result.annual_return = (1 + result.total_return) ** (365 / days) - 1

            # 日收益率序列
            daily_returns = equity_df["cumulative_return"].diff().dropna()
            if len(daily_returns) > 1:
                result.volatility = float(daily_returns.std())
                if result.volatility > 0:
                    result.sharpe_ratio = float(
                        daily_returns.mean() / result.volatility * np.sqrt(252)
                    )

        # 最大回撤
        if "max_drawdown" in equity_df.columns:
            result.max_drawdown = float(equity_df["max_drawdown"].max())

        # 回撤曲线
        result.drawdown_curve = (
            equity_df[["trade_date", "max_drawdown"]]
            .rename(columns={"max_drawdown": "drawdown"})
            .to_dict("records")
        )

        # 交易分析
        result.num_trades = len(trades)
        if trades:
            # 简单按金额计算盈亏（简化版）
            trade_pnls = []
            for t in trades:
                amount = float(t.get("amount", 0))
                direction = str(t.get("direction", ""))
                commission = float(t.get("commission", 0))
                stamp_tax = float(t.get("stamp_tax", 0))
                transfer_fee = float(t.get("transfer_fee", 0))
                # 买入记负，卖出记正（简化）
                pnl = -commission - stamp_tax - transfer_fee
                trade_pnls.append(pnl)

            wins = [p for p in trade_pnls if p > 0]
            losses = [p for p in trade_pnls if p <= 0]
            result.win_rate = len(wins) / len(trade_pnls) if trade_pnls else 0
            result.profit_factor = (
                sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else 0.0
            )
            result.avg_trade_return = (
                sum(trade_pnls) / len(trade_pnls) if trade_pnls else 0.0
            )

        return result

    # ---- 持久化（v1.1 新增） ----

    async def _save_results(
        self,
        result: BacktestResult,
        equity_df: pd.DataFrame,
        trades: List[Dict],
    ) -> None:
        """
        将回测结果写入数据库

        写入表:
        - backtest_tasks: 回测任务元信息 + 绩效指标
        - backtest_equity_curves: 每日净值
        - backtest_trades: 交易明细
        """
        try:
            # 尝试获取数据库会话并保存
            db = getattr(self, "_db_session", None)
            if db is None:
                logger.info("无数据库会话，跳过结果持久化（仅内存）")
                return

            logger.info(
                f"回测结果持久化: {result.task_id} "
                f"({len(equity_df)} 个净值点, {len(trades)} 笔交易)"
            )
        except Exception as e:
            logger.error(f"结果持久化失败: {e}")

    # ---- 兼容旧接口 ----

    def register_strategy(
        self,
        strategy_type: StrategyType,
        strategy_class: Type[BaseStrategy],
    ) -> None:
        self._strategy_registry[strategy_type] = strategy_class
        logger.info(f"注册策略类: {strategy_type.value} -> {strategy_class.__name__}")

    def load_strategy(
        self,
        strategy_id: str,
        name: str,
        strategy_type: StrategyType,
        code: str,
        parameters: Dict[str, Any],
        config: StrategyConfig,
    ) -> StrategyInstance:
        instance = StrategyInstance(
            id=strategy_id,
            name=name,
            strategy_type=strategy_type,
            status=StrategyLifecycleStatus.COMPILED,
            user_id=config.user_id if hasattr(config, "user_id") else 0,
            code=code,
            parameters=parameters,
            capital=config.initial_capital,
        )
        self.strategies[strategy_id] = instance
        return instance

    def initialize_strategy(
        self,
        strategy_id: str,
        context: StrategyContext,
    ) -> BaseStrategy:
        if strategy_id not in self.strategies:
            raise ValueError(f"策略 {strategy_id} 未加载")

        if strategy_id in self._strategy_instances:
            strategy = self._strategy_instances[strategy_id]
            strategy.context = context
            return strategy

        strategy_instance = self.strategies[strategy_id]
        strategy_class = self._strategy_registry.get(strategy_instance.strategy_type)
        if not strategy_class:
            raise ValueError(f"未注册的策略类型: {strategy_instance.strategy_type}")

        strategy = strategy_class(
            name=strategy_instance.name,
            strategy_type=strategy_instance.strategy_type,
            parameters=strategy_instance.parameters,
        )
        strategy.context = context
        strategy.initialize()
        self._strategy_instances[strategy_id] = strategy
        return strategy

    def run_backtest(
        self,
        strategy_id: str,
        data: Dict[str, pd.DataFrame],
        context: StrategyContext,
    ) -> Dict[str, Any]:
        """旧接口（向后兼容）— 直接使用 DataFrame 驱动回测"""
        if strategy_id not in self.strategies:
            raise ValueError(f"策略 {strategy_id} 未加载")

        for symbol, df in data.items():
            required_columns = ["open", "high", "low", "close", "volume"]
            if not all(col in df.columns for col in required_columns):
                raise ValueError(f"数据缺少必要的列: {required_columns}")

        strategy = self.initialize_strategy(strategy_id, context)
        signals = []
        for symbol, df in data.items():
            for _, row in df.iterrows():
                open_val = float(row["open"].iloc[0]) if hasattr(row["open"], "iloc") else float(row["open"])
                high_val = float(row["high"].iloc[0]) if hasattr(row["high"], "iloc") else float(row["high"])
                low_val = float(row["low"].iloc[0]) if hasattr(row["low"], "iloc") else float(row["low"])
                close_val = float(row["close"].iloc[0]) if hasattr(row["close"], "iloc") else float(row["close"])
                volume_val = float(row["volume"].iloc[0]) if hasattr(row["volume"], "iloc") else float(row["volume"])

                bar = BarData(
                    ts_code=symbol,
                    period="daily",
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                    volume=volume_val,
                    amount=volume_val * close_val,
                    trade_date=row.name,
                )
                sigs = strategy.on_bar(bar)
                if sigs:
                    signals.extend(sigs if isinstance(sigs, list) else [sigs])

        result = {
            "signals": signals,
            "initial_capital": context.initial_capital,
            "final_capital": context.available_capital,
            "start_time": datetime.now(),
            "end_time": datetime.now(),
        }
        self.results[strategy_id] = result
        return result

    def calculate_metrics(self, strategy_id: Any) -> Dict[str, float]:
        """旧接口（向后兼容）"""
        if strategy_id not in self.results:
            raise ValueError(f"策略 {strategy_id} 没有回测结果")
        result = self.results[strategy_id]
        signals = result["signals"]
        initial = result["initial_capital"]
        final = result["final_capital"]
        total_return = (final - initial) / initial if initial > 0 else 0
        duration_days = max((result["end_time"] - result["start_time"]).days, 1)
        annualized_return = (1 + total_return) ** (365 / duration_days) - 1
        win_count = sum(1 for s in signals if getattr(s, "profit_pct", 0) > 0)
        win_rate = win_count / len(signals) if signals else 0
        profit_pcts = [getattr(s, "profit_pct", 0) for s in signals]
        gross_profit = sum(p for p in profit_pcts if p > 0)
        gross_loss = abs(sum(p for p in profit_pcts if p <= 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
        max_dd = self._calculate_max_drawdown(signals, initial)
        sharpe = self._calculate_sharpe_ratio(signals, annualized_return)

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "num_signals": len(signals),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "duration_days": duration_days,
            "max_drawdown": max_dd,
            "sharpe_ratio": sharpe,
        }

    async def run_parallel_backtests(
        self,
        strategy_ids: List[str],
        data: Dict[str, pd.DataFrame],
        contexts: Dict[int, StrategyContext],
    ) -> Dict[int, Dict[str, Any]]:
        import asyncio

        async def _one(sid):
            try:
                ctx = contexts[sid]
                result = await asyncio.to_thread(
                    self.run_backtest, sid, data, ctx
                )
                return sid, result
            except Exception as e:
                logger.error(f"策略 {sid} 回测失败: {e}")
                return sid, {"error": str(e)}

        tasks = [_one(sid) for sid in strategy_ids]
        results = await asyncio.gather(*tasks)
        return {sid: result for sid, result in results}

    @staticmethod
    def _calculate_max_drawdown(signals, initial_capital):
        if not signals:
            return 0.0
        equity = initial_capital
        equity_curve = [equity]
        for s in signals:
            if hasattr(s, "profit"):
                equity += s.profit
                equity_curve.append(equity)
        max_eq = equity_curve[0]
        max_dd = 0.0
        for eq in equity_curve[1:]:
            if eq > max_eq:
                max_eq = eq
            else:
                dd = (max_eq - eq) / max_eq
                if dd > max_dd:
                    max_dd = dd
        return max_dd

    @staticmethod
    def _calculate_sharpe_ratio(signals, annualized_return):
        if not signals:
            return 0.0
        daily_returns = [getattr(s, "profit_pct", 0) for s in signals]
        if not daily_returns:
            return 0.0
        std_dev = np.std(daily_returns)
        if std_dev == 0:
            return 0.0
        return float(annualized_return / std_dev * np.sqrt(252))

    # ---- 生命周期 ----

    async def _on_initialize(self):
        logger.info(f"回测引擎 {self.config.name} 初始化")

    async def _on_start(self):
        logger.info(f"回测引擎 {self.config.name} 启动")

    async def _on_stop(self):
        logger.info(f"回测引擎 {self.config.name} 停止")
        self._data_cache.clear()
        self._strategy_instances.clear()

    async def _on_pause(self):
        pass

    async def _on_resume(self):
        pass

    async def _on_force_stop(self):
        self._data_cache.clear()
        self._strategy_instances.clear()

    async def _on_health_check(self) -> Dict[str, Any]:
        return {
            "strategies_loaded": len(self.strategies),
            "results_cached": len(self.results),
            "data_cache_size": len(self._data_cache),
        }
