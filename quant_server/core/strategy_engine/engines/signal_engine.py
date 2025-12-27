# core/engines/signal_engine.py
import logging
from decimal import Decimal
from typing import Dict, Optional
from datetime import datetime

from quant_server.modules.data_models import SignalData, Direction
from quant_server.core.strategy_engine.event_engine import EventEngine, Event
from quant_server.db import get_db_session
from quant_server.shared.database.models.business_models import Signal, Order

logger = logging.getLogger(__name__)


def _is_trading_time() -> bool:
    """检查是否为交易时间"""
    # 实现交易时间检查逻辑
    current_time = datetime.now()
    # 简单实现：检查是否为交易日的工作时间
    if current_time.weekday() >= 5:  # 周末
        return False

    if current_time.hour < 9 or current_time.hour >= 15:  # 非交易时间
        return False

    return True


def _map_signal_to_direction(signal_type: str) -> Optional[str]:
    """映射信号类型到订单方向"""
    signal_type_lower = signal_type.lower()

    if signal_type_lower in ['buy', 'long', 'b']:
        return "BUY"
    elif signal_type_lower in ['sell', 'short', 's']:
        return "SELL"
    elif signal_type_lower in ['cover', 'close_long', 'cl']:
        return "COVER"
    elif signal_type_lower in ['cover_short', 'close_short', 'cs']:
        return "COVER_SHORT"
    else:
        return None


