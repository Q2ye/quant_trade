from collections import defaultdict
import logging

# 引入统一通知工具
from ..utils.notification import send_signal_notification

logger = logging.getLogger('signal_manager')


def _send_notification(signal: dict):
    """使用统一通知工具发送通知"""
    try:
        send_signal_notification(signal)
    except Exception as e:
        logger.error(f"发送信号通知失败: {str(e)}")


class SignalManager:
    def __init__(self, main_engine):
        self.main_engine = main_engine
        self.signal_history = defaultdict(list)  # 信号历史记录

        # 注册事件处理
        main_engine.event_engine.register('signal', self.process_signal)

        logger.info("信号管理器已初始化")

    def process_signal(self, event):
        """处理信号事件"""
        signal = event.data
        self._store_signal(signal)
        _send_notification(signal)

    def _store_signal(self, signal: dict):
        """存储信号到历史记录"""
        symbol = signal['symbol']
        self.signal_history[symbol].append(signal)

        # 保留最近50条记录
        if len(self.signal_history[symbol]) > 50:
            self.signal_history[symbol] = self.signal_history[symbol][-50:]

    def get_signals(self, symbol: str = None, strategy: str = None, limit: int = 20) -> list:
        """获取历史信号"""
        if symbol:
            return self.signal_history.get(symbol, [])[-limit:]

        all_signals = []
        for signals in self.signal_history.values():
            if strategy:
                all_signals.extend([s for s in signals if s['strategy'] == strategy])
            else:
                all_signals.extend(signals)

        # 按时间排序
        all_signals.sort(key=lambda x: x['signal_time'], reverse=True)
        return all_signals[:limit]