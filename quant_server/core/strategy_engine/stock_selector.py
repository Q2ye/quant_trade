from datetime import datetime
from typing import Dict, List
from .event_engine import Event
from ..strategies.base_strategy import BaseStrategy
import time
import logging

logger = logging.getLogger(__name__)


def _is_after_market_close() -> bool:
    """检查当前时间是否在A股收盘后（15:00后）"""
    now = datetime.now()
    # 工作日检查
    if now.weekday() >= 5:  # 周六日
        return False

    # 时间检查 (15:00 - 23:59)
    return now.hour >= 15


class StockSelector:
    def __init__(self, main_engine,data_source_manager):
        self.main_engine = main_engine
        self.strategies: Dict[str, BaseStrategy] = {}
        self.data_source_manager = data_source_manager
        self.stock_pool = []  # 股票池
        self.last_run_time = None

    def get_strategies(self) -> List[BaseStrategy]:
        """获取选股器中的所有策略实例列表"""
        return list(self.strategies.values())

    def add_strategy(self, strategy: BaseStrategy):
        """添加策略实例"""
        if strategy.name in self.strategies:
            logger.warning(f"策略 {strategy.name} 已存在，将被替换")
        self.strategies[strategy.name] = strategy
        logger.info(f"策略 {strategy.name} 已添加")

    def remove_strategy(self, strategy_name: str):
        """移除策略"""
        if strategy_name in self.strategies:
            del self.strategies[strategy_name]
            logger.info(f"策略 {strategy_name} 已移除")
        else:
            logger.warning(f"尝试移除不存在的策略: {strategy_name}")

    def update_stock_pool(self):
        """更新股票池"""
        # 获取全市场A股（排除ST/*ST）
        all_stocks = self.data_source_manager.get_ashare_list()

        # 获取沪深300成分股
        hs300 = self.data_source_manager.get_index_constituents('000300.SH')

        # 合并股票池
        self.stock_pool = list(set(all_stocks.index.tolist() + hs300))
        logger.info(f"股票池已更新，共 {len(self.stock_pool)} 只股票")

    def run_selection(self, force=False):
        """运行所有选股策略"""
        # 检查是否在交易时间后运行
        now = datetime.now()
        if not force:
            if self.last_run_time and (now - self.last_run_time).hours < 23:
                logger.info("距离上次运行不足23小时，跳过本次执行")
                return []

            if not _is_after_market_close():
                logger.info("当前时间不在收盘后，跳过本次执行")
                return []

        # 更新股票池
        self.update_stock_pool()

        all_signals = []
        for name, strategy in self.strategies.items():
            try:
                logger.info(f"开始执行策略: {name}")
                start_time = time.time()

                # 预加载数据
                strategy.preload_data(self.stock_pool)

                # 生成信号
                signals = strategy.generate_signals()

                # 处理信号
                for signal in signals:
                    signal['strategy'] = name
                    signal['signal_time'] = now
                    self.main_engine.put_event(Event('signal', signal))

                # 保存信号
                self.save_signals(signals)

                duration = time.time() - start_time
                logger.info(f"策略 {name} 执行完成，生成 {len(signals)} 个信号，耗时 {duration:.2f} 秒")
                all_signals.extend(signals)
            except Exception as e:
                logger.error(f"策略 {name} 执行失败: {str(e)}", exc_info=True)

        self.last_run_time = now
        return all_signals

    def save_signals(self, signals: List[dict]):
        """保存信号到数据库"""
        if not signals:
            return

        try:
            db = self.main_engine.db
            for signal in signals:
                # 生成唯一ID: 日期+策略名+股票代码
                signal_id = f"{datetime.now().strftime('%Y%m%d')}_{signal['strategy']}_{signal['symbol']}"
                signal_data = {
                    'id': signal_id,
                    'strategy': signal['strategy'],
                    'symbol': signal['symbol'],
                    'signal_type': signal['signal_type'],
                    'signal_time': signal['signal_time'],
                    'reason': signal.get('reason', ''),
                    'score': signal.get('score', 0.0)
                }
                db.save_signal(signal_data)
            logger.info(f"已保存 {len(signals)} 个信号到数据库")
        except Exception as e:
            logger.error(f"保存信号失败: {str(e)}", exc_info=True)