class SignalEngine:
    """信号引擎 - 负责交易信号处理和风险控制"""

    def __init__(self, main_engine, event_engine: EventEngine):
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.session = get_db_session()
        self.signals = {}

        # 注册事件处理
        event_engine.register("strategy_signal", self.process_strategy_signal)
        event_engine.register("risk", self.process_risk_event)  # 监听风控事件

        logger.info("信号引擎初始化完成")

    def process_strategy_signal(self, event: Event):
        """处理策略信号事件"""
        signal_data: SignalData = event.data

        try:
            # 信号风险检查
            if not self._check_signal_risk(signal_data):
                logger.warning(f"信号未通过风险检查: {signal_data}")
                return

            # 信号聚合处理
            aggregated_signal = self._aggregate_signals(signal_data)

            # 生成交易指令
            if aggregated_signal and self._should_generate_order(aggregated_signal):
                order_instruction = self._generate_order_instruction(aggregated_signal)

                # 发布交易指令
                self.event_engine.put(Event("order_instruction", order_instruction))

                # 记录信号
                self._record_signal(aggregated_signal, order_instruction)

                logger.info(f"生成交易指令: {order_instruction}")

        except Exception as e:
            logger.error(f"处理信号失败: {str(e)}", exc_info=True)

    def process_risk_event(self, event: Event):
        """处理风控事件 - 可能影响信号处理"""
        risk_data = event.data

        # 根据风控事件类型调整信号处理
        if risk_data['type'] in ['daily_loss_limit', 'max_drawdown']:
            # 高风险事件，暂停所有信号处理
            self._suspend_signal_processing()
        elif risk_data['type'] == 'position_limit':
            # 仓位限制事件，调整相关信号的仓位计算
            self._adjust_position_sizing(risk_data['data']['symbol'])

    def _check_signal_risk(self, signal: SignalData) -> bool:
        """检查信号风险"""
        # 1. 检查黑名单
        if signal.symbol in self.main_engine.risk_engine.risk_rules["blacklist"]:
            logger.warning(f"信号标的在黑名单中: {signal.symbol}")
            return False

        # 2. 检查ST股票
        if self.main_engine.risk_engine.is_st_stock(signal.symbol):
            logger.warning(f"信号标的为ST股票: {signal.symbol}")
            return False

        # 3. 检查涨跌停
        signal_direction = Direction[signal.signal_type.upper()]
        if self.main_engine.risk_engine.is_limit_price(signal.symbol, signal.price, signal_direction):
            logger.warning(f"信号价格在涨跌停附近: {signal.symbol} @ {signal.price}")
            return False

        # 4. 检查交易时间
        if not _is_trading_time():
            logger.warning("非交易时间产生的信号")
            return False

        return True

    def _aggregate_signals(self, new_signal: SignalData) -> SignalData:
        """信号聚合处理 - 合并同一标的的多重信号"""
        symbol = new_signal.symbol

        if symbol not in self.signals:
            self.signals[symbol] = []

        # 添加新信号
        self.signals[symbol].append(new_signal)

        # 保留最近N个信号
        if len(self.signals[symbol]) > 10:
            self.signals[symbol] = self.signals[symbol][-10:]

        # 计算信号强度加权平均值
        if len(self.signals[symbol]) >= 3:  # 至少3个信号才进行聚合
            # 按时间加权（越近的信号权重越高）
            total_weight = 0
            weighted_direction = 0
            weighted_price = 0
            weighted_strength = 0

            for i, signal in enumerate(self.signals[symbol]):
                weight = i + 1  # 线性权重
                total_weight += weight

                # 方向：买入为1，卖出为-1
                dir_value = 1 if signal.direction == Direction.BUY else -1
                weighted_direction += dir_value * weight

                weighted_price += signal.price * weight
                weighted_strength += signal.strength * weight

            # 计算加权平均值
            avg_direction = Direction.BUY if weighted_direction > 0 else Direction.SELL
            avg_price = weighted_price / total_weight
            avg_strength = weighted_strength / total_weight

            # 创建聚合信号 - 修复参数问题
            aggregated = SignalData(
                strategy_id=new_signal.strategy_id,
                symbol=symbol,
                signal_type= str(avg_direction),
                price=avg_price,
                strength=avg_strength,
                signal_time=datetime.now(),
                reason=f"聚合{len(self.signals[symbol])}个信号"
            )

            return aggregated

        return new_signal  # 信号数量不足，返回原始信号

    def _should_generate_order(self, signal: SignalData) -> bool:
        """判断是否应生成交易指令"""
        # 1. 检查信号强度阈值
        if signal.strength < 0.6:  # 强度低于0.6不交易
            return False

        # 2. 检查最小价格变动
        current_price = self._get_current_price(signal.symbol)
        if current_price and abs(signal.price - current_price) / current_price < 0.005:
            logger.debug("信号价格与当前价格差异太小")
            return False

        # 3. 检查仓位限制
        if not self._check_position_limit(signal):
            return False

        return True

    def _generate_order_instruction(self, signal: SignalData) -> Dict:
        """生成交易指令"""
        # 计算订单数量
        quantity = self._calculate_order_quantity(signal)

        # 构建指令 - 修复参数问题
        instruction = {
            "symbol": signal.symbol,
            "direction": signal.signal_type,
            "price": signal.price,
            "quantity": quantity,
            "order_type": "LIMIT",
            "time_in_force": "DAY",
            "source": "signal_engine",
            "signal_strength": signal.strength,
            "timestamp": datetime.now()
        }

        return instruction

    def _calculate_order_quantity(self, signal: SignalData) -> int:
        """计算订单数量"""
        # 根据信号强度和账户资金计算仓位
        position_ratio = 0.1 * signal.strength  # 最大10%仓位，按信号强度调整

        # 获取当前价格
        current_price = self._get_current_price(signal.symbol)
        if not current_price:
            current_price = signal.price

        # 计算订单金额
        order_value = self.main_engine.total_asset * position_ratio

        # 计算股数
        quantity = int(order_value / current_price / 100) * 100  # 取整百股

        return max(100, quantity)  # 最少100股

    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        # 实现获取当前价格的逻辑
        # 简化实现：实际应从行情服务获取
        try:
            from quant_server.shared.database.models.data_models import StockDaily
            latest_price = self.session.query(StockDaily.close).filter(
                StockDaily.ts_code == symbol
            ).order_by(StockDaily.trade_date.desc()).first()

            return latest_price[0] if latest_price else 0
        except Exception as e:
            logger.error(f"获取当前价格失败: {str(e)}")
            return 0

    def _check_position_limit(self, signal: SignalData) -> bool:
        """检查仓位限制"""
        # 实现仓位限制检查逻辑
        # 简化实现：实际应检查当前持仓和风控规则
        try:
            from quant_server.shared.database.models.business_models import Position
            current_position = self.session.query(Position).filter(
                Position.ts_code == signal.symbol
            ).first()

            if current_position:
                position_ratio = current_position.market_value / self.main_engine.total_asset
                if position_ratio > self.main_engine.risk_engine.risk_rules["max_position_ratio"]:
                    logger.warning(f"仓位已超限: {signal.symbol}")
                    return False

            return True
        except Exception as e:
            logger.error(f"检查仓位限制失败: {str(e)}")
            return True

    def _record_signal(self, signal: SignalData, order_instruction: Dict):
        """记录信号到数据库"""
        user_id = self._get_user_id_from_strategy(signal.strategy_id)
        if not user_id:
            logger.warning(f"无法获取策略 {signal.strategy_id} 的用户ID，使用默认用户")
            user_id = 1  # 默认用户ID，实际应用中应该有更好的处理方式

        direction = _map_signal_to_direction(signal.signal_type)
        if not direction:
            logger.error(f"无法识别的信号类型: {signal.signal_type}")
            return

        order_quantity = order_instruction.get("quantity", 0)
        if order_quantity <= 0:
            logger.warning(f"订单数量无效: {order_quantity}, 不创建订单记录")
            return

        order_price = order_instruction.get("price", signal.price)

        db_signal = Signal(
            strategy_id=getattr(signal, 'strategy_id', 'unknown'),
            ts_code=signal.symbol,
            signal_type=signal.signal_type,
            signal_time=signal.signal_time,
            price=Decimal(str(signal.price)) if signal.price else None,
            strength=Decimal(str(signal.strength)) if signal.strength else None,
            reason=signal.reason,
            created_at=datetime.now()
        )
        order = Order(
            order_id=f"order_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{signal.symbol}",
            user_id=user_id,
            strategy_id=signal.strategy_id,
            ts_code=signal.symbol,
            order_type=order_instruction.get("order_type", "LIMIT"),
            direction=direction,
            price=Decimal(str(order_price)) if order_price else None,
            volume=order_quantity,
            status="submitted",
            submitted_at=datetime.now()
        )

        try:
            self.session.add(db_signal)
            self.session.add(order)
            self.session.commit()
        except Exception as e:
            logger.error(f"记录信号失败: {str(e)}")
            self.session.rollback()

    def _suspend_signal_processing(self):
        """暂停信号处理"""
        # 清空当前信号缓存
        self.signals.clear()
        logger.warning("信号处理已暂停（因风控事件）")

    def _adjust_position_sizing(self, symbol: str):
        """调整仓位计算（因风控事件）"""
        # 减少相关标的的仓位计算
        if symbol in self.signals:
            for signal in self.signals[symbol]:
                signal.strength *= 0.5  # 降低信号强度
            logger.info(f"已调整 {symbol} 的信号强度（因仓位限制）")

    def _get_user_id_from_strategy(self, strategy_id: str) -> Optional[int]:
        """从策略ID获取用户ID"""
        try:
            from quant_server.shared.database.models.business_models import Strategy
            strategy = self.session.query(Strategy).filter(Strategy.id == strategy_id).first()
            return strategy.user_id if strategy else None
        except Exception as e:
            logger.error(f"获取策略用户ID失败: {str(e)}")
            return None